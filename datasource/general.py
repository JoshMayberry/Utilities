import io
import os
import re
import sys
import json
import time
import math
import boto3
import types
import string
import decimal
import logging
import zipfile
import datetime
import requests
import itertools
import functools
import mimetypes
import traceback
import contextlib
import configparser
import urllib.parse
import dateutil.relativedelta

import bs4
import msal
import numpy
import pandas
import pyodbc
import pysftp
import trello
import asyncio
import dropbox
import dateutil
import netsuite
import openpyxl
import pymsteams

import psycopg2
import psycopg2.extras

import webflowpy.Webflow
import xml.etree.ElementTree

import PyUtilities.common
from PyUtilities.datasource.common import config
import PyUtilities.datasource.postgres

import PyUtilities.logger
import PyUtilities.testing

def yield_fileOutput(data, folder=None, filename=None, *, input_type="csv", can_yield_pandas=False,
	data_hasHeader=False, filterInput_pre=None, filterInput=None, walk_allow=("csv", "xlsx", "xls"), **kwargs):
	""" A generator that yields file handles and their intended destinations based on the input criteria.
	See: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
	See: https://stackoverflow.com/questions/13120127/how-can-i-use-io-stringio-with-the-csv-module/45608450#45608450

	data (any) - What to send to the implemented storage
	folder (str) - What folder path of the container to store the file(s) in
		- If None: Will put the file in the root directory
	filename (str) - What file name to use for the file
		- If None: Will try coming up with a file name
	input_type (str) - How to handle parsing the input data
		- raw: Just send it as recieved
		- json: If it is not a string
		- csv: Make it a csv file
			- Can be a container
		- file: Will use *data* as a filepath to look it up from disk; if there is no file extension it will walk that directory and send all files contained there
			- Can be a container
	walk_allow (tuple) - What file extensions to allow from walking the directory for *input_type*
	can_yield_pandas (bool) - If a pandas frame can be yielded instead of a file buffer

	Example Input: yield_fileOutput([{Lorem: "ipsum"}])
	Example Input: yield_fileOutput([{Lorem: "ipsum"}], folder="rps")
	Example Input: yield_fileOutput({Lorem: "ipsum"}, input_type="json")
	Example Input: yield_fileOutput("C:/lorem/ipsum", input_type="file")
	Example Input: yield_fileOutput("C:/lorem/ipsum", input_type="file", walk_allow=("csv"))
	Example Input: yield_fileOutput(open("lorem.txt", "r"), filename="lorem.txt", input_type="raw")
	Example Input: yield_fileOutput("SELECT * FROM lorem", input_type="postgres")
	Example Input: yield_fileOutput({"query_sql": SELECT * FROM lorem WHERE ipsum = %s", "query_args": (1,), input_type="postgres")
	"""

	def checkIteratorFunction(item):
		dfdsdfs
		_item, _info = (item if data_hasHeader else (item, None))

		if (isinstance(_item, pandas.DataFrame)):
			return False

		return (not isinstance(_item, dict))

	def formatReturn(handle, _info, destination):
		answer = [handle]

		if (data_hasHeader):
			answer.append(_info)

		if (len(answer) > 1):
			return (answer, destination)

		return (handle, destination)

	#####################

	elementCriteria=[(None, dict)] # Array of catalogues; ({"a":1, "b":2}, {"a":3, "b":4})

	if (data_hasHeader):
		elementCriteria.append((2, (None, dict))) # Array of [item, info]; ((frame, {"a":1, "b":2}), (frame, {"a":3, "b":4}))

	found = False
	destination = os.path.join(folder or "", filename or "").replace("\\", "/")
	for item in PyUtilities.common.iensure_container(data, checkIteratorFunction=checkIteratorFunction, elementCriteria=elementCriteria, can_yieldSubContainer=False, subContainer_nestedLimit=1):			
		_input_type = input_type
		
		if (_input_type != "mixed"):
			_item, _info = (item if data_hasHeader else (item, None))
			if (filterInput_pre and (not filterInput_pre(item, _info, destination))):
				continue

		match _input_type:
			case "mixed":
				if (isinstance(item, dict)):
					for _item in yield_fileOutput((item,), folder, filename, input_type="csv", filterInput_pre=filterInput_pre, filterInput=filterInput, can_yield_pandas=can_yield_pandas, walk_allow=walk_allow, data_hasHeader=data_hasHeader, **kwargs):
						found = True
						yield _item
					continue

				if (isinstance(item, pandas.DataFrame)):
					_input_type = "csv"
				elif (isinstance(item, str)):
					_input_type = "file"
				else:
					raise KeyError(f"Unknown mixed type '{item}'")

				for _item in yield_fileOutput(item, folder, filename, input_type=_input_type, filterInput_pre=filterInput_pre, filterInput=filterInput, can_yield_pandas=can_yield_pandas, walk_allow=walk_allow, data_hasHeader=data_hasHeader, **kwargs):
					found = True
					yield _item

			case "raw":
				if (filterInput and (not filterInput(item, _info, destination))):
					continue
				found = True
				yield formatReturn(_item, _info, destination)

			case "json":
				if (not isinstance(_item, str)):
					_item = json.dumps(_item)

				if (not isinstance(_item, bytes)):
					_item = _item.encode("utf8")

				with io.BytesIO(_item) as handle_file:
					handle_file.contentType = "application/json"

					if (filterInput and (not filterInput(handle_file, _info, destination))):
						continue
					found = True
					yield formatReturn(handle_file, _info, destination)

			case "postgres":
				for sqlKwargs in PyUtilities.common.ensure_container(PyUtilities.common.ensure_dict(data, defaultKey="query_sql")):
					response = PyUtilities.datasource.postgres.raw(**sqlKwargs, as_dict=True, **kwargs)

					if (filterInput and (not filterInput(response, _info, destination))):
						continue
					found = True
					yield formatReturn(response, _info, destination)

			case "file":
				if (not isinstance(_item, str)):
					if (isinstance(_item, zipfile.ZipExtFile)):
						handle_bytes = _item
						handle_bytes.contentType = mimetypes.guess_type(_item.name)

						if (not filename):
							destination = os.path.join(folder or "", _item.name)

						if (filterInput and (not filterInput(handle_bytes, _info, destination))):
							continue
						found = True
						yield formatReturn(handle_bytes, _info, destination)
						continue


					raise NotImplementedError("Unknown File type", _item)


					continue

				if (_item.startswith("http")):
					response = requests.request("GET", _item,
						headers={},
						data={},
					)

					handle_bytes = io.BytesIO(response.content)
					handle_bytes.contentType = response.headers['content-type']

					if (filterInput and (not filterInput(handle_bytes, _info, destination))):
						continue
					found = True
					yield formatReturn(handle_bytes, _info, destination)
				else:
					if (os.path.splitext(_item)[1]):
						destination = os.path.join(folder or "", os.path.basename(_item)).replace("\\", "/")
						with open(_item, "rb") as handle_file:
							handle_file.contentType = mimetypes.guess_type(_item)

							if (filterInput and (not filterInput(handle_file, _info, destination))):
								continue
							found = True
							yield formatReturn(handle_file, _info, destination)
							continue

					for (root, _, files) in os.walk(_item):
						for filename_source in files:
							if (filename_source.startswith("~")):
								continue

							if (os.path.splitext(filename_source)[1][1:] not in walk_allow):
								continue

							source = os.path.join(root, filename_source)
							destination = os.path.join(folder or "", filename or filename_source).replace("\\", "/")
							with open(source, "rb") as handle_file:
								handle_file.contentType = mimetypes.guess_type(source)

								if (filterInput and (not filterInput(handle_file, _info, destination))):
									continue
								found = True
								yield formatReturn(handle_file, _info, destination)

			case "csv":
				data_isPandas = isinstance(_item, pandas.DataFrame)

				if (data_isPandas and can_yield_pandas):
					if (filterInput and (not filterInput(_item, _info, destination))):
						continue
					found = True
					yield formatReturn(_item, _info, destination)
					continue

				with io.StringIO(newline="") as handle_csv:
					frame = _item if data_isPandas else pandas.DataFrame(_item)
					
					if (can_yield_pandas):
						if (filterInput and (not filterInput(frame, _info, destination))):
							continue
						found = True
						yield formatReturn(frame, _info, destination)
						continue

					frame.to_csv(handle_csv, header=True, index=False, date_format=r"%Y-%m-%dT%H:%M:%S.%fZ")
					
					handle_bytes = io.BytesIO(handle_csv.getvalue().encode('utf8'))
					handle_bytes.contentType = "text/csv"

					if (filterInput and (not filterInput(handle_bytes, _info, destination))):
						continue
					found = True
					yield formatReturn(handle_bytes, _info, destination)

			case _:
				raise KeyError(f"Unknown *input_type* '{_input_type}'")

	if (not found):
		logging.info(f"No data to found")

