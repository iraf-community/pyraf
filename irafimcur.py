"""This gives the ability to read the cursor position from
SAOIMAGE or XIMTOOL in a manner compatible with IRAF's imcur
parameter"""

import os, iraf, wutil
try:
	import cdl
except ImportError:
	raise iraf.IrafProcessError(
		"image display library (cdlmodule.so) not available")

def imcur():

	"""Returns the string expected for IRAF's imcur parameter"""

	imtdev = ""
	if os.environ.has_key('IMTDEV'):
		imtdev = os.environ['IMTDEV']
	displayHandle = cdl.cdl_open(imtdev)
	if displayHandle == "NULL":
		raise iraf.IrafProcessError("Unable to open image display")
	if wutil.imageWindowID:
		# move focus and cursor to window if focus in pyraf window family
		if not wutil.isFocusElsewhere():
			imID = wutil.getImageWindowID()
			if wutil.isViewable(imID):
				curWinID = wutil.getWindowID()
				if curWinID == wutil.getTerminalWindowID():
					# save terminal cursor position if in that window
					wutil.saveTerminalCursorPosition()
				pos = wutil.getLastImagePos()
				wutil.setFocusTo(imID)
				wutil.moveCursorTo(imID,pos[0],pos[1])
	# Require keystroke to read cursor position (0 arg)
	key, xpos, ypos, dummy = cdl.cdl_readCursor(displayHandle, 0)
	if not wutil.ImageWindowID:
		wutil.ImageWindowID = wutil.getWindowID()
	wutil.saveImageCursorPosition()
	frame = cdl.cdl_getFrame(displayHandle)
	cdl.cdl_close(displayHandle)
	termWinID = wutil.getTerminalWindowID()
	if key == ':':
		if wutil.isViewable(termWinID):
			wutil.saveImageCursorPosition()
			wutil.setFocusTo(termWinID)
			x, y = wutil.getLastTermPos()
			wutil.moveCursorTo(termWinID,x,y)		
		colonString = raw_input(": ")
		imID = wutil.getWindowID()
		if wutil.isViewable(imID):
			wutil.saveTerminalCursorPosition()
			wutil.setFocusTo(imID)
			x, y = wutil.getLastImagePos()
			wutil.moveCursorTo(termWinID,x,y)
	else:
		colonString = ""
	# The following is a bit of a kludge, but appears to be the only
	# way of preventing focus flashing between the image window and
	# terminal window on each imcur loop. We will assume that a convention
	# is being followed by the application in that the key stroke
	# 'q' means quit imcur mode will result in a focus change back to
	# the terminal window. If that isn't true, it isn't the end of the
	# world.
	if key == 'q':
		if wutil.isViewable(termWinID):
			wutil.saveImageCursorPosition()
			wutil.setFocusTo(termWinID)
			x, y = wutil.getLastTermPos()
			wutil.moveCursorTo(termWinID,x,y)		
	print frame, "frame"
	wcs = 100*frame + 1
	return "%f %f %d %s %s" % (xpos, ypos, wcs, key, colonString)
	

