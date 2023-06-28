import io
import os
import sys
import boto3
import pandas
import logging
import datetime
import requests
import imagehash
import mimetypes
import contextlib
import urllib.parse

import PIL.Image
import xml.etree.ElementTree

import PyUtilities.common
import PyUtilities.datasource.general
import PyUtilities.datasource.postgres
from PyUtilities.datasource.common import config

def lookup_typeId(url, mimeType=None):
	""" Determines what type_id to use for the given attachment

	Example Input: lookup_typeId("https://www.lorem.com/ipsum.png")
	Example Input: lookup_typeId("https://www.lorem.com/ipsum.png", "image/png")
	"""

	if (url is None):
		return 0

	if (mimeType is None):
		if (isinstance(url, str)):
			mimeType = mimetypes.guess_type(url)[0]
		elif (hasattr(url, "contentType")):
			mimeType = url.contentType

	if (mimeType is not None):
		group, sub = mimeType.split("/")

		match (group):
			case "image":
				return 1

			case "application":
				match (sub):
					case "pdf":
						return 2

					case "zip":
						return 8

					case "rtf":
						return 4

			case "text":
				match (sub):
					case "csv":
						return 3

					case "plain":
						return 4

					case "html":
						return 5

					case _:
						return 4
		return 0

	if (not isinstance(url, str)):
		raise NotImplementedError("Non-string given for *url* with no provided *mimeType*")

	extension = os.path.splitext(url)[-1]
	match (extension):
		case "bmp" | "gif" | "jpeg" | "jpg" | "png":
			return 1

		case "pdf":
			return 2

		case "csv":
			return 3

		case "doc" | "docx" | "txt":
			return 4

		case "mp3" | "wav":
			return 6

		case "avi" | "mp4" | "mpeg" | "mpg" | "wmv":
			return 7

		case "zip":
			return 8

		case "xls" | "xlsx":
			return 9

		case "ppt" | "pptx":
			return 10

		case _:
			raise KeyError(f"Unknown file type '{extension}'")

def openURL(url, *, handle_bytes=None, handle_pil=None):
	""" Returns a file handle for the given url.

	Example Input: openURL("https://www.lorem.com/ipsum.png")
	"""

	if (handle_bytes is not None):
		return handle_bytes

	if (isinstance(url, io.BytesIO)):
		return url

	if (isinstance(url, str)):
		if (not url.startswith("http")):
			raise NotImplementedError(f"Cannot find the file '{url}'")

		response = requests.request("GET", url, stream=True, headers={}, data={})
		handle_bytes = io.BytesIO(response.content)
		handle_bytes.contentType = response.headers['content-type']
		return handle_bytes

	if (isinstance(url, PIL.Image.Image)):
		raise SyntaxError("Cannot derive *handle_bytes* from *handle_pil*")

	raise NotImplementedError(f"Unknown file format for '{url}'")

def openPIL(url, *, handle_bytes=None, handle_pil=None):
	""" Returns a PIL handle for the given url.

	Example Input: openPIL("https://www.lorem.com/ipsum.png")
	"""

	if (handle_pil is not None):
		return handle_pil

	if (isinstance(url, PIL.Image.Image)):
		return url

	if (handle_bytes is None):
		handle_bytes = url if (isinstance(url, io.BytesIO)) else openURL(url)

	try:
		return PIL.Image.open(handle_bytes)
	except PIL.UnidentifiedImageError as error:
		pass
	finally:
		handle_bytes.seek(0)

def phash_get(url, *, hashSize=64, handle_bytes=None, handle_pil=None):
	""" Makes a hash for image columns and checks that hash against existing hashes.
	Use: https://medium.com/@somilshah112/how-to-find-duplicate-or-similar-images-quickly-with-python-2d636af9452f

	Example Input: phash_get(handle_pil)
	Example Input: phash_get(handle_bytes)
	Example Input: phash_get("https://www.lorem.com/ipsum.png")
	"""

	if (handle_pil is None):
		handle_pil = openPIL(url, handle_bytes=handle_bytes, handle_pil=handle_pil)
		if (handle_pil is None):
			return ""
	return str(imagehash.phash(handle_pil, hashSize))