def get_frame(*args, include_destination=False, data_hasHeader=False, **kwargs):
	frameList = tuple(yield_frame(*args, include_destination=include_destination, data_hasHeader=data_hasHeader, **kwargs))

	if (include_destination or data_hasHeader):
		return frameList

	match (len(frameList)):
		case 0:
			return pandas.DataFrame()

		case 1:
			return frameList[0]

		case _:
			return pandas.concat(frameList, ignore_index=True).reset_index(drop=True)

def yield_frame(data, *, is_excel=False, is_json=False, typeCatalogue=None, alias=None, remove=None, modifyData=None, replace_nan=True, no_duplicates=None,
	sort_by=None, sortByKwargs=None, sort_by_post=None, sortByPostKwargs=None, filterData_pre=None, filterData=None, filterData_post=None, last_modifier=None,
	string_index=None, string_index__keepValue=None, foreign=None, move=None, connection=None, data_hasHeader=False, can_findNone=False, yieldEmpty=False,
	onError_decimal=None, onError_int=None, etc=None, etc_post=None, etc_skip=None, include_destination=False, remove_allNull=False, modifyData_pre=None, **kwargs):
	""" A generator that yields pandas data frames.
	See: https://stackoverflow.com/questions/46283312/how-to-proceed-with-none-value-in-pandas-fillna/62691803#62691803
	See: https://github.com/pandas-dev/pandas/issues/25288#issuecomment-463054425

	data (str or DataFrame) - A filepath or pandas frame

	Example Input: yield_frame(data="./SyncSource/vineyards/acapdetail.csv")
	Example Input: yield_frame(data="./SyncSource/vineyards/acapdetail.csv", typeCatalogue={"lorem": "datetime"})
	Example Input: yield_frame(data="./SyncSource/vineyards/acapdetail.csv", alias={"Old Name 1": "new_name_1", "Old Name 2": "new_name_2"})
	Example Input: yield_frame(data="./SyncSource/vineyards/acapdetail.csv", remove=("Unecissary Column 1", "Unecissary Column 2"))
	Example Input: yield_frame(data=frame, modifyData=lambda data: [*data, {"lorem": "ipsum"}])
	Example Input: yield_frame(data=[{"lorem": 1, "ipsum": 2}, {"lorem": 3, "ipsum": 4}])
	Example Input: yield_frame(data=frame, foreign={"table": "lorem", "column": "ipsum"})
	Example Input: yield_frame(data=frame, foreign={"table": "lorem", "column": {"ipsum": "dolor"}})
	Example Input: yield_frame(data=frame, foreign={"table": "lorem", "column": {"ipsum": "dolor", "sit": "sit"}})
	Example Input: yield_frame(data=frame, move={"table": "lorem", "column": {"ipsum": "dolor"}})
	Example Input: yield_frame(data=frame, etc=("lorem", "ipsum"))
	Example Input: yield_frame(data=frame, etc={ "status": ("lorem", "ipsum"), "etc": "sit" })
	Example Input: yield_frame(data=frame, etc="lorem", etc_post="ipsum")
	Example Input: yield_frame(data="SELECT * FROM lorem", input_type="postgres")
	"""

	def formatReturn(frame, _info, destination):
		answer = [frame]

		if (data_hasHeader):
			answer.append(_info)

		if (include_destination):
			answer.append(destination)

		if (PyUtilities.logger.debugging):
			with pandas.option_context("display.max_rows", 4, "display.max_columns", None):
				logging.debug(f"\n{frame}")

		if (len(answer) > 1):
			return answer

		return frame

	################################

	dtype = {}
	int_columns = {}
	int_columns_null = {}
	int_columns_list = {}
	datetime_columns = []
	etc_skip = set(PyUtilities.common.ensure_container(etc_skip))
	if (typeCatalogue):
		for (key, value) in typeCatalogue.items():
			match value:
				case "datetime" | "date":
					datetime_columns.append(key)

				case "int":
					dtype[key] = "Int64"
					int_columns[key] = True

				case "int_null":
					dtype[key] = "Int64"
					int_columns[key] = True
					int_columns_null[key] = True

				case "int_list":
					dtype[key] = "Int64"
					int_columns[key] = True
					int_columns_list[key] = True

				case "str" | "string":
					dtype[key] = "str"

				case "decimal":
					dtype[key] = "decimal"

				case "bool":
					dtype[key] = "bool"

				case _:
					raise KeyError(f"Unknown *typeCatalogue['{key}']* '{value}'")

	found = False
	for (item, destination) in yield_fileOutput(data=data, data_hasHeader=data_hasHeader, **{"can_yield_pandas": True, "connection":connection, **kwargs}):
		found = True
		handle_binary, _info = (item if data_hasHeader else (item, None))

		if (isinstance(handle_binary, pandas.DataFrame)):
			frame = handle_binary
		
		elif (is_json):
			frame = pandas.read_json(handle_binary, orient="records", lines=False)
		
		elif (is_excel):
			frame = pandas.read_excel(handle_binary)
		
		elif (isinstance(handle_binary, str)):
			try:
				frame = pandas.read_csv(handle_binary, encoding="Windows-1252")
			except UnicodeDecodeError as error:
				frame = pandas.read_excel(handle_binary) # What if it was an excel file instead of a csv?
		
		elif (isinstance(handle_binary, (list, tuple))):
			frame = pandas.DataFrame(handle_binary)
		
		elif (isinstance(handle_binary, io.BufferedReader)):
			frame = pandas.read_csv(handle_binary, encoding="Windows-1252")
		
		else:
			raise ValueError(f"Unknown data type {type(handle_binary)}")

		if (frame.empty):
			if (yieldEmpty):
				yield formatReturn(frame, _info, destination)
			continue

		if (modifyData_pre):
			logging.info("Modifying input data...")
			for myFunction in PyUtilities.common.ensure_container(modifyData_pre):
				if (myFunction is not None):
					response = myFunction(frame)
					if (response is not None):
						frame = response

		if (last_modifier and ("last_modifier" not in frame.columns)):
			frame["last_modifier"] = last_modifier

		if (alias):
			logging.info("Applying alias to data...")
			frame.rename(alias, axis=1, inplace=True)

		if (no_duplicates):
			# TODO: https://stackoverflow.com/questions/20625582/how-to-deal-with-settingwithcopywarning-in-pandas/53954986#53954986
			logging.info("Removing duplicate rows...")
			frame.drop_duplicates(subset=list(PyUtilities.common.ensure_container(no_duplicates)), inplace=True)

		if (len(dtype.keys()) or len(datetime_columns)):
			logging.info("Converting data types...")

			for key in datetime_columns:
				frame[key] = pandas.to_datetime(frame[key], errors="coerce")

			for (key, type_method) in dtype.items():
				if (key in frame.columns):
					match type_method:
						case "decimal":
							def formatDecimal(value):
								if (value is None):
									return None

								if (isinstance(value, (int, decimal.Decimal))):
									return value

								if (isinstance(value, float)):
									return decimal.Decimal(value)

								if (isinstance(value, str)):
									if (not value):
										return None

									try:
										if ("%" in value):
											value = value.replace("%", "").replace(",", "").strip()
											value = f"{float(value) / 100:.2f}"
										else:
											value = value.replace(",", "").strip()

										return decimal.Decimal(value)
									except (decimal.InvalidOperation, ValueError) :
										if (onError_decimal):
											try:
												return formatDecimal(onError_decimal(value))
											except Exception as error:
												logging.info(f"*onError_decimal* failed while formatting a decimal on '{key}': '{value}'; {error}")
												raise error

										logging.info(f"Invalid decimal format on '{key}': '{value}'")
										return None

								raise NotImplementedError(f"Unknown type conversion: '{type(value)}' to decimal", {"value": value})

							############################

							frame[key] = frame[key].map(formatDecimal)

						case "bool":
							def formatBool(value):
								if (value is None):
									return None

								if (isinstance(value, bool)):
									return value

								if (isinstance(value, int)):
									return bool(value)

								if (isinstance(value, str)):
									if (not value):
										return None

									if (value.isnumeric()):
										return value != "0"

									match value.strip().lower():
										case "yes" | "y" | "on" | "true" | "t":
											return True

										case "no" | "n" | "off" | "false" | "f":
											return False

										case _:
											raise NotImplementedError(f"Unknown boolean format: '{value.lower()}' for '{key}")


								raise NotImplementedError(f"Unknown type conversion: '{type(value)}' to bool", {"value": value})

							############################

							frame[key] = frame[key].map(formatBool).astype(bool)

						case "Int64":
							def formatInt(value):

								if ((value is None) or (value == "")):
									return None

								if (isinstance(value, int)):
									return value

								# Remove any commas
								if (isinstance(value, str)):
									value = value.replace(",", "")

								# Account for floats
								if (isinstance(value, (str, float))):
									if (isinstance(value, float) and numpy.isnan(value)):
										return None

									try:
										value = int(float(value))
									except ValueError:
										if (onError_int):
											return formatInt(onError_int(value))

										logging.info(f"Invalid int format on '{key}': '{value}'")
										return None

								return value

							############################

							if (key in int_columns_list):
								frame[key] = frame[key].astype(str).str.split(",").str[0]
								frame.loc[frame[key] == "nan", key] = 0

							frame[key] = frame[key].map(formatInt)
							if (key not in int_columns_null):
								frame[key] = frame[key].fillna(0) # Do not truncate "int64" to "int32"
							
							if (frame[key].dtype == "float64"):
								frame[key] = frame[key].astype(str).str.split(".").str[0] # Fixes cannot safely cast non-equivalent float64 to int64

							frame[key] = frame[key].astype("Int64")

						case "str":
							# See: https://bobbyhadz.com/blog/python-remove-xa0-from-string#remove-xa0-from-a-string-in-python
							frame[key] = frame[key].replace({numpy.nan: None})
							frame[key] = frame[key].astype(str).str.normalize("NFKC")
							frame[key] = frame[key].replace({"None": None})

						case _:
							frame[key] = frame[key].astype(value)

		if (filterData_pre):
			logging.info("Filtering input data...")
			for myFunction in PyUtilities.common.ensure_container(filterData_pre):
				if (myFunction is not None):
					frame = frame[myFunction(frame)].copy(deep=True)

			if (frame.empty):
				logging.info("Filtered data is now empty")
				if (yieldEmpty):
					yield formatReturn(frame, _info, destination)
				continue

		if (string_index):
			logging.info("Referencing String Index Columns...")
			for key in PyUtilities.datasource.postgres.apply_stringIndex(frame, string_index, string_index__keepValue=string_index__keepValue, connection=connection):
				int_columns[key] = True
				etc_skip.add(key)

		if (foreign):
			logging.info("Migrating Foreign Columns...")
			for foreignKwargs in PyUtilities.common.ensure_container(foreign):
				for key in PyUtilities.datasource.postgres.apply_foreign(frame, **foreignKwargs, connection=connection):
					int_columns[key] = True
					etc_skip.add(key)

		if (move):
			logging.info("Moving Columns...")
			for moveKwargs in PyUtilities.common.ensure_container(move):
				PyUtilities.datasource.postgres.apply_foreign(frame, insert_fk=True, **moveKwargs, connection=connection)

		if (replace_nan):
			for key in int_columns.keys():
				if ((key in frame.columns) and (key not in int_columns_null)):
					frame.fillna({key: 0}, inplace=True)

			# for key in datetime_columns:
			# 	if (key in frame.columns):
			# 		frame.fillna({key: datetime.datetime(1800,1,1)}, inplace=True)

			frame.fillna(numpy.nan, inplace=True)
			frame.replace({numpy.nan: None}, inplace=True)

		if (remove):
			logging.info("Removing Columns...")

			remove_keys = set()
			remove_functions = []
			for key in PyUtilities.common.ensure_container(remove):
				if (isinstance(key, str)):
					if (key in frame.columns):
						remove_keys.add(key)
					continue

				if (PyUtilities.common.inspect.ismethod(key) or PyUtilities.common.inspect.isfunction(key)):
					remove_functions.append(key)

			for myFunction in remove_functions:
				if (myFunction is not None):
					remove_keys.update(filter(myFunction, frame.columns))

			if (len(remove_keys)):
				frame.drop(remove_keys, axis=1, inplace=True)

		if (remove_allNull):
			frame.drop(getNullColumns(frame), axis=1, inplace=True)

		if (True or PyUtilities.logger.debugging):
			with pandas.option_context("display.max_rows", 4, "display.max_columns", None):
				logging.debug(f"\n{frame}")

		if (filterData):
			logging.info("Filtering data...")
			for myFunction in PyUtilities.common.ensure_container(filterData):
				if (myFunction is not None):
					frame = frame[myFunction(frame)].copy(deep=True)

			if (frame.empty):
				logging.info("Filtered data is now empty")
				if (yieldEmpty):
					yield formatReturn(frame, _info, destination)
				continue

		if (sort_by):
			logging.info("Sorting Pre Modified data...")
			frame.sort_values(by=sort_by, axis=0, inplace=True, ascending=True, na_position="last", **(sortByKwargs or {}))
			frame = frame.reset_index(drop=True)

		if (etc):
			logging.info("Moving columns into an etc column...")
			apply_etc(frame, etc, alias=alias, etc_skip=etc_skip)

		if (modifyData):
			logging.info("Modifying data...")
			for myFunction in PyUtilities.common.ensure_container(modifyData):
				if (myFunction is not None):
					response = myFunction(frame)
					if (response is not None):
						frame = response

		if (etc_post):
			logging.info("Moving modified columns into an etc column...")
			apply_etc(frame, etc_post, alias=alias, etc_skip=etc_skip)

		if (sort_by_post):
			logging.info("Sorting Post Modified data...")
			frame.sort_values(by=sort_by_post, axis=1, inplace=True, ascending=True, na_position="last", **(sortByPostKwargs or {}))
			frame = frame.reset_index(drop=True)

		if (filterData_post):
			logging.info("Filtering output data...")
			for myFunction in PyUtilities.common.ensure_container(filterData):
				if (myFunction is not None):
					frame = frame[myFunction(frame)].copy(deep=True)

			if (frame.empty):
				logging.info("Filtered data is now empty")
				if (yieldEmpty):
					yield formatReturn(frame, _info, destination)
				continue

		yield formatReturn(frame, _info, destination)

	if ((not found) and (not can_findNone)):
		raise ValueError("No files were found")

