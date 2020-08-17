import os
import sys
import ast
import types

import io
import re
import stat
import queue
import shutil
import typing

import itertools
import contextlib
import collections

import inspect
import traceback

class Singleton():
	"""Used to get values correctly.

	Example Use: FLAG = MyUtilities.common.Singleton("FLAG")
	"""

	def __init__(self, label = "Singleton", *, state = None, private = False):
		"""
		label (str) - What this singleton is called
		private (bool) - Determines if only this module may use this singleton (Not Implemented)

		state (bool) - Determiens what happens if this singleton is evaluated by bool()
			- If True: Will always return True
			- If False: Will always return False
			- If None: No special action is taken
		"""

		self.private = private

		if (not self.private):
			self.label = label
		else:
			self.label = f"{label} ({__name__} only)"

		if (state is not None):
			if (state):
				self.__bool__ = lambda self: True
			else:
				self.__bool__ = lambda self: False

	def __repr__(self):
		return f"{self.label}()"

NULL = Singleton("NULL", state = False)
NULL_private = Singleton("NULL", state = False, private = True)

class ELEMENT():
	"""Used to make a class pass ensure_container() as an element instead of a container."""

class CATALOGUE():
	"""Used to make a class pass ensure_dict() as a dict instead of a dict key or value."""

#Inheritance Flagging
def makeTracker(myFunction, *args, skipFirst = False, extraClass = None, **kwargs):
	"""Returns a metaclass that is able to run a function when inherited.

	myFunction (function) - What function to run when the tracker is inherited
		~ Must take the inherited class as the first (non-self) parameter
		- If str: Will call a class function from the new class that matches that variable

	args (*) - Given to myFunction
	kwargs (*) - Given to myFunction

	skipFirst (bool) - Determines if the first class to inherit the tracker will not trigger the function
		~ The first class to inherit the tracker is the one who assigns the metaclass

	extraClass (type) - Extra classes that need to be combined with the meta class to avoid the following error:
		TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases
		~ See: https://stackoverflow.com/questions/11276037/resolving-metaclass-conflicts/41266737#41266737

	___________________________________________________________

	Example Use:
		def sit(cls):
			print("Lorem Ipsum", cls)

		class Lorem(metaclass = makeTracker(sit, skipFirst = True)):
			pass

		class Ipsum():
			class Dolor(Lorem):
				pass

	Alternative Syntax:
		class Lorem(metaclass = makeTracker("sit")):
			def sit(cls):
				print("Lorem Ipsum", cls)
	___________________________________________________________

	Example Use:
		def sit(cls):
			print("Lorem Ipsum", cls)

		class A(type): pass
		class B(metaclass = A): pass
		class C(B, metaclass = makeTracker(sit, extraClass = B)): pass
		class D(C): pass
	___________________________________________________________

	Example Input: makeTracker(lorem)
	Example Input: makeTracker(lorem, skipFirst = True)
	Example Input: makeTracker(lorem, extraClass = Ipsum)
	"""

	class Tracker(type):
		def __new__(cls, name, bases, catalogue):
			nonlocal myFunction, args, kwargs, skipFirst

			newClass = type.__new__(cls, name, bases, catalogue)

			if (skipFirst):
				skipFirst = False
				return newClass

			if (isinstance(myFunction, str)):
				myFunction = getattr(newClass, myFunction)

			myFunction(newClass, *args, **kwargs)
			return newClass

	if (extraClass is not None):
		class Tracker_Patch(Tracker, *getMetaclass(extraClass, forceTuple = True)): 
			pass
		return Tracker_Patch
	return Tracker

def metaclass_resolver(*classes):
	"""Helps solve the following error:
		TypeError: metaclass conflict: the metaclass of a derived class must be a (non-strict) subclass of the metaclasses of all its bases
	Modified code from: https://stackoverflow.com/questions/11276037/resolving-metaclass-conflicts/41266737#41266737
	___________________________________________________________

	Example Use:
		class M_A(type): pass
		class M_B(type): pass
		class A(metaclass = M_A): pass
		class B(metaclass = M_B): pass
		class C(metaclass_resolver(A, B)): pass
	___________________________________________________________
	
	Example Input: metaclass_resolver(Lorem, Ipsum)
	"""

	metaclass = tuple(set(type(cls) for cls in classes))

	if (len(metaclass) is 1):
		metaclass = metaclass[0]
	else:
		metaclass = type("_".join(cls.__name__ for cls in metaclass), metaclass, {})
	return metaclass("_".join(cls.__name__ for cls in classes), classes, {})

def getMetaclass(cls, includeNested = True, forceTuple = False):
	"""Returns the metaclass of 'cls'

	includeNested (bool) - Determines if nested bases are checked for their meta classes as well
	___________________________________________________________

	Example Use:
		class M_A(type): pass
		class M_B(type): pass
		class A(metaclass = M_A): pass
		class B(metaclass = M_B): pass
		class M_AM_B(M_A, M_B): pass
		class C(A, B, metaclass = M_AM_B): pass

		print(getMetaclass(A))
		print(getMetaclass(C))
	___________________________________________________________

	Example Input: getMetaclass(Lorem)
	"""

	exclude = (type, object)

	def yieldAnswer():
		nonlocal cls, includeNested

		metaclass = type(cls)

		if (includeNested):
			for item in metaclass.__bases__:
				if (item in exclude):
					continue

				yield item

				for answer in getMetaclass(item, forceTuple = True):
					yield answer

		if (metaclass not in exclude):
			yield metaclass

	####################

	if (cls in exclude):
		if (forceTuple):
			return ()
		return

	return oneOrMany(yieldAnswer, forceTuple = forceTuple)

def oneOrMany(answer, *, forceTuple = False, forceContainer = True, 
	consumeFunction = True, isDict = False, returnForNone = None):
	"""Returns the the first element of the list if it is one item long.
	Otherwise, returns the list.

	Example Input: oneOrMany(answer)
	Example Input: oneOrMany(yieldAnswer)
	Example Input: oneOrMany(yieldAnswer())
	Example Input: oneOrMany(answer, forceTuple = True)
	Example Input: oneOrMany(myList, forceContainer = False)
	Example Input: oneOrMany(myClass, consumeFunction = False)
	Example Input: oneOrMany(catalogue, isDict = True, forceContainer = False)
	"""

	if (consumeFunction and (inspect.ismethod(answer) or inspect.isfunction(answer))):
		answer = answer()

	if (forceContainer and (not isDict)):
		answer = ensure_container(answer)

	if (forceTuple or (len(answer) is not 1)):
		return answer
	elif (isDict):
		return next(iter(answer.values()), returnForNone)
	else:
		return next(iter(answer), returnForNone)

#Iterators
class CommonIterator(object):
	"""Used by handle objects to iterate over their nested objects."""

	def __init__(self, data, filterNone = False):
		if (not isinstance(data, (list, dict))):
			data = data[:]

		self.data = data

		if (isinstance(self.data, dict)):
			self.order = list(self.data.keys())

			if (filterNone):
				self.order = [key for key in self.data.keys() if key is not None]
			else:
				self.order = [key if key is not None else "" for key in self.data.keys()]
			self.order = sorted(self.order, key = lambda item: f"{item}")
			self.order = [key if key != "" else None for key in self.order]

	def __iter__(self):
		return self

	def __next__(self):
		if (not isinstance(self.data, dict)):
			if not self.data:
				raise StopIteration

			return self.data.pop(0)
		else:
			if not self.order:
				raise StopIteration

			key = self.order.pop()
			return self.data[key]

