"""
implement IRAF ukey functionality

$id$
"""

import sys
import wutil

# This class emulates the IRAF ukey parameter mechanism. IRAF calls for
# a ukey parameter and expects that the user will type a character in
# response. The value of this character is then returned to the iraf task
# This class works in a manner similar to irafgcur. Importing the module
# creates a ukey object and subsequent calls to this object return
# the key typed by the user. Tkinter is used to handle user keystrokes,
# even for non-graphical tasks (the only simple portable way of doing
# such I/O). We may implement a termios variant for nongraphics
# tasks later.

class UserKey:

	"""This handles the classical IRAF ukey parameter mode"""

	def __init__(self):

		self.retString = None
		self.prevFocus = None

	def __call__(self): return self.startUKeyMode()

	def startUKeyMode(self):

		self.top = self._getFocusWindow()
		self.bind()
		self.top.mainloop()
		self.unbind()
		if self.prevFocus: wutil.setFocusTo(self.prevFocus)
		return self.retString

	def _getFocusWindow(self):

		# use existing graphics window for Tk events if it exists.
		# If not, use Tk root, else import if not there

		self.prevFocus = wutil.getWindowID()
		if sys.modules.has_key('gwm'):
			import gwm
			tkwin = gwm.getActiveWindowTop()
		elif sys.modules.has_key('Tkinter'):
			import Tkinter
			tkwin = Tkinter.root
		else:
			# a warning message indicating a delay for importing
			warnMess="...wait until this message disappears before responding"
			print warnMess,
			import Tkinter
			print (len(warnMess)+1)*'\b',
			print len(warnMess)*' ',
			print (len(warnMess)+1)*'\b',
			tkwin = root
		tkwin.focus_force()
		return tkwin
		
	def bind(self):

		self.top.bind("<Key>",self.getKey)

	def unbind(self):

		self.top.unbind("<Key>")
		
	def getKey(self, event):

		key = event.char
		if not key:
			# ignore keypresses non printable characters.
			return
		else:
			self.retString = key
			self.top.quit()
