"""
OpenGL implementation of the gki kernel class

$Id$
"""

import Numeric, sys, string, wutil
import Tkinter, msgiobuffer
from OpenGL.GL import *
import toglcolors
import gki, openglgcur, opengltext, irafgwcs
from irafglobals import IrafError

import gwm # needed only for delete function

nIrafColors = 16

_errorMessageCount = 0
MAX_ERROR_COUNT = 3

def errorMessage(text):
	"""a way of truncating the number of error messages produced
	in a plot. This really should be done at the gki level, but would
	require folding the function table members into the class itself,
	so this less than ideal approach is being taken for now"""
	global _errorMessageCount
	if _errorMessageCount < MAX_ERROR_COUNT:
		print text
		_errorMessageCount = _errorMessageCount + 1
	elif _errorMessageCount == MAX_ERROR_COUNT:
		print "\nAdditional graphics error messages suppressed"
		_errorMessageCount = _errorMessageCount + 1


#*****************************************************************

standardWarning = """
The graphics kernel for IRAF tasks has just recieved a metacode
instruction it never expected to see. Please inform the STSDAS
group of this occurance"""

standardNotImplemented = """
You have tried to run an IRAF task which requires graphics kernel
facility not implemented in the Python graphics kernel for IRAF tasks"""

#**********************************************************************