class CustomIterator():
	"""Iterates over items in an external list."""
	def __init__(self, parent, variableName = None, loop = False, printError = False):
		"""
		parent (object) - The object that will be using this iterator; typically self
		variableName (str) - The name of a variable in *parent* that will be used as the list to iterate through
			- If None: The user plans to override _getItem()
		loop (bool) - If the iterator should never stop, and link the two ends of the list
		printError (bool) - If errors should be printed

		Example Input: CustomIterator(self, "printBarcode_containerList")
		"""

		self.index = -1
		self.loop = loop
		self.parent = parent
		self.printError = printError

		if (variableName is not None):
			if (not isinstance(variableName, str)):
				errorMessage = f"'variableName' must be a str, not a {type(variableName)}"
				raise ValueError(errorMessage)
			if (not hasattr(self.parent, variableName)):
				errorMessage = f"{self.parent.__repr__()} must have a variable named {variableName}"
				raise ValueError(errorMessage)
			if (not isinstance(getattr(self.parent, variableName), (list, tuple))):
				errorMessage = f"{variableName} in {self.parent.__repr__()} must be a list or tuple, not a {type(getattr(self.parent, variableName))}"
				raise ValueError(errorMessage)
			self._variableName = variableName

	def __iter__(self):
		return self

	def __next__(self):
		"""Returns the next item in the list.

		Example Use: next(self.printBarcode_containerIterator)
		"""

		try:
			self.index += 1
			return self._getItem()
		except IndexError:
			if (self.loop):
				return self.start()
			else:
				raise StopIteration

	def stepForward(self):
		self.index += 1

	def stepBackward(self):
		if (self.index is -1):
			self.index = len(self) - 1
	
		self.index -= 1

	def previous(self):
		"""Returns the previous item in the list.

		Example input: previous()
		"""

		try:
			if (self.index is -1):
				self.index = len(self) - 1
		
			self.index -= 1
			return self._getItem()
		except IndexError:
			if (self.loop):
				return self.end()
			else:
				raise StopIteration

	def start(self):
		"""Returns the first item in the list.

		Example Input: start()
		"""

		try:
			self.index = 0
			return self._getItem()
		except IndexError:
			raise StopIteration

	def end(self):
		"""Returns the last item in the list.

		Example Input: end()
		"""

		try:
			self.index = len(self.parent.printBarcode_containerList) - 1
			return self._getItem()
		except IndexError:
			raise StopIteration

	def next(self, n = None, terminator = None):
		"""Returns the next item(s) in the list.

		n (int) - How many pairs the results should be grouped in
			- If None: Will run as an alias for next(self)

		Example input: next()
		Example input: next(2)
		"""

		if (n is None):
			try:
				return next(self)
			except StopIteration:
				return terminator

		answer = []
		for i in range(n):
			try:
				answer.append(next(self))
			except StopIteration:
				answer.append(terminator)

		return answer

	def asGenerator(self, n = None, terminator = None, resetIndex = True):
		"""Returns a generator for iterating through this iterator.

		n (int) - How many pairs the results should be grouped in.

		Example Input: asGenerator()
		Example Input: asGenerator(2)

		Example Use: for topHandle, bottomHandle in self.printBarcode_containerIterator.asGenerator(2): pass
		"""

		if (resetIndex):
			self.index = -1
		while True:
			answer = self.next(n = n, terminator = terminator)

			if (((n is not None) and all(item == terminator for item in answer)) or (answer is None)):
				break
			yield answer

	def _getItem(self):
		"""Returns the item for the current index.

		Example Input: _getItem()
		Example Input: _getItem(0)
		"""

		try:
			return getattr(self.parent, self._variableName)[self.index]
		except IndexError as error:
			if (self.printError):
				traceback.print_exception(type(error), error, error.__traceback__)
			raise error

#Queues
class PriorityQueue(queue.PriorityQueue):
	"""A priority queue that keeps item order.
	Modified code from jcollado on https://stackoverflow.com/questions/9289614/how-to-put-items-into-priority-queues
	"""
	
	def __init__(self, defaultPriority = 100):
		super().__init__()
		self.counter = 0
		self.defaultPriority = defaultPriority

	def put(self, item, priority = None):
		if (priority is None):
			priority = self.defaultPriority
		super().put((priority, self.counter, item))
		self.counter += 1

	def get(self, *args, **kwargs):
		return super().get(*args, **kwargs)[2]


#Custom Types
class _set(set):
	def append(self, *args, **kwargs):
		return self.add(*args, **kwargs)

class _dict(dict):
	"""A dictionary that can use circular references.

	EXAMPLE USE:
		x = _dict({
			1: "Lorem", 
			"1": "Ipsum", 
			"ips": "${1}", 
			"lor": "${1:int}", 
			2: "${lor} Dolor ${1}", 
			3: "Sit ${lor} Dolor ${1} Amet", 
		})
		print(x[3])
	___________________________________________________________

	EXAMPLE USE:
		y = _dict({"lorem": "ipsum"}, caseSensitive = False)
		print(y["Lorem"])
	___________________________________________________________

	EXAMPLE USE:
		z = _dict({"1": "lorem"}, typeSensitive = False)
		print(z[1])
	"""

	typeCatalogue = {
		"int": int, int: int, 
		"str": str, str: str, 
		"None": ast.literal_eval, "eval": ast.literal_eval, "?": ast.literal_eval, 
	}

	def __init__(self, iterable = None, *, interpreter = NULL, caseSensitive = True, typeSensitive = True, **kwargs):
		super().__init__()

		self.caseSensitive = caseSensitive
		self.typeSensitive = typeSensitive

		self.setInterpreter(interpreter)
		self.setSensitivity(caseSensitive = caseSensitive, typeSensitive = typeSensitive)

		self.update(kwargs)
		self.update(iterable)

	def __setitem__(self, key, value):
		"""Overridden to account for key formatting."""
		super().__setitem__(self.formatKey(key), value)

	def set(self, key, value = None):
		"""Overridden to account for key formatting."""

		return super().set(self.formatKey(key), value)

	def __getitem__(self, key):
		"""Overridden to account for key formatting."""
		
		return self.formatValue(super().__getitem__(self.formatKey(key)))

	def get(self, key, default = None):
		"""Overridden to account for key formatting."""

		return self.formatValue(super().get(self.formatKey(key), default))

	def _yieldInterpreted(self, text):
		"""Yields pieces of 'text' that are put through the interpreter.

		Example Input: _yieldInterpreted("Lorem ${ipsum} Dolor ${2:int} Amet")
		"""

		for pre, key, _type, post in re.findall(self.interpreter, text):
			if (not key):
				yield f"{pre}{post}"
				continue

			if (not _type):
				yield f"{pre}{self[key]}{post}"
				continue

			yield f"{pre}{self[self.typeCatalogue.get(_type, str)(key)]}{post}"

	def setInterpreter(self, interpreter = NULL):
		"""Sets the interpreter for the text.
		By default, dictionary keys can be flag by a dollar sign and surrounding them with brackets.
		A colon can be used to declare a callable in 'typeCatalogue' that can return the correct key to use.

		interpreter (compiled regex) - A compiled regex to use for searching for circular references
			~ Should yield four item tuples for _yieldInterpreted()
			- If None: Will not allow circular references
			- If NULL: Will use the default interpreter

		Example Input: setInterpreter()
		"""

		if (interpreter is not NULL):
			self.interpreter = interpreter
			return

		subkey = "[^\:\}}]"
		key = f"({subkey}+)(?:\:({subkey}+))?"
		inside_brackets =  f"(?:\$\{{{key}\}})"
		outside_brackets = "(?:([^(?:\$\{)]+))"
		self.interpreter = re.compile(f"{outside_brackets}*{inside_brackets}*{outside_brackets}*")

	def formatValue(self, value = None):
		"""Formats the value using the interpreter.

		Example Input: formatValue()
		"""

		if (self.interpreter is None):
			return value
		if (not isinstance(value, str)):
			return value
		if ("${" not in value):
			return value

		return ''.join(self._yieldInterpreted(value))

	def setSensitivity(self, caseSensitive = NULL, typeSensitive = NULL):
		"""Changes if keys are sensitive to case or type.
		Note: This cannot be changed after items are added.

		caseSensitive (bool) - Determines if string case matters for strings
			- If True: "a" != "A"
			- If False: "a" == "A"

		typeSensitive (bool) - Determines if variable type matters
			- If True: "1" != 1
			- If False: "1" == 1

		Example Input: setSensitivity()
		"""

		if (self):
			errorMessage = "Sensitivity must be set before items are added"
			raise SyntaxError(errorMessage)

		if (caseSensitive is not NULL):
			self.caseSensitive = caseSensitive

		if (typeSensitive is not NULL):
			self.typeSensitive = typeSensitive

		if (self.caseSensitive):
			if (self.typeSensitive):
				self.formatKey = lambda key: key
			else:
				self.formatKey = lambda key: f"{key}"
		else:
			if (self.typeSensitive):
				self.formatKey = lambda key: key.casefold() if (isinstance(key, str)) else key
			else:
				self.formatKey = lambda key: f"{key}".casefold()

	def pop(self, key, default = None):
		"""Overridden to account for key formatting."""

		return super().pop(self.formatKey(key), default)

	def setdefault(self, key, default = None):
		"""Overridden to account for key formatting."""

		return super().setdefault(self.formatKey(key), default)

	def update(self, other = None):
		"""Overridden to account for key formatting."""

		def generator():
			nonlocal other

			if (isinstance(other, dict)):
				for key, value in other.items():
					yield self.formatKey(key), value
				return

			raise NotImplementedError(type(other))

		###################

		if (other is None):
			return

		super().update(generator())

#Ensure Functions
def ensure_set(item, convertNone = False):
	"""Makes sure the given item is a set.

	Example Input: ensure_set(exclude)
	Example Input: ensure_set(exclude, convertNone = True)
	"""

	if (item is not None):
		if (isinstance(item, (str, int, float))):
			return {item}
		elif (not isinstance(item, set)):
			return set(item)
		return item

	if (convertNone):
		return set()

def ensure_list(item, convertNone = False):
	"""Makes sure the given item is a list.

	Example Input: ensure_list(exclude)
	Example Input: ensure_list(exclude, convertNone = True)
	"""

	if (item is not None):
		if (isinstance(item, str) or (not isinstance(item, typing.Iterable))):
			return [item]
		elif (not isinstance(item, list)):
			return list(item)
		return item

	if (convertNone):
		return []

def ensure_lastElement(container, default = None):
	"""Returns the last element in 'container' if there is one; otherwise returns 'default'.
	Assumes that 'container' is indexable.

	Example Input: ensure_lastElement(myList)
	Example Input: ensure_lastElement(myList, default = int)
	"""

	if (not container):
		return default

	return container[-1]