def format_payload(url, *, database_formatting=True, formsite_formatting=False, metadata=None, skip_phash=False, handle_bytes=None, handle_pil=None, mime=None, **kwargs):
	""" Formats a payload for Amazon S3.

	Example Input: uploadS3("https://www.lorem.com/ipsum.png", database_formatting=False)
	Example Input: uploadS3("https://www.lorem.com/ipsum.png", database_formatting=False, metadata={"ipsum": 1})
	Example Input: uploadS3("https://www.lorem.com/ipsum.png", database_formatting=False, skip_phash=True)
	Example Input: uploadS3("https://www.lorem.com/ipsum.png", source="dolor", location_id=101)
	"""

	metadata = {**metadata} if metadata else {}

	if (database_formatting):
		# Required Metadata
		for key in ("source", "location_id"):
			if (key not in metadata):
				metadata[key] = PyUtilities.common.requiredArg(kwargs.get(key, None), f"*{key}* is required")

		# Semi-Required Metadata
		found = False
		for key in ("site_id", "property_id", "resident_id", "resident_group_id"):
			if (key in metadata):
				found = True
			elif (key in kwargs):
				found = True
				metadata[key] = kwargs[key]
		if (not found):
			raise KeyError("Missing *site_id*, *property_id*, *resident_id*, and/or *resident_group_id*")

		# Optional Metadata
		if ("comment" in kwargs):
			metadata["comment"] = kwargs["comment"]

		# Computed Metadata
		if ("type_id" not in metadata):
			type_id = kwargs.get("type_id", None)
			if (type_id is None):
				if (mime is None):
					mime = metadata.get("mime") or ((handle_bytes is not None) and hasattr(handle_bytes, "contentType") and handle_bytes.contentType) or mimetypes.guess_type(url)[0]
					metadata["mime"] = mime

				type_id = lookup_typeId(url, mime)
			metadata["type_id"] = type_id

	if (formsite_formatting):
		# Required Metadata
		for key in ("formsite_id", "formsite_form_code", "formsite_date_start", "formsite_date_finish", "formsite_date_update"):
			if (key not in metadata):
				metadata[key] = PyUtilities.common.requiredArg(kwargs.get(key, None), f"*{key}* is required")

		# Computed Metadata
		if ("formsite_url" not in metadata):
			metadata["formsite_url"] = url

	if (not skip_phash):
		try:
			metadata["phash"] = kwargs.get("phash", None) or metadata.get("phash", None) or phash_get(url, handle_bytes=handle_bytes, handle_pil=handle_pil)
		except Exception as error:
			logging.error(error)
			metadata["phash"] = None

	return {key: f"{value}" for (key, value) in metadata.items()}

@contextlib.contextmanager
def getConnection(*args, region=None, access_key=None, secret_key=None, connection=None, configKwargs=None, **kwargs):
	""" Retuns an object to use for connecting to ShowMojo.
	See: https://www.stackvidhya.com/specify-credentials-in-boto3/#passing_credentials_as_parameters

	Example Input: getConnection()
	"""

	if (connection is not None):
		yield connection
		return

	region = region or config("region", "s3", **(configKwargs or {}))
	access_key = access_key or config("access_key", "s3", **(configKwargs or {}))
	secret_key = secret_key or config("secret_key", "s3", **(configKwargs or {}))

	session = boto3.Session(
		aws_access_key_id=access_key,
		aws_secret_access_key=secret_key,
	)

	yield session.client("s3",
		region_name=region,
	)

