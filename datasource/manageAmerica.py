import os
import sys
import json
import time
import logging
import requests
import itertools

import PyUtilities.common
import PyUtilities.testing
from PyUtilities.datasource.common import config

def _getToken(login_user=None, login_password=None, *, configKwargs=None, nested_max=3, retry_seconds=20, **kwargs):
	""" Function to return MA access token.
	See: https://docs.python-requests.org/en/v1.0.0/api/#main-interface

	login_user (str) - The username to use for logging in
	login_password (str) - The password to use for logging in

	Example Input: _getToken()
	Example Input: _getToken("Lorem", "Ipsum")
	"""

	def doRequest(nested=0):
		try:
			return requests.request("POST", "https://api.manageamerica.com/api/account/signin",
				headers={"Content-Type": "application/json"},
				data=json.dumps(options),
			)
		except requests.exceptions.ConnectionError as error:
			# Too many requests. Wait at least one minute and try again.
			if (nested >= nested_max):
				raise error

			nested += 1;

			logging.info(f"Waiting {retry_seconds} seconds then trying again ({nested} of {nested_max} tries)")
			time.sleep(retry_seconds)

			return doRequest(nested=nested)

	################################

	login_user = login_user or config("user", "ma_vineyards", **(configKwargs or {}))
	login_password = login_password or config("password", "ma_vineyards", **(configKwargs or {}))
	options = {"login": login_user, "password": login_password}

	logging.info("Getting MA token...")
	response = doRequest()
	response_json = response.json()

	if ("exceptionMessage" in response_json): 
		raise ValueError(response_json["exceptionMessage"], options, response_json)

	token = response_json["token"]

	if (token is None):
		logging.info(response_json)
		raise ValueError(f"Could not get token for user '{login_user}'");

	logging.debug(f"ma_token: '{token}'")
	return token

def select(url, *, token=None, alias=None, remove=None, modifyData=None, filterData=None, customReport=False, nested_max=3, retry_seconds=90, **kwargs):
	""" Returns data from Manage America.

	url (str or tuple) - The URL to pull the data from
		- If tuple: Will get the data from each URL in the list
	alias (dict of str) - Key names to replace in the data source if they exist
	remove (tuple of str) - Key names to remove from the data source if they exist
	modifyData (function) - A function which modifies the data before it is returned
	filterData (function) - A function which filters the data before it is modified or returned
	customReport (bool) - If the result should be parsed as a manage america 'adds report'
	nested_max (int) - How many times to retry a URL before erroring out

	Example Input: select("https://n6.manageamerica.com/api/property/?companyId=233")
	Example Input: select("https://n6.manageamerica.com/api/property/?companyId=233", modifyData=lambda data: [*data, {"lorem": "ipsum"}])
	Example Input: select("https://n6.manageamerica.com/api/property/?companyId=233", filterData=lambda item: row.get("type") == "Detail")
	Example Input: select(["https://www.lorem.com", "https://www.ipsum.com"])
	Example Input: select("https://n6.manageamerica.com/api/addsReport/v1/runReport?Company_Id=233&Report_Id=4553", customReport=True)
	Example Input: select("https://n6.manageamerica.com/api/property/?companyId=233", alias={"Old Name 1": "new_name_1", "Old Name 2": "new_name_2"})
	"""

	def doRequest(url, nested=0):
		try:
			return requests.request("GET", _url,
				headers = {"Authorization": f"Bearer {token}"},
				data = {},
			)
		except requests.exceptions.ConnectionError as error:
			# Too many requests. Wait at least one minute and try again.
			if (nested >= nested_max):
				raise error

			nested += 1;

			logging.info(f"Waiting {retry_seconds} seconds then trying again ({nested} of {nested_max} tries)")
			time.sleep(retry_seconds)

			return doRequest(url, nested=nested)

	############################

	token = token or _getToken(**kwargs)

	data = []
	urlList = PyUtilities.common.ensure_container(url)
	for (index, _url) in enumerate(urlList):
		logging.info(f"Getting data for url {index + 1}: '{_url}'")
		response = doRequest(url)

		try:
			answer = response.json()
			if (isinstance(answer, dict)):
				if (answer.get("message", None)):
					raise ValueError(answer)
				data.append(answer)
			else: 
				data.extend(answer or ())
			logging.info(f"Rows Recieved: '{len(answer or ())}'")
		except requests.exceptions.JSONDecodeError as error:
			logging.info(f"url: '{_url}'")
			raise error

	if (not len(data)):
		return

	if (customReport):
		logging.info("Parsing custom report data...")
		columns = tuple(item["name"] for item in data[0]["columns"])
		data = tuple({key: value for (key, value) in itertools.zip_longest(columns, item["data"])} for item in data[0]["rows"] if (item["type"] != "Total"))
		if (not len(data)):
			return

	if (alias):
		logging.info("Renaming columns...")
		data = tuple({alias.get(key, key): value for (key, value) in catalogue.items()} for catalogue in data)

	if (remove):
		logging.info("Removing columns...")
		data = tuple({key: value for (key, value) in catalogue.items() if (key not in remove)} for catalogue in data)

	if (filterData):
		logging.info("Filtering rows...")
		for myFunction in PyUtilities.common.ensure_container(filterData):
			data = data.filter(myFunction)

	if (modifyData):
		logging.info("Modifying data...")
		for myFunction in PyUtilities.common.ensure_container(modifyData):
			data = myFunction(data)

	return data

class TestCase(PyUtilities.testing.BaseCase):
	def test_ManageAmerica_password(self):
		with self.assertLogs(level="INFO"):
			self.assertIsNotNone(ManageAmerica._getToken(
				login_user=config("user", "ma_vineyards"),
				login_password=config("password", "ma_vineyards"),
			))

		with self.assertLogs(level="INFO"):
			self.assertIsNotNone(ManageAmerica._getToken(
				login_user=config("user", "ma_treehouse"),
				login_password=config("password", "ma_treehouse"),
			))

if (__name__ == "__main__"):
	PyUtilities.testing.test()