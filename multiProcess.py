import time
import atexit
import multiprocessing

if (__name__ == "__main__"):
	import common
else:
	import Utilities.common as common

processList = set()

# @atexit.register
# def end_processes():
# 	"""Modified code from: https://www.sharats.me/posts/the-ever-useful-and-neat-subprocess-module#auto-kill-on-death"""
# 	global processList

# 	for process in processList:
# 		process.kill()

class Parent(common.EnsureFunctions):
	"""Functions meant to be used by the parent application.
	For now, each parent can only have one child.

	Use: https://docs.python.org/3/library/multiprocessing.html
	Use: https://www.blog.pythonlibrary.org/2016/08/02/python-201-a-multiprocessing-tutorial/
	"""

	def __init__(self, queue = None, pipe = None, event = None):
		"""

		Example Input: Parent()
		Example Input: Parent(pipe = True)
		Example Input: Parent(pipe = myPipe)
		Example Input: Parent(event = 3)
		"""

		def create(value, function, *args, expected = 1, returnForNone = None, **kwargs):
			def getValue():
				if (value is None):
					return returnForNone

				if (isinstance(value, bool)):
					if (value):
						return function(*args, **kwargs)

				elif (isinstance(value, int)):
					return tuple(function(*args, **kwargs) for i in range(value))

				return returnForNone

			########################################################


			if (expected is 1):
				return getValue()

			answer = tuple(getValue() for i in range(expected))
			try:
				return tuple(zip(*answer))
			except TypeError:
				return answer

		###############################

		self.child = None
		self.queue = create(queue, multiprocessing.Queue)
		self.event = create(event, multiprocessing.Event)
		self.myEnd, self.childEnd = create(pipe, multiprocessing.Pipe, expected = 2)
		
	def spawn(self, *args, queue = None, pipe = None, event = None, **kwargs):
		"""Creates a child process.
		Any args and kwargs passed in will be given to the child process as args and kwargs

		Example Input: spawn("py", "lorem.py", "ipsum", "dolor" = None)
		"""

		self.child = Child(*args, 
			queue = queue or self.queue, 
			pipe = pipe or self.childEnd, 
			event = event or self.event, 
			**kwargs)

		return self.child

	def send(self, item):
		"""Sends an item down the pipe.

		Example Input: send(1)
		"""

		self.myEnd.put(item)

	def get(self):
		"""Gets an item from the pipe.

		Example Input: get()
		"""

		return self.myEnd.recv()

	def closeQueue(self):
		"""Closes the queue"""

		self.queue.close()
		self.queue.join_thread()

class Child(multiprocessing.Process, common.EnsureFunctions):
	"""Functions meant to be used by the child application."""

	def __init__(self, myFunction, myFunctionArgs = None, myFunctionKwargs = None, 
		*sharedMemory, queue = None, pipe = None, event = None, lock = None, daemon = None):
		super().__init__(target = myFunction, args = (self, *self.ensure_container(myFunctionArgs)), kwargs = myFunctionKwargs or {}, daemon = daemon)

		self.lock = lock
		self.pipe = pipe
		self.queue = queue
		self.event = event
		self.sharedMemory = sharedMemory

	def __enter__(self):
		self.start()

		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if (traceback is not None):
			return False

		self.join()

	def start(self, *args, **kwargs):
		global processList

		processList.add(self)
		super().start(*args, **kwargs)

	def join(self, *args, **kwargs):
		global processList

		processList.discard(self)
		super().join(*args, **kwargs)

	def append(self, item):
		"""Adds an item to the queue.

		Example Input: append(1)
		"""

		if (self.queue is None):
			errorMessage = f"No queue was given during the creation of {self.__repr__()}"
			raise ValueError(errorMessage)

		self.queue.put(item)

	def send(self, item):
		"""Sends an item down the pipe.

		Example Input: send(1)
		"""

		if (self.pipe is None):
			errorMessage = f"No pipe was given during the creation of {self.__repr__()}"
			raise ValueError(errorMessage)

		self.pipe.send(item)

	def get(self):
		"""Gets an item from the pipe.

		Example Input: get()
		"""

		if (self.pipe is None):
			errorMessage = f"No pipe was given during the creation of {self.__repr__()}"
			raise ValueError(errorMessage)

		return self.pipe.recv()

def test_counter(self, n = 5, *, delay = 100):
	for i in range(n):
		self.send(f"@test_counter.{i}")
		time.sleep(delay / 1000)

if __name__ == '__main__':
	parent = Parent(pipe = True)
	with parent.spawn(test_counter) as child:
		for i in range(5):
			print(f"@main{i}", parent.get())

	print()
	with parent.spawn(test_counter, myFunctionArgs = (3,), myFunctionKwargs = {"delay": 500}) as child:
		for i in range(3):
			print(f"@main{i}", parent.get())
