"""irafimcur.py: image cursor interaction

This gives the ability to read the cursor position from
SAOIMAGE or XIMTOOL in a manner compatible with IRAF's imcur
parameter.

$Id$
"""

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

	try:
		wutil.openImageDisplay()
		imageDisplay = wutil.focusController.getFocusEntity("image")
		displayHandle = imageDisplay.getHandle()
#		imageDisplay.activateImcur()
		wutil.focusController.setFocusTo("image")
		# Require keystroke to read cursor position (0 arg)
		key, xpos, ypos, dummy = cdl.cdl_readCursor(displayHandle, 0)
		if not imageDisplay.getWindowID():
			imageDisplay.setWindowID()
		frame = cdl.cdl_getFrame(displayHandle)
		# don't close the display!
		if key == '\\':
			# This is what cdl returns for any control key. Since
			# we need to trap control-D, this is what we will
			# interpret it as.
			key = ' ' # just to give it a value
			raise EOFError # irafexecute will handle this properly
		if key == ':':
			wutil.focusController.setFocusTo("terminal")
			colonString = raw_input(": ")
			wutil.focusController.restoreLast()
		else:
			colonString = ""
		# The following is a bit of a kludge, but appears to be the only
		# way of preventing focus flashing between the image window and
		# terminal window on each imcur loop. We will assume that a convention
		# is being followed by the application in that the key strokes
		# 'q' or '?' means quit imcur mode or help respectively and will
		# result in a focus change back to the terminal window. If that
		# isn't true, it isn't the end of the world.
#		if key in ('q','?'):
#			wutil.imcurActive = 0
#			returnFocusToTermWindow()

		wcs = 100*frame + 1
	except:
		# Above all, make sure the imcur flag doesn't stay on in case
		# of an error.
		wutil.focusController.resetFocusHistory()
		wutil.focusController.restoreLast()
		raise
	wutil.focusController.restoreLast()
	return "%f %f %d %s %s" % (xpos, ypos, wcs, key, colonString)
	