def insert(url, filepath=None, container=None, *, region=None, acl=None, configKwargs=None, mime=None,
	formsite_formatting=False, database_formatting=True, database_insert=False, connection_postgres=None, connection=None, **kwargs):
	""" Does a PUT request for s3.
	See: https://boto3.amazonaws.com/v1/documentation/api/latest/guide/s3-uploading-files.html

	Example Input: insert("https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w")
	Example Input: insert("https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w", "photos/liquidCat.jpg")
	Example Input: insert("https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w", "photos/liquidCat.jpg", "roots-pictures")
	"""

	acl = acl or config("acl", "s3", **(configKwargs or {}))
	region = region or config("region", "s3", **(configKwargs or {}))
	container = container or config("container", "s3", **(configKwargs or {}))

	if (filepath is None):
		filepath = "unknown"

	if ("." not in filepath):
		if (isinstance(url, str)):
			filepath = os.path.join(filepath, os.path.basename(url).split("?")[0])
		else:
			filepath = os.path.join(filepath, "unknown.txt")
	filepath = filepath.replace('\\', '/')

	with getConnection(configKwargs=configKwargs, connection=connection, **kwargs) as connection_s3:
		handle_bytes = openURL(url)
		handle_pil = openPIL(url, handle_bytes=handle_bytes)

		mime = mime or handle_bytes.contentType or (hasattr(handle_bytes, "contentType") and handle_bytes.contentType) or mimetypes.guess_type(filepath)[0]
		metadata = format_payload(url, database_formatting=database_formatting or database_insert, formsite_formatting=formsite_formatting, mime=mime, handle_bytes=handle_bytes, handle_pil=handle_pil, **kwargs)

		handle_bytes.seek(0)
		logging.info(f"Sending '{url}' to s3")
		response = connection_s3.put_object(Bucket=container, Key=filepath, Body=handle_bytes, Metadata=metadata, ACL=acl)
		response["key"] = filepath
		response["contentType"] = handle_bytes.contentType or mime
		response["object_url"] = f"https://{container}.s3.{region}.amazonaws.com/{urllib.parse.quote(filepath)}" if (container) else f"https://s3.{region}.amazonaws.com/{urllib.parse.quote(filepath)}"
		
		response["metadata"] = metadata

		if (response["ResponseMetadata"]["HTTPStatusCode"] != 200):
			raise ValueError(f"Error uplaoding '{url}' to S3", response)

		answer = {
			**metadata,
			"url": response["object_url"],
			"_response": response,
		}

		if (database_insert):
			return insertPostgres(answer, connection=connection_postgres, **kwargs)
		return answer

debugging_doneOne = False
def series_insertFormsite(series, key, *, database_insert=True, pictureType_prefix=None, pictureType_suffix="__location_id", comment=None, connection=None, connection_postgres=None):
	""" Use with dataframe.apply to upload a picture from formsite to the database.

	EXAMPLE USE
		frame.outside__deck__photo = frame.apply(lambda series: PyUtilities.datasource.s3.series_insertFormsite(series, "outside__deck__photo", connection_postgres=self.connection_postgres, connection=self.connection_s3), axis=1)
	
	Example Input: series_insertFormsite(series, "outside__deck__photo")
	Example Input: series_insertFormsite(series, "outside__deck__photo", database_insert=False)
	Example Input: series_insertFormsite(series, "outside__deck__photo", connection_postgres=self.connection_postgres, connection=self.connection_s3)
	"""
	global debugging_doneOne

	url = series[key]
	if (url is None):
		return

	if (debugging_doneOne):
		return

	debugging_doneOne = True

	formsite_form_code = series.get("formsite_form_code")

	answer = PyUtilities.datasource.s3.insert(
		skip_phash=False,
		formsite_formatting=True,
		database_formatting=True,
		database_insert=database_insert,

		connection=connection,
		connection_postgres=connection_postgres,
		
		url=url,
		filepath=f"formsite/{formsite_form_code}",
		source=f"formsite: {formsite_form_code}",
		location_id=series[f"{pictureType_prefix or ''}{key}{pictureType_suffix or ''}"],
		
		site_id=series.get("site_id") or 0,
		property_id=series.get("property_id") or 0,
		resident_id=series.get("resident_id") or 0,
		resident_group_id=series.get("resident_group_id") or 0,
		
		mime=None,
		comment=comment,
		metadata={
			"formsite_id": series.get("formsite_id"),
			"formsite_form_code": formsite_form_code,
			"formsite_date_start": series.get("formsite_date_start"),
			"formsite_date_finish": series.get("formsite_date_finish"),
			"formsite_date_update": series.get("formsite_date_update"),
			"formsite_url": url,
		},
	)[0]

	if (database_insert):
		return answer["attachment_id"]

	return answer

def frame_insertFormsite(frame, key, *, database_insert=True, pictureType_prefix=None, pictureType_suffix="__location_id", comment=None, connection=None, connection_postgres=None, **kwargs):
	""" Updates the frame with the s3 url or attachment_id.

	Example Input: frame_insertFormsite(frame, "outside__deck__photo", database_insert=True, connection_postgres=self.connection_postgres, connection=self.connection_s3)
	"""

	with PyUtilities.datasource.postgres.getConnection(connection=connection_postgres, **kwargs) as _connection_postgres:
		with PyUtilities.datasource.s3.getConnection(connection=connection, **kwargs) as _connection:
			frame[key] = frame.apply(lambda series: series_insertFormsite(series, key, database_insert=database_insert, connection_postgres=_connection_postgres, connection=_connection), axis=1)
			frame.drop(f"{pictureType_prefix or ''}{key}{pictureType_suffix or ''}", axis=1, inplace=True)

	return frame