def is_container(item, *, elementTypes = None, elementCriteria = None):
	"""Returns if the given item is a container or not.
	Generators are not considered containers.

	elementTypes (list) - Extra types that are ok to be elements
	elementCriteria (tuple) - Allows for formatted tuples to pass as elements if they match the criteria
		~ (required length (int), required type (type))
		- If None: Will count all tuples as containers

	Example Input: is_container(valueList)
	Example Input: is_container(valueList, evaluateGenerator = False)

	Example Input: is_container(handle, elementTypes = (Base,))
	Example Input: is_container((255, 255, 0), elementCriteria = (3, int))
	Example Input: is_container((255, 255, 0), elementCriteria = ((3, int), (4, int)))
	Example Input: is_container(("lorem", 1), elementCriteria = (2, (str, int)))
	"""

	def checkItem(_item, _type):
		if (_type is None):
			return True

		return isinstance(_item, _type)

	def checkType(requiredLength, requiredType):
		nonlocal item

		if (len(item) != requiredLength):
			return False

		if (requiredType is None):
			return True

		container = ensure_container(requiredType)
		return all(checkItem(*_item) for _item in itertools.zip_longest(item, container, fillvalue = ensure_lastElement(container)))

	###########################

	if (isinstance(item, (str, ELEMENT, typing.Mapping, typing.MutableMapping))):
		return False

	if (not isinstance(item, typing.Iterable)):
		return False

	if (isinstance(item, tuple(ensure_container(elementTypes, convertNone = True)))):
		return False

	if ((elementCriteria is not None) and isinstance(item, (tuple, list))):
		if (not item):
			return True

		if (not isinstance(elementCriteria[0], tuple)): ## TO DO ## This line is clunky; find another way
			elementCriteria = (elementCriteria,)

		return not any(checkType(*required) for required in elementCriteria)

	if (isinstance(item, (list, tuple, set))):
		return True

def ensure_container(item, *args, useForNone = None, convertNone = True, is_container_answer = NULL_private, 
	returnForNone = None, evaluateGenerator = True, consumeFunction = True, **kwargs):
	"""Makes sure the given item is a container.

	args (*) - What should be appended to the end of the container 'item'

	returnForNone (any) - What should be returned if 'item' is None
		- If function: will return whatever the function returns

	Example Input: ensure_container(valueList)
	Example Input: ensure_container(valueList, convertNone = False)
	Example Input: ensure_container(valueList, evaluateGenerator = False)
	Example Input: ensure_container((x for x in range(3)))

	Example Input: ensure_container(handle, elementTypes = (Base,))
	Example Input: ensure_container((255, 255, 0), elementCriteria = (3, int))
	Example Input: ensure_container((255, 255, 0), elementCriteria = ((3, int), (4, int)))
	"""

	if (args):
		return (*ensure_container(item, useForNone = useForNone, convertNone = convertNone, is_container_answer = is_container_answer, 
			returnForNone = returnForNone, evaluateGenerator = evaluateGenerator, consumeFunction = consumeFunction, **kwargs), *args)

	if (item is useForNone):
		if (convertNone):
			return ()
		if (consumeFunction and (inspect.ismethod(returnForNone) or inspect.isfunction(returnForNone))):
			return returnForNone()
		return (returnForNone,)

	if (is_container_answer is NULL_private):
		state = is_container(item, **kwargs)
	else:
		state = is_container_answer

	if (state):
		return item
	if (state is not None):
		return (item,)

	if (evaluateGenerator and isinstance(item, typing.Iterable)):
		return ensure_container(tuple(item), useForNone = useForNone, convertNone = convertNone, returnForNone = returnForNone, evaluateGenerator = evaluateGenerator, **kwargs)
	return (item,)

def ensure_dict(catalogue, default = None, *, useForNone = None, useAsKey = True, convertContainer = True, convertNone = True):
	"""Makes sure the given catalogue is a dictionary.

	useAsKey (bool) - Determines how 'catalogue' is used if it is not a dictionary
		- If True: {catalogue: default}
		- If False: {default: catalogue}
		- If None: {catalogue: catalogue}

	Example Input: ensure_dict(relation, attribute)
	"""

	if (catalogue is useForNone):
		if (convertNone):
			return {}
	elif (isinstance(catalogue, (dict, CATALOGUE))):
		return catalogue
	elif (convertContainer and isinstance(catalogue, Container)):
		return catalogue._dataCatalogue

	if (useAsKey is None):
		return {catalogue: catalogue}
	if (useAsKey):
		return {catalogue: default}
	return {default: catalogue}

def ensure_default(value, default = None, *args, defaultFlag = None, condition = None, 
	consumeFunction = True, consumeList = True, forceTuple = False):
	"""Returns 'default' if 'value' is 'defaultFlag'; otherwise returns 'value'.

	value (any) - What to check against 'defaultFlag'
	default (any) - What to use instead of 'value' if 'value' is 'defaultFlag'
	args (*) - If given, are combined with 'default' to make a 'default' a list

	consumeList (bool) - Determines what happens if 'default' is a list
		- If True: Returns the first non-'defaultFlag' element from 'default'
		- If False: Returns the entire list from 'default'

	condition (callable) - An extra condition that must be met
		- If None: Does nothing

	Example Input: ensure_default(autoPrint, False)
	Example Input: ensure_default(autoPrint, defaultFlag = NULL)

	Example Input: ensure_default(autoPrint, lambda: self.checkPermission("autoPrint"))
	Example Input: ensure_default(myFunction, self.checkPermission, consumeFunction = False)

	Example Input: ensure_default(autoPrint, self.autoPrint, False)
	Example Input: ensure_default(autoPrint, [self.autoPrint, False])
	Example Input: ensure_default(myList, [1, 2, 3], consumeList = False)
	"""

	def checkFlag(_value):
		nonlocal defaultFlag, condition

		if (_value is defaultFlag):
			return True

		if ((condition is not None) and condition(_value)):
			return True

	def yieldDefault():
		nonlocal default

		for item in (*ensure_container(default, convertNone = False), *args):
			if (consumeFunction and (inspect.ismethod(item) or inspect.isfunction(item))):
				yield item()
			else:
				yield item

	######################################

	if (not checkFlag(value)):
		return value

	if (consumeList):
		for item in yieldDefault():
			if (not checkFlag(item)):
				return item
		return item

	return oneOrMany(yieldDefault, forceTuple = forceTuple)

def ensure_string(value, *, returnForNone = "", extend = None):
	"""Returns 'value' as a string.

	returnForNone (str) - What to return if 'value' is None
	extend (str) - What to replace all instances of '{}' in 'value' with

	Example Input: ensure_string(value)
	Example Input: ensure_string(value, returnForNone = "Empty")
	"""

	if (value is None):
		return returnForNone

	if (extend is None):
		return f"{value}"

	return f"{value}".format(extend)

def ensure_filePath(filePath, *, ending = None, raiseError = True, default = None, checkExists = True):
	if (filePath is None):
		if (callable(default)):
			return default()
		return default

	if (ending is not None):
		for _ending in ensure_container(ending):
			if (filePath.endswith(_ending)):
				break
		else:
			filePath += _ending

	if (checkExists and (not os.path.exists(filePath))):
		if (raiseError):
			raise FileNotFoundError(filePath)
		if (callable(default)):
			return default()
		return default
	return filePath
	
