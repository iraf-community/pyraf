"""Contains python routines to do special Window manipulations not
possible in Tkinter.
These are python stubs that are overloaded by a c version implementations.
If the c versions do not exist, then these routines will do nothing

$Id$
"""

import struct, fcntl, sys

def getWindowID(): return None
def moveCursorTo(WindowID, x, y): pass
def setFocusTo(WindowID): pass
def setBackingStore(WindowID): pass
def getPointerPosition(WindowID): pass
def getWindowAttributes(WindowID): pass
def getParentID(WindowID): pass

try:
	from xlibtricks import *
except ImportError:
	pass


def getTopID(WindowID):

	"""Find top level X windows ID parent of given window.
	If window is already top (or not implemented), it returns its own ID"""
	wid = WindowID
	while 1:
		pid = getParentID(wid)
		if not pid:
			return wid
		else:
			wid = pid

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

def getTerminalWindowID():

	"""return ID of python terminal window manager was started from"""
	return terminalWindowID

def getImageWindowID():

	"""return ID of image display window (e.g., SAOIMAGE or XIMTOOL)"""
	return imageWindowID

def getLastTermPos():	return lastTermPos
def setLastTermPos(x, y):
	global lastTermPos
	lastTermPos = (x, y)
def getLastImagePos():  return lastImagePos
def setLastImagePos(x, y):
	global lastImagePos
	lastImagePos = (x, y)

def saveTerminalCursorPosition():

	# save current position unless (0,0), then save center position
	termWinID = getTerminalWindowID()
	posdict = getPointerPosition(termWinID)
	if posdict:
		x = posdict['win_x']
		y = posdict['win_y']
	else:
		x, y = 0, 0
	#if x == 0 and y == 0:
	windict = getWindowAttributes(termWinID)
	if windict:
		maxX = windict['width']
		maxY = windict['height']
	else:
		maxX, maxY = 20,20
	x = min(max(x,0),maxX)
	y = min(max(y,0),maxY)
	setLastTermPos(x,y)

def saveImageCursorPosition():

	# save current position unless (0,0), then save center position
	imageWinID = getImageWindowID()
	if imageWinID:
		posdict = getPointerPosition(imageWinID)
		if posdict:
			x = posdict['win_x']
			y = posdict['win_y']
		else:
			x, y = 0, 0
		#if x == 0 and y == 0:
		windict = getWindowAttributes(imageWinID)
		if windict:
			maxX = windict['width']
			maxY = windict['height']
		else:
			maxX, maxY = 20,400
		x = min(max(x,0),maxX)
		y = min(max(y,0),maxY)
		setLastImagePos(x,y)

def isFocusElsewhere():

	# Determine if focus lies outside of terminal/graphics window set.
	import gwm
	try:
		currentFocusWinID = getWindowID()
		currentTopID = getTopID(currentFocusWinID)
		terminalWindowTopID = getTopID(getTerminalWindowID())
		pyrafFamily = [terminalWindowTopID]
		wm = gwm.getGraphicsWindowManager()
		if gwm.getActiveWindow():
			for win in wm.windows.values():
				pyrafFamily.append(getTopID(win.top.winfo_id()))
		if imageWindowID:
			pyrafFamily.append(getTopID(imageWindowID))
		if currentTopID in pyrafFamily:
			return 0
		else:
			return 1
	except EnvironmentError:
		# if for some reason the above obtains a bad window ID for getTopID
		return 1
		
# XXXX find more portable scheme for handling absence of FCNTL

terminalWindowID = getWindowID()
imageWindowID = None
imcurActive = 0
lastTermPos = (0,0)
lastImagePos = (0,0)