attachment_list_columns = {
	"location_id": "int",
	"type_id": "int",
	"source": "str",
	"url": "str",
	"comment": "str",
	"last_modifier": "str",
	"site_id": "int",
	"property_id": "int",
	"resident_id": "int",
	"resident_group_id": "int",
	"phash": "str",
}

def formatPostgres(row, *, method="normal"):
	""" Formats data to be inserted into postgres

	Example Input: formatPostgres(series)
	Example Input: formatPostgres([row_1, row_2])
	Example Input: formatPostgres(PyUtilities.datasource.s3.insert(*args, **kwargs))
	Example Input: formatPostgres({"url": url, "type_id": 1, "location_id": 0, "property_id": property_id, "phash": phash})
	"""

	if (not isinstance(row, dict)):
		if (isinstance(row, pandas.Series)):
			row = row.to_dict()

		elif (isinstance(row, pandas.DataFrame)):
			raise NotImplementedError("Call `.apply(formatPostgres, axis=1)` instead of passing in a Data Frame")

		elif (isinstance(row, (tuple, list, set))):
			answer = []
			for item in row:
				answer.append(formatPostgres(row))
			return answer

		else:
			raise NotImplementedError(f"Unknown format for *row*: '{type(row)}'")

	etc = {}
	catalogue = {}
	catalogue["etc"] = etc
	if ("last_modifier" not in row):
		catalogue["last_modifier"] = PyUtilities.datasource.postgres.get_last_modifier(routineName="S3", method=method)

	for (key, value) in row.items():
		if (key in attachment_list_columns):
			catalogue[key] = value
			continue

		if (key == "_response"):
			continue

		if (key == "etc"):
			etc = {**etc, **value}
			continue

		etc[key] = value

	return catalogue

def insertPostgres(data, *, method="normal", **kwargs):
	""" Adds the given information to the postgres database.
	Assumes it has already been uploaded to S3.
	See: https://stackoverflow.com/questions/3494906/how-do-i-merge-a-list-of-dicts-into-a-single-dict/50179453#50179453

	Example Input: insertPostgres(series)
	Example Input: insertPostgres([row_1, row_2])
	Example Input: insertPostgres(PyUtilities.datasource.s3.insert(*args, **kwargs))
	Example Input: insertPostgres({"url": url, "type_id": 1, "location_id": 0, "property_id": property_id, "phash": phash})
	Example Input: insertPostgres(frame, returning=None)
	"""

	with PyUtilities.datasource.postgres.getConnection(**kwargs) as connection:
		(values_post, data_post) = PyUtilities.datasource.postgres.insert(
			data=formatPostgres(data, method=method),
			connection=connection,
			schema="attachment",
			table="list",
			method="upsert",
			reset_incrementer="attachment_id",
			returning=("attachment_id", "url"),
			typeCatalogue={
				"etc": "json",
			},
			upsert_constraint="list_un",
		)

		return tuple({key: value for item in myList for (key, value) in item.items()} for myList in zip(values_post, data_post))

