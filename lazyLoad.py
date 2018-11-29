import lazy_import

lazy_import.lazy_module("os")
lazy_import.lazy_module("re")
lazy_import.lazy_module("sys")
lazy_import.lazy_module("math")
lazy_import.lazy_module("types")

lazy_import.lazy_module("shutil")
lazy_import.lazy_module("typing")
lazy_import.lazy_module("inspect")

lazy_import.lazy_module("operator")
lazy_import.lazy_module("functools")
lazy_import.lazy_module("contextlib")
lazy_import.lazy_module("collections")

lazy_import.lazy_module("PIL")
lazy_import.lazy_module("stat")

def load_wx():
	"""Loads all the wxPython modules.

	Example Input: load_wx()
	"""
	
	lazy_import.lazy_module("wx")
	lazy_import.lazy_module("wx.html", level = "base")
	lazy_import.lazy_module("wx.lib.wordwrap", level = "base")

def load(name):
	"""Lazy loads the given module.

	Example Input: load(numpy)
	"""

	if (isinstance(name, str)):
		return lazy_import.lazy_module(name)
	return tuple(lazy_import.lazy_module(item) for item in name)