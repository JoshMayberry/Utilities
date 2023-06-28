import io
import os
import sys
import logging

import pandas
from azure.storage.blob import BlobServiceClient
import azure.core.exceptions

import PyUtilities.common
import PyUtilities.testing
import PyUtilities.datasource.general
from PyUtilities.datasource.common import config

def getConnection(container, *, account_name="rpbireporting", account_key=None, configKwargs=None, connection=None, **kwargs):
	""" Returns a blob storage connection.

	account_name (str) - The name of the account to connect to
	account_key (str) - THey key of the account to connect to

	Example Input: getConnection("treehouse")
	Example Input: getConnection("ma-extract", account_name="birdeye01reporting")
	"""

	if (connection is not None):
		return connection

	account_key = account_key or config("account_key", "blob", **(configKwargs or {}))

	logging.info(f"Making blob storage connection to '{container}'...")
	connection_string = ";".join([
		"DefaultEndpointsProtocol=https",
		f"AccountName={account_name}",
		f"AccountKey={account_key}",
		f"BlobEndpoint=https://{account_name}.blob.core.windows.net/",
		f"QueueEndpoint=https://{account_name}.queue.core.windows.net/",
		f"TableEndpoint=https://{account_name}.table.core.windows.net/",
		f"FileEndpoint=https://{account_name}.file.core.windows.net/;",
	])

	logging.debug(f"Connection string: '{connection_string}'")
	return BlobConnection(connection_string, container)

def insert(data, container="postgres", folder=None, filename=None, *, method="upsert", **kwargs):
	""" Sends data to an Azure blob storage.

	data (any) - What to send to the blob storage
	container (str) - Which blob storage container to store the blob(s) in
	folder (str) - What folder path of the container to store the blob(s) in
		- If None: Will put the file in the root directory
	filename (str) - What file name to use for the blob
		- If None: Will try coming up with a file name
	method (str) - How to handle sending the data
		- upsert: Update existing blob in the folder, otherwise create a new blob
		- insert: Try adding it and throw an error if it alrteady exists
		- drop: Drop all blobs in the folder and insert new blobs

	Example Input: insert([{Lorem: "ipsum"}])
	Example Input: insert([{Lorem: "ipsum"}], container="treehouse", folder="rps")
	Example Input: insert({Lorem: "ipsum"}, input_type="json")
	Example Input: insert("C:/lorem/ipsum", input_type="file")
	Example Input: insert("C:/lorem/ipsum", input_type="file", walk_allow=("csv", "xlsx"))
	Example Input: insert(open("lorem.txt", "r"), filename="lorem.txt", input_type="raw")
	"""

	connection = getConnection(container, **kwargs)

	is_upsert = False
	existing = connection.ls_files(folder or "")
	if (len(existing)):
		match method:
			case "drop":
				logging.info(f"Dropping the following from '{folder}': {existing}...")
				for filename_source in existing:
					try:
						connection.rm(f"{folder}/{filename_source}")
					except azure.core.exceptions.ResourceNotFoundError as error:
						pass

			case "upsert":
				is_upsert = True

			case "insert":
				pass

			case _:
				raise KeyError(f"Unknown *method* '{method}'")

	found = False
	for (handle_binary, destination) in PyUtilities.datasource.general.yield_fileOutput(data=data, folder=folder, filename=filename, **kwargs):
		if (is_upsert):
			for filename_source in existing:
				if (destination.endswith(filename_source)):
					logging.info(f"Dropping '{filename_source}' from '{folder}'...")
					try:
						connection.rm(f"{folder}/{filename_source}")
					except azure.core.exceptions.ResourceNotFoundError as error:
						pass
					break

		found = True
		logging.info(f"Uploading blob to '{destination}'...")
		connection.client.upload_blob(name=destination, data=handle_binary.read())

	if (not found):
		raise ValueError("No files were found")

	return True

