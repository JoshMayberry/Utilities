import os
import sys
import json
import time
import logging
import datetime
import requests
import dateutil.relativedelta

import pandas

import PyUtilities.common
import PyUtilities.datasource.s3
import PyUtilities.datasource.postgres
from PyUtilities.datasource.common import config

def getConnection(*args, connection=None, **kwargs):
	""" Retuns an object to use for connecting to Formsite.

	Example Input: getConnection()
	"""

	if (connection is not None):
		return connection

	return FormsiteConnection(*args, **kwargs)

def select(form_code, **kwargs):
	""" Yields the unformatted data for a form from Formsite

	form_code (str or tuple) - The form code of the form to return data for 
		- If tuple: Will get the data from each form code in the list

	Example Input: select_unformatted("wjsrave6n6")
	Example Input: select_unformatted("rf1gmwaueh", view=101)
	Example Input: select_unformatted("wjsrave6n6", output_type="raw")
	"""

	connection = getConnection(**kwargs)

	data = []
	for _form_code in PyUtilities.common.ensure_container(form_code):
		data.append(connection.getForm(_form_code, **kwargs))

	return data

def uploadS3(row, form_code=None, *, imageCheck=True, connection=None):
	""" Uploads the given data into Amazon S3 and returns meta data about the upload.

	Example Input: doUpload({ url: www.lorem.com/ipsum.png })
	"""

	raise NotImplementedError("Update to use the new method for s3 uploading")

	form_code = form_code or row.get("form_code", None) or "Unknown"

	with PyUtilities.datasource.s3.getConnection(connection=connection) as _connection:
		url = row["url"]
		if (not url.startswith("http")):
			logging.warning(f"URL was missing http; appending it to '{url}'")
			url = f"https://fs8.formsite.com/e1SwO6/files/{url}"

		result = PyUtilities.datasource.s3.insert(url, f"formsite/{form_code}", connection=_connection, imageCheck=imageCheck, metadata={
			key: value for (key, value) in (
				("formsite_url", url),
				("formsite_id", f"{row['id']}"),
				("formsite_code", form_code),
				("location_id", f"{row['location_id']}"),
				("property_id", f"{row.get('property_id')}"),
				("site_id", f"{row.get('site_id')}"),
				("resident_group_id", f"{row.get('resident_group_id')}"),
				("resident_id", f"{row.get('resident_id')}"),
			) if (value is not None)
		})

		row["url_s3"] = result[0]["object_url"]
		row["type"] = result[0].get("contentType", None)
		if (imageCheck):
			row["phash"] = result[0].get("phash", None)

		return row

def uploadS3_frame(frame, column_url, column_location=None, *, location_id=None):
	""" Uploads the urls for each row in the frame into Amazon S3 and puts the new url in the frame.

	Example Input: uploadS3_frame(frame, "lorem", "lorem__location_id")
	"""



