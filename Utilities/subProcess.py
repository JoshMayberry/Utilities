import io
import sys
import time
import atexit
import subprocess

subProcessList = []

@atexit.register
def end_subprocesses():
	"""Modified code from: https://www.sharats.me/posts/the-ever-useful-and-neat-subprocess-module#auto-kill-on-death"""
	global subProcessList

	for process in subProcessList:
		process.kill()

class Parent():
	"""Functions meant to be used by the parent application.
	For now, each parent can only have one child.
	"""

	def __init__(self):
		
		self.child = None
		self.child_input = None
		self.child_output = None
		self.child_error = None

	def write(self, message = None, *, autoNewline = True):
		"""Sends a message to the child process.
		Use: https://pymotw.com/3/subprocess/#interacting-with-another-command

		message (str) - What text to send
			- If None: Will tell the child process to close

		autoNewline (bool) - Determiens if a new line is automatically added to the end of the message

		Example Input: write()
		Example Input: write("Lorem Ipsum")
		"""

		if (message is None):
			message = ""
		else:
			message = f"{message}"
		if (autoNewline and (not message.endswith("\n"))):
			message += "\n"

		self.child_input.write(message)		

	def read(self, all = False):
		"""Reads input from the child process
		Use: https://pymotw.com/3/subprocess/#interacting-with-another-command

		all (bool) - Determines how much information is read from the child
			- If True: Will read everything the child sends; closing the child process
			- If False: Will read one line from the child; keeping the child process open

		Example Input: read()
		Example Input: read(all = True)
		"""

		message = self.child_output.readline()
		return message.rstrip()

	def spawn(self, *args, **kwargs):
		"""Creates a child subprocess.
		Any args and kwargs passed in will be given to the cmd as args and kwargs for the process

		Example Input: spawn("py", "lorem.py", "ipsum", "dolor" = None)
		"""
		global subProcessList

		def yieldCommands():
			for item in args:
				yield f"{item}"

			for key, value in kwargs.items():
				if (value is None):
					yield f"-{key}"
				else:
					yield f"--{key} {value}"

		#################################################

		self.child = subprocess.Popen(tuple(yieldCommands()), stdin = subprocess.PIPE, stdout = subprocess.PIPE)
		self.child_input = io.TextIOWrapper(self.child.stdin, encoding = "utf-8", line_buffering = True)
		self.child_output = io.TextIOWrapper(self.child.stdout, encoding = "utf-8")

		subProcessList.append(self.child)

	def close(self):
		"""Ends the child process.

		Example Input: close()
		"""

		return self.child.communicate()[0].decode("utf-8")

	def flushInput(self):
		"""Flushes the child's input buffer.

		Example Input: flushInput()
		"""

		self.child_input.flush()

	def flushOutput(self):
		"""Flushes the child's output buffer.

		Example Input: flushOutput()
		"""

		self.child_output.flush()

	def flushError(self):
		"""Flushes the child's error buffer.

		Example Input: flushError()
		"""

		self.child_error.flush()

class Child():
	"""Functions meant to be used by the child application."""

	def __init__(self):
		sys.stderr.write("Child Starting\n")
		sys.stderr.flush()

	def write(self, message = None, *, autoNewline = True):
		"""Sends a message to the parent process.
		Use: https://pymotw.com/3/subprocess/#interacting-with-another-command

		message (str) - What text to send
		autoNewline (bool) - Determiens if a new line is automatically added to the end of the message

		Example Input: write("Lorem Ipsum")
		"""

		if (message is None):
			message = ""
		else:
			message = f"{message}"
		if (autoNewline and (not message.endswith("\n"))):
			message += "\n"

		sys.stdout.write(message)
		sys.stdout.flush()

	def read(self, *, closeOnEmpty = False):
		"""Reads input from the parent process
		Use: https://pymotw.com/3/subprocess/#interacting-with-another-command

		closeOnEmpty (bool) - Determines if this subprocess should close itself if an empty message is recieved

		Example Input: read()
		"""

		message = sys.stdin.readline()
		sys.stderr.flush()

		if (closeOnEmpty and (not message)):
			self.close()

		return message.rstrip()

	def close(self):
		"""Ends this child process

		Example Input: close()
		"""

		sys.stderr.write("Child Exiting")
		sys.stderr.flush()
		sys.exit()

if (__name__ == "__main__"):
	import argparse

	parser = argparse.ArgumentParser()
	parser.add_argument("-c", "--child", action = "store_true", help = "Marks this program as a child, and not the parent")
	args = parser.parse_args()

	if (args.child):
		handle = Child()
		while True:
			message = handle.read(closeOnEmpty = True)
			if (not message):
				break
			handle.write(message)

	else:
		handle = Parent()

		print("One line at a time:")
		child = handle.spawn("py", "H:/Python/Material_Tracker/test_subProcess_2.py", c = None)
		for i in range(5):
			handle.write(i)
			print(handle.read())
		print(handle.close())

		print("\nAll output at once:")
		child = handle.spawn("py", "H:/Python/Material_Tracker/test_subProcess_2.py", c = None)
		
		for i in range(5):
			handle.write(i)
		handle.flushInput()
		print(handle.close())
