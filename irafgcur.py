"""
implement IRAF gcur functionality

$Id$
"""

import string
import gwm
import irafgwcs

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
		self.win = gwm.getActiveWindow()
		self.bind()
		self.top.mainloop()
		self.unbind()
		return self.retString

	def bind(self):
	
		self.win.bind("<Button-1>",self.getMousePosition)
		self.win.bind("<Key>",self.getKey)
		self.win.bind("q",self.getKey)
		self.win.focus_force()
				
	def unbind(self):
	
		self.win.unbind("<Button-1>")
		self.win.unbind("<Key>")
		self.win.unbind("q")
		
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
		print self.x, self.y

	def getKey(self, event):
		# The main character handling routine (to be filled out)
		key = event.char
		x,y = self.getNDCCursorPos()
		if key in string.lowercase:
			wx,wy,gwcs = gwm.getActiveWindow().iplot.wcs.get(x,y)
			self.retString = str(wx)+' '+str(wy)+' '+str(gwcs)+' '+key
			print "getKey:", self.retString
			self.top.quit() # time to go!
		else:
			# ignore for the time being
			pass
		
# Eventually there may be multiple Gcursor classes that return a string
# that satisfies clgcur. In that case we will use a factory function
# to set gcur to the desired mode of operation. For now Gcursor is it.

gcur = Gcursor()

