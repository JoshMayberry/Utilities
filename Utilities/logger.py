import os
import sys

import logging

if (__name__ == "__main__"):
	import common
else:
	from . import common

NULL = common.NULL

levelCatalogue = common._dict({
	"d": "DEBUG", 		1: "${d}", 
	"i": "INFO", 		2: "${i}", 
	"w": "WARNING", 	3: "${w}", 
	"e": "ERROR", 		4: "${e}", 
	"c": "CRITICAL", 	5: "${c}", 
	None: "NOTSET", 
}, caseSensitive = False, typeSensitive = False)

def configure(level = NULL, fileName = None, fileMode = None, 
	formatter = None, formatter_timestamp = None, formatter_style = None, 
	streamHandler = None, handlers = None):
	"""Changes how the logger will behave.
	Note: Can only be called once, and before any other logging function.

	level (int) - What level of severity to use
		- If None: Will use the default level

	fileName (str) - Where the file should be located
		- If None: Will print to the cmd window

	fileMode (str) - How to interact with the log file
		~ r: open for reading
		~ w: open for writing, truncating the file first
		~ x: open for exclusive creation, failing if the file already exists
		~ a: open for writing, appending to the end of the file if it exists (default)
		~ b: binary mode
		~ t: text mode (default)
		~ +: open a disk file for updating (reading and writing)

	formatter (str) - How each entry is formatted
		~ See: https://docs.python.org/3.6/library/logging.html#logrecord-attributes

	formatter_timestamp (str) - How each timestamp is formatted
		~ See: https://docs.python.org/3.6/library/time.html#time.strftime

	Example Input: configure()
	Example Input: configure(level = 1)
	Example Input: configure(fileName = "test.log")
	Example Input: configure(formatter = "%(levelname)s:%(message)s")
	Example Input: configure(formatter = "%(asctime)s %(levelname)s:%(message)s", formatter_timestamp = "%m/%d/%Y %I:%M:%S %p")
	"""
	global levelCatalogue

	def yieldKwargs():
		if (fileName is not None):
			yield "filename", fileName
		
		if (fileMode is not None):
			yield "filemode", fileMode

		if (formatter is not None):
			yield "format", formatter

		if (formatter_timestamp is not None):
			yield "datefmt", formatter_timestamp

		if (formatter_style is not None):
			yield "style", formatter_style

		if (level is not NULL):
			yield "level", levelCatalogue.get(level)

		if (streamHandler is not None):
			yield "stream", streamHandler

		if (handlers is not None):
			yield "handlers", handlers

	##################################

	logging.basicConfig(**dict(yieldKwargs()))

def setLevel(level = None):
	"""Changes the severity level to log for.

	level (int) - What level of severity to use
		- If None: Will use the default level

	Example Input: setLevel()
	Example Input: setLevel(1)
	"""

	logging.setLevel(levelCatalogue.get(level))

def debug(message):
	logging.debug(message)

def info(message):
	logging.info(message)

def warning(message):
	logging.warning(message)

def error(message, includeTraceback = False):
	if (includeTraceback):
		logging.exception(message)
	else:
		logging.error(message)

def critical(message):
	logging.critical(message)

def getLogger(label = None):
	return logging.getLogger(label or __name__)











configure(level = 1)#, formatter = "%(levelname)s:%(message)s")
# setOutput("H:/Python/modules/Utilities/test.log")

logging.debug('This message should go to the log file')
logging.info('So should this')
logging.warning('And this, too')

# log.info("Lorem")
# log.debug("Ipsum")


 
# try:
# 	exit(main())
# except Exception:
# 	logging.exception("Exception in main(): ")
# 	exit(1)
