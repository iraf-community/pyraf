from OpenGL.GL import *
from gki import *
import Numeric
import gwm

DEBUG = 0

class GkiOpenGlKernel(GkiKernel):

	def __init__(self):

		GkiKernel.__init__(self)
		self.functionTable = gkiFunctionTable
		# self.glBuffer = []
		self.controlFunctionTable = [controlDefault]*(GKI_MAX_OP_CODE+1)
		self.controlFunctionTable[GKI_OPENWS] = openWS
		self.controlFunctionTable[GKI_CLOSEWS] = controlDoNothing
		self.controlFunctionTable[GKI_REACTIVATEWS] = controlDoNothing
		self.controlFunctionTable[GKI_DEACTIVATEWS] = controlDoNothing
		self.controlFunctionTable[GKI_CLEARWS] = controlDoNothing
		self.controlFunctionTable[GKI_SETWCS] = controlDoNothing
		self.controlFunctionTable[GKI_GETWCS] = controlDoNothing

	def control(self, gkiMetacode):

		gkiTranslate(gkiMetacode, self.controlFunctionTable)

	def translate(self, gkiMetacode, fTable):

		glbuf = gwm.g.activeWindow.gwidget.glBuffer
		posStart = len(glbuf)
		gkiTranslate(gkiMetacode, fTable)
		posEnd = len(glbuf)
		newgl = glbuf[posStart:posEnd]
		draw(newgl) # render new stuff immediately
#		gwm.g.activeWindow.gwidget.tkRedraw()

#*****************************************

def controlDefault(arg):

	# This function should never be called.
	print "controlDefault called"

def controlDoNothing(arg):

	print "controlDoNothing called"

def openWS(arg):

	# ignore device name and mode for now
	print arg
	if gwm.g.activeWindow == None:
		gwm.g.window()
	gwm.g.activeWindow.gwidget.redraw = redraw
	# Adding this attribute to the active window is needed so that
	# redraw can find its way back to the gl buffer through the
	# argument given it. Is there a better way?
	gwm.g.activeWindow.gwidget.glBuffer = []

def draw(glbuf):

	for gl in glbuf:
		apply(gl[0],gl[1])
	
def redraw(o):
		
		glClearColor(0,0,0,0)
		glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
		glOrtho(0,1,0,1,-1,1)
		glDisable(GL_LIGHTING)
		glEnable(GL_VERTEX_ARRAY)

		for gl in o.glBuffer:
			apply(gl[0],gl[1])

#*****************************************

def gki_eof(arg): print "GKI_EOF "
def gki_openws(arg): print "GKI_OPENWS "
def gki_closews(arg): print "GKI_CLOSEWS "
def gki_reactivatews(arg): print "GKI_REACTIVATEWS "
def gki_deactivatews(arg): print "GKI_DEACTIVATEWS "
def gki_mftitle(arg): print "GKI_MFTITLE "
def gki_clearws(arg): print "GKI_CLEARWS "
def gki_cancel(arg): print "GKI_CANCEL "
def gki_flush(arg): print "GKI_FLUSH "

def gki_polyline(arg):

	print "GL_POLYLINE xx"
#	print self.ndc(arg[1:])
	gwm.g.activeWindow.gwidget.glBuffer.append((gl_polyline,(ndc(arg[1:]),)))

def gki_polymarker(arg): print "GKI_POLYMARKER "
def gki_text(arg): print "GKI_TEXT "
def gki_fillarea(arg): print "GKI_FILLAREA "
def gki_putcellarray(arg): print "GKI_PUTCELLARRAY "
def gki_setcursor(arg): print "GKI_SETCURSOR "
def gki_plset(arg): print "GKI_PLSET "
def gki_pmset(arg): print "GKI_PMSET "
def gki_txset(arg): print "GKI_TXSET "
def gki_faset(arg): print "GKI_FASET "
def gki_getcursor(arg): print "GKI_GETCURSOR (GKI_CURSORVALUE) "
def gki_getcellarray(arg): print "GKI_GETCELLARRAY "
def gki_unknown(arg): print "GKI_UNKNOWN "
def gki_escape(arg): print "GKI_ESCAPE "
def gki_setwcs(arg): print "GKI_SETWCS "
def gki_getwcs(arg): print "GKI_GETWCS "
		
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
# 	for i in xrange(len(vertices)/2):
# 		glVertex2f(vertices[2*i],vertices[2*i+1])
	glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
	glEnd()
#*********
#	glVertexPointer(2, 0, vertices)
#	glDrawArrays(GL_LINE_STRIP, 0, len(vertices)/2)

def gl_polymarker(arg): pass
def gl_text(arg): pass
def gl_fillarea(arg): pass
def gl_putcellarray(arg): pass
def gl_setcursor(arg): pass
def gl_plset(arg): pass
def gl_pmset(arg): pass
def gl_txset(arg): pass
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


