import os
import sys
import logging
import datetime
import requests

import bs4
import pandas

import PyUtilities.common
from PyUtilities.datasource.common import config

def getConnection(*args, connection=None, **kwargs):
	""" Retuns an object to use for connecting to ShowMojo.

	Example Input: getConnection()
	"""

	if (connection is not None):
		return connection

	return ShowMojoConnection(*args, **kwargs)

def select(report_id=None, include_standard=False, **kwargs):
	""" Yields the unformatted data for a report from ShowMojo

	report_id (str or tuple) - The report id of the report to return data for 
		- If tuple: Will get the data from each report id in the list

	Example Input: select_unformatted("1569")
	Example Input: select_unformatted(("1569", "1570"))
	Example Input: select_unformatted("1569", include_standard=True)
	Example Input: select_unformatted("1569", date_start=datetime.datetime.now())
	"""

	connection = getConnection(**kwargs)

	data = []

	if (report_id is not None):
		data.append(*connection.yieldReport(report_id, **kwargs))

	if (include_standard):
		data.append(*connection.yieldStandard(**kwargs))

	return tuple(data)

class ShowMojoConnection():
	def __init__(self, login_user=None, login_password=None, *, configKwargs=None, **kwargs):
		""" A helper object for working with ShowMojo.

		Example Input: ShowMojoConnection()
		"""

		configKwargs = configKwargs or {}
		login_user = login_user or config("user", "showmojo", **(configKwargs or {}))
		login_password = login_password or config("password", "showmojo", **(configKwargs or {}))

		self._soup_root = None
		self._soup_list = None
		self.authorization = (login_user, login_password)

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass

	@property
	def soup_root(self):
		if (self._soup_root):
			return self._soup_root

		response = requests.request("GET", "https://showmojo.com/syndication/trulia/46415e1005.xml")
		response.raise_for_status()

		self._soup_root = bs4.BeautifulSoup(response.content, "xml")
		return self._soup_root

	@property
	def soup_list(self):
		if (self._soup_list):
			return self._soup_list

		def yieldItems(element):
			try:
				yield ("listing_id", element.details.find("provider-listingid").string)
				yield ("listing_type", element.find("listing-type").string)
				yield ("status", element.status.string)

				yield ("address_street", element.location.find("street-address").string)
				yield ("address_city", element.location.find("city-name").string)
				yield ("address_zip", element.location.zipcode.string)

				address_state = element.location.find("state-code")
				yield ("address_state", address_state.string if address_state else None)

				# yield ("url_home", element.find("landing-page").find("lp-url").string)
				# yield ("url_schedule", element.site.find("site-url").string)

				# listing_title = element.details.find("listing-title")
				# yield ("listing_title", listing_title.string if listing_title else None)

				# listing_description = element.details.find("description")
				# yield ("listing_description", listing_description.string if listing_description else None)

				date_available = element.details.find("date-available")
				yield ("date_available", date_available.string if date_available else None)

				property_type = element.details.find("property-type")
				yield ("property_type", property_type.string if property_type else None)

				count_bedroom = element.details.find("num-bedrooms")
				yield ("count_bedroom", count_bedroom.string if count_bedroom else None)

				count_bathroom = element.details.find("num-full-bathrooms")
				yield ("count_bathroom", count_bathroom.string if count_bathroom else None)

				count_living = element.details.find("living-area-square-feet")
				yield ("count_living", count_living.string if count_living else None)

				# agent_id = element.agent.find("agent-id")
				# yield ("agent_id", agent_id.string if agent_id else None)

				agent_name = element.agent.find("agent-name")
				yield ("agent_name", agent_name.string if agent_name else None)

				# agent_phone = element.agent.find("agent-phone")
				# yield ("agent_phone", agent_phone.string if agent_phone else None)

				# agent_email = element.agent.find("agent-email")
				# yield ("agent_email", agent_email.string if agent_email else None)

				# yield ("url_video", tuple(item.find("video-url").string for item in element.videos.children if (item != "\n")) if element.videos else None)
				yield ("url_picture", tuple(item.find("picture-url").string for item in element.pictures.children if (item != "\n")) if element.pictures else None)

			except Exception as error:
				print(element.prettify())
				raise error

		##############################

		self._soup_list = tuple({key: value for (key, value) in yieldItems(element)} for element in self.soup_root.find_all("property"))
		return self._soup_list

	def yieldStandard(self, **kwargs):
		""" Returns all the standard reports.

		Example Input: yieldStandard()
		Example Input: yieldStandard(date_start=datetime.datetime.now())
		"""

		for report_id in ("detailed_prospect_data", "high_level_metrics", "detailed_listing_data", "listing_and_showing_metrics", "prospect_showing_data", "listing_performance"):
			yield yieldReport(report_id, **kwargs)

	def yieldReport(self, report_id, *, date_start=None, date_finish=None):
		""" Returns a report object.
		See: https://showmojo.com/help#/29069-api/223545-report-export-api
		See: https://docs.python-requests.org/en/v1.0.0/api/#main-interface

		report_id (str) - The form code of the form to return data for or it's base form url

		Example Input: getForm("1569")
		Example Input: getForm("1569", date_start=datetime.datetime.now())
		Example Input: getForm("detailed_prospect_data")
		"""

		date_start = date_start or "2019-12-19"
		date_finish = date_finish or datetime.datetime.now()

		if (isinstance(date_start, datetime.date)):
			date_start = date_start.strftime("%Y-%m-%d")

		if (isinstance(date_finish, datetime.date)):
			date_finish = date_finish.strftime("%Y-%m-%d")

		for _report_id in PyUtilities.common.ensure_container(report_id):
			if (report_id == "xml"):
				frame = pandas.DataFrame(self.soup_list)

				dtype = {
					# "url_video": object,
					"url_picture": object,
				}
				for (key, value) in dtype.items():
					frame[key] = frame[key].astype(value)

				yield frame
				continue

			if (f"{_report_id}".isnumeric()):
				url = f"https://showmojo.com/api/v3/reports/custom?report_id={_report_id}&start_date={date_start}&end_date={date_finish}"
			elif (_report_id in ("detailed_prospect_data", "high_level_metrics", "detailed_listing_data", "listing_and_showing_metrics", "prospect_showing_data", "listing_performance")):
				url = f"https://showmojo.com/api/v3/reports/{_report_id}?start_date={date_start}&end_date={date_finish}"
			else:
				raise KeyError(f"Unknown *report_id*: '{_report_id}'")

			logging.info(f"Getting report '{_report_id}': {url}")
			response = requests.request("POST", url, auth=self.authorization)
			response.raise_for_status()

			catalogue = response.json()["response"]
			match (catalogue["status"]):
				case "success":
					yield pandas.DataFrame(catalogue["data"])

				case _:
					raise KeyError(f"Unknown status: '{catalogue['status']}'", catalogue)

	def getStandard(self, *args, **kwargs):
		return tuple(self.yieldAllStandard(*args, **kwargs))

	def getReport(self, *args, **kwargs):
		return tuple(self.yieldReport(*args, **kwargs))
