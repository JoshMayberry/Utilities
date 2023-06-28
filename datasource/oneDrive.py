import io
import os
import sys
import urllib
import logging
import requests

import msal
import pandas
import openpyxl

import PyUtilities.common
from PyUtilities.datasource.common import config

def getConnection(*args, connection=None, **kwargs):
	""" Retuns an object to use for connecting to OneDrive.

	Example Input: getConnection()
	"""

	if (connection is not None):
		return connection

	return OneDriveConnection(*args, **kwargs)

def select(*args, **kwargs):
	""" Returns files from OneDrive

	Example Input: select()
	"""

	connection = getConnection(**kwargs)
	return connection.select(*args, **kwargs)

class OneDriveConnection():
	def __init__(self, client_id=None, client_secret=None, tenant_id=None, user_id=None, configKwargs=None, **kwargs):
		""" A helper object for working with OneDrive.
		Use: https://raquickstartprod.blob.core.windows.net/quickstartcodesample/PythonDaemon-16.zip
		See: https://msal-python.readthedocs.io/en/latest/#confidentialclientapplication

		To Apply permission changes: https://login.microsoftonline.com/common/adminconsent?client_id=55aa08f1-7366-4596-961b-6a737a879a6b

		Example Input: OneDriveConnection()
		"""

		self.token = None
		self.client_id = client_id or config("client_id", "onedrive", **(configKwargs or {}))
		self.client_secret = client_secret or config("client_secret", "onedrive", **(configKwargs or {}))
		self.tenant_id = tenant_id or config("tenant_id", "onedrive", **(configKwargs or {}))
		self.user_id = user_id or config("user_id", "onedrive", **(configKwargs or {}))

		self.authority = f"https://login.microsoftonline.com/{self.tenant_id}"
		self.redirect_uri = "https://login.live.com/oauth20_desktop.srf"

		logging.info(f"Making onedrive connection...")

		# Create a preferably long-lived app instance which maintains a token cache.
		self.app = msal.ConfidentialClientApplication(self.client_id, authority=self.authority, client_credential=self.client_secret)

	def __enter__(self):

		self.token = self._getToken()

		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		self.token = None

	def _getToken(self, scope=None):
		""" Returns a token to use.
		See: https://msal-python.readthedocs.io/en/latest/#msal.ConfidentialClientApplication.acquire_token_for_client
		See: https://learn.microsoft.com/en-us/graph/auth-v2-service
		Use: https://github.com/AzureAD/microsoft-authentication-library-for-python/blob/dev/sample/confidential_client_secret_sample.py

		scope (list) - Contains the scopes requested.
			For confidential clients, this should use the format similar to {Application ID URI}/.default to indicate that the scopes being requested
			are the ones statically defined in the app object set in the Azure portal (for Microsoft Graph,
			{Application ID URI} points to https://graph.microsoft.com).
			For custom web APIs, {Application ID URI} is defined under the Expose an API section in App registrations in the Azure Portal.

		Example Input: _getToken()
		Example Input: _getToken("files.read.all")
		"""

		scope = PyUtilities.common.ensure_container(scope) if scope else [f"https://graph.microsoft.com/.default"]

		result = self.app.acquire_token_silent(scope, account=None)

		if (not result):
			# No suitable token exists in cache. Let's get a new one from AAD.
			logging.info(f"Getting new token for onedrive...")
			result = self.app.acquire_token_for_client(scopes=scope)

		if ("access_token" not in result):
			raise ValueError(result["error"], result)

		return result["access_token"]

	def select(self, *args, **kwargs):
		return tuple(self.yield_select(*args, **kwargs))

	def yield_select(self, location="file", filepath=None, *, user_id=None, output_type="python",
		filterInput_pre=None, filterInput=None, include_info=False, include_contents=True, **kwargs):
		""" Yields data from the given endpoint.
		Use: https://github.com/pranabdas/Access-OneDrive-via-Microsoft-Graph-Python#onedrive-operations
		Use: https://stackoverflow.com/questions/20635778/using-openpyxl-to-read-file-from-memory/64725882#64725882
		See: https://keathmilligan.net/automate-your-work-with-msgraph-and-python
		See: https://learn.microsoft.com/en-us/graph/filter-query-parameter?tabs=http

		location (str) - Where on OneDrive to look
		filepath (str) - Which file to grab
		user_id (str) - Can be the "object id" or their "user principal name"

		Example Input: yield_select("root")
		Example Input: yield_select("shared")
		Example Input: yield_select("drive", "Showmojo Ads.xlsx")
		Example Input: yield_select("shared", "Homes Team Regions.xlsx", connection=connection)
		Example Input: yield_select("recent", user_id="lorem@rootsmg.com")
		"""

		def yield_info(endpoint):
			for info in self.select_raw(endpoint, **kwargs)["value"]:
				if (filepath and ((location == "shared") or (location == "recent")) and (filepath not in info["name"])):
					continue
				if (filterInput_pre and (not filterInput_pre(None, info, {"location": location, "filepath": filepath, "user_id": user_id}))):
					continue

				match (location):
					case "shared":
						info_2 = self.select_raw(f"drives/{info['remoteItem']['parentReference']['driveId']}/items/{info['remoteItem']['id']}", **kwargs)

						if (filterInput_pre and (not filterInput_pre(None, info_2, {"location": location, "filepath": filepath, "user_id": user_id, "info_share": info}))):
							continue

						yield info_2

					case _:
						yield info

		def formatContent(info):
			url_download = info.get("@microsoft.graph.downloadUrl", None)
			if (not url_download):
				raise ValueError(f"Download not configured for location '{location}'", info)

			if (output_type == "url"):
				return url_download

			filename = info["name"]
			if (".mp4" in filename):
				logging.warning(f"NOT IMPLEMENTED YET: read videos; filename: '{filename}'")
				return None

			handle_request = urllib.request.urlopen(url_download)
			if (output_type == "handle_request"):
				return handle_request

			handle_bytes = io.BytesIO(handle_request.read())
			if (output_type == "handle_bytes"):
				return handle_bytes

			if (".csv" in filename):
				return pandas.read_csv(url_download)

			if (".xls" in filename):
				return openpyxl.load_workbook(handle_bytes)

			raise NotImplementedError(f"Cannot read file '{filename}'", info)

		###############################

		user_id = user_id or self.user_id
		endpoint_base = f"users/{user_id}/drive"
		endpoint_info = endpoint_base

		match (location):
			case "recent":
				# See: https://learn.microsoft.com/en-us/onedrive/developer/rest-api/api/drive_recent?view=odsp-graph-online
				endpoint_info += "/recent"

			case "shared":
				# See: https://learn.microsoft.com/en-us/onedrive/developer/rest-api/api/drive_sharedwithme?view=odsp-graph-online
				endpoint_info += "/sharedWithMe"

				# TODO: Will not filtering beforehand cause performace issues as the number of shared files grow? Is there a limit to the number of shared files we can get?

			case "root":
				# See: https://learn.microsoft.com/en-us/onedrive/developer/rest-api/api/driveitem_list_children?view=odsp-graph-online
				endpoint_info += "/root/children"
				if (filepath):
					# See: https://learn.microsoft.com/en-us/graph/filter-query-parameter?tabs=http
					endpoint_info += f"?$filter=contains(name, '{filepath}')"

			case "id":
				# See: https://learn.microsoft.com/en-us/onedrive/developer/rest-api/resources/driveitem?view=odsp-graph-online
				endpoint_info += "/items/" + PyUtilities.common.requiredArg(filepath, f"*filepath* required if *location* = '{location}'")

			case "file":
				# See: https://learn.microsoft.com/en-us/onedrive/developer/rest-api/resources/driveitem?view=odsp-graph-online
				endpoint_info += "/root:/" + PyUtilities.common.requiredArg(filepath, f"*filepath* required if *location* = '{location}'")

			case _:
				raise KeyError(f"Unknown location '{location}'")

		for info in yield_info(endpoint_info):
			if (not include_contents):
				yield info
				continue

			contents = formatContent(info)

			if (filterInput and (not filterInput(contents, info, {"location": location, "filepath": filepath, "user_id": user_id}))):
				continue
			yield (info, contents) if (include_info) else contents

	def select_raw(self, endpoint, **kwargs):
		""" Returns the raw result from a given endpoint.

		output_type (str) - How to return the file
			- client: Pre-download file handle
			- byte: The raw binary string contents of the blob
			- handle_str: Stringified file handle
			- str: The raw string contents of the blob
			- python: Make it into a python object
		input_type (str) - How to interpret the blob when *output_type* is 'python'
			- csv: A list of dictionaries

		Example Input: select_raw("users/")
		Example Input: select_raw(f"drives/{driveId}/items/{id}/content")
		"""

		if (not self.token):
			self.token = self._getToken(**kwargs)

		url = f"https://graph.microsoft.com/v1.0/{endpoint}"
		logging.info(f"Sending '{url}' to OneDrive")
		response = requests.get(url, headers={ "Authorization": f"Bearer {self.token}" })

		if (not endpoint.endswith("/content")):
			answer = response.json()
			if ("error" in answer):
				raise ValueError(answer["error"]["code"], answer["error"])

			return answer

		handle_bin = io.BytesIO(response.content)
		handle_bin.contentType = response.headers['content-type']

		return handle_bin

if (__name__ == "__main__"):
	PyUtilities.logger.logger_info()

	with getConnection() as connection:
		data = select("shared", "Homes Team Regions.xlsx", connection=connection)
		print("@0", data)