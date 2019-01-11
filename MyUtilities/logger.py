import os
import sys
import glob

import operator
import threading
import traceback

import logging
import logging.handlers

import MyUtilities.common

NULL = MyUtilities.common.NULL

#Use: https://realpython.com/python-logging/
#Use: https://docs.python.org/3.6/howto/logging.html#advanced-logging-tutorial
#Use: https://fangpenlin.com/posts/2012/08/26/good-logging-practice-in-python/
#Use: https://www.blog.pythonlibrary.org/2014/02/11/python-how-to-create-rotating-logs/

class LabelUsedError(Exception): pass
class LoggerExistsError(Exception): pass

levelCatalogue = MyUtilities.common._dict({
	"n": "NOTSET", 		0: "${n}", 	"NOTSET": 	"${n}", 	None: "${n}", 
	"d": "DEBUG", 		1: "${d}", 	"DEBUG": 	"${d}", 
	"i": "INFO", 		2: "${i}", 	"INFO": 	"${i}", 
	"w": "WARNING", 	3: "${w}", 	"WARNING": 	"${w}", 
	"e": "ERROR", 		4: "${e}", 	"ERROR": 	"${e}", 
	"c": "CRITICAL", 	5: "${c}", 	"CRITICAL": "${c}", 
}, caseSensitive = False, typeSensitive = False)

#Monkey Patches
def _mp_FileHandler__open(self):
	"""Overridden to ensure file directory exists.
	Modified code from unutbu on: https://stackoverflow.com/questions/20666764/python-logging-how-to-ensure-logfile-directory-is-created/20667049#20667049
	"""

	os.makedirs(os.path.dirname(self.baseFilename), exist_ok = True)
	return old_FileHandler__open(self)

old_FileHandler__open = logging.FileHandler._open
logging.FileHandler._open = _mp_FileHandler__open

if (__name__ == "__main__"):
	_srcfile = logging._srcfile
else:
	_srcfile = os.path.normcase(_mp_FileHandler__open.__code__.co_filename)

def currentframe():
	"""Overridden to ignore this module too."""
	global _srcfile

	frame = sys._getframe(1)
	exclude = (logging._srcfile, _srcfile)
	while hasattr(frame, "f_code"):
		if (os.path.normcase(frame.f_code.co_filename) not in exclude):
			return frame
		frame = frame.f_back
	return frame

def _mp_Logger_findCaller(self, stack_info = False):
	"""Overridden to ignore this module too."""

	frame = currentframe()
	code = frame.f_code

	if (stack_info):
		sinfo = f"Stack (most recent call last):\n{''.join(traceback.format_list(traceback.extract_stack(frame)))}".rstrip("\n")
	else:
		sinfo = None
	
	return code.co_filename, frame.f_lineno, code.co_name, sinfo

logging.Logger.findCaller = _mp_Logger_findCaller

#Logger Functions
loggerLock = threading.RLock()
loggerCatalogue = {}
def getLogger(label = None, *, config = None):
	"""Returns a Logger handle.
	Special thanks to Louis LC for how to get the name of the module that called this function on: https://stackoverflow.com/questions/1095543/get-name-of-calling-functions-module-in-python/5071539#5071539

	Example Input: getLogger()
	Example Input: getLogger(__name__)
	"""
	global loggerCatalogue

	if (label is None):
		if (__name__ == "__main__"):
			label = "__main__"
		else:
			label = sys._getframe(1).f_globals["__name__"]

	elif (label is NULL):
		label = None

	elif (isinstance(label, Logger)):
		return label

	with loggerLock:
		if (label in loggerCatalogue):
			return loggerCatalogue[label]
		return Logger(label = label, config = config)

