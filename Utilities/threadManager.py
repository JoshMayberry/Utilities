import sys

import time
import queue
import threading
import contextlib

import Utilities as MyUtilities

NULL = MyUtilities.common.NULL


#Utility Functions
def _yieldKwargs(catalogue, selfObject = None):
	"""A helper function that looks through the given catalogue for kwargs to give to MyUtilities.common.runMyFunction."""

	includeSelf = catalogue.get("includeSelf", False)
	if (includeSelf):
		yield "includeSelf", includeSelf
		yield "selfObject", catalogue.get("selfObject", selfObject)

	includeEvent = catalogue.get("includeEvent", False)
	if (includeEvent):
		yield "includeEvent", includeEvent
		yield "event", catalogue.get("event", None)

	errorFunction = catalogue.get("errorFunction", None)
	if (errorFunction):
		yield "includeError", catalogue.get("includeError", None)
		yield "errorFunction", errorFunction
		yield "errorFunctionArgs", catalogue.get("errorFunctionArgs", None)
		yield "errorFunctionKwargs", catalogue.get("errorFunctionKwargs", None)

#Background Processes
class ThreadManager(MyUtilities.logger.LoggingFunctions):
	"""Manages a group of threads."""

	logger_config = {
			None: {
				"level": 1,
			},
			"console": {
				"type": "stream",
				"level": 1,
			},
		}

	def __init__(self, maxThreads = 50, logger_name = None, logger_config = None):
		"""Internal variables.

		maxThreads (int) - How many threads can run at once
			~ Crashes around 600
		"""
		MyUtilities.logger.LoggingFunctions.__init__(self, label = logger_name or __name__, config = logger_config or self.logger_config, force_quietRoot = __name__ == "__main__")

		self.maxThreads = maxThreads

		self.thread_catalogue = {}
		self.thread_unnamed = set()
		self.thread_functions = set()
		self.thread_lock = threading.RLock()

		self.listener_catalogue = {}
		self.listener_unnamed = set()
		self.listener_functions = set()
		self.listener_lock = threading.RLock()
		self.pauseOnDialog = set()
	
		self.callback_queue = queue.Queue() #Used to pass functions between threads

	def getThread(self, label):
		"""Returns the thread if it is being managed by this threadManager.

		Example Input: getThread("autoSave")
		"""
		
		return self._get(label, catalogue = self.thread_catalogue, unnamed = self.thread_unnamed, functions = self.thread_functions, lock = self.thread_lock)

	def getListener(self, label):
		"""Returns the listener if it is being managed by this threadManager.

		Example Input: getListener("autoSave")
		"""

		return self._get(label, catalogue = self.listener_catalogue, unnamed = self.listener_unnamed, functions = self.listener_functions, lock = self.listener_lock)

	def _get(self, label, catalogue = None, unnamed = None, functions = None, lock = None):
		"""Returns the child if it is being managed by this threadManager.

		label (str) - What the child is labeled as
			- If function: Will look for a child that has that function for 'myFunction'
		"""
		assert lock is not None
		assert unnamed is not None
		assert functions is not None
		assert catalogue is not None

		if (label is None):
			return

		with lock:
			if (isinstance(label, str)):
				return catalogue.get(label)

			if (label not in functions):
				return

			for container in (catalogue.values(), unnamed):
				for child in container:
					if (child.myFunction == label):
						return child

	def _add(self, child, catalogue = None, unnamed = None, functions = None, lock = None, *, canReplace = False):
		"""Adds a child to this threadManager.

		child (object) - What to add
		canReplace (bool) - Determines if 'child' can replace another one with the same label
		"""
		assert lock is not None
		assert unnamed is not None
		assert functions is not None
		assert catalogue is not None

		with lock:
			label = child.label
			if (label is None):
				unnamed.add(child)
				if (child.myFunction is not None):
					functions.add(child.myFunction)
				return

			if ((not canReplace) and (label in catalogue)):
				errorMessage = f"A {child.__class__.__name__} is already labeled as {label}"
				raise KeyError(errorMessage)

			catalogue[label] = child
			if (child.myFunction is not None):
				functions.add(child.myFunction)

	def _remove(self, child, catalogue = None, unnamed = None, functions = None, lock = None):
		"""Removes a child from this threadManager.

		child (object) - What to remove
		"""
		assert lock is not None
		assert unnamed is not None
		assert functions is not None
		assert catalogue is not None

		with lock:
			label = child.label
			if (label is None):
				unnamed.discard(child)
			else:
				catalogue.discard(label)

			functions.discard(child.myFunction)

	def passFunction(self, *args, thread = None, **kwargs):
		"""A function from a MyThread to be called in the main thread.
		If a thread object is not given it will pass from the current thread to the main thread.
		Modified code from Claudiu on: https://stackoverflow.com/questions/18989446/execute-python-function-in-main-thread-from-call-in-dummy-thread

		Example Input: passFunction(lorem)
		"""

		if (thread is not None):
			raise NotImplementedError()

		if (threading.current_thread() is threading.main_thread()):
			errorMessage = "Cannot pass from the main thread to the main thread"
			raise SyntaxError(errorMessage)

		self.callback_queue.put((args, kwargs))

	def recieveFunction(self, blocking = True, printEmpty = False, **kwargs):
		"""An non-critical function from the sub-thread will run in the main thread.
		Yields each answer, stops when the queue is empty.
		Modified code from Claudiu on: https://stackoverflow.com/questions/18989446/execute-python-function-in-main-thread-from-call-in-dummy-thread

		kwargs (**) - Given to MyUtilities.common.runMyFunction()

		blocking (bool) - If True: This is a non-critical function
		
		Example Input: recieveFunction()
		"""

		while True:
			try:
				functionArgs, functionKwargs = self.callback_queue.get(not blocking) #doesn't block
			
			except queue.Empty: #raised when queue is empty
				if (printEmpty):
					print("--- Thread Queue Empty ---")
				answer = None
				break

			yield MyUtilities.common.runMyFunction(*functionArgs, **functionKwargs, **kwargs)

	def backgroundRun(self, myFunction = None, *args, makeThread = True, name = None, daemon = True, **kwargs):
		"""Runs a function in the background in a way that it does not lock up the GUI.
		Meant for functions that take a long time to run.
		If 'makeThread' is true, the new thread object will be returned to the user.

		makeThread (bool) - Determines if this function runs on a different thread
			- If True: A new thread will be created to run the function
			- If False: The function will only run while the GUI is idle. Note: This can cause lag. Use this for operations that must be in the main thread.
		
		Example Input: backgroundRun(self.startupFunction)
		Example Input: backgroundRun(self.startupFunction, shown = True)
		"""

		if (not makeThread):
			raise NotImplementedError()
					
		thread = self.MyThread(self, name = name, *args, daemon = daemon, myFunction = myFunction, **kwargs)
		return thread

	def listen(self, myFunction = None, *args, autoStart = True, allowMultiple = False, **kwargs):
		"""Creates a listener for 'myFunction'.
		Returns a listener object.

		autoStart (bool) - Determines if the listener should start automatically
			- If False: The user needs to call the start() method themself

		allowMultiple (bool) - Determines if multiple listeners can use the same function
			- If True: Will create a new listener, regardless of function use 
			- If False: Will use the existing listener instead of creating a new one
			- If None: Will raise an error

		Example Input: listen(self.checkCapsLock, shown = True)
		"""

		def _getListener():
			nonlocal self, myFunction, allowMultiple, args, kwargs

			if (myFunction in self.listener_functions):
				if (allowMultiple is None):
					errorMessage = f"The function {myFunction} is already being used by another listener"
					raise KeyError(errorMessage)

				elif (not allowMultiple):
					return self.getListener(myFunction)
			return self.Listener(self, myFunction = myFunction, *args, **kwargs)

		##################################################

		listener = _getListener()
		assert listener is not None

		if (autoStart):
			listener.start()

		return listener

	def oneShot(self, myFunction = None, *args, oneShot = False, **kwargs):
		"""Configures a listener to be a reuseable one-shot.

		Example Input: oneShot(self.save)
		"""

		return self.listen(myFunction = myFunction, *args, oneShot = oneShot, **kwargs)

	def pause(self, state = True):
		"""Pauses all listeners.

		Example Input: pause()
		Example Input: pause(state = False)
		"""

		for container in (listener_catalogue.values(), listener_unnamed):
			for listener in container:
				listener.pause(state = state)

	class Listener():
		def __init__(self, parent, myFunction = None, *args, label = None, condition_start = None,
			delay = 1000, delayAfter = False, pauseOnDialog = False, notPauseOnDialog = None, 
			canTrigger = None, oneShot = None, bool_includeStop = True, bool_includePause = False, 
			
			resultFunction = None, resultFunctionArgs = None, resultFunctionKwargs = None, 
			alternativeFunction = None, alternativeFunctionArgs = None, alternativeFunctionKwargs = None, 
			preStartFunction = None, preStartFunctionArgs = None, preStartFunctionKwargs = None, 
			postStartFunction = None, postStartFunctionArgs = None, postStartFunctionKwargs = None, 
			postFunction = None, postFunctionArgs = None, postFunctionKwargs = None, 
			
			shown = False, makeThread = True, threadName = NULL, **kwargs):
			"""An object that loops a threaded function

			label (str) - What this listener should be catalogued as
			getThreadName (str) - What the thread should be catalogued as
				- If NULL: Will use 'label'

			myFunction (function) - A function that checks certain conditions
			resultFunction (function) - A function that runs if 'myFunction' return True
			preStartFunction (function) - A function that runs before a new thread starts
			postStartFunction (function) - A function that runs after a new thread starts
			postFunction (function) - A function that runs after a thread has finished
			alternativeFunction (function) - A function that runs instead of 'myFunction' if the one-shot is already made

			args (*) - Given to MyUtilities.common.runMyFunction()
			kwargs (**) - Given to MyUtilities.common.runMyFunction()

			bool_includeStop (bool) - Determines if 'stopFlag' should be considered in __bool__()
			bool_includePause (bool) - Determines if 'no_pauseFlag' should be considered in __bool__()
			condition_start (callable) - A callable function that determines if this listener is allowed to start a new thread or not
				~ Should take no args or kwargs, and should return True or False
				- If None: Will ignore this variable

			Example Input: Listener(self, myFunction = self.autoSave, canTrigger = True)
			Example Input: Listener(self, myFunction = self.checkCapsLock, shown = True)
			Example Input: Listener(self, myFunction = self.save, myFunctionArgs = "position", delay = 1500, oneShot = False)
			Example Input: Listener(self, myFunction = self.checkAutoLogout, resultFunction = self.logout, pauseOnDialog = True)
			Example Input: Listener(self, myFunction = self.listenScanner, pauseOnDialog = True, not_pauseOnDialog = "modifyBarcode")
			Example Input: Listener(self, myFunction = self.listenStatusText, delay = 0.01, errorFunction = self.listenStatusText_handleError)
			"""

			self.no_pauseFlag = threading.Event()
			self.no_triggerFlag = threading.Event()

			self.label = label
			self.shown = shown
			self.parent = parent
			self.threadName = threadName
			self.makeThread = makeThread
			self.condition_start = condition_start
			self.bool_includePause = bool_includePause
			self.bool_includeStop = bool_includeStop

			self.myFunction = myFunction
			self.functionArgs = args
			self.functionKwargs = kwargs

			self.delay = delay
			self.canTrigger = canTrigger
			self.oneShot = oneShot
			self.delayAfter = delayAfter

			self.pauseOnDialog = pauseOnDialog
			self.notPauseOnDialog = notPauseOnDialog

			self.resultFunction = resultFunction
			self.resultFunctionArgs = resultFunctionArgs
			self.resultFunctionKwargs = resultFunctionKwargs

			self.alternativeFunction = alternativeFunction
			self.alternativeFunctionArgs = alternativeFunctionArgs
			self.alternativeFunctionKwargs = alternativeFunctionKwargs

			self.preStartFunction = preStartFunction
			self.preStartFunctionArgs = preStartFunctionArgs
			self.preStartFunctionKwargs = preStartFunctionKwargs

			self.postFunction = postFunction
			self.postFunctionArgs = postFunctionArgs
			self.postFunctionKwargs = postFunctionKwargs

			self.parent._add(self, catalogue = self.parent.listener_catalogue, unnamed = self.parent.listener_unnamed, functions = self.parent.listener_functions, lock = self.parent.listener_lock)

		def __bool__(self):
			"""Checks if the listening routine is running in a thread."""

			with self.parent.listener_lock:
				if (not self.listening):
					return False

				if (self.bool_includeStop and self.stopFlag):
					return False

				if (self.bool_includePause and self.no_pauseFlag.is_set()):
					return False

				return True

		#Properties
		@MyUtilities.common.makeProperty(default = 0)
		class listening():
			"""Tracks how many threads are running _listenRoutine() for this listener."""

			def setter(self, value):
				with self.parent.listener_lock:
					self._listening = int(value)

		@MyUtilities.common.makeProperty(default = None)
		class oneShot():
			"""oneShot (bool) - Determines if the thread ends after running 'myFunction'
				- If None: The thread will loop back to the top of the thread routine
				- If True: The thread will end, and 'myFunction' will not be ran by future threads, until reset() is called
				- If False: The thread will end

			Modifying this also resets this listener
			"""

			def setter(self, value):
				with self.parent.listener_lock:
					self._oneShot = value

					self.reset()

		@MyUtilities.common.makeProperty(default = 100)
		class delay():
			"""How long to wait (in milliseconds) before running 'myFunction'.
				~ If 'canTrigger' is not None: How long to wait before listening for 'canTrigger'
			"""

			def setter(self, value):
				with self.parent.listener_lock:
					self._delay = float(MyUtilities.common.ensure_default(value, default = 0))

		@MyUtilities.common.makeProperty(default = False)
		class delayAfter():
			"""Determines when 'delay' is processed.
				- If True: Delays after 'myFunction' runs
				- If False: Delays before 'myFunction' runs
			"""

			def setter(self, value):
				with self.parent.listener_lock:
					self._delayAfter = bool(value)

		@MyUtilities.common.makeProperty(default = True)
		class canRun():
			"""Determines if 'myFunction' can run.
				- If True: Runs 'myFunction'
				- If False: Runs 'alternativeFunction'
			"""

			def setter(self, value):
				with self.parent.listener_lock:
					self._canRun = bool(value)

		@MyUtilities.common.makeProperty(default = False)
		class stopFlag():
			"""Determines if the listening routine should be stopped."""

			def setter(self, value):
				with self.parent.listener_lock:
					self.pause(state = False)
					self.trigger(state = False)
					self._stopFlag = bool(value)

		@MyUtilities.common.makeProperty(default = None)
		class canTrigger():
			"""Determines if trigger_listen() will cause 'myFunction' to run.
				- If True or False: Will wait for a signal from trigger_listen() before running 'myFunction'
				- If None: Will run 'myFunction' after 'delay' is over
			"""

			def setter(self, value):
				with self.parent.listener_lock:
					self._canTrigger = value

		@MyUtilities.common.makeProperty(default = None)
		class resultFunction():
			"""What function runs if 'myFunction' returns True."""

			def setter(self, value):
				with self.parent.listener_lock:
					self._resultFunction = value

		@MyUtilities.common.makeProperty(default = None)
		class resultFunctionArgs():
			"""The args to use for 'resultFunction."""

			def setter(self, value):
				with self.parent.listener_lock:
					self._resultFunctionArgs = value

		@MyUtilities.common.makeProperty(default = None)
		class resultFunctionKwargs():
			"""The kwargs to use for 'resultFunction."""

			def setter(self, value):
				with self.parent.listener_lock:
					self._resultFunctionKwargs = value

		@MyUtilities.common.makeProperty(default = False)
		class pauseOnDialog():
			"""Determines if the background function should wait if a dialog box is showing
				- If True: Will pause for any dialog window
				- If not bool: Will pause only if the dialog's label matches this
			"""

			def setter(self, value):
				with self.parent.listener_lock:
					if (not isinstance(value, bool)):
						raise NotImplementedError()

					if (value):
						self.parent.pauseOnDialog.add(self)
					else:
						self.parent.pauseOnDialog.discard(self)

			def getter(self):
				return self in self.parent.pauseOnDialog

		@MyUtilities.common.makeProperty(default = NULL)
		class pauseOnDialog_exclude():
			"""The label of a dialog window to not pause on (Overrides 'pauseOnDialog'). 
				- If list: Will not pause on all given dialog windows.
			"""

			def setter(self, value):
				with self.parent.listener_lock:
					self._pauseOnDialog_exclude = MyUtilities.common.ensure_container(value, useForNone = NULL)

			def getter(self):
				value = self._pauseOnDialog_exclude
				if (value is NULL):
					return ()
				return value

		#Listen Routine Functions
		def _checkClear(self):
			"""Tells other threads listening for 'myFunction' to stop."""

			if (self.listening > 0):
				# self.parent.log_debug("Listener Waiting", label = self.label, listening = self.listening, total = threading.active_count())

				while (self.listening > 0):
					self.stopFlag = True
					time.sleep(100 / 1000)

			self.stop(state = False)

		def _wait(self):
			"""Sleeps for the set delay."""

			if (self.delay is 0):
				return

			time.sleep(self.delay / 1000)

		def _waitEvent(self, event, timeout = None):
			"""Waits for the flag to be set to True."""

			if (event.is_set()):
				return

			if (not timeout):
				event.wait()
				return

			while True:
				event.wait(timeout = timeout)
				if (event.is_set()):
					break

		def _checkPause(self):
			"""Accounts for pausing the listening routine for 'myFunction'."""

			self._waitEvent(self.no_pauseFlag)

		def _checkTrigger(self, timeout = None):
			"""Accounts for a trigger assciated with 'myFunction'."""
			
			if (self.canTrigger is None):
				return

			self._waitEvent(self.no_triggerFlag)

			self.canTrigger = False

		def _runFunction(self):
			"""Runs the correct functions."""

			if (self.canRun):
				if (self.oneShot):
					self.reset(state = False)
				answer = MyUtilities.common.runMyFunction(self.myFunction, *self.functionArgs, **self.functionKwargs)
			else:
				answer = MyUtilities.common.runMyFunction(self.alternativeFunction, myFunctionArgs = self.alternativeFunctionArgs, myFunctionKwargs = self.alternativeFunctionKwargs, **dict(_yieldKwargs(self.functionKwargs)))
			if (answer):
				MyUtilities.common.runMyFunction(self.resultFunction, myFunctionArgs = self.resultFunctionArgs, myFunctionKwargs = self.resultFunctionKwargs, **dict(_yieldKwargs(self.functionKwargs)))

		def _listenRoutine(self):
			"""The listening routine for this listener."""

			# print("@_listenRoutine.1", self.oneShot, self.listening)
			self._checkClear()
			# print("@_listenRoutine.2", self.oneShot, self.listening)

			self.listening += 1
			try:
				self.parent.log_info("Listener Routine Start", label = self.label, delay = self.delay, canTrigger = self.canTrigger, total = threading.active_count())
				while True:
					if (self.stopFlag):
						break

					if (self._checkPause()):
						self.stop()
						break

					if (not self.delayAfter):
						self._wait()

					if (self._checkTrigger()):
						self.stop()
						break

					self._runFunction()

					if (self.delayAfter):
						self._wait()

					if (self.oneShot is not None):
						break

			finally:
				self.listening -= 1
				# self.parent.log_debug("Listener Routine Finished", label = self.label, total = threading.active_count())

		#User Functions
		def reset(self, state = True):
			"""Resets the one-shot for this listener.

			Example Input: reset()
			Example Input: reset(state = False)
			"""

			self.canRun = state

		def stop(self, state = True):
			"""Tells the listener to stop the listening routine.

			Example Input: stop()
			Example Input: stop(state = False)
			"""

			# self.parent.log_debug(f"Listener {('Not ', '')[state]}Stopping", label = self.label, total = threading.active_count())
			self.stopFlag = state

		def pause(self, state = True):
			"""Tells the listener to pause the listening routine.

			Example Input: pause()
			Example Input: pause(state = False)
			"""

			# self.parent.log_debug(f"Listener {('Not ', '')[state]}Pausing", label = self.label, total = threading.active_count())

			if (state):
				self.no_pauseFlag.clear()
			else:
				self.no_pauseFlag.set()

		def trigger(self, state = True):
			"""Tells the listener to trigger the listening routine.

			Example Input: trigger()
			Example Input: trigger(state = False)
			"""

			# self.parent.log_debug(f"Listener {('Not ', '')[state]}Triggering", label = self.label, total = threading.active_count())

			if (state):
				self.no_triggerFlag.clear()
			else:
				self.no_triggerFlag.set()

		def start(self, threadName = NULL):
			"""Starts the listen routine.

			Example Input: start()
			"""

			def stopFunction():
				nonlocal self

				self.stop()

			def _checkOneShot():
				"""Accounts for one-shot functions.
					- If False: A new thread can be started
					- If True: A new thread cannot be started
				"""
				nonlocal self

				if (self.oneShot is None):
					return False

				if (not self.listening):
					return False

				return True

			def getThreadName():
				nonlocal self, threadName

				if (threadName is not NULL):
					return threadName

				if (self.threadName is not NULL):
					return self.threadName


				return self.label

			######################

			# self.parent.log_debug(f"Listener Starting", label = self.label, total = threading.active_count())

			if (_checkOneShot()):
				return False

			if ((self.condition_start is not None) and (not self.condition_start())):
				return False

			self.parent.backgroundRun(self._listenRoutine, name = getThreadName(), shown = self.shown, makeThread = self.makeThread, stopFunction = stopFunction,
				preStartFunction = self.preStartFunction, preStartFunctionArgs = self.preStartFunctionArgs, preStartFunctionKwargs = self.preStartFunctionKwargs, 
				postFunction = self.postFunction, postFunctionArgs = self.postFunctionArgs, postFunctionKwargs = self.postFunctionKwargs)

	class MyThread(threading.Thread):
		"""Used to run functions in the background.
		More information on threads can be found at: https://docs.python.org/3.4/library/threading.html
		Use: https://wiki.wxpython.org/Non-Blocking%20Gui
		Use: http://effbot.org/zone/thread-synchronization.htm
		_________________________________________________________________________

		CREATE AND RUN A NEW THREAD
		#Create new threads
		thread1 = myThread(1, "Thread-1", 1)
		thread2 = myThread(2, "Thread-2", 2)

		#Start new threads
		thread1.start()
		thread2.start()
		_________________________________________________________________________

		RUNNING A FUNCTION ON A THREAD
		After the thread has been created and started, you can run functions on it like you do on the main thread.
		The following code shows how to run functions on the new thread:

		runFunction(longFunction, [1, 2], {label: "Lorem"}, self, False)
		_________________________________________________________________________

		If you exit the main thread, the other threads will still run.

		EXAMPLE CREATING A THREAD THAT EXITS WHEN THE MAIN THREAD EXITS
		If you want the created thread to exit when the main thread exits, make it a daemon thread.
			thread1 = myThread(1, "Thread-1", 1, daemon = True)

		You can also make it a daemon using the function:
			thread1.setDaemon(True)
		_________________________________________________________________________

		CLOSING A THREAD
		If any thread is open, the program will not end. To close a thread use return on the function that is running in the thread.
		The thread will then close itself automatically.
		"""

		def __init__(self, parent, name = None, *args, threadID = None, daemon = None, label = None, **kwargs):
			"""Setup the thread.

			name (str)     - The thread name. By default, a unique name is constructed of the form "Thread-N" where N is a small decimal number.
			daemon (bool)  - Sets whether the thread is daemonic. If None (the default), the daemonic property is inherited from the current thread.
			label (str) - A name for the thread
				- If name already exists: Will stop the existing thread and replace it with this one
			
			Example Input: MyThread(self)
			Example Input: MyThread(self, name = "Thread-1")
			Example Input: MyThread(self, daemon = True)
			"""

			#Initialize the thread
			threading.Thread.__init__(self, name = name, daemon = daemon)

			#Setup thread properties
			if (threadID is not None):
				self.threadID = threadID

			self.stopEvent = threading.Event() #Used to stop the thread

			#Initialize internal variables
			self.parent = parent
			self.label = label

			self.shown = None
			self.window = None

			self.functionArgs = ()
			self.functionKwargs = {}
			self.myFunction = None

			self.stopFunction = None
			self.stopFunctionArgs = None
			self.stopFunctionKwargs = None

			self._checkClear()
			self._catalogueThread()

			if (args or kwargs):
				self.runFunction(*args, **kwargs)

		def _checkClear(self, delay = 10):
			"""Waits for other threads to stop if there are too many running."""

			if (threading.active_count() <= self.parent.maxThreads):
				return

			# warnings.warn(f"Too many threads at {printCurrentTrace(printout = False)}", Warning, stacklevel = 2)
			while (threading.active_count() > self.parent.maxThreads):
				time.sleep(delay / 1000)

		def _catalogueThread(self):
			"""Marks this thread in the catalogue."""

			thread = self.parent.getThread(self.label)
			if (thread is not None):
				thread.join()

				# thread.stop()
				# try:
				# 	thread.join()
				# except RuntimeError as error:
				# 	pass

			self.parent._add(self, catalogue = self.parent.thread_catalogue, unnamed = self.parent.thread_unnamed, functions = self.parent.thread_functions, lock = self.parent.thread_lock, canReplace = True)

		def runFunction(self, myFunction = None, *args, window = None, shown = False,
			preStartFunction = None, preStartFunctionArgs = None, preStartFunctionKwargs = None, 
			postStartFunction = None, postStartFunctionArgs = None, postStartFunctionKwargs = None, 
			postFunction = None, postFunctionArgs = None, postFunctionKwargs = None, 
			stopFunction = None, stopFunctionArgs = None, stopFunctionKwargs = None, **kwargs):
			"""Sets the function to run in the thread object.

			myFunction (function) - What function will run in this thread
			kwargs (**) - Given to MyUtilities.common.runMyFunction
			
			window (wxFrame) - The window that called this function
				- If None: 'shown' is ignored

			shown (bool) - Determines what happens if 'window' is not shown yet
				- If True: It will wait for 'window' to be shown before running 'myFunction'
				- If False: 'myFunction' will run regardless of if 'window' is shown or not

			stopFunction (function) - An extra function used to stop the thread
			preStartFunction (function) - A function that runs before the thread starts
			preStartFunction (function) - A function that runs after the thread starts
			postFunction (function) - A function that runs after the thread has finished running 'myFunction'

			Example Input: runFunction(myFunction = longFunction, myFunctionKwargs = (1, 2), myFunctionKwargs = {"label": "Lorem"})
			"""

			self.shown = shown
			self.window = window

			self.functionArgs = args
			self.functionKwargs = kwargs
			self.myFunction = myFunction

			self.stopFunction = stopFunction
			self.stopFunctionArgs = stopFunctionArgs
			self.stopFunctionKwargs = stopFunctionKwargs

			self.postStartFunction = postStartFunction
			self.postStartFunctionArgs = postStartFunctionArgs
			self.postStartFunctionKwargs = postStartFunctionKwargs

			self.postFunction = postFunction
			self.postFunctionArgs = postFunctionArgs
			self.postFunctionKwargs = postFunctionKwargs

			if (preStartFunction is not None):
				MyUtilities.common.runMyFunction(myFunction = preStartFunction, myFunctionArgs = preStartFunctionArgs, myFunctionKwargs = preStartFunctionKwargs, **dict(_yieldKwargs(self.functionKwargs, selfObject = self.parent)))

			self.start()

		def _checkShown(self):
			"""Waits for the window to be shown, if necissary."""

			if ((not self.shown) or (self.window is None)):
				return

			while True:
				if (self.stopEvent.is_set()):
					return True

				if (self.window.showWindowCheck()):
					break

				time.sleep(0.01)

		def _threadRoutine(self):
			"""The process that this thread goes through when running."""

			if (self.myFunction is None):
				return

			if (self._checkShown()):
				return

			if (self.stopEvent.is_set()):
				return 

			MyUtilities.common.runMyFunction(myFunction = self.myFunction, *self.functionArgs, selfObject = self.parent, **self.functionKwargs)

		def run(self):
			"""Runs the thread and then closes it.

			To start the thread correctly, use runFunction()
			"""

			self.parent.log_info("Running Thread", name = self.name, total = threading.active_count())

			try:
				if (self.postStartFunction is not None):
					MyUtilities.common.runMyFunction(myFunction = self.postStartFunction, myFunctionArgs = self.postStartFunctionArgs, myFunctionKwargs = self.postStartFunctionKwargs, **dict(_yieldKwargs(self.functionKwargs, selfObject = self.parent)))

				self._threadRoutine()

				if (self.postFunction is not None):
					MyUtilities.common.runMyFunction(myFunction = self.postFunction, myFunctionArgs = self.postFunctionArgs, myFunctionKwargs = self.postFunctionKwargs, **dict(_yieldKwargs(self.functionKwargs, selfObject = self.parent)))

			finally:
				self.parent._remove(self, catalogue = self.parent.thread_catalogue, unnamed = self.parent.thread_unnamed, functions = self.parent.thread_functions, lock = self.parent.thread_lock)
			
			self.parent.log_info("Closing Thread", name = self.name, total = threading.active_count())

		def join(self, *args, **kwargs):
			self.stop()
			threading.Thread.join(self, *args, **kwargs)

		def stop(self):
			"""Stops the running thread."""

			self.stopEvent.set()

			if (self.stopFunction is not None):
				MyUtilities.common.runMyFunction(myFunction = self.stopFunction, myFunctionArgs = self.stopFunctionArgs, myFunctionKwargs = self.stopFunctionKwargs, **dict(_yieldKwargs(self.functionKwargs, selfObject = self.parent)))

