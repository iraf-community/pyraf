"""irafimcur.py: image cursor interaction

This gives the ability to read the cursor position from
SAOIMAGE or XIMTOOL in a manner compatible with IRAF's imcur
parameter.

$Id$
"""

import os, sys, wutil
from irafglobals import Verbose, IrafError
try:
	import cdl
	try:
		import threading
		import gwm
		def imcur(): return  _imcur(_threadedReadCursor)
	except ImportError:
		def imcur(): return  _imcur()
except ImportError:
	def imcur():
		raise IrafError(
		"image display library (cdlmodule.so) not available")

prevDisplayHandle = None

def _readCursor(displayHandle, retlist=None):
	"""Reads image cursor and returns tuple with key, position"""
	# Require keystroke to read cursor position (0 arg)
	win = gwm.getActiveWindowTop()
	if win is not None: win.update()
	rv = cdl.cdl_readCursor(displayHandle, 0)
	if retlist is not None: retlist.append(rv)
	if Verbose>1: print rv
	return rv

def _threadedReadCursor(displayHandle):
	"""Reads image cursor in a thread so Tk windows can remain active"""
	result = []
	th = threading.Thread(target=_readCursor, args=(displayHandle, result))
	if Verbose>1: print "starting imcur thread"
	th.start()
	timeout = 0.5
	# messy -- I wish I could just sleep until thread is done, letting
	# Python's implicit mainloop run.  That doesn't work though.
	win = gwm.getActiveWindowTop()
	while th.isAlive():
		th.join(timeout)
		if win is None:
			win = gwm.getActiveWindowTop()
			if win is not None: win.update()
		else:
			win.update()
	if Verbose>1: print "finished imcur thread"
	return result[0]


def _imcur(readCursor=_readCursor):

	"""Returns the string expected for IRAF's imcur parameter"""

	imageDisplay = wutil.openImageDisplay()
	displayHandle = imageDisplay.getHandle()
	# Read cursor position at keystroke
	key, xpos, ypos, wcs, dummy = readCursor(displayHandle)
	# don't close the display!
	if key in ['\004', '\032']:
		raise EOFError # irafexecute will handle this properly
	if key == ':':
		sys.stdout.write(": ")
		sys.stdout.flush()
		colonString = sys.stdin.readline()[:-1]
	else:
		colonString = ""
	return "%f %f %d %s %s" % (xpos, ypos, wcs, key, colonString)