class GkiOpenGlKernel(gki.GkiKernel, wutil.FocusEntity):

	"""OpenGL graphics kernel implementation"""

	def __init__(self, windowName):

		gki.GkiKernel.__init__(self)
		self.stdin = None
		self.stdout = None
		self.stderr = None
		self.name = 'OpenGL'

		import Ptogl # local substitute for OpenGL.Tk
					 # (to remove goofy 3d cursor effects)
					 # import is placed here since it has the side effect
					 # of creating a tk window, so delay import to
					 # a time that a window is really needed. Subsequent
					 # imports will be ignored

		self.irafGkiConfig = IrafGkiConfig()
		self.windowName = windowName

		self.top = Tkinter.Toplevel(visual='best')
		self.gwidget = Ptogl.Ptogl(self.top,width=600,height=420)
		self.colorManager = glColorManager(self.irafGkiConfig.defaultColors,
				self.gwidget.rgbamode)
		self.gwidget.status = msgiobuffer.MsgIOBuffer(self.top, width=600)
		self.gwidget.redraw = self.redraw
		self.top.title(windowName)
		self.gwidget.status.msgIO.pack(side=Tkinter.BOTTOM, fill = Tkinter.X)
		self.gwidget.pack(side = 'top', expand=1, fill='both')
		self.top.protocol("WM_DELETE_WINDOW", self.gwdestroy)
		self.gwidget.firstPlotDone = 0
		self.gwidget.interactive = 0

		self.colorManager.setColors(self.gwidget)
		self.glBuffer = GLBuffer()
		self.wcs = None
		self.colors = IrafColors(self)
		self.linestyles = IrafLineStyles()
		self.hatchfills = IrafHatchFills()
		self.textAttributes = opengltext.TextAttributes()
		self.lineAttributes = LineAttributes()
		self.fillAttributes = FillAttributes()
		self.markerAttributes = MarkerAttributes()

		windowID = self.gwidget.winfo_id()
		wutil.setBackingStore(windowID)
		self.gcursor = openglgcur.Gcursor(self)

	def activate(self):
		"""Make this the active window"""
		self.gwidget.activate()

	def flush(self):
		try:
			self.gwidget.update_idletasks()
		except Tkinter.TclError:
			pass

	def hasFocus(self):
		"""Returns true if this window currently has focus"""
		return  wutil.getTopID(wutil.getWindowID()) == \
			wutil.getTopID(self.getWindowID())

	def setDrawingColor(self, irafColorIndex):
		self.colorManager.setDrawingColor(irafColorIndex)

	def taskDoneCleanup(self):
		"""Hack to prevent the double redraw after first Tk plot"""
		gwin = self.gwidget
		if gwin and (not gwin.firstPlotDone) and wutil.hasGraphics:
			# this is a hack to prevent the double redraw on first plots
			# (when they are not interactive plots). This should be done
			# better, but it appears to work most of the time.
			if not gwin.interactive:
				gwin.ignoreNextNRedraws = 2
			gwin.firstPlotDone = 1

	# the following methods implement the FocusEntity interface
	# used by wutil.FocusController

	def saveCursorPos(self):

		"""save current position if window has focus and cursor is
		in window, otherwise do nothing"""

		# first see if window has focus
		if not self.hasFocus():
			return

		gwin = self.gwidget
		posdict = wutil.getPointerPosition(gwin.winfo_id())
		if posdict:
			x = posdict['win_x']
			y = posdict['win_y']
		else:
			return
		maxX = gwin.winfo_width()
		maxY = gwin.winfo_height()
		if x < 0 or y < 0 or x >= maxX or y >= maxY:
			return
		gwin.lastX = x
		gwin.lastY = y

	def forceFocus(self):

		# only force focus if window is viewable
		if not wutil.isViewable(self.top.winfo_id()):
			return
		# warp cursor
		# if no previous position, move to center
		gwin = self.gwidget
		if not gwin.lastX:
			gwin.lastX = gwin.winfo_width()/2
			gwin.lastY = gwin.winfo_height()/2
		wutil.moveCursorTo(gwin.winfo_id(),gwin.lastX,gwin.lastY)
		gwin.focus_force()

	def getWindowID(self):

		return self.gwidget.winfo_id()

	# end of FocusEntity methods

	def getWindowName(self):

		return self.windowName

	def gwdestroy(self):

		# delete self-references to allow this to be reclaimed
		del self.gcursor
		gwm.delete(self.windowName)
		# protect against bugs that try to access deleted object
		self.gwidget = None

	# here's where GkiKernel methods start

	def _glAppend(self, opcode, *args):

		"""append a 2-tuple (gl_function, args) to the glBuffer"""
		if opcode == gki.GKI_CLEARWS:
			self.clear()
		glfunc = glFunctionTable[opcode]
		if glfunc is not None:
			# add the window to the args
			self.glBuffer.append((glfunc,(self,) + args))

	def clear(self, win=None):
		if not win:
			win = self.gwidget
		self.gkibuffer.reset()
		self.glBuffer.reset()
		self.wcs = None
		win.immediateRedraw()
		win.status.updateIO(text=" ")

	def translate(self, gkiMetacode):

		gki.gkiTranslate(gkiMetacode, self.functionTable)
		win = self.gwidget
		glbuf = self.glBuffer
		# render new stuff immediately
		function, args = glbuf.getNextCall()
		while function:
			apply(function, args)
			function, args = glbuf.getNextCall()
		glFlush()

	def control_openws(self, arg):

		global _errorMessageCount
		_errorMessageCount = 0
		mode = arg[0]
		win = self.gwidget
		ta = self.textAttributes
		ta.setFontSize(self)
		self.raiseWindow()
		# redirect stdin & stdout to status line
		self.stdout = StatusLine(self.gwidget, self.windowName)
		self.stdin = self.stdout
		# disable stderr while graphics is active (to supress xgterm gui
		# messages)
		self.stderr = DevNullError()
		if mode == 5:
			# clear the display
			self.gkibuffer.reset()
			self.glBuffer.reset()
			self.wcs = None
			win.immediateRedraw()
		elif mode == 4:
			# append, i.e., do nothing!
			pass
		elif mode == 6:
			# Tee mode (?), ignore for now
			pass

	def raiseWindow(self):
		if self.top.state() != 'normal':
			self.top.deiconify()
		self.top.tkraise()

	def control_clearws(self, arg):
		# apparently this control routine is not used???
		self.clear()

	def control_reactivatews(self, arg):

		global _errorMessageCount
		_errorMessageCount = 0
		self.raiseWindow()

		if not self.stdout:
			# redirect stdout if not already
			self.stdout = StatusLine(self.gwidget, self.windowName)
			self.stdin = self.stdout
		if not self.stderr:
			self.stderr = DevNullError()

	def control_deactivatews(self, arg):
		if self.stdout:
			self.stdout.close()
			self.stdout = None
			self.stdin = None
		if self.stderr:
			self.stderr.close()
			self.stderr = None

	def control_setwcs(self, arg):

		win = self.gwidget
		self.wcs = irafgwcs.IrafGWcs(arg)

	def control_getwcs(self, arg):

		win = self.gwidget
		if not self.wcs:
			self.errorMessage("Error: can't append to a nonexistent plot!")
			raise IrafError
		if self.returnData:
			self.returnData = self.returnData + self.wcs.pack()
		else:
			self.returnData = self.wcs.pack()

	def control_closews(self, arg):

		win = self.gwidget
		win.deactivateSWCursor()  # turn off software cursor
		if self.stdout:
			self.stdout.close()
			self.stdout = None
			self.stdin = None
		if self.stderr:
			self.stderr.close()
			self.stderr = None
		wutil.focusController.restoreLast()

	# special methods that go into the function tables

	def gki_clearws(self, arg):
		self._glAppend(gki.GKI_CLEARWS,0)

	def gki_cancel(self, arg):
		self.gki_clearws(arg)

	def gki_flush(self, arg):
		self._glAppend(gki.GKI_FLUSH,arg)

	def gki_polyline(self, arg):
		self._glAppend(gki.GKI_POLYLINE, gki.ndc(arg[1:]))

	def gki_polymarker(self, arg):
		self._glAppend(gki.GKI_POLYMARKER, gki.ndc(arg[1:]))

	def gki_text(self, arg):

		x = gki.ndc(arg[0])
		y = gki.ndc(arg[1])
		text = arg[3:].astype(Numeric.Int8).tostring()
		self._glAppend(gki.GKI_TEXT, x, y, text)

	def gki_fillarea(self, arg): 

		self._glAppend(gki.GKI_FILLAREA, gki.ndc(arg[1:]))

	def gki_putcellarray(self, arg): 

		errorMessage(standardNotImplemented)

	def gki_setcursor(self, arg):

		cursorNumber = arg[0]
		x = arg[1]/gki.GKI_MAX
		y = arg[2]/gki.GKI_MAX
		self._glAppend(gki.GKI_SETCURSOR, cursorNumber, x, y)

	def gki_plset(self, arg):

		linetype = arg[0]
		linewidth = arg[1]/gki.GKI_FLOAT_FACTOR
		color = arg[2]
		self._glAppend(gki.GKI_PLSET, linetype, linewidth, color)

	def gki_pmset(self, arg):

		marktype = arg[0]
		marksize = arg[1]/gki.GKI_MAX
		color = arg[2]
		self._glAppend(gki.GKI_PMSET, marktype, marksize, color)

	def gki_txset(self, arg):

		charUp = float(arg[0])
		charSize = arg[1]/gki.GKI_FLOAT_FACTOR
		charSpace = arg[2]/gki.GKI_FLOAT_FACTOR
		textPath = arg[3]
		textHorizontalJust = arg[4]
		textVerticalJust = arg[5]
		textFont = arg[6]
		textQuality = arg[7]
		textColor = arg[8]
		self._glAppend(gki.GKI_TXSET, charUp, charSize, charSpace, textPath,
			textHorizontalJust, textVerticalJust, textFont,
			textQuality, textColor)

	def gki_faset(self, arg):

		fillstyle = arg[0]
		color = arg[1]
		self._glAppend(gki.GKI_FASET, fillstyle, color)

	def gki_getcursor(self, arg):

		print "GKI_GETCURSOR"
		raise standardNotImplemented
		 
	def gki_getcellarray(self, arg):

		print "GKI_GETCELLARRAY"
		raise standardNotImplemented

	def gki_unknown(self, arg): 

		errorMessage("GKI_UNKNOWN:\n"+standardWarning)

	def gki_escape(self, arg):
		print "GKI_ESCAPE"

	def gki_setwcs(self, arg):
		pass #print "GKI_SETWCS"

	def gki_getwcs(self, arg):
		print "GKI_GETWCS"


	def redraw(self, o=None):

		# Note argument is not needed because we only get redraw
		# events for our own gwidget
		ta = self.textAttributes
		ta.setFontSize(self)
		cm = self.colorManager
		if cm.rgbamode:
			glClearColor(0,0,0,0)
		else:
			glClearIndex(cm.indexmap[0])
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		glOrtho(0,1,0,1,-1,1)
		glDisable(GL_LIGHTING)
		glDisable(GL_DITHER)
		glShadeModel(GL_FLAT)

		for (function, args) in self.glBuffer.get():
			apply(function, args)
		glFlush()

	def gcur(self): return self.gcursor()


