"""
OpenGL implementation of the gki kernel class

$Id$
"""

from OpenGL.GL import *
from gki import *
import iraf
import Numeric
import gwm
import irafgcur
import irafgwcs
import wutil
from  iraftext import *

# debugging purposes only

import __main__

class IrafPlot:

	"""An object that groups all the data items needed to support
    IRAF gki graphics. This object is expected to be an attribute of
	the togl widget used to display the graphics. Each togl widget
	should have its own copy of this class object"""

	def __init__(self):

		self.glBuffer = GLBuffer()
		self.gkiBuffer = GkiBuffer()
		self.wcs = None
		self.colors = IrafColors()
		self.linestyles = IrafLineStyles()
		self.hatchfills = IrafHatchFills()
		self.textAttributes = TextAttributes()
		self.lineAttributes = LineAttributes()
		self.fillAttributes = FillAttributes()
		self.markerAttributes = MarkerAttributes()

class GkiOpenGlKernel(GkiKernel):

	def __init__(self):

		GkiKernel.__init__(self)
		self.functionTable = gkiFunctionTable
		self.controlFunctionTable = [self.controlDefault]*(GKI_MAX_OP_CODE+1)
		self.controlFunctionTable[GKI_OPENWS] = self.openWS
		self.controlFunctionTable[GKI_CLOSEWS] = self.closeWS
		self.controlFunctionTable[GKI_REACTIVATEWS] = self.reactivateWS
		self.controlFunctionTable[GKI_DEACTIVATEWS] = self.deactivateWS
		self.controlFunctionTable[GKI_CLEARWS] = self.clearWS
		self.controlFunctionTable[GKI_SETWCS] = self.setWCS
		self.controlFunctionTable[GKI_GETWCS] = self.getWCS

	def control(self, gkiMetacode):

		gkiTranslate(gkiMetacode, self.controlFunctionTable)
		return self.returnData

	def translate(self, gkiMetacode, fTable):

		gkiTranslate(gkiMetacode, fTable)
		win = gwm.getActiveWindow()
		glbuf = win.iplot.glBuffer
		# render new stuff immediately
		function, args = glbuf.getNextCall()
		while function:
			apply(function, args)
			function, args = glbuf.getNextCall()
		glFlush()

	def controlDefault(self, arg):

		# This function should never be called.
		print "controlDefault called"

	def controlDoNothing(self, arg):
		pass
