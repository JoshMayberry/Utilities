import lazy_import

#Some lazy imports are turned off for now, because of: https://github.com/mnmelo/lazy_import/issues/10

_loadCatalogue = {
	"wx": (
		# "wx.adv", 
		# "wx.grid", 
		# "wx.html", 

		# "wx.lib.masked", 
		# "wx.lib.buttons", 
		# "wx.lib.dialogs", 
		# "wx.lib.newevent", 
		# "wx.lib.wordwrap", 
		# "wx.lib.splitter", 
		# "wx.lib.scrolledpanel", 
		# "wx.lib.mixins.listctrl", 

		# "wx.lib.agw.aui", 
		# "wx.lib.agw.flatmenu", 
		# "wx.lib.agw.floatspin", 
		# "wx.lib.agw.multidirdialog", 
		# "wx.lib.agw.fourwaysplitter", 
		# "wx.lib.agw.ultimatelistctrl", 
		# "wx.lib.agw.genericmessagedialog", 
	),

	"sqlalchemy": (
		"sqlalchemy_utils",
	),

	"serial": (
		"serial.tools.list_ports",
	),

	"email": (
		"email.encoders",
		"email.mime.base.MIMEBase",
		"email.mime.text.MIMEText",
		"email.mime.image.MIMEImage",
		"email.mime.multipart.MIMEMultipart",
	),

	"xml": (
		"xml.etree.cElementTree",
	),

	"ctypes": (
		"ctypes.windll",
	),

	"distutils": (
		"distutils.core.setup",
	),

	"Cryptodome": (
		"Cryptodome.Random", 
		"Cryptodome.Cipher.AES", 
		"Cryptodome.PublicKey.RSA", 
		"Cryptodome.Cipher.PKCS1_OAEP", 
	),

	"matplotlib": (
		"matplotlib.pyplot", 
	),

	"Utilities": (
		"Utilities.legal", 
		"Utilities.logger", 
		"Utilities.common", 
		"Utilities.caching", 
		"Utilities.wxPython", 
		"Utilities.debugging", 
		"Utilities.subProcess", 
		"Utilities.multiProcess", 
		"Utilities.threadManager", 
	),

	# "forks": (
	# 	{"name": "forks.pypubsub.src.pubsub.pub", "autoBase": False}
	# ),
}

_typical = (
	"re", "time", "math", "types", 
	"abc", "enum", "shutil", "decimal", "datetime", 
	"queue", "threading", "subprocess", 
	"typing", "inspect", "warnings", "traceback", 
	"operator", "itertools", "functools", "contextlib", "collections", 
)

def load(name = None, *moreNames, autoBase = True, useCatalogue = True, includeKey = True):
	"""Lazy loads the given module.

	name (str) - What module to lazy load
		- If None: Will load the list from '_typical'
		- If list: Will load all modules given in the list

	autoBase (bool) - Determines if the base is used instead of leaf for the import level
	useCatalogue (bool) - Determines if '_loadCatalogue' is consulted for extra imports
	includeKey (bool) - Determines if 'name' is included when using the catalogue

	Example Input: load("numpy")
	Example Input: load("numpy", "wx")
	Example Input: load(("numpy", "wx"))
	"""
	global _typical, _loadCatalogue

	def yieldModules():
		if (includeKey):
			yield lazy_import.lazy_module(name, level = ("leaf", "base")[autoBase])

		for item in load(_loadCatalogue[name], autoBase = autoBase, useCatalogue = useCatalogue):
			yield item

	#####################
	
	if (name is None):
		name = _typical

	if (moreNames):
		return load((name, *moreNames), autoBase = autoBase, useCatalogue = useCatalogue)

	if (not isinstance(name, str)):
		if (isinstance(name, dict)):
			return load(**name, autoBase = autoBase, useCatalogue = useCatalogue)
		return tuple(load(item, autoBase = autoBase, useCatalogue = useCatalogue) for item in name)

	if (useCatalogue and (name in _loadCatalogue)):
		return tuple(yieldModules())

	return lazy_import.lazy_module(name, level = ("leaf", "base")[autoBase])

load("Utilities")
