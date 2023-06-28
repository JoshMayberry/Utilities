import os
import pandas
import platform
import configparser

import PyUtilities.json_expanded
PyUtilities.json_expanded.makeDefault(datetime_method="string")

pandas.options.mode.chained_assignment = "raise"  # See: https://stackoverflow.com/questions/20625582/how-to-deal-with-settingwithcopywarning-in-pandas/53954986#53954986

is_dev = (platform.node() == "DESKTOP-8J5RE8C")

detaultConfig = os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))), "settings.ini")

parser = None
def config(_key=None, _section="postgres_prod", *, filename=detaultConfig, useCached=False, defaultValue=None, key=None, section=None, **kwargs):
	""" Reads value(s) from the config file.

	section (str) - Which ini section to read from
	key (str) - Which key to return from the ini file
		- If None: Returns a dictionary of all items in *section*
	filename (str) - Where the ini file is located
	useCached (bool) - If the config file loaded last time should be reused
	defaultValue (any) - What shoudl be used if *key* is not in *section*

	Example Input: config()
	Example Input: config(section="ipsum")
	Example Input: config(filename="lorem.ini")
	Example Input: config(key="token", section="dropbox")
	"""
	global parser

	key = key or _key
	section = section or _section

	if (not useCached or not parser):
		parser = configparser.ConfigParser()
		parser.read(filename)
 
	if (not parser.has_section(section)):
		raise ValueError(f"Section '{section}' not found in the '{filename}' file")

	if (key):
		return parser[section].get(key, defaultValue)

	return {key: value for (key, value) in parser.items(section)}