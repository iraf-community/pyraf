#!/usr/bin/env python


"""
Adapted from that distributed in the Tk.__init__ file that came with
PyOpenGL. (to get rid of 3-d cursor effects among other things)

$Id$
"""

import os
from OpenGL.GL import *
from OpenGL.GLU import *
from Tkinter import _default_root
from Tkinter import *
#import gki

eventCount = 0 #
REDRAW_DELAY = 100 # in milliseconds

if _default_root is None:
	Tk().tk.call('package', 'require', 'Togl')
	createdRoot = 1
else:
	_default_root.tk.call('package', 'require', 'Togl')
	createdRoot = 0
	
# This code is needed to avoid faults on sys.exit()
# [DAA, Jan 1998]
import sys
oldexitfunc = None
if hasattr(sys, 'exitfunc'):
	oldexitfunc = sys.exitfunc
def cleanup():
	from Tkinter import _default_root, TclError
	import Tkinter
	try: 
		if _default_root: _default_root.destroy()
	except TclError:
		pass
	Tkinter._default_root = None
	if oldexitfunc: oldexitfunc()
sys.exitfunc = cleanup
# [end DAA]

class RawOpengl(Widget, Misc):
	"""Widget without any sophisticated bindings\
	by Tom Schwaller (modified by Perry Greenfield to remove
	interactive behavior of original widget and to minimize redraws
	when backing store is not being used, and invoke a software cursor"""

	def __init__(self, master=None, cnf={}, **kw):
		Widget.__init__(self, master, 'togl', cnf, kw)
		# self.bind('<Map>', self.tkMap)
		self.bind('<Expose>', self.tkExpose)
		self.bind('<Configure>', self.tkExpose)
		self.ignoreNextRedraw = 1
		self.__isSWCursorActive = 0
		self.__SWCursor = None
		# Add a placeholder software cursor attribute. If it is None,
		# that means no software cursor is in effect. If it is not None,
		# then it will be used to render the cursor.
	
	def immediateRedraw(self):
		self.tk.call(self._w, 'makecurrent')
		glPushMatrix()
		self.update_idletasks()
		self.redraw(self)
		# If software cursor exists, render it.
		if self.__isSWCursorActive:
			self.__SWCursor.isVisible = 0 # after all, it's just been erased!
#			self.__SWCursor.draw()
		glFlush()
		glPopMatrix()
#		self.update_idletasks()
		self.tk.call(self._w, 'swapbuffers')

	def delayedRedraw(self, eventNumber):
		if self.ignoreNextRedraw:
			self.ignoreNextRedraw = 0
			return
		if eventNumber == eventCount:
			# No events since the event that generated this delayed call;
			# perform the redraw
			self.immediateRedraw()
		else:
			# New events, do nothing
			return

	def tkRedraw(self, *dummy):
		global eventCount
		eventCount = eventCount + 1
		if eventCount > 2000000000: eventCount = 0 # yes, unlikely
		self.after(REDRAW_DELAY, self.delayedRedraw, eventCount)

	def activateSWCursor(self, x=0.5, y=0.5, type=None):
		# Load a blank cursor from a file (isn't there a better way
		# to disable a cursor in Tk?).
		# XBM file for cursor is in same directory as this module
		self['cursor'] = '@' + \
				os.path.join(os.path.dirname(__file__), 'blankcursor.xbm') + \
				' black'
		# ignore type for now since only one type of software cursor
		# is implemented
		if not self.__isSWCursorActive:
			if not self.__SWCursor:
				self.__SWCursor = FullWindowCursor(x,y)
			self.__isSWCursorActive = 1
			self.bind("<Motion>",self.moveCursor)
		if not self.__SWCursor.isVisible:
			self.__SWCursor.draw()
			self.update_idletasks()

	def deactivateSWCursor(self):
		if self.__isSWCursorActive:
			self.__SWCursor.erase()
			self.unbind("<Motion>")
			self.__isSWCursorActive = 0
			self['cursor'] = 'arrow'
