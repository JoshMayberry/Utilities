import wx
import wx.html
import wx.lib.wordwrap
import wx.lib.newevent
import wx.lib.mixins.listctrl

import re
import sys
import math
import types

import warnings
import operator
import functools
import contextlib

import PIL

import MyUtilities.legal
import MyUtilities.common

NULL = MyUtilities.common.NULL	

class NoActiveWindowError(Exception):
	pass

def wrap_skipEvent(includeSelf = True):
	def decorator(function):
		@functools.wraps(function)
		def wrapper(self, event = None, *args, **kwargs):
			"""Ensures the event gets skipped.

			Example Usage: @wrap_skipEvent()
			"""

			try:
				# if (isinstance(function, types.MethodType)):
				if (includeSelf):
					return function(self, event, *args, **kwargs)
				else:
					return function(event, *args, **kwargs)

			finally:
				if (event is not None):
					event.Skip()

		return wrapper
	return decorator

@contextlib.contextmanager
def asCM(function, *args, **kwargs):
	"""Used to build with wxWidgets as context managers to help organize code."""

	yield function(*args, **kwargs)

#Converters
def _convertImageToBitmap(imgImage):
	"""Converts a wxImage image (wxPython) to a wxBitmap image (wxPython).
	Adapted from: https://wiki.wxpython.org/WorkingWithImages

	imgImage (object) - The wxBitmap image to convert

	Example Input: _convertImageToBitmap(image)
	"""

	bmpImage = imgImage.ConvertToBitmap()
	return bmpImage

def _convertBitmapToImage(bmpImage):
	"""Converts a wxBitmap image (wxPython) to a wxImage image (wxPython).
	Adapted from: https://wiki.wxpython.org/WorkingWithImages

	bmpImage (object) - The wxBitmap image to convert

	Example Input: _convertBitmapToImage(image)
	"""

	#Determine if a static bitmap was given
	classType = bmpImage.GetClassName()
	if (classType == "wxStaticBitmap"):
		bmpImage = bmpImage.GetBitmap()

	imgImage = bmpImage.ConvertToImage()
	return imgImage

def _convertImageToPil(imgImage):
	"""Converts a wxImage image (wxPython) to a PIL image (pillow).
	Adapted from: https://wiki.wxpython.org/WorkingWithImages

	imgImage (object) - The wxImage image to convert

	Example Input: _convertImageToPil(image)
	"""

	pilImage = PIL.Image.new("RGB", (imgImage.GetWidth(), imgImage.GetHeight()))
	pilImage.fromstring(imgImage.GetData())
	return pilImage

def _convertBitmapToPil(bmpImage):
	"""Converts a wxBitmap image (wxPython) to a PIL image (pillow).
	Adapted from: https://wiki.wxpython.org/WorkingWithImages

	bmpImage (object) - The wxBitmap image to convert

	Example Input: _convertBitmapToPil(image)
	"""

	imgImage = _convertBitmapToImage(bmpImage)
	pilImage = _convertImageToPil(imgImage)
	return pilImage

def _convertPilToImage(pilImage, alpha = False):
	"""Converts a PIL image (pillow) to a wxImage image (wxPython).
	Adapted from: https://wiki.wxpython.org/WorkingWithImages

	pilImage (object) - The PIL image to convert
	alpha (bool)      - If True: The image will preserve any alpha chanels

	Example Input: _convertPilToImage(image)
	Example Input: _convertPilToImage(image, True)
	"""

	imgImage = wx.Image(pilImage.size[0], pilImage.size[1])

	hasAlpha = pilImage.mode[-1] == 'A'
	if (hasAlpha and alpha):
		pilImageCopyRGBA = pilImage.copy()
		pilImageRgbData = pilImageCopyRGBA.convert("RGB").tobytes()
		imgImage.SetData(pilImageRgbData)
		imgImage.SetAlpha(pilImageCopyRGBA.tobytes()[3::4])

	else:
		pilImage = pilImage.convert("RGB").tobytes()
		imgImage.SetData(pilImage)

	return imgImage

def _convertPilToBitmap(pilImage, alpha = False):
	"""Converts a PIL image (pillow) to a wxBitmap image (wxPython).
	Adapted from: https://wiki.wxpython.org/WorkingWithImages

	pilImage (object) - The PIL image to convert
	alpha (bool)      - If True: The image will preserve any alpha chanels

	Example Input: _convertPilToBitmap(image)
	"""

	imgImage = _convertPilToImage(pilImage, alpha)
	bmpImage = _convertImageToBitmap(imgImage)
	return bmpImage

class Converters():
	@classmethod
	def _convertImageToBitmap(cls, *args, **kwargs):
		return _convertImageToBitmap(*args, **kwargs)
		
	@classmethod
	def _convertBitmapToImage(cls, *args, **kwargs):
		return _convertBitmapToImage(*args, **kwargs)
		
	@classmethod
	def _convertImageToPil(cls, *args, **kwargs):
		return _convertImageToPil(*args, **kwargs)
		
	@classmethod
	def _convertBitmapToPil(cls, *args, **kwargs):
		return _convertBitmapToPil(*args, **kwargs)
		
	@classmethod
	def _convertPilToImage(cls, *args, **kwargs):
		return _convertPilToImage(*args, **kwargs)
		
	@classmethod
	def _convertPilToBitmap(cls, *args, **kwargs):
		return _convertPilToBitmap(*args, **kwargs)