def apply_etc(frame, container, *, alias=None, etc_skip=None, **kwargs):
	""" Moves the given columns into an etc column.

	container (str) - Which column(s) to move into an etc column
		- If dict: The key says what the column should be named
		- If True: Moves all columns not in *alias*

	etc_skip (str) - Which column(s) to not move in if it was going to move in

	Example Input: apply_etc(frame, "lorem")
	Example Input: apply_etc(frame, ("lorem", "ipsum"))
	Example Input: apply_etc(frame, { "status": ("lorem", "ipsum"), "etc": "sit" })
	Example Input: apply_etc(frame, { "status": {"lorem": "lorem", "ipsum": "dolor"} }), "etc": "sit" })
	"""

	def makeEtc(series, catalogue_key, column):
		catalogue = series[column] if (column in series) else {};
		for (key_old, key_new) in catalogue_key.items():
			catalogue[key_new] = series[key_old]

		return catalogue

	##########################

	etc_skip = PyUtilities.common.ensure_container(etc_skip) if etc_skip else ()

	remove_keys = set()
	for (column, catalogue_key) in PyUtilities.common.ensure_dict(container, defaultKey="etc", convertContainer=False).items():
		catalogue_key = PyUtilities.common.ensure_dict(catalogue_key, useAsKey=None, convertContainer=True, useForTrue=True)
		if (catalogue_key is True):
			if (not alias):
				raise NotImplementedError("Moving unaliased columns into etc group without alias being given")

			# Move unaliased columns into etc group
			catalogue_key = tuple(filter(lambda key:  (key not in etc_skip) and (key not in alias.values()), frame.columns.to_list()))


		frame[column] = [makeEtc(series, catalogue_key, column) for (index, series) in frame.iterrows()]
		remove_keys.update(catalogue_key.keys())

	if (len(remove_keys)):
		frame.drop(remove_keys, axis=1, inplace=True)

