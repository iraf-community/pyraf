"""
OpenGL implementation of the gki kernel class

$Id$
"""

from OpenGL.GL import *
import gki
from irafglobals import IrafError
import Numeric
import gwm
import openglgcur
import irafgwcs
import wutil
import sys
import string
import opengltext

# open /dev/null for general availability
devNull = open('/dev/null','w')
def_stderr = sys.stderr

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
			
class IrafPlot:

	"""An object that groups all the data items needed to support
    IRAF gki graphics. This object is expected to be an attribute of
	the togl widget used to display the graphics. Each togl widget
	should have its own copy of this class object"""

	def __init__(self):

		self.glBuffer = GLBuffer()
		self.gkiBuffer = gki.GkiBuffer()
		self.wcs = None
		self.kernel = None
		self.colors = IrafColors()
		self.linestyles = IrafLineStyles()
		self.hatchfills = IrafHatchFills()
		self.textAttributes = opengltext.TextAttributes()
		self.lineAttributes = LineAttributes()
		self.fillAttributes = FillAttributes()
		self.markerAttributes = MarkerAttributes()

def nullAction(arg): pass

class GkiOpenGlKernel(gki.GkiKernel):

	def __init__(self):

		gki.GkiKernel.__init__(self)
		self.controlFunctionTable = [self.controlDefault]*(gki.GKI_MAX_OP_CODE+1)
		self.controlFunctionTable[gki.GKI_OPENWS] = self.openWS
		self.controlFunctionTable[gki.GKI_CLOSEWS] = self.closeWS
		self.controlFunctionTable[gki.GKI_REACTIVATEWS] = self.reactivateWS
		self.controlFunctionTable[gki.GKI_DEACTIVATEWS] = self.deactivateWS
		self.controlFunctionTable[gki.GKI_CLEARWS] = self.clearWS
		self.controlFunctionTable[gki.GKI_SETWCS] = self.setWCS
		self.controlFunctionTable[gki.GKI_GETWCS] = self.getWCS
		self.stdin = None
		self.stdout = None
		self.stderr = None
		self.gcursor = openglgcur.Gcursor()
		self.name = 'OpenGL'

	def _gkiAction(self, opcode, arg):

		"""append a 2-tuple (gl_function, args) to the glBuffer"""
		win = gwm.getActiveWindow()
		if opcode == gki.GKI_CLEARWS:
			win.iplot.gkiBuffer.reset()
			win.iplot.glBuffer.reset()
			win.iplot.wcs = None
			win.immediateRedraw()
			win.status.updateIO(text=" ")
		glarg = (glFunctionTable[opcode],arg)
		win.iplot.glBuffer.append(glarg)

	def getBuffer(self):

		if gwm.getActiveWindow():
			win = gwm.getActiveWindow()
			return win.iplot.gkiBuffer
		else:
			print "ERROR: no IRAF plot window active"
			raise IrafError
	
	def control(self, gkiMetacode):

		gki.gkiTranslate(gkiMetacode, self.controlFunctionTable,
						 nullAction)
		return self.returnData

	def translate(self, gkiMetacode, fTable):

		gki.gkiTranslate(gkiMetacode, fTable, self._gkiAction)
		win = gwm.getActiveWindow()
		glbuf = win.iplot.glBuffer
		# render new stuff immediately
		function, args = glbuf.getNextCall()
		while function:
			apply(function, args)
			function, args = glbuf.getNextCall()
		glFlush()

	def controlDefault(self, dummy, arg):

		# This function should never be called.
		print "controlDefault called"

	def controlDoNothing(self, dummy, arg):
		pass

	def openWS(self, dummy, arg):

		global _errorMessageCount
		_errorMessageCount = 0
		mode = arg[0]
		# first see if there are any graphics windows, if not, create one 
		win = gwm.getActiveWindow()
		if win == None:
			gwm.window()
			win = gwm.getActiveWindow()
		win.redraw = self.redraw
		if not hasattr(win,"iplot"):
			win.iplot = IrafPlot()
		ta = win.iplot.textAttributes
		ta.setFontSize()
		gwm.raiseActiveWindow()
		# redirect stdin & stdout to status line
		self.stdout = StatusLine()
		self.stdin = self.stdout
		# disable stderr while graphics is active (to supress xgterm gui
		# messages)
		self.stderr = DevNullError()
		if mode == 5:
			# clear the display
			win.iplot.gkiBuffer.reset()
			win.iplot.glBuffer.reset()
			win.iplot.wcs = None
			win.immediateRedraw()
		elif mode == 4:
			# append, i.e., do nothing!
			pass
		elif mode == 6:
			# Tee mode (?), ignore for now
			pass
			
	def clearWS(self, dummy, arg):

		# apparently this control routine is not used???

		win = gwm.getActiveWindow()
		win.iplot.gkiBuffer.reset()
		win.iplot.glBuffer.reset()
		win.iplot.wcs = None
		win.immediateRedraw()

	def reactivateWS(self, dummy, arg):

		global _errorMessageCount
		_errorMessageCount = 0
		gwm.raiseActiveWindow()

		if not self.stdout:
			# redirect stdout if not already
			self.stdout = StatusLine()  
			self.stdin = self.stdout
		if not self.stderr:
			self.stderr = DevNullError()
		
	def deactivateWS(self, dummy, arg):
		if self.stdout:
			self.stdout.close()
			self.stdout = None
			self.stdin = None
		if self.stderr:
			self.stderr.close()
			self.stderr = None

	def setWCS(self, dummy, arg):

		#__main__.wcs = arg # pass it up to play with
		win = gwm.getActiveWindow()
		win.iplot.wcs = irafgwcs.IrafGWcs(arg)

	def getWCS(self, dummy, arg):

		win = gwm.getActiveWindow()
		if not win.iplot.wcs:
			self.errorMessage("Error: can't append to a nonexistent plot!")
			raise IrafError
		if self.returnData:
			self.returnData = self.returnData + win.iplot.wcs.pack()
		else:
			self.returnData = win.iplot.wcs.pack()

	def closeWS(self, dummy, arg):

		win = gwm.getActiveWindow()
		win.deactivateSWCursor()  # turn off software cursor
		if self.stdout:
			self.stdout.close()
			self.stdout = None
			self.stdin = None
		if self.stderr:
			self.stderr.close()
			self.stderr = None
		wutil.focusController.restoreLast()

	def redraw(self, o):

		ta = o.iplot.textAttributes
		ta.setFontSize()
		cm = gwm.getColorManager()
		if cm.rgbamode:
			glClearColor(0,0,0,0)
		else:
			glClearIndex(gwm._g.colorManager.indexmap[0])
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		glOrtho(0,1,0,1,-1,1)
		glDisable(GL_LIGHTING)
                glDisable(GL_DITHER)
		glShadeModel(GL_FLAT)
		
		for (function, args) in o.iplot.glBuffer.get():
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
	
	def __init__(self):
		self.graphicsWindow = gwm.getActiveWindow()
		self.windowName = gwm.getActiveWindowName()
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

