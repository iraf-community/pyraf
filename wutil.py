"""Contains python routines to do special Window manipulations not
possible in Tkinter.
These are python stubs that are overloaded by a c version implementations.
If the c versions do not exist, then these routines will do nothing

$Id$
"""

import struct, fcntl, sys, os, cdl

def getWindowID(): return None
def moveCursorTo(WindowID, x, y): pass
def setFocusTo(WindowID): pass
def setBackingStore(WindowID): pass
def getPointerPostion(WindowID): pass
def getWindowAttributes(WindowID): pass
def getParentID(WindowID): pass
def getDeepestVisual(): return 24

try:
	from xlibtricks import *
except ImportError:
	pass


def getTopID(WindowID):

	"""Find top level X windows ID parent of given window.
	If window is already top (or not implemented), it returns its own ID.
	If the input Id represents the root window then it will just
	return itself"""
	# Assuming root window has id 1 (should eliminate this dependency)
	wid = WindowID
	try:
		if wid <= 0:
			return wid
		while 1:
			pid = getParentID(wid)
			if not pid:
				return wid
			else:
				wid = pid
	except EnvironmentError:
		return None

def isViewable(WindowID):

	attrdict = getWindowAttributes(WindowID)
	if attrdict:
		return attrdict['viewable']
	else:
		return 1
	
def getTermWindowSize():

	"""return a tuple containing the x,y size of the terminal window
	in characters"""

	try:
		import IOCTL
		magicConstant = IOCTL.TIOCGWINSZ
	except ImportError:
		platform = sys.platform
		if platform == 'sunos5':
			magicConstant = ord('T')*256 + 104 # at least on Solaris!
		elif platform == 'linux2':
			magicConstant = 0x5413
		else:
			raise Exception("platform isn't supported: "+platform)
	# define string to serve as memory area to recieve copy of structure
	# created by IOCTL call
	tstruct = ' '*20 # that should be more than enough memory
	# xxx exception handling needed (but what exception to catch?)
	rstruct = fcntl.ioctl(sys.stdin.fileno(), magicConstant, tstruct)
	xsize, ysize = struct.unpack('hh',rstruct[0:4])
	return xsize, ysize

#def getTerminalWindowID():

#	"""return ID of python terminal window manager was started from"""
#	return terminalWindowID

#def getImageWindowID():

#	"""return ID of image display window (e.g., SAOIMAGE or XIMTOOL)"""
#	return imageWindowID

def openImageDisplay():

	"""Connect to an ximtool/saoimage compatible image display"""
	
	if focusController.getFocusEntity("image"):
		# no need to do anything, display already open.
		return
	imtdev = ""
	if os.environ.has_key('IMTDEV'):
		imtdev = os.environ['IMTDEV']
	# must open the display only once in the CDL!
	displayHandle = cdl.cdl_open(imtdev)
	if displayHandle == "NULL":
		raise iraf.IrafProcessError("Unable to open image display")
	# Create image FocusEntity object for the FocusController
	imageFocusEntity = ImageDisplay(displayHandle)
	focusController.addFocusEntity("image",imageFocusEntity)
		
class ImageDisplay:

	"""Handles image display (ximtool/saoimage) interactions. Also
	implements wutil.FocusEntity interface."""

	def __init__(self, displayHandle):
		self.handle = displayHandle
		self.winID = None
		self.lastX = None
		self.lastY = None
		self.imcurActive = 0

	def getHandle(self):
		return self.handle

	def setWindowID(self):
		"""This ASSUMES that the image window has focus when this is called"""
		self.winID = getWindowID()
	
	def activateImcur(self):
		self.imcurActive = 1
	def deactivateImcur(self):
		self.imcurActive = 0

	# beginning of FocusEntity methods

	def saveCursorPos(self):

		if not self.winID:
			# no window ID yet known, can't handle; do nothing
			return
		if getTopID(getWindowID()) != getTopID(self.winID):
			return
		posdict = getPointerPosition(self.winID)
		if posdict:
			x = posdict['win_x']
			y = posdict['win_y']
		else:
			return
		windict = getWindowAttributes(self.winID)
		if windict:
			maxX = windict['width']
			maxY = windict['height']
		else:
			return
		if x < 0 or y < 0 or x >= maxX or y >= maxY:
			return
		self.lastX = x
		self.lastY = y

	def forceFocus(self):

		if not self.winID:
			return
		if not isViewable(self.winID):
			return
		if self.lastX is not None:
			moveCursorTo(self.winID,self.lastX,self.lastY)
		setFocusTo(self.winID)

	def getWindowID(self):
		return self.winID

	# End of FocusEntity methods


		

class FocusEntity:

	"""Represents an interface to peform focus manipulations on a variety of
	window objects. This allows the windows to be handled by code that does
	not need to know the specifics of how to set focus to, restore focus
	to, warp the cursor to, etc. Since nothing is implemented, it isn't
	necessary to inherit it. It serves as documentation for the interface.
	"""

	def __init__(self):
		pass
	def saveCursorPos(self):
		"""When this method is called, the object should know how to save
		the current position of the cursor in the window. If the cursor is
		not in the window or the window does not currently have focus, it
		should do nothing."""
		pass
	def forceFocus(self):
		"""When called, the object should force focus to the window it
		represents and warp the cursor to it using the last saved cursor
		position."""
		pass

	def getWindowID(self):
		"""return a window ID that can be used to find the top window
		of the window heirarchy."""

