"""
Graphics window manager, creates multple toplevel togl widgets for
use by python plotting

$Id$
"""

import string, wutil, toglcolors
from OpenGL.GL import *
import gki, gkiopengl

class GWMError(Exception):
	pass

class GraphicsWindowManager(gki.GkiProxy):

	"""Proxy for active graphics window and manager of multiple windows

	Each window is an instance of GkiOpenGlKernel.  stdgraph
	holds the active window pointer.
	"""

	def __init__(self, GkiKernelClass):

		"""GkiKernelClass is the class of kernel objects created

		Class must implement both GkiKernel and FocusEntity interfaces
		and must have:

		- activate() method to make widget active
		- raiseWindow() method to deiconify and raise window
		- gwidget attribute with the actual widget
		- top attribute with the top level widget

		The last 2 seem unneccesarily implemenation-specific and
		probably should be eliminated if possible.
		"""

		gki.GkiProxy.__init__(self)
		self.GkiKernelClass = GkiKernelClass
		self.windows = {}
		self.windowName = None
		# save list of window names in order of creation
		self.createList = []

	def window(self, windowName=None):

		if not windowName: # think up a default name!
			number = 1
			while 1:
				windowName = 'graphics'+str(number)
				if not self.windows.has_key(windowName):
					break
				number = number + 1
		if not self.windows.has_key(windowName):
			self.windows[windowName] = self.GkiKernelClass(windowName)
			self.createList.append(windowName)
		self.windowName = windowName
		self.stdgraph = self.windows[windowName]
		self.stdgraph.activate()
		# register with focus manager
		wutil.focusController.addFocusEntity(windowName,self.stdgraph)

	def windowNames(self):
		"""Return list of all window names"""
		return self.windows.keys()

	def delete(self, windowName):

		window = self.windows.get(windowName)
		if window is None:
			print "error: specified graphics window doesn't exist"
		else:
			changeActiveWindow = (self.stdgraph == window)
			window.top.destroy()
			del self.windows[windowName]
			if len(self.windows) == 0:
				self.windowName = None
				self.stdgraph = None
			elif changeActiveWindow:
				# change to most recently created window
				while self.createList:
					wname = self.createList.pop()
					if self.windows.has_key(wname):
						self.createList.append(wname)
						break
				else:
					# something's messed up
					# change to randomly selected active window
					wname = self.windows.keys()[0]
				self.windowName = wname
				self.stdgraph =self.windows[wname]
			wutil.focusController.removeFocusEntity(windowName)

	def flush(self):
		for window in self.windows.values():
			window.flush()

	def openKernel(self):
		self.window()


# Create a module instance of the GWM object that can be referred
# by anything that imports this module. It is in effect a singleton
# object intended to be instantiated only once and be accessible from
# the module.

if wutil.hasGraphics:
	_g = GraphicsWindowManager(gkiopengl.GkiOpenGlKernel)
	wutil.isGwmStarted = 1
else:
	_g = None
	wutil.isGwmStarted = 0

#
# Public routines to access windows managed by _g
#

def getGraphicsWindowManager():

	"""Return window manager object (None if none defined)"""

	return _g

def window(windowName=None):

	"""Create a new graphics window if the named one doesn't exist or
	make it the active one if it does. If no argument is given a new
	name is constructed."""

	if not _g:
		raise GWMError("No graphics window manager is available")
	_g.window(windowName)

def delete(windowName=None):

	"""Delete the named window (or active window if none specified)"""

	if not _g:
		raise GWMError("No graphics window manager is available")
	if windowName is None:
		windowName = getActiveWindowName()
	if windowName is not None:
		_g.delete(windowName)

def getActiveWindowName():

	"""Return name of active window (None if none defined)"""

	if _g and _g.windowName:
		return _g.windowName

def getActiveWindow():

	"""Get the active window widget (None if none defined)"""

	if _g and _g.stdgraph:
		#XXX gwidget looks implementation-specific
		return _g.stdgraph.gwidget

def getActiveGraphicsWindow():

	"""Get the active graphics kernel object (None if none defined)"""

	if _g and _g.stdgraph:
		return _g.stdgraph

def getActiveWindowTop():

	"""Get the top window (None if none defined)"""

	if _g and _g.stdgraph:
		#XXX top is implementation-specific
		return _g.stdgraph.top

def raiseActiveWindow():

	"""Deiconify if not mapped, and raise to top"""

	stdgraph = getActiveGraphicsWindow()
	if not stdgraph:
		raise GWMError("No plot has been created yet")
	stdgraph.raiseWindow()

def resetFocusHistory():

	"""Reset focus history after an error occurs"""

	wutil.focusController.resetFocusHistory()

