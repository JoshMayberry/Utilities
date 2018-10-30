import wx
import wx.html

import re
import operator
import functools

if (__name__ == "__main__"):
	import LICENSE_forSections as Legal
else:
	from . import LICENSE_forSections as Legal

class AutocompleteTextCtrl(wx.TextCtrl):
	"""Modified code from: https://bitbucket.org/raz/wxautocompletectrl/src/default/autocomplete.py"""

	__license__ = Legal.AutocompleteTextCtrl.__license__
	__author__ = Legal.AutocompleteTextCtrl.__author__
	__url__ = Legal.AutocompleteTextCtrl.__url__

	def __init__(self, parent, height = 300, completer = None, caseSensitive = False, useWildcards = False, 
		alwaysShow = False, multiline = False, frequency = 250, style = None, **kwargs):

		self.choices = ()
		self.template = None
		self.parent = parent
		self.height = height
		self.skip_event = False
		self.queued_popup = False
		self.frequency = frequency
		self.alwaysShow = alwaysShow
		self.useWildcards = useWildcards
		self.caseSensitive = caseSensitive

		if (isinstance(style, int)):
			style = [style]
		else:
			style = style or []

		style.append(wx.TE_PROCESS_ENTER)
		if (multiline):
			style.append(wx.TE_MULTILINE)

		if (isinstance(self.parent, wx.Window)):
			wx.TextCtrl.__init__(self, self.parent, style = functools.reduce(operator.ior, style or [0]), **kwargs)
		else:
			wx.TextCtrl.__init__(self, self.parent.thing, style = functools.reduce(operator.ior, style or [0]), **kwargs)
		
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
		self.popup._suggestions.Bind(wx.EVT_LEFT_DOWN, self.OnSuggestionClicked)
		self.popup._suggestions.Bind(wx.EVT_KEY_DOWN, self.OnSuggestionKeyDown)
		self.Bind(wx.EVT_SET_FOCUS, self.OnSetFocus)
		self.Bind(wx.EVT_KILL_FOCUS, self.OnKillFocus)

	def AdjustPopupPosition(self):
		self.popup.Position = self.ClientToScreen((0, self.Size.height)).Get()

	def OnMove(self, event):
		self.AdjustPopupPosition()
		event.Skip()

	def OnTextUpdate(self, event):
		if self.skip_event:
			self.skip_event = False
		elif (not self.queued_popup):
			wx.CallLater(self.frequency, self.AutoComplete)
			self.queued_popup = True
		event.Skip()

	def UpdateChoices(self, choices = None):
		self.choices = choices or []

	def AutoComplete(self, choices = None):
		def apply(formated, unformated = None):
			nonlocal self

			self.popup.SetSuggestions(formated, unformated)

			self.AdjustPopupPosition()
			self.popup.ShowWithoutActivating()
			self.SetFocus()

		####################################

		self.queued_popup = False

		if (choices):
			self.UpdateChoices(choices)

		if (self.Value != ""):
			formated, unformated = self.completer(self.Value)
			if (formated):
				return apply(formated, unformated)

		if (self.alwaysShow):
			return apply(self.choices)

		self.popup.Hide()

	def OnSizeChange(self, event):
		self.popup.Size = (self.Size[0], self.height)
		event.Skip()

	def OnKeyDown(self, event):
		key = event.GetKeyCode()

		if key == wx.WXK_UP:
			self.popup.CursorUp()
			return

		elif key == wx.WXK_DOWN:
			self.popup.CursorDown()
			return

		elif key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER) and self.popup.Shown:
			self.skip_event = True
			self.SetValue(self.popup.GetSelectedSuggestion())
			self.SetInsertionPointEnd()
			self.popup.Hide()
			return

		elif key == wx.WXK_HOME:
			self.popup.CursorHome()

		elif key == wx.WXK_END:
			self.popup.CursorEnd()

		elif event.ControlDown() and unichr(key).lower() == "a":
			self.SelectAll()

		elif key == wx.WXK_ESCAPE:
			self.popup.Hide()
			return

		event.Skip()

	def OnSuggestionClicked(self, event):
		self.skip_event = True
		n = self.popup._suggestions.VirtualHitTest(event.Position[1])
		self.Value = self.popup.GetSuggestion(n)
		self.SetInsertionPointEnd()
		wx.CallAfter(self.SetFocus)
		event.Skip()

	def OnSuggestionKeyDown(self, event):
		key = event.GetKeyCode()
		if (key in (wx.WXK_RETURN, wx.WXK_NUMPAD_ENTER)):
			self.skip_event = True
			self.SetValue(self.popup.GetSelectedSuggestion())
			self.SetInsertionPointEnd()
			self.popup.Hide()
		event.Skip()

	def OnSetFocus(self, event):
		if (self.alwaysShow and (not self.popup.IsActive())):
			self.AutoComplete()
		event.Skip()

	def OnKillFocus(self, event):
		if (not self.popup.IsActive()):
			self.popup.Hide()
		event.Skip()

	class SuggestionsPopup(wx.Frame):
		__license__ = Legal.SuggestionsPopup.__license__
		__author__ = Legal.SuggestionsPopup.__author__
		__url__ = Legal.SuggestionsPopup.__url__

		def __init__(self, parent, frame):
			# wx.Frame.__init__(self, frame, style = wx.FRAME_NO_TASKBAR|wx.FRAME_FLOAT_ON_PARENT|wx.STAY_ON_TOP)
			wx.Frame.__init__(self, frame, style = wx.FRAME_FLOAT_ON_PARENT|wx.STAY_ON_TOP|wx.RESIZE_BORDER)

			panel = wx.Panel(self, wx.ID_ANY)
			sizer = wx.BoxSizer(wx.VERTICAL)

			self._suggestions = self._listbox(panel)#, size = (parent.GetSize()[1], 100))#, size = (500, 400))
			self._suggestions.SetItemCount(0)
			self._unformated_suggestions = None

			sizer.Add(self._suggestions, 1, wx.ALL|wx.EXPAND, 5)
			panel.SetSizer(sizer)

		class _listbox(wx.html.HtmlListBox):
			items = None

			def OnGetItem(self, n):
				return self.items[n] or ""

		def SetSuggestions(self, suggestions, unformated_suggestions = None):
			self._suggestions.items = suggestions
			self._suggestions.SetItemCount(len(suggestions))
			self._suggestions.SetSelection(0)
		
			self._suggestions.Refresh()
			self.SendSizeEvent()

			self._unformated_suggestions = unformated_suggestions or suggestions

		def CursorUp(self):
			selection = self._suggestions.GetSelection()
			if selection > 0:
				self._suggestions.SetSelection(selection - 1)

		def CursorDown(self):
			selection = self._suggestions.GetSelection()
			last = self._suggestions.GetItemCount() - 1
			if selection < last:
				self._suggestions.SetSelection(selection + 1)

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