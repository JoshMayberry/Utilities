import os
import sys
import logging
import datetime
import requests

import PyUtilities.common
import PyUtilities.logger
from PyUtilities.datasource.common import config
import PyUtilities.datasource.general

def getConnection(*args, connection=None, **kwargs):
	""" Retuns an object to use for connecting to PhoneBurner.

	Example Input: getConnection()
	"""

	if (connection is not None):
		return connection

	return PhoneBurnerConnection(*args, **kwargs)

def select(endpoint_name, **kwargs):
	""" Returns the data from an api endpoint of PhoneBurner

	Example Input: select("folder")
	Example Input: select("contact", limit=3, page_size=2)
	"""

	connection = getConnection(**kwargs)

	data = []

	data.append(*connection.select(endpoint_name, **kwargs))

	return tuple(data)

class PhoneBurnerConnection():
	def __init__(self, *, token=None, client_id=None, client_secret=None, configKwargs=None, **kwargs):
		""" A helper object for working with PhoneBurner.
		See: https://www.phoneburner.com/developer/authentication#index

		token (str) - Generate a "Personal Access Token" when creating a "Custom Application"

		Example Input: ShowMojoConnection()
		"""

		configKwargs = configKwargs or {}
		self.token = token or config("token", "phoneburner", **(configKwargs or {}))
		self.client_id = client_id or config("client_id", "phoneburner", **(configKwargs or {}))
		self.client_secret = client_secret or config("client_secret", "phoneburner", **(configKwargs or {}))

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_val, exc_tb):
		pass

	# catalog_endpoint = {
	# 	"tranquility": True,
	# 	"folders": True,
	# 	"voicemails": True,
	# 	"contacts": True,
	# 	"content": True,
	# 	"customfields": True,
	# 	"dialsession": True,
	# 	"members": True,
	# 	"tags": True,
	# 	"phonenumber": True,
	# }

	def select(self, endpoint_name, **kwargs):
		if (not hasattr(self, f"_urlFor__{endpoint_name}")):
			raise ValueError(f"Unknown PhoneBurner *endpoint_name* '{endpoint_name}'")

		for item in getattr(self, f"_urlFor__{endpoint_name}")(**kwargs):
			yield item

	def _urlFor__test(self, **kwargs):
		for item in self.yield_raw("tranquility", **kwargs):
			yield item

	def _urlFor__folder(self, **kwargs):
		for (index, catalogue) in self.yield_raw("folders", **kwargs):
			yield {
				"folder_id": catalogue["folder_id"],
				"name": catalogue["folder_name"],
				"description": catalogue["description"],
			}

	def _urlFor__contact(self, **kwargs):
		for catalogue in self.yield_raw("contacts", **kwargs):

			customFields = {}
			for field in catalogue["custom_fields"]:
				customFields[field["name"]] = field["value"]

			yield {
				"user_id": catalogue["user_id"],
				"lead_id": catalogue["lead_id"],
				"owner_id": catalogue["owner_id"],
				"member_id": catalogue["member_id"],
				"contact_owner_id": catalogue["contact_owner_id"],
				"contact_user_id": catalogue["contact_user_id"],

				"category_id": catalogue["category"]["category_id"],
				"category_name": catalogue["category"]["name"],
				"category_description": catalogue["category"]["description"],

				"name_first": catalogue["first_name"],
				"name_last": catalogue["last_name"],
				"status_call": catalogue["call_result"],

				"email": catalogue["primary_email"],
				"phone": catalogue["primary_phone"],
				"zipcode": catalogue["raw_zip"],
				"comment": catalogue["notes"].get("notes", None),
				"community_name": customFields.get("Community Name", None),
				"source": customFields.get("Lead Source", None),

				"count_call_total": catalogue["total_calls"],
				"rating": catalogue["rating"],

				"is_nocall": catalogue["do_not_call"],
				"is_archived": catalogue["archived"],
				"is_removed": catalogue["removed"],
				"is_viewed": catalogue["viewed"],
				"is_sale": customFields.get("For Sale or For Rent", None) == "For Sale",

				"date_added": catalogue["date_added"],
				"date_last_call": catalogue["last_call_time"],
				"date_contacted": catalogue["contacted"],
				"date_reachout": datetime.datetime.strptime(customFields.get("Date Prospect Reached Out To Us", None), "%Y%m%d"),
				"pb_date_modified": catalogue["date_modified"],
			}
		
	def _urlFor__contact_activity(self, *, contact_id=None, days_ago=None, **kwargs):
			for _contact_id in PyUtilities.common.ensure_container(PyUtilities.common.requiredArg(contact_id, f"*contact_id* required for *contact_activity*")):
				for catalogue in self.yield_raw("contacts", f"{_contact_id}/activities", json_name="contact_activities", queryParams={ "days": days_ago or 1, "contact_id": _contact_id }):
					catalogue["contact_id"] = _contact_id

					yield catalogue

	def _urlFor__member(self, **kwargs):
		for item in self.yield_raw("members", **kwargs):
			# item.pop("_link")
			yield item

	def _urlFor__content(self, **kwargs):
		for item in self.yield_raw("content", queryParams={ "type": "script", "list": "both" }, **kwargs):
			yield item

	def _urlFor__tag(self, **kwargs):
		for item in self.yield_raw("tags", **kwargs):
			yield item

	def _urlFor__customfield(self, **kwargs):
		for item in self.yield_raw("customfields", **kwargs):
			yield item

	def _urlFor__dialsession(self, date_start=None, date_end=None, **kwargs):
		count_yielded = 0
		for (_date_start, _date_end) in PyUtilities.datasource.general.yield_datePair(date_start=date_start, date_end=date_end, frequency="D"):
			for (user_id, catalogue) in self.yield_raw("dialsession", "usage", count_yielded=count_yielded, queryParams={ "date_start": _date_start.strftime("%Y-%m-%d"), "date_end": _date_end.strftime("%Y-%m-%d") }, **kwargs):
				catalogue["user_id"] = user_id
				catalogue["date_session"] = _date_start

				yield catalogue
				count_yielded += 1

	def yield_raw(self, endpoint_name, extra=None, *, queryParams=None, json_name=None, limit=None, page_size=100, offset=1, count_yielded=0, **kwargs):
		""" Returns the contents of the given endpoint_name.
		See: https://www.phoneburner.com/developer/route_list

		Example Input: yield_raw("tranquility")
		Example Input: yield_raw("content", queryParams={ "type": "script", "list": "both" }
		"""

		if (limit and (count_yielded >= limit)):
			return

		if (limit and (limit < 100) and (limit < page_size)):
			page_size = limit # No need to ask for more info than we actually will use

		hasMore = True
		while hasMore:
			result = self._makeRequest(endpoint_name, extra=extra, offset=offset, queryParams=queryParams, json_name=json_name, page_size=page_size)

			page = result.pop("page", 0)
			page_size = result.pop("page_size", 0)
			total_pages = result.pop("total_pages", 0)
			total_results = result.pop("total_results", 0)
			logging.debug(PyUtilities.logger.debugging and {"page": page, "page_size": page_size, "total_pages": total_pages, "total_results": total_results})

			_json_name = json_name or extra or endpoint_name
			if (total_results):
				logging.info(f"Got {offset} of {total_results} pages for '{_json_name}'");

			container = result[_json_name] if (_json_name in result) else ((key, value) for (key, value) in result.items() if (key.isnumeric()))
			for catalogue in container:
				if (not isinstance(catalogue, list)):
					yield catalogue
					
					count_yielded +=1
					if (limit and (count_yielded >= limit)):
						return

					continue

				for item in catalogue:
					yield item

					count_yielded +=1
					if (limit and (count_yielded >= limit)):
						return

			if (page >= total_pages):
				return

	def _makeRequest(self, endpoint_name, extra=None, json_name=None, *, queryParams=None, page_size=100, offset=1):
		url = f"https://www.phoneburner.com/rest/1/{endpoint_name}" + (f"/{extra}" if extra else "")
		logging.info(f"Sending '{url}' to PhoneBurner")

		response = requests.request("GET", url,
			headers={
				"Content-Type": "application/json",
				"Authorization": f"Bearer {self.token}",
			},
			params={
				"page_size": page_size,
				"page": offset,
				**(queryParams or {}),
			}
		)
		response.raise_for_status()

		response_json = response.json()
		if (response_json["http_status"] != 200):
			raise NotImplementedError(response_json)

		try:
			return response_json[json_name or extra or endpoint_name]
		except Exception as error:
			logging.error(response_json)
			raise error

if (__name__ == "__main__"):
	PyUtilities.logger.logger_info()

	with getConnection() as connection:
		# for item in connection.select("contact", limit=1):
		for item in connection.select("contact_activity", contact_id=978253340, days=30, limit=1):
		# for item in connection.select("dialsession", date_start=dateutil.relativedelta.relativedelta(days=3), date_end=datetime.datetime.now()):
		# for item in connection.select("folder"):
			print("@0", item)