#***********************************************************

def gl_eof(arg): pass
def gl_openws(arg): pass
def gl_closews(arg): pass
def gl_reactivatews(arg): pass
def gl_deactivatews(arg): pass
def gl_mftitle(arg): pass
def gl_clearws(arg): pass
def gl_cancel(arg): pass

def gl_flush(arg): glFlush()

def gl_polyline(vertices):

	# First, set all relevant attributes
	win = gwm.getActiveWindow()
	cursorActive =  win.isSWCursorActive()
	if cursorActive:
		win.SWCursorSleep()
	la = win.iplot.lineAttributes
	glPointSize(1.0)
	glDisable(GL_LINE_SMOOTH)
	glLineWidth(la.linewidth)
	stipple = 0
	clear = 0
	if la.linestyle == 0: clear = 1 # "clear" linestyle, don't draw!
	elif la.linestyle == 1: pass # solid line
	elif 2 <= la.linestyle < len(win.iplot.linestyles.patterns):
		glEnable(GL_LINE_STIPPLE)
		stipple = 1
		glLineStipple(1,win.iplot.linestyles.patterns[la.linestyle])
	glBegin(GL_LINE_STRIP)
	if not clear:
		gwm.setGraphicsDrawingColor(la.color)
	else:
		gwm.setGraphicsDrawingColor(0)
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()
	if stipple:
		glDisable(GL_LINE_STIPPLE)
	if cursorActive:
		win.SWCursorWake()

def gl_polymarker(vertices):

	# IRAF only implements points for poly marker, that makes it real simple
	win = gwm.getActiveWindow()
	cursorActive = win.isSWCursorActive()
	ma = win.iplot.markerAttributes
	clear = 0
	glPointSize(1)
	if not clear:
		gwm.setGraphicsDrawingColor(ma.color)
	else:
		gwm.setGraphicsDrawingColor(0)
	if cursorActive:
		win.SWCursorSleep()
	glBegin(GL_POINTS)
	glVertex(Numeric.reshape(vertices, (len(vertices)/2,2)))
	glEnd()
	if cursorActive:
		win.SWCursorWake()