class FocusController:

	"""A mediator that allows different components to give responsibility
	to this class for deciding how to manipulate focus. It is this class
	that knows what elements are available and where focus should be returned
	to when asked to restore the previous focus and cursor position. The
	details of doing it for different windows is encapsulated in descendants
	of the FocusEntity objects that it contains. Since this is properly 
	a singleton, it is created by the wutil module itself and accessed
	as an object of wutil"""

	def __init__(self, termwindow):
		self.focusEntities = {'terminal':termwindow}
		self.focusStack = [termwindow]

	def addFocusEntity(self, name, focusEntity):
		if name == 'terminal':
			return # ignore any attempts to change terminal entity
		if self.focusEntities.has_key(name):
			return # ignore for now, not sure what proper behavior
				#is
		self.focusEntities[name] = focusEntity
			
	def removeFocusEntity(self, focusEntityName):

		if self.focusEntities.has_key(focusEntityName):
			del self.focusEntities[focusEntityName]
			
	def restoreLast(self):

		if len(self.focusStack) > 1:
			self.focusStack[-1].saveCursorPos()
			del self.focusStack[-1]	
		if self.focusInFamily():
			self.focusStack[-1].forceFocus()

	def setCurrent(self):
		
		"""This is to be used in cases where focus has been lost to
		a window not part of this scheme (dialog boxes for example)
		and it is desired to return focus to the entity currently considered
		active."""
		self.focusStack[-1].forceFocus()

	def resetFocusHistory(self):
		self.focusStack = [self.focusEntities['terminal']]

	def getCurrentFocusEntity(self):

		"""Return the focus entity that currently has focus.
		Return None if focus is not in the focus family"""
		currentFocusWinID = getWindowID()
		currentTopID = getTopID(currentFocusWinID)
		namematch = None
		for name,focusEntity in self.focusEntities.items():
			if getTopID(focusEntity.getWindowID()) == currentTopID:
				namematch = name
		if namematch:
			return namematch, self.focusEntities[namematch]
		else:
			return None, None

	def saveCursorPos(self):

		name, focusEntity = self.getCurrentFocusEntity()
		if focusEntity:
			focusEntity.saveCursorPos()

	def setFocusTo(self,focusTarget):

		"""focusTarget can be a string or a FocusEntity. It is possible to
		give a FocusEntity that is not in focusEntities (so it isn't 
		considered part of the focus family, but is part of the restore
		chain."""
		current = self.focusStack[-1]
		if type(focusTarget) == type(""):
			next = self.focusEntities[focusTarget]
		else:
			next = focusTarget
		# only append if focus stack last entry different from new
		if next != self.focusStack[-1]:
			self.focusStack.append(next)
		if self.focusInFamily():
			current.saveCursorPos()
			next.forceFocus()

	def getFocusEntity(self, FEName):

		"""See if named Focus Entity is currently registered. Return it
		if it exists, None otherwise"""

		if self.focusEntities.has_key(FEName):
			return self.focusEntities[FEName]
		else:
			return None

	def focusInFamily(self):

		"""Determine if current focus is within the pyraf family
		(as defined by self.focusEntities)"""
		currentFocusWinID = getWindowID()
		currentTopID = getTopID(currentFocusWinID)
		for focusEntity in self.focusEntities.values():
			if focusEntity.getWindowID():
				if getTopID(focusEntity.getWindowID()) == currentTopID:
					return 1
		return 0  # not in family

# XXXX find more portable scheme for handling absence of FCNTL

class TerminalFocusEntity:

	"""Implementation of FocusEntity interface for the originating
	terminal window"""

	def __init__(self):
		"""IMPORTANT: This class must be instantiated while focus
		is in the terminal window"""
		self.windowID = getWindowID()
		self.curposX = 30
		self.curposY = 30
	
	def getWindowID(self):
		return self.windowID

	def forceFocus(self):
		if not isViewable(self.windowID):
			return
		moveCursorTo(self.windowID, self.curposX, self.curposY)
		setFocusTo(self.windowID)

	def saveCursorPos(self):
		posdict = getPointerPosition(self.windowID)
		if posdict:
			x = posdict['win_x']
			y = posdict['win_y']
		else:
			return
		windict = getWindowAttributes(self.windowID)
		if windict:
			maxX = windict['width']
			maxY = windict['height']
		else:
			return
		# do nothing if position out of window
		if x < 0 or y < 0 or x >= maxX or y >= maxY:
			return
		self.curposX = x
		self.curposY = y

	# some extra utility methods

	def getWindowSize(self):
		
		"""return a tuple containing the x,y size of the terminal window
		in characters"""

		try:
			import IOCTL
			magicConstant = IOCTL.TIOCGWINSZ
		except ImportError:
			platform = sys.platform
			if platform == 'sunos5':
				magicConstant = ord('T')*256 + 104 # at least on Solaris!
			elif platform == 'linux2':
				magicConstant = 0x5413
			else:
				raise Exception("platform isn't supported: "+platform)
		# define string to serve as memory area to recieve copy of structure
		# created by IOCTL call
		tstruct = ' '*20 # that should be more than enough memory
		# xxx exception handling needed (but what exception to catch?)
		rstruct = fcntl.ioctl(sys.stdin.fileno(), magicConstant, tstruct)
		xsize, ysize = struct.unpack('hh',rstruct[0:4])
		return xsize, ysize

def getScreenDepth():

	return getDeepestVisual()

terminal = TerminalFocusEntity()
terminalWindowID = terminal.getWindowID()
focusController = FocusController(terminal)
hasGraphics = terminalWindowID > 1
if not hasGraphics:
	print ""
	print "No graphics display available for this session " + \
			  "(Xwindow unavailable)."
	print "Graphics tasks that attempt to plot to an interactive " + \
			  "screen will fail."
	print ""