class Logger():
	"""Helps automate the use of logging.Logger objects."""

	def __init__(self, label = None, *, config = None):
		self._setLogger(label)
		self._setConfig(config)

		self.silent = False

	@MyUtilities.common.makeProperty()
	class label():
		def setter(self, value):
			global loggerCatalogue

			if (hasattr(self, "_label")):
				errorMessage = f"This logger already has the label {self._label}, and it is trying to be replaced by {value}"
				raise LabelUsedError(errorMessage)

			if (value in loggerCatalogue):
				errorMessage = f"The label {value} is already being used by another logger"
				raise LoggerExistsError(errorMessage)

			self._label = value
			with loggerLock:
				loggerCatalogue[value] = self

		def getter(self):
			return self._label

	def _setLogger(self, logger = None):
		"""Sets the logger to be used.

		logger (logging.Logger) - What logger to use
			- If None: Will use the module level name as the label

		Example Input: _setLogger()
		Example Input: _setLogger(None)
		Example Input: _setLogger("lorem")
		Example Input: _setLogger(__name__)
		"""

		if (logger is NULL):
			self.label = None

		elif (logger is None):
			if (__name__ == "__main__"):
				self.label = "__main__"
			else:
				self.label = sys._getframe(3).f_globals["__name__"]

		elif (isinstance(logger, logging.Logger)):
			self.label = logger.name
			self.thing = logger
			return

		else:
			self.label = logger

		self.thing = logging.getLogger(self.label)

	def _setConfig(self, instructions = None):
		"""Builds the configuration for this logger.

		instructions (dict) - What configuration to apply
			#Logger Sections
			None:
				level (int): What severity level to start at

			#Handler Sections
			A unique name (str):
				type (str): What kind of handler to add
				**variable for add function (str): value for variable (any)

		Example Input: _setConfig()
		Example Input: _setConfig({None: {"level": 1}})
		Example Input: _setConfig({None: {"level": 1, "console": {"type": "stream", "level": 1}})
		"""

		def applyLogger(catalogue):
			nonlocal self

			for key, value in catalogue.items():
				if (key == "level"):
					self.setLevel(level = value)
					continue
				
				raise NotImplementedError()

		def applyHandler(catalogue):
			nonlocal self

			self.addHandler(catalogue.pop("type", "null"), **catalogue)

		#########################################

		if (not instructions):
			return

		if (not isinstance(instructions, dict)):
			raise NotImplementedError()

		for section, sectionCatalogue in instructions.items():
			if (section is None):
				applyLogger(sectionCatalogue)
			else:
				applyHandler({**sectionCatalogue})

	def quiet(self, state = True):
		"""Makes the logger not log things temporarily.

		Example Input: quiet()
		Example Input: quiet(state = False)
		"""

		self.silent = state

	def setLevel(self, level = None):
		"""Changes the severity level to log for.

		level (int) - What level of severity to use
			- If None: Will use the default level

		Example Input: setLevel()
		Example Input: setLevel(1)
		"""
		global levelCatalogue

		self.thing.setLevel(levelCatalogue.get(level))

	def addHandler(self, handler, **kwargs):
		"""Adds handlers to this logger.

		handler (logging.Handler) - Adds this handler directly

		Example Input: addHandler(handler)
		"""

		if (not isinstance(handler, logging.Handler)):
			self._addHandler_functionCatalogue[handler](self, **kwargs)
		else:
			self.thing.addHandler(handler)

	def addStream(self, stream = None, **kwargs):
		"""Adds a stream handler to this logger.

		stream (any) - What stream to use
			- If None: Will use sys.stderr

		Example Input: addStream()
		Example Input: addStream(stream = sys.stdout)
		"""

		handler = logging.StreamHandler(stream = stream)
		configureHandler(handler, **kwargs)
		self.thing.addHandler(handler)

	def addFile(self, name = None, mode = None, *, encoding = None, delay = False, historyCount = 1,
		maximum = None, timer = None, units = None, utc = True, **kwargs):
		"""Adds a file handler to this logger.

		name (str) - Where to save the file
			- If None: Will use the current working directory

		mode (str) - How to interact with the log file
			~ r: open for reading
			~ w: open for writing, truncating the file first
			~ x: open for exclusive creation, failing if the file already exists
			~ a: open for writing, appending to the end of the file if it exists (default)
			~ b: binary mode
			~ t: text mode (default)
			~ +: open a disk file for updating (reading and writing)

		encoding (str) - What kind of encoding to use for the log file
			- If None: Will not encode the file

		delay (bool) - Determiens if opening the file should wait until the first call to emit() for the generated handle
		historyCount (int) - How many old log files should be kept because of 'maximum' or 'timer'

		maximum (int) - What the maximum file size (in bytes) can be before a new log file should be used
			- If None: Will keep using the same log file

		timer (int) - How many units of time to wait before starting a new log file
			- If None: Will keep using the same log file

		units (str) - What units to count the timer in (default is hours)
			~ 'seconds', 'minutes', 'hours', 'days'; Only the first letter is needed

		utc (bool) - Determiens what time is used
			- If True: Uses UTC time
			- If False: Uses the computer's local time

		Example Input: addFile()
		Example Input: addFile("temp.log")
		"""

		mode = MyUtilities.common.ensure_default(mode, default = "a")
		name = MyUtilities.common.ensure_default(name, default = lambda: os.path.join(os.getcwd(), "temp.log"))

		if (maximum is not None):
			handler = logging.handlers.RotatingFileHandler(name, mode = mode, maxBytes = maximum, backupCount = historyCount, encoding = encoding, delay = delay)
		
		elif (timer):
			handler = logging.handlers.TimedRotatingFileHandler(name, interval = timer, when = units[0], utc = utc, backupCount = historyCount, encoding = encoding, delay = delay)

		else:
			handler = logging.FileHandler(name, mode = mode, encoding = encoding, delay = delay)

		configureHandler(handler, **kwargs)
		self.thing.addHandler(handler)

	def addSocket(self, host, port = None, *, udp = False):
		"""Adds a socket handler to this logger.

		Example Input: addSocket("192.168.0.1")
		"""

		raise NotImplementedError()

		if (udp):
			handler = logging.handlers.DatagramHandler(host, port)
		else:
			handler = logging.handlers.SocketHandler(host, port)
		
		configureHandler(handler, **kwargs)
		self.thing.addHandler(handler)

	def addEmail(self, address_to, address_from, password, subject = None, *, server = None, port = None, timeout = 1.0):
		"""Adds an email handler to this logger.

		address_to (str) - A valid email address to send to
		address_from (str) - A valid email address to send from
		password (str) - The password for 'address_from'
		subject (str) - What the email's subject will be

		server (str) - What email server is being used
			- If None: Will use gmail

		port (int) - What port to use
			- If None: 587

		Example Input: addEmail("lorem@gmail.com", "ipsum@gmail.com", "dolor")
		"""
		
		raise NotImplementedError()

		server = MyUtilities.common.ensure_default(server, default = "smtp.gmail.com")
		port = MyUtilities.common.ensure_default(port, default = 587)

		handler = logging.handlers.SMTPHandler((server, port), address_from, address_to, subject, credentials = (address_from, password), timeout = timeout)
		configureHandler(handler, **kwargs)
		self.thing.addHandler(handler)

	def addTemp(self, maxSize):
		"""Adds memory handler to this logger.

		Example Input: addTemp()
		"""

		raise NotImplementedError()

		handler = logging.handlers.MemoryHandler(maxSize, flushLevel = flushLevel, target = target, flushOnClose = flushOnClose)
		configureHandler(handler, **kwargs)
		self.thing.addHandler(handler)

	def addWebsite(self, host, url):
		"""Adds an http handler to this logger.

		Example Input: addWebsite()
		"""

		raise NotImplementedError()

		handler = logging.handlers.HTTPHandler(host, url, method = method, secure = secure, credentials = credentials, context = context)
		configureHandler(handler, **kwargs)
		self.thing.addHandler(handler)

	def addQueue(self, queue):
		"""Adds a queue handler to this logger.

		queue (queue.Queue) - The queue to send logs to

		Example Input: addQueue(queue)
		"""

		#Use: https://docs.python.org/3.6/library/logging.handlers.html#queuehandler
		#Use: https://docs.python.org/3.6/library/logging.handlers.html#queuelistener

		raise NotImplementedError()
		
		handler = logging.handlers.QueueHandler(queue)
		configureHandler(handler, **kwargs)
		self.thing.addHandler(handler)

	def addNull(self, **kwargs):
		"""Adds a do-nothing handler to this logger.
		See: https://docs.python.org/3.6/howto/logging.html#configuring-logging-for-a-library

		Example Input: addNull()
		"""

		handler = logging.NullHandler
		self.thing.addHandler(handler)

	_addHandler_functionCatalogue = MyUtilities.common._dict({
		"null": addNull, None: "${null}", 
		"temp": addTemp, 
		"file": addFile, 
		"email": addEmail, 
		"queue": addQueue, 
		"stream": addStream, 
		"socket": addSocket, 
		"website": addWebsite, 
	}, caseSensitive = False, typeSensitive = False)

	def removeHandler(self, handler = None):
		"""Removes handlers from this logger.

		handler (logging.Handler) - What handler to remove
			- If None: Will remove all handlers

		Example Input: removeHandler()
		"""

		if (not self.thing.handlers):
			return

		if (handler is not None):
			raise NotImplementedError(handler)

		for handler in self.thing.handlers:
			self.thing.removeHandler(handler)

	def debug(self, message, *args, includeTraceback = False, **kwargs):
		"""Logs a message with the severity level 'debug'.

		Example Input: debug("lorem ipsum")
		"""

		if (self.silent):
			return

		self.thing.debug(formatMessage(message, *args, **kwargs), exc_info = includeTraceback)

	def info(self, message, *args, includeTraceback = False, **kwargs):
		"""Logs a messagewith the severity level 'info'.

		Example Input: info("lorem ipsum")
		"""

		if (self.silent):
			return

		self.thing.info(formatMessage(message, *args, **kwargs), exc_info = includeTraceback)

	def warning(self, message, *args, includeTraceback = False, **kwargs):
		"""Logs a message aswith the severity level 'warning'.

		Example Input: warning("lorem ipsum")
		"""

		if (self.silent):
			return

		self.thing.warning(formatMessage(message, *args, **kwargs), exc_info = includeTraceback)

	def error(self, message, *args, includeTraceback = False, **kwargs):
		"""Logs a message with the severity level 'error'.

		Example Input: error("lorem ipsum")
		"""

		if (self.silent):
			return

		self.thing.error(formatMessage(message, *args, **kwargs), exc_info = includeTraceback)

	def critical(self, message, *args, includeTraceback = False, **kwargs):
		"""Logs a message as with the severity level 'critical'.

		Example Input: critical("lorem ipsum")
		"""

		if (self.silent):
			return

		self.thing.critical(formatMessage(message, *args, **kwargs), exc_info = includeTraceback)

	def yieldLogs(self, returnExisting = True, returnHistory = True):
		"""Yields where logs are being stored.

		returnExisting (bool) - Determines if only existing filesnames are returned
			- If False: The filenames are what the currentlog file would be called
			- If True: The filenames are actually on the system

		returnHistory (bool) - Determines if history log files should also be returned

		Example Input: yieldLogs()
		Example Input: yieldLogs(returnExisting = False)
		"""

		def yieldFile(fileName):
			if (returnHistory):
				fileList = glob.iglob(f"{fileName}*")
			else:
				fileList = (fileName,)

			for item in fileList:
				if ((not returnExisting) or (os.path.exists(fileName))):
					yield item

		########################################################

		for handler in self.thing.handlers:
			if (not isinstance(handler, logging.FileHandler)):
				continue

			for item in yieldFile(handler.baseFilename):
				yield item

	def getLogs(self, *args, **kwargs):
		"""A non-generator version of yieldLogs().

		Example Input: getLogs()
		"""

		return tuple(self.yieldLogs(*args, **kwargs))