#			self.update_idletasks()			

	def moveCursor(self, event):
		"""Call back for mouse motion events"""
		x = event.x
		y = event.y
		winSizeX = self.winfo_width()
		winSizeY = self.winfo_height()
		ndcX = float(x)/winSizeX
		ndcY = float(winSizeY - y)/winSizeY
		self.__SWCursor.moveTo(ndcX,ndcY)
	
	def tkMap(self, *dummy):
		self.tkExpose()

	def tkExpose(self, *dummy):
		self.tkRedraw()

class Ptogl(RawOpengl):
	"""
Subclassing the togl widget
"""

	def __init__(self, master=None, cnf={}, **kw):
		"""
		Create an opengl widget.
		Arrange for redraws when the window is exposed or when
		it changes size."""
		
		apply(RawOpengl.__init__, (self, master, cnf), kw)
		self.initialised = 0

		# The _back color
		self.r_back = 1.
		self.g_back = 0.
		self.b_back = 1.

		# to save last cursor position if switching to another window
		self.lastX = None
		self.lastY = None

		# Basic bindings for the virtual trackball
#self.bind('<Map>', self.tkMap)
		self.bind('<Expose>', self.tkExpose)
		self.bind('<Configure>', self.tkExpose)

	def activate(self):
		"""Cause this Opengl widget to be the current destination for drawing."""

		self.tk.call(self._w, 'makecurrent')

		# This should almost certainly be part of some derived class.
		# But I have put it here for convenience.

	def basic_lighting(self):
		"""\
		Set up some basic lighting (single infinite light source).

		Also switch on the depth buffer."""

		self.activate()
		light_position = (1, 1, 1, 0);
		glLightf(GL_LIGHT0, GL_POSITION, light_position);
		glEnable(GL_LIGHTING);
		glEnable(GL_LIGHT0);
		glDepthFunc(GL_LESS);
		glEnable(GL_DEPTH_TEST);
		glMatrixMode(GL_MODELVIEW);
		glLoadIdentity()

	def report_opengl_errors(message = "OpenGL error:"):
		"""Report any opengl errors that occured while drawing."""

		while 1:
			err_value = glGetError()
			if not err_value: break     
			print message, gluErrorString(err_value)

	def set_background(self, r, g, b):
		"""Change the background colour of the widget."""

		self.r_back = r
		self.g_back = g
		self.b_back = b

		self.tkRedraw()

	def tkMap(self, *dummy):
		"""Cause the opengl widget to redraw itself."""

		self.tkExpose()

	def tkExpose(self, *dummy):
		"""Redraw the widget.
		Make it active, update tk events, call redraw procedure and
		swap the buffers.  Note: swapbuffers is clever enough to
		only swap double buffered visuals."""

		self.activate()
		if not self.initialised:
			self.basic_lighting()
			self.initialised = 1
		self.tkRedraw()

class FullWindowCursor:

	"""This implements a  full window crosshair cursor"""
	# Perhaps this should inherit from an abstract Cursor class eventually
	# Coordinates are in IRAF NDC coordinates (same as OpenGL for now,
	# but if we use OpenGL coordinate transforms to implement zooming
	# and translation, they won't be.

	def __init__(self, x, y):

		"""Display the cursor for the first time"""

		self.lastx = x
		self.lasty = y
		self.isVisible = 0
 		self.draw()

	def setPosition(self, x, y):

		self.lastx = x
		self.lasty = y
		
	def xorDraw(self):

		glEnable(GL_COLOR_LOGIC_OP)
		glLogicOp(GL_INVERT)
		glBegin(GL_LINES)
#		glColor3f(1,1,1)
		glVertex2f(0,self.lasty)
		glVertex2f(1,self.lasty)
		glVertex2f(self.lastx,0)
		glVertex2f(self.lastx,1)
		glEnd()
		glDisable(GL_COLOR_LOGIC_OP)
		glFlush()

	def erase(self):

		if self.isVisible:
			self.xorDraw()
			self.isVisible = 0

	def draw(self):

		if not self.isVisible:
			self.xorDraw()
			self.isVisible = 1

	def moveTo(self,x,y):

		if (self.lastx != x) or (self.lasty != y):
			self.erase() # erase previous cursor
			self.lastx = x
			self.lasty = y
			self.draw() # draw new position


	
		

