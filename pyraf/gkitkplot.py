"""
Tkplot implementation of the gki kernel class
"""

import numpy
import tkinter
from . import wutil
from . import Ptkplot
from . import gki
from . import gkitkbase
from . import gkigcur
from . import tkplottext

TK_LINE_STYLE_PATTERNS = ['.', '.', '_', '.', '.._']

# -----------------------------------------------


class GkiTkplotKernel(gkitkbase.GkiInteractiveTkBase):
    """Tkplot graphics kernel implementation"""

    def makeGWidget(self, width=600, height=420):
        """Make the graphics widget"""

        self.gwidget = Ptkplot.PyrafCanvas(self.top,
                                           width=width,
                                           height=height)
        self.gwidget.firstPlotDone = 0
        self.colorManager = tkColorManager(self.irafGkiConfig)
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
                function(*args)
            gwidget.flush()
            if active:
                gwidget.activateSWCursor()

    # special methods that go into the function tables

    def _tkplotAppend(self, tkplot_function, *args):
        """append a 2-tuple (tkplot_function, args) to the glBuffer"""

        self.drawBuffer.append((tkplot_function, args))

    def gki_clearws(self, arg):

        # don't put clearws command in the tk buffer, just clear the display
        self.clear()
        # This is needed to clear all the previously plotted objects
        # within tkinter (it has its own buffer it uses to replot)
        # self.gwidget.delete(tkinter.ALL)

    def gki_cancel(self, arg):

        self.gki_clearws(arg)

    def gki_flush(self, arg):

        # don't put flush command in tk buffer
        # render current plot immediately on flush
        self.incrPlot()

    def gki_polyline(self, arg):

        # commit pending WCS changes when draw is found
        self.wcs.commit()
        self._tkplotAppend(self.tkplot_polyline, gki.ndc(arg[1:]))

    def gki_polymarker(self, arg):

        self.wcs.commit()
        self._tkplotAppend(self.tkplot_polymarker, gki.ndc(arg[1:]))

    def gki_text(self, arg):

        self.wcs.commit()
        x = gki.ndc(arg[0])
        y = gki.ndc(arg[1])
        text = arg[3:].astype(numpy.int8).tobytes().decode('ascii')
        self._tkplotAppend(self.tkplot_text, x, y, text)

    def gki_fillarea(self, arg):

        self.wcs.commit()
        self._tkplotAppend(self.tkplot_fillarea, gki.ndc(arg[1:]))

    def gki_putcellarray(self, arg):

        self.wcs.commit()
        self.errorMessage(gki.standardNotImplemented % "GKI_PUTCELLARRAY")

    def gki_setcursor(self, arg):

        cursorNumber = arg[0]
        x = gki.ndc(arg[1])
        y = gki.ndc(arg[2])
        self._tkplotAppend(self.tkplot_setcursor, cursorNumber, x, y)

    def gki_plset(self, arg):

        linetype = arg[0]
        # Handle case where some terms (eg. xgterm) allow higher values,
        # by looping over the possible visible patterns.  (ticket #172)
        if linetype >= len(TK_LINE_STYLE_PATTERNS):
            num_visible = len(TK_LINE_STYLE_PATTERNS) - 1
            linetype = 1 + (linetype % num_visible)
        linewidth = arg[1] / gki.GKI_FLOAT_FACTOR
        color = arg[2]
        self._tkplotAppend(self.tkplot_plset, linetype, linewidth, color)

    def gki_pmset(self, arg):

        marktype = arg[0]
        # XXX Is this scaling for marksize correct?
        marksize = gki.ndc(arg[1])
        color = arg[2]
        self._tkplotAppend(self.tkplot_pmset, marktype, marksize, color)

    def gki_txset(self, arg):

        charUp = float(arg[0])
        charSize = arg[1] / gki.GKI_FLOAT_FACTOR
        charSpace = arg[2] / gki.GKI_FLOAT_FACTOR
        textPath = arg[3]
        textHorizontalJust = arg[4]
        textVerticalJust = arg[5]
        textFont = arg[6]
        textQuality = arg[7]
        textColor = arg[8]
        self._tkplotAppend(self.tkplot_txset, charUp, charSize, charSpace,
                           textPath, textHorizontalJust, textVerticalJust,
                           textFont, textQuality, textColor)

    def gki_faset(self, arg):

        fillstyle = arg[0]
        color = arg[1]
        self._tkplotAppend(self.tkplot_faset, fillstyle, color)

    def gki_getcursor(self, arg):

        raise NotImplementedError(gki.standardNotImplemented % "GKI_GETCURSOR")

    def gki_getcellarray(self, arg):

        raise NotImplementedError(gki.standardNotImplemented %
                                  "GKI_GETCELLARRAY")

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
        # finally ready to do the drawing
        self.activate()
        # Have Tk remove all previously plotted objects
        self.gwidget.delete(tkinter.ALL)
        # Clear the screen
        self.tkplot_faset(0, 0)
        self.tkplot_fillarea(numpy.array([0., 0., 1., 0., 1., 1., 0., 1.]))
        # Plot the current buffer
        for (function, args) in self.drawBuffer.get():
            function(*args)
        self.gwidget.flush()

    # -----------------------------------------------
    # These are the routines for the innermost loop in the redraw
    # function.  They are supposed to be stripped down to make
    # redraws as fast as possible.  (Still could be improved.)

    def tkplot_flush(self, arg):

        self.gwidget.flush()

    def tkplot_polyline(self, vertices):

        # First, set all relevant attributes
        la = self.lineAttributes
        # XXX not handling linestyle yet, except for clear
        npts = len(vertices) // 2
        if la.linestyle == 0:  # clear
            color = self.colorManager.setDrawingColor(0)
        else:
            color = self.colorManager.setDrawingColor(la.color)
        options = {"fill": color, "width": la.linewidth}
        if la.linestyle > 1:
            options['dash'] = TK_LINE_STYLE_PATTERNS[la.linestyle]
        # scale coordinates
        gw = self.gwidget
        h = gw.winfo_height()
        w = gw.winfo_width()
        scaled = (numpy.array([w, -h]) *
                  (numpy.reshape(vertices, (npts, 2)) - numpy.array([0., 1.])))
        gw.create_line(*(tuple(scaled.ravel().astype(numpy.int32))), **options)

    def tkplot_polymarker(self, vertices):

        # IRAF only implements points for poly marker, that makes it simple
        ma = self.markerAttributes  # Marker attributes don't appear
        # to be set when this mode is used though.
        npts = len(vertices) // 2
        color = self.colorManager.setDrawingColor(ma.color)
        gw = self.gwidget
        h = gw.winfo_height()
        w = gw.winfo_width()
        scaled = (numpy.array([w, -h]) *
                  (numpy.reshape(vertices,
                                 (npts, 2)) - numpy.array([0., 1.]))).astype(
                                     numpy.int32)
        # Lack of intrinsic Tk point mode means that they must be explicitly
        # looped over.
        for i in range(npts):
            gw.create_rectangle(scaled[i, 0],
                                scaled[i, 1],
                                scaled[i, 0],
                                scaled[i, 1],
                                fill=color,
                                outline='')

    def tkplot_text(self, x, y, text):

        tkplottext.softText(self, x, y, text)

    def tkplot_fillarea(self, vertices):

        fa = self.fillAttributes
        npts = len(vertices) // 2
        if fa.fillstyle != 0:
            color = self.colorManager.setDrawingColor(fa.color)
        else:  # clear region
            color = self.colorManager.setDrawingColor(0)
        options = {"fill": color}
        # scale coordinates
        gw = self.gwidget
        h = gw.winfo_height()
        w = gw.winfo_width()
        scaled = (numpy.array([w, -h]) *
                  (numpy.reshape(vertices, (npts, 2)) - numpy.array([0., 1.])))
        coords = tuple(scaled.ravel().astype(numpy.int32))
        if fa.fillstyle == 1:  # hollow
            gw.create_line(*(coords + (coords[0], coords[1])), **options)
        else:  # solid or clear cases
            gw.create_polygon(*coords, **options)

    def tkplot_setcursor(self, cursornumber, x, y):

        gwidget = self.gwidget
        # Update the sw cursor object (A clear example of why this update
        # is needed is how 'apall' re-centers the cursor w/out changing y, when
        # the user types 'r'; without this update, the two cursors separate.)
        swCurObj = gwidget.getSWCursor()
        if swCurObj:
            swCurObj.moveTo(x, y, SWmove=1)
        # wutil.MoveCursorTo uses 0,0 <--> upper left, need to convert
        sx = int(x * gwidget.winfo_width())
        sy = int((1 - y) * gwidget.winfo_height())
        rx = gwidget.winfo_rootx()
        ry = gwidget.winfo_rooty()
        # call the wutil version to move the cursor
        wutil.moveCursorTo(gwidget.winfo_id(), rx, ry, sx, sy)

    def tkplot_plset(self, linestyle, linewidth, color):

        self.lineAttributes.set(linestyle, linewidth, color)

    def tkplot_pmset(self, marktype, marksize, color):

        self.markerAttributes.set(marktype, marksize, color)

    def tkplot_txset(self, charUp, charSize, charSpace, textPath,
                     textHorizontalJust, textVerticalJust, textFont,
                     textQuality, textColor):

        self.textAttributes.set(charUp, charSize, charSpace, textPath,
                                textHorizontalJust, textVerticalJust, textFont,
                                textQuality, textColor)

    def tkplot_faset(self, fillstyle, color):

        self.fillAttributes.set(fillstyle, color)