def formatMessage(message, *args, **kwargs):
	"""Adds the kwargs to the end of the message."""

	def yieldMessage():
		yield f"{message}"

		if (args):
			yield f"; {'; '.join(f'{item}' for item in args)}"

		if (kwargs):
			yield f"; {'; '.join(f'{key}: {value}' for key, value in kwargs.items())}"

	###############################

	return "".join(yieldMessage())

def configureHandler(handler, *, level = NULL, formatter = NULL, timestamp = NULL, formatStyle = NULL, filterer = NULL, filter_nonLevel = False):
	"""Changes how the handler will behave.

	level (int) - What minimum level of severity to listen to messages for
		- If None: Will use the default level

	formatter (str) - How each entry is formatted
		~ See: https://docs.python.org/3.6/library/logging.html#logrecord-attributes
		- If NULL: Will use the default formatter for the given 'formatStyle'
		- If None: Will only print the message

	formatStyle (str) - Which formatting style to use
		~ See: https://docs.python.org/3.6/library/logging.html#logrecord-attributes
		- If None: Will use the f-string style

	timestamp (str) - How each timestamp is formatted
		~ See: https://docs.python.org/3.6/library/time.html#time.strftime

	filterer (Object) - A class with a filter() method
		~ See: https://docs.python.org/3.6/library/logging.html#filter-objects
		~ See: https://docs.python.org/3.6/howto/logging-cookbook.html#using-filters-to-impart-contextual-information

	filter_nonLevel (bool) - Determines if items that do not match the given level should be ignored

	Example Input: configureHandler(handler, level = 1)
	Example Input: configureHandler(handler, formatter = "{name} - {levelname} - {message}")
	Example Input: configureHandler(handler, formatter = "%(name)s - %(levelname)s - %(message)s", formatStyle = "%")
	"""

	timestamp = MyUtilities.common.ensure_default(timestamp, default = None, defaultFlag = NULL)
	formatStyle = MyUtilities.common.ensure_default(formatStyle, default = "{", defaultFlag = NULL)
	formatter = MyUtilities.common.ensure_default(formatter, default = logging._STYLES[formatStyle][1], defaultFlag = NULL)
	
	handler.setFormatter(logging.Formatter(formatter, datefmt = timestamp, style = formatStyle))

	if (level is not NULL):
		handler.setLevel(levelCatalogue.get(level))

	if (filterer is not NULL):
		handler.addFilter(filterer)

	if (filter_nonLevel):
		handler.addFilter(Filter_Level(handler))