def ensure_functionInput(myFunction = None, *args, myFunctionArgs = None, myFunctionKwargs = None, 
	includeSelf = False, selfObject = None, self = None, includeEvent = False, event = None, **kwargs):
	"""Makes sure that 'myFunctionArgs' and 'myFunctionKwargs' are able to be passed into 'myFunction' correctly.
	Yields the following for each function to run: (myFunction, myFunctionArgs, myFunctionKwargs).

	myFunction (function) - What function to run
		- If list: Will run each function in the order given

	myFunctionArgs (list) - What args to use for 'myFunction', along with *args
		~ If 'myFunction' is a list, this must be a list of equal length

	myFunctionKwargs (list) - What kwargs to use for 'myFunction', along with **kwargs
		~ If 'myFunction' is a list, this must be a list of equal length

	args (*) - What args to give each function should run (before 'myFunctionArgs')
	kwargs (**) - What default kwargs to give each function should run (applied before 'myFunctionKwargs')

	includeSelf (bool) - Determines if 'self' is tacked on to the start of 'args' (before 'event')
	self (object) - Used to emulate class functions, or to pass in 'self' as a parent variable

	includeEvent (bool) - Determines if 'event' is tacked on to the start of 'args'
	event (wxEvent) - An event variable to start the function with

	Example Input: ensure_functionInput(lorem, myFunctionArgs = 1)
	Example Input: ensure_functionInput(lorem, myFunctionArgs = (1, 2))

	Example Input: 

	Example Input: ensure_functionInput([lorem], myFunctionArgs = (1,))
	Example Input: ensure_functionInput([lorem], myFunctionArgs = [None])
	Example Input: ensure_functionInput([lorem], myFunctionArgs = [[None]])

	Example Input: ensure_functionInput([lorem, ipsum], myFunctionArgs = (1, 2))
	Example Input: ensure_functionInput([lorem, ipsum], myFunctionArgs = ((1, 2, 3), None), myFunctionKwargs = (None, {"dolor": 1})))

	Equivalent Inputs:
		ensure_functionInput(lorem, myFunctionArgs = (1, 2), myFunctionKwargs = {"x": 3})
		ensure_functionInput(lorem, 1, 2, x = 3)

	Equivalent Inputs:
		ensure_functionInput(lorem, myFunctionArgs = [1, 2, 3])
		ensure_functionInput([lorem], myFunctionArgs = [[1, 2, 3]])

	Equivalent Inputs:
		ensure_functionInput(lorem, myFunctionArgs = None)
		ensure_functionInput([lorem], myFunctionArgs = [None])

	Equivalent Inputs:
		ensure_functionInput(lorem, myFunctionArgs = [None])
		ensure_functionInput([lorem], myFunctionArgs = [[None]])

	"""

	if (self is not None):
		assert selfObject is None
		selfObject = self

	def yieldArgs(n):
		def yieldCombined(argsList):
			nonlocal includeSelf, selfObject, includeEvent, event, args

			if (includeSelf):
				yield selfObject

			if (includeEvent):
				yield event

			for item in args:
				yield item

			for item in ensure_container(argsList):
				yield item

		def yieldFormatted():
			nonlocal myFunctionArgs, n, is_container_answer

			if (not is_container_answer):
				if (myFunctionArgs is None):
					yield ()
				else:
					yield myFunctionArgs
				return

			argsList = ensure_container(myFunctionArgs)

			if (not argsList):
				for i in range(n):
					yield ()
				return

			if (len(argsList) != n):
				errorMessage = f"A list of length {n} is required for myFunctionArgs, but it has a length of {len(argsList)}"
				raise SyntaxError(errorMessage)

			for item in argsList:
				yield item

		#########################################

		for item in yieldFormatted():
			yield tuple(yieldCombined(item))

	def yieldKwargs(n):
		def applyFormat(item):
			if (item is None):
				return {}

			if (isinstance(item, dict)):
				return item

			if (is_container(item)):
				n = len(item)
				if (n is 1):
					return applyFormat(item[0])

				if (n is 0):
					return {}

				raise NotImplementedError(type(item), n)

			raise NotImplementedError(type(item))

		def yieldFormatted():
			nonlocal myFunctionKwargs, n

			if (not myFunctionKwargs):
				for item in range(n):
					yield {}
				return

			if (n is 1):
				yield applyFormat(myFunctionKwargs)
				return

			kwargsList = ensure_container(myFunctionKwargs)
			if (len(kwargsList) != n):
				errorMessage = f"A list of length {n} is required for myFunctionKwargs, but it has a length of {len(kwargsList)}"
				raise SyntaxError(errorMessage)

			for item in kwargsList:
				yield applyFormat(item)

		#########################################

		for catalogue in yieldFormatted():
			yield {**kwargs, **catalogue}

	####################################

	is_container_answer = is_container(myFunction)
	functionList = ensure_container(myFunction, is_container_answer = is_container_answer)
	if (not functionList):
		return

	n = len(functionList)
	for item in zip(functionList, yieldArgs(n), yieldKwargs(n)):
		yield item

class EnsureFunctions():
	@classmethod
	def ensure_set(cls, *args, **kwargs):
		return ensure_set(*args, **kwargs)

	@classmethod
	def ensure_list(cls, *args, **kwargs):
		return ensure_list(*args, **kwargs)

	@classmethod
	def ensure_container(cls, *args, **kwargs):
		return ensure_container(*args, **kwargs)

	@classmethod
	def ensure_dict(cls, *args, **kwargs):
		return ensure_dict(*args, **kwargs)

	@classmethod
	def ensure_default(cls, *args, **kwargs):
		return ensure_default(*args, **kwargs)

	@classmethod
	def ensure_string(cls, *args, **kwargs):
		return ensure_string(*args, **kwargs)

	@classmethod
	def ensure_filePath(cls, *args, **kwargs):
		return ensure_filePath(*args, **kwargs)

	@classmethod
	def ensure_functionInput(cls, *args, selfObject = None, **kwargs):
		return ensure_functionInput(*args, selfObject = ensure_default(selfObject, default = cls), **kwargs)

	@classmethod
	def is_container(cls, *args, **kwargs):
		return is_container(*args, **kwargs)

	@classmethod
	def oneOrMany(cls, *args, **kwargs):
		return oneOrMany(*args, **kwargs)

#Etc
def nestedUpdate(target, catalogue, *, preserveNone = True):
	"""Updates a nested dictionary.
	Modified code from Alex Martelli on https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth/3233356#3233356
	
	Example Input: nestedUpdate(self.contents, self.contents_override)
	"""

	if (target is None):
		if (preserveNone):
			errorMessage = "Catalogue mismatch"
			raise KeyError(errorMessage)
		target = {}

	for key, value in catalogue.items():
		if (isinstance(value, dict)):
			target[key] = nestedUpdate(target.get(key, {}), value, preserveNone = preserveNone)
		else:
			if ((key in target) and (isinstance(target[key], dict))):
				target[key]["value"] = value
			else:
				target[key] = value
	return target

def _StringToValue(value, converter, extraArgs = []):
	"""
	Convert the given value to a string, using the given converter
	"""
	if (extraArgs):
		try:
			return converter(value, *extraArgs)
		except:
			pass
	try:
		return converter(value)
	except TypeError:
		pass

	if (converter and isinstance(value, (datetime.datetime, datetime.date, datetime.time))):
		return value.strftime(converter)

	if (converter and isinstance(value, wx.DateTime)):
		return value.Format(converter)

	# By default, None is changed to an empty string.
	if ((not converter) and (not value)):
		return ""

	fmt = converter or "%s"
	try:
		return fmt % value
	except UnicodeError:
		return unicode(fmt) % value

def _SetValueUsingMunger(source, value, munger, extraArgs = []):
	"""
	Look for ways to update source with value using munger.
	"""
	# If there isn't a munger, we can't do anything
	if (munger is None):
		return

	# Is munger a function?
	if (extraArgs):
		try:
			munger(source, value, *extraArgs)
			return
		except:
			pass
	try:
		munger(source, value)
		return
	except:
		pass

	# Is munger a dictionary key?
	try:
		if (munger in source):
			source[munger] = value
			return
	except:
		pass

	# Is munger the name of a method?
	try:
		attr = getattr(source, munger)
		attr(value)
		return
	except:
		pass

	# Is munger is the name of an attribute or property on source?
	try:
		if (hasattr(source, munger)):
			setattr(source, munger, value)
	except:
		pass

def _Munge(munger, source = None, extraArgs = [], returnMunger_onFail = False):
	"""Wrest some value from the given source using the munger.
	Modified code from: ObjectListView

	source (object) - What to try getting the munger from
		- If None: Will only use munger

	'munger' can be:

	1) a callable.
	   This method will return the result of executing 'munger' with 'source' as its parameter.

	2) the name of an attribute of the source.
	   If that attribute is callable, this method will return the result of executing that attribute.
	   Otherwise, this method will return the value of that attribute.

	3) an index (string or integer) onto the source.
	   This allows dictionary-like objects and list-like objects to be used directly.

	Example Input: _Munge(function, extraArgs = [myWidget])
	Example Input: _Munge(variable, source = handle, extraArgs = [myWidget])
	Example Input: _Munge(variable, source = handle, extraArgs = [myWidget], returnMunger_onFail = True)
	Example Input: _Munge(function, source = handle, returnMunger_onFail = True)
	"""

	if (munger is None):
		return None

	if (source is None):
		if (callable(munger)):
			if (extraArgs):
				try:
					return munger(*extraArgs)
				except TypeError as error:
					pass

			#Allow the error to propigate if one occurs
			return munger()

	else:
		# Try attribute access
		try:
			attr = getattr(source, munger, None)
			if (attr is not None):
				try:
					return attr()
				except TypeError:
					return attr
		except TypeError:
			# Happens when munger is not a string
			pass

		# Use the callable directly, if possible.
		# Try/except can mask errors from the user's callable function
		if (callable(munger)):
			if (extraArgs):
				try:
					return munger(source, *extraArgs)
				except TypeError:
					pass

			#Allow the error to propigate if one occurs
			return munger(source)

		# Try dictionary-like indexing
		try:
			return source[munger]
		except:
			pass

	if (returnMunger_onFail):
		return munger
	else:
		return None

def getClass(function):
	"""Returns the class that the given function belongs to.
	Modified code from Yoel on: https://stackoverflow.com/questions/3589311/get-defining-class-of-unbound-method-object-in-python-3/25959545#25959545

	Example Input: getClass(myFunction)
	"""

	if (inspect.ismethod(function)):
		for cls in inspect.getmro(function.__self__.__class__):
			if (cls.__dict__.get(function.__name__) is function):
				return cls
		function = function.__func__
	
	if (inspect.isfunction(function)):
		cls = getattr(inspect.getmodule(function), function.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0])
		if (isinstance(cls, type)):
			return cls

	return getattr(function, '__objclass__', None)

