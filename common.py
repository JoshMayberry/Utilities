""" These functions are generic and not project specific. """

import time
import uuid
import types
import queue
import typing
import asyncio
import inspect
import itertools
import traceback
import collections

from heapdict import heapdict

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

def requiredArg(value, message=None):
	""" Throws an error if *value* is None.

	Example Input: requiredArg(value)
	Example Input: requiredArg(value, "Must pass in *value*")
	"""

	if (value is None):
		raise ValueError(message or "A value is None that should not be")

	return value

def tryExcept(pre=None, post=None, onError=None, throwError=False):
	""" A decorator the surrounds the inner function with a try/except

	EXAMPLE USE
		@tryExcept()
		def fragileFunction():
			pass

	EXAMPLE USE
		@tryExcept(pre=lorem, post=ipsum)
		def fragileFunction():
			pass
	"""

	if ((not pre) and (not post) and (not onError)):
		def decorator(myFunction):
			def wrapper(*args, **kwargs):
				try:
					return myFunction(*args, **kwargs)
				except Exception as error:
					if (throwError):
						raise error
					traceback.print_exception(type(error), error, error.__traceback__)
			return wrapper
		return decorator

	def decorator(myFunction):
		def wrapper(*args, **kwargs):
			answer = None
			try:
				if (pre):
					pre(*args, **kwargs)

				answer = myFunction(*args, **kwargs)

				if (post):
					post(answer, *args, **kwargs)

			except Exception as error:
				skip = False
				if (onError):
					try:
						skip = onError(error, answer, *args, **kwargs)
					except Exception as _error:
						if (throwError):
							raise error
						traceback.print_exception(type(_error), _error, _error.__traceback__)

				if (not skip):
					if (throwError):
						raise error
					traceback.print_exception(type(error), error, error.__traceback__)
			return answer
		return wrapper
	return decorator

def runOnFail(onFail, *args, **kwargs):
	""" A decorator that calls a function if an assertion failure happens.
	Use: https://stackoverflow.com/questions/41010841/python-unittest-call-function-when-assertion-fails/41016659#41016659

	Example Use: @runOnFail(sendEmail)
	Example Use: @runOnFail(sendEmail, title="ACAP is Empty")
	"""

	def decorator(myFunction):
		def inner(*args_inner, **kwargs_inner):
			try:
				myFunction(*args_inner, **kwargs_inner)
			except AssertionError as error:
				onFail(error, *args, **kwargs)
				raise error
		return inner
	return decorator

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

	if (forceTuple or (len(answer) != 1)):
		return answer
	elif (isDict):
		return next(iter(answer.values()), returnForNone)
	else:
		return next(iter(answer), returnForNone)

def ensure_lastElement(container, default = None):
	"""Returns the last element in 'container' if there is one; otherwise returns 'default'.
	Assumes that 'container' is indexable.

	Example Input: ensure_lastElement(myList)
	Example Input: ensure_lastElement(myList, default = int)
	"""

	if (not container):
		return default

	return container[-1]

