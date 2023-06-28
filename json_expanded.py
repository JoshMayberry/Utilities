import json
import pandas
import datetime
import collections

global__set_tag = "_set"
global__timedelta_tag = "_timedelta"
global__datetime_tag = "_datetime"
global__datetime_method = "dict"

#Expand JSON
class _JSONEncoder(json.JSONEncoder):
	"""Allows sets to be saved in JSON files.
	Use: https://stackoverflow.com/questions/8230315/how-to-json-serialize-sets/36252257#36252257
	Use: https://gist.github.com/majgis/4200488

	Example Use: 
		json.dumps(["abc", {1, 2, 3}], cls = _JSONEncoder)

		json._default_encoder = _JSONEncoder()
		json.dumps(["abc", {1, 2, 3}])
	"""

	def default(self, item):
		if (pandas.isnull(item)):
			return None
				
		if (isinstance(item, set)):
			return {global__set_tag: list(item)}

		if isinstance(item, datetime.datetime):
			if (global__datetime_method == "string"):
				return item.strftime(r"%Y-%m-%dT%H:%M:%S")

			return {
				global__datetime_tag: {
					'year' : item.year,
					'month' : item.month,
					'day' : item.day,
					'hour' : item.hour,
					'minute' : item.minute,
					'second' : item.second,
					'microsecond' : item.microsecond,
				}
			}

		if (isinstance(item, datetime.timedelta)):
			return {
				global__timedelta_tag: {
					'days' : item.days,
					'seconds' : item.seconds,
					'microseconds' : item.microseconds,
				}
			}

		return super().default(item)

class _JSONDecoder(json.JSONDecoder):
	"""Allows sets to be loaded from JSON files.
	Use: https://stackoverflow.com/questions/8230315/how-to-json-serialize-sets/36252257#36252257
	Use: https://gist.github.com/majgis/4200488

	Example Use: 
		json.loads(encoded, cls = _JSONDecoder)

		json._default_decoder = _JSONDecoder()
		json.loads(encoded)
	"""

	def __init__(self, *, object_hook=None, **kwargs):
		super().__init__(object_hook = object_hook or self.myHook, **kwargs)

	def myHook(self, catalogue):
		if (global__set_tag in catalogue):
			return set(catalogue[global__set_tag])

		if (global__datetime_tag in catalogue):
			return datetime.datetime(**catalogue[global__datetime_tag])

		if (global__timedelta_tag in catalogue):
			return datetime.timedelta(**catalogue[global__timedelta_tag])

		return catalogue

def makeDefault(set_tag=None, timedelta_tag=None, datetime_tag=None, datetime_method=None, **kwargs):
	global global__set_tag, global__timedelta_tag, global__datetime_tag, global__datetime_method

	global__set_tag = set_tag or ""
	global__timedelta_tag = timedelta_tag or ""
	global__datetime_tag = datetime_tag or ""
	global__datetime_method = datetime_method or ""


	json._default_encoder = _JSONEncoder(**kwargs)
	json._default_decoder = _JSONDecoder(**kwargs)

	original_dump = json.dump
	def mp_dump(*args, cls = None, **kwargs):
		"""Defaults to *_JSONEncoder* when kwargs are given"""

		if (cls is None):
			cls = _JSONEncoder

		return original_dump(*args, cls = cls, **kwargs)
	json.dump = mp_dump

	original_dumps = json.dumps
	def mp_dumps(*args, cls = None, **kwargs):
		"""Defaults to *_JSONEncoder* when kwargs are given"""

		if (cls is None):
			cls = _JSONEncoder

		return original_dumps(*args, cls = cls, **kwargs)
	json.dumps = mp_dumps

	original_load = json.load
	def mp_load(*args, cls = None, **kwargs):
		"""Defaults to *_JSONDecoder* when kwargs are given"""

		if (cls is None):
			cls = _JSONDecoder

		return original_load(*args, cls = cls, **kwargs)
	json.load = mp_load

	original_loads = json.loads
	def mp_loads(*args, cls = None, **kwargs):
		"""Defaults to *_JSONDecoder* when kwargs are given"""

		if (cls is None):
			cls = _JSONDecoder

		return original_loads(*args, cls = cls, **kwargs)
	json.loads = mp_loads