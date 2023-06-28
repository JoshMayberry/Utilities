import os
import sys
import logging
import contextlib

import trello

import PyUtilities.common
from PyUtilities.datasource.common import config

@contextlib.contextmanager
def getConnection(board_id, *, connection=None, **kwargs):
	""" Retuns an object to use for connecting to Rent Manager.
	See: https://github.com/tghw/trello-py
	See: https://www.reddit.com/r/trello/comments/4axfcd/comment/d14ok3k/?utm_source=share&utm_medium=web2x&context=3

	Example Input: getConnection(board_id)
	"""

	if (connection is not None):
		yield connection
		return

	with TrelloConnection(board_id, **kwargs) as connection:
		yield connection

class TrelloConnection():
	def __init__(self, board_id, *, key=None, token=None, **kwargs):
		self.initKwargs = kwargs

		self.board_id = board_id
		self.key = key or config("key", "trello", **(kwargs.get("configKwargs") or {}))
		self.token = token or config("token", "trello", **(kwargs.get("configKwargs") or {}))

		self.connection = None

		self._customField = None
		self._board = None
		self._card = None
		self._list = None
		
	def __enter__(self):
		logging.info("Connecting to Trello...")
		self.connection = trello.TrelloApi(self.key, self.token)
		return self

	def __exit__(self, type, value, traceback):
		self.connection = None

	@property
	def customField(self):
		if (self._customField is not None):
			return self._customField

		self._customField = {}
		for item in self.connection.boards.get_custom_fields(self.board_id):
			catalogue = {
				"name": item.get("name"),
				"type": item.get("type"),
			}

			if ("options" in item):
				_catalogue = {}
				for _item in item["options"]:
					value = _item.get("value", {})
					_catalogue[_item.get("id")] = value.get("text") or value.get("date") or value.get("number")
				catalogue["options"] = _catalogue

			self._customField[item["id"]] = catalogue

		return self._customField

	@property
	def list(self):
		if (self._list is not None):
			return self._list

		self._list = {item["id"]: item.get("name") for item in self.connection.boards.get_list(self.board_id)}
		return self._list

	@property
	def card(self):
		if (self._card is not None):
			return self._card

		_list = self.list
		_customField = self.customField

		self._card = {}
		for item in self.connection.boards.get_card(self.board_id, customFieldItems=True):
			catalogue = {
				"name": item.get("name"),
				"description": item.get("desc"),
				"list": _list.get(item.get("idList")),
				"url": item.get("shortUrl"),
				"url_id": item.get("shortLink"),
				"date_start": item.get("start"),
				"date_due": item.get("due"),
				"date_dueComplete": item.get("dueComplete"),
				"date_lastActivity": item.get("dateLastActivity"),
			}

			if ("labels" in item):
				catalogue["label"] = [_item.get("name") for _item in item["labels"]]

			if ("customFieldItems" in item):
				_catalogue = {}
				for _item in item["customFieldItems"]:
					field = _customField.get(_item["idCustomField"], {})

					value = None
					match (field.get("type")):
						case "text":
							value = _item.get("value", {}).get("text")

						case "date":
							value = _item.get("value", {}).get("date")

						case "number":
							value = _item.get("value", {}).get("number")

						case "list":
							value = field["options"][_item["idValue"]]

						case _:
							print("-- field:", field)
							print("-- _item:", _item)
							raise NotImplementedError("Unknown Trello Custom Field Type")

					_catalogue[_customField[_item["idCustomField"]]["name"]] = value
				catalogue["customField"] = _catalogue

			self._card[item["id"]] = catalogue

		return self._card