def select(container="postgres", folder=None, filename=None, *,
	input_type="csv", output_type="python", as_dict=True,
	multifile_method="append", force_list=False, **kwargs):
	""" Returns data from blob storage

	container (str or tuple)) - Which blob storage container to store the blob(s) in
		- If tuple: Will look in all container names given
	folder (str or tuple)) - What folder path of the container to store the blob(s) in
		- If None: Will put the file in the root directory
		- If tuple: Will look in all folder names given
	filename (str or tuple) - What file name to use for the blob
		- If None: Will try coming up with a file name
		- If tuple: Will look for all files given
	output_type (str) - How to return what is in the blob storage
		- client: Pre-download file handle
		- handle_bin: Post-download file handle
		- bin: The raw binary string contents of the blob
		- handle_str: Stringified file handle
		- str: The raw string contents of the blob
		- python: Make it into a python object
	input_type (str) - How to interpret the blob when *output_type* is 'python'
		- csv: A list of dictionaries
	as_dict (bool) - If csv file contrents sholuld be returnded as a list of dictionaries
	multifile_method (str) - How to handle when multiple files are requested (Only applies to the 'python' *output_type*; all other output types will use *multifile_method* as 'separate')
		- append: Add the results from all following files to the ones from the first
		- separate: Each result is a separate item in a list
	force_list (bool) - If empty lists or single item lists should still be rreturned as lists

	Example Input: select(container="ma-extract", folder="treehouse", filename="Resident.csv")
	Example Input: select(container="ma-extract", folder="treehouse", filename="Resident.csv", as_dict=False)
	Example Input: select(container="ma-extract", folder="treehouse", filename="Resident.csv", output_type="handle_str")
	Example Input: select(container="ma-extract", folder="[treehouse", "vineyards"], filename="Resident.csv")
	Example Input: select(container="ma-extract", folder="[treehouse", "vineyards"], filename="Resident.csv", multifile_method="separate")
	Example Input: select(container="ma-extract", folder="treehouse", filename="Resident.csv", force_list=True)
	"""

	def yieldFile():
		for _container in PyUtilities.common.ensure_container(container, checkIteratorFunction=lambda item: not isinstance(item, pandas.DataFrame)):
			connection = getConnection(_container, **kwargs)

			for _folder in PyUtilities.common.ensure_container(folder or ("")):
				for _filename in PyUtilities.common.ensure_container(filename or ("")):
					destination = os.path.join(_folder, _filename)
					logging.info(f"Getting blob from '{destination}'...")
					handle_client = connection.client.get_blob_client(blob=destination)
					if (output_type == "client"):
						yield handle_client
						continue

					handle_blob = handle_client.download_blob()
					if (output_type == "handle_blob"):
						yield handle_blob
						continue

					data_bin = handle_blob.readall()
					if ((output_type == "blob") or ((input_type == "excel") and (output_type == "python"))):
						yield data_bin
						continue

					# try:
					handle_str = io.TextIOWrapper(io.BytesIO(data_bin), encoding="Windows-1252")
					# except UnicodeDecodeError as error:
					# 	import chardet
					# 	handle_str = io.TextIOWrapper(io.BytesIO(data_bin), encoding=chardet.detect(data_bin))

					if (output_type == "str"):
						yield handle_str.read()
						continue

					yield handle_str

	###############################

	output = tuple(yieldFile())
	output_count = len(output)
	if (not output_count):
		return () if force_list else None

	if (output_type != "python"):
		return output if (force_list or (output_count > 1)) else output[0]

	match input_type:
		case "csv" | "excel":

			answer = []
			for item in output:
				# See: https://pandas.pydata.org/docs/reference/api/pandas.read_csv.html#pandas-read-csv
				# See: https://pandas.pydata.org/docs/reference/api/pandas.DataFrame.to_csv.html
				if (input_type == "excel"):
					frame = pandas.read_excel(item)
				else:
					frame = pandas.read_csv(item)
				# frame.to_csv(header=True, index=False, date_format=r"%Y-%m-%dT%H:%M:%S.%fZ")
				answer.append(frame)

			if (multifile_method == "separate"):
				return answer

			# See: https://pandas.pydata.org/pandas-docs/stable/user_guide/merging.html
			return pandas.concat(answer, join="outer", ignore_index=True, sort=False)

		case _:
			raise KeyError(f"Unknown *input_type* '{input_type}'")

def getMeta(*args, force_list=False, **kwargs):
	output = tuple(handle_client.get_blob_properties() for handle_client in select(*args, force_list=True, **{**kwargs, "output_type": "client"}))
	
	output_count = len(output)
	if (not output_count):
		return () if force_list else None

	if (force_list or (output_count > 1)):
		return output

	return output[0]