class DevNullError:

	def __init__(self):
		pass
	def write(self, text):
		pass
	def flush(self):
		pass
	def close(self):
		pass

class StatusLine:

	def __init__(self, window, name):
		self.graphicsWindow = window
		self.windowName = name
	def readline(self):
		"""Shift focus to graphics, read line from status, restore focus"""
		wutil.focusController.setFocusTo(self.windowName,always=1)
		rv = self.graphicsWindow.status.readline()
		wutil.focusController.restoreLast()
		return rv
	def write(self, text):
		self.graphicsWindow.status.updateIO(text=string.strip(text))
	def flush(self):
		self.graphicsWindow.update_idletasks()
	def close(self):
		# clear status line
		self.graphicsWindow.status.updateIO(text="")
	def isatty(self):
		return 1
	def fileno(self):
		return sys.__stdout__.fileno()

class glColorManager:

	"""Encapsulates the details of setting the graphic's windows colors.

	Needed since we may be using rgba mode or color index mode and we
	do not want any of the graphics programs to have to deal with the
	mode being used. The current design applies the same colors to all
	graphics windows for color index mode (but it isn't required).
	An 8-bit display depth results in color index mode, otherwise rgba
	mode is used. In color index mode we attempt to allocate pairs of
	color indices (even, odd) so that xor mode on the least sig bit of
	the index results in ideal color flipping. If no new colors are
	available, we take what we can get. We do not attempt to get a
	private colormap.
	"""

	def __init__(self, defaultColors, rgbamode):

		self.colorset = [None]*nIrafColors
		self.indexmap = [None]*nIrafColors
		self.rgbamode = rgbamode
		for cind in xrange(len(defaultColors)):
			self.defineColor(cind,
				defaultColors[cind][0],
				defaultColors[cind][1],
				defaultColors[cind][2])
		# call setColors to allocate colors after widget is created

	def defineColor(self, colorindex, red, green, blue):
		"""Color list consists of color triples. This method only
		sets up the desired color set, it doesn't allocate any colors
		from the colormap in color index mode."""
		self.colorset[colorindex] = (red, green, blue)

	def setColors(self, widget):
		"""Does nothing in rgba mode, allocates colors in index mode"""
		if self.rgbamode:
			return
		for i in xrange(len(self.indexmap)):
			self.indexmap[i] = toglcolors.AllocateColor(widget.toglStruct,
							   self.colorset[i][0],
							   self.colorset[i][1],
							   self.colorset[i][2])

	def setDrawingColor(self, irafColorIndex):
		"""Apply the specified iraf color to the current OpenGL drawing
		state using the appropriate mode."""
		if self.rgbamode:
			color = self.colorset[irafColorIndex]
			glColor3f(color[0], color[1], color[2])
		else:
			glIndex(self.indexmap[irafColorIndex])


