"""Contains python routines to do special Window manipulations not
possible in Tkinter.
These are python stubs that are overloaded by a c version implementations.
If the c versions do not exist, then these routines will do nothing

$Id$
"""

def getWindowID(): return None
def moveCursorTo(XWindowID, x, y): pass
def setFocusTo(XWindowID): pass

try:
	from xlibtricks import *
except ImportError:
	pass
