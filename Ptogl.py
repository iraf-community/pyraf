#!/usr/bin/env python


"""
Adapted from that distributed in the Tk.__init__ file that came with
PyOpenGL. (to get rid of 3-d cursor effects among other things)

$Id$
"""

import os, toglcolors
from OpenGL.GL import *
from OpenGL.GLU import *
from Tkinter import _default_root
from Tkinter import *

# XBM file for cursor is in same directory as this module
_blankcursor = 'blankcursor.xbm'
dirname = os.path.dirname(__file__)
if os.path.isabs(dirname):
	_blankcursor = os.path.join(dirname, _blankcursor)
else:
	# change relative directory paths to absolute
	_blankcursor = os.path.join(os.getcwd(), dirname, _blankcursor)
del dirname

REDRAW_DELAY = 100 # in milliseconds
CURSOR_DELAY = 100 # in milliseconds

if _default_root is None:
	# create the initial Tk window and immediately withdraw it
	import Tkinter
	Tk().tk.call('package', 'require', 'Togl')
	_default_root = Tkinter._default_root
	_default_root.withdraw()
	del Tkinter
else:
	_default_root.tk.call('package', 'require', 'Togl')

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
toglcolors.init() # posts the togl widget create callback function

# visuals that use true colors
truevis = {
		'truecolor' : 1,
		'directcolor' : 1,
		}

class RawOpengl(Widget, Misc):
	"""Widget without any sophisticated bindings by Tom Schwaller

	Modified by Perry Greenfield to remove interactive behavior of
	original widget, to minimize redraws when backing store is
	not being used, and to invoke a software cursor.
	"""

	def __init__(self, master=None, cnf=None, **kw):
		if cnf is None: cnf = {}
		# choose rgb mode that is compatible with master widget
		top = master or _default_root
		visual = top.winfo_visual()
		if truevis.has_key(visual):
			kw['rgba'] = 1
		else:
			kw['rgba'] = 0
		Widget.__init__(self, master, 'togl', cnf, kw)
		self.rgbamode = kw['rgba']
		self.eventCount = 0
		self.cursorEventCount = 0
		# self.bind('<Map>', self.tkMap)
		self.bind('<Expose>', self.tkExpose)
		self.bind('<Configure>', self.tkExpose)
		self.ignoreNextRedraw = 1
		self.ignoreNextNRedraws = 0
		self.status = None
		self.toglStruct = toglcolors.getToglStruct()
		# Add a placeholder software cursor attribute. If it is None,
		# that means no software cursor is in effect. If it is not None,
		# then it will be used to render the cursor.
		self.__isSWCursorActive = 0
		self.__isSWCursorSleeping = 0
		self.__SWCursor = None

	def immediateRedraw(self):
		self.tk.call(self._w, 'makecurrent')
		glPushMatrix()
		self.update_idletasks()
		# need to indicate cursor is not visible before redraw, since
		# cursor sleeps are now issued by redraw. The presumption is that
		# redraw will wipe out cursor visibility, so we set it first
		if self.__isSWCursorActive: # and not self.__isSWCursorSleeping:
			# deactivate cursor for duration of redraw
			# otherwise it slows the redraw to a glacial pace
			cursorActivate = 1
			x = self.__SWCursor.lastx
			y = self.__SWCursor.lasty
			self.deactivateSWCursor()
		else:
			cursorActivate = 0
		self.redraw(self)
		if cursorActivate:
			self.activateSWCursor(x,y)
		glFlush()
		glPopMatrix()
		self.tk.call(self._w, 'swapbuffers')

	def delayedRedraw(self, eventNumber):
		if self.ignoreNextRedraw:
			self.ignoreNextRedraw = 0
			if self.ignoreNextNRedraws > 0:
				self.ignoreNextNRedraws = self.ignoreNextNRedraws - 1
			return
		if self.ignoreNextNRedraws > 0:
			self.ignoreNextNRedraws = self.ignoreNextNRedraws - 1
			return
		if eventNumber == self.eventCount:
			# No events since the event that generated this delayed call;
			# perform the redraw
			self.immediateRedraw()
		else:
			# New events, do nothing
			return

	def tkRedraw(self, *dummy):
		self.eventCount = self.eventCount + 1
		if self.eventCount > 2000000000: self.eventCount = 0 # yes, unlikely
		self.after(REDRAW_DELAY, self.delayedRedraw, self.eventCount)

	def isSWCursorActive(self):
		return self.__isSWCursorActive

	def activateSWCursor(self, x=0.5, y=0.5, type=None):
		# Load a blank cursor from a file (isn't there a better way
		# to disable a cursor in Tk?).
		# XBM file for cursor is in same directory as this module
		global _blankcursor
		self['cursor'] = '@' + _blankcursor + ' black'
		# ignore type for now since only one type of software cursor
		# is implemented
		self.__isSWCursorSleeping = 0
		self.activate()
		if not self.__isSWCursorActive:
			if not self.__SWCursor:
				self.__SWCursor = FullWindowCursor(x,y,self.rgbamode)
			self.__isSWCursorActive = 1
			self.bind("<Motion>",self.moveCursor)
		if not self.__SWCursor.isVisible:
			self.__SWCursor.draw()
			self.update_idletasks()

	def deactivateSWCursor(self):
		self.__isSWCursorSleeping = 0
		if self.__isSWCursorActive:
			self.activate()
			self.__SWCursor.erase()
			self.unbind("<Motion>")
			self.__isSWCursorActive = 0
			self['cursor'] = 'arrow'

	def SWCursorSleep(self):
		self.__isSWCursorSleeping = 1
		self.activate()
		self.__SWCursor.erase()


	def SWCursorWake(self):
		# Assumes that we don't have > 2**31 drawing operations
		# before reset, should be ok since user will die of old
		# age by then.
		self.cursorEventCount = self.cursorEventCount + 1
		self.after(CURSOR_DELAY, self.SWCursorDelayedWake, self.cursorEventCount)

	def SWCursorImmediateWake(self):
		self.cursorEventCount = 0 # reset
		self.__isSWCursorSleeping = 0
		if self.__isSWCursorActive:
			self.activate()
			self.__SWCursor.draw()


	def SWCursorDelayedWake(self, cursorEventNumber):
		if cursorEventNumber == self.cursorEventCount:
			# No cursor Wake calls since the last one that generated this
			# delayed call, restore the cursor.
			self.SWCursorImmediateWake()

	def moveCursor(self, event):
		"""Call back for mouse motion events"""
		x = event.x
		y = event.y
		winSizeX = self.winfo_width()
		winSizeY = self.winfo_height()
		ndcX = float(x)/winSizeX
		ndcY = float(winSizeY - y)/winSizeY
		self.activate()
		self.__SWCursor.moveTo(ndcX,ndcY,self.__isSWCursorSleeping)