#Settings
def getItemMod(flags = None, stretchable = True, border = 5):
	"""Returns modable item attributes, stretchability, and border.

	flags (list) - Which flag to add to the sizer
		How the sizer item is aligned in its cell.
		"ac" (str) - Align the item to the center
		"av" (str) - Align the item to the vertical center only
		"ah" (str) - Align the item to the horizontal center only
		"at" (str) - Align the item to the top
		"ab" (str) - Align the item to the bottom
		"al" (str) - Align the item to the left
		"ar" (str) - Align the item to the right

		Which side(s) the border width applies to.
		"ba" (str) - Border the item on all sides
		"bt" (str) - Border the item to the top
		"bb" (str) - Border the item to the bottom
		"bl" (str) - Border the item to the left
		"br" (str) - Border the item to the right

		Whether the sizer item will expand or change shape.
		"ex" (str) - Item expands to fill as much space as it can
		"ea" (str) - Item expands, but maintain aspect ratio
		"fx" (str) - Item will not change size when the window is resized
		"fh" (str) - Item will still take up space, even if hidden

		These are some common combinations of flags.
		"c1" (str) - "ac", "ba", and "ex"
		"c2" (str) - "ba" and "ex"
		"c3" (str) - "ba" and "ea"
		"c4" (str) - "al", "bl", "br"

	stretchable (bool) - Whether or not the item will grow and shrink with respect to a parent sizer
	border (int)       - The width of the item's border

	Example Input: getItemMod("ac")
	Example Input: getItemMod("ac", border = 10)
	Example Input: getItemMod("c1")
	"""

	#Determine the flag types
	fixedFlags = ""
	if (flags is not None):
		#Ensure that 'flags' is a list
		if (not isinstance(flags, list)):
			flags = [flags]

		#Evaluate each flag
		for flag in flags:
			flag = flag.lower()
			##Typical combinations
			if (flag[0] == "c"):
				#Align to center, Border all sides, expand to fill space
				if (flag[1] == "1"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_CENTER|wx.ALL|wx.EXPAND"

				#Border all sides, expand to fill space
				elif (flag[1] == "2"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALL|wx.EXPAND"

				#Border all sides, expand to fill space while maintaining aspect ratio
				elif (flag[1] == "3"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALL|wx.SHAPED"

				#Align to left, Border left and right side
				elif (flag[1] == "4"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_LEFT|wx.LEFT|wx.RIGHT"

				#Unknown Action
				else:
					errorMessage = f"Unknown combination flag {flag}"
					raise ValueError(errorMessage)

			##Align the Item
			elif (flag[0] == "a"):
				#Center 
				if (flag[1] == "c"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_CENTER"

				#Center Vertical
				elif (flag[1] == "v"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_CENTER_VERTICAL"

				#Center Horizontal
				elif (flag[1] == "h"):
					fixedFlags += "wx.ALIGN_CENTER_HORIZONTAL"
					
				#Top
				elif (flag[1] == "t"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_TOP"
					
				#Bottom
				elif (flag[1] == "b"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_BOTTOM"
					
				#Left
				elif (flag[1] == "l"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_LEFT"
					
				#Right
				elif (flag[1] == "r"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALIGN_RIGHT"

				#Unknown Action
				else:
					errorMessage = f"Unknown alignment flag {flag}"
					raise ValueError(errorMessage)

			##Border the Item
			elif (flag[0] == "b"):
				#All
				if (flag[1] == "a"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.ALL"
					
				#Top
				elif (flag[1] == "t"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.TOP"
					
				#Bottom
				elif (flag[1] == "b"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.BOTTOM"
					
				#Left
				elif (flag[1] == "l"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.LEFT"
					
				#Right
				elif (flag[1] == "r"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.RIGHT"

				#Unknown Action
				else:
					errorMessage = f"Unknown border flag {flag}"
					raise ValueError(errorMessage)

			##Expand the Item
			elif (flag[0] == "e"):
				#Expand
				if (flag[1] == "x"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.EXPAND"
					
				#Expand with Aspect Ratio
				elif (flag[1] == "a"):
					if (fixedFlags != ""):
						fixedFlags += "|"
					fixedFlags += "wx.SHAPED"

				#Unknown Action
				else:
					errorMessage = f"Unknown expand flag {flag}"
					raise ValueError(errorMessage)

			##Fixture the Item
			elif (flag[0] == "f"):
				#Fixed Size
				if (flag[1] == "x"):
					fixedFlags += "wx.FIXED_MINSIZE"
					
				#Fixed Space when hidden
				elif (flag[1] == "h"):
					fixedFlags += "wx.RESERVE_SPACE_EVEN_IF_HIDDEN"

				#Unknown Action
				else:
					errorMessage = f"Unknown fixture flag {flag}"
					raise ValueError(errorMessage)

			##Unknown Action
			else:
				errorMessage = f"Unknown flag {flag}"
				raise ValueError(errorMessage)
	else:
		fixedFlags = "0"

	#Determine stretchability
	if (stretchable):
		position = 1
	else:
		position = 0

	return fixedFlags, position, border

imageCatalogue = {
	"lightBulb": 	wx.ART_TIP, 				#A yellow light bulb with a '!' in it
	"question2": 	wx.ART_HELP, 				#A white speach bubble with a '?' in it. Looks different from "question"
	"error": 		wx.ART_ERROR, 				#A red circle with an 'x' in it
	"warning": 		wx.ART_WARNING, 			#A yellow yield sign with a '!' in it
	"question": 	wx.ART_QUESTION, 			#A white speach bubble with a '?' in it
	"info": 		wx.ART_INFORMATION, 		#A white circle with an 'i' in it
	
	"arrowLeft": 	wx.ART_GO_BACK, 			#A white arrow pointing left
	"arrowRight": 	wx.ART_GO_FORWARD, 			#A white arrow pointing right
	"arrowUp": 		wx.ART_GO_UP, 				#A white arrow pointing up
	"arrowDown": 	wx.ART_GO_DOWN, 			#A white arrow pointing down
	"arrowCurve": 	wx.ART_GO_TO_PARENT, 		#A white arrow that moves left and then up
	"first": 		wx.ART_GOTO_FIRST, 			#
	"last": 		wx.ART_GOTO_LAST, 			#
	"home": 		wx.ART_GO_HOME, 			#A white house
	
	"plus": 		wx.ART_PLUS, 				#
	"minus": 		wx.ART_MINUS, 				#
	"markX": 		wx.ART_CROSS_MARK, 			#A black 'X'
	"markCheck": 	wx.ART_TICK_MARK, 			#A black check mark
	
	"quit": 		wx.ART_QUIT, 				#A door opening to the left with a green arrow coming out of it to the right
	"close": 		wx.ART_CLOSE, 				#
	"delete": 		wx.ART_DELETE, 				#"markX" in a different style
	
	"print": 		wx.ART_PRINT, 				#A printer
	"font": 		wx.ART_HELP_SETTINGS, 		#A times new roman 'A'
	"book": 		wx.ART_HELP_BOOK, 			#A blue book with white pages
	
	"open": 		wx.ART_FILE_OPEN, 			#"folderOpen" with a green arrow curiving up and then down inside it
	"save": 		wx.ART_FILE_SAVE, 			# A blue floppy disk
	"saveAs": 		wx.ART_FILE_SAVE_AS, 		#"save" with a yellow spark in the top right corner
	"diskHard": 	wx.ART_HARDDISK, 			#
	"diskFloppy": 	wx.ART_FLOPPY, 				#
	"diskCd": 		wx.ART_CDROM, 				#

	"copy": 		wx.ART_COPY, 				#Two "page" stacked on top of each other with a southeast offset
	"cut": 			wx.ART_CUT, 				#A pair of open scissors with red handles
	"paste": 		wx.ART_PASTE, 				#A tan clipboard with a blank small version of "page2" overlapping with an offset to the right
	"undo": 		wx.ART_UNDO, 				#A blue arrow that goes to the right and turns back to the left
	"redo": 		wx.ART_REDO, 				#A blue arrow that goes to the left and turns back to the right
	
	"folder": 		wx.ART_FOLDER, 				#A blue folder
	"folderNew": 	wx.ART_NEW_DIR, 			#"folder" with a yellow spark in the top right corner
	"folderOpen": 	wx.ART_FOLDER_OPEN, 		#An opened version of "folder"
	"folderUp": 	wx.ART_GO_DIR_UP, 			#"folderOpen" with a green arrow pointing up inside it
	"page": 		wx.ART_NORMAL_FILE, 		#A blue page with lines on it
	"page2": 		wx.ART_HELP_PAGE, 			#"page" in a different style
	"pageNew": 		wx.ART_NEW, 				#"page" with a green '+' in the top left corner
	"pageGear": 	wx.ART_EXECUTABLE_FILE, 	#"page" with a blue gear in the bottom right corner
	"pageTorn": 	wx.ART_MISSING_IMAGE, 		#A grey square with a white border torn in half lengthwise
	
	"find": 		wx.ART_FIND, 				#A magnifying glass
	"findReplace": 	wx.ART_FIND_AND_REPLACE, 	#"find" with a double sided arrow in the bottom left corner pointing left and right
	
	"addBookmark": 	wx.ART_ADD_BOOKMARK, 		#A green banner with a '+' by it
	"delBookmark": 	wx.ART_DEL_BOOKMARK, 		#A red banner with a '-' by it
	"sidePanel": 	wx.ART_HELP_SIDE_PANEL, 	#A grey box with lines in with a white box to the left with arrows pointing left and right
	"viewReport": 	wx.ART_REPORT_VIEW, 		#A white box with lines in it with a grey box with lines in it on top
	"viewList": 	wx.ART_LIST_VIEW, 			#A white box with squiggles in it with a grey box with dots in it to the left
	}
def getImage(imagePath, internal = False, *, alpha = True, 
	scale = None, rotate = None, mask = None, returnIcon = False, 
	rotateColor = None, maskColor = None, returnForNone = wx.NullBitmap):
	"""Returns a wxBitmap.

	imagePath (str) - Where the image is on the computer
		- If None: Will return 'returnForNone'
		- If (PIL.Image): Will use the given pillow image

	internal (bool) - Determines if 'imagePath' is interpreted as a file path or a key for 'imageCatalogue'
	alpha (bool) - Determines if existing alpha chanels will be preserved during the format process

	mask (str) - A path to the mask to use for the image
		- If None: No mask will be applied
		- If True: Will use 'image' as the mask file

	maskColor (wxColor) - What color to use for the mask

	Example Input: getImage("example.bmp")
	Example Input: getImage(image)
	Example Input: getImage("error", internal = True)
	Example Input: getImage(image, scale = 1.5)
	Example Input: getImage(image, scale = (32, 32))
	Example Input: getImage(image, rotate = 90)
	Example Input: getImage(image, mask = True)
	Example Input: getImage(image, returnForNone = lambda: getImage("error", internal = True))
	"""

	def applyImagePath(imagePath):
		if (not imagePath):
			if (callable(returnForNone)):
				return returnForNone()
			return returnForNone

		if (isinstance(imagePath, str)):
			if (internal):
				return wx.ArtProvider.GetBitmap(imageCatalogue.get(imagePath, wx.ART_ERROR))
			try:
				return wx.Bitmap(imagePath)
			except:
				return wx.Image(imagePath).ConvertToBitmap()

		if (PIL.Image.isImageType(imagePath)):
			return _convertPilToBitmap(imagePath, alpha)
		
		errorMessage = f"Unknown file type {type(imagePath)} for getImage()"
		raise KeyError(errorMessage)

	def applyScale(image):
		nonlocal scale

		if (scale is None):
			return image

		if (isinstance(scale, int)):
			scale = (scale, scale)

		if (isinstance(scale[0], float)):
			scale[0] = math.ceil(image.GetWidth() * scale[0])
		if (isinstance(scale[1], float)):
			scale[1] = math.ceil(image.GetHeight() * scale[1])
		
		return image.Scale(*scale)

	def applyRotate(image):
		nonlocal rotate, rotateColor

		if (rotate is None):
			return image

		image.SetMaskColour(*getColor(rotateColor, returnForNone = wx.WHITE).Get(includeAlpha = False))
		if (isinstance(rotate, (list, tuple))):
			rotate = rotate[0]
			center = rotate[1]
		else:
			center = (image.GetWidth() / 2, image.GetHeight() / 2)

		return image.Rotate(math.radians(rotate), center)

	def applyMask(bitmap):
		nonlocal mask

		def getMask():
			nonlocal bitmap, mask, maskColor

			if (isinstance(mask, wx.Mask)):
				return mask

			if (isinstance(mask, bool)):
				if (not mask):
					return

				return wx.Mask(bitmap, getColor(maskColor, returnForNone = wx.BLACK))

		########################

		if (mask is None):
			return bitmap

		bitmapMask = getMask()
		if (bitmapMask is None):
			return bitmap

		bitmap.SetMask(bitmapMask)
		return bitmap

	#####################################################

	bitmap = applyImagePath(imagePath)

	if ((scale is not None) or (rotate is not None)):
		image = bitmap.ConvertToImage()
		image = applyScale(image)
		image = applyRotate(image)
		bitmap = image.ConvertToBitmap()

	bitmap = applyMask(bitmap)

	if (returnIcon):
		return wx.Icon(bitmap)
	return bitmap

def yieldColor(colorList, *, returnForNone = wx.NullColour):
	"""Yields wxColor objects.

	colorList (str) - What color to return
		- If tuple: Will interperet as (Red, Green, Blue). Values can be integers from 0 to 255 or floats from 0.0 to 1.0

	Example Input: yieldColor("white")
	Example Input: yieldColor((255, 255, 0))
	Example Input: yieldColor((0.5, 0.5, 0.5))
	Example Input: yieldColor((255, 0.5, 0))
	"""

	def formatColor(color):
		for element in color:
			#Ensure numbers are between 0 and 255
			if (isinstance(element, float)):
				yield min(255, max(0, math.ceil(element * 255)))
			else:
				yield min(255, max(0, element))

	##############################

	for color in MyUtilities.common.ensure_container(colorList, elementCriteria = ((3, int), (4, int)), convertNone = False):
		if (color is None):
			for item in yieldColor(returnForNone):
				yield item
			continue

		if (isinstance(color, wx.Colour)):
			yield color
			continue

		if (isinstance(color, str)):
			colorHandle = wx.Colour(color)
			if (colorHandle.IsOk()):
				yield colorHandle
				continue

			wx.lib.colourdb.updateColourDB()
			yield wx.Colour(color)
			continue

		if (not isinstance(color, (list, tuple, range))):
			errorMessage = f"'color' must be a tuple or string, not a {type(color)}"
			raise ValueError(errorMessage)
		
		if (len(color) != 3):
			errorMessage = f"'color' must have a length of three, not {len(color)}"
			raise ValueError(errorMessage)

		yield wx.Colour(*formatColor(color))
	
def getColor(*args, forceTuple = False, **kwargs):
	"""Returns a wxColor object.

	color (str) - What color to return
		- If tuple: Will interperet as (Red, Green, Blue). Values can be integers from 0 to 255 or floats from 0.0 to 1.0

	Example Input: getColor("white")
	Example Input: getColor((255, 255, 0))
	Example Input: getColor((0.5, 0.5, 0.5))
	Example Input: getColor((255, 0.5, 0))
	"""

	answer = tuple(yieldColor(*args, **kwargs))

	if (forceTuple):
		return answer
	if (len(answer) == 1):
		return answer[0]
	return answer

fontCatalogue = {
	"bold": {
		True: wx.BOLD,
		False: wx.NORMAL,
		None: wx.LIGHT,
	},
	"italic": {
		True: wx.ITALIC,
		False: wx.NORMAL,
		None: wx.SLANT,
	},
	"family": {
		"TimesNewRoman": wx.ROMAN,
		None: wx.DEFAULT
	},
}
def getFont(size = NULL, font = None, *, bold = NULL, italic = NULL, family = NULL, underline = NULL, strikethrough = NULL):
	"""Returns a wxFont object.
	Can modify an existing wxFont object.

	size (int)    - The font size of the text in points
		- If Tuple: Uses in pixels instead of points
	bold (bool)   - Determines the boldness of the text
		- If True: The font will be bold
		- If False: The font will be normal
		- If None: The font will be light
	italic (bool) - Determines the italic state of the text
		- If True: The font will be italicized
		- If False: The font will not be italicized
		- If None: The font will be slanted
	family (str)  - What font family it is.
		~ "times new roman"

	Example Input: getFont()
	Example Input: getFont(size = 72, bold = True, color = "red")
	Example Input: getFont(size = (32, 32), bold = True, color = "red")
	"""

	def _getSize(_size):
		if (_size in (None, NULL)):
			return wx.DEFAULT

		if (isinstance(_size, (int, wx.Size))):
			return _size

		return wx.Size(*_size)

	def _getUnderline(_underline):
		return MyUtilities.common.ensure_default(_underline, default = False, defaultFlag = NULL)

	def _getStrikethrough(_strikethrough):
		return MyUtilities.common.ensure_default(_strikethrough, default = False, defaultFlag = NULL)

	def _getBold(_bold):
		return fontCatalogue["bold"].get(MyUtilities.common.ensure_default(_bold, default = False, defaultFlag = NULL), wx.NORMAL)

	def _getFamily(_family):
		return fontCatalogue["family"].get(MyUtilities.common.ensure_default(_family, default = None, defaultFlag = NULL), wx.DEFAULT)

	def _getItalic(_italic):
		return fontCatalogue["italic"].get(MyUtilities.common.ensure_default(_italic, default = False, defaultFlag = NULL), wx.NORMAL)

	def _getFont():
		nonlocal font

		if (font is None):
			return wx.Font(_getSize(size), _getFamily(family), _getItalic(italic), _getBold(bold))
		_font = wx.Font(font)

		if (size is not NULL):
			_font.SetPointSize(_size)

		if (family is not NULL):
			_font.SetFamily(_family)

		if (bold is not NULL):
			_font.SetWeight(_bold)

		if (italic is not NULL):
			_font.SetStyle(_italic)

		return _font

	#############################################

	_font = _getFont()

	_font.SetUnderlined(_getUnderline(underline))
	_font.SetStrikethrough(_getStrikethrough(strikethrough))

	return _font

def getWildcard(wildcard = None):
	"""Returns a formatted file picker wildcard.

	Example Input: getWildcard()
	Example Input: getWildcard(wildcard)
	"""

	def yieldText():
		nonlocal wildcard

		if (wildcard is None):
			yield "All files (*.*)|*.*"
			return

		for catalogue in MyUtilities.common.ensure_container(wildcard):
			for key, valueList in MyUtilities.common.ensure_dict(catalogue, useAsKey = None).items():
				fileTypes = "; ".join(f"*.{value}" if (value is not None) else "*.*" for value in MyUtilities.common.ensure_container(valueList))
				if (key is not None):
					yield f"{key} ({fileTypes})|{fileTypes}"
					continue

				if (fileTypes == "*.*"):
					yield f"All Files (*.*)|*.*"
					continue

				yield f"{fileTypes}|{fileTypes}"

	###########################

	return '|'.join(yieldText())

def autoRun(delay = None, *args, **kwargs):
	"""Automatically runs the provided function.

	delay (int)       - How many milliseconds to wait before the function is executed

	Example Input: autoRun(0, self.startupFunction)
	Example Input: autoRun(5000, myFrame.switchWindow, [0, 1])
	"""

	for function, functionArgs, functionKwargs in MyUtilities.common.ensure_functionInput(*args, **kwargs):
		if (not delay):
			wx.CallAfter(function, *functionArgs, **functionKwargs)
		else:
			wx.CallLater(delay, function, *functionArgs, **functionKwargs)

def threadSafe(function, *args, **kwargs):
	"""Ensures that this function runs in the main thread."""

	if (wx.IsMainThread()):
		return function(*args, **kwargs)
	wx.CallAfter(function, *args, **kwargs)

#Event Functions
myEventCatalogue = {}
def _makeBinder(cls, *, useId = True, returnEvent = False, returnBinder = False, **kwargs):
	"""Creates an event binder for this event."""
	global myEventCatalogue

	if (useId):
		event, binder = wx.lib.newevent.NewCommandEvent(**kwargs)
	else:
		event, binder = wx.lib.newevent.NewEvent(**kwargs)

	myEventCatalogue[cls] = binder

	if (returnEvent):
		if (returnBinder):
			return event, binder
		return event
	elif (returnBinder):
		return binder

class MyEvent(wx.PyCommandEvent, metaclass = MyUtilities.common.makeTracker(_makeBinder, skipFirst = True, extraClass = wx.PyCommandEvent)):
	"""Used to create my own events.
	Modified code from: ObjectListView.DOLVEvent.py

	Use: https://wiki.wxpython.org/CustomEventClasses
	Use: https://wxpython.org/Phoenix/docs/html/wx.lib.newevent.html

	Example Use:
		#Make event handler
		class EVT_FINISHED(MyEvent):
			def __init__(self, parent, **kwargs):
				super().__init__(self, parent, canVeto = True)

				self.page = kwargs.pop("page", None)
				self.wizard = kwargs.pop("wizard", None)

		#Bind event
		self._betterBind(self.EVT_FINISHED, self.thing, myFunction, mode = 2)

		#Trigger event manually
		self.triggerEvent(self.EVT_FINISHED, page = self.currentPage, wizard = self)

		#Trigger event from other event
		myWidget.setFunction_click(self.onTriggerEvent, myFunctionArgs = (self.EVT_FINISHED,))
		myWidget.setFunction_click(self.onTriggerEvent, myFunctionKwargs = {"eventType": self.EVT_FINISHED, "okFunction": self.hideWindow, "okFunctionKwargs": {"modalId": wx.ID_OK}})
	"""

	def __init__(self, source, parent, canVeto = False):
		global myEventCatalogue
		
		wx.PyCommandEvent.__init__(self, myEventCatalogue[source.__class__].typeId, -1)

		self.veto = False
		self.parent = parent
		self.canVeto = canVeto
		self.SetEventObject(parent.thing)

	def Veto(self, state = True):
		self.veto = state and self.canVeto

	def IsVetoed(self):
		return self.veto

class EventFunctions():
	"""Contains functions pertaining to manipulating events."""

	def __init__(self):
		self.boundEvents = []

	def onTriggerEvent(self, event, *args, **kwargs):
		"""A wxEvent version of triggerEvent().

		Example Use: myWidget.setFunction_click(self.onTriggerEvent, myFunctionArgs = (self.EVT_FINISHED,))
		Example Use: myWidget.setFunction_click(self.onTriggerEvent, myFunctionKwargs = {"eventType": self.EVT_FINISHED, "okFunction": self.hideWindow, "okFunctionKwargs": {"modalId": wx.ID_OK}})
		"""

		self.triggerEvent(*args, **kwargs)
		event.Skip()

	def triggerEvent(self, eventType = None, thing = None, *, returnEvent = False,
		okFunction = None, okFunctionArgs = None, okFunctionKwargs = None,
		vetoFunction = None, vetoFunctionArgs = None, vetoFunctionKwargs = None, **kwargs):
		"""Allows the user to easily trigger an event remotely.

		Example Input: triggerEvent(self, self.EVT_PAGE_CHANGED)
		Example Input: triggerEvent(self, self.EVT_PAGE_CHANGING, returnEvent = True, fromNode = self.currentNode, toNode = node)
		Example Input: triggerEvent(self, self.EVT_FINISHED, okFunction = self.hideWindow, okFunctionKwargs = {"modalId": wx.ID_OK})
		"""

		assert eventType
		newEvent = eventType(self, **kwargs)

		if (thing is None):
			thing = self.thing

		thing.GetEventHandler().ProcessEvent(newEvent)
		if (returnEvent):
			return newEvent

		if (newEvent.IsVetoed()):
			MyUtilities.common.runMyFunction(myFunction = vetoFunction, myFunctionArgs = vetoFunctionArgs, myFunctionKwargs = vetoFunctionKwargs)
			return False

		MyUtilities.common.runMyFunction(myFunction = okFunction, myFunctionArgs = okFunctionArgs, myFunctionKwargs = okFunctionKwargs)
		return True
				
	def _betterBind(self, eventType, thing, myFunction, myFunctionArgs = None, myFunctionKwargs = None, *, mode = 1, rebind = False, printError = True, **kwargs):
		"""Binds wxObjects in a better way.
		Inspired by: "Florian Bosch" on http://stackoverflow.com/questions/173687/is-it-possible-to-pass-arguments-into-event-bindings
		Special thanks for help on mult-functions to "Mike Driscoll" on http://stackoverflow.com/questions/11621833/how-to-bind-2-functions-to-a-single-event

		eventType (CommandEvent) - The wxPython event to be bound
		thing (wxObject)         - What is being bound to
		myFunctionList (str)     - The function that will be ran when the event occurs
		myFunctionArgs (list)    - Any input arguments for myFunction. A list of multiple functions can be given
		myFunctionKwargs (dict)  - Any input keyword arguments for myFunction. A dictionary of variables for each function can be given as a list. The index of the variables must be the same as the index for the functions 
		mode (int)               - Dictates how things are bound. Used for special cases
		rebind (bool)            - Will unbind the provided function (if it was already bound) from the 'thing' and then rebind it. Only works for non-argument functions
			- If True: Will rebind
			- If False: Will not rebind
			- If None: Will remove all previously bound functions
		_________________________________________________________________________

		MULTIPLE FUNCTION ORDER
		The functions are ran in the order given; from left to right.

		MULTIPLE FUNCTION FAILURE
		Make it a habbit to end all bound functions with 'event.Skip()'. 
		If the bound function does not end with 'event.Skip()', then it will overwrite a previously bound function.
		This will result in the new function being ran in place of both functions.
		_________________________________________________________________________

		Example Input: _betterBind(self, wx.EVT_BUTTON, menuItem, "self.onExit", "Extra Information")
		Example Input: _betterBind(self, wx.EVT_BUTTON, menuItem, ["self.toggleObjectWithLabel", "self.onQueueValue", ], [["myCheckBox", True], None])
		"""
		global MyEvent, myEventCatalogue

		def bind(myFunctionEvaluated, myFunctionArgs, myFunctionKwargs):
			"""This sub-function is needed to make the multiple functions work properly."""
			nonlocal self, eventType, thing, mode, rebind

			#Get the class type in order to bind the object to the correct thing
			thingClass = thing.GetClassName()

			##Determine how to bind the object
			if (thingClass == "wxWindow"):
				if (mode == 2):
					bindObject = thing
				else:
					bindObject = self.parent.thing

			elif (thingClass in ["wxMenuItem", "wxToolBarToolBase"]):
				bindObject = self.thing
			else:
				bindObject = thing

			#Account for rebinding
			if (rebind is None):
				bindObject.Unbind(eventType, source = thing)
			elif (rebind):
				if (mode == 1):
					unbound = bindObject.Unbind(eventType, handler = myFunctionEvaluated, source = thing)
				else:
					unbound = bindObject.Unbind(eventType, handler = myFunctionEvaluated)
				if ((not unbound) and printError):
					#If the lambda style function was used, this will not work
					warnings.warn(f"Unbinding function {myFunctionEvaluated} for {self.__repr__()} failed", Warning, stacklevel = 3)

			if ((not rebind) and (eventType in self.boundEvents)):
				self.boundEvents.remove(eventType)

			#Typical binding mode
			if (mode == 1):
				if ((len(myFunctionKwargs) == 0) and (len(myFunctionArgs) == 0)):
					bindObject.Bind(eventType, myFunctionEvaluated, thing)
				else:
					bindObject.Bind(eventType, lambda event: myFunctionEvaluated(event, *myFunctionArgs, **myFunctionKwargs), thing)

			#Binding mode for window key bindings
			elif (mode == 2):
				if ((len(myFunctionKwargs) == 0) and (len(myFunctionArgs) == 0)):
					bindObject.Bind(eventType, myFunctionEvaluated)
				else:
					bindObject.Bind(eventType, lambda event: myFunctionEvaluated(event, *myFunctionArgs, **myFunctionKwargs))

			else:
				errorMessage = f"Unknown mode {mode} for _betterBind()"
				raise TypeError(errorMessage)

			if (eventType not in self.boundEvents):
				self.boundEvents.append(eventType)

		##############################################################################################################################
		
		#Skip empty functions
		if (myFunction is None):
			return

		if (isinstance(eventType, type) and issubclass(eventType, MyEvent)):
			eventType = myEventCatalogue[eventType]

		for item in MyUtilities.common.ensure_functionInput(myFunction = myFunction, myFunctionArgs = myFunctionArgs, myFunctionKwargs = myFunctionKwargs, self = self, **kwargs):
			bind(*item)

class CommonFunctions():
	@classmethod
	def getItemMod(cls, *args, **kwargs):
		return getItemMod(*args, **kwargs)
		
	@classmethod
	def getImage(cls, *args, **kwargs):
		return getImage(*args, **kwargs)
		
	@classmethod
	def getColor(cls, *args, **kwargs):
		return getColor(*args, **kwargs)
		
	@classmethod
	def getFont(cls, *args, **kwargs):
		return getFont(*args, **kwargs)
		
	@classmethod
	def getWildcard(cls, *args, **kwargs):
		return getWildcard(*args, **kwargs)
		
	@classmethod
	def autoRun(cls, *args, **kwargs):
		return autoRun(*args, **kwargs)
		
	@classmethod
	def threadSafe(cls, *args, **kwargs):
		return threadSafe(*args, **kwargs)
		
	@classmethod
	def onBackgroundRun(cls, *args, self = None, **kwargs):
		return onBackgroundRun(*args, self = MyUtilities.common.ensure_default(self, cls), **kwargs)
	
def getPen(color, width = 1):
	"""Returns a pen or list of pens to the user.
	Pens are used to draw shape outlines.

	color (tuple) - (R, G, B) as integers
				  - If a list of tuples is given: A brush for each color will be created
	width (int)   - How thick the pen will be

	Example Input: getPen((255, 0, 0))
	Example Input: getPen((255, 0, 0), 3)
	"""

	return wx.Pen(getColor(color), int(width))

def getBrush(color, style = "solid", image = None, internal = False):
	"""Returns a pen or list of pens to the user.
	Brushes are used to fill shapes

	color (tuple)  - (R, G, B) as integers
					 If None: The fill will be transparent (no fill)
				   - If a list of tuples is given: A brush for each color will be created
	style (str)    - If not None: The fill style
				   - If a list is given: A brush for each style will be created
	image (str)    - If 'style' has "image" in it: This is the image that is used for the bitmap. Can be a PIL image
	internal (str) - If True and 'style' has "image" in it: 'image' is an iternal image

	Example Input: getBrush((255, 0, 0))
	Example Input: getBrush([(255, 0, 0), (0, 255, 0)])
	Example Input: getBrush((255, 0, 0), style = "hatchCross)
	Example Input: getBrush([(255, 0, 0), (0, 255, 0)], ["hatchCross", "solid"])
	Example Input: getBrush(None)
	Example Input: getBrush([(255, 0, 0), None])
	"""

	#Account for void color
	if (color is None):
		color = wx.Colour(0, 0, 0)
		style, image = getBrushStyle("transparent", None)
		brush = wx.Brush(color, style)

	else:
		#Account for brush lists
		multiple = [False, False]
		if (isinstance(color, (tuple, list)) and isinstance(color[0], (tuple, list))):
			multiple[0] = True

		if (isinstance(style, (tuple, list))):
			multiple[1] = True

		#Create a brush list
		if (multiple[0] or multiple[1]):
			brushList = []
			for i, item in enumerate(color):
				#Determine color
				if (multiple[0]):
					#Account for void color
					if (color[i] is not None):
						color = wx.Colour(color[i][0], color[i][1], color[i][2])
					else:
						color = wx.Colour(0, 0, 0)
				else:
					#Account for void color
					if (color is not None):
						color = wx.Colour(color[0], color[1], color[2])
					else:
						color = wx.Colour(0, 0, 0)

				#Determine style
				if (multiple[1]):
					#Account for void color
					if (color[i] is not None):
						style, image = getBrushStyle(style[i], image)
					else:
						style, image = getBrushStyle("transparent", None)
				else:
					#Account for void color
					if (color is not None):
						style, image = getBrushStyle(style, image)
					else:
						style, image = getBrushStyle("transparent", None)

				#Create bruh
				brush = wx.Brush(color, style)

				#Bind image if an image style was used
				if (image is not None):
					brush.SetStipple(image)

				#Remember the brush
				brushList.append(brush)
			brush = brushList

		#Create a single brush
		else:
			#Account for void color
			if (color is not None):
				#Create brush
				color = wx.Colour(color[0], color[1], color[2])
				style, image = getBrushStyle(style, image)
			else:
				color = wx.Colour(0, 0, 0)
				style, image = getBrushStyle("transparent", None)
			brush = wx.Brush(color, style)

			#Bind image if an image style was used
			if (image is not None):
				brush.SetStipple(image)

	return brush

def getBrushStyle(style, image = None, internal = False):
	"""Returns a brush style to the user.

	style (str) - What style the shape fill will be. Only some of the letters are needed. The styles are:
		'solid'       - Solid. Needed: "s"
		'transparent' - Transparent (no fill). Needed: "t"

		'image'                - Uses a bitmap as a stipple. Needed: "i"
		'imageMask'            - Uses a bitmap as a stipple; a mask is used for masking areas in the stipple bitmap. Needed: "im"
		'imageMaskTransparent' - Uses a bitmap as a stipple; a mask is used for blitting monochrome using text foreground and background colors. Needed: "it"

		'hatchHorizontal'   - Horizontal hatch. Needed: "hh"
		'hatchVertical'     - Vertical hatch. Needed: "hv"
		'hatchCross'        - Cross hatch. Needed: "h"
		'hatchDiagForward'  - Forward diagonal hatch. Needed: "hdf" or "hfd"
		'hatchDiagBackward' - Backward diagonal hatch. Needed: "hdb" or "hbd"
		'hatchDiagCross'    - Cross-diagonal hatch. Needed: "hd"

	image (str)    - If 'style' has "image" in it: This is the image that is used for the bitmap. Can be a PIL image
	internal (str) - If True and 'style' has "image" in it: 'image' is an iternal image

	Example Input: getBrushStyle("solid")
	Example Input: getBrushStyle("image", image)
	Example Input: getBrushStyle("image", "example.bmp")
	Example Input: getBrushStyle("image", "error", True)
	"""

	#Ensure lower case
	if (style is not None):
		style = style.lower()

	#Normal
	if (style is None):
		style = wx.BRUSHSTYLE_SOLID
		image = None

	elif (style[0] == "s"):
		style = wx.BRUSHSTYLE_SOLID
		image = None

	elif (style[0] == "t"):
		style = wx.BRUSHSTYLE_TRANSPARENT
		image = None

	#Bitmap
	elif (style[0] == "i"):
		#Make sure an image was given
		if (image is not None):
			#Ensure correct image format
			image = getImage(imagePath, internal)

			#Determine style
			if ("t" in style):
				style = wx.BRUSHSTYLE_STIPPLE_MASK_OPAQUE

			elif ("m" in style):
				style = wx.BRUSHSTYLE_STIPPLE_MASK

			else:
				style = wx.BRUSHSTYLE_STIPPLE
		else:
			warnings.warn(f"Must supply an image path in getBrushStyle() to use the style {style}", Warning, stacklevel = 2)
			style = wx.BRUSHSTYLE_TRANSPARENT

	#Hatch
	elif (style[0] == "h"):
		#Diagonal
		if ("d" in style):
			if ("f" in style):
				style = wx.BRUSHSTYLE_FDIAGONAL_HATCH

			elif ('b' in style):
				style = wx.BRUSHSTYLE_BDIAGONAL_HATCH

			else:
				style = wx.BRUSHSTYLE_CROSSDIAG_HATCH
		else:
			if ("h" in style[1:]):
				style = wx.BRUSHSTYLE_HORIZONTAL_HATCH

			elif ('v' in style):
				style = wx.BRUSHSTYLE_VERTICAL_HATCH

			else:
				style = wx.BRUSHSTYLE_CROSS_HATCH
		image = None

	else:
		warnings.warn(f"Unknown style {style} in getBrushStyle()", Warning, stacklevel = 2)
		style = wx.BRUSHSTYLE_TRANSPARENT
		image = None

	return style, image

_alignCatalogue = {
	"x": {
		"left": wx.ALIGN_LEFT, 
		"right": wx.ALIGN_RIGHT, 
		"center": wx.ALIGN_CENTER_HORIZONTAL,
	},
	"y": {
		"top": wx.ALIGN_TOP, 
		"bottom": wx.ALIGN_BOTTOM, 
		"center": wx.ALIGN_CENTER_VERTICAL,
	},
}
def _drawText(dc, text, *, x = 0, y = 0, x_offset = 0, y_offset = 0, angle = None, 
	color = None, isSelected = False, isEnabled = True, 
	wrap = None, align = None, x_align = None, y_align = None, **fontKwargs):
	"""Draws text on the canvas.
	Special thanks to Milan Skala for how to center text on http://wxpython-users.1045709.n5.nabble.com/Draw-text-over-an-existing-bitmap-td5725527.html

	text (str)    - The text that will be drawn on the canvas
	x (int)       - The x-coordinate of the text on the canvas
	y (int)       - The y-coordinate of the text on the canvas
	angle (int)   - If not None: The angle in degrees that the text will be rotated. Positive values rotate it counter-clockwise
	color (tuple) - (R, G, B) as integers

	wrap (int)    - How far to draw the text until; it wraps back at 'x'
		- If rect or tuple: Will use the width of the given rectangle
		- If None or 0: Will not wrap the text

	align (tuple) - How far from (0, 0) to consider the bottom right corner

	x_align (str) - Where the text should be aligned in the cell
		~ "left", "right", "center"
		- If None: No alignment will be done
		- Note: Must define 'align' to use

	y_align (str) - Where the button should be aligned with respect to the x-axis in the cell
		~ "top", "bottom", "center"
		- If None: Will use "center"
		- Note: Must define 'align' to use

	Example Input: _drawText(dc, "Lorem Ipsum")
	Example Input: _drawText(dc, "Lorem Ipsum", 5, 5)
	Example Input: _drawText(dc, "Lorem Ipsum", 5, 5, 10)
	Example Input: _drawText(dc, "Lorem Ipsum", 5, 5, 10, 45)
	Example Input: _drawText(dc, "Lorem Ipsum", 5, 5, color = (255, 0, 0))

	Example Input: _drawText(dc, "Lorem Ipsum", wrap = 10)
	Example Input: _drawText(dc, "Lorem Ipsum", wrap = (0, 10, 275, 455))
	Example Input: _drawText(dc, "Lorem Ipsum", align = (0, 10, 275, 455), x_align = "center")
	Example Input: _drawText(dc, "Lorem Ipsum", align = (0, 10, 275, 455), x_align = "center", angle = 90)
	"""
	global _alignCatalogue

	def _getColor():
		nonlocal color

		if (color is not None):
			return getColor(color)
		
		if (not isEnabled):
			return wx.SystemSettings.GetColour(wx.SYS_COLOUR_GRAYTEXT)
		
		if (isSelected):
			#Use: https://wxpython.org/Phoenix/docs/html/wx.SystemColour.enumeration.html
			return wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHTTEXT)
		
		return wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNTEXT)

	def _getPosition():
		nonlocal dc, angle, align

		if ((align is None) or (angle in (None, 0))):
			return x + x_offset, y + y_offset

		def _get_x():
			nonlocal x_align, width, height

			if (x_align in (None, "left")):
				_x = 0
				if (angle >= 270):
					return _x + x_offset + height
				if (angle >= 180):
					return _x + x_offset + width
				if (angle >= 90):
					return _x + x_offset + 0
				return _x + x_offset + 0

			if (x_align == "right"):
				_x = align.width - width
				if (angle >= 270):
					return _x + x_offset + width
				if (angle >= 180):
					return _x + x_offset + width
				if (angle >= 90):
					return _x + x_offset + width - height
				return _x + x_offset + 0
			
			_x = (align.width - width) / 2
			if (angle >= 270):
				return _x + x_offset + width / 2 + height / 2
			if (angle >= 180):
				return _x + x_offset + width
			if (angle >= 90):
				return _x + x_offset + width / 2 - height / 2
			return _x + x_offset + 0

		def _get_y():
			nonlocal y_align, width, height

			if (y_align in (None, "top")):
				_y = 0
				if (angle >= 270):
					return _y + y_offset + 0
				if (angle >= 180):
					return _y + y_offset + height
				if (angle >= 90):
					return _y + y_offset + width
				return _y + y_offset + 0

			if (y_align == "bottom"):
				_y = align.height - height
				if (angle >= 270):
					return _y + y_offset + -width + height
				if (angle >= 180):
					return _y + y_offset + height
				if (angle >= 90):
					return _y + y_offset + height
				return _y + y_offset + 0

				_y = (align.height - height) / 2
				if (angle >= 270):
					return _y + y_offset + -width / 2 + height / 2
				if (angle >= 180):
					return _y + y_offset + height
				if (angle >= 90):
					return _y + y_offset + width / 2 + height / 2
				return _y + y_offset + 0

		######################

		align = wx.Rect(align)
		width, height = dc.GetTextExtent(_text)

		return _get_x(), _get_y()

	def applyWrap():
		nonlocal text, wrap

		if ((wrap is not None) and (not isinstance(wrap, int))):
			wrap = wx.Rect(wrap)
		if (wrap):
			if (isinstance(wrap, int)):
				return wx.lib.wordwrap.wordwrap(text, dc.DeviceToLogicalX(wrap), dc)
			else:
				return wx.lib.wordwrap.wordwrap(text, dc.DeviceToLogicalX(wrap[2] - wrap[0]), dc)
		return text

	######################################################

	oldColor = dc.GetTextForeground()
	oldFont = dc.GetFont()
	try:
		dc.SetFont(getFont(**fontKwargs))
		dc.SetTextForeground(_getColor())

		_x, _y = _getPosition()
		_text = applyWrap()

		if (angle not in (None, 0)):
			dc.DrawRotatedText(_text, _x, _y, angle)
		elif (align is None):
			dc.DrawText(_text, _x, _y)
		else:
			dc.DrawLabel(_text, (_x + align[0], _y + align[1], align[2], align[3]), alignment = _alignCatalogue.get(x_align, 0)|_alignCatalogue.get(y_align, wx.ALIGN_TOP))

	finally:
		dc.SetFont(oldFont)
		dc.SetTextForeground(oldColor)

def _drawBackground(dc, rectangle, isSelected, color = None):
	"""Draw an appropriate background based on selection state.

	Example Input: _drawBackground(dc, rectangle, isSelected)
	Example Input: _drawBackground(dc, rectangle, isSelected, color = cellColor)"""

	oldPen = dc.GetPen()
	oldBrush = dc.GetBrush()

	try:
		if (color is not None):
			color = tuple(min(255, max(0, item)) for item in color) #Ensure numbers are between 0 and 255
		else:
			if (isSelected):
				color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_HIGHLIGHT)
			else:
				color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_WINDOW)
		dc.SetBrush(wx.Brush(color, style = wx.SOLID))
	
		dc.SetPen(wx.TRANSPARENT_PEN)
		dc.DrawRectangle(rectangle.x, rectangle.y, rectangle.width, rectangle.height)
	finally:
		dc.SetPen(oldPen)
		dc.SetBrush(oldBrush)

def _drawButton(dc, rectangle, isSelected, fitTo = None, radius = 1, borderWidth = 1,
	x_offset = 0, y_offset = 0, width_offset = 0, height_offset = 0,
	x_align = None, y_align = None, color = None, borderColor = None):
	"""Draw a button in appropriate colors.
	If both 'x_align' and 'y_align' are None, no alignment will be done

	fitTo (str)   - Determines the initial width and height of the button
		- If str: Will use the size of the text if it were drawn
		- If None: Will use 'rectangle'

	x_align (str) - Where the button should be aligned with respect to the x-axis in the cell
		~ "left", "right", "center"
		- If None: Will use "center"

	y_align (str) - Where the button should be aligned with respect to the x-axis in the cell
		~ "top", "bottom", "center"
		- If None: Will use "center"

	Example Input: _drawButton(dc, rectangle, isSelected)
	Example Input: _drawButton(dc, rectangle, isSelected, x_align = "right", y_align = "top")
	Example Input: _drawButton(dc, rectangle, isSelected, x_align = "center", y_align = "center", width_offset = -10, height_offset = -10)
	Example Input: _drawButton(dc, rectangle, isSelected, fitTo = "Lorem Ipsum", width_offset = 6)
	"""

	oldPen = dc.GetPen()
	oldBrush = dc.GetBrush()

	try:
		if (color is not None):
			color = tuple(min(255, max(0, item)) for item in color) #Ensure numbers are between 0 and 255
		else:
			if (isSelected):
				color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNHIGHLIGHT)
			else:
				color = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNFACE)
		dc.SetBrush(wx.Brush(color, style = wx.SOLID))

		if (borderColor is not None):
			borderColor = tuple(min(255, max(0, item)) for item in borderColor) #Ensure numbers are between 0 and 255
		else:
			borderColor = wx.SystemSettings.GetColour(wx.SYS_COLOUR_BTNSHADOW)
		dc.SetPen(wx.Pen(borderColor, width = borderWidth, style = wx.SOLID))
		# dc.SetPen(wx.TRANSPARENT_PEN)

		if (fitTo is None):
			width = rectangle.width
			height = rectangle.height
		else:
			width, height = dc.GetTextExtent(fitTo)

		if ((x_align is None) and (y_align is None)):
			x_align = 0
			y_align = 0
		else:
			if (x_align is None):
				x_align = "center"
			elif (y_align is None):
				y_align = "center"

			if (x_align.lower()[0] == "l"):
				x_align = 0
			elif (x_align.lower()[0] == "r"):
				x_align = rectangle.width - (width + width_offset)
			else:
				x_align = (rectangle.width - (width + width_offset)) / 2

			if (y_align.lower()[0] == "t"):
				y_align = 0
			elif (y_align.lower()[0] == "b"):
				y_align = rectangle.height - (height + height_offset)
			else:
				y_align = (rectangle.height - (height + height_offset)) / 2

		dc.DrawRoundedRectangle(rectangle.x + x_align + x_offset, rectangle.y + y_align + y_offset, width + width_offset, height + height_offset, radius)
	finally:
		dc.SetPen(oldPen)
		dc.SetBrush(oldBrush)
		
def _clip(dc, rectangle):
	"""Setup the clipping rectangle"""
	
	dc.SetClippingRegion(rectangle.x, rectangle.y, rectangle.width, rectangle.height)

def _unclip(dc):
	"""Destroy the clipping rectangle"""
	
	dc.DestroyClippingRegion()

def getWindowAsBitmap(window = None, *, useFrame = True, onlyThis = False):
	"""Makes a bmp of what a wxWindow looks like.
	Modified code from Andrea Gavana on: https://www.blog.pythonlibrary.org/2010/04/16/how-to-take-a-screenshot-of-your-wxpython-app-and-print-it/
	See: https://stackoverflow.com/questions/4773961/get-a-widgets-dc-in-wxpython/4783203#4783203

	window (wxWindow) - What object to get a bitmap of
		- If None: Will use the currently active wxWindow

	useFrame (bool) - Determines how to use 'window
		- If True: Will use the wxFrame 'window' is nested in
		- If False: Will use 'window' directly

	onlyThis (bool) - Determines what in the frame is used to create the bitmap
		- If True: Only this wxWindow object will be used
		- If False: What the screen looks like where this wxWindow is will be used

	Example Input: getWindowAsBitmap(self.thing)
	"""

	if (window is None):
		window = wx.GetActiveWindow()
		if (window is None):
			raise NoActiveWindowError()

	if (useFrame):
		window = wx.GetTopLevelParent(window)

	x, y, width, height = window.GetRect()
	bitmap = wx.Bitmap(width, height)

	if (onlyThis):
		x_offset = 0
		y_offset = 0
		source_dc = wx.WindowDC(window)
	else:
		x_offset = x
		y_offset = y
		source_dc = wx.ScreenDC()

	memory_dc = wx.MemoryDC(bitmap)
	memory_dc.Blit(0, 0, width, height, source_dc, x_offset, y_offset)
	memory_dc.SelectObject(wx.NullBitmap)
	return bitmap

@contextlib.contextmanager
def _useOverlay(eventObject, overlay):
	"""Yields the wxClientDc of the given wxWindow object with a wxOverlay applied to it.

	eventObject (wxWindow) - What to get the wxClientDc from
	overlay (wxOverlay) - The wxOverlay object to use
	freeze (bool) - Determines if 'eventObject' should be frozen to reduce flickering
	thaw (bool) - Determiens if 'eventObject' should be unfrozen if this function froze it
	_______________________________________________________________________________________

	Example Use:
		with self._useOverlay(eventObject, self.status_overlay) as dc:
			self._drawText(dc, "Lorem Ipsum")
	"""

	overlay.Reset()
	
	dc = wx.ClientDC(eventObject)
	dc.Clear()
	odc = wx.DCOverlay(overlay, dc)
	odc.Clear()

	if ('wxMac' not in wx.PlatformInfo):
		dc = wx.GCDC(dc) #Mac's DC is already the same as a GCDC

	yield dc

	del odc  # Make sure the odc is destroyed before the dc is.

class DrawFunctions():
	@classmethod
	def getPen(cls, *args, **kwargs):
		return getPen(*args, **kwargs)

	@classmethod
	def getBrush(cls, *args, **kwargs):
		return getBrush(*args, **kwargs)

	@classmethod
	def getBrushStyle(cls, *args, **kwargs):
		return getBrushStyle(*args, **kwargs)

	@classmethod
	def _drawText(cls, *args, **kwargs):
		return _drawText(*args, **kwargs)
		
	@classmethod
	def _drawBackground(cls, *args, **kwargs):
		return _drawBackground(*args, **kwargs)
		
	@classmethod
	def _drawButton(cls, *args, **kwargs):
		return _drawButton(*args, **kwargs)
		
	@classmethod
	def _clip(cls, *args, **kwargs):
		return _clip(*args, **kwargs)
		
	@classmethod
	def _unclip(cls, *args, **kwargs):
		return _unclip(*args, **kwargs)
		
	@classmethod
	def getWindowAsBitmap(cls, *args, **kwargs):
		return getWindowAsBitmap(*args, **kwargs)
		
	@classmethod
	def _useOverlay(cls, *args, **kwargs):
		return _useOverlay(*args, **kwargs)

imageTypeCatalogue = MyUtilities.common._dict({
	"any": 		wx.BITMAP_TYPE_ANY, 		None: "${any}", 
	"bmp": 		wx.BITMAP_TYPE_BMP, 
	"gif": 		wx.BITMAP_TYPE_GIF, 
	"png": 		wx.BITMAP_TYPE_PNG, 
	"jpeg": 	wx.BITMAP_TYPE_JPEG, 

	"ico": 		wx.BITMAP_TYPE_ICO, 
	"icon": 	wx.BITMAP_TYPE_ICON, 
	"cur": 		wx.BITMAP_TYPE_CUR, 

	"tif": 		wx.BITMAP_TYPE_TIF, 
	"tiff": 	wx.BITMAP_TYPE_TIFF, 
	"ani": 		wx.BITMAP_TYPE_ANI, 
	"iff": 		wx.BITMAP_TYPE_IFF, 
	"tga": 		wx.BITMAP_TYPE_TGA, 
	"pnm": 		wx.BITMAP_TYPE_PNM, 
	"pcx": 		wx.BITMAP_TYPE_PCX, 
	"pict": 	wx.BITMAP_TYPE_PICT, 

	"xbm": 		wx.BITMAP_TYPE_XBM, 
	"xpm": 		wx.BITMAP_TYPE_XPM, 
	"xbm_data": wx.BITMAP_TYPE_XBM_DATA, 
	"xpm_data": wx.BITMAP_TYPE_XPM_DATA, 

}, caseSensitive = False, typeSensitive = False)
def saveBitmap(bitmap, fileName, *, imageType = None):
	"""Saves the given bitmap.

	bitmap (wxBitmap) - What bitmap to save
	fileName (str) - Where to save the bitmap
		- If io.StreamIO: Will save the bitmap to this io stream

	Example Input: saveBitmap(bitmap, "lorem", imageType = "bmp")
	Example Input: saveBitmap(bitmap, stream, imageType = "bmp")
	"""
	global imageTypeCatalogue

	image = bitmap.ConvertToImage()
	image.SaveFile(fileName, imageTypeCatalogue.get(imageType))

#Custom Widgets
class AutocompleteTextCtrl(wx.TextCtrl):
	"""Modified code from: https://bitbucket.org/raz/wxautocompletectrl/src/default/autocomplete.py"""

	__license__ = MyUtilities.legal.AutocompleteTextCtrl.__license__
	__author__ = MyUtilities.legal.AutocompleteTextCtrl.__author__
	__url__ = MyUtilities.legal.AutocompleteTextCtrl.__url__

	def __init__(self, parent, height = 300, completer = None, frequency = 250, style = None, 
		caseSensitive = False, useWildcards = False, alwaysShow = False, multiline = False, 
		onSelect_hide = False, onSelect_update = False, onKey_update = False, 
		formatter = None, verifier = None, showEmpty = False, **kwargs):

		self.parent = parent
		self.height = height
		self.frequency = frequency

		self.choices = ()
		self.template = None
		self.queued_popup = False
		self.previousValue = None
		self.skipEvent_update = False

		self.verifier = verifier
		self.formatter = formatter

		self.showEmpty = showEmpty
		self.alwaysShow = alwaysShow
		self.useWildcards = useWildcards
		self.caseSensitive = caseSensitive

		self.onKey_update = onKey_update
		self.onSelect_hide = onSelect_hide
		self.onSelect_update = onSelect_update

		if (isinstance(style, int)):
			style = [style]
		else:
			style = style or []

		style.append(wx.TE_PROCESS_ENTER)
		if (multiline):
			style.append(wx.TE_MULTILINE)

		if (isinstance(self.parent, wx.Window)):
			wx.TextCtrl.__init__(self, self.parent, style = functools.reduce(operator.ior, style or (0,),), **kwargs)
		else:
			wx.TextCtrl.__init__(self, self.parent.thing, style = functools.reduce(operator.ior, style or (0,),), **kwargs)
		
		self.SetCompleter(completer)

	def default_completer(self, choices = None, template = None):
		"""Modified code from: https://bitbucket.org/raz/wxautocompletectrl/src/default/test_autocomplete.py"""
		
		choices = choices or ()
		template = template or "<b><u>{}</b></u>"

		if (choices):
			self.choices = choices

		def completer(query):
			if (not query):
				return (), ()

			_choices = self.choices or choices
			if (not _choices):
				return (), ()

			_template = self.template or template

			if (self.useWildcards):
				if (self.caseSensitive):
					def searchValue(section, full):
						return re.search(section, full) is not None

					def formatValue(section, full):
						nonlocal _template
						return re.sub(section, _template.format(section), full)
				else:
					def searchValue(section, full):
						return re.search(section, full, flags = re.IGNORECASE) is not None

					def formatValue(section, full):
						nonlocal _template
						return re.sub(section, _template.format(section), full, flags = re.IGNORECASE)
			else:
				if (self.caseSensitive):
					def searchValue(section, full):
						return section in full

					def formatValue(section, full):
						nonlocal _template
						return full.replace(section, _template.format(section))
				else:
					def searchValue(section, full):
						return section.casefold() in full.casefold()

					def formatValue(section, full):
						nonlocal _template
						return re.sub(re.escape(section), _template.format(section), full, flags = re.IGNORECASE)

			def yieldValues(query): #Do all this with a generator cleanly
				nonlocal _choices, searchValue, formatValue

				for item in _choices:
					if (item is None):
						continue

					item = f"{item}"
					if (not searchValue(query, item)):
						continue

					yield formatValue(query, item), item

			###########################################
				
			answer = tuple(zip(*yieldValues(query)))
			if (not answer):
				return (), ()

			formated, unformated = answer
			return formated, unformated

		return completer

	def SetCompleter(self, completer = None):
		"""
		Initializes the autocompletion. The 'completer' has to be a function
		with one argument (the current value of the control, ie. the query)
		and it has to return two lists: formated (html) and unformated
		suggestions.
		"""

		if (callable(completer)):
			self.completer = completer
		else:
			self.completer = self.default_completer(completer or ())

		frame = self.Parent
		while not isinstance(frame, (wx.Frame, wx.Dialog, wx.adv.Wizard)):
			frame = frame.Parent

		self.popup = self.SuggestionsPopup(self, frame)

		frame.Bind(wx.EVT_MOVE, self.OnMove)
		self.Bind(wx.EVT_TEXT, self.OnTextUpdate)
		self.Bind(wx.EVT_SIZE, self.OnSizeChange)
		self.Bind(wx.EVT_KEY_DOWN, self.OnKeyDown)
		self.Bind(wx.EVT_RIGHT_UP, self.OnRightClick)
		self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)
		self.popup._suggestions.Bind(wx.EVT_KEY_DOWN, self.OnSuggestionKeyDown)
		self.popup._suggestions.Bind(wx.EVT_LEFT_DOWN, self.OnSuggestionClicked)

	def SetValue(self, value = NULL, default = None, triggerPopup = True):
		def apply(_value):
			nonlocal self, triggerPopup

			if (not triggerPopup):
				self.skipEvent_update = True

			super(self.__class__, self).SetValue(_value)

		################################

		if (value is NULL):
			value = self.Value

		if (self.verifier):
			if (not self.verifier(value)):
				if (default is not None):
					return apply(default)
				return

		if (self.formatter):
			value = self.formatter(value)
			if (value is None):
				if (default is not None):
					return apply(default)
				return

		if (self.previousValue is None):
			self.previousValue = value

		return apply(value)

	def AdjustPopupPosition(self):
		self.popup.Position = self.ClientToScreen((0, self.Size.height)).Get()

	def OnMove(self, event):
		self.AdjustPopupPosition()
		event.Skip()

	def OnTextUpdate(self, event):
		if (self.IsFrozen()):
			pass

		elif (self.skipEvent_update):
			self.skipEvent_update = False

		elif (not self.queued_popup):
			wx.CallLater(self.frequency, self.AutoComplete)
			self.queued_popup = True

		event.Skip()

	def UpdateChoices(self, choices = None):
		self.choices = choices or ()

	def AutoComplete(self, choices = None):
		def apply(formated, unformated = None):
			nonlocal self

			self.popup.SetSuggestions(formated, unformated)

			if (not self.IsFrozen()):
				self.AdjustPopupPosition()
				self.popup.ShowWithoutActivating()
				self.SetFocus()

		####################################

		self.queued_popup = False

		if (choices):
			self.UpdateChoices(choices)

		value = self.GetValue()
		if (value != ""):
			formated, unformated = self.completer(value)
			if (self.showEmpty or formated):
				return apply(formated, unformated)

		elif (self.alwaysShow):
			return apply(self.choices)

		if (not self.IsFrozen()):
			self.popup.Hide()

	def OnSizeChange(self, event):
		self.popup.Size = (self.Size[0], self.height)
		event.Skip()

	def OnKeyDown(self, event):
		key = event.GetKeyCode()

		if (key == wx.WXK_UP):
			self.popup.CursorUp()
			return

		elif (key == wx.WXK_DOWN):
			self.popup.CursorDown()
			return

		elif (key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and self.popup.Shown):
			self.skipEvent_update = True
			self.SetValue(self.popup.GetSelectedSuggestion())
			self.SetInsertionPointEnd()
			self.popup.Hide()
			return

		elif (key == wx.WXK_HOME):
			self.popup.CursorHome()

		elif (key == wx.WXK_END):
			self.popup.CursorEnd()

		elif (event.ControlDown() and chr(key).lower() == "a"):
			self.SelectAll()

		elif (key == wx.WXK_ESCAPE):
			self.popup.Hide()
			return

		event.Skip()

	def OnSuggestionClicked(self, event):
		self.skipEvent_update = True
		self.SetValue(self.popup.GetSuggestion(self.popup._suggestions.VirtualHitTest(event.Position[1])))
		self.SetInsertionPointEnd()
		
		wx.CallAfter(self.SetFocus)
		if (self.onSelect_update):
			wx.CallAfter(self.AutoComplete)
		elif (self.onSelect_hide):
			wx.CallAfter(self.popup.Hide)

		event.Skip()

	def OnSuggestionKeyDown(self, event):
		key = event.GetKeyCode()
		if (key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
			self.skipEvent_update = True
			self.SetValue(self.popup.GetSelectedSuggestion())
			self.SetInsertionPointEnd()
			self.popup.Hide()

		event.Skip()

	def OnRightClick(self, event):
		if (self.alwaysShow):
			if (self.popup.IsShown()):
				self.popup.Hide()
			else:
				self.AutoComplete()
			return
		event.Skip()

	def OnKillFocus(self, event):
		if (self.FindFocus() not in (self.popup._suggestions, self)):
			self.popup.Hide()

			if (self.verifier or self.formatter):
				self.skipEvent_update = True
				self.SetValue(default = self.previousValue)
				self.previousValue = self.Value

		event.Skip()

	class SuggestionsPopup(wx.Frame):
		__license__ = MyUtilities.legal.SuggestionsPopup.__license__
		__author__ = MyUtilities.legal.SuggestionsPopup.__author__
		__url__ = MyUtilities.legal.SuggestionsPopup.__url__

		def __init__(self, parent, frame):
			# wx.Frame.__init__(self, frame, style = wx.FRAME_NO_TASKBAR|wx.FRAME_FLOAT_ON_PARENT|wx.STAY_ON_TOP)
			wx.Frame.__init__(self, frame, style = wx.FRAME_NO_TASKBAR|wx.FRAME_FLOAT_ON_PARENT|wx.STAY_ON_TOP|wx.RESIZE_BORDER)

			self.parent = parent
			panel = wx.Panel(self, wx.ID_ANY)
			sizer = wx.BoxSizer(wx.VERTICAL)

			self._suggestions = self._listbox(panel)#, size = (parent.GetSize()[1], 100))#, size = (500, 400))
			self._suggestions.SetItemCount(0)
			self._unformated_suggestions = None

			sizer.Add(self._suggestions, 1, wx.ALL|wx.EXPAND, 5)
			panel.SetSizer(sizer)

			self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

		class _listbox(wx.html.HtmlListBox):
			items = None

			def OnGetItem(self, n):
				return self.items[n] or ""

		def SetSuggestions(self, suggestions, unformated_suggestions = None):
			self._suggestions.items = suggestions
			self._suggestions.SetItemCount(len(suggestions))
			if (suggestions):
				self._suggestions.SetSelection(0)
		
			self._suggestions.Refresh()
			self.SendSizeEvent()

			self._unformated_suggestions = unformated_suggestions or suggestions

		def CursorUp(self):
			selection = self._suggestions.GetSelection()
			if selection > 0:
				self._suggestions.SetSelection(selection - 1)

			thing = self.parent
			if (thing.onKey_update):
				thing.skipEvent_update = True
				thing.SetValue(self.GetSelectedSuggestion())

		def CursorDown(self):
			selection = self._suggestions.GetSelection()
			last = self._suggestions.GetItemCount() - 1
			if selection < last:
				self._suggestions.SetSelection(selection + 1)

			thing = self.parent
			if (thing.onKey_update):
				thing.skipEvent_update = True
				thing.SetValue(self.GetSelectedSuggestion())

		def CursorHome(self):
			if self.IsShown():
				self._suggestions.SetSelection(0)

		def CursorEnd(self):
			if self.IsShown():
				self._suggestions.SetSelection(self._suggestions.GetItemCount() - 1)

		def GetSelectedSuggestion(self):
			return self._unformated_suggestions[self._suggestions.GetSelection()]

		def GetSuggestion(self, n):
			return self._unformated_suggestions[n]

		def OnKillFocus(self, event):
			if (self.FindFocus() not in (self._suggestions, self.parent)):
				self.Hide()
			event.Skip()

# @MyUtilities.common.makeHook("popup.checkList", "Append", "SetSelection", "Clear")
class CheckListCtrl(wx.ComboCtrl, MyUtilities.common.EnsureFunctions, EventFunctions):
	"""A wxListCtrl-like widget where each item in the drop-down list has a check box.
	Modified code from: https://github.com/wxWidgets/Phoenix/blob/master/demo/ComboCtrl.py
	"""

	def __init__(self, parent, root = None, *, myId = None, initial = None, position = None, size = None, style = None, 
		readOnly = False, alphabetic = False, **kwargs):
		"""
		parent (wxWindow) – Parent window (must not be None)
		initial (str) – Initial selection string
		readOnly (bool) - Determiens if the user can modify values in this widget

		Example Input: CheckListCtrl(self)
		"""

		EventFunctions.__init__(self)

		self.thing = self
		self.parent = parent

		root = self.ensure_default(root, default = parent)
		if (not isinstance(self.parent, wx.Window)):
			root = root.thing

		#Configure settings
		if (isinstance(style, int)):
			style = [style]
		else:
			style = style or []

		if (readOnly):
			style.append(wx.CB_READONLY)

		if (alphabetic):
			style.append(wx.CB_SORT)

		#Create object
		super().__init__(root, 
			id = myId or wx.ID_ANY, 
			value = initial or "", 
			pos = position or wx.DefaultPosition, 
			size = size or wx.DefaultSize, 
			style = functools.reduce(operator.ior, style or (0,)))

		self.popup = self.MyPopup(self, **kwargs)

	def Append(self, *args, **kwargs):
		return self.popup.checkList.Append(*args, **kwargs)

	def SetSelection(self, *args, **kwargs):
		return self.popup.checkList.SetSelection(*args, **kwargs)

	def Clear(self, *args, **kwargs):
		return self.popup.checkList.Clear(*args, **kwargs)

	def setFunction_check(self, myFunction = None, myFunctionArgs = None, myFunctionKwargs = None):
		self._betterBind(self.EVT_CHECK, self, myFunction, myFunctionArgs, myFunctionKwargs, mode = 2)

	def OnCheckItem(self, index, state, item):
		self.triggerEvent(self.EVT_CHECK, index = index, state = state, item = item, text = item.GetText(), raw = self.parent.choices[index])

	class EVT_CHECK(MyEvent):
		def __init__(self, parent, **kwargs):
			super().__init__(self, parent)

			self.raw = kwargs.pop("raw", None) #The un-formatted version of 'text'
			self.item = kwargs.pop("item", None) #The wxListItem that was checked
			self.text = kwargs.pop("text", None) #What the item says
			self.index = kwargs.pop("index", None) #The index of the item
			self.state = kwargs.pop("state", None) #If the item is checked or not

	# @MyUtilities.common.makeHook("checkList", "Append", "SetSelection", "Clear")
	class MyPopup(wx.ComboPopup, MyUtilities.common.EnsureFunctions):
		"""The popup control used by CheckListCtrl."""

		def __init__(self, parent, *, prefHeight = None, lazyLoad = False, **kwargs):
			"""
			multiple (bool) - Determines if the user can check multiple boxes or not
			lazyLoad (bool) - Determines if when Create() is called
				- If True: Waits for the first time the popup is called
				- If False: Calls it during the build process
			
			prefHeight (int) - What height you would prefer the popup box use
				- If None: Will calculate what hight to use based on it's contents
				- If -1: Will use the default height
			"""

			self.parent = parent
			self.lazyLoad = lazyLoad 
			self.prefHeight = prefHeight

			self._buildKwargs = kwargs

			super().__init__()

			parent.SetPopupControl(self)

		def Create(self, parent):
			self.checkList = self.MyListCtrl(self, parent, **self._buildKwargs)
			del self._buildKwargs

			return True

		def GetControl(self):
			return self.checkList

		def GetAdjustedSize(self, minWidth, prefHeight, maxHeight):
			if (self.prefHeight is -1):
				return super().GetAdjustedSize(minWidth, prefHeight, maxHeight)
			
			elif (self.prefHeight is not None):
				return (minWidth, min(self.prefHeight, maxHeight))

			return self.checkList.GetBestSize(minWidth, prefHeight, maxHeight)

		def LazyCreate(self):
			return self.lazyLoad

		class MyListCtrl(wx.ListCtrl, wx.lib.mixins.listctrl.CheckListCtrlMixin, MyUtilities.common.EnsureFunctions):
			"""Modified code from: https://github.com/wxWidgets/wxPython/blob/master/demo/CheckListCtrlMixin.py"""

			def __init__(self, parent, root, *, popupId = None, multiple = False, 
				image_check = None, image_uncheck = None):
				"""
				multiple (bool) - Determines if the user can check multiple boxes or not
				"""

				self.parent = parent
				self.widget = parent.parent

				#Configure settings
				style = [wx.LC_LIST, wx.SIMPLE_BORDER]

				if (not multiple):
					style.append(wx.LC_SINGLE_SEL)

				#Create object
				wx.ListCtrl.__init__(self, root, id = popupId or wx.ID_ANY, style = functools.reduce(operator.ior, style or (0,)))
				wx.lib.mixins.listctrl.CheckListCtrlMixin.__init__(self, check_image = image_check, uncheck_image = image_uncheck)

				#Bind functions
				# self.Bind(wx.EVT_LIST_ITEM_ACTIVATED, self.OnItemActivated)
				# self.Bind(wx.EVT_MOTION, self.OnMotion)
				# self.Bind(wx.EVT_LEFT_DOWN, self.OnLeftDown)

			def Append(self, value, default = False, *, triggerEvent = False):
				"""Appends the given item to the list.

				value (str) - What the item will say
				default (bool) - What state the check box will start out at

				Example Input: Append("lorem")
				Example Input: Append("lorem", default = True)
				"""

				# print("@Append", self.widget)

				n = self.GetItemCount()
				self.InsertItem(n, value)

				if (default):
					self.CheckItem(n, triggerEvent = triggerEvent)

			def Clear(self):
				self.ClearAll()

			def SetSelection(self, selection, state = True, *, triggerEvent = False):
				for index in selection:
					self.CheckItem(index, check = state, triggerEvent = triggerEvent)

			def GetBestSize(self, minWidth, prefHeight, maxHeight):
				return (minWidth, min(prefHeight, maxHeight, sum(self.GetItemRect(i)[3] for i in range(self.GetItemCount())) + self.GetItemRect(0)[3]))

			def CheckItem(self, index, check = True, triggerEvent = True):
				"""Overridden to allow for the event to not be triggered."""

				# print("@CheckItem", index)

				imageIndex = self.GetItem(index).GetImage()
				if (not operator.xor(imageIndex, check)):
					return

				self.SetItemImage(index, int(check))

				if (triggerEvent):
					self.OnCheckItem(index, check)

			def OnCheckItem(self, index, state):
				item = self.GetItem(index)
				self.widget.OnCheckItem(index = index, state = state, item = item)

if (__name__ == "__main__"):
	class TestFrame(wx.Frame):
		def __init__(self):
			super().__init__(None, wx.ID_ANY, "Lorem Ipsum")

			with asCM(wx.Panel, self, wx.ID_ANY) as myPanel:
				with asCM(wx.BoxSizer, wx.VERTICAL) as mySizer:
		 
					with asCM(CheckListCtrl, myPanel, prefHeight = None) as myWidget:
						myWidget.Append("lorem")
						myWidget.Append("ipsum", default = True)
						myWidget.Append("dolor")
						
						myWidget.setFunction_check(self.onCheck)
						mySizer.Add(myWidget, 0, wx.ALL, 5)
			 
					myPanel.SetSizer(mySizer)

		def onCheck(self, event):
			print("@onCheck", event.state, event.index, event.text, event.item)

	####################################

	app = wx.App(False)
	frame = TestFrame()
	frame.Show()
	app.MainLoop()
