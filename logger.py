import time
import logging
import collections

import PyUtilities.common

debugging = False
logger = logging.getLogger(__name__)

def setLogger(label=None):
	global logger

	logger = logging.getLogger(label)
	return logger

def logger_debug(silence_azure=True, silence_urlib=False, silence_paramiko=True):
	""" Changes the log level to debug.
	See: https://docs.python.org/3/howto/logging.html

	Example Input: logger_debug()
	Example Input: logger_debug(silence_azure=False)
	"""
	global debugging

	debugging = True # Use this to short-circuit expensive f-strings
	logging.basicConfig(level=logging.DEBUG)

	if (silence_azure):
		logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)

	if (silence_urlib):
		logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

	if (silence_paramiko):
		logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

def logger_info(silence_azure=True, silence_urlib=False, silence_paramiko=True):
	""" Changes the log level to info.
	See: https://docs.python.org/3/howto/logging.html

	Example Input: logger_info()
	Example Input: logger_info(silence_azure=False)
	"""

	logging.basicConfig(level=logging.INFO)

	if (silence_azure):
		logging.getLogger('azure.core.pipeline.policies.http_logging_policy').setLevel(logging.WARNING)

	if (silence_urlib):
		logging.getLogger('urllib3.connectionpool').setLevel(logging.WARNING)

	if (silence_paramiko):
		logging.getLogger('paramiko.transport').setLevel(logging.WARNING)

logger_timers = collections.defaultdict(dict)
def logger_timer(label=None):
	""" A decorator that records how long a function took to execute.
	If the logger level is not info or debug, will not do anything.
	See: https://docs.python.org/3/howto/logging.html#optimization

	label (str) - What the timer is called
		- If None: Will assign a unique number as the label for this timer

	EXAMPLE USE
		@logger_timer()
		def longFunction():
			pass

	EXAMPLE USE
		@logger_timer("lorem")
		def longFunction():
			pass
	"""

	if (not logger.isEnabledFor(logging.INFO)):
		def decorator(myFunction):
			return myFunction
		return decorator

	def decorator(myFunction):
		def wrapper(*args, **kwargs):
			nonlocal label

			label = logger_timer_start(label)
			answer = myFunction(*args, **kwargs)
			logger_timer_end(label)
			return answer
		return wrapper
	return decorator

def logger_timer_start(label=None):
	if (label is None):
		label = len(logger_timers)
		while label in logger_timers:
			label += 1

	catalogue = logger_timers[label]

	# logging.info(f"Starting the '{label}' timer")
	catalogue["start"] = time.perf_counter()
	return label

def logger_timer_end(label):
	# logging.info(f"Ending the '{label}' timer")
	catalogue = logger_timers[label]
	catalogue["end"] = time.perf_counter()

def logger_timer_print(label=None):
	""" Prints the times for timers.

	label (str) - Which timer to print the time for
		- If None: Will print for all timers
		- If tuple: WIll print for each timer in the list

	Example Input: logger_timer_print()
	Example Input: logger_timer_print("lorem")
	"""

	for _label in PyUtilities.common.ensure_container(label, convertNone=False, returnForNone=lambda: logger_timers.keys()):
		catalogue = logger_timers.get(_label)
		start_time = catalogue.get("start")
		if (start_time is not None):
			logging.info(f"{_label}: {catalogue.get('end', time.perf_counter()) - start_time:.2f}")

def logger_runtime(log_open, log_save):
	""" A decorator that starts directing stdout and stderr to a handler for the duration of a function

	EXAMPLE USE
		@logger_runtime()
		def longFunction(log_open=log_open, log_save=log_save):
			pass
	"""

	def decorator(myFunction):
		def wrapper(self, *args, **kwargs):

			log_open()
			try:
				answer = myFunction(self, *args, **kwargs)
			except Exception as error:
				log_save(error=error)
				raise error
			log_save()

			return answer
		return wrapper
	return decorator
