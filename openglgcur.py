"""
implement IRAF gcur functionality

$Id$
"""

import string, os, sys, Numeric
import gwm, wutil, iraf, openglcmd, gki

# The following class attempts to emulate the standard IRAF gcursor
# mode of operation. That is to say, it is basically a keyboard driven
# system that uses the same keys that IRAF does for the same purposes.
# The keyboard I/O will use Tkinter event handling instead of terminal
# I/O primarily because it is simpler and it is necessary to use Tkinter
# anyway.

class Gcursor:

	"""This handles the classical IRAF gcur mode"""

	def __init__(self, window):
	
		self.x = 0
		self.y = 0
		self.top = None
		self.window = window
		self.gwidget = window.gwidget
		self.top = window.top
		self.markcur = 0
		self.retString = None

	def __call__(self): return self.startCursorMode()

	def startCursorMode(self):
		
		# bind event handling from this graphics window
		self.window.raiseWindow()
		self.gwidget.interactive = 1
		self.top.update()
		wutil.focusController.setFocusTo(self.window)
		if self.gwidget.lastX is not None:
			self.gwidget.activateSWCursor(
				float(self.gwidget.lastX)/self.gwidget.winfo_width(),
				float(self.gwidget.lastY)/self.gwidget.winfo_height())
		else:
			self.gwidget.activateSWCursor()
		self.bind()
		self.gwidget.ignoreNextRedraw = 1
		activate = self.window.getStdout() is None
		if activate:
			self.window.control_reactivatews(None)
		self.top.mainloop()
		self.unbind()
		self.gwidget.deactivateSWCursor()
		if activate:
			self.window.control_deactivatews(None)
		self.gwidget.lastX = self.x
		self.gwidget.lastY = self.y
		return self.retString

	def bind(self):
	
		self.gwidget.bind("<Button-1>",self.getMousePosition)
		self.gwidget.bind("<Key>",self.getKey)
		self.gwidget.bind("<Up>",self.moveUp)
		self.gwidget.bind("<Down>",self.moveDown)
		self.gwidget.bind("<Right>",self.moveRight)
		self.gwidget.bind("<Left>",self.moveLeft)
		self.gwidget.bind("<Shift-Up>",self.moveUpBig)
		self.gwidget.bind("<Shift-Down>",self.moveDownBig)
		self.gwidget.bind("<Shift-Right>",self.moveRightBig)
		self.gwidget.bind("<Shift-Left>",self.moveLeftBig)
					
	def unbind(self):
	
		self.gwidget.unbind("<Button-1>")
		self.gwidget.unbind("<Key>")
		self.gwidget.unbind("<Up>")
		self.gwidget.unbind("<Down>")
		self.gwidget.unbind("<Right>")
		self.gwidget.unbind("<Left>")
		self.gwidget.unbind("<Shift-Up>")
		self.gwidget.unbind("<Shift-Down>")
		self.gwidget.unbind("<Shift-Right>")
		self.gwidget.unbind("<Shift-Left>")
		
	def getNDCCursorPos(self):

		"""Do an immediate cursor read and return coordinates in
		NDC coordinates"""

		win = self.gwidget
		sx = win.winfo_pointerx() - win.winfo_rootx()
		sy = win.winfo_pointery() - win.winfo_rooty()
		self.x = sx
		self.y = sy
		# get current window size
		winSizeX = self.gwidget.winfo_width()
		winSizeY = self.gwidget.winfo_height()
		ndcX = float(sx)/winSizeX
		ndcY = float(winSizeY - sy)/winSizeY
		return ndcX, ndcY

	def getMousePosition(self, event):
	
		self.x = event.x
		self.y = event.y

	def moveCursorRelative(self, event, deltaX, deltaY):
		
		gwin = self.gwidget
		# only force focus if window is viewable
		if not wutil.isViewable(self.top.winfo_id()):
			return
		# if no previous position, ignore
		newX = event.x + deltaX
		newY = event.y + deltaY
		if (newX < 0):
			newX = 0
		if (newY < 0):
			newY = 0
		if (newX >= gwin.winfo_width()):
			newX = gwin.winfo_width() - 1
		if (newY >= gwin.winfo_height()):
			newY = gwin.winfo_height() - 1
		wutil.moveCursorTo(gwin.winfo_id(),newX,newY)

	def moveUp(self, event): self.moveCursorRelative(event, 0, -1)
	def moveDown(self, event): self.moveCursorRelative(event, 0, 1)
	def moveRight(self, event): self.moveCursorRelative(event, 1, 0)
	def moveLeft(self, event): self.moveCursorRelative(event, -1, 0)
	def moveUpBig(self, event): self.moveCursorRelative(event, 0, -5)
	def moveDownBig(self, event): self.moveCursorRelative(event, 0, 5)
	def moveRightBig(self, event): self.moveCursorRelative(event, 5, 0)
	def moveLeftBig(self, event): self.moveCursorRelative(event, -5, 0)

	def readString(self, prompt=""):
		"""Prompt and read a string"""
		stdout = self.window.getStdout(default=sys.stdout)
		stdin = self.window.getStdin(default=sys.stdin)
		stdout.write(prompt)
		stdout.flush()
		return stdin.readline()[:-1]

	def getKey(self, event):

		# The main character handling routine where no special keys
		# are used (e.g., control or arrow keys)
		key = event.char
		if not key:
			# ignore keypresses of non printable characters
			return
		x,y = self.getNDCCursorPos()
   		if self.markcur and key not in 'q?:=UR':
		   	metacode = openglcmd.markCross(x,y)
			openglcmd.appendMetacode(metacode)
		if key == ':':
			colonString = self.readString(prompt=": ")
			if colonString[0] == '.':
				if colonString[1:] == 'markcur+':
					self.markcur = 1
				elif colonString[1:] == 'markcur-':
					self.markcur = 0
				elif colonString[1:] == 'markcur':
					self.markcur = not self.markcur
				else:
					print "Don't handle this CL level gcur :. commands."
					print "Please check back later."
			else:
				self._setRetString(key,x,y,colonString)
		elif key == '=':
			# snap command - print the plot
			gki.printPlot(self.window)
		elif key in string.uppercase:
			if   key == 'R':
				openglcmd.redrawOriginal()
			elif key == 'T':
				textString = self.readString(prompt="Annotation string: ")
				metacode = openglcmd.text(textString,x,y)
				openglcmd.appendMetacode(metacode)
			elif key == 'U':
				openglcmd.undo()
			else:
				print "Not quite ready to handle this particular" + \
					  "CL level gcur command."
				print "Please check back later."
		else:
			self._setRetString(key,x,y,"")

	def getShiftKey(self, event):

		print event.key
		print ord(event.key)

	def _setRetString(self, key, x, y, colonString):

		wcs = self.window.wcs
		if wcs:
			wx,wy,gwcs = self.window.wcs.get(x,y)
		else:
			wx,wy,gwcs = x,y,0
		if key <= ' ' or ord(key) >= 127:
			key = '\\%03o' % ord(key)
		self.retString = str(wx)+' '+str(wy)+' '+str(gwcs)+' '+key
		if colonString:
			self.retString = self.retString +' '+colonString
		self.top.quit() # time to go!

