"""This gives the ability to read the cursor position from
SAOIMAGE or XIMTOOL in a manner compatible with IRAF's imcur
parameter"""

import os, iraf, wutil
try:
	import cdl
	def imcur(): return  _imcur()
except ImportError:
	def imcur():
		raise iraf.IrafError(
		"image display library (cdlmodule.so) not available")

prevDisplayHandle = None

def _imcur():

	"""Returns the string expected for IRAF's imcur parameter"""

	global prevDisplayHandle
	try:
		termWinID = wutil.getTerminalWindowID()
		imtdev = ""
		if os.environ.has_key('IMTDEV'):
			imtdev = os.environ['IMTDEV']
		# must open the display only once in cdl!
		if not prevDisplayHandle:
			displayHandle = cdl.cdl_open(imtdev)
			prevDisplayHandle = displayHandle
			if displayHandle == "NULL":
				raise iraf.IrafProcessError("Unable to open image display")
		else:
			displayHandle = prevDisplayHandle
		wutil.imcurActive = 1
		if wutil.imageWindowID:
			# move focus and cursor to window if focus in pyraf window family
			if not wutil.isFocusElsewhere():
				imID = wutil.getImageWindowID()
				if wutil.isViewable(imID):
					curWinID = wutil.getWindowID()
#					if curWinID == wutil.getTerminalWindowID():
#						# save terminal cursor position if in that window
#						wutil.saveTerminalCursorPosition()
#					pos = wutil.getLastImagePos()
					wutil.setFocusTo(imID)
#					wutil.moveCursorTo(imID,pos[0],pos[1])
		# Require keystroke to read cursor position (0 arg)
		key, xpos, ypos, dummy = cdl.cdl_readCursor(displayHandle, 0)
		if not wutil.imageWindowID:
			wutil.imageWindowID = wutil.getWindowID()
#		wutil.saveImageCursorPosition()
		frame = cdl.cdl_getFrame(displayHandle)
		# don't close the display!
		if key == ':':
			returnFocusToTermWindow()
			colonString = raw_input(": ")
			imID = wutil.getWindowID()
			if wutil.isViewable(imID):
#				wutil.saveTerminalCursorPosition()
				wutil.setFocusTo(imID)
#				x, y = wutil.getLastImagePos()
#				wutil.moveCursorTo(imID,x,y)
		else:
			colonString = ""
		# The following is a bit of a kludge, but appears to be the only
		# way of preventing focus flashing between the image window and
		# terminal window on each imcur loop. We will assume that a convention
		# is being followed by the application in that the key strokes
		# 'q' or '?' means quit imcur mode or help respectively and will
		# result in a focus change back to the terminal window. If that
		# isn't true, it isn't the end of the world.
		if key in ('q','?'):
			wutil.imcurActive = 0
			returnFocusToTermWindow()
		wcs = 100*frame + 1
	except:
		# Above all, make sure the imcur flag doesn't stay on in case
		# of an error.
		wutil.imcurActive = 0
		returnFocusToTermWindow()
		raise
	return "%f %f %d %s %s" % (xpos, ypos, wcs, key, colonString)
	
def returnFocusToTermWindow():

	termWinID = wutil.getTerminalWindowID()
	if wutil.isViewable(termWinID):
#		wutil.saveImageCursorPosition()
		wutil.setFocusTo(termWinID)
#		x, y = wutil.getLastTermPos()
#		wutil.moveCursorTo(termWinID,x,y)		