# -----------------------------------------------


class tkColorManager:
    """Encapsulates the details of setting the graphic's windows colors.

    Needed since we may be using rgba mode or color index mode and we
    do not want any of the graphics programs to have to deal with the
    mode being used. The current design applies the same colors to all
    graphics windows for color index mode (but it isn't required).
    An 8-bit display depth results in color index mode, otherwise rgba
    mode is used.  If no new colors are available, we take what we can
    get. We do not attempt to get a private colormap.
    """

    def __init__(self, config):

        self.config = config
        self.rgbamode = 0
        self.indexmap = len(self.config.defaultColors) * [None]
        # call setColors to allocate colors after widget is created

    def setColors(self, widget):
        """Not needed for Tkplot, a nop"""
        pass

    def setCursorColor(self, irafColorIndex=None):
        """Set crosshair cursor color to given index

        Only has an effect in index color mode."""
        if irafColorIndex is not None:
            self.config.setCursorColor(irafColorIndex)

    def setDrawingColor(self, irafColorIndex):
        """Return the specified iraf color usable by tkinter"""
        color = self.config.defaultColors[irafColorIndex]
        red = int(255 * color[0])
        green = int(255 * color[1])
        blue = int(255 * color[2])
        return f"#{red:02x}{green:02x}{blue:02x}"