def configureRoot(*, level = NULL, fileName = None, fileMode = None, 
	formatter = None, formatter_timestamp = None, formatter_style = None, 
	streamHandler = None, handlers = None):
	"""Changes how the root logger will behave.
	Note: This will reset the handlers given to the logger
	Special thanks to Carlos A. Ibarra for how to configure a logger after using it on: https://stackoverflow.com/questions/1943747/python-logging-before-you-run-logging-basicconfig/2588054#2588054

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

	Example Input: configureRoot()
	Example Input: configureRoot(level = 5)
	Example Input: configureRoot(fileName = "test.log")
	Example Input: configureRoot(formatter = "%(levelname)s:%(message)s")
	Example Input: configureRoot(formatter = "%(asctime)s %(levelname)s:%(message)s", formatter_timestamp = "%m/%d/%Y %I:%M:%S %p")
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

	root = logging.getLogger()
	for handler in root.handlers:
		self.thing.removeHandler(handler)
	logging.basicConfig(**dict(yieldKwargs()))

def quietRoot():
	"""Silences the output given to the root logger.

	Example Input: quietRoot()
	"""

	root = logging.getLogger()
	for handler in root.handlers:
		root.removeHandler(handler)
	logging.basicConfig(handlers = (logging.NullHandler(),))

#Filters
class Filter_Level(logging.Filter):
	def __init__(self, parent, level = None, comparer = None):
		"""Filters out anything that is not the given level.
		Modified code from srgerg on: https://stackoverflow.com/questions/8162419/python-logging-specific-level-only/8163115#8163115

		level (int) - What level of severity to use
			- If None: Will use the current level of 'parent'

		comparer (function) - A function used to compare the level numbers
			~ Should take two parameters and return a bool
			- If None; Will use: operator.is_

		Example Input: Filter_Level(self)
		Example Input: Filter_Level(self, level = 1)
		"""
		self.parent = parent
		self.level = level
		self.comparer = MyUtilities.common.ensure_default(comparer, default = operator.is_, consumeFunction = False)

	def filter(self, record):
		if (self.level is None):
			return self.comparer(record.levelno, self.parent.level)
		return self.comparer(record.levelno, self.level)

#User Functions
class LoggingFunctions():
	"""Logging functions meant to be inherited by an object."""

	def __init__(self, *, force_quietRoot = False, **kwargs):
		if (force_quietRoot):
			quietRoot()

		self._logger = getLogger(**kwargs)

	def log_debug(self, *args, **kwargs):
		self._logger.debug(*args, **kwargs)

	def log_info(self, *args, **kwargs):
		self._logger.info(*args, **kwargs)

	def log_warning(self, *args, **kwargs):
		self._logger.warning(*args, **kwargs)

	def log_error(self, *args, **kwargs):
		self._logger.error(*args, **kwargs)

	def log_critical(self, *args, **kwargs):
		self._logger.critical(*args, **kwargs)

	def log_getLogs(self, *args, **kwargs):
		return self._logger.getLogs(*args, **kwargs)

if (__name__ == "__main__"):
	quietRoot()
	if (False):
		logger = getLogger()
		logger.setLevel(1)
		logger.addStream(sys.stdout, level = 1, filter_nonLevel = True)
	else:
		config = {
			None: {
				"level": 1,
			},
			"console": {
				"type": "stream",
				"level": 1,
				"filter_nonLevel": True,
			},
			"disk": {
				"type": "file", 
				"delay": True, 
				"maximum": 20_000, 
				"name": os.path.join(os.getcwd(), "logs", os.environ.get('username'), "info.log"), 

				"level": "info", 
				"historyCount": 2, 
				"filter_nonLevel": True, 
			},
		}
		logger = getLogger(config = config)

		print(logger.thing)

	# logger.debug("Lorem")
	# logger.info("Ipsum")
	# logger.warning("Dolor")
	# logger.error("Sit")
	# logger.critical("Amet")

	print(logger.getLogs())
