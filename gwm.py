"""
Graphics window manager, creates multple toplevel togl widgets for
use by python plotting

$Id$
"""

from OpenGL.GL import *
import Tkinter
import gkiopengl
import wutil

class GWMError(Exception):
	pass

# for the moment this is a really crude implementation. It leaves out
# lots of useful methods for managing these windows as well as handling
# all the kinds of options for creating these windows that you would
# expect.

def redraw(o):

	# A placeholder function to be used until the desired function
	# is assigned.

	# At the very least, clear the window.
	glClearColor(0.5, 0.5, 0.5, 0)
	glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
	glEnable(GL_LINE_SMOOTH)

class GraphicsWindowManager:

	def __init__(self):
	
		self.windows = {}
#		self.terminalWindowID = wutil.terminalWindowID
		self.lastTermPos = (0, 0)
		self.activeWindow = None
		self.irafGkiConfig = gkiopengl.IrafGkiConfig()
		
	def window(self, windowName=None):

		if not windowName: # think up a default name!
			done = 0
			number = 1
			while not done:
				trialName = 'graphics'+str(number)
				if not self.windows.has_key(trialName):
					self.windows[trialName] = GraphicsWindow(trialName)
					self.activeWindow = self.windows[trialName]
					done = 1
					windowName = trialName
				number = number +1
		else:
			if not self.windows.has_key(windowName):
				self.windows[windowName] = GraphicsWindow(windowName)
			self.activeWindow = self.windows[windowName]
		self.activeWindow.gwidget.activate()
		# The following attaches to the new window a reference to the
		# window manager so that the window knows who to call to have
		# it removed from the list (e.g., user closes window). This
		# probably is not the best way to do it!
		self.activeWindow.windowManager = self
		# register with focus manager
		wutil.focusController.addFocusEntity(windowName,self.activeWindow)
			
	def nWindows(self):
		
		return len(self.windows)

	def delete(self, windowName):

		changeActiveWindow = 0
		if self.windows.has_key(windowName):
			if self.activeWindow.getWindowName() == windowName:
				changeActiveWindow = 1
			window = self.windows[windowName]
			window.top.destroy()
			del self.windows[windowName]
			if changeActiveWindow:
				if len(self.windows):
					self.activeWindow = self.windows.keys()[0]
				else:
					self.activeWindow = None
			wutil.focusController.removeFocusEntity(windowName)
		else:
			print "error: specified graphics window doesn't exist"
				
class GraphicsWindow:

	def __init__(self, windowName=None):

		import Ptogl # local substitute for OpenGL.Tk
		             # (to remove goofy 3d cursor effects)
					 # import is placed here since it has the side effect
					 # of creating a tk window, so delay import to
					 # a time that a window is really needed. Subsequent
					 # imports will be ignored
		if Ptogl.createdRoot:
			Tkinter._default_root.withdraw()
			Ptogl.createdRoot = 0   # clear so subsequent calls don't redo

		self.windowName = windowName
		self.top = Tkinter.Toplevel()
		self.gwidget = Ptogl.Ptogl(self.top,width=700,height=500)
		self.gwidget.redraw = redraw
		self.top.title(windowName)
		self.gwidget.pack(side = 'top', expand=1, fill='both')
		self.top.protocol("WM_DELETE_WINDOW", self.gwdestroy)
		windowID = self.gwidget.winfo_id()
		wutil.setBackingStore(windowID)

	# the following methods implement the FocusEntity interface
	# used by wutil.FocusController

	def saveCursorPos(self):

		"""save current position if window has focus and cursor is
		in window, otherwise do nothing"""
		gwin = self.gwidget

		# first see if window has focus
		if wutil.getTopID(wutil.getWindowID()) != \
		   wutil.getTopID(self.gwidget.winfo_id()):
			return
		posdict = wutil.getPointerPosition(gwin.winfo_id())
		if posdict:
			x = posdict['win_x']
			y = posdict['win_y']
		else:
			return
		maxX = gwin.winfo_width()
		maxY = gwin.winfo_height()
		if x < 0 or y < 0 or x >= maxX or y >= maxY:
			return
		gwin.lastX = x
		gwin.lastY = y

	def forceFocus(self):

		gwin = self.gwidget
		# only force focus if window is viewable
		if not wutil.isViewable(self.top.winfo_id()):
			return
		# warp cursor
		# if no previous position, move to center
		if not gwin.lastX:
			gwin.lastX = gwin.winfo_width()/2
			gwin.lastY = gwin.winfo_height()/2
		wutil.moveCursorTo(gwin.winfo_id(),gwin.lastX,gwin.lastY)
		self.gwidget.focus_force()

	def getWindowID(self):

		return self.gwidget.winfo_id()

	# end of FocusEntity methods

	def getWindowName(self):

		return self.windowName
			
	def gwdestroy(self):

		self.windowManager.delete(self.windowName)

# Create a module instance of the GWM object that can be referred
# by anything that imports this module. It is in effect a singleton
# object intended to be instantiated only once and be accessible from
# the module.

_g = GraphicsWindowManager()
wutil.isGwmStarted = 1

#
# Public routines to access windows managed by _g
#

def getGraphicsWindowManager():

	"""return window manager object"""
	return _g

def createWindow():

	"""Create a new graphics window and make it the active one"""
	_g.window()

def getActiveWindow():

	"""Get the active Ptogl window"""
	if _g.activeWindow:
		return _g.activeWindow.gwidget
	else:
		return None

def getActiveGraphicsWindow():
	
	"""Get the active Graphics window object"""
	if _g.activeWindow:
		return _g.activeWindow

def getActiveWindowTop():

	"""Get the top window"""
	if _g.activeWindow:
		return _g.activeWindow.top
	else:
		return None

def raiseActiveWindow():

	"""deiconify if not mapped, and raise to top"""
	top = getActiveWindowTop()
	if not top: raise GWMError("No plot has been created yet")
	if top.state() != 'normal':
		top.deiconify()
	top.tkraise()

def getIrafGkiConfig():

	"""return configuration object"""
	return _g.irafGkiConfig