def is_container(item, *, elementTypes=None, elementCriteria=None):
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
	Example Input: is_container([{"a":1, "b":2}, {"a":1, "b":2}], elementCriteria=(None, dict))
	Example Input: is_container(["lorem", {"a":1, "b":2}], elementCriteria=(2, (None, dict)))
	"""

	def checkItem(_item, _type):
		if (_type is None):
			return True

		return isinstance(_item, _type)

	def checkType(requiredLength, requiredType):
		nonlocal item

		if (requiredLength and (len(item) != requiredLength)):
			return False

		if (requiredType is None):
			return True

		container = ensure_container(requiredType)
		return all(checkItem(*_item) for _item in itertools.zip_longest(item, container, fillvalue=ensure_lastElement(container)))

	###########################

	if (isinstance(item, (str, ELEMENT, typing.Mapping, typing.MutableMapping))):
		return False

	if (not isinstance(item, typing.Iterable)):
		return False

	if ((elementTypes is not None) and isinstance(item, tuple(ensure_container(elementTypes, convertNone=True)))):
		return False

	if (not isinstance(item, (list, tuple, set, typing.ItemsView, typing.KeysView, typing.ValuesView))):
		return False
		
	if (not len(item)):
		return True

	if (elementCriteria is None):
		return True

	if (not isinstance(elementCriteria[0], tuple)): ## TO DO ## This line is clunky; find another way
		elementCriteria = (elementCriteria,)

	return not any(checkType(*required) for required in elementCriteria)

def ensure_container(*args, **kwargs):
	return tuple(iensure_container(*args, **kwargs))

def iensure_container(container, *, useForNone=None, convertNone=True, is_container_answer=NULL_private,
	returnForNone=None, evaluateGenerator=True, consumeFunction=True, checkIteratorFunction=None,
	can_yieldSubContainer=True, subContainer_nestedLimit=None, checkGeneratorItems=True, **kwargs):
	"""Makes sure the given item is a container.
	Iterable objects are not counted as containers if they inherit ELEMENT.

	args (*) - What should be appended to the end of the container 'item'
	returnForNone (any) - What should be returned if 'item' is None
		- If function: will return whatever the function returns

	Example Input: iensure_container(valueList)
	Example Input: iensure_container(valueList, convertNone = False)
	Example Input: iensure_container(valueList, evaluateGenerator = False)
	Example Input: iensure_container((x for x in range(3)))
	Example Input: iensure_container(handle, elementTypes = (Base,))
	Example Input: iensure_container((255, 255, 0), elementCriteria = (3, int))
	Example Input: iensure_container((255, 255, 0), elementCriteria = ((3, int), (4, int)))
	Example Input: iensure_container(valueList, convertNone=False, returnForNone=lamda:[1,2,3])
	Example Input: iensure_container(frame, checkIteratorFunction=lambda item: not isinstance(item, pandas.DataFrame))
	Example Input: iensure_container(((1,2), (3,4)), can_yieldSubContainer=False)
	Example Input: iensure_container(([(1,2), (3,4)], [(5,6), (7,8)]), can_yieldSubContainer=False, subContainer_nestedLimit=1)
	"""

	def yieldSubContainer(_container):
		nonlocal returnForNone

		if (_container is useForNone):
			if (not convertNone):
				if (consumeFunction and (inspect.ismethod(returnForNone) or inspect.isfunction(returnForNone))):
					returnForNone = returnForNone()

				if (not is_container(returnForNone, **kwargs)):
					returnForNone = (returnForNone,)

				for item in returnForNone:
					yield item
			return

		state = is_container_answer
		if (state is NULL_private):
			if (evaluateGenerator and isinstance(_container, types.GeneratorType)):
				if (not checkGeneratorItems):
					for item in _container:
						yield item
					return

				for item in _container:
					for _item in ensure_container(item, useForNone=useForNone, convertNone=convertNone, returnForNone=returnForNone, evaluateGenerator=evaluateGenerator, consumeFunction=consumeFunction, checkIteratorFunction=checkIteratorFunction, can_yieldSubContainer=can_yieldSubContainer, subContainer_nestedLimit=subContainer_nestedLimit, **kwargs):
						yield _item
				return

			state = is_container(_container, **kwargs)

		if (state):
			for item in _container:
				yield item
			return

		if (state is not None):
			yield _container
			return

		if ((not isinstance(_container, typing.Iterable)) or (checkIteratorFunction and (not checkIteratorFunction(_container)))):
			yield _container
			return

		for item in _container:
			for _item in ensure_container(item, useForNone=useForNone, convertNone=convertNone, returnForNone=returnForNone, evaluateGenerator=evaluateGenerator, consumeFunction=consumeFunction, checkIteratorFunction=checkIteratorFunction, can_yieldSubContainer=can_yieldSubContainer, subContainer_nestedLimit=subContainer_nestedLimit, **kwargs):
				yield _item

	def yieldSubItem(_container, nested=0):
		if (subContainer_nestedLimit and (nested >= subContainer_nestedLimit)):
			for item in yieldSubContainer(_container):
				yield item
			return

		for item in yieldSubContainer(_container):
			if (not (is_container(item, **kwargs) or (evaluateGenerator and isinstance(item, types.GeneratorType)))):
				yield item
				continue

			for _item in yieldSubItem(item, nested=nested + 1):
				yield _item

	#########################

	if (can_yieldSubContainer):
		for item in yieldSubContainer(container):
			yield item
		return

	for item in yieldSubItem(container):
		yield item

def ensure_dict(catalogue, defaultKey=None, *, useAsKey=False, convertContainer=False, convertNone=True, useForNone=None, useForTrue=None, returnForNone=NULL_private):
	"""Makes sure the given catalogue is a dictionary.
	Objects are counted as dictionaries if they inherit CATALOGUE.

	catalogue (any) - What to make sure is a dictionary
	defaultKey (any) - What to use for the key if *catalogue* is not a dictionary
	useAsKey (bool) - Determines how *catalogue* is used if it is not a dictionary
		- If True: {catalogue: defaultKey}
		- If False: {defaultKey: catalogue}
		- If None: {catalogue: catalogue}
	convertNone (bool) - If when *catalogue* is None, return *returnForNone*
	convertContainer (bool) - If *catalogue* is a container, should each key be recursively pass through this function?
	useForNone (any) - What to compare against to see if it is None
	returnForNone (any) - What to return if *catalogue* is None; defaults to an empty dictionary

	Example Input: ensure_dict("value")
	Example Input: ensure_dict("value", "key")
	Example Input: ensure_dict({"key": "value"})
	Example Input: ensure_dict("key", "value", useAsKey=True)
	Example Input: ensure_dict(None, useForNone=PyUtilities.common.NULL)
	Example Input: ensure_dict(None, "key", convertNone=False)

	Example Input: ensure_dict("lorem", defaultKey="id")
	Example Input: ensure_dict({"id": "lorem", "value": "ipsum"}, defaultKey="id")
	Example Input: ensure_dict(true, defaultKey="id", useForTrue={"id": -1, is_internal: true})

	"""

	if (convertNone and (catalogue is useForNone)):
		if (returnForNone is NULL_private):
			return {}
		return returnForNone

	if ((useForTrue is not None) and isinstance(catalogue, bool) and catalogue):
		return useForTrue

	if (isinstance(catalogue, (dict, CATALOGUE))):
		return catalogue

	if (convertContainer and is_container(catalogue)):
		answer = {}
		for item in catalogue:
			answer.update(ensure_dict(item, defaultKey=defaultKey, useAsKey=useAsKey,
				convertContainer=convertContainer, convertNone=convertNone, useForNone=useForNone, returnForNone=returnForNone
			))
		return answer

	if (useAsKey is None):
		return {catalogue: catalogue}

	if (useAsKey):
		return {catalogue: defaultKey}

	return {defaultKey: catalogue}

def yieldChunk(container, chunk_size=1000, *, chunk_offset=0, yield_index=False, yieldGenerator=False, **kwargs):
	""" Yields a chunk of items from the given container (even if it's a generator).
	Use: https://stackoverflow.com/questions/8991506/iterate-an-iterator-by-chunks-of-n-in-python/8998040#8998040

	Example Input: yieldChunk(1, 2)
	Example Input: yieldChunk((1,2,3,4,5), 2)
	Example Input: yieldChunk(generator, 2)
	Example Input: yieldChunk((1,2,3,4,5), 2, chunk_offset=1)
	Example Input: yieldChunk((1,2,3,4,5), 2, chunk_offset=1, yield_index=True)
	"""


	if (not isinstance(container, types.GeneratorType)):
		container = iensure_container(container, **kwargs)

	i = chunk_offset;
	if (chunk_offset):
		for x in range(0, chunk_offset):
			consumeIterator(itertools.islice(container, chunk_size))

	while True:
		generator = itertools.islice(container, chunk_size)

		try:
			first = next(generator)
		except StopIteration:
			return

		generator_combined = itertools.chain((first,), generator)
		if (not yieldGenerator):
			generator_combined = tuple(generator_combined)

		if (yield_index):
			yield (i, generator_combined)
			i += 1
			continue;

		yield generator_combined

def consumeIterator(generator, n=None):
	""" Skips *n* items in the given generator.
	If *n* is not given, will consume the entire generator.
	Use: https://stackoverflow.com/questions/5509302/whats-the-best-way-of-skip-n-values-of-the-iteration-variable-in-python/64250255#64250255
	Use: https://docs.python.org/3.7/library/itertools.html#itertools-recipes

	Example Input: consumeIterator(generator)
	Example Input: consumeIterator(generator, 3)
	"""

	if (n is None):
		return collections.deque(generator, maxlen=0)

	return next(itertools.islice(generator, n-1, n), None)

def syncRunAsync(myFunction, *, loop=None):
	""" Runs an async function as a sync function.
	Use: https://www.joeltok.com/posts/2021-02-python-async-sync/

	Example Input: syncRunAsync(lorem())
	"""

	async def runFunction():
		return await myFunction

	###################

	loop = loop or asyncio.new_event_loop()
	return loop.run_until_complete(runFunction())

class PriorityQueue():
	""" Initially created by ChatGPT.

	PROMPT
		Imagine you are a program that writes python programs.
		Help me write a python program using "queue.PriorityQueue".

		I need a Priority Queue that uses a string label as the key for each item.
		Items with a higher priority should come first when calling `next()` and have a lower `position()`, regardless of when they were inserted.

		Each item should be a dictionary with the following key/value pairs:
			- token: A uuid unique to this item
			- timestamp: A timestamp when the item was added to the queue
			- priority: What priority this item has; defaults to 0 and can be negative

		The correct token should be required by the following methods before they will work:
			- increase/decrease the priority of an item after it is added
			- remove an item from the queue

		We should be able to do the following:
			- Get a list of dictionaries from the queue without removing the items
			- Ask for the next item in the queue and have it automatically removed
			- Optionally limit how many thigns can be in queue at once
			- Ask what position an item is in in the queue
			- Ask what time an item entered the queue at

		Errors should be thrown in the following scenarios:
			- InvalidTokenError: Modify priority or remove with invalid token
			- FullError: Adding when queue is too full (only if a queue limit was given)
			- AlreadyInQueueError: Adding an item to the queue that is already in the queue

		Add an optional list that can be given to the constructor. In the case that multiple items have the same priority, use that list to determine which should come out next

		EXAMPLE USE
			# Create a new priority queue
			>>> myQueue = PriorityQueue(limit=10)

			# Add items to the queue with optional priority
			>>> myQueue.add("lorem")
			'6edd1645-04b4-4c6a-972c-04236c73827b'
			>>> myQueue.add("ipsum", priority=1)
			'91b66494-3fe7-4673-8f85-558e66e625db'
			>>> myQueue.add("dolor")
			'2de01d08-7f4f-4b78-b6ea-1a2f435614fb'

			# Check if an item is in the queue and get its position
			>>> myQueue.position("ipsum")
			0
			>>> myQueue.position("dolor")
			2
			>>> myQueue.position("lorem")
			1
			>>> myQueue.position("sit")
			None

			# Get an item's timestamp
			>>> myQueue.timestamp("lorem")
			1682633006.5570998

			# Get all the info for an item (except it's token)
			>>> myQueue.info("lorem")
			{'label': 'lorem', position': 1, timestamp': 1682633006.5570998, 'priority': 0}

			# Remove an item in the queue
			>>> myQueue.remove("dolor")
			InvalidTokenError
			>>> myQueue.remove("dolor", token="6edd1645-04b4-4c6a-972c-04236c73827b")
			InvalidTokenError
			>>> myQueue.remove("dolor", token="2de01d08-7f4f-4b78-b6ea-1a2f435614fb")
			True

			# Get the info for the entire queue
			>>> myQueue.infoAll()
			[{'label': 'ipsum', 'priority': 1, 'position': 0, timestamp': 1682633259.7568653}, {'label': 'lorem', 'priority': 0, 'position': 1, timestamp': 1682633006.5570998}]

			# Get the next item in the queue (removing it from the queue)
			>>> myQueue.next()
			'ipsum'
			>>> myQueue.next()
			'lorem'
			>>> myQueue.next()
			None
	"""

	def __init__(self, limit=None, tiebreak_order=None):
		""" Initialize a new PriorityQueue instance with an optional limit.

		limit (int, optional) - The maximum number of items allowed in the queue. Default is None.

		Example Input: PriorityQueue(limit=10)
		"""

		self.limit = limit if (limit and (limit > 0)) else None
		self.tiebreak_order = tiebreak_order or []
		self.queue = heapdict()
		self.items = {}

	def __len__(self):
		return len(self.queue)

	def __bool__(self):
		return len(self.queue) > 0

	def __contains__(self, label):
		return (label in self.items)

	def isFull(self):
		""" Returns if the queue is full or not.

		Example Input: isFull()
		"""

		return ((self.limit is not None) and (len(self.queue) >= self.limit))

	def add(self, label, priority=0):
		""" Add a new item to the PriorityQueue with an optional priority.
		Returns A unique token (str) for the added item.

		label (str) - The label to associate with the new item.
		priority (int, optional) - The priority of the item. Default is 0.

		Example Input: add("lorem", priority=2)
		"""

		if (self.isFull()):
			raise PriorityQueue.FullError

		if (label in self.items):
			raise PriorityQueue.AlreadyInQueueError

		token = str(uuid.uuid4())
		timestamp = time.time()

		# Apply tiebreak order
		if label in self.tiebreak_order:
			tiebreak_priority = self.tiebreak_order.index(label)
		else:
			tiebreak_priority = len(self.tiebreak_order)

		self.queue[label] = (-priority, tiebreak_priority) # Negate the priority to ensure higher priorities come first
		self.items[label] = {"token": token, "timestamp": timestamp, "priority": priority}

		return token

	def increase_priority(self, label, token, amount=1):
		""" Increase the priority of an item in the PriorityQueue.

		label (str) - The label of the item to update.
		token (str) - The token associated with the item.
		amount (int, optional) - The amount to increase the priority by. Default is 1.

		Example Input: increase_priority("lorem", token="some_token", amount=2)
		"""

		if ((label not in self.items) or (self.items[label]["token"] != token)):
			raise PriorityQueue.InvalidTokenError

		self.queue[label] -= amount  # Update the priority in the queue
		self.items[label]["priority"] += amount  # Update the priority in the items dictionary

	def decrease_priority(self, label, token, amount=1):
		""" Decrease the priority of an item in the PriorityQueue.

		label (str) - The label of the item to update.
		token (str) - The token associated with the item.
		amount (int, optional) - The amount to decrease the priority by. Default is 1.

		Example Input: decrease_priority("lorem", token="some_token", amount=2)
		"""

		self.increase_priority(label, token, -amount)

	def remove(self, label, token):
		""" Remove an item from the PriorityQueue.
		Returns True if the item was successfully removed.

		label (str) - The label of the item to remove.
		token (str) - The token associated with the item.

		Example Input: remove("lorem", token="some_token")
		"""

		if ((label not in self.items) or (self.items[label]["token"] != token)):
			raise PriorityQueue.InvalidTokenError

		del self.queue[label]
		del self.items[label]

		return True

	def position(self, label):
		""" Get the position of an item in the PriorityQueue.
		Returns the position (int) of the item in the queue, or None if the item is not in the queue.

		label (str) - The label of the item to retrieve the position for.

		Example Input: position("lorem")
		"""

		if (label not in self.items):
			return None

		return sorted(self.queue.keys(), key=lambda x: self.queue[x]).index(label)

	def timestamp(self, label):
		""" Return the timestamp of the specified item in the queue, or None if the item is not in the queue.

		label (str) - The label of the item to retrieve the timestamp for.

		Example Input: timestamp("lorem")
		"""

		catalogue = self.items.get(label)
		if (not catalogue):
			return None

		return catalogue["timestamp"]

	def priority(self, label):
		""" Return the priority of the specified item in the queue, or None if the item is not in the queue.

		label (str) - The label of the item to retrieve the priority for.

		Example Input: priority("lorem")
		"""

		catalogue = self.items.get(label)
		if (not catalogue):
			return None

		return catalogue["priority"]

	def info(self, label=None):
		""" Get all the information for an item in the PriorityQueue (except its token).
		Returns a dictionary containing the item's information, or None if the item is not in the queue.

		label (str) - The label of the item to retrieve the information for.

		Example Input: info("lorem")
		"""

		if (label is None):
			return tuple(self.yield_info())

		catalogue = self.items.get(label)
		if (not catalogue):
			return None

		return {"label": label, "priority": catalogue["priority"], "timestamp": catalogue["timestamp"], "position": self.position(label)}

	def yield_info(self):
		""" Get the information for all items in the PriorityQueue.
		Yields dictionaries containing the information for each item in the queue.

		Example Input: yield_info()
		"""

		for label in self.queue.keys():
			yield self.info(label)

	def next(self):
		""" Get the next item in the PriorityQueue (removing it from the queue).

		Example Input: next()
		"""

		if not self.queue:
			return None

		label, _ = self.queue.popitem()
		del self.items[label]

		return label

	class FullError(Exception):
		pass

	class AlreadyInQueueError(Exception):
		pass

	class InvalidTokenError(Exception):
		pass

	@classmethod
	def test(cls):
		""" Prompt:	Add a test function using assert that can be ran to verify the class works as intended

		Example Input: test()
		"""

		# Create a new priority queue with a limit of 3 items
		pq = PriorityQueue(limit=3)

		# Add items to the queue with optional priority
		token1 = pq.add("apple", priority=3)
		token2 = pq.add("banana", priority=1)
		token3 = pq.add("cherry", priority=2)

		# Check if an item is in the queue and get its position
		assert pq.position("apple") == 0
		assert pq.position("banana") == 2
		assert pq.position("cherry") == 1
		assert pq.position("orange") is None

		# Increase priority of an item
		pq.increase_priority("banana", token2, amount=4)

		# Verify updated position
		assert pq.position("banana") == 0

		# Decrease priority of an item
		pq.decrease_priority("banana", token2, amount=2)

		# Verify updated position
		assert pq.position("banana") == 1

		# Verify the next item in the queue
		assert pq.next() == "banana"

		# Verify the next item in the queue after removing the previous one
		assert pq.next() == "apple"

		# Verify removing an item with an incorrect token raises an error
		try:
			pq.remove("cherry", "invalid_token")
		except PriorityQueue.InvalidTokenError:
			pass
		else:
			assert False, "Expected InvalidTokenError"

		# Verify adding an item when the queue is full raises an error
		token4 = pq.add("orange")
		token4 = pq.add("apple")
		try:
			pq.add("grape")
		except PriorityQueue.FullError:
			pass
		else:
			assert False, "Expected FullError"

		# Verify removing an item with the correct token
		assert pq.remove("cherry", token3)

		# Verify adding an item already in the queue raises an error
		try:
			pq.add("orange")
		except PriorityQueue.AlreadyInQueueError:
			pass
		else:
			assert False, "Expected AlreadyInQueueError"

	@classmethod
	def test_tiebreak(cls):
		""" Prompt: Write a test function to make sure `tiebreak_order` works as intended

		Example Input: test_tiebreak()
		"""

		tiebreak_order = ["apple", "banana", "cherry", "orange"]

		# Create a new priority queue with a tiebreak_order list
		pq = PriorityQueue(limit=4, tiebreak_order=tiebreak_order)

		# Add items with equal priority
		pq.add("cherry")
		pq.add("apple")
		pq.add("orange")
		pq.add("banana", priority=1)

		# Verify the position of items based on tiebreak_order
		assert pq.position("banana") == 0
		assert pq.position("apple") == 1
		assert pq.position("cherry") == 2
		assert pq.position("orange") == 3

		# Verify the next item based on tiebreak_order
		assert pq.next() == "banana"
		assert pq.next() == "apple"
		assert pq.next() == "cherry"
		assert pq.next() == "orange"



if (__name__ == "__main__"):
	# print(is_container([{"a":1, "b":2}, {"a":1, "b":2}]))
	# print(is_container([{"a":1, "b":2}, {"a":1, "b":2}], elementCriteria=(None, dict)))

	# print(ensure_container(([(1,2), (3,4)], [(5,6), (7,8)])))
	# print(ensure_container(([(1,2), (3,4)], [(5,6), (7,8)]), can_yieldSubContainer=False))
	# print(ensure_container(([(1,2), (3,4)], [(5,6), (7,8)]), can_yieldSubContainer=False, subContainer_nestedLimit=1))

	# print(is_container(["lorem", {"a":1, "b":2}]))
	# print(is_container(["lorem", {"a":1, "b":2}], elementCriteria=(2, (None, dict))))
	
	# PriorityQueue.test()
	PriorityQueue.test_tiebreak()