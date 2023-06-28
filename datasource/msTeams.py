import os
import sys
import logging

import pymsteams

import PyUtilities.common
from PyUtilities.datasource.common import config

def insert(data, *, webhook=None, configKwargs=None, severity=None, title=None, **kwargs):
	""" Posts a message on MS Teams.
	See: https://pypi.org/project/pymsteams/
	Use: https://stackoverflow.com/questions/59371631/send-automated-messages-to-microsoft-teams-using-python/59371723#59371723
	TODO: https://learn.microsoft.com/en-us/microsoftteams/platform/task-modules-and-cards/cards/cards-format?tabs=adaptive-md%2Cdesktop%2Cconnector-html#user-mention-in-incoming-webhook-with-adaptive-cards

	Example Input: insert("Lorem Ipsum")
	Example Input: insert(str(error), severity=2, webhook=config("webhook", "teams_unittest"))
	"""

	webhook = webhook or config("webhook", "teams_default")
	teamsMessage = pymsteams.connectorcard(webhook)

	if (title):
		teamsMessage.title(title)

	match severity:
		# Use: https://colordesigner.io/gradient-generator
		case None | 0:
			teamsMessage.color("#2196f3")

		case 1:
			teamsMessage.color("#927beb")

		case 2:
			teamsMessage.color("#d653c2")

		case 3:
			teamsMessage.color("#f81b7e")

		case _:
			teamsMessage.color("#F3212D")

	teamsMessage.text(data)

	logging.info(f"MS Teams Payload: '{teamsMessage.printme()}'")
	teamsMessage.send()