def yieldSubClass(cls, *, getNested = True, include = None, exclude = None, 
	yieldBase = False, filterByModule = True, onlyName = False):
	"""Returns a list of all subclasses (other instances that inheirt 'cls') belonging to the given class.

	getNested (bool) - Determines if the subclasses of the subclasses will also be returned

	include (list) - A list of modules that the subclasses must be from
		- If None: Does nothing

	exclude (list) - A list of modules that the subclasses cannot be from
		- If None: Does nothing

	yieldBase (bool) - Determines if the base classes (classes inherited by 'cls') should be returned instead of subclasses

	filterByModule (bool) - Determiens if 'include' and 'exclude' refer to imported module names or class names

	onlyName (bool) - Determines if only the class names are compared or if the whole namespace is compared

	Example Input: yieldSubClass(myClass)
	"""

	def isOk(_cls):
		nonlocal include, exclude, onlyName

		if (filterByModule):
			if (onlyName):
				compare = _cls.__module__.split(".")[-1]
			else:
				compare = _cls.__module__
		else:
			if (onlyName):
				compare = _cls.__name__
			else:
				compare = f"{_cls.__module__}.{_cls.__name__}"

		if (compare in exclude):
			return False

		if ((not include) or (compare in include)):
			return True

	def yieldSubSubClass(_cls):
		nonlocal getNested

		if (yieldBase):
			classList = _cls.__bases__
		else:
			classList = _cls.__subclasses__()

		for sub in classList:
			if (isOk(sub)):
				yield sub

			if (not getNested):
				continue

			for subSub in yieldSubSubClass(sub):
				if (isOk(subSub)):
					yield subSub

	#########################

	include = ensure_container(include)
	exclude = ensure_container(exclude)

	for item in yieldSubSubClass(cls):
		yield item

def yieldBaseClass(*args, **kwargs):
	"""Returns a list of all base classes (classes inherited by 'cls') belonging to the given class.

	Example Input: yieldBaseClass(myClass)
	"""

	for item in yieldSubClass(*args, yieldBase = True, **kwargs):
		yield item

def removeDir(filePath):
	"""Removes the given directory if it exists."""

	def onerror(function, path, exc_info):
		"""An Error handler for shutil.rmtree.
		Modified code from Justin Peel on https://stackoverflow.com/questions/2656322/shutil-rmtree-fails-on-windows-with-access-is-denied
		"""

		if (not os.access(path, os.W_OK)):
			os.chmod(path, stat.S_IWUSR)
			function(path)
		else:
			raise

	shutil.rmtree(filePath, ignore_errors = False, onerror = onerror)

def runMyFunction(myFunction = None, *args, includeError = True, forceTuple = False, 
	errorFunction = None, errorFunctionArgs = None, errorFunctionKwargs = None, **kwargs):
	"""Runs a function.

	args (*) - Given to ensure_functionInput()
	kwargs (**) - Given to ensure_functionInput()

	errorFunction (function) - A function to run if an error occurs while running 'myFunction'
	errorFunctionArgs (list) - args for 'errorFunction'
	errorFunctionKwargs (list) - kwargs for 'errorFunction'

	Example Input: runMyFunction(lorem)
	"""

	def handleError(error):
		nonlocal errorFunction, errorFunctionArgs, errorFunctionKwargs

		if (errorFunction is None):
			raise error

		if (includeError):
			_args = (error,)
		else:
			_args = ()

		for answer in runMyFunction(errorFunction, *_args, myFunctionArgs = errorFunctionArgs, myFunctionKwargs = errorFunctionKwargs, forceTuple = True):
			yield answer

	def getAnswer(function, functionArgs, functionKwargs):
		nonlocal forceTuple

		try:
			return function(*functionArgs, **functionKwargs)

		except Exception as error:
			return oneOrMany(handleError(error), forceTuple = forceTuple)

	#########################################################

	#Skip empty functions
	if (myFunction is None):
		return

	return oneOrMany((getAnswer(*item) for item in ensure_functionInput(myFunction, *args, **kwargs)), forceTuple = forceTuple)
		
class CommonFunctions():
	@classmethod
	def nestedUpdate(cls, *args, **kwargs):
		return nestedUpdate(*args, **kwargs)
		
	# @classmethod
	# def setDocstring(cls, *args, **kwargs):
	# 	return setDocstring(*args, **kwargs)

	@classmethod
	def _StringToValue(cls, *args, **kwargs):
		return _StringToValue(*args, **kwargs)

	@classmethod
	def _SetValueUsingMunger(cls, *args, **kwargs):
		return _SetValueUsingMunger(*args, **kwargs)

	@classmethod
	def _Munge(cls, *args, **kwargs):
		return _Munge(*args, **kwargs)

	@classmethod
	def yieldSubClass(cls, *args, **kwargs):
		return yieldSubClass(cls, *args, **kwargs)

	@classmethod
	def yieldBaseClass(cls, *args, **kwargs):
		return yieldBaseClass(cls, *args, **kwargs)

	@classmethod
	def removeDir(cls, *args, **kwargs):
		return removeDir(*args, **kwargs)

	def runMyFunction(self, *args, selfObject = None, **kwargs):
		return runMyFunction(*args, selfObject = ensure_default(selfObject, default = self), **kwargs)
	
#Decorators
## TO DO ## - https://hynek.me/articles/decorators/

def setDocstring(docstring):
	"""Sets the docstring of a function.
	Special thanks to estani for how to change a docstring on https://stackoverflow.com/questions/4056983/how-do-i-programmatically-set-the-docstring/13603271#13603271
	
	docstring (str) - What the docstring for this function should be
		- If function: Will copy the docstring belonging to that function

	Example Use: 
		@setDocstring("New Docstring")
		def test(): pass
	_________________________________________

	Example Use: 
		@setDocstring(myFunction)
		def test(): pass
	"""

	if (callable(docstring)):
		docstring = docstring.__doc__

	def decorator(function):
		function.__doc__ = docstring
		return function
	return decorator

def makeProperty(default = NULL_private, variableName = "_{}", *, publisher = None, subscription = None, 
	forceType = None, convertType = False, setterVariable = "value"):
	"""Turns the decorated class into a property.
	Uses the docstring of the class for the docstring of the property.
	Uses the functions getter, setter, and remover to create the property.

	default (any) - What to use if the getter is called before the setter is used
		- If NULL_private: Will not attempt to create a default

	variableName (str) - What naming convention to use for the getter variable
		~ The class name will be placed in all instances of "{}"

	publisher (module) - The pubsub module to use for 'subscription'
		- If None: 'subscription' will not be used
	subscription (str) - A pubsub subscription label to subscribe the setter to
		~ Note: You will have to pass in the self parameter as a different kwarg for this to work
		- If None: Will use the property name as the subscription label

	forceType (bool) - Determines if the type annotation for 'value' in setter() should be enforced
		- If None: Does nothing
		- If True: All values must be the given type
		- If False: All values must be the given type or None

	convertType (bool) - Determines what happens if 'forceType' fails
		- If True: Will try casting 'value' as the type that it is annotated as in setter()
		- If False: Raises an error
		- If callable: Will pass 'value' in as an arg to 'convertType'

	setterVariable (str) - What the variable is called to check the annotation for in setter()
	_________________________________________
	
	Example Use:
		class Test():
			@makeProperty()
			class lorem():
				'''Lorem ipsum dolor sit amet.'''

				def getter(self):
					return self.ipsum

				def setter(self, value):
					self.ipsum = value

				def remover(self):
					del self.ipsum

	_________________________________________

	Example Input: makeProperty(publisher = pubsub.pub)
	Example Input: makeProperty(publisher = pubsub.pub, subscription = "dolor")

	Example Input: makeProperty(default = None)
	Example Input: makeProperty(default = None, variableName = "ipsum")
	Example Input: makeProperty(default = None, variableName = "{}_ipsum")

	Example Input: makeProperty(forceType = True)
	Example Input: makeProperty(forceType = False)
	Example Input: makeProperty(forceType = True, convertType = True)
	Example Input: makeProperty(forceType = True, convertType = formatter)
	"""

	def decorator(cls):
		def make_getter():
			nonlocal cls, default

			_getter = getattr(cls, "getter", None)
			if (default is NULL_private):
				return _getter

			_variable = variableName.format(cls.__name__)
			if (_getter is None):
				_getter = lambda self: getattr(self, _variable)
			
			def getter(self):
				if (not hasattr(self, _variable)):
					setter(self, default)

				return _getter(self)
			return getter

		def make_setter():
			nonlocal cls, default, forceType

			_setter = getattr(cls, "setter", None)
			if ((forceType is None) or (_setter is None) or (setterVariable not in _setter.__annotations__)):
				if ((default is NULL_private) or (_setter is not None)):
					return _setter
				return lambda self, value: setattr(self, _variable, value)

			_type = _setter.__annotations__[setterVariable]

			if (forceType):
				checkType = lambda value: isinstance(value, _type)
			else:
				checkType = lambda value: (value is None) or isinstance(value, _type)

			if (not convertType):
				def converter(value):
					errorMessage = f"The given value should be a {_type}, not a {type(value)}"
					raise TypeError(errorMessage)
			elif (callable(convertType)):
				converter = convertType
			else:
				converter = _type

			def setter(self, value):
				nonlocal checkType, converter, _setter

				if (not checkType(value)):
					value = converter(value)
				return _setter(self, value)
			return setter

		#############################################


		setter = make_setter()
		getter = make_getter()

		if (publisher is not None):
			publisher.subscribe(setter, subscription or cls.__name__)

		return property(
			fset = setter, 
			fget = getter, 
			fdel = getattr(cls, "remover", None), 
			doc = cls.__doc__ or None)

	return decorator

