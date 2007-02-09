"""
OpenGL implementation of the gki kernel class

$Id$
"""

import numpy, os, sys, string, re, wutil
import Tkinter, msgiobuffer
from OpenGL.GL import *
import toglcolors
import gki, gkitkbase, gkigcur, opengltext, irafgwcs
import openglutil

#-----------------------------------------------


#-----------------------------------------------

class GkiOpenGlKernel(gkitkbase.GkiInteractiveTkBase):

    """OpenGL graphics kernel implementation"""

    def makeGWidget(self, width=600, height=420):

        """Make the graphics widget"""

        # Ptogl is local substitute for OpenGL.Tk
        # (to remove goofy 3d cursor effects)
        # Import is placed here since it can be slow, so delay import to
        # a time that a window is really needed. Subsequent imports will
        # be fast.
        import Ptogl
        self.gwidget = Ptogl.Ptogl(self.top,width=width,height=height)
        self.gwidget.firstPlotDone = 0
        self.colorManager = glColorManager(self.irafGkiConfig,
                                self.gwidget.rgbamode)
        self.startNewPage()
        self._gcursorObject = gkigcur.Gcursor(self)
        self.gRedraw()

    def gcur(self):

        """Return cursor value after key is typed"""

        return self._gcursorObject()

    def gcurTerminate(self, msg='Window destroyed by user'):

        """Terminate active gcur and set EOF flag"""

        if self._gcursorObject.active:
            self._gcursorObject.eof = msg
            # end the gcur mainloop -- this is what allows
            # closing the window to act the same as EOF
            self.top.quit()

    def taskDone(self, name):

        """Called when a task is finished"""

        # Hack to prevent the double redraw after first Tk plot
        self.doubleRedrawHack()

    def update(self):

        """Update for all Tk events

        This should not be called unless necessary since it can
        cause double redraws.  It is used in the imcur task to
        allow window resize (configure) events to be caught
        while a task is running.  Possibly it should be called
        during long-running tasks too, but that will probably
        lead to more extra redraws"""

        # Hack to prevent the double redraw after first Tk plot
        self.doubleRedrawHack()
        self.top.update()

    def doubleRedrawHack(self):

        # This is a hack to prevent the double redraw on first plots.
        # There is a mysterious Expose event that appears on the
        # idle list, but not until the Tk loop actually becomes idle.
        # The only approach that seems to work is to set this flag
        # and to ignore the event.
        # This is ugly but appears to work as far as I can tell.
        gwidget = self.gwidget
        if gwidget and not gwidget.firstPlotDone:
            gwidget.ignoreNextRedraw = 1
            gwidget.firstPlotDone = 1

    def prepareToRedraw(self):

        """Clear glBuffer in preparation for complete redraw from metacode"""

        self.drawBuffer.reset()

    def getHistory(self):

        """Additional information for page history"""

        return self.drawBuffer

    def setHistory(self, info):

        """Restore using additional information from page history"""

        self.drawBuffer = info

    def startNewPage(self):

        """Setup for new page"""

        self.drawBuffer = gki.DrawBuffer()

    def clearPage(self):

        """Clear buffer for new page"""

        self.drawBuffer.reset()

    def isPageBlank(self):

        """Returns true if this page is blank"""

        return len(self.drawBuffer) == 0

    # -----------------------------------------------
    # GkiKernel implementation

    def incrPlot(self):

        """Plot any new commands in the buffer"""

        gwidget = self.gwidget
        if gwidget:
            active = gwidget.isSWCursorActive()
            if active:
                gwidget.deactivateSWCursor()
            # render new contents of glBuffer
            self.activate()
            for (function, args) in self.drawBuffer.getNewCalls():
                apply(function, args)
            gwidget.flush()
            if active:
                gwidget.activateSWCursor()

    # special methods that go into the function tables

    def _glAppend(self, gl_function, *args):

        """append a 2-tuple (gl_function, args) to the glBuffer"""

        self.drawBuffer.append((gl_function,args))

    def gki_clearws(self, arg):

        # don't put clearws command in the gl buffer, just clear the display
        self.clear()

    def gki_cancel(self, arg):

        self.gki_clearws(arg)

    def gki_flush(self, arg):

        # don't put flush command in gl buffer
        # render current plot immediately on flush
        self.incrPlot()

    def gki_polyline(self, arg):

        # commit pending WCS changes when draw is found
        self.wcs.commit()
        self._glAppend(self.gl_polyline, gki.ndc(arg[1:]))

    def gki_polymarker(self, arg):

        self.wcs.commit()
        self._glAppend(self.gl_polymarker, gki.ndc(arg[1:]))

    def gki_text(self, arg):

        self.wcs.commit()
        x = gki.ndc(arg[0])
        y = gki.ndc(arg[1])
        text = arg[3:].astype(numpy.int8).tostring()
        self._glAppend(self.gl_text, x, y, text)

    def gki_fillarea(self, arg):

        self.wcs.commit()
        self._glAppend(self.gl_fillarea, gki.ndc(arg[1:]))

    def gki_putcellarray(self, arg):

        self.wcs.commit()
        self.errorMessage(gki.standardNotImplemented % "GKI_PUTCELLARRAY")

    def gki_setcursor(self, arg):

        cursorNumber = arg[0]
        x = gki.ndc(arg[1])
        y = gki.ndc(arg[2])
        self._glAppend(self.gl_setcursor, cursorNumber, x, y)

    def gki_plset(self, arg):

        linetype = arg[0]
        linewidth = arg[1]/gki.GKI_FLOAT_FACTOR
        color = arg[2]
        self._glAppend(self.gl_plset, linetype, linewidth, color)

    def gki_pmset(self, arg):

        marktype = arg[0]
        #XXX Is this scaling for marksize correct?
        marksize = gki.ndc(arg[1])
        color = arg[2]
        self._glAppend(self.gl_pmset, marktype, marksize, color)

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
        self._glAppend(self.gl_txset, charUp, charSize, charSpace, textPath,
                textHorizontalJust, textVerticalJust, textFont,
                textQuality, textColor)

    def gki_faset(self, arg):

        fillstyle = arg[0]
        color = arg[1]
        self._glAppend(self.gl_faset, fillstyle, color)

    def gki_getcursor(self, arg):

        raise RuntimeError(gki.standardNotImplemented %  "GKI_GETCURSOR")

    def gki_getcellarray(self, arg):

        raise RuntimeError(gki.standardNotImplemented % "GKI_GETCELLARRAY")

    def gki_unknown(self, arg):

        self.errorMessage(gki.standardWarning % "GKI_UNKNOWN")

    def gRedraw(self):

        if self.gwidget:
            self.gwidget.tkRedraw()

    def redraw(self, o=None):

        """Redraw for expose or resize events

        This method generally should not be called directly -- call
        gwidget.tkRedraw() instead since it does some other
        preparations.
        """

        # Note argument o is not needed because we only get redraw
        # events for our own gwidget
        ta = self.textAttributes
        ta.setFontSize(self)
        cm = self.colorManager
        if cm.rgbamode:
            glClearColor(0,0,0,0)
        else:
            glClearIndex(cm.indexmap[0])
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        if not openglutil.oldpyopengl:
            glEnableClientState(GL_VERTEX_ARRAY) ## for pyOpenGL V2
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0,1,0,1,-1,1)
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        glShadeModel(GL_FLAT)

        # finally ready to do the drawing
        self.activate()
        for (function, args) in self.drawBuffer.get():
            apply(function, args)
        self.gwidget.flush()

    #-----------------------------------------------
    # These are the routines for the innermost loop in the redraw
    # function.  They are supposed to be stripped down to make
    # redraws as fast as possible.  (Still could be improved.)

    def gl_flush(self, arg):

        self.gwidget.flush()

    def gl_polyline(self, vertices):

        # First, set all relevant attributes
        la = self.lineAttributes
        glPointSize(1.0)
        glDisable(GL_LINE_SMOOTH)
        glLineWidth(la.linewidth)
        stipple = 0
        clear = 0
        npts = len(vertices)/2
        if la.linestyle == 0:
            clear = 1 # "clear" linestyle, don't draw!
        elif la.linestyle == 1:
            pass # solid line
        elif 2 <= la.linestyle < len(self.linestyles.patterns):
            glEnable(GL_LINE_STIPPLE)
            stipple = 1
            glLineStipple(1,self.linestyles.patterns[la.linestyle])
        if not clear:
            self.colorManager.setDrawingColor(la.color)
        else:
            self.colorManager.setDrawingColor(0)
        openglutil.glPlot(vertices, GL_LINE_STRIP)
        if stipple:
            glDisable(GL_LINE_STIPPLE)

    def gl_polymarker(self, vertices):

        # IRAF only implements points for poly marker, that makes it simple
        ma = self.markerAttributes
        clear = 0
        npts = len(vertices)/2
        glPointSize(1)
        if not clear:
            self.colorManager.setDrawingColor(ma.color)
        else:
            self.colorManager.setDrawingColor(0)
        openglutil.glPlot(vertices, GL_POINTS)

    def gl_text(self, x, y, text):

        opengltext.softText(self,x,y,text)

    def gl_fillarea(self, vertices):

        fa = self.fillAttributes
        clear = 0
        polystipple = 0
        npts = len(vertices)/2
        if fa.fillstyle == 0: # clear region
            clear = 1
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        elif fa.fillstyle == 1: # hollow
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        elif fa.fillstyle >= 2: # solid
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
    #       elif fa.fillstyle > 2: # hatched
    # This is commented out since PyOpenGL does not currently support
    # glPolygonStipple!
    #               if fa.fillstyle > 6: fa.fillstyle = 6
    #               t = self.hatchfills
    #               print t
    #               tp = t.patterns
    #               print tp, "patterns"
    #               fill = self.hatchfills.patterns[fa.fillstyle]
    #               print fill, "fill"
    #               polystipple = 1
    #               glEnable(GL_POLYGON_STIPPLE)
    #               glPolygonStipple(fill)
        if not clear:
            self.colorManager.setDrawingColor(fa.color)
        else:
            self.colorManager.setDrawingColor(0)
        openglutil.glPlot(vertices, GL_POLYGON)
        if polystipple:
            glDisable(GL_POLYGON_STIPPLE)

    def gl_setcursor(self, cursornumber, x, y):

        gwidget = self.gwidget
        # wutil.MoveCursorTo uses 0,0 <--> upper left, need to convert
        sx = int(  x   * gwidget.winfo_width())
        sy = int((1-y) * gwidget.winfo_height())
        wutil.moveCursorTo(gwidget.winfo_id(), sx, sy)

    def gl_plset(self, linestyle, linewidth, color):

        self.lineAttributes.set(linestyle, linewidth, color)

    def gl_pmset(self, marktype, marksize, color):

        self.markerAttributes.set(marktype, marksize, color)

    def gl_txset(self, charUp, charSize, charSpace, textPath,
                    textHorizontalJust, textVerticalJust,
                    textFont, textQuality, textColor):

        self.textAttributes.set(charUp, charSize, charSpace,
                textPath, textHorizontalJust, textVerticalJust, textFont,
                textQuality, textColor)

    def gl_faset(self, fillstyle, color):

        self.fillAttributes.set(fillstyle, color)

