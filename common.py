import os
import sys
import typing

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

def ensure_container(item, evaluateGenerator = True, convertNone = True, elementTypes = None):
	"""Makes sure the given item is a container.

	elementTypes (list) - Extra types that are ok to be elements

	Example Input: ensure_container(valueList)
	Example Input: ensure_container(valueList, convertNone = False)
	Example Input: ensure_container(valueList, evaluateGenerator = False)
	Example Input: ensure_container(handle, elementTypes = (Base,))
	"""

	if (item is None):
		if (convertNone):
			return ()
		return (None,)

	if ((isinstance(item, (str, typing.Mapping, typing.MutableMapping)) or (not isinstance(item, typing.Iterable))) or (isinstance(item, tuple(ensure_container(elementTypes, convertNone = True))))):
		return (item,)

	if (not isinstance(item, (list, tuple, set))):
		if (evaluateGenerator and not callable(item)):
			return tuple(item)
		return item
	return item

class Ensure():
	@classmethod
	def ensure_set(cls, *args, **kwargs):
		return ensure_set(*args, **kwargs)

	@classmethod
	def ensure_list(cls, *args, **kwargs):
		return ensure_list(*args, **kwargs)

	@classmethod
	def ensure_container(cls, *args, **kwargs):
		return ensure_container(*args, **kwargs)

#Etc
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

def nestedUpdate(target, catalogue):
	"""Updates a nested dictionary.
	Modified code from Alex Martelli on https://stackoverflow.com/questions/3232943/update-value-of-a-nested-dictionary-of-varying-depth/3233356#3233356
	
	Example Input: nestedUpdate(self.contents, self.contents_override)
	"""

	for key, value in catalogue.items():
		if (isinstance(value, dict)):
			target[key] = nestedUpdate(target.get(key, {}), value)
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

class CommonFunctions():
	@classmethod
	def nestedUpdate(cls, *args, **kwargs):
		return nestedUpdate(*args, **kwargs)
		

	@classmethod
	def _StringToValue(cls, *args, **kwargs):
		return _StringToValue(*args, **kwargs)
		

	@classmethod
	def _SetValueUsingMunger(cls, *args, **kwargs):
		return _SetValueUsingMunger(*args, **kwargs)


	@classmethod
	def _Munge(cls, *args, **kwargs):
		return _Munge(*args, **kwargs)
	
