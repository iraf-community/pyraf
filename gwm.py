"""
Graphics window manager, creates multple toplevel togl widgets for
use by python plotting

$Id$
"""

from OpenGL.GL import *
import Tkinter

# for the moment this is a really crude implementation. It leaves out
# lots of useful methods for managing these windows as well as handling
# all the kinds of options for creating these windows that you would
# expect.

def redraw(o):

	# A placeholder function to be used until the desired function
	# is assigned.

	# At the very least, clear the window.
	glClearColor(0.5, 0.5, 0.5, 0)
	glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)


class GraphicsWindowManager:

	def __init__(self):
	
		self.windows = {}
		self.activeWindow = None

	def window(self, windowName=None):

		if not windowName: # think up a default name!
			done = 0
			number = 1
			while not done:
				trialName = 'graphics'+str(number)
				if not self.windows.has_key(trialName):
					self.windows[trialName] = GraphicsWindow(trialName)
					self.activeWindow = self.windows[trialName]
					done = 1
				number = number +1
		else:
			if not self.windows.has_key(windowName):
				self.windows[windowName] = GraphicsWindow(windowName)
			self.activeWindow = self.windows[windowName]
		self.activeWindow.gwidget.activate()
			
	def nWindows(self):
		
		return len(self.windows)

	def delete(self, windowName):

		if self.windows.has_key(windowName):
			window = self.windows[windowName]
			window.top.destroy()
			del self.windows[windowName]
			self.activeWindow = None
		else:
			print "error: specified graphics window doesn't exist"


				
class GraphicsWindow:

	def __init__(self, windowName=None):

		import Ptogl # local substitute for OpenGL.Tk
		             # (to remove goofy 3d cursor effects)
					 # import is placed here since it has the side effect
					 # of creating a tk window, so delay import to
					 # a time that a window is really needed. Subsequent
					 # imports will be ignored
		if Ptogl.createdRoot:
			Tkinter._default_root.withdraw()
			Ptogl.createdRoot = 0   # clear so subsequent calls don't redo

		self.top = Tkinter.Toplevel()
		self.gwidget = Ptogl.Ptogl(self.top)
		self.gwidget.redraw = redraw
		self.top.title(windowName)
		self.gwidget.pack(side = 'top', expand=1, fill='both')
		self.top.protocol("WM_DELETE_WINDOW", self.callback)
		
		# try this hack to reset focus back to command line window
		
#		self.top.after_idle(self.callback,())
#		self.top.mainloop()

	def callback(dummyarg):
	
		pass # completely ignore attempts to close the window

# Create a module instance of the GWM object that can be referred
# by anything that imports this module. It is in effect a singleton
# object intended to be instantiated only once and be accessible from
# the module.

g = GraphicsWindowManager()