def lazyProperty(variable = None, *, default = NULL, defaultVariable = None, readOnly = False,
	catalogueVariable_all = "_lazyProperties_all", catalogueVariable_used = "_lazyProperties_used"):
	"""Crates a property using the decorated function as the getter.
	The docstring of the decorated function becomes the docstring for the property.

	variable (str) - The name of the variable in 'self' to use for the property
		- If None: uses the name of 'function' prefixed by an underscore

	default (any) - What value to initialize 'variable' in 'self' as if it does not yet exist
		- If NULL: Checks for a kwarg in 'function' that matches 'defaultVariable'

	defaultVariable (str) - The name of a kwarg in 'function' to use for 'default'
		- If None: Uses "default"
		Note: this must be a kwarg, not an arg with a default; this means it must appear after *

	readOnly (bool) - Determines if the value can be set once initialized or not
		- If False: The decorated function is the setter
		- If True: The decorated function is used once to initialize the property

	catalogueVariable_all (str) - The name of a variable for a set to add each lazy property name to 
		- If None: Will not catalogue variable names

	catalogueVariable_used (str) - The name of a variable for a set to add each created lazy property name to 
		- If None: Will not catalogue variable names
	___________________________________________________________

	Example Use:
		class Test():
			@lazyProperty()
			def x(self, value, *, default = 0):
				'''Lorem ipsum'''
				return f"The value is {value}"

		test = Test()
		print(test.x)
		test.x = 1
		print(test.x)

	Equivalent Use:
		@lazyProperty(defaultVariable = "someKwarg")
		def x(self, value, *, someKwarg = 0):

	Equivalent Use:
		@lazyProperty(default = 0)
		def x(self, value):
	___________________________________________________________
	"""

	def decorator(function):
		if (catalogueVariable_all is not None):
			module = inspect.getmodule(function)
			if (not hasattr(module, catalogueVariable_all)):
				setattr(module, catalogueVariable_all, collections.defaultdict(set))
			getattr(module, catalogueVariable_all)[function.__qualname__.split('.<locals>', 1)[0].rsplit('.', 1)[0]].add(function.__name__)

		_variable = variable or f"_{function.__name__}"

		if (default is not NULL):
			_default = default
		elif (function.__kwdefaults__ is not None):
			_default = function.__kwdefaults__.get(defaultVariable or "default")
		else:
			_default = None

		def getter(self):
			nonlocal getter_runOnce, getter, initializer, _default, catalogueVariable_used #Both functions must have the same number of 'free variables' to replace __code__
			return getattr(self, _variable)

		def getter_runOnce(self):
			if (not hasattr(self, _variable)):
				initializer(self, _default)

			if (catalogueVariable_used is not None):
				if (not hasattr(self, catalogueVariable_used)):
					setattr(self, catalogueVariable_used, {_variable})
				else:
					getattr(self, catalogueVariable_used).add(_variable)

			getter_runOnce.__code__ = getter.__code__
			return getattr(self, _variable)

		def initializer(self, value):
			setattr(self, _variable, function(self, value))

		def remover(self):
			delattr(self, _variable)

		if (readOnly):
			setter = None
		else:
			setter = initializer

		return property(fget = getter_runOnce, fset = setter, fdel = remover, doc = function.__doc__)
	return decorator

class addAlias(object):
	"""A decorator that makes another function that this function can be called by.
	Modified Code from: http://code.activestate.com/recipes/577659-decorators-for-adding-aliases-to-methods-in-a-clas/

	This function MUST be used within a class decorated with canAlias().
	_________________________________________

	Example Use: 
		@addAlias("AddItem")
		def Append(self): pass

	Equivalent Use:
		@addAlias("ipsum", "dolor")
		def lorem(self): pass

		@addAlias("ipsum")
		@addAlias("dolor")
		def lorem(self): pass
	"""

	def __init__(self, *names):
		"""
		names (*str) - What the other names for this function
		"""

		self.aliases = set(names)

	def __call__(self, function):
		"""This method will only be called once. Afterwards, only the function will be called."""

		if (hasattr(self, "_aliases")):
			function._aliases.update(self.aliases)
		else:
			function._aliases = self.aliases
		
		return function

def canAlias(cls):
	"""A class decorator that makes addAlias() work.
	_________________________________________

	Example Use:
		@canAlias
		class MyClass(object):
			@alias("ipsum", "dolor")
			def lorem(self): pass

		assert MyClass.lorem == MyClass.ipsum == MyClass.dolor
	"""

	original = cls.__dict__.copy()
	original_set = set(original.keys())
	for name, method in original.items():
		if (not hasattr(method, "_aliases")):
			continue

		for alias in method._aliases - original_set:
			setattr(cls, alias, method)
	
	return cls

# def makeHook(target, *functionList):
# 	"""A class decorator that creates hook functions for another object.

# 	functionList (*str) - What the functions to make hooks for are called
# 		- If dict: {what the hook is called (str): what the function ito hook to is called (str)}
# 	_________________________________________

# 	The example below will do the same as this:
# 		class Test():
# 			def Append(self, *args, **kwargs):
# 				return self.popup.Append(*args, **kwargs)
# 			def GetValue(self, *args, **kwargs):
# 				return self.popup.GetValue(*args, **kwargs)
# 			def Refresh(self, *args, **kwargs):
# 				return self.popup.Reset(*args, **kwargs)

# 	Equivalent Use:
# 		@makeHook("popup", "Append", "GetValue", {"Refresh": "Reset"})
# 		class Test(): pass

# 		@makeHook("popup", "Append")
# 		@makeHook("popup", "GetValue")
# 		@makeHook("popup", {"Refresh": "Reset"})
# 		class Test(): pass
# 	"""

# 	def decorator(cls):
# 		nonlocal functionList

# 		def hookFactory(name):

# 			def final(hook, self, *args, **kwargs):
# 				return hook(self, *args, **kwargs)

# 			def setup(self, *args, **kwargs):
# 				_target = self
# 				for item in target.split("."):
# 					_target = getattr(_target, item)

# 				hook = getattr(_target, name)

# 				def replace(hook, _self, *_args, **_kwargs):

# 					return final(hook, _self, *_args, **_kwargs)

# 				############################################

# 				setup.__code__ = final.__code__
# 				print(locals().keys())
				
# 				return hook(*args, **kwargs)
# 				# return final(self, *args, **kwargs)

# 			return setup

# 		##################################################

# 		for item in functionList:
# 			for key, value in ensure_dict(item, useAsKey = None).items():
# 				setattr(cls, key, hookFactory(value))

# 		return cls
# 	return decorator

#Etc Functions
def getClosest(myList, number, returnLower = True, autoSort = False):
	"""Returns the closest number in 'myList' to 'number'
	Modified Code from: Lauritz V. Thaulow on https://stackoverflow.com/questions/12141150/from-list-of-integers-get-number-closest-to-a-given-value

	myList (list) - The list to look through
	number (int)  - The number to search with
	returnLower (bool) - Determines what happens if 'number' is equadistant from the left and right bound.
		- If True: Returns the left bound
		- If False: Returns the right bound
	autoSort (bool) - Determines if the list should be sorted before checking
		- If True: Ensures the list is sorted
		- If False: Assumes the list is sorted already

	Example Input: getClosest([7, 15, 25, 30], 20))
	"""

	if (autoSort):
		myList = sorted(myList)

	position = bisect.bisect_left(myList, number)
	if (position == 0):
		answer = myList[0]

	elif (position == len(myList)):
		answer = myList[-1]

	else:
		before = myList[position - 1]
		after = myList[position]

		if (after - number < number - before):
			answer = after
		elif (returnLower):
			answer = before
		else:
			answer = after

	return answer

def getNumber(itemList = None, depthMax = None, _currentDepth = 1):
	"""Returns the number of items in 'itemList'.
	Special thanks to stonesam92 for how to check nested items on https://stackoverflow.com/questions/27761463/how-can-i-get-the-total-number-of-elements-in-my-arbitrarily-nested-list-of-list

	itemList (any) - What to check the number of
	_currentDepth (int) - How many recursions have been done on this branch
	depthMax (int) - The max number of recursions to do
		- If None: Will not limit the number of recursions

	Example Input:: getNumber()
	Example Input:: getNumber([1, 2, 3])
	Example Input:: getNumber({1: 2, 3: {4: 5}})
	"""

	if ((depthMax is not None) and (_currentDepth > depthMax)):
		return 0
	elif (isinstance(itemList, str)):
		return 1
	elif (isinstance(itemList, dict)):
		count = 0
		for key, value in itemList.items():
			count += 1 + getNumber(value, depthMax = depthMax, _currentDepth = _currentDepth + 1)
		return count
	elif (isinstance(itemList, (list, tuple, range)) or hasattr(itemList, '__iter__')):
		return sum(getNumber(item, depthMax = depthMax, _currentDepth = _currentDepth + 1) for item in itemList)
	else:
		return 1

