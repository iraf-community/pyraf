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

terminalWindowID = getWindowID()

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
		

# XXXX find more portable scheme for handling absence of FCNTL