#-----------------------------------------------

class glColorManager:

    """Encapsulates the details of setting the graphic's windows colors.

    Needed since we may be using rgba mode or color index mode and we
    do not want any of the graphics programs to have to deal with the
    mode being used. The current design applies the same colors to all
    graphics windows for color index mode (but it isn't required).
    An 8-bit display depth results in color index mode, otherwise rgba
    mode is used.  If no new colors are available, we take what we can
    get. We do not attempt to get a private colormap.
    """

    def __init__(self, config, rgbamode):

        self.config = config
        self.rgbamode = rgbamode
        self.indexmap = len(self.config.defaultColors)*[None]
        # call setColors to allocate colors after widget is created

    def setColors(self, widget):

        """Does nothing in rgba mode, allocates colors in index mode"""

        if not self.rgbamode:
            colorset = self.config.defaultColors
            for i in xrange(len(self.indexmap)):
                self.indexmap[i] = toglcolors.AllocateColor(widget.toglStruct,
                                                   colorset[i][0],
                                                   colorset[i][1],
                                                   colorset[i][2])
        self.setCursorColor()

    def setCursorColor(self, irafColorIndex=None):

        """Set crosshair cursor color to given index

        Only has an effect in index color mode."""
        import Ptogl
        if irafColorIndex is not None:
            self.config.setCursorColor(irafColorIndex)
        if self.rgbamode:
            Ptogl.cursorTrue = self.config.defaultColors[self.config.cursorColor]
        else:
            # cursor color is result of xor-ing desired cursor color with
            # background color
            fgcolor = self.indexmap[self.config.cursorColor]
            bgcolor = self.indexmap[0]
            Ptogl.cursorColor = fgcolor ^ bgcolor

    def setDrawingColor(self, irafColorIndex):

        """Apply the specified iraf color to the current OpenGL drawing

        state using the appropriate mode."""
        if self.rgbamode:
            color = self.config.defaultColors[irafColorIndex]
            glColor3f(color[0], color[1], color[2])
        else:
            glIndex(self.indexmap[irafColorIndex])

#-----------------------------------------------
