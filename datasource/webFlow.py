import os
import sys
import logging

import webflowpy.Webflow

import PyUtilities.common
from PyUtilities.datasource.common import config

def select(collection_id, limit=-1, *, offset=0, token=None, configKwargs=None, **kwargs):
	""" Returns the data from a webflow collection.
	See: https://www.briantsdawson.com/blog/webflow-api-how-to-get-site-collection-and-item-ids-for-zapier-and-parabola-use

	collection_id (str) - Which collection to connect to
	limit (int) - How much data to return. If less than 1 will return everything
	offset (int) - Use in combination with limit being not less than 1

	Example Input: select(collection_id="623107ba68bd7ba11ca033c7")
	Example Input: select(collection_id="623107ba68bd7ba11ca033c7", limit=1)
	Example Input: select(collection_id="623107ba68bd7ba11ca033c7", limit=100, offset=100)
	"""

	token = token or config("token", "webflow_treehouse", **(configKwargs or {}))

	webflow_api = webflowpy.Webflow.Webflow(token=token)
	return webflow_api.collection(collection_id=collection_id, limit=limit, all=limit <= 0)["items"]

def insert(data, collection_id="623107ba68bd7ba11ca033c7", *, method="upsert", upsert_on="_id", live=False, token=None, configKwargs=None, **kwargs):
	""" Sends data to a webflow collection.
	See: https://www.briantsdawson.com/blog/webflow-api-how-to-get-site-collection-and-item-ids-for-zapier-and-parabola-use

	method (str) - How to handle sending the data
		- insert: Try adding it and throw an error if it already exists
		- drop: Drop all collection items in the folder and insert new collection items
	upsert_on (str) - What key to compare updates against
	live (bool) - If the change should be applied to the production server instead of the development server

	Example Input: insert([{Lorem: "ipsum"}])
	Example Input: insert([{Lorem: "ipsum"}], collection_id="623107ba68bd7ba11ca033c7")
	"""

	if (isinstance(data, pandas.DataFrame)):
		# See: https://pandas.pydata.org/pandas-docs/version/0.17.0/generated/pandas.DataFrame.to_dict.html#pandas.DataFrame.to_dict
		data = data.replace({numpy.nan: None}).to_dict("records")

	if (not len(data)):
		logging.info(f"No data to insert into '{table}'")
		return False

	token = token or config("token", "webflow_treehouse", **(configKwargs or {}))
	webflow_api = webflowpy.Webflow.Webflow(token=token)

	match method:
		case "drop":
			for item in webflow_api.items(collection_id=collection_id)["items"]:
				webflow_api.removeItem(collection_id=collection_id, item_id=item["_id"])

			for item in data:
				webflow_api.createItem(collection_id=collection_id, item_data=item, live=live)

		case "insert":
			for item in data:
				webflow_api.createItem(collection_id=collection_id, item_data=item, live=live)

		case "upsert":
			catalogue = {}
			catalogue = {item.get(upsert_on, None): item for item in webflow_api.items(collection_id=collection_id)["items"]}

			for item in data:
				item_existing = catalogue.get(item.get(upsert_on, None), None)
				if (not item_existing):
					if ("_draft" not in item):
						item["_draft"] = False

					if ("_archived" not in item):
						item["_archived"] = False

					webflow_api.createItem(collection_id=collection_id, item_data=item, live=live)
					continue

				# Check if any changes need to be made
				for (key, value) in item.items():
					if (item_existing.get(key, None) != value):
						webflow_api.patchItem(collection_id=collection_id, item_id=item_existing["_id"], item_data=item, live=live)
						break
	
		case _:
			raise KeyError(f"Unknown *method* '{method}'")