rootManager = ThreadManager()

class CommonFunctions():
	def __init__(self, threadManager = None):
		global rootManager

		self.threadManager = threadManager or rootManager

	def backgroundRun(self, *args, selfObject = None, **kwargs):
		return self.threadManager.backgroundRun(*args, **kwargs, 
			selfObject = MyUtilities.common.ensure_default(selfObject, default = self))

	def onBackgroundRun(event, *args, **kwargs):
		"""A wxEvent version of backgroundRun()."""

		self.backgroundRun(*args, **kwargs)
		event.Skip()

	def pause(self, *args, selfObject = None, **kwargs):
		return self.threadManager.pause(*args, **kwargs, 
			selfObject = MyUtilities.common.ensure_default(selfObject, default = self))

	def listen(self, *args, selfObject = None, **kwargs):
		return self.threadManager.listen(*args, **kwargs, 
			selfObject = MyUtilities.common.ensure_default(selfObject, default = self))

	def oneShot(self, *args, selfObject = None, **kwargs):
		return self.threadManager.oneShot(*args, **kwargs, 
			selfObject = MyUtilities.common.ensure_default(selfObject, default = self))

if (__name__ == "__main__"):
	def test_backgroundRun():
		def test():
			for i in range(10):
				# print("@test", i)
				# jkhjhjkjhk
				time.sleep(250 / 1000)

		######################################

		rootManager.backgroundRun(test)

		while True:
			# print("@__main__")
			time.sleep(500 / 1000)

	def test_oneShot(runOnce = True, singleInstance = False):
		def test():
			for i in range(10):
				# print("@test", i)
				time.sleep(250 / 1000)

		if (singleInstance):
			listener = rootManager.listen(test, oneShot = runOnce, delay = 100 / 1000, autoStart = False)
			def trigger_oneShot():
				listener.start()
		else:
			def trigger_oneShot():
				rootManager.listen(test, oneShot = runOnce, delay = 100 / 1000)

		#############################################

		while True:
			trigger_oneShot()
			time.sleep(500 / 1000)

	##################################################

	# test_backgroundRun()
	test_oneShot(runOnce = False, singleInstance = False)