#***********************************************************
# These are the routines for the innermost loop in the redraw
# function.  They are supposed to be stripped down to make
# redraws as fast as possible.  (Still could be improved.)

def gl_flush(win, arg):
	glFlush()

def gl_polyline(win, vertices):

	gwidget = win.gwidget
	# First, set all relevant attributes
	cursorActive =  gwidget.isSWCursorActive()
	if cursorActive:
		gwidget.SWCursorSleep()
	la = win.lineAttributes
	glPointSize(1.0)
	glDisable(GL_LINE_SMOOTH)
	glLineWidth(la.linewidth)
	stipple = 0
	clear = 0
	if la.linestyle == 0: clear = 1 # "clear" linestyle, don't draw!
	elif la.linestyle == 1: pass # solid line
	elif 2 <= la.linestyle < len(win.linestyles.patterns):
		glEnable(GL_LINE_STIPPLE)
		stipple = 1
		glLineStipple(1,win.linestyles.patterns[la.linestyle])
	glBegin(GL_LINE_STRIP)
	if not clear:
		win.colorManager.setDrawingColor(la.color)
	else:
		win.colorManager.setDrawingColor(0)
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()
	if stipple:
		glDisable(GL_LINE_STIPPLE)
	if cursorActive:
		gwidget.SWCursorWake()