def extendString(source, variable, preMessage = "-- {}: ", postMessage = "\n", *, useForNone = None, useRepr = False, useId = False):
	"""Returns a string that can be used to extend an existing string.
	Will return an empty string if the value of 'variable' for 'source' is 'useForNone'.

	preMessage (str) - What to put before the value of 'variable'
		~ All instances of '{}' will be replaced by a title version of 'variable'

	Example Input: extendString(self, "parent")
	Example Input: extendString(self, "parent", "~ {}: ")
	Example Input: extendString(self, "parent", "-- Source: ")
	Example Input: extendString(self, "parent", useRepr = True)
	Example Input: extendString(self, "parent", useId = True)
	Example Input: extendString(self, "label", preMessage = ", {} = ", postMessage = None)
	"""

	value = getattr(source, variable, useForNone)
	if (value is useForNone):
		return ""

	if (useRepr):
		value = value.__repr__()
	elif (useId):
		value = id(value)

	return f"{ensure_string(preMessage, extend = variable.title())}{value}{ensure_string(postMessage)}"

_srcfile = os.path.normcase(ensure_container.__code__.co_filename)
def getCurrentframe(*, exclude = None):
	"""Returns the current stack frame.
	Modified code from: logging.Logger.findCaller

	exclude (str) - What filename to ignore frames from
		- If list: Will exclude from all given

	Example Input: getCurrentframe()
	Example Input: getCurrentframe(exclude = __file__)
	"""
	global _srcfile

	frame = sys._getframe(1)
	exclude = (_srcfile, *ensure_container(exclude))
	while hasattr(frame, "f_code"):
		if (os.path.normcase(frame.f_code.co_filename) not in exclude):
			return frame
		frame = frame.f_back
	return frame

def getCaller(*, exclude = None, forceTuple = False, 
	include_fileName = False, include_lineNumber = False, include_traceback = False):
	"""Returns information about what function called the function that calls this function.
	Modified code from: logging.Logger.findCaller

	include_fileName (bool) - Determiens the path to the file the function is located in is included
	include_lineNumber (bool) - Determiens if the line the function is called on is included
	include_traceback (bool) - Determiens if traceback information is included

	Example Input: getCaller()
	Example Input: getCaller(exclude = __file__)
	"""

	def yieldInfo():
		frame = getCurrentframe(exclude = exclude)
		code = frame.f_code

		yield code.co_name

		if (include_fileName):
			yield code.co_filename

		if (include_lineNumber):
			yield frame.f_lineno

		if (include_traceback):
			yield f"Stack (most recent call last):\n{''.join(traceback.format_list(traceback.extract_stack(frame)))}".rstrip("\n")

	########################################

	return oneOrMany(yieldInfo, forceTuple = forceTuple)

@contextlib.contextmanager
def openPlus(location = None, mode = "w", *, newline = "\n", closeIO = True, unique = False, unique_template = " ({})"):
	"""Automates opening files in different ways.

	location (str) - Where the file to open is located on disk
		~ If None: Will open an empty io stream
		~ If IO stream: Will use that location in RAM

	mode (str) - How to open the location

	Example Input: openPlus("example.ini")
	Example Input: openPlus(myStream)
	Example Input: openPlus(myStream, mode = "wb")
	"""

	def getHandle():
		nonlocal location, mode, newline

		if (location is None):
			if ("b" in mode):
				return io.BytesIO(location)
			return io.StringIO(location, newline = newline)

		if (isinstance(location, str)):
			directory = os.path.dirname(location)
			if (directory):
				os.makedirs(directory, exist_ok = True)

			if (unique and os.path.exists(location)):
				name, extension = os.path.splitext(location)
				i = 1
				while os.path.exists(f"{name}{unique_template.format(i)}{extension}"):
					i += 1
				location = f"{name}{unique_template.format(i)}{extension}"

			return open(location, mode)

		if (isinstance(location, io.IOBase)):
			return location

		raise NotImplementedError(type(location))

	#####################################

	if (not closeIO):
		yield getHandle()
		return
		
	with getHandle() as fileHandle:
		yield fileHandle
		
class EtcFunctions():
	"""An assortment of etc functions."""

	@classmethod
	def getClosest(cls, *args, **kwargs):
		return getClosest(*args, **kwargs)

	@classmethod
	def getNumber(cls, *args, **kwargs):
		return getNumber(*args, **kwargs)

	@classmethod
	def extendString(cls, *args, **kwargs):
		return extendString(cls, *args, **kwargs)

	@classmethod
	def getCaller(cls, *args, **kwargs):
		return getCaller(*args, **kwargs)

	@classmethod
	def openPlus(cls, *args, **kwargs):
		return openPlus(*args, **kwargs)


def _get(itemCatalogue, label = None, *, returnExists = False, exclude = None, returnForNone = NULL_private):
	"""Searches the label catalogue for the requested object.

	label (any) - What the object is labled as in the catalogue
		- If slice: objects will be returned from between the given spots 
		- If None: Will return all that would be in an unbound slice

	Example Input: _get(self.rowCatalogue)
	Example Input: _get(self.rowCatalogue, 0)
	Example Input: _get(self.rowCatalogue, slice(None, None, None))
	Example Input: _get(self.rowCatalogue, slice(2, 7, None))
	"""

	def yieldSlice(sliceHandle):
		nonlocal itemCatalogue, exclude

		if (sliceHandle.step is not None):
			raise NotImplementedError()
		elif ((sliceHandle.start is not None) and (sliceHandle.start not in itemCatalogue)):
			errorMessage = f"There is no item labled {sliceHandle.start} in the given catalogue"
			raise KeyError(errorMessage)
		elif ((sliceHandle.stop is not None) and (sliceHandle.stop not in itemCatalogue)):
			errorMessage = f"There is no item labled {sliceHandle.stop} in the given catalogue"
			raise KeyError(errorMessage)

		generator = (item for item in sorted(itemCatalogue.keys(), key = lambda item: f"{item}"))
		if (sliceHandle.start is not None):
			for item in generator:
				if (itemCatalogue[item].sliceHandle == sliceHandle.start):
					if (item not in exclude):
						yield item
					break

		if (sliceHandle.stop is not None):
			for item in generator:
				if (itemCatalogue[item].sliceHandle == sliceHandle.stop):
					break
				if (item not in exclude):
					yield item
			return

		for item in generator:
			if (item not in exclude):
				yield item

	#############################################

	exclude = ensure_container(exclude)

	if (label is None):
		return oneOrMany(yieldSlice(slice(None, None, None)))

	if (isinstance(label, slice)):
		return oneOrMany(yieldSlice(label))

	if (returnExists):
		return label in itemCatalogue

	if (label in itemCatalogue):
		return oneOrMany(itemCatalogue[label])

	if (returnForNone is not NULL_private):
		return returnForNone

	errorMessage = f"There is no item labled {label} in the given catalogue"
	raise KeyError(errorMessage)

class Container_Item():
	def __init__(self, label_variable = None):
		self._label_variable = ensure_string(label_variable, returnForNone = "label")

	def __repr__(self):
		representation = f"{self.__class__.__name__}(id = {id(self)}"
		representation += extendString(self, self._label_variable, preMessage = ", {} = ", postMessage = None)
		representation += ")"
		return representation

	def __str__(self):
		output = f"{self.__class__.__name__}()\n-- id: {id(self)}\n"
		output += extendString(self, self._label_variable)
		output += extendString(self, "parent", useRepr = True)
		output += extendString(self, "root", useRepr = True)
		return output

