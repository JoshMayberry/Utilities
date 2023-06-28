import os
import sys
import logging

import dropbox

import PyUtilities.testing
import PyUtilities.datasource.general
from PyUtilities.datasource.common import config

def insert(data, container="systems_data/report_data_source", folder=None, filename=None, *, method="upsert", token=None, chunk_size=145, configKwargs=None, **kwargs):
	""" Sends data to dropbox.
	See: https://riptutorial.com/dropbox-api/example/1927/uploading-a-file-using-the-dropbox-python-sdk

	data (any) - What to send to the dropbox
	container (str) - Which dropbox root folder to store the file(s) in
	folder (str) - What folder path of the container to store the file(s) in
		- If None: Will put the file in the root directory
	filename (str) - What file name to use for the file
		- If None: Will try coming up with a file name
	method (str) - How to handle sending the data
		- upsert: Update existing file in the folder, otherwise create a new file
		- insert: Try adding it and throw an error if it alrteady exists
		- drop: Drop all blobs in the folder and insert new blobs
	token (str) - The access token for the dropbox account
	chunk_size (int) - How many MB large a chunk should be

	Example Input: insert([{Lorem: "ipsum"}])
	Example Input: insert([{Lorem: "ipsum"}], container="treehouse", folder="rps")
	Example Input: insert({Lorem: "ipsum"}, input_type="json")
	Example Input: insert("C:/lorem/ipsum", input_type="file")
	Example Input: insert("C:/lorem/ipsum", input_type="file", walk_allow=("csv", "xlsx"))
	Example Input: insert(open("lorem.txt", "r"), filename="lorem.txt", input_type="raw")
	"""

	token = token or config("token", "dropbox", **(configKwargs or {}))
	with dropbox.Dropbox(token, timeout=900) as dropboxHandle:
		# See: https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html#dropbox.dropbox_client.Dropbox.files_list_folder
		# contents = dropboxHandle.files_list_folder(folder or "")
		# if (len(contents)):
		
		mode = None
		autorename = False
		match method:
			case "drop":
				raise NotImplementedError("Dropbox drop all folder contents")

			case "upsert":
				mode = dropbox.files.WriteMode.overwrite
				pass

			case "insert":
				autorename = True
				mode = dropbox.files.WriteMode.add

			case _:
				raise KeyError(f"Unknown *method* '{method}'")

		chunk_size *= 1024 * 1024

		# See: https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html#dropbox.dropbox_client.Dropbox.files_upload
		for (handle_binary, destination) in PyUtilities.datasource.general.yield_fileOutput(data=data, folder=folder, filename=filename, **kwargs):
			# See: https://stackoverflow.com/questions/4677433/in-python-how-do-i-check-the-size-of-a-stringio-object/4677542#4677542
			handle_raw = getattr(handle_binary, "raw", handle_binary)
			current = handle_raw.tell()
			handle_raw.seek(0, os.SEEK_END)
			file_size = handle_raw.tell()
			handle_raw.seek(current, os.SEEK_SET)

			_destination = os.path.join("/", container, destination).replace("\\","/")
			if (file_size <= chunk_size):
				logging.info(f"Sending file to dropbox at '{_destination}'...")
				dropboxHandle.files_upload(handle_binary.read(), _destination, mode=mode, autorename=autorename)
				continue

			# See: https://dropbox-sdk-python.readthedocs.io/en/latest/api/files.html#dropbox.files.CommitInfo
			logging.info(f"Sending file in chunks to dropbox at '{_destination}'...")
			session = dropboxHandle.files_upload_session_start(handle_binary.read(chunk_size))
			cursor = dropbox.files.UploadSessionCursor(session_id=session.session_id, offset=handle_binary.tell())
			commit = dropbox.files.CommitInfo(path=_destination, mode=mode, autorename=autorename)

			while (handle_binary.tell() < file_size):
				logging.info(f"Sending chunk at '{cursor.offset}' of '{file_size}'...")
				if ((file_size - handle_binary.tell()) <= chunk_size):
					dropboxHandle.files_upload_session_finish(handle_binary.read(chunk_size), cursor, commit)
				else:
					dropboxHandle.files_upload_session_append(handle_binary.read(chunk_size), cursor.session_id, cursor.offset)
					cursor.offset = handle_binary.tell()

		return True

def select():
	raise NotImplementedError("Get Dropbox File")

def getMeta():
	# See: https://www.dropboxforum.com/t5/Dropbox-API-Support-Feedback/python-SDK/td-p/206272
	# See: https://dropbox-sdk-python.readthedocs.io/en/latest/api/dropbox.html#dropbox.dropbox_client.Dropbox.files_get_metadata

	raise NotImplementedError("Get Dropbox Metadata")
	# connection.files_get_metadata(filename)

testFile = os.path.join(os.path.dirname(__file__), "test.txt")
class TestCase(PyUtilities.testing.BaseCase):
	def test_DropBox_canInsert(self):
		with self.assertLogs(level="INFO"):
			with self.assertRaises(FileNotFoundError):
				Dropbox.insert(
					data="unknown.txt",
					container="systems_data/report_data_source",
					folder="vineyards_feed",
					input_type="file",
				)

			Dropbox.insert(
				data=testFile,
				container="systems_data/report_data_source",
				folder="vineyards_feed",
				input_type="file",
			)
				
if (__name__ == "__main__"):
	PyUtilities.testing.test()