def gl_polymarker(win, vertices):

	gwidget = win.gwidget
	# IRAF only implements points for poly marker, that makes it real simple
	cursorActive = gwidget.isSWCursorActive()
	ma = win.markerAttributes
	clear = 0
	glPointSize(1)
	if not clear:
		win.colorManager.setDrawingColor(ma.color)
	else:
		win.colorManager.setDrawingColor(0)
	if cursorActive:
		gwidget.SWCursorSleep()
	glBegin(GL_POINTS)
	glVertex(Numeric.reshape(vertices, (len(vertices)/2,2)))
	glEnd()
	if cursorActive:
		gwidget.SWCursorWake()

def gl_text(win, x, y, text):

	gwidget = win.gwidget
	cursorActive =  gwidget.isSWCursorActive()
	if cursorActive:
		gwidget.SWCursorSleep()
	opengltext.softText(win,x,y,text)
	if cursorActive:
		gwidget.SWCursorWake()

def gl_fillarea(win, vertices):

	gwidget = win.gwidget
	cursorActive =  gwidget.isSWCursorActive()
	if cursorActive:
		gwidget.SWCursorSleep()
	fa = win.fillAttributes
	clear = 0
	polystipple = 0
	if fa.fillstyle == 0: # clear region
		clear = 1
		glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
	elif fa.fillstyle == 1: # hollow
		glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
	elif fa.fillstyle >= 2: # solid
		glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
#	elif fa.fillstyle > 2: # hatched
# This is commented out since PyOpenGL does not currently support
# glPolygonStipple!
#		if fa.fillstyle > 6: fa.fillstyle = 6
#		t = win.hatchfills
#		print t
#		tp = t.patterns
#		print tp, "patterns"
#		fill = win.hatchfills.patterns[fa.fillstyle]
#		print fill, "fill"
#		polystipple = 1
#		glEnable(GL_POLYGON_STIPPLE)
#		glPolygonStipple(fill)
	if not clear:
		win.colorManager.setDrawingColor(fa.color)
	else:
		win.colorManager.setDrawingColor(0)
#		glColor3f(0.,0.,0.)
	# not a simple rectangle
	glBegin(GL_POLYGON)
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()
	if polystipple:
		glDisable(GL_POLYGON_STIPPLE)
	if cursorActive:
		gwidget.SWCursorWake()

def gl_setcursor(win, cursornumber, x, y):

	gwidget = win.gwidget
	# wutil.MoveCursorTo uses 0,0 <--> upper left, need to convert
	sy = gwidget.winfo_height() - y
	sx = x
	wutil.moveCursorTo(gwidget.winfo_id(), sx, sy)

def gl_plset(win, linestyle, linewidth, color):

	win.lineAttributes.set(linestyle, linewidth, color)

def gl_pmset(win, marktype, marksize, color):

	win.markerAttributes.set(marktype, marksize, color)

def gl_txset(win, charUp, charSize, charSpace, textPath, textHorizontalJust,
			 textVerticalJust, textFont, textQuality, textColor):

	win.textAttributes.set(charUp, charSize, charSpace,
		textPath, textHorizontalJust, textVerticalJust, textFont,
		textQuality, textColor)

def gl_faset(win, fillstyle, color):

	win.fillAttributes.set(fillstyle, color)

glFunctionTable = (gki.GKI_MAX_OP_CODE+1)*[None]
glFunctionTable[gki.GKI_FLUSH] = gl_flush
glFunctionTable[gki.GKI_POLYLINE] = gl_polyline
glFunctionTable[gki.GKI_POLYMARKER] = gl_polymarker
glFunctionTable[gki.GKI_TEXT] = gl_text
glFunctionTable[gki.GKI_FILLAREA] = gl_fillarea
glFunctionTable[gki.GKI_SETCURSOR] = gl_setcursor
glFunctionTable[gki.GKI_PLSET] = gl_plset
glFunctionTable[gki.GKI_PMSET] = gl_pmset
glFunctionTable[gki.GKI_TXSET] = gl_txset
glFunctionTable[gki.GKI_FASET] = gl_faset


#********************************************

