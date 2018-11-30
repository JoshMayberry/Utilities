import threading
import cachetools

#Required Modules
##py -m pip install
	# cachetools

# cached = cachetools.cached
class LFUCache(cachetools.LFUCache):
	def __init__(self, maxsize = 128):
		self.initialMaxSize = maxsize

		super().__init__(maxsize = maxsize)

	def setMaxSize(self, size = None):
		"""Sets the max size for the cache.

		size (int) - How large the cache will be
			- If None: Will set the cache to it's initial max size

		Example Input: setMaxSize()
		Example Input: setMaxSize(10)
		"""

		self._Cache__maxsize = size or self.initialMaxSize


def cached(cache = None, *, key = None, typed = False, lock = None, **kwargs):
	"""A decorator function that automates cache creation.

	cache (cachetools.Cache or dict) - What cache to use
		- If None: Will create a LFUCache with the given 'kwargs'

	key (function) - What function to use to find cached objects
		~ Must return a tuple
		- If None: Will create a key based on 'typed'

	typed (bool) - Determines what kind of key is created
		- If True: A key that accounts of object type will be created; 3 != 3.0
		- If True: A key that does not account for object types will be created; 3 == 3.0

	lock (threading.Lock) - What lock to use
		- If None: No lock is used
		- If True: Will use a Lock
		- If False: Will use an RLock

	Example Input: cached()
	Example Input: cached(indexCache)
	"""

	if (cache is None):
		cache = LFUCache(**kwargs)

	if (key is None):
		if (typed):
			key = cachetools.keys.hashkey
		else:
			key = cachetools.keys.typedkey

	if (lock is True):
		lock = threading.Lock()
	elif (lock is False):
		lock = threading.RLock()

	return cachetools.cached(cache, key = key, lock = lock)

