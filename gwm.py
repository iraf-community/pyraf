"""
Graphics window manager, creates multple toplevel togl widgets for
use by python plotting

$Id$
"""

from OpenGL.GL import *
import Tkinter
import string
import gkiopengl
import wutil
import toglcolors

nIrafColors = 16

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
	if _g.colorManager.rgbamode:
		glClearColor(0.5, 0.5, 0.5, 0)
	else:
		glClearIndex(_g.colorManager.indexmap[1])
	glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
	# glEnable(GL_LINE_SMOOTH)

class GraphicsWindowManager:

	def __init__(self):
	
		self.windows = {}
		self.initialized = 0
		self.lastTermPos = (0, 0)
		self.activeWindow = None
		self.irafGkiConfig = gkiopengl.IrafGkiConfig()
		self.colorManager = gColor()

	def window(self, windowName=None):

		if not windowName: # think up a default name!
			number = 1
			while 1:
				windowName = 'graphics'+str(number)
				if not self.windows.has_key(windowName):
					break
				number = number + 1
		if not self.windows.has_key(windowName):
			self.windows[windowName] = GraphicsWindow(windowName,
										  self.colorManager.rgbamode)
		self.activeWindow = self.windows[windowName]
		self.activeWindow.gwidget.activate()
		# The following attaches to the new window a reference to the
		# window manager so that the window knows who to call to have
		# it removed from the list (e.g., user closes window). This
		# probably is not the best way to do it!
		self.activeWindow.windowManager = self
		# register with focus manager
		wutil.focusController.addFocusEntity(windowName,self.activeWindow)
		# if the new window is the only one, initialize and allocate colors
		if not self.initialized:
			self.initialized = 1
			cset = self.irafGkiConfig.defaultColors
			for cind in xrange(nIrafColors):
				self.colorManager.defineColor(cind,
						   cset[cind][0], cset[cind][1], cset[cind][2])
			self.colorManager.setColors()
		
	def nWindows(self):
		
		return len(self.windows)

	def delete(self, windowName):

		window = self.windows.get(windowName)
		if window is None:
			print "error: specified graphics window doesn't exist"
		else:
			changeActiveWindow = (self.activeWindow == window)
			window.top.destroy()
			del self.windows[windowName]
			if len(self.windows) == 0:
				self.initialized = 0
				self.activeWindow = None
			elif changeActiveWindow:
				#XXX change to randomly selected active window
				self.activeWindow =self.windows[self.windows.keys()[0]]
			wutil.focusController.removeFocusEntity(windowName)

class GraphicsWindow:

	def __init__(self, windowName, colormode):

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
		self.gwidget = Ptogl.Ptogl(self.top,width=600,height=420,
								   rgba=colormode)
		self.gwidget.status = Tkinter.Label(self.top, text="",
											relief = Tkinter.SUNKEN,
											borderwidth=1,
											anchor=Tkinter.W,height=1)
		self.gwidget.redraw = redraw
		self.top.title(windowName)
		self.gwidget.status.pack(side=Tkinter.BOTTOM,
					 fill=Tkinter.X, padx=2, pady=1, ipady=1)
		self.gwidget.pack(side = 'top', expand=1, fill='both')
		self.top.protocol("WM_DELETE_WINDOW", self.gwdestroy)
		self.gwidget.firstPlotDone = 0
		self.gwidget.interactive = 0
		windowID = self.gwidget.winfo_id()
		wutil.setBackingStore(windowID)

	def write(self, text):
		"""a write method so that this can be used to capture stdout to
		status"""
		
		self.gwidget.status.config(text=string.rstrip(text))

	def flush(self):
		self.gwidget.update_idletasks()

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

"""Encapsulates the details of setting the graphic's windows colors.
Needed since we may be using rgba mode or color index mode and we
do not want any of the graphics programs to have to deal with the
mode being used. The current design applies the same colors to all
graphics windows for color index mode (but it isn't required).
An 8-bit display depth results in color index mode, otherwise rgba
mode is used. In color index mode we attempt to allocate pairs of
color indices (even, odd) so that xor mode on the least sig bit of
the index results in ideal color flipping. If no new colors are
available, we take what we can get. We do not attempt to get a
private colormap"""

class gColor:

	def __init__(self):

		self.colorset = [None]*nIrafColors
		self.indexmap = [None]*nIrafColors
		depth = wutil.getScreenDepth()
		# print "screen depth =", depth
		if depth <=8:
			self.rgbamode = 0
		else:
			self.rgbamode = 1
			
	def defineColor(self, colorindex, red, green, blue):
		"""Color list consists of color triples. This method only
		sets up the desired color set, it doesn't allocate any colors
		from the colormap in color index mode."""
		self.colorset[colorindex] = (red, green, blue)

	def setColors(self):
		"""Does nothing in rgba mode, allocates 16 colors in index mode"""
		if self.rgbamode:
			return
		g = getActiveWindow()
		for i in xrange(16):
			self.indexmap[i] = toglcolors.AllocateColor(g.toglStruct,
							   self.colorset[i][0],
							   self.colorset[i][1],
							   self.colorset[i][2])

	def setDrawingColor(self, irafColorIndex):
		"""Apply the specified iraf color to the current OpenGL drawing
		state using the appropriate mode."""
		if self.rgbamode:
			color = self.colorset[irafColorIndex]
			glColor3f(color[0], color[1], color[2])
		else:
			glIndex(self.indexmap[irafColorIndex])
			
# Create a module instance of the GWM object that can be referred
# by anything that imports this module. It is in effect a singleton
# object intended to be instantiated only once and be accessible from
# the module.

if wutil.hasGraphics:
	_g = GraphicsWindowManager()
	wutil.isGwmStarted = 1
else:
	_g = None
	wutil.isGwmStarted = 0

#
# Public routines to access windows managed by _g
#

def getGraphicsWindowManager():

	"""return window manager object"""
	return _g

def getColorManager():

	return _g.colorManager

def window(windowName=None):

	"""Create a new graphics window if the named one doesn't exist or
	make it the active one if it does. If no argument is given a new
	name is constructed."""
	_g.window(windowName)

def delete(windowName):

	"""delete the named window"""
	_g.delete(windowName)

def getActiveWindowName():

	return _g.activeWindow.windowName

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

def setGraphicsDrawingColor(irafColorIndex):

	_g.colorManager.setDrawingColor(irafColorIndex)


def restoreLastFocus():
	"""Restore focus to terminal window after first Tk plot"""
	gwin = getActiveWindow()
	if gwin:
		if (not gwin.firstPlotDone) and wutil.hasGraphics:
			# this is a hack to prevent the double redraw on first plots
			# (when they are not interactive plots). This should be done
			# better, but it appears to work.
			if not gwin.interactive:
				gwin.ignoreNextNRedraws = 2
			wutil.focusController.restoreLast()
			gwin.firstPlotDone = 1

def resetFocusHistory():
	"""Reset focus history after an error occurs"""
	wutil.focusController.resetFocusHistory()