#	def tkMap(self, *dummy):
#		print "tkMap called"
#		self.tkExpose()

#	def tkExpose(self, *dummy):
#		print "tkExpose called"
#		self.tkRedraw()

class Ptogl(RawOpengl):

	"""Subclassing the togl widget"""

	def __init__(self, master=None, cnf=None, **kw):
		"""Create an opengl widget.
		Arrange for redraws when the window is exposed or when
		it changes size."""

		if cnf is None: cnf = {}
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
		"""Set up some basic lighting (single infinite light source).

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

	def __init__(self, x, y, rgbamode):

		"""Display the cursor for the first time"""

		self.lastx = x
		self.lasty = y
		self.isVisible = 0
		self.rgbamode = rgbamode
		self.draw()

	def setPosition(self, x, y):

		self.lastx = x
		self.lasty = y

	def xorDraw(self):

		if self.rgbamode:
			glEnable(GL_COLOR_LOGIC_OP)
			glLogicOp(GL_INVERT)
		else:
			glEnable(GL_INDEX_LOGIC_OP)
			glLogicOp(GL_XOR)
			glIndex(1)
		glBegin(GL_LINES)
		glVertex2f(0,self.lasty)
		glVertex2f(1,self.lasty)
		glVertex2f(self.lastx,0)
		glVertex2f(self.lastx,1)
		glEnd()
		if self.rgbamode:
			glDisable(GL_COLOR_LOGIC_OP)
		else:
			glDisable(GL_INDEX_LOGIC_OP)
		glFlush()

	def erase(self):

		if self.isVisible:
			self.xorDraw()
			self.isVisible = 0

	def draw(self):

		if not self.isVisible:
			self.xorDraw()
			self.isVisible = 1

	def moveTo(self,x,y,hide=0):

		if (self.lastx != x) or (self.lasty != y):
			self.erase() # erase previous cursor
			self.lastx = x
			self.lasty = y
			if not hide:
				self.draw() # draw new position