def gl_text(x,y,text):

	win = gwm.getActiveWindow()
	cursorActive =  win.isSWCursorActive()
	if cursorActive:
		win.SWCursorSleep()
	opengltext.softText(x,y,text)
	if cursorActive:
		win.SWCursorWake()

def gl_fillarea(vertices):

	win = gwm.getActiveWindow()
	cursorActive =  win.isSWCursorActive()
	if cursorActive:
		win.SWCursorSleep()
	fa = win.iplot.fillAttributes
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
#		t = win.iplot.hatchfills
#		print t
#		tp = t.patterns
#		print tp, "patterns"
#		fill = win.iplot.hatchfills.patterns[fa.fillstyle]
#		print fill, "fill"
#		polystipple = 1
#		glEnable(GL_POLYGON_STIPPLE)
#		glPolygonStipple(fill)
	if not clear:
		gwm.setGraphicsDrawingColor(fa.color)
	else:
		gwm.setGraphicsDrawingColor(0)
#		glColor3f(0.,0.,0.)
	# not a simple rectangle
	glBegin(GL_POLYGON)
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()
	if polystipple:
		glDisable(GL_POLYGON_STIPPLE)
	if cursorActive:
		win.SWCursorWake()


def gl_putcellarray(arg): pass

def gl_setcursor(cursornumber, x, y):

	win = gwm.getActiveWindow()
	# wutil.MoveCursorTo uses 0,0 <--> upper left, need to convert
	sy = win.winfo_height() - y
	sx = x
	wutil.moveCursorTo(win.winfo_id(), sx, sy)
	
def gl_plset(linestyle, linewidth, color):

	win = gwm.getActiveWindow()
	win.iplot.lineAttributes.set(linestyle, linewidth, color)
	
def gl_pmset(marktype, marksize, color):

	win = gwm.getActiveWindow()
	win.iplot.markerAttributes.set(marktype, marksize, color)

def gl_txset(charUp, charSize, charSpace, textPath, textHorizontalJust,
			 textVerticalJust, textFont, textQuality, textColor):
	
	win = gwm.getActiveWindow()
	win.iplot.textAttributes.set(charUp, charSize, charSpace,
		textPath, textHorizontalJust, textVerticalJust, textFont,
		textQuality, textColor)

def gl_faset(fillstyle, color):
	
	win = gwm.getActiveWindow()
	win.iplot.fillAttributes.set(fillstyle, color)

def gl_getcursor(arg): pass
def gl_getcellarray(arg): pass
def gl_unknown(arg): pass
def gl_escape(arg): pass
def gl_setwcs(arg): pass
def gl_getwcs(arg): pass

glFunctionTable = [
	gl_eof,	   	# 0
	gl_openws,  
	gl_closews,
	gl_reactivatews,
	gl_deactivatews,
	gl_mftitle,	# 5
	gl_clearws,
	gl_cancel,
	gl_flush,
	gl_polyline,
	gl_polymarker,# 10
	gl_text,
	gl_fillarea,
	gl_putcellarray,
	gl_setcursor,
	gl_plset,		# 15
	gl_pmset,
	gl_txset,
	gl_faset,
	gl_getcursor, # also gl_cursorvalue,
	gl_getcellarray,#20  also	gl_cellarray,
	gl_unknown,
	gl_unknown,
	gl_unknown,
	gl_unknown,
	gl_escape,		# 25
	gl_setwcs,
	gl_getwcs]

#********************************************



class GLBuffer:

	"""implement a buffer for GL commands which allocates memory in blocks so that 
	a new memory allocation is not needed everytime functions are appended"""

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
			(0.32,0.32,0.32),  # gray32
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.),  # white
			(1.,1.,1.)   # white
		]
	def fontSize(self):
	
		"""
	Determine the unit font size for the given setup in pixels.
	The unit size refers to the horizonal size of fixed width characters
	(allow for proportionally sized fonts later?).
	
	Basically, if font aspect is not fixed, the unit font size is proportional
	to the window dimension (for v and h independently), with the exception
	that if min or max pixel sizes are enabled, they are 'clipped' at the 
	specified value. If font aspect is fixed, then the horizontal size is the
	driver if the window is higher than wide and vertical size for the 
	converse.
	"""
	
		win = gwm.getActiveWindow()
		hWin = win.winfo_width()
		vWin = win.winfo_height()
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

	def __init__(self):

		self.setDefaults()

	def setDefaults(self):

		irafConfig = gwm.getIrafGkiConfig()
		self.defaultColors = irafConfig.getIrafColors()

	def toRGB(self, irafcolor):

		if not (0 <= irafcolor < 16):
			print "WARNING: Iraf color out of legal range (1-16)"
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