#		print "controlDoNothing called"

	def openWS(self, arg):

		mode = arg[0]
		device = arg[1:].tostring() # but will be ignored
		if wutil.getTerminalWindowID() == wutil.getWindowID():
			# save current cursor position
			wutil.saveTerminalCursorPosition()
		# first see if there are any graphics windows, if not, create one 
		win = gwm.getActiveWindow()
		if win == None:
			gwm.createWindow()
			win = gwm.getActiveWindow()
		win.redraw = self.redraw
		if not hasattr(win,"iplot"):
			win.iplot = IrafPlot()
		ta = win.iplot.textAttributes
		ta.setFontSize()
		gwm.raiseActiveWindow()
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
		
	def clearWS(self, arg):

		# apparently this control routine is not used???

		win = gwm.getActiveWindow()
		win.iplot.gkiBuffer.reset()
		win.iplot.glBuffer.reset()
		win.iplot.wcs = None
		win.immediateRedraw()

	def reactivateWS(self, arg):
		gwm.raiseActiveWindow()
		
	def deactivateWS(self, arg):

		# Move focus and cursor to terminal window if focus is currently
		# within Pyraf family of windows -- Sigh, unless graphics was
		# opened from an interactive session with an image display
		# window, in which case we should try to move focus back to it.
		self.restorePreviousFocus()
		
	def setWCS(self, arg):

		__main__.wcs = arg # pass it up to play with
		win = gwm.getActiveWindow()
		win.iplot.wcs = irafgwcs.IrafGWcs(arg)

	def getWCS(self, arg):

		win = gwm.getActiveWindow()
		if not win.iplot.wcs:
			print "Error: can't append to a nonexistent plot!"
			raise iraf.IrafError
		if self.returnData:
			self.returnData = self.returnData + win.iplot.wcs.pack()
		else:
			self.returnData = win.iplot.wcs.pack()

	def closeWS(self, arg):

		self.restorePreviousFocus()
		
	def redraw(self, o):

		ta = o.iplot.textAttributes
		ta.setFontSize()
		glClearColor(0,0,0,0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		glOrtho(0,1,0,1,-1,1)
		glDisable(GL_LIGHTING)
		glShadeModel(GL_FLAT)
		
		for (function, args) in o.iplot.glBuffer.get():
			apply(function, args)
		glFlush()

	def restorePreviousFocus(self):

		gwm.saveGraphicsCursorPosition()
		if not wutil.isFocusElsewhere():
			if not wutil.imcurActive:
				x, y = wutil.getLastTermPos()
				winID = wutil.getTerminalWindowID()
			else:
				x, y = wutil.getLastImagePos()
				winID = wutil.getImageWindowID()
			# make sure cursor is out of scroll bar region
			if x < 50: x = 50
			if wutil.isViewable(winID):
				wutil.setFocusTo(winID)
				wutil.moveCursorTo(winID,x,y)
				
def _glAppend(arg):

	"""append a 2-tuple (gl_function, args) to the glBuffer"""
	win = gwm.getActiveWindow()
	win.iplot.glBuffer.append(arg)


#***********************************************************

standardWarning = """
The graphics kernel for IRAF tasks has just recieved a metacode
instruction it never expected to see. Please inform the STSDAS
group of this occurance"""

standardNotImplemented = """
You have tried to run an IRAF task which requires graphics kernel
facility not implemented in the Python graphics kernel for IRAF tasks"""

def gki_eof(arg): pass # ignored
def gki_openws(arg): pass	# handled in control channel
def gki_closews(arg): pass # handled in control channel
def gki_reactivatews(arg): pass # ignored
def gki_deactivatews(arg): pass # ignored
def gki_mftitle(arg): pass # ignored
def gki_clearws(arg):

	win = gwm.getActiveWindow()
	win.iplot.gkiBuffer.reset()
	win.iplot.glBuffer.reset()
	win.iplot.wcs = None
	win.immediateRedraw()

def gki_cancel(arg): gki_clearws(arg)

def gki_flush(arg): _glAppend((gl_flush,(arg,)))

def gki_polyline(arg): _glAppend((gl_polyline,(ndc(arg[1:]),)))

def gki_polymarker(arg): 

	print standardWarning
	# throw exception here xxx
		
def gki_text(arg):
	
#	print "GKI_TEXT:", arg[3:].tostring()
	x = ndc(arg[0])
	y = ndc(arg[1])
	text = arg[3:].astype(Numeric.Int8).tostring()
	_glAppend((gl_text, (x, y, text)))

def gki_fillarea(arg): 

	_glAppend((gl_fillarea,(ndc(arg[1:]),)))

def gki_putcellarray(arg): 
	
	print standardNotImplemented
	# throw exception here xxxx
	
def gki_setcursor(arg):

	cursorNumber = arg[0]
	x = arg[1]/GKI_MAX
	y = arg[2]/GKI_MAX
	_glAppend((gl_setcursor, (cursorNumber, x, y)))
	
def gki_plset(arg):

	linetype = arg[0]
	linewidth = arg[1]/GKI_FLOAT_FACTOR
	color = arg[2]
	_glAppend((gl_plset, (linetype, linewidth, color)))
	
def gki_pmset(arg):

#	marktype = arg[0]
#	marksize = arg[1]/GKI_MAX
#	color = arg[2]
#	print "GKI_PMSET", marktype, marksize, color
#	_glAppend((gl_pmset, (marktype, marksize, color)))
	print standardWarning

def gki_txset(arg):

	charUp = float(arg[0])
	charSize = arg[1]/GKI_FLOAT_FACTOR
	charSpace = arg[2]/GKI_FLOAT_FACTOR
	textPath = arg[3]
	textHorizontalJust = arg[4]
	textVerticalJust = arg[5]
	textFont = arg[6]
	textQuality = arg[7]
	textColor = arg[8]
	_glAppend((gl_txset, (charUp, charSize, charSpace, textPath,
		textHorizontalJust, textVerticalJust, textFont,
		textQuality, textColor)))

def gki_faset(arg):

	fillstyle = arg[0]
	color = arg[1]
	_glAppend((gl_faset,(fillstyle, color)))

def gki_getcursor(arg):

	print "GKI_GETCURSOR"
	print standardNotImplemented
	# Throw exception here xxxx
	 
def gki_getcellarray(arg):

	print "GKI_GETCELLARRAY"
	print standardNotImplemented
	# Throw exception here xxxx
	
def gki_unknown(arg): 
	
	print "GKI_UNKNOWN"
	print standardWarning
	# Throw exception here xxxx
	
def gki_escape(arg): print "GKI_ESCAPE"
def gki_setwcs(arg): pass #print "GKI_SETWCS"
def gki_getwcs(arg): print "GKI_GETWCS"

#*****************************************

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
	la = win.iplot.lineAttributes
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
		apply(glColor3f,win.iplot.colors.toRGB(la.color))
	else:
		glColor3f(0.,0.,0.)
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()
	if stipple:
		glDisable(GL_LINE_STIPPLE)

def gl_polymarker(arg): pass

def gl_text(x,y,text):

	softText(x,y,text)

def gl_fillarea(vertices):

	win = gwm.getActiveWindow()
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
		apply(glColor3f,win.iplot.colors.toRGB(fa.color))
	else:
		glColor3f(0.,0.,0.)
	# not a simple rectangle
	glBegin(GL_POLYGON)
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()
	if polystipple:
		glDisable(GL_POLYGON_STIPPLE)

def gl_putcellarray(arg): pass

def gl_setcursor(cursornumber, x, y):

	win = gwm.getActiveWindow()
	# wutil.MoveCursorTo uses 0,0 <--> upper left, need to convert
	sy = win.wininfo_height() - y
	sx = x
	wutil.moveCursorTo(win.winfo_id(), sx, sy)
	
def gl_plset(linestyle, linewidth, color):

	win = gwm.getActiveWindow()
	win.iplot.lineAttributes.set(linestyle, linewidth, color)
	
def gl_pmset(marktype, marksize, color): pass

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

#********************************************

# function tables
gkiFunctionTable = [
	gki_eof,			# 0
	gki_openws,  
	gki_closews,
	gki_reactivatews,
	gki_deactivatews,
	gki_mftitle,	# 5
	gki_clearws,
	gki_cancel,
	gki_flush,
	gki_polyline,
	gki_polymarker,# 10
	gki_text,
	gki_fillarea,
	gki_putcellarray,
	gki_setcursor,
	gki_plset,		# 15
	gki_pmset,
	gki_txset,
	gki_faset,
	gki_getcursor, # also gki_cursorvalue,
	gki_getcellarray,#20  also	gki_cellarray,
	gki_unknown,
	gki_unknown,
	gki_unknown,
	gki_unknown,
	gki_escape,		# 25
	gki_setwcs,
	gki_getwcs]


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
			(0.,0.,0.), # black
			(1.,1.,1.), # white
			(1.,0.,0.), # red
			(0.,1.,0.), # green
			(0.,0.,1.), # blue
			(1.,1.,0.), # yellow
			(0.,1.,1.), # cyan
			(1.,0.,1.), # magenta
			(1.,0.5,0.), # coral
			(0.7,0.19,0.38), # maroon
			(1.,0.65,0.), # orange
			(0.94,0.9,0.55), # khaki
			(0.25,0.88,0.82), # turquoise
			(0.96,0.87,0.7) # wheat
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

	def __init__(self): pass
