import sys
import time
import atexit
import logging
import threading

class ThreadManager():
	def __init__(self, maxThreads=50):
		""" Manages a group of threads.

		maxThreads (int) - How many threads can run at once
			~ Crashes around 600
		"""

		self.maxThreads = maxThreads

		self.catalogue = {}
		self.lock = threading.RLock()

	def get(self, label):
		""" Returns the thread if it is being managed by this threadManager.

		label (str) - What the child is labeled as

		Example Input: get("autoSave")
		"""

		if (label is None):
			return

		with self.lock:
			return self.catalogue.get(label)

	def add(self, child, *, canReplace=False):
		""" Returns the thread if it is being managed by this threadManager.
		See: https://stackoverflow.com/questions/70733909/can-i-run-cleanup-code-in-daemon-threads-in-python/70737935#70737935

		child (MyThread) - What to add
		canReplace (bool) - Determines if 'child' can replace another one with the same label

		Example Input: add("autoSave")
		"""

		if (child is None):
			return

		with self.lock:
			label = child.label

			if (child.daemon):
				# Ensure threads are cleaned up on exit
				atexit.register(lambda: child.join())

			if ((not canReplace) and (label in self.catalogue)):
				errorMessage = f"A Thread is already labeled as '{label}'"
				raise KeyError(errorMessage)

			thread = self.catalogue.get(label)
			if (thread is not None):
				thread.stop()
				thread.join()

			self.catalogue[label] = child

	def remove(self, child):
		""" Removes a child from this threadManager.

		child (object) - What to remove

		Example remove(self)
		Example remove("autoSave")
		"""

		with self.lock:
			if (isinstance(child, str)):
				self.catalogue.pop(child, None)
				return

			self.catalogue.pop(child.label, None)

	def run(self, myFunction, *args, daemon=True, **kwargs):
		""" Runs a function in the background in a way that it does not lock up the GUI.
		Meant for functions that take a long time to run.
		If 'makeThread' is true, the new thread object will be returned to the user.

		Example Input: run(self.startupFunction)
		"""
		
		return self.MyThread(self, myFunction, *args, daemon=daemon, **kwargs)

	def listen(self, myFunction, *args, listenFunction=True, **kwargs):
		return self.MyThread(self, myFunction, *args, listenFunction=listenFunction, **kwargs)

	def oneShot(self, myFunction, *args, listenFunction=True, alternateFunction=True, **kwargs):
		return self.MyThread(self, myFunction, *args, listenFunction=listenFunction, alternateFunction=alternateFunction, **kwargs)

	class MyThread(threading.Thread):
		""" Used to run functions in the background.

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

		def __init__(self, parent, myFunction, label=None, *args, daemon=None, name=None, autoStart=True,
			delay_checkClear=10, delay_listen=1000,
			myFunctionArgs=None, myFunctionKwargs=None,
			preStartFunction=None, preStartFunctionArgs=None, preStartFunctionKwargs=None, 
			postStartFunction=None, postStartFunctionArgs=None, postStartFunctionKwargs=None, 
			preFunction=None, preFunctionArgs=None, preFunctionKwargs=None, 
			postFunction=None, postFunctionArgs=None, postFunctionKwargs=None, 
			stopFunction=None, stopFunctionArgs=None, stopFunctionKwargs=None,
			listenFunction=None, listenFunctionArgs=None, listenFunctionKwargs=None,
			alternateFunction=None, alternateFunctionArgs=None, alternateFunctionKwargs=None, **kwargs):
			""" Setup the thread.

			name (str)     - The thread name. By default, a unique name is constructed of the form "Thread-N" where N is a small decimal number.
			daemon (bool)  - Sets whether the thread is daemonic. If None (the default), the daemonic property is inherited from the current thread.
			label (str) - A name for the ThreadManager
				~ If name already exists: Will stop the existing thread and replace it with this one
			
			myFunction (function) - The main function to run on the thread
			preStartFunction (function) - A function that runs before the thread starts
			postStartFunction (function) - A function that runs after the thread starts
			preFunction (function) - A function that runs before the thread runs *myFunction*
			postFunction (function) - A function that runs after the thread has finished running *myFunction*
			stopFunction (function) - An extra function used to stop the thread

			listenFunction (function) - A function to run for checking if *myFunction* should run again
				~ Must return True before *myFunction* can run the first time
				~ If given, will keep the thread alive even after *myFunction* runs
			alternateFunction (function) - A function to run instead of *myFunction* if it has run already (unless *reset* is called)
				~ If not given, the thread will not have a 'One Shot' behavior
				~ Can be true to make it be a 'One Shot' without providing a function

			Example Input: MyThread(self, myFunction)
			Example Input: MyThread(self, myFunction, name="Thread-1")
			Example Input: MyThread(self, myFunction, daemon=True)
			"""

			# Initialize the thread
			threading.Thread.__init__(self, name=name, daemon=daemon)

			# Setup thread properties
			self.event_stop = threading.Event() # Used to stop the thread
			self.event_noPause = threading.Event() # Used to pause the thread
			self.event_triggered = threading.Event() # Used to give 'One Shot' behavior to the thread

			# Initialize internal variables
			self.parent = parent
			self.label = label or name

			self.delay_listen = delay_listen
			self.delay_checkClear = delay_checkClear

			self.myFunction = myFunction
			self.myFunctionArgs = myFunctionArgs or ()
			self.myFunctionKwargs = myFunctionKwargs or {}

			self.postFunction = postFunction
			self.postFunctionArgs = postFunctionArgs or ()
			self.postFunctionKwargs = postFunctionKwargs or {}

			self.preFunction = preFunction
			self.preFunctionArgs = preFunctionArgs or ()
			self.preFunctionKwargs = preFunctionKwargs or {}

			self.preStartFunction = preStartFunction
			self.preStartFunctionArgs = preStartFunctionArgs or ()
			self.preStartFunctionKwargs = preStartFunctionKwargs or {}

			self.postStartFunction = postStartFunction
			self.postStartFunctionArgs = postStartFunctionArgs or ()
			self.postStartFunctionKwargs = postStartFunctionKwargs or {}

			self.stopFunction = stopFunction
			self.stopFunctionArgs = stopFunctionArgs or ()
			self.stopFunctionKwargs = stopFunctionKwargs or {}

			self.listenFunction = listenFunction
			self.listenFunctionArgs = listenFunctionArgs or ()
			self.listenFunctionKwargs = listenFunctionKwargs or {}

			self.alternateFunction = alternateFunction
			self.alternateFunctionArgs = alternateFunctionArgs or ()
			self.alternateFunctionKwargs = alternateFunctionKwargs or {}

			self._checkClear()
			
			self.parent.add(self, canReplace=True)

			if (autoStart):
				self.start()

		def start(self, *args, **kwargs):
			try:
				if (self.preStartFunction):
					self.preStartFunction(*self.preStartFunctionArgs, **self.preStartFunctionKwargs)
			except Exception as error:
				self.parent.remove(self)
				raise error

			threading.Thread.start(self, *args, **kwargs)

		def _checkClear(self):
			""" Waits for other threads to stop if there are too many running."""

			if (threading.active_count() <= self.parent.maxThreads):
				return

			# warnings.warn(f"Too many threads at {printCurrentTrace(printout = False)}", Warning, stacklevel = 2)
			while (threading.active_count() > self.parent.maxThreads):
				time.sleep(self.delay_checkClear / 1000)

		def _triggerFunction(self):
			if (self.preFunction):
				self.preFunction(*self.preFunctionArgs, **self.preFunctionKwargs)
				if (self.event_stop.is_set()):
					return

			self.myFunction(*self.myFunctionArgs, **self.myFunctionKwargs)
			self.event_triggered.set()
			if (self.event_stop.is_set()):
				return

			if (self.postFunction):
				self.postFunction(*self.postFunctionArgs, **self.postFunctionKwargs)

		def _checkPause(self, timeout=None):
			if (not self.event_noPause.is_set()):
				return

			if (not timeout):
				self.event_noPause.wait()
				return

			while True:
				self.event_noPause.wait(timeout=timeout)
				if (self.event_noPause.is_set()):
					break

		def run(self):
			""" Runs the thread and then closes it.
			If *listenFunction* was given, will keep the. thread alive until it is explicitly stopped

			To start the thread correctly, use start()
			"""

			logging.info(f"Running Thread '{self.name}'; total: {threading.active_count()}")

			is_oneshot = isinstance(self.alternateFunction, bool)
			is_listener = isinstance(self.listenFunction, bool)

			try:
				if (self.event_stop.is_set()):
					return

				if (self.postStartFunction):
					self.postStartFunction(*self.postStartFunctionArgs, **self.postStartFunctionKwargs)
					if (self.event_stop.is_set()):
						return

				# Account for no listener
				if (self.listenFunction is None):
					return self._triggerFunction()

				while True:
					time.sleep(self.delay_listen / 1000)
					
					if (self.event_stop.is_set()):
						return

					self._checkPause()

					answer = True if is_listener else self.listenFunction(*self.listenFunctionArgs, **self.listenFunctionKwargs)
					if (not answer):
						if (self.event_stop.is_set()):
							return
						continue

					# Account for One Shot
					if (self.alternateFunction and self.event_triggered.is_set()):
						if (not is_oneshot):
							self.alternateFunction(*self.alternateFunctionArgs, **self.alternateFunctionKwargs)
							if (self.event_stop.is_set()):
								return
						continue

					self._triggerFunction()

					if (self.event_stop.is_set()):
						return

			except Exception as error:
				raise error

			finally:
				self.parent.remove(self)
				logging.info(f"Closing Thread '{self.name}'; total: {threading.active_count()}")

		def stop(self):
			""" Marks the thread as needing to stop."""

			self.event_stop.set()

			if (self.stopFunction):
				self.stopFunction(*self.stopFunctionArgs, **self.stopFunctionKwargs)

		def join(self, *args, **kwargs):
			self.stop()
			threading.Thread.join(self, *args, **kwargs)

		def pause(self, state=True):
			if (state):
				self.event_noPause.clear()
			else:
				self.event_noPause.set()

		def reset(self):
			self.event_triggered.clear()


rootManager = ThreadManager()

if (__name__ == "__main__"):
	def test_run():
		def test():
			for i in range(10):
				print("@test", i)
				time.sleep(250 / 1000)

		def postFunction():
			nonlocal stopLoop
			stopLoop = True

		######################################

		rootManager.run(test, postFunction=postFunction)

		stopLoop = False
		while (not stopLoop):
			print("@__main__")
			time.sleep(500 / 1000)

	def test_trigger():
		def test():
			for i in range(10):
				print("@test", i)
				time.sleep(250 / 1000)

		def postFunction():
			nonlocal stopLoop
			stopLoop = True

		def listenFunction():
			print("@listenFunction")
			return canFire

		######################################

		rootManager.run(test, listenFunction=listenFunction, postFunction=postFunction)

		canFire = False
		stopLoop = False

		print("@__main__.1")
		time.sleep(3)
		canFire = True

		while (not stopLoop):
			print("@__main__.2")
			time.sleep(500 / 1000)

	def test_listen():
		def test():
			for i in range(10):
				print("@test", i)
				time.sleep(250 / 1000)

		def postFunction():
			nonlocal count
			count += 1

		def listenFunction():
			print("@listenFunction")
			return canFire

		######################################

		rootManager.run(test, listenFunction=listenFunction, postFunction=postFunction)

		count = 0
		while (count < 3):
			print("@__main__")
			canFire = False
			time.sleep(1)
			canFire = True
			time.sleep(1)

	##################################################

	logging.basicConfig(level=logging.INFO)
	# test_run()
	# test_trigger()
	test_listen()
