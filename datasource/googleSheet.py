import os
import sys
import string
import logging

import pandas

import PyUtilities.common
from PyUtilities.datasource.common import config

def select(book_id, sheet_name=None, cell_range=None, **kwargs):
	""" Returns data from the google sheet.
	Use: https://towardsdatascience.com/read-data-from-google-sheets-into-pandas-without-the-google-sheets-api-5c468536550
	See: https://stackoverflow.com/questions/33713084/download-link-for-google-spreadsheets-csv-export-with-multiple-sheets/33727897#33727897

	Example Input: select(book_id)
	Example Input: select(book_id, "Sheet1")
	Example Input: select(book_id, "Sheet1", "A1:S27")
	"""

	if (not sheet_name):
		return pandas.read_csv(f"https://docs.google.com/spreadsheets/d/{book_id}/export?format=csv", **kwargs)
	
	url = f"https://docs.google.com/spreadsheets/d/{book_id}/gviz/tq?tqx=out:csv&sheet={sheet_name.replace(' ', '%20')}"
	if (cell_range):
		url += f"&range={cell_range}"
	logging.info(f"Loading Google Sheet from: {url}")
	return pandas.read_csv(url, **kwargs)

def number2Column(number):
	# Use: https://stackoverflow.com/questions/23861680/convert-spreadsheet-number-to-column-letter/28782635#28782635
	
	text = ""
	alist = string.ascii_uppercase
	while number:
		mod = (number-1) % 26
		number = int((number - mod) / 26)  
		text += alist[mod]
	return text[::-1]

def column2Number(text):
	# Use: https://stackoverflow.com/questions/7261936/convert-an-excel-or-spreadsheet-column-letter-to-its-number-in-pythonic-fashion/12640614#12640614
	
	number = 0
	for c in text:
		if c in string.ascii_letters:
			number = number * 26 + (ord(c.upper()) - ord('A')) + 1
	return number