class BlobConnection:
	""" coding: utf-8
	-------------------------------------------------------------------------
	Copyright (c) Microsoft Corporation. All rights reserved.
	Licensed under the MIT License. See License.txt in the project root for
	license information.
	--------------------------------------------------------------------------

	FILE: blob_samples_directory_interface.py
	DESCRIPTION:
		This example shows how to perform common filesystem-like operations on a
		container. This includes uploading and downloading files to and from the
		container with an optional prefix, listing files in the container both at
		a single level and recursively, and deleting files in the container either
		individually or recursively.
		To run this sample, provide the name of the storage container to operate on
		as the script argument (e.g. `python3 directory_interface.py my-container`).
		This sample expects that the `AZURE_STORAGE_CONNECTION_STRING` environment
		variable is set. It SHOULD NOT be hardcoded in any code derived from this
		sample.
	USAGE: python blob_samples_directory_interface.py CONTAINER_NAME
		Set the environment variables with your own values before running the sample:
		1) AZURE_STORAGE_CONNECTION_STRING - the connection string to your storage account
	"""

	def __init__(self, connection_string, container_name):
		service_client = BlobServiceClient.from_connection_string(connection_string)
		self.client = service_client.get_container_client(container_name)

	def upload(self, source, dest):
		'''
		Upload a file or directory to a path inside the container
		'''
		if (os.path.isdir(source)):
			self.upload_dir(source, dest)
		else:
			self.upload_file(source, dest)

	def upload_file(self, source, dest):
		'''
		Upload a single file to a path inside the container
		'''
		print(f'Uploading {source} to {dest}')
		with open(source, 'rb') as data:
			self.client.upload_blob(name=dest, data=data)

	def upload_dir(self, source, dest):
		'''
		Upload a directory to a path inside the container
		'''
		prefix = '' if dest == '' else dest + '/'
		prefix += os.path.basename(source) + '/'
		for root, dirs, files in os.walk(source):
			for name in files:
				dir_part = os.path.relpath(root, source)
				dir_part = '' if dir_part == '.' else dir_part + '/'
				file_path = os.path.join(root, name)
				blob_path = prefix + dir_part + name
				self.upload_file(file_path, blob_path)

	def download(self, source, dest):
		'''
		Download a file or directory to a path on the local filesystem
		'''
		if not dest:
			raise Exception('A destination must be provided')

		blobs = self.ls_files(source, recursive=True)
		if blobs:
			# if source is a directory, dest must also be a directory
			if not source == '' and not source.endswith('/'):
				source += '/'
			if not dest.endswith('/'):
				dest += '/'
			# append the directory name from source to the destination
			dest += os.path.basename(os.path.normpath(source)) + '/'

			blobs = [source + blob for blob in blobs]
			for blob in blobs:
				blob_dest = dest + os.path.relpath(blob, source)
				self.download_file(blob, blob_dest)
		else:
			self.download_file(source, dest)

	def download_file(self, source, dest):
		'''
		Download a single file to a path on the local filesystem
		'''
		# dest is a directory if ending with '/' or '.', otherwise it's a file
		if dest.endswith('.'):
			dest += '/'
		blob_dest = dest + os.path.basename(source) if dest.endswith('/') else dest

		print(f'Downloading {source} to {blob_dest}')
		os.makedirs(os.path.dirname(blob_dest), exist_ok=True)
		bc = self.client.get_blob_client(blob=source)
		with open(blob_dest, 'wb') as file:
			data = bc.download_blob()
			file.write(data.readall())

	def ls_files(self, path, recursive=False):
		'''
		List files under a path, optionally recursively
		'''
		if not path == '' and not path.endswith('/'):
			path += '/'

		blob_iter = self.client.list_blobs(name_starts_with=path)
		files = []
		for blob in blob_iter:
			relative_path = os.path.relpath(blob.name, path)
			if recursive or not '/' in relative_path:
				files.append(relative_path)
		return files

	def ls_dirs(self, path, recursive=False):
		'''
		List directories under a path, optionally recursively
		'''
		if not path == '' and not path.endswith('/'):
			path += '/'

		blob_iter = self.client.list_blobs(name_starts_with=path)
		dirs = []
		for blob in blob_iter:
			relative_dir = os.path.dirname(os.path.relpath(blob.name, path))
			if relative_dir and (recursive or not '/' in relative_dir) and not relative_dir in dirs:
				dirs.append(relative_dir)

		return dirs

	def rm(self, path, recursive=False):
		'''
		Remove a single file, or remove a path recursively
		'''
		if recursive:
			self.rmdir(path)
		else:
			print(f'Deleting {path}')
			self.client.delete_blob(path)

	def rmdir(self, path):
		'''
		Remove a directory and its contents recursively
		'''
		blobs = self.ls_files(path, recursive=True)
		if not blobs:
			return

		if not path == '' and not path.endswith('/'):
			path += '/'
		blobs = [path + blob for blob in blobs]
		print(f'Deleting {", ".join(blobs)}')
		self.client.delete_blobs(*blobs)

testFile = os.path.join(os.path.dirname(__file__), "test.txt")
class TestCase(PyUtilities.testing.BaseCase):
	def test_BlobStorage_canInsert(self):
		with self.assertLogs(level="INFO"):
			with self.assertRaises(FileNotFoundError):
				BlobStorage.insert(
					data="unknown.txt",
					container="ma-extract",
					folder="vineyards",
					input_type="file",
				)

			BlobStorage.insert(
				data=testFile,
				container="ma-extract",
				folder="vineyards",
				input_type="file",
			)
				
if (__name__ == "__main__"):
	PyUtilities.testing.test()