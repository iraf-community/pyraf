"""
implement IRAF gcur functionality

$Id$
"""

import string, os
import gwm, wutil, iraf, irafexecute, gkiopengl
import irafgwcs
import tkSimpleDialog

# The following class attempts to emulate the standard IRAF gcursor
# mode of operation. That is to say, it is basically a keyboard driven
# system that uses the same keys that IRAF does for the same purposes.
# The keyboard I/O will use Tkinter event handling instead of terminal
# I/O primarily because it is simpler and it is necessary to use Tkinter
# anyway.

class Gcursor:

	"""This handles the classical IRAF gcur mode"""

	def __init__(self):
	
		self.x = 0
		self.y = 0
		self.top = None
		self.win = None
		self.retString = None

	def __call__(self): return self.startCursorMode()

	def startCursorMode(self ):
		
		# Get reference to active graphics window and bind event handling
		#  from it.
		self.top = gwm.getActiveWindowTop()
		if not self.top:
			# if graphics hasn't been started yet xxx depends implicitly on
			# opengl kernel. This may become optional
			irafexecute.stdgraph = gkiopengl.GkiOpenGlKernel()
			irafexecute.stdgraph.openWS(irafexecute.Numeric.array([5,0]))
			irafexecute.stdgraph.closeWS(None)
			self.top = gwm.getActiveWindowTop()
		self.win = gwm.getActiveWindow()
		gwm.raiseActiveWindow()
		self.top.update()
		wutil.focusController.setFocusTo(gwm.getActiveGraphicsWindow())
		self.win.activateSWCursor(
			float(self.win.lastX)/self.win.winfo_width(),
			float(self.win.lastY)/self.win.winfo_height())
		self.bind()
		self.win.ignoreNextRedraw = 1
		self.top.mainloop()
		self.unbind()
		return self.retString

	def bind(self):
	
		self.win.bind("<Button-1>",self.getMousePosition)
		self.win.bind("<Key>",self.getKey)
			
	def unbind(self):
	
		self.win.unbind("<Button-1>")
		self.win.unbind("<Key>")
		
	def getNDCCursorPos(self):

		"""Do an immediate cursor read and return coordinates in
		NDC coordinates"""

		win = gwm.getActiveWindow()
		sx = win.winfo_pointerx() - win.winfo_rootx()
		sy = win.winfo_pointery() - win.winfo_rooty()
		self.x = sx
		self.y = sy
		# get current window size
		winSizeX = self.win.winfo_width()
		winSizeY = self.win.winfo_height()
		ndcX = float(sx)/winSizeX
		ndcY = float(winSizeY - sy)/winSizeY
		return ndcX, ndcY

	def getMousePosition(self, event):
	
		self.x = event.x
		self.y = event.y

	def getKey(self, event):

		# The main character handling routine (to be filled out)
		key = event.char
		if not key:
			# ignore keypresses of non printable characters
			return
		x,y = self.getNDCCursorPos()
		if key == 'q': # Expecting the graphics task to end. Possibly false,
		               # but no big deal if it is. The vast majority of the
					   # time it is true.
			wutil.focusController.restoreLast()
		if key == '?': # Expecting irafukey to be called, may not be the case
			           # but no big deal if it isn't. The vast majority of the
					   # time it is.
			wutil.focusController.setFocusTo('terminal')
		if key == ':':
			# pop up text entry dialog
			colonString = tkSimpleDialog.askstring("Gcur colon command","")
			# Explicitly return focus to graphics window since some
			# window managers apparently don't do this automatically
			# (e.g. openwindows)
			self.top.focus_force()
			if colonString[0] == '.':
				print "Not quite ready to handle CL level gcur :. commands."
				print "Please check back later."
			else:
				self._setRetString(key,colonString)
		elif key == '=':
			# snap command - print the plot
			printPlot()
			print "snap completed"
		elif 'A' <= key <= 'Z':
			print "Not quite ready to handle CL level gcur commands."
			print "Please check back later."
		else:
			self._setRetString(key,"")

	def _setRetString(self, key, cstring):

		x,y = self.getNDCCursorPos()
		wcs = gwm.getActiveWindow().iplot.wcs
		if wcs:
			wx,wy,gwcs = gwm.getActiveWindow().iplot.wcs.get(x,y)
		else:
			wx,wy,gwcs = x,y,0
		if key <= ' ' or ord(key) >= 127:
			key = '\\%03o' % ord(key)
		self.retString = str(wx)+' '+str(wy)+' '+str(gwcs)+' '+key
		if cstring:
			self.retString = self.retString +' '+cstring
#		gwm.saveGraphicsCursorPosition()
#		wutil.focusController.restoreLast()
		self.top.quit() # time to go!

def printPlot():

	win = gwm.getActiveWindow()
	gkibuff = win.iplot.gkiBuffer.get()
	if gkibuff:
		# write to a temporary file
		# XXXX better temporary filename?
		tmpfn = iraf.Expand('tmp$')+"pysnap"+str(os.getpid())+".gki"
		fout = open(tmpfn,'w')
		fout.write(gkibuff.tostring())
		fout.close()
		iraf.stsdas.motd="no"
		iraf.load("stsdas",doprint=0)
		iraf.load("graphics",doprint=0)
		iraf.load("stplot",doprint=0)
		printkernel = iraf.getTask("psikern")
		printkernel(tmpfn)
		os.remove(tmpfn)
		
# Eventually there may be multiple Gcursor classes that return a string
# that satisfies clgcur. In that case we will use a factory function
# to set gcur to the desired mode of operation. For now Gcursor is it.

gcur = Gcursor()