class Raw():
	""" An attempt at interacting with S3 without a specialized library. """

	@classmethod
	def _getToken(cls, url, method="PUT", *, metadata=None, contentType=None, access_key=None, secret_key=None, configKwargs=None):
		""" Returns an s3 authentication string.
		See: https://docs.aws.amazon.com/AmazonS3/latest/userguide/RESTAuthentication.html
		See: https://docs.aws.amazon.com/AmazonS3/latest/userguide/access-policy-language-overview.html

		Example Input: _getToken("/roots-formsite/", "GET")
		Example Input: _getToken("/roots-formsite/photos/puppy.jpg", "GET")
		Example Input: _getToken("/roots-formsite/photos/puppy.jpg", contentType="image/jpeg")
		"""

		access_key = access_key or config("access_key", "s3", **(configKwargs or {}))
		secret_key = secret_key or config("secret_key", "s3", **(configKwargs or {}))

		url = url.replace('\\', '/')
		timestamp = datetime.datetime.now().strftime("%a, %d %b %Y %H:%M:%S %z")
		if (("+" not in timestamp) or ("-" not in timestamp)):
			timestamp += "+0000"

		string_to_sign = f"{method}\n{metadata or ''}\n{contentType or ''}\n{timestamp}\n{url}"
		signature = base64.encodebytes(hmac.new(secret_key.encode("utf-8"), string_to_sign.encode("utf-8"), hashlib.sha1).digest()).strip()
		return (f"AWS {access_key}:{signature.decode()}", timestamp)

	@classmethod
	def select(cls, filepath=None, container=None, *, queryParams=None, region=None, public=True, configKwargs=None, **kwargs):
		""" Does a GET request for s3.
		See: https://docs.aws.amazon.com/AmazonS3/latest/userguide/RESTAPI.html

		Example Input: select()
		Example Input: select("photos/liquidCat.jpg")
		Example Input: select("photos/liquidCat.jpg", "roots-formsite")
		Example Input: select("photos/liquidCat.jpg", "roots-formsite", public=False)
		Example Input: select(container="roots-formsite")
		Example Input: select(container="roots-formsite", queryParams="prefix=photos&max-keys=50&marker=liquid")
		"""

		region = region or config("region", "s3", **(configKwargs or {}))
		container = container or config("container", "s3", **(configKwargs or {}))

		url = f"https://{container}.s3.{region}.amazonaws.com" if (container) else f"https://s3.{region}.amazonaws.com"
		if (filepath):
			url = os.path.join(url, filepath)

		if (queryParams):
			url += f"?{queryParams}"

		headers = {}
		if (not public):
			raise NotImplementedError("S3 Select for non-public containers")
			url_cannonized = os.path.join("/", container or "", filepath or "")

			authorization, timestamp = cls._getToken(
				url=url_cannonized,
				method="GET",
				**kwargs,
			)

			headers={
				"Date": timestamp,
				"x-amz-date": timestamp,
				"Authorization": authorization,
			}

		response = requests.request("GET", url.replace("\\", "/"), headers=headers)
		response.raise_for_status()

		if (response.headers.get("Content-Type") == "application/xml"):
			return xml.etree.ElementTree.fromstring(response.text)

		return response.text

	@classmethod
	def insert(cls, source, filepath=None, container=None, *, region=None, public=True, configKwargs=None, **kwargs):
		""" Does a PUT request for s3.
		See: https://docs.aws.amazon.com/AmazonS3/latest/userguide/RESTAPI.html

		Example Input: insert("https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w")
		Example Input: insert("https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w", "photos/liquidCat.jpg")
		Example Input: insert("https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w", "photos/liquidCat.jpg", "roots-pictures")
		Example Input: insert("https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w", "photos/liquidCat.jpg", "roots-pictures", public=False)
		"""

		region = region or config("region", "s3", **(configKwargs or {}))
		container = container or config("container", "s3", **(configKwargs or {}))

		url = f"https://{container}.s3.{region}.amazonaws.com" if (container) else f"https://s3.{region}.amazonaws.com"

		headers = {}
		if (not public):
			raise NotImplementedError("S3 Insert for non-public containers")
			url_cannonized = os.path.join("/", container or "", filepath or "")

			authorization, timestamp = cls._getToken(
				url=url_cannonized,
				method="PUT",
				**kwargs,
			)

			headers={
				"Date": timestamp,
				"x-amz-date": timestamp,
				"Authorization": authorization,
			}

		url = url.replace("\\", "/")
		logging.info([f"Sending file to s3: '{url}'", headers])
		response = requests.request("PUT", url, headers=headers)
		response.raise_for_status()

		if (response.headers.get("Content-Type") == "application/xml"):
			return xml.etree.ElementTree.fromstring(response.text)

		return response.text

if (__name__ == "__main__"):
	# PyUtilities.logger.logger_debug()
	# PyUtilities.logger.logger_info()
	
	data = insert(
		url="https://images.squarespace-cdn.com/content/v1/5897942717bffc479b6d245b/1578887088518-13ON8E15UJGXWVS0NUKI/cats+liquid+1.jpg?format=500w",
		filepath="test",
		source="testing",
		property_id=12693,
		site_id=10257386,
		location_id=0,
		metadata={"lorem": 123},
		database_insert=True,
	)

	print(data)
