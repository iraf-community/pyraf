"""
OpenGL implementation of the gki kernel class

$Id$
"""

from OpenGL.GL import *
from gki import *
import Numeric
import gwm
import irafgcur
import irafgwcs
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
		self.textAttributes = TextAttributes()

class GkiOpenGlKernel(GkiKernel):

	def __init__(self):

		GkiKernel.__init__(self)
		self.functionTable = gkiFunctionTable
		self.controlFunctionTable = [self.controlDefault]*(GKI_MAX_OP_CODE+1)
		self.controlFunctionTable[GKI_OPENWS] = self.openWS
		self.controlFunctionTable[GKI_CLOSEWS] = self.controlDoNothing
		self.controlFunctionTable[GKI_REACTIVATEWS] = self.controlDoNothing
		self.controlFunctionTable[GKI_DEACTIVATEWS] = self.controlDoNothing
		self.controlFunctionTable[GKI_CLEARWS] = self.clearWS
		self.controlFunctionTable[GKI_SETWCS] = self.setWCS
		self.controlFunctionTable[GKI_GETWCS] = self.controlDoNothing

	def control(self, gkiMetacode):

		gkiTranslate(gkiMetacode, self.controlFunctionTable)

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
		# first see if there are any graphics windows, if not, create one 
		win = gwm.getActiveWindow()
		if win == None:
			gwm.createWindow()
			win = gwm.getActiveWindow()
		win.redraw = self.redraw
		if not hasattr(win,"iplot"):
			win.iplot = IrafPlot()
		if mode == 5:
			# clear the display
			print "clearing the display"
			win.iplot.gkiBuffer.reset()
			win.iplot.glBuffer.reset()
			win.iplot.wcs = None
			win.tkRedraw()
		elif mode == 4:
			# append, i.e., do nothing!
			pass
		elif mode == 6:
			# Tee mode (?), ignore for now
			pass

	def clearWS(self, arg):

		# apparently this control routine is not used???

		print "clearws"
		win = gwm.getActiveWindow()
		win.iplot.gkiBuffer.reset()
		win.iplot.glBuffer.reset()
		win.iplot.wcs = None
		win.tkRedraw()
		
	def setWCS(self, arg):

		print 'setwcs'
		__main__.wcs = arg # pass it up to play with
		win = gwm.getActiveWindow()
		win.iplot.wcs = irafgwcs.IrafGWcs(arg)

	def redraw(self, o):

		glClearColor(0,0,0,0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		glMatrixMode(GL_PROJECTION)
		glLoadIdentity()
		glOrtho(0,1,0,1,-1,1)
		glDisable(GL_LIGHTING)

		for (function, args) in o.iplot.glBuffer.get():
			apply(function, args)
		glFlush()

def _glAppend(arg):

	"""append a 2-tuple (gl_function, args) to the glBuffer"""
	win = gwm.getActiveWindow()
	win.iplot.glBuffer.append(arg)

def gki_eof(arg): print "GKI_EOF"
def gki_openws(arg): print "GKI_OPENWS"
def gki_closews(arg): print "GKI_CLOSEWS"
def gki_reactivatews(arg): print "GKI_REACTIVATEWS"
def gki_deactivatews(arg): print "GKI_DEACTIVATEWS"
def gki_mftitle(arg): print "GKI_MFTITLE"
def gki_clearws(arg):

	print "GKI_CLEARWS"
	win = gwm.getActiveWindow()
	win.iplot.gkiBuffer.reset()
	win.iplot.glBuffer.reset()
	win.iplot.wcs = None
	win.tkRedraw()

def gki_cancel(arg): print "GKI_CANCEL"
def gki_flush(arg): print "GKI_FLUSH"
def gki_polyline(arg): _glAppend((gl_polyline,(ndc(arg[1:]),)))
def gki_polymarker(arg): print "GKI_POLYMARKER"
def gki_text(arg):
	
	print "GKI_TEXT:", arg[3:].tostring()
	x = ndc(arg[0])
	y = ndc(arg[1])
	text = arg[3:].astype(Numeric.Int8).tostring()
	_glAppend((gl_text, (x, y, text)))


def gki_fillarea(arg): print "GKI_FILLAREA"
def gki_putcellarray(arg): print "GKI_PUTCELLARRAY"
def gki_setcursor(arg): print "GKI_SETCURSOR"
def gki_plset(arg): print "GKI_PLSET"
def gki_pmset(arg): print "GKI_PMSET"
def gki_txset(arg):

	print "GKI_TXSET"
	charUp = arg[0]/GKI_FLOAT_FACTOR
	charSize = arg[1]/GKI_FLOAT_FACTOR
	charSpace = arg[2]/GKI_FLOAT_FACTOR
	textPath = arg[3]
	textHorizontalJust = arg[4]
	textVerticalJust = arg[5]
	textFont = arg[6]
	textQuality = arg[7]
	textColor = arg[8]
	print "txset",charUp, charSize, charSpace, textPath, textHorizontalJust, \
		textVerticalJust, textFont, textQuality, textColor
	_glAppend((gl_txset, (charUp, charSize, charSpace, textPath,
		textHorizontalJust, textVerticalJust, textFont,
		textQuality, textColor)))

def gki_faset(arg): print "GKI_FASET"
def gki_getcursor(arg): print "GKI_GETCURSOR (GKI_CURSORVALUE)"
def gki_getcellarray(arg): print "GKI_GETCELLARRAY"
def gki_unknown(arg): print "GKI_UNKNOWN"
def gki_escape(arg): print "GKI_ESCAPE"
def gki_setwcs(arg): print "GKI_SETWCS"
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
def gl_flush(arg): pass

def gl_polyline(vertices):

	glBegin(GL_LINE_STRIP)
	glColor3f(1,1,1)
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()

def gl_polymarker(arg): pass
def gl_text(x,y,text):
	softText(x,y,text)
#	drawchar(x,y,text)
def gl_fillarea(arg): pass
def gl_putcellarray(arg): pass
def gl_setcursor(arg): pass
def gl_plset(arg): pass
def gl_pmset(arg): pass

def gl_txset(charUp, charSize, charSpace, textPath, textHorizontalJust,
			 textVerticalJust, textFont, textQuality, textColor):
	
	win = gwm.getActiveWindow()
	# Ignore attributes for initial testing!!!!!   	
	win.iplot.textAttributes =  TextAttributes(charUp, charSize, charSpace,
		textPath, textHorizontalJust, textVerticalJust, textFont,
		textQuality, textColor)

def gl_faset(arg): pass
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
		self.UnitFontWindowFraction = 1./80
		# minimum unit font size in pixels
		self.minUnitHFontSize = 6.
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
		hSize = hWin * self.UnitFontWindowFraction
		vSize = vWin * self.UnitFontWindowFraction/self.fontAspect
		if not self.isFixedAspectFont:
			if self.hasMinPixSizeUnitFont:
				hSize = max(hSize,self.minUnitHFontSize)
				vSize = max(vSize,self.minUnitVFontSize)
			if self.config.hasMaxPixSizeUnitFont:
				hSize = min(hSize,self.maxUnitHFontSize)
				vSize = min(hSize,self.maxUnitVFontSize)
			fontAspect = vSize/hSize		
		else:
			if vWin >= hWin:
				if self.hasMinPixSizeUnitFont:
					hSize = max(hSize,self.minUnitHFontSize)
				if self.hasMaxPixSizeUnitFont:
					hSize = min(hSize,self.maxUnitHFontSize)
				vSize = hSize * self.fontAspect
			else:
				if self.hasMinPixSizeUnitFont:
					vSize = max(vSize,self.minUnitVFontSize)
				if self.hasMaxPixSizeUnitFont:
					vSize = min(vSize,self.maxUnitVFontSize)
				hSize = vSize/self.fontAspect
			fontAspect = self.fontAspect
		return (hSize, fontAspect)