def getUnique(data, column, *, as_list=True):
	""" Returns a list of the unique values in *data* for *columns*

	data (any) - What to search through
		- Can be a container
	column (str) - What column to search through
		- If list of strings, will return a combined list of all unique values for each item seprately
	as_list (bool) - If the answer should be returned as a list

	Example Input: getUnique(frame, "lorem")
	Example Input: getUnique(frame, ("lorem", "ipsum", "dolor"))
	Example Input: getUnique(frame, "lorem", as_list=False)
	"""

	columnList = list(PyUtilities.common.ensure_container(column))

	data_str = pandas.concat(tuple(item[columnList].copy() for item in PyUtilities.common.ensure_container(data, checkIteratorFunction=lambda item: not isinstance(item, pandas.DataFrame))), ignore_index=True)
	data_unique = pandas.concat(data_str[key].drop_duplicates() for key in columnList).drop_duplicates().dropna()
	
	if (as_list):
		return data_unique.tolist()

	frame = pandas.DataFrame()
	frame["value"] = data_unique

	return frame

def makeEtc(frame, columnList, *, columnName="etc", overwrite=False):
	""" Moves values from *columnList* in *frame* into a JSON object column

	Example Input: makeEtc(frame, ("lorem", "ipsum"))
	Example Input: makeEtc(frame, ("lorem", "ipsum"), overwrite=True)
	Example Input: makeEtc(frame, ("lorem", "ipsum"), columnName="house_info")
	"""

	def myFunction(series):
		catalogue = series[columnName]
		for key in columnList:
			catalogue[key] = series[key]

	#########################

	if (overwrite or (columnName not in frame.columns)):
		frame[columnName] = [{} for i in range(len(frame))]

	frame.apply(myFunction, axis=1)
	frame.drop(list(columnList), axis=1, inplace=True)

	return frame

