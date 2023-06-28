import os
import sys
import math
import logging
import requests
import contextlib
import dateutil.relativedelta

import PyUtilities.common
from PyUtilities.datasource.common import config

@contextlib.contextmanager
def getConnection(*, connection=None, **kwargs):
	""" Retuns an object to use for connecting to Rent Manager.
	Use: https://github.com/itsDrew86/rentmanager_pipeline/blob/main/rentmanager/client.py

	Example Input: getConnection()
	"""

	if (connection is not None):
		yield connection
		return

	# base_url=https://thgprop.api.rentmanager.com
	# environment=PRODUCTION
	# token_header_name=X-RM12Api-ApiToken
	# sync_interval=15

	with RentManagerConnection(**kwargs) as connection:
		yield connection

def select(*args, **kwargs):
	""" Returns Data from the Rent Manager API.

	Example Input: select("property")
	"""

	with getConnection(**kwargs) as connection:
		return connection.select(*args, **kwargs)

class RentManagerConnection():
	def __init__(self, *, autoStart=True, **kwargs):
		self.token = None
		self.initKwargs = kwargs

	def __enter__(self):
		self.startSession(**self.initKwargs)

		return self

	def __exit__(self, type, value, traceback):
		self.endSession()

	catalogue_environment = {
		"production": 1,
		"sandbox": 15,
		"faztrack_sandbox": 16,
		"capex_testing": 25,
	}

	def startSession(self, login_user=None, login_password=None, *, environment="production", configKwargs=None, **kwargs):
		login_user = login_user or config("user", "rentmanager", **(configKwargs or {}))
		login_password = login_password or config("password", "rentmanager", **(configKwargs or {}))

		logging.info("Getting Token...")
		response = requests.post("https://thgprop.api.rentmanager.com/Authentication/AuthorizeUser", json={
			'Username': login_user,
			'Password': login_password,
			'LocationID': self.catalogue_environment[environment],
		})

		if (response.status_code == 401):
			print("--", [login_user, login_password])
			raise PermissionError("Could not get Token")

		response.raise_for_status()

		logging.info("Token successfully authorized")
		self.token = response.json()
		return True

	def endSession(self):
		if (self.token is None):
			raise ValueError("No active token")

		response = requests.post(f"https://thgprop.api.rentmanager.com/Authentication/DeAuthorize?token={self.token}")
		response.raise_for_status()

		self.token = None
		logging.info("Token successfully deauthorized")
		return True

	def select(self, endpoint_name, *, limit=1000, **kwargs):
		""" Gets information from Rent Manager

		Example Input: select("model")
		Example Input: select("model", name="LocationTenantIDModel")

		Example Input: select("property")
		Example Input: select("property_group", property_group_id=169)
		
		Example Input: select("enumeration", name=name)
		Example Input: select("report", report_id=report_id)
		Example Input: select("job")
		Example Input: select("job_type")
		Example Input: select("account")
		"""

		if (not hasattr(self, f"_urlFor__{endpoint_name}")):
			raise ValueError(f"Unknown *endpoint_name* '{endpoint_name}'")

		endpoint, queryParams = getattr(self, f"_urlFor__{endpoint_name}")(**kwargs)
		url = f"https://thgprop.api.rentmanager.com/{endpoint}"

		if (limit):
			queryParams["PageSize"] = limit

		if (queryParams):
			url += "?"
			url += "&".join(f"{key}={value}" for (key, value) in queryParams.items())

		# TODO: Make this multi-threaded in a generic way that can be applied to other connectors; See old multi-threazding code from college and Andrew's implentation as examples
		# TODO: See how multi-threading plays with DataBricks before impllementing
		return self._makeRequest(url, limit=limit)

	def _makeRequest(self, url, *, limit=1000):
		logging.info(f"Getting data from RentManager; {url}")
		response = requests.get(url, headers={
			"X-RM12Api-ApiToken": self.token,
		})

		if (response.status_code == 401):
			self.startSession()
			response = requests.get(url, headers={
				"X-RM12Api-ApiToken": self.token,
			})

		response.raise_for_status()

		response.encoding = "utf-8-sig"
		answer = response.json() # Assume the result will be a list of objects

		if ("RunReport" in url):
			answer = answer["Grid1"]

		# Account for paginated results
		count = response.headers.get("x-results", None)
		if (not count):
			return answer

		count = int(count)
		count_total = int(response.headers["x-total-results"])
		if ((count == count_total) or (count_total <= limit)):
			return answer

		for page in range(1, math.ceil((count_total / limit))):
			response = requests.get(f"{url}&PageNumber={page}", headers={
				"X-RM12Api-ApiToken": self.token,
			})
			answer.extend(response.json())

		return answer

	@classmethod
	def _urlFor__enumeration(cls, *, name=None, **kwargs):
		return "APIInformation/EnumerationValues", {
			"name": PyUtilities.common.requiredArg(name, f"*name* required for 'enumeration'"),
		}

	@classmethod
	def _urlFor__enumeration(cls, *, name=None, **kwargs):
		if (name):
			return "APIInformation/Model", {
				"name": name,
			}

		return "APIInformation/Models", {}

	@classmethod
	def _urlFor__property(cls, *, include_accountingClose=True, include_address=True, include_propertyGroup=True, **kwargs):
		# See: https://thgprop.api.rentmanager.com/Help/Resource/Properties

		embeds = []

		if (include_accountingClose):
			embeds.append("AccountingClose")

		if (include_address):
			embeds.append("Addresses")

		if (include_propertyGroup):
			embeds.append("PropertyGroups")

		queryParams = { "embeds": ",".join(embeds) } if embeds else {}

		return "Properties", queryParams

	@classmethod
	def _urlFor__property_group(cls, *, property_group_id=None, include_property=False, **kwargs):
		# See: https://thgprop.api.rentmanager.com/Help/Subresource/Properties/PropertyGroups

		embeds = []

		if (include_property):
			embeds.append("Properties")

		queryParams = { "embeds": ",".join(embeds) } if embeds else {}

		if (property_group_id):
			return f"PropertyGroups/{property_group_id}", queryParams

		return "PropertyGroups", queryParams

	@classmethod
	def _urlFor__job(cls, *, job_id=None, include_file=False, include_budget=False, include_userValues=False, filter_inactive=True, **kwargs):
		embeds = []

		if (include_file):
			embeds.append("History.HistoryAttachments.File")

		if (include_budget):
			embeds.append("JobBudgets")

		if (include_userValues):
			embeds.append("UserDefinedValues")

		queryParams = { "embeds": ",".join(embeds) } if embeds else {}

		if (filter_inactive):
			queryParams["filter"] = "IsActive,eq,true"

		if (job_id):
			return f"Jobs/{job_id}", queryParams
		return "Jobs", queryParams

	@classmethod
	def _urlFor__job_type(cls, *, job_id=None, **kwargs):
		return "JobTypes", {}

	@classmethod
	def _urlFor__history_notes(cls, *, job_id=None, **kwargs):
		return "HistoryNotes", {} # TODO

	@classmethod
	def _urlFor__site(cls, **kwargs):
		return "Units", {} # TODO: Put this in

	# @classmethod
	# def _urlFor__chart_format(cls, **kwargs):
	# 	# See: https://thgprop.api.rentmanager.com/Help/Resource/ChartOfAccountsMappings
	# 	return "ChartOfAccountsMappings", {}

	# @classmethod
	# def _urlFor__chart_account(cls, **kwargs):
	# 	# See: https://thgprop.api.rentmanager.com/Help/Resource/ChartOfAccountsMappedAccounts
	# 	return "ChartOfAccountsMappedAccounts", {}

	@classmethod
	def _urlFor__gl_account(cls, *, gl_account_id=None, include_child=False, **kwargs):
		# See: https://thgprop.api.rentmanager.com/Help/Resource/GLAccounts

		embeds = []

		if (include_child):
			embeds.append("ChildGLAccounts")

		queryParams = { "embeds": ",".join(embeds) } if embeds else {}

		if (gl_account_id):
			return f"GLAccounts/{gl_account_id}", queryParams
		return "GLAccounts", queryParams

	@classmethod
	def _urlFor__user(cls, **kwargs):
		# See: https://thgprop.api.rentmanager.com/Help/Resource/Users
		return "Users", {}

	@classmethod
	def _urlFor__asset(cls, **kwargs):
		return "Assets", {}

	@classmethod
	def _urlFor__report(cls, *, report_id=None, reportParams=None, include_score=False, **kwargs):
		if (not report_id):
			return "/Reports", {}

		embeds = []

		if (include_score):
			embeds.append("ReportParameters.ReportParameterValueSource")

		queryParams = { "embeds": ",".join(embeds) } if embeds else {}

		return f"/Reports/{report_id}", {
			**queryParams,
			**(reportParams or {}),
		}

	@classmethod
	def _format_reportReturn(cls, report_id, reportParams=None, queryParams=None):
		queryParams = queryParams or {}

		queryParams["GetOptions"] = "ReturnJSONStream"

		if (reportParams):
			queryParams["parameters"] = ";".join(f"{key},{value}" for (key, value) in reportParams.items())

		return f"/Reports/{report_id}/RunReport", queryParams

	@classmethod
	def _urlFor__report_run(cls, *, report_id=None, reportParams=None, queryParams=None, **kwargs):
		return cls._format_reportReturn(PyUtilities.common.requiredArg(report_id, f"*name* required for 'report_run'"), reportParams=reportParams, queryParams=queryParams)

	# @classmethod
	# def _urlFor__balance_sheet(cls, **kwargs):
	# 	return cls._format_reportReturn(38, {})

	# @classmethod
	# def _urlFor__balance_sheet_comparison(cls, **kwargs):
	# 	return cls._format_reportReturn(39, {})

	# @classmethod
	# def _urlFor__profit_loss(cls, **kwargs):
	# 	return cls._format_reportReturn(43, {})

	# @classmethod
	# def _urlFor__profit_loss_recap(cls, **kwargs):
	# 	return cls._format_reportReturn(45, {})

	@classmethod
	def _urlFor__transaction(cls, *, date_start=None, date_end=None, exclude_zero=True, include_breakdown=True, property_id=None, **kwargs):

		reportParams = {
			"StartDate": PyUtilities.common.requiredArg(date_start, f"*date_start* required for 'transaction'"),
			"EndDate": date_end or (date_start + dateutil.relativedelta.relativedelta(years=1))
		}

		if (exclude_zero):
			reportParams["ZeroAmountExclusion"] = 2

		if (include_breakdown):
			reportParams["SHOWDEPOSITBREAKDOWN"] = True

		if (property_id):
			reportParams["PropOwnerIDs"] = "(" + ", ".join(str(x) for x in PyUtilities.common.ensure_container(property_id)) + ")"

		return cls._format_reportReturn(51, reportParams)

	# @classmethod
	# def _urlFor__cash_flow(cls, **kwargs):
	# 	return cls._format_reportReturn(54, {})

	# @classmethod
	# def _urlFor__budget_fiscal(cls, **kwargs):
	# 	return cls._format_reportReturn(55, {})

	# @classmethod
	# def _urlFor__budget_compare(cls, **kwargs):
	# 	return cls._format_reportReturn(56, {})

	# @classmethod
	# def _urlFor__budget_analysis(cls, **kwargs):
	# 	return cls._format_reportReturn(57, {})

	# @classmethod
	# def _urlFor__job_general_ledger(cls, **kwargs):
	# 	return cls._format_reportReturn(546, {})

	# @classmethod
	# def _urlFor__profit_loss_period(cls, **kwargs):
	# 	return cls._format_reportReturn(606, {})

	# @classmethod
	# def _urlFor__balance_period(cls, **kwargs):
	# 	return cls._format_reportReturn(607, {})

	# @classmethod
	# def _urlFor__profit_loss_period_recap(cls, **kwargs):
	# 	return cls._format_reportReturn(609, {})

	# @classmethod
	# def _urlFor__budget_compare_period(cls, **kwargs):
	# 	return cls._format_reportReturn(610, {})

	# @classmethod
	# def _urlFor__trial_balance(cls, **kwargs):
	# 	return cls._format_reportReturn(617, {})

	def insert(self, output_type, name=None, property_id=None):
		url = "https://thgprop.api.rentmanager.com"
		queryParams = []
		catalogue = {}
		method = "POST"

		match (output_type):
			case "property_group":
				url += "/PropertyGroups"
				catalogue["Name"] = PyUtilities.common.requiredArg(name, f"*name* required if *output_type* = '{output_type}'")
				catalogue["Properties"] = PyUtilities.common.requiredArg(property_id, f"*property_id* required if *output_type* = '{output_type}'")

				queryParams.append("embeds=Properties")

	def delete(self, output_type, *args):
		url = "https://thgprop.api.rentmanager.com"
		queryParams = []
		catalogue = {}
		method = "DELETE"

		match (output_type):
			case "property_group":
				url += f"""/PropertyGroups/{common.requiredArg(name, f"*name* required if *output_type* = '{output_type}'")}"""

if (__name__ == "__main__"):
	PyUtilities.logger.logger_info()

	with getConnection() as connection:
		data = connection.select("gl_account")
		print(data)