class GLBuffer:

	"""implement a buffer for GL commands which allocates memory in blocks
	so that a new memory allocation is not needed everytime functions are
	appended"""

	INCREMENT = 500

	def __init__(self):

		self.buffer = None
		self.bufferSize = 0
		self.bufferEnd = 0 
		self.nextTranslate = 0

	def reset(self):

		# discard everything up to nextTranslate pointer

		newEnd = self.bufferEnd - self.nextTranslate
		if newEnd > 0:
			self.buffer[0:newEnd] = self.buffer[self.nextTranslate:self.bufferEnd]
			self.bufferEnd = newEnd
		else:
			self.buffer = None
			self.bufferSize = 0
			self.bufferEnd = 0
		self.nextTranslate = 0

	def append(self, funcargs):

		# append a single (function,args) tuple to the list

		if self.bufferSize < self.bufferEnd + 1:
			# increment buffer size and copy into new array
			self.bufferSize = self.bufferSize + self.INCREMENT
			newbuffer = self.bufferSize*[None]
			if self.bufferEnd > 0:
				newbuffer[0:self.bufferEnd] = self.buffer[0:self.bufferEnd]
			self.buffer = newbuffer
		self.buffer[self.bufferEnd] = funcargs
		self.bufferEnd = self.bufferEnd + 1

	def get(self):

		if self.buffer:
			return self.buffer[0:self.bufferEnd]
		else:
			return []

	def getNextCall(self):
		"""Return a tuple with (function, args) for next call in buffer.
		Returns (None,None) on end-of-buffer."""
		ip = self.nextTranslate
		if ip < self.bufferEnd:
			retval = self.buffer[ip]
			self.nextTranslate = ip + 1
			return retval
		else:
			return (None, None)

class IrafGkiConfig:

	"""Holds configurable aspects of IRAF plotting behavior"""

	def __init__(self):

		# All set to constants for now, eventually allow setting other
		# values

		# h = horizontal font dimension, v = vertical font dimension

		# ratio of font height to width
		self.fontAspect = 42./27.
		self.fontMax2MinSizeRatio = 4.
		# Empirical constants for font sizes; try xterm fractions for now
		self.UnitFontHWindowFraction = 1./100
		self.UnitFontVWindowFraction = 1./35
		# minimum unit font size in pixels
		self.minUnitHFontSize = 7.
		self.minUnitVFontSize = self.minUnitHFontSize * self.fontAspect
		# maximum unit font size in pixels
		self.maxUnitHFontSize = \
			self.minUnitHFontSize * self.fontMax2MinSizeRatio
		self.maxUnitVFontSize = self.maxUnitHFontSize * self.fontAspect
		# offset constants to match iraf's notion of where 0,0 is relative
		# to the coordinates of a character
		self.vFontOffset = 0.0
		self.hFontOffset = 0.0
		# font sizing switches
		self.isFixedAspectFont = 1
		self.hasMinPixSizeUnitFont = 1
		self.hasMaxPixSizeUnitFont = 1
		# The following is a list of rgb tuples (0.0-1.0 range) for the
		# default IRAF set of colors
		self.defaultColors = [
			(0.,0.,0.),  # black
			(1.,1.,1.),  # white
			(1.,0.,0.),  # red
			(0.,1.,0.),  # green
			(0.,0.,0.1), # blue
			(0.,1.,1.),  # cyan
			(1.,1.,0.),  # yellow
			(1.,0.,1.),  # magenta
			(1.,1.,1.),  # white
			# (0.32,0.32,0.32),  # gray32
			(0.18,0.31,0.31),  # IRAF blue-green
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
		]