class FormsiteConnection():
	def __init__(self, server=None, user=None, bearer=None, cookie=None, configKwargs=None, **kwargs):
		""" A helper object for working with formsite.

		server (str) - Which formsite server to use
		user (str) - Which formsite user account to use
		bearer (str) - The bearer token to use
		cookie (str) - The cookies token to send

		Example Input: FormsiteConnection()
		"""

		configKwargs = configKwargs or {}
		self.user = user or config("user", "formsite", **configKwargs)
		self.server = server or config("server", "formsite", **configKwargs)
		self.bearer = bearer or config("bearer", "formsite", **configKwargs)
		self.cookie = cookie or config("cookie", "formsite", **configKwargs)

		self.url_base = f"https://{self.server}.formsite.com/api/v2/{self.user}"

		self.headers = {
			"Authorization": self.bearer,
			"Cookie": self.cookie,
		}

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass

	def getForm(self, form_code, *, output_type="pipe_values_formatted", **kwargs):
		""" Returns a form object.

		form_code (str) - The form code of the form to return data for or it's base form url

		Example Input: getForm("wjsrave6n6")
		Example Input: getForm(url_base_form)
		Example Input: getForm("wjsrave6n6", output_type="raw")
		"""

		form = self.FormsiteForm(self, form_code, **kwargs)

		match output_type:
			case "raw":
				return form

			case "pipe_labels":
				return form.pipe_labels

			case "pipe_values":
				return form.pipe_values

			case "pipe_values_formatted":
				return form.pipe_values_formatted

			case "expanded":
				return form.expanded

			case "pipe_picture_types":
				return form.pipe_picture_types

			case "picture_combined":
				return form.picture_combined

			case "picture":
				return form.picture_list

			case "picture_s3":
				return form.picture_list_s3

			case _:
				raise NotImplementedError(f"Unknown *output_type* '{output_type}'")

	class FormsiteForm():
		def __init__(self, parent, form_code, *, view=None, view_label=None, photo_label=None, limit=None, page=None, sort_direction=None, imageCheck=None, include_meta=None,
			before_date=None, after_date=None, after_id=None, before_id=None, sort_id=None, search=None, filter_incomplete=None, s3Kwargs=None, json_pipes=True,
			modifyData=None, modifyData_label=None, modifyData_picture=None, modifyData_s3=None, filterData=None, limit_page=None, limit_picture=None, multipleInput=None,
			pictureType_prefix=None, pictureType_suffix="__location_id"
		):
			""" A lazy form result from Formsite.
			Things are calculated as they are requested.
			See: https://support.formsite.com/hc/en-us/articles/360000288594-API

			form_code (str) - The form code of the form to return data for or it's base form url
			view (str) - Which result view to return data for
			page (int) - If None, will return all pages
			sort_direction (str or bool) - If True: "asc"; If False: "desc"

			after_date (str or datetime or dict) - If True: Will get the latest date from *after_date__table*
				- dateFormat (str) - What format to use for parsing *after_date*
				- schema (str) - Which schema to get the date from
				- table (str) - Which table to get the date from
				- column (str) - Which column from *after_date__table* to get the max date from
			before_date (str or datetime or bool) - If True: Will get the earliest date from *after_date__table*

			Example Input: FormsiteForm(self, "wjsrave6n6")
			Example Input: FormsiteForm(self, "rf1gmwaueh", view=101)
			Example Input: FormsiteForm(self, "wjsrave6n6", after_date="2022-05-11")
			Example Input: FormsiteForm(self, "wjsrave6n6", sort_direction=True)
			Example Input: FormsiteForm(self, "wjsrave6n6", after_date={ "schema": "public", "table": "lorem", "column": "date_update" })
			Example Input: FormsiteForm(self, "wjsrave6n6", after_date={ "schema": "public", "table": "lorem", "column": "date_update" }, date_before={ "offset": 30 })
			"""

			self.parent = parent
			self.form_code = form_code

			self.view = view
			self.view_label = view_label
			self.photo_label = photo_label
			self.limit = limit
			self.limit_page = limit_page
			self.limit_picture = limit_picture
			self.page = page
			self.sort_direction = sort_direction
			self.before_date = before_date
			self.after_date = after_date
			self.after_id = after_id
			self.before_id = before_id
			self.sort_id = sort_id
			self.search = search
			self.imageCheck = imageCheck
			self.filter_incomplete = filter_incomplete
			self.s3Kwargs = s3Kwargs
			self.modifyData = modifyData
			self.modifyData_label = modifyData_label
			self.modifyData_picture = modifyData_picture
			self.modifyData_s3 = modifyData_s3
			self.filterData = filterData
			self.include_meta = include_meta
			self.json_pipes = json_pipes
			self.multipleInput = multipleInput
			self.pictureType_prefix = pictureType_prefix or ""
			self.pictureType_suffix = pictureType_suffix or ""

			self.url_base = f"{self.parent.url_base}/forms/{self.form_code}"

			self._pipe_ids = None
			self._pipe_labels = None
			self._pipe_values = None
			self._pipe_values_formatted = None
			self._pipe_picture_types = None
			self._expanded = None
			self._picture_list = None
			self._picture_list_s3 = None

		@classmethod
		def formatDate(cls, value):
			if (pandas.isnull(value)):
				return None

			if ("Z" in value):
				return datetime.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ")

			return datetime.datetime.strptime(value, "%Y-%m-%d %H:%M:%S")

		def yield_label(self, view_label=None):
			def yieldResult(*, nested=0, nested_max=3):
				logging.info(f"Getting pipe labels from url: '{url}'")
				response = requests.request("GET", url, headers=self.parent.headers)

				catalogue = response.json()
				error = catalogue.get("error")
				if (error):
					match (error["status"]):
						case 429: # Too many requests. Wait at least one minute and try again.
							if (nested >= nested_max):
								raise ValueError(error["message"], catalogue)

							logging.info(f"Waiting 90 seconds then trying again ({nested + 1} of {nested_max} tries)")
							time.sleep(90)
							for item in yieldResult(nested=nested + 1):
								yield item
							return

						case _:
							raise ValueError(error["message"], catalogue)

				if ("items" not in catalogue):
					raise ValueError("Unknown JSON response", catalogue)

				for item in catalogue["items"]:
					yield (item["id"], item["label"])

			########################

			url = f"{self.url_base}/items"
			if (view_label is not None):
				url += f"?results_labels={view_label}" 

			for item in yieldResult():
				yield item

		@property
		def pipe_labels(self):
			if (self._pipe_labels is not None):
				return self._pipe_labels

			view_label = None
			if (self.view_label is not None):
				view_label = self.view_label
			elif (self.view is not None):
				view_label = self.view - 101

			self._pipe_labels = dict(self.yield_label(view_label))

			if (self.modifyData_label):
				temp = self.modifyData_label(self._pipe_labels)
				if (temp != None):
					self._pipe_labels = temp

			return self._pipe_labels

		@property
		def pipe_picture_types(self):
			if (self._pipe_picture_types is not None):
				return self._pipe_picture_types
			
			if (self.photo_label is None):
				raise KeyError("*photo_label* required for the 'pipe_picture_types' routine")

			self._pipe_picture_types = { key: value for (key, value) in self.yield_label(self.photo_label) if (value.isnumeric()) }

			return self._pipe_picture_types

		@property
		def pipe_values(self):
			if (self._pipe_values is not None):
				return self._pipe_values

			def getResultPage(page, last_page, *, nested=0, nested_max=3):
				nonlocal url_noPage

				url = f"{url_noPage}&page={page}"
				logging.info(f"Getting pipe values for url {page} of {last_page}: '{url}'")
				response = requests.request("GET", url, headers=self.parent.headers)
				catalogue = response.json()

				error = catalogue.get("error")
				if (error):
					match (error["status"]):
						case 429: # Too many requests. Wait at least one minute and try again.
							if (nested >= nested_max):
								raise ValueError(error["message"], catalogue)

							logging.info(f"Waiting 90 seconds then trying again ({nested + 1} of {nested_max} tries)")
							time.sleep(90)
							for item in getResultPage(page, last_page, nested=nested + 1):
								yield item
							return

						case _:
							raise ValueError(error["message"], catalogue)

				if ("results" not in catalogue):
					raise ValueError("Unknown JSON response", catalogue)

				for item in catalogue["results"]:
					if (self.filter_incomplete and ("date_finish" not in item)):
						continue

					# Account for duplicate entries (that happen when people submit during the query?)
					index = item["id"]
					if (index in self._pipe_ids):
						logging.info(f"Encountered a duplicate entry; {item}")
						continue

					self._pipe_ids[index] = True

					yield item

			def yieldResult():
				if (self.page != None):
					for item in getResultPage(self.page, "?"):
						yield item
					return

				url = f"{self.url_base}/results?{'&'.join(url_filter)}"
				logging.info(f"Getting number of pages: '{url}'")
				response = requests.request("GET", url, headers=self.parent.headers)
				try:
					response.raise_for_status()
				except Exception as error:
					try:
						print(response.json())
					except Exception as error_sub:
						print(error_sub)
					raise error

				last_page = 1 if self.limit else int(response.headers["Pagination-Page-Last"])
				if (self.limit_page and (last_page > self.limit_page)):
					last_page = self.limit_page

				for page in range(1, last_page + 1):
					for item in getResultPage(page, last_page):
						yield item

			def formatDateReference(value, *, reference_date=None):
				if (isinstance(value, dict)):
					if (value.get("reference_date")):
						return getDate(**value)

					return getDate(**{**value, "reference_date": reference_date})

				if (isinstance(value, str)):
					return value

				return self.formatDate(value)

			def getDate(schema=None, table=None, column=None, *, skip=False, timezone=6, reference_date=None, reference_dateFormat=None, dateFormat=None,
				offset=None, where=None, columnJson=None, connection=None, connectionKwargs=None, fallback=None):
				if (skip):
					return

				if (schema and table and column):
					query_sql = f"""SELECT max({table}.{column}{f" ->> '{columnJson}'" if columnJson else ''}) as answer FROM {schema or 'public'}.{table}"""
					if (where):
						query_sql += f" WHERE ({where})"

					response = PyUtilities.datasource.postgres.runSQL(((query_sql, ()),), **{"connection": connection, **(connectionKwargs or {})})

					if (len(response)):
						answer = response[0]["answer"]
						if (answer):
							answer = datetime.datetime.strptime(answer, dateFormat or "%Y-%m-%d %H:%M:%S")
						else:
							answer = fallback
					else:
						answer = fallback

					if (answer is None):
						return
					
				elif (not reference_date):
					return
				elif (isinstance(reference_date, str)):
					answer = datetime.datetime.strptime(reference_date, reference_dateFormat or "%Y-%m-%dT%H:%M:%SZ")
				else:
					answer = reference_date

				if (timezone):
					if (timezone > 0):
						answer += dateutil.relativedelta.relativedelta(hours=timezone)
					else:
						answer += dateutil.relativedelta.relativedelta(hours=(timezone * -1))

				if (offset):
					if (offset > 0):
						answer += dateutil.relativedelta.relativedelta(hours=offset)
					else:
						answer -= dateutil.relativedelta.relativedelta(hours=(offset * -1))

				return answer.strftime("%Y-%m-%dT%H:%M:%SZ")

			######################

			url_noPage = f"{self.url_base}/results?"
			url_filter = []
			after_date = None
			if (self.after_date):
				after_date = formatDateReference(self.after_date)
				if (after_date):
					url_filter.append(f"after_date={after_date}")

			if (self.before_date):
				before_date = formatDateReference(self.before_date, reference_date=after_date)
				if (before_date):
					url_filter.append(f"before_date={before_date}")

			if (self.view is not None):
				url_filter.append(f"results_view={self.view}")

			if (self.limit is not None):
				url_filter.append(f"limit={self.limit}")

			if (self.after_id is not None):
				url_filter.append(f"after_id={self.after_id}")

			if (self.before_id is not None):
				url_filter.append(f"before_id={self.before_id}")

			if (self.sort_id is not None):
				url_filter.append(f"sort_id={self.sort_id}")

			if (self.sort_direction is not None):
				if (isinstance(self.sort_direction, bool)):
					self.sort_direction = "asc" if self.sort_direction else "desc"
				url_filter.append(f"sort_direction={self.sort_direction}")

			if (self.search is not None):
				pass

			url_noPage += "&".join(url_filter)

			self._pipe_ids = {}
			self._pipe_values = tuple(yieldResult())

			if (self.filterData):
				count_previous = len(self._pipe_values)
				self._pipe_values = tuple(filter(self.filterData, self._pipe_values))
				logging.info(f"Filtered formsite results from {count_previous} to {len(self._pipe_values)}")

			if (self.modifyData):
				temp = self.modifyData(self._pipe_values)
				if (temp != None):
					self._pipe_values = temp

			return self._pipe_values

		@property
		def pipe_values_formatted(self):
			if (self._pipe_values_formatted is not None):
				return self._pipe_values_formatted

			def formatValue(row):
				pipe_values = {}
				catalogue = {
					"id": row["id"],
					"form_code": self.form_code,
					"date_start": self.formatDate(row.get("date_start")),
					"date_finish": self.formatDate(row.get("date_finish")),
					"date_update": self.formatDate(row.get("date_update")),
					"pipe_labels": pipe_labels,
					"pipe_values": pipe_values,
				}

				if (pipe_picture_types):
					catalogue["pipe_picture_types"] = pipe_picture_types

				if (self.include_meta is not None):
					if (self.include_meta):
						for key in ["user_ip", "user_referrer", "user_os", "result_status", "user_browser", "user_device"]:
							if (key in row):
								catalogue[key] = row[key]
					else:
						catalogue["metadata"] = json.dumps({ key: row[key] for key in ["user_ip", "user_referrer", "user_os", "result_status", "user_browser", "user_device"] if (key in row) })

				for item in row["items"]:
					if "values" not in item:
						pipe_values[item["id"]] = item["value"]
						continue

					match len(item["values"]):
						case 0:
							pipe_values[item["id"]] = None

						case 1:
							pipe_values[item["id"]] = item["values"][0]["value"]

						case _:
							match (self.multipleInput):
								case None | "raise":
									raise NotImplementedError(f"Multiple formsite values; {item['values']}")
								
								case "first":
									pipe_values[item["id"]] = item["values"][0]["value"]

								case _:
									raise KeyError(f"Unknown formsite *multipleInput* '{self.multipleInput}'")

				catalogue["pipe_combined"] = { pipe_labels[key]: value for (key, value) in pipe_values.items() }

				if (pipe_picture_types):
					catalogue["picture_types"] = { f"{self.pictureType_prefix}{pipe_labels[key]}{self.pictureType_suffix}": value for (key, value) in pipe_picture_types.items() }

				if (not self.json_pipes):
					return catalogue

				catalogue["pipe_combined"] = json.dumps(catalogue["pipe_combined"])
				catalogue["pipe_labels"] = json.dumps(catalogue["pipe_labels"])
				catalogue["pipe_values"] = json.dumps(catalogue["pipe_values"])

				if (pipe_picture_types):
					catalogue["picture_types"] = json.dumps(catalogue["picture_types"])
					catalogue["pipe_picture_types"] = json.dumps(catalogue["pipe_picture_types"])

				return catalogue

			##########################

			# So the logging makes sense- ensure these are calculated first
			pipe_labels = self.pipe_labels
			_pipe_values = self.pipe_values

			pipe_picture_types = None
			if (self.photo_label is not None):
				pipe_picture_types = self.pipe_picture_types

			logging.info("Combineing pipe labels and values")

			if (self.filter_incomplete):
				self._pipe_values_formatted = tuple(formatValue(row) for row in _pipe_values if (("date_start" in row) and ("date_finish" in row)))
			else:
				self._pipe_values_formatted = tuple(formatValue(row) for row in _pipe_values)

			return self._pipe_values_formatted

		@property
		def expanded(self):
			if (self._expanded is not None):
				return self._expanded

			def flatten():
				for row in _pipe_values_formatted:
					if (self.json_pipes):
						yield {
							"id": row["id"],
							"form_code": row["form_code"],
							"date_start": row["date_start"],
							"date_finish": row["date_finish"],
							"date_update": row["date_update"],
							**json.loads(row["pipe_combined"]),
							**(json.loads(row["picture_types"]) if self.photo_label else {}),
						}
					else:
						yield {
							"id": row["id"],
							"form_code": row["form_code"],
							"date_start": row["date_start"],
							"date_finish": row["date_finish"],
							"date_update": row["date_update"],
							**row["pipe_combined"],
							**(row["picture_types"] if self.photo_label else {}),
						}

			#######################

			_pipe_values_formatted = self.pipe_values_formatted

			self._expanded = tuple(flatten())

			return self._expanded

		@property
		def picture_list(self):
			if (self._picture_list is not None):
				return self._picture_list

			def yield_picture(row):
				if (self.filter_incomplete and (not row["date_finish"])):
					return

				def addValue(key, value):
					if (key.isnumeric()):
						pictureList.append((key, value))
						return

					catalogue[key] = value

				####################

				pictureList = []
				catalogue = {
					"id": row["id"],
					"form_code": self.form_code,
					"date_start": self.formatDate(row.get("date_start")),
					"date_finish": self.formatDate(row.get("date_finish")),
					"date_update": self.formatDate(row.get("date_update")),
				}

				for column in row["items"]:
					key = _pipe_labels[column["id"]]
					if (key == "?"):
						print("-- column:", column)
						print("-- row:", row)
						raise KeyError(f"Unformatted key for form {self.form_code}")

					value = column.get("value", None)
					if (value is not None):
						addValue(key, value);
						continue

					
					valueList = column["values"]
					if (not len(valueList)):
						continue
					
					for value in [item["value"] for item in valueList]:
						addValue(key, value)

				for (key, value) in pictureList:
					if (value):
						yield {
							**catalogue,
							"location_id": key,
							"url": value,
						}

			def flatten_pictures():
				i = 0
				for row in _pipe_values:
					myList = tuple(yield_picture(row))
					if (not len(myList)):
						continue

					if (self.limit_picture and (i >= self.limit_picture)):
						return

					i += 1
					for item in myList:
						yield item

			#######################

			logging.info(f"Getting pictures")

			if (self.view is None):
				self.view = 102

			_pipe_labels = self.pipe_labels
			_pipe_values = self.pipe_values

			self._picture_list = tuple(flatten_pictures())

			if (self.modifyData_picture):
				temp = self.modifyData_picture(self._picture_list)
				if (temp != None):
					self._picture_list = temp

			return self._picture_list

		@property
		def picture_list_s3(self):
			if (self._picture_list_s3 is not None):
				return self._picture_list_s3

			with PyUtilities.datasource.s3.getConnection() as connection:
				total = len(self.picture_list)
				for (i, row) in enumerate(self.picture_list, start=1):
					logging.info(f"Converting {i} of {total} formsite url to an s3 url")
					uploadS3(row, self.form_code, imageCheck=self.imageCheck, connection=connection)

			self._picture_list_s3 = self._picture_list

			if (self.modifyData_s3):
				temp = self.modifyData_s3(self._picture_list_s3)
				if (temp != None):
					self._picture_list_s3 = temp

			return self._picture_list_s3
