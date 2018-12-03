import os
import sys
import ast

import re
import stat
import shutil
import typing
import inspect
import collections

class Singleton():
	"""Used to get values correctly.

	Example Use: FLAG = MyUtilities.common.Singleton("FLAG")
	"""

	def __init__(self, label = "Singleton"):
		self.label = label

	def __repr__(self):
		return f"{self.label}()"

NULL = Singleton("NULL")

class ELEMENT():
	"""Used to make a class pass ensure_container() as an element instead of a container."""

#Iterators
class CustomIterator():
	"""Iterates over items in an external list."""
	def __init__(self, parent, variableName, loop = False, printError = False):
		"""
		parent (object) - The object that will be using this iterator; typically self
		variableName (str) - The name of a variable in *parent* that will be used as the list to iterate through
		loop (bool) - If the iterator should never stop, and link the two ends of the list
		printError (bool) - If errors should be printed

		Example Input: CustomIterator(self, "printBarcode_containerList")
		"""

		self.index = -1
		self.loop = loop
		self.parent = parent
		self.printError = printError

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

	def previous(self):
		"""Returns the previous item in the list.

		Example input: previous()
		"""

		try:
			if (self.index == -1):
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

def ensure_container(item, *, convertNone = True, returnForNone = None, 
	evaluateGenerator = True, elementTypes = None, elementCriteria = None):
	"""Makes sure the given item is a container.

	returnForNone (any) - What should be returned if 'item' is None
		- If function: will return whatever the function returns

	elementTypes (list) - Extra types that are ok to be elements
	elementCriteria (tuple) - Allows for formatted tuples to pass as elements if they match the criteria
		~ (required length (int), required type (type))
		- If None: Will count all tuples as containers

	Example Input: ensure_container(valueList)
	Example Input: ensure_container(valueList, convertNone = False)
	Example Input: ensure_container(valueList, evaluateGenerator = False)

	Example Input: ensure_container(handle, elementTypes = (Base,))
	Example Input: ensure_container((255, 255, 0), elementCriteria = (3, int))
	Example Input: ensure_container((255, 255, 0), elementCriteria = ((3, int), (4, int)))
	"""

	if (item is None):
		if (convertNone):
			return ()
		if (callable(returnForNone)):
			return returnForNone()
		return (returnForNone,)

	if ((isinstance(item, (str, ELEMENT, typing.Mapping, typing.MutableMapping)) or (not isinstance(item, typing.Iterable))) or (isinstance(item, tuple(ensure_container(elementTypes, convertNone = True))))):
		return (item,)

	if ((elementCriteria is not None) and isinstance(item, (tuple, list))):
		if (not item):
			return ()

		if (not isinstance(elementCriteria[0], tuple)):
			elementCriteria = (elementCriteria,)
		for requiredLength, requiredType in elementCriteria:
			if ((len(item) == requiredLength) and (all((isinstance(subItem, requiredType)) for subItem in item))):
				return (item,)
		return item

	if (not isinstance(item, (list, tuple, set))):
		if (evaluateGenerator and not callable(item)):
			return ensure_container(tuple(item), convertNone = convertNone, returnForNone = returnForNone, evaluateGenerator = evaluateGenerator, elementTypes = elementTypes, elementCriteria = elementCriteria)
		return item
	return item

def ensure_dict(catalogue, default = None, *, useAsKey = True):
	"""Makes sure the given catalogue is a dictionary.

	useAsKey (bool) - Determines how 'catalogue' is used if it is not a dictionary
		- If True: {catalogue: default}
		- If False: {default: catalogue}
		- If None: {catalogue: catalogue}

	Example Input: ensure_dict(relation, attribute)
	"""

	if (isinstance(catalogue, dict)):
		return catalogue
	if (useAsKey is None):
		return {catalogue: catalogue}
	if (useAsKey):
		return {catalogue: default}
	return {default: catalogue}

def ensure_default(value, default = None, *, consumeFunction = True, defaultFlag = None, condition = None):
	"""Returns 'default' if 'value' is 'defaultFlag'.
	otherwise returns 'value'.

	condition (callable) - An extra condition that must be met
		- If None: Does nothing

	Example Input: ensureDefault(autoPrint, False)
	Example Input: ensureDefault(autoPrint, lambda: self.checkPermission("autoPrint"))
	Example Input: ensureDefault(autoPrint, defaultFlag = NULL)
	Example Input: ensureDefault(myFunction, self.checkPermission, consumeFunction = False)
	"""

	def useDefault():
		nonlocal value, defaultFlag

		if (value is defaultFlag):
			return True

		if ((condition is not None) and condition(value)):
			return True

	######################################

	if (useDefault()):
		if (consumeFunction and callable(default)):
			return default()
		return default
	return value

def ensure_string(value, *, returnForNone = ""):
	"""Returns 'value' as a string.

	returnForNone (str) - What to return if 'value' is None

	Example Input: ensure_string(value)
	Example Input: ensure_string(value, returnForNone = "Empty")
	"""

	if (value is None):
		return returnForNone
	return f"{value}"

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
	
#Decorators
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

def makeProperty(*, publisher = None, subscription = None):
	"""Turns the decorated class into a property.
	Uses the docstring of the class for the docstring of the property.
	Uses the functions getter, setter, and remover to create the property.

	publisher (module) - The pubsub module to use for 'subscription'
		- If None: 'subscription' will not be used
	subscription (str) - A pubsub subscription label to subscribe the setter to
		~ Note: You will have to pass in the self parameter as a different kwarg for this to work
		- If None: Will use the property name as the subscription label
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

	Use Variation:
		@makeProperty(publisher = pubsub.pub)
		class lorem(classHandle = None):

	Use Variation:
		@makeProperty(publisher = pubsub.pub, subscription = "dolor")
		class lorem(classHandle = None):
	"""

	def decorator(cls):
		setter = getattr(cls, "setter", None)
		if (publisher is not None):
			publisher.subscribe(setter, subscription or cls.__name__)

		return property(
			fset = setter, 
			fget = getattr(cls, "getter", None), 
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