def yield_chunk(frame, *, chunk_size=1000):
	""" Yields the frame in chunks.
	Use: https://stackoverflow.com/questions/44729727/pandas-slice-large-dataframe-into-chunks/70615708#70615708

	Example Input: yield_chunk(frame)
	Example Input: yield_chunk(frame, chunk_size=50)
	"""

	start = 0
	length = frame.shape[0]

	# If frame is smaller than the chunk, return the frame
	if length <= chunk_size:
		yield frame[:]
		return

	# Yield individual chunks
	while start + chunk_size <= length:
		yield frame[start:chunk_size + start]
		start = start + chunk_size

	# Yield the remainder chunk, if needed
	if start < length:
		yield frame[start:]

def yield_duplicates(frame, subset, *, include_first=True):
	""" Yields the duplicated rows.

	Example Input: yield_duplicates(frame, "property_id")
	Example Input: yield_duplicates(frame, "property_id", include_first=false)
	"""

	if (include_first):
		for (index, frame_grouped) in frame.groupby(subset):
			if (len(frame_grouped) > 1):
				yield frame_grouped
		return

	frame_duplicated = frame[frame.duplicated(subset=subset)]
	if (not len(frame_duplicated)):
		return

	for (index, frame_grouped) in frame_duplicated.groupby(subset):
		yield frame_grouped