class Container(Container_Item):
	def __init__(self, dataCatalogue = None, label_variable = None):
		Container_Item.__init__(self, label_variable = label_variable)

		assert not hasattr(self, "_dataCatalogue")

		if (isinstance(dataCatalogue, str)):
			if (not hasattr(self, dataCatalogue)):
				setattr(self, dataCatalogue, {})
			self._dataCatalogue = getattr(self, dataCatalogue)

		elif (dataCatalogue is None):
			self._dataCatalogue = {}
			
		else:
			raise NotImplementedError(dataCatalogue)

	def __str__(self):
		output = super().__str__()
		output += extendString(len(self), "Children Count")
		return output

	def __len__(self):
		return len(self._dataCatalogue)

	def __contains__(self, key):
		return _get(self._dataCatalogue, key, returnExists = True)

	def __iter__(self):
		return CommonIterator(self._dataCatalogue)

	def __getitem__(self, key):
		return _get(self._dataCatalogue, key)

	def __setitem__(self, key, value):
		self._dataCatalogue[key] = value

	def __delitem__(self, key):
		del self._dataCatalogue[key]

	def __enter__(self):
		return self

	def __exit__(self, exc_type, exc_value, traceback):
		if (traceback is not None):
			return False

	def keys(self, *args, **kwargs):
		return self._dataCatalogue.keys(*args, **kwargs)

	def values(self, *args, **kwargs):
		return self._dataCatalogue.values(*args, **kwargs)

	def items(self, *args, **kwargs):
		return self._dataCatalogue.items(*args, **kwargs)

	# def mirrorContainer(self, source):
	# 	"""Mirrors the methods from another object.

	# 	Example Input: mirrorContainer(gui_maker)
	# 	"""

	# 	def apply_or_remove(functionName, isFunction = True):
	# 		"""Either mirrors this function, or removes it.

	# 		Example Input: apply_or_remove("keys")
	# 		"""

	# 		if (hasattr(source, functionName)):
	# 			setattr(self, functionName, getattr(source, functionName))
	# 		elif (isFunction):
	# 			setattr(self, functionName, NotImplementedError)
	# 		else:
	# 			delattr(self, functionName)

	# 	###############################

	# 	print("@1", self.__getitem__, source.__getitem__)

	# 	self.__len__ = source.__len__
	# 	self.__iter__ = source.__iter__
	# 	self.__exit__ = source.__exit__
	# 	self.__enter__ = source.__enter__
	# 	self.__getitem__ = source.__getitem__
	# 	self.__setitem__ = source.__setitem__
	# 	self.__delitem__ = source.__delitem__
	# 	self.__contains__ = source.__contains__

	# 	apply_or_remove("keys")
	# 	apply_or_remove("items")
	# 	apply_or_remove("values")
	# 	apply_or_remove("_dataCatalogue", isFunction = False)

	# 	print("@2", self.__getitem__, source.__getitem__)

	def _get(self, *args, **kwargs):
		return _get(self._dataCatalogue, *args, **kwargs)

	def getValue(self, variable, order = True, includeMissing = True, exclude = [], sortNone = False, reverse = False, getFunction = None):
		"""Returns a list of all values for the requested variable.
		Special thanks to Andrew Clark for how to sort None on https://stackoverflow.com/questions/18411560/python-sort-list-with-none-at-the-end

		variable (str) - what variable to retrieve from all rows
		order (str) - By what variable to order the items
			- If variable does not exist: Will place the item at the end of the list with sort() amongst themselves
			- If True: Will use the python list function sort()
			- If False: Will not sort returned items
			- If None: Will not sort returned items
		sortNone (bool) - Determines how None is sorted
			- If True: Will place None at the beginning of the list
			- If False: Will place None at the end of the list
			- If None: Will remove all instances of None from the list

		Example Input: getValue("naed")
		Example Input: getValue(self.easyPrint_selectBy)
		Example Input: getValue("naed", "defaultOrder")
		Example Input: getValue("barcode", sortNone = None)
		"""

		if (not isinstance(exclude, (list, tuple, range))):
			exclude = [exclude]
		if (getFunction is None):
			getFunction = getattr

		if ((order is not None) and (not isinstance(order, bool))):
			data = [getFunction(item, variable) for item in self.getOrder(order, includeMissing = includeMissing, 
				getFunction = getFunction, sortNone = sortNone, exclude = exclude) if (item not in exclude)]
		else:
			data = [getFunction(item, variable) for item in self if (item not in exclude)]

			if ((order is not None) and (isinstance(order, bool)) and order):
				data = sorted(filter(lambda item: True if (sortNone is not None) else (item is not None), data), 
					key = lambda item: (((item is None)     if (reverse) else (item is not None)) if (sortNone) else
										((item is not None) if (reverse) else (item is None)), item), 
					reverse = reverse)

		return data

	def getOrder(self, variable, includeMissing = True, where = None, exclude = [], sortNone = False, reverse = False, 
		getFunction = None, compareFunction = None):
		"""Returns a list of children in order according to the variable given.
		Special thanks to Andrew Dalke for how to sort objects by attributes on https://wiki.python.org/moin/HowTo/Sorting#Key_Functions

		variable (str) - what variable to use for sorting
			- If None: Will not sort it
		includeMissing (bool) - Determiens what to do with children who do not have the requested variable
		getFunction (function) - What function to run to get the value of this variable where the args are [handle, variable]
			- If None: will use getattr
		exclude (list) - What handles should not be included
			- If function: Determine if the handle should be excluded where the args are [handle]

		Example Input: getOrder("order")
		Example Input: getOrder("order", includeMissing = False, sortNone = None)
		Example Input: getOrder("order", getFunction = lambda item, variable: getattr(item, variable.name))
		Example Input: getOrder("order", where = {"inventoryTitle": None}, compareFunction = lambda item, where: all(item.getAttribute(variable) != value for variable, value in where.items()))
		Example Input: getOrder("order", exclude = lambda handle: not handle.removePending)
		"""

		if (not callable(exclude)):
			if (not isinstance(exclude, (list, tuple, range, types.GeneratorType))):
				exclude = [exclude]
			excludeFunction = lambda handle: handle in exclude
		else:
			excludeFunction = exclude
		if (getFunction is None):
			getFunction = getattr

		if (variable is None):
			handleList = self.getHandle(where = where, exclude = excludeFunction, getFunction = getFunction, compareFunction = compareFunction)
		else:
			try:
				handleList = sorted(filter(lambda item: hasattr(item, variable) and (not excludeFunction(item)) and ((sortNone is not None) or (getFunction(item, variable) is not None)), 
					self.getHandle(where = where, exclude = excludeFunction, getFunction = getFunction, compareFunction = compareFunction)), 
					key = lambda item: (((getFunction(item, variable) is None)     if (reverse) else (getFunction(item, variable) is not None)) if (sortNone) else
										((getFunction(item, variable) is not None) if (reverse) else (getFunction(item, variable) is None)), getFunction(item, variable)), 
					reverse = reverse)
			except TypeError as error:
				for item in filter(lambda item: hasattr(item, variable) and (not excludeFunction(item)) and ((sortNone is not None) or (getFunction(item, variable) is not None)), 
					self.getHandle(where = where, exclude = excludeFunction, getFunction = getFunction, compareFunction = compareFunction)):

					print(getFunction(item, variable), item)
				raise error

			if (includeMissing):
				handleList.extend([item for item in self if (not hasattr(item, variable) and (not excludeFunction(item)))])

		return handleList

	def getHandle(self, where = None, exclude = [], getFunction = None, compareFunction = None, compareAsStrings = False):
		"""Returns a list of children whose variables are equal to what is given.

		where (dict) - {variable (str): value (any)}
			- If None, will not check the values given
		exclude (list) - What handles should not be included
			- If function: Determine if the handle should be excluded where the args are [handle]
		getFunction (function) - What function to run to get the value of this variable where the args are [handle, variable]
			- If None: will use getattr
		compareFunction (function) - What function to run to evaluate 'where' where the args are [handle, where]
			- If None: will use getattr

		Example Input: getHandle()
		Example Input: getHandle({"order": 4})
		Example Input: getHandle(exclude = ["main"])
		Example Input: getHandle(exclude = lambda handle: not handle.removePending)
		"""

		if (not callable(exclude)):
			if (not isinstance(exclude, (list, tuple, range, set, types.GeneratorType))):
				exclude = [exclude]
			excludeFunction = lambda handle: handle in exclude
		else:
			excludeFunction = exclude
		if (getFunction is None):
			getFunction = getattr
		if (compareFunction is None):
			if (compareAsStrings):
				compareFunction = lambda handle, where: all(hasattr(handle, variable) and (f"{getFunction(handle, variable)}" == f"{value}") for variable, value in where.items())
			else:
				compareFunction = lambda handle, where: all(hasattr(handle, variable) and (getFunction(handle, variable) == value) for variable, value in where.items())

		handleList = []
		for handle in self:
			if (not excludeFunction(handle)):
				if ((where is None) or (len(where) == 0)):
					handleList.append(handle)
				elif (compareFunction(handle, where)):
					handleList.append(handle)

		return handleList

	def getUnique(self, base = "{}", increment = 1, start = 1, exclude = []):
		"""Returns a unique name with the given criteria.

		Example Input: getUnique()
		Example Input: getUnique("Format_{}")
		Example Input: getUnique(exclude = [item.database_id for item in self.parent])
		"""
		assert increment is not 0

		if (not isinstance(exclude, (list, tuple, range, set, types.GeneratorType))):
			exclude = [exclude]

		while True:
			ending = start + increment - 1
			if ((base.format(ending) in self) or (base.format(ending) in exclude) or (ending in exclude) or (str(ending) in [str(item) for item in exclude])):
				increment += 1
			else:
				break
		return base.format(ending)

# if (__name__ == "__main__"):

	# def test(x):
	# 	print("@test", x)
	# 	jhkhjkjkh
	# 	return 2

	# def test2(error):
	# 	print("@test2", error)

	# print("@__main__", runMyFunction(test, 1, errorFunction = test2))

	# @makeHook("ipsum.dolor", "Append", "SetSelection")
	# class Lorem():
	# 	def __init__(self):
	# 		self.ipsum = Ipsum()

	# class Ipsum():
	# 	def __init__(self):
	# 		self.dolor = Dolor()

	# class Dolor():
	# 	def Append(self, x):
	# 		return (x, 1)

	# 	def SetSelection(self, x):
	# 		return (x, 2)

	# print(tuple(item for item in dir(Lorem) if (not item.startswith("__"))))

	# lorem = Lorem()
	# print(tuple(item for item in dir(lorem) if (not item.startswith("__"))))

	# print(lorem.Append(1))
	# print(lorem.Append(1))
	# print(lorem.Append(1))
	# print(lorem.SetSelection(1))
	# print(lorem.SetSelection(1))
	# print(lorem.SetSelection(1))
	# print(lorem.Append(1))