# old colors
#			(1.,0.5,0.), # coral
#			(0.7,0.19,0.38), # maroon
#			(1.,0.65,0.), # orange
#			(0.94,0.9,0.55), # khaki
#			(0.85,0.45,0.83), # orchid
#			(0.25,0.88,0.82), # turquoise
#			(0.91,0.53,0.92), # violet
#			(0.96,0.87,0.72) # wheat

	def fontSize(self, gwidget):

		"""Determine the unit font size for the given setup in pixels.
		The unit size refers to the horizonal size of fixed width characters
		(allow for proportionally sized fonts later?).

		Basically, if font aspect is not fixed, the unit font size is
		proportional to the window dimension (for v and h independently),
		with the exception that if min or max pixel sizes are enabled,
		they are 'clipped' at the specified value. If font aspect is fixed,
		then the horizontal size is the driver if the window is higher than
		wide and vertical size for the converse.
		"""

		hWin = gwidget.winfo_width()
		vWin = gwidget.winfo_height()
		hSize = hWin * self.UnitFontHWindowFraction
		vSize = vWin * self.UnitFontVWindowFraction*self.fontAspect
		if not self.isFixedAspectFont:
			if self.hasMinPixSizeUnitFont:
				hSize = max(hSize,self.minUnitHFontSize)
				vSize = max(vSize,self.minUnitVFontSize)
			if self.config.hasMaxPixSizeUnitFont:
				hSize = min(hSize,self.maxUnitHFontSize)
				vSize = min(hSize,self.maxUnitVFontSize)
			fontAspect = vSize/hSize
		else:
			hSize = min(hSize,vSize/self.fontAspect)
			if self.hasMinPixSizeUnitFont:
				hSize = max(hSize,self.minUnitHFontSize)
			if self.hasMaxPixSizeUnitFont:
				hSize = min(hSize,self.maxUnitHFontSize)
			vSize = hSize * self.fontAspect
			fontAspect = self.fontAspect
		return (hSize, fontAspect)

	def getIrafColors(self):

		return self.defaultColors


class IrafColors:

	def __init__(self, win):

		self.defaultColors = win.irafGkiConfig.getIrafColors()

	def toRGB(self, irafcolor):

		if not (0 <= irafcolor < len(self.defaultColors)):
			print "WARNING: Iraf color out of legal range (1-%d)" % \
				(len(self.defaultColors),)
			irafcolor = 1
		return self.defaultColors[irafcolor]

class IrafLineStyles:

	def __init__(self):

		self.patterns = [0x0000,0xFFFF,0x00FF,0x5555,0x33FF]

class IrafHatchFills:

	def __init__(self):

		# Each fill pattern is a 32x4 ubyte array (represented as 1-d).
		# These are computed on initialization rather than using a
		# 'data' type initialization since they are such simple patterns.
		# these arrays are stored in a pattern list. Pattern entries
		# 0-2 should never be used since they are not hatch patterns.

		# so much for these, currently PyOpenGL does not support
		# glPolygonStipple()! But adding it probably is not too hard.

		self.patterns = [None]*7
		# pattern 3, vertical stripes
		p = Numeric.zeros(128,Numeric.Int8)
		p[0:4] = [0x92,0x49,0x24,0x92]
		for i in xrange(31):
			p[(i+1)*4:(i+2)*4] = p[0:4]
		self.patterns[3] = p
		# pattern 4, horizontal stripes
		p = Numeric.zeros(128,Numeric.Int8)
		p[0:4] = [0xFF,0xFF,0xFF,0xFF]
		for i in xrange(10):
			p[(i+1)*12:(i+1)*12+4] = p[0:4]
		self.patterns[4] = p
		# pattern 5, close diagonal striping
		p = Numeric.zeros(128,Numeric.Int8)
		p[0:12] = [0x92,0x49,0x24,0x92,0x24,0x92,0x49,0x24,0x49,0x24,0x92,0x49]
		for i in xrange(9):
			p[(i+1)*12:(i+2)*12] = p[0:12]
		p[120:128] = p[0:8]
		self.patterns[5] = p
		# pattern 6, diagonal stripes the other way
		p = Numeric.zeros(128,Numeric.Int8)
		p[0:12] = [0x92,0x49,0x24,0x92,0x49,0x24,0x92,0x49,0x24,0x92,0x49,0x24]
		for i in xrange(9):
			p[(i+1)*12:(i+2)*12] = p[0:12]
		p[120:128] = p[0:8]
		self.patterns[6] = p


class LineAttributes:

	def __init__(self):

		self.linestyle = 1
		self.linewidth = 1.0
		self.color = 1

	def set(self, linestyle, linewidth, color):

		self.linestyle = linestyle
		self.linewidth = linewidth
		self.color = color

class FillAttributes:

	def __init__(self):

		self.fillstyle = 1
		self.color = 1

	def set(self, fillstyle, color):

		self.fillstyle = fillstyle
		self.color = color

class MarkerAttributes:

	def __init__(self):

		# the first two attributes are not currently used in IRAF, so ditch'em
		self.color = 1

	def set(self, markertype, size, color):

		self.color = color
