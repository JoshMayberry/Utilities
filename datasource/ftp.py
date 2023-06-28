import io
import os
import sys
import logging
import zipfile
import datetime
import contextlib

import pandas
import pysftp

import PyUtilities.common
from PyUtilities.datasource.common import config

@contextlib.contextmanager
def getConnection(login_user=None, login_password=None, login_host=None, *, connection=None, configKwargs=None, **kwargs):
	""" Retuns an object to use for connecting to an FTP server.

	Example Input: getConnection()
	"""

	if (connection is not None):
		yield connection
		return

	login_host = login_host or config("host", "ftp_ma_vineyards", **(configKwargs or {}))
	login_user = login_user or config("user", "ftp_ma_vineyards", **(configKwargs or {}))
	login_password = login_password or config("password", "ftp_ma_vineyards", **(configKwargs or {}))

	options = pysftp.CnOpts()
	options.hostkeys = None

	with pysftp.Connection(host=login_host, username=login_user, password=login_password, cnopts=options) as _connection:
		yield _connection

def select(*args, multifile_method="separate", output_type="python", include_info=False, **kwargs):
	""" Convinence function for *yield_select*.
	Can merge pandas frames into one.

	Example Input: select("Feeds")
	Example Input: select("Feeds", include_info=True)
	Example Input: select("Feeds", multifile_method="append")
	"""

	if (include_info and (multifile_method != "separate")):
		raise ValueError("*include_info* cannot be true if *multifile_method* is not 'separtate'")

	answer = tuple(yield_select(*args, include_info=include_info, output_type=output_type, **kwargs))
	if (multifile_method == "separate"):
		return answer

	match output_type:
		case "python":
			# See: https://pandas.pydata.org/pandas-docs/stable/user_guide/merging.html
			return pandas.concat(answer, join="outer", ignore_index=True, sort=False)

		case _:
			raise KeyError(f"Unknown *multifile_method* '{multifile_method}' for an *output_type* '{output_type}'")

def yield_select(folder, filename=None, *, input_type="csv", output_type="python", filterData=None, filterData_pre=None, modifyData=None, include_info=False, pandasKwargs=None, **kwargs):
	""" Gets data from an ftp server.

	Example Input: yield_select("Feeds")
	"""

	def formatData(data_bytes, is_excel):
		if (output_type == "bytes"):
			yield data_bytes
			return

		if (is_excel):
			if (output_type == "str"):
				raise NotImplementedError("Returning a string representation of an excel file")
			
			yield pandas.read_excel(data_bytes)
			return

		try:
			data_str = data_bytes.decode()
		except UnicodeDecodeError:
			# try:
			data_str = data_bytes.decode(encoding="Windows-1252")
			# except UnicodeDecodeError:
			# 	import chardet
			# 	data_str = data_bytes.decode(encoding=chardet.detect(data_bytes)["encoding"])
		
		if (output_type == "str"):
			yield data_str
			return

		with io.StringIO(data_str) as handle_str:
			if (output_type == "handle_str"):
				yield handle_str
				return

			if (output_type != "python"):
				raise KeyError(f"Unknown *output_type* '{output_type}'")

			match input_type:
				case "csv":
					frame = pandas.read_csv(handle_str, **pandasKwargs)

				case "excel":
					frame = pandas.read_excel(handle_str, **pandasKwargs)

				case "json":
					frame = pandas.read_json(handle_str, orient="records", lines=False, **pandasKwargs)

				case _:
					raise KeyError(f"Unknown *input_type* '{input_type}'")

			if (modifyData):
				logging.info("Modifying data from ftp server...")
				for myFunction in PyUtilities.common.ensure_container(modifyData):
					if (myFunction is not None):
						response = myFunction(frame)
						if (response is not None):
							frame = response

			yield frame

	def yieldData(path, info):
		logging.info(f"Getting ftp contents for '{path}'...")

		if (output_type == "handle_binary_noClose"):
			handle_bytes = io.BytesIO()
			connection.getfo(path, handle_bytes)
			yield handle_bytes
			return

		is_excel = (path.endswith("xlsx") or (input_type == "excel"))
		is_zip = path.endswith("zip")

		with io.BytesIO() as handle_bytes:
			connection.getfo(path, handle_bytes)

			if (not is_zip):
				if (output_type == "handle_bytes"):
					yield handle_bytes
				else:
					yield formatData(handle_bytes.getvalue(), is_excel=is_excel)
				return

			handle_zip = zipfile.ZipFile(handle_bytes)
			if (output_type == "handle_zip"):
				yield handle_zip
				return

			with handle_zip:
				for _info in handle_zip.infolist():
					if (filterData and not filterData(_info)):
						continue

					if (_info.is_dir()):
						raise NotImplementedError("directory inside zipfile")

					if ("zip__path" not in info):
						info["zip__path"] = info["path"]
						info["zip__size"] = info["size"]
						info["zip__filename"] = info["filename"]
						info["zip__date_modified"] = info["date_modified"]
						info["zip__date_modified_timestamp"] = info["date_modified_timestamp"]

					info["path"] = f"{info['zip__path']}/{_info.filename}"
					info["size"] = _info.file_size
					info["filename"] = _info.filename
					info["date_modified"] = _info.date_time
					info["date_modified_timestamp"] = None

					with handle_zip.open(_info.filename) as myfile:
						if (output_type == "handle_bytes"):
							yield myfile
						else:
							yield formatData(myfile.read(), is_excel=(is_excel or _info.filename.endswith("xlsx")))


	def makeInfo(path, catalogue=None):
		logging.info(f"Getting ftp info for '{path}'...")
		if (catalogue is None):
			catalogue = connection.lstat(path)

		return {
			"path": path,
			"filename": getattr(catalogue, "filename", os.path.basename(path)),
			"size": catalogue.st_size,
			"date_modified_timestamp": catalogue.st_mtime,
			"date_modified": datetime.datetime.fromtimestamp(catalogue.st_mtime),
			"mode": catalogue.st_mode,
			"gid": catalogue.st_gid,
			"uid": catalogue.st_uid,
		}

	########################

	pandasKwargs = pandasKwargs or {}
	
	pathList = []
	with getConnection(**kwargs) as connection:
		for _folder in PyUtilities.common.ensure_container(folder):
			for _filename in ((filename,) if (filename) else connection.listdir(os.path.join(connection.pwd, _folder).replace("\\", "/"))):
				pathList.append(os.path.join(connection.pwd, _folder, _filename).replace("\\", "/"))

	# Avoid paramiko.ssh_exception.SSHException between files
	for path in pathList:
		if (filterData_pre and not filterData_pre(path)):
			continue

		# TODO: Only make a new connection after a certain time has passed
		with getConnection(**kwargs) as connection:

			info = makeInfo(path)
			if (filterData and not filterData(info)):
				continue

			for item in yieldData(path, info):
				if (include_info):
					yield (item, info)
					continue

				yield item