def yield_datePair(date_start=None, date_end=None, frequency="D"):
	""" Yields a pair of dates using the given *frequency*
	See: https://pandas.pydata.org/docs/user_guide/timeseries.html#timeseries-offset-aliases

	Example Input: yield_datePair()
	Example Input: yield_datePair(date_start=dateutil.relativedelta.relativedelta(days=1))
	Example Input: yield_datePair(date_end=dateutil.relativedelta.relativedelta(days=30))
	Example Input: yield_datePair(date_end=dateutil.relativedelta.relativedelta(years=1), frequency="MS")
	"""

	if (date_start is None):
		date_start = datetime.datetime.now()
	elif (isinstance(date_start, dateutil.relativedelta.relativedelta)):
		date_start = datetime.datetime.now() - date_start

	if (date_end is None):
		date_end = date_start + dateutil.relativedelta.relativedelta(days=1)
	elif (isinstance(date_end, dateutil.relativedelta.relativedelta)):
		date_end = date_start + date_end

	generator = (item.date() for item in pandas.date_range(start=date_start, end=date_end, freq=frequency))

	previous = next(generator, None)
	for item in generator:
		yield (previous, item)
		previous = item

def getNullColumns(frame, *, invert=False):
	""" Returns a list of columns only full on null values.

	Example Input: getNullColumns(frame)
	"""

	if (invert):
		return frame.columns[~frame.isnull().all()]

	return frame.columns[frame.isnull().all()]
