"""
matplotlib implementation of the gki kernel class
"""



import math
import numpy
import tkinter
import matplotlib
# (done in mca file) matplotlib.use('TkAgg') # set backend
from matplotlib.lines import Line2D
from matplotlib.figure import Figure
from matplotlib.patches import Rectangle

from . import gki
from . import gkitkbase
from . import textattrib
from . import gkigcur
from . import MplCanvasAdapter as mca
from .wutil import moveCursorTo
try:
    import readline
except ImportError:
    readline = None

# MPL version
MPL_MAJ_MIN = matplotlib.__version__.split('.')  # tmp var
MPL_MAJ_MIN = float(MPL_MAJ_MIN[0] + '.' + MPL_MAJ_MIN[1])

# MPL linewidths seem to be thicker by default
GKI_TO_MPL_LINEWIDTH = 0.65

# GKI seems to use: 0: clear, 1: solid, 2: dash, 3: dot, 4: dot-dash, 5: ?
GKI_TO_MPL_LINESTYLE = ['None', '-', '--', ':', '-.', 'steps']

# Convert GKI alignment int values to MPL (idx 0 = default), 0 is invalid
GKI_TO_MPL_HALIGN = ['left', 'center', 'left', 'right', 0, 0, 0, 0]
GKI_TO_MPL_VALIGN = ['bottom', 'center', 0, 0, 0, 0, 'top', 'bottom']
# "surface dev$pix" uses idx=5, though that's not allowed
GKI_TO_MPL_VALIGN[4] = 'top'
GKI_TO_MPL_VALIGN[5] = 'bottom'

# some text is coming out too high by about this much
GKI_TEXT_Y_OFFSET = 0.005

# marktype seems unused at present (most markers are polylines), but for
# future use, the GIO document lists:
#    'Acceptable choices are "point", "box", "plus", "cross", "circle" '
GKI_TO_MPL_MARKTYPE = ['.', 's', '+', 'x', 'o']

# Convert other GKI font attributes to MPL (cannot do bold italic?)
GKI_TO_MPL_FONTATTR = [
    'normal', 1, 2, 3, 4, 5, 6, 7, 'roman', 'greek', 'italic', 'bold', 'low',
    'medium', 'high'
]

# -----------------------------------------------


class GkiMplKernel(gkitkbase.GkiInteractiveTkBase):
    """matplotlib graphics kernel implementation"""

    def makeGWidget(self, width=600, height=420):
        """Make the graphics widget.  Also perform some self init."""
        self.__pf = tkinter.Frame(self.top)
        self.__pf.pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        self.__xsz = width
        self.__ysz = height

        ddd = 100
        self.__fig = Figure(figsize=(self.__xsz / (1. * ddd),
                                     self.__ysz / (1. * ddd)),
                            dpi=ddd)
        self.__fig.set_facecolor('k')  # default to black

        self.__mca = mca.MplCanvasAdapter(self, self.__fig, master=self.__pf)
        self.__mca.pack(side=tkinter.TOP, fill=tkinter.BOTH, expand=1)
        self.__mca.gwidgetize(width, height)  # Add attrs to the gwidget
        self.gwidget = self.__mca.get_tk_widget()

        self.__normLines = []  # list of Line2D objs
        self.__normPatches = []  # list of Patch objs
        self.__extraHeightMax = 25
        self.__firstPlotDone = 0
        self.__skipPlotAppends = False  # allow gki_ funcs to be reused
        self.__allowDrawing = False  # like taskStart, but can't rely on that
        self._forceNextDraw = False
        #       self.__lastGkiCmds = (None, None, None) # unused for now

        self.colorManager = tkColorManager(self.irafGkiConfig)
        self.startNewPage()
        self.__gcursorObject = gkigcur.Gcursor(self)
        self.__mca.draw()  # or, could: self.gRedraw() with a .draw()

    # not currently using getAdjustedHeight because the background is drawn and
    # it is not black (or the same color as the rest of the empty window)
    def getAdjustedHeight(self):
        """ Calculate an adjusted height to make the plot look better in the
            widget's viewfield - otherwise the graphics are too close to
            the top of the window.  Use in place of self.__ysz"""
        adjHt = self.__ysz - min(0.05 * self.__ysz, self.__extraHeightMax)
        return adjHt

    def getTextPointSize(self, gkiTextScaleFactor, winWidth, winHeight):
        """ Make a decision on the best font size (point) based on the
            size of the graphics window and other factors """
        # The default point size for the initial window size
        dfltPtSz = 8.0
        WIN_SZ_FACTOR = 300.0  # honestly just trying a number that looks good

        # The contribution to the sizing from the window itself, could
        # be taken from just the height, but that would leave odd font
        # sizes in the very tall/thin windows.  Another option is to average
        # the w & h.  We will try taking the minimum.
        winSzContrib = min(winWidth, winHeight)
        ptSz = dfltPtSz * (winSzContrib / WIN_SZ_FACTOR)

        # The above gives us a proportionally sized font, but it can be larger
        # than what we are used to with the standard gkitkplot, so trim down
        # the large sizes.
        if (ptSz > dfltPtSz):
            ptSz = (ptSz + dfltPtSz) / 2.0

        # Now that the best standard size for this window has been
        # determined, apply the GKI text scale factor used to it (deflt: 1.0)
        ptSz = ptSz * gkiTextScaleFactor

        # leave as float (not N.float64), it'll get truncated by Text if needed
        return float(ptSz)

    def clearMplData(self):
        """ Clear all lines, patches, text, etc. from the figure as well
            as any of our own copies we may be keeping around to facilitate
            redraws/resizes/etc. of the figure. """
        self.__normLines = []  # clear our lines
        self.__normPatches = []  # clear our patches
        self.__fig.clear()  # clear all from fig

    def resizeGraphics(self, width, height):
        """ It is time to set a magnitude to our currently normalized
            lines, and send them to the figure. Here we assume that
            __normLines & __normPatches are already fully populated. """
        self.__fig.lines = []  # clear all old lines from figure
        self.__fig.patches = []  # clear all old patches from figure
        self.__xsz = width
        self.__ysz = height

        # scale each text item
        for t in self.__fig.texts:
            t.set_size(self.getTextPointSize(t.gkiTextSzFactor, width, height))

        # scale each line, then apply it to the figure
        for nrln in self.__normLines:
            ll = Line2D([], [])
            ll.update_from(nrln)
            ll.set_data(
                nrln.get_xdata(True) * self.__xsz,
                nrln.get_ydata(True) * self.__ysz)
            self.__fig.lines.append(ll)

        # scale each patch, then apply it to the figure
        for nrpa in self.__normPatches:
            rr = Rectangle((0, 0), 0, 0)
            rr.update_from(nrpa)
            rr.set_x(nrpa.get_x() * self.__xsz)
            rr.set_y(nrpa.get_y() * self.__ysz)
            rr.set_width(nrpa.get_width() * self.__xsz)
            rr.set_height(nrpa.get_height() * self.__ysz)
            self.__fig.patches.append(rr)

        # do not redraw here - we are called only to set the sizes
        # done

    def gcur(self):
        """Return cursor value after key is typed"""
        # BUT, before we rush into sending that gcur obj back, this happens to
        # be an excellent spot to redraw!  If we are an interactive task (yes
        # since they want a gcur) AND if we haven't been drawing because we
        # are saving draws for performance-sake, then do so now.
        if not self.__allowDrawing:
            self.gki_flush(None, force=True)
        # else, we have already been drawing, so no need to flush here

        # Now, do what we came here for.
        return self.__gcursorObject()

    def gcurTerminate(self, msg='Window destroyed by user'):
        """Terminate active gcur and set EOF flag"""
        if self.__gcursorObject.active:
            self.__gcursorObject.eof = msg
            # end the gcur mainloop -- this is what allows
            # closing the window to act the same as EOF
            self.top.quit()

    def pre_imcur(self):
        """ Override this so as to redraw if needed """
        # Just like in gcur(), this may be an excellent time to redraw.
        if not self.__allowDrawing:
            self.gki_flush(None, force=True)
        # else, we have already been drawing, so no need to flush here

    def prePageSelect(self):
        """ Override this so as to redraw when needed """
        self._forceNextDraw = True  # make sure to flush at end of redraw!

    def forceNextDraw(self):
        """ Override this so as to force a redraw at the next opportunity """
        self._forceNextDraw = True

    def taskStart(self, name):
        """ Because of redirection, this is not always called on the first plot
        but it should be called for every successive one. """
        # We take this opportuninty to simply set our draw-saving flag.
        self.__allowDrawing = False
        # Note the task command given to be shown in the status widget
        if readline is not None:
            self._toWriteAtNextClear = readline.get_history_item(
                readline.get_current_history_length())

    def taskDone(self, name):
        """Called when a task is finished"""
        # This is the usual hack to prevent the double redraw after first
        # Tk plot, but this version does not seem to suffer from the bug.
        #       self.doubleRedrawHack()

        # No need to draw now, UNLESS we haven't yet
        if not self.__allowDrawing:
            # If we have not yet made our first draw, then we need to now.
            # For interactive tasks, we should have drawn already (see gcur).
            # For non-interactive tasks, we will not have drawn yet.
            self.gki_flush(None, force=True)
        # else, we have already been drawing, so no need to flush here

    def update(self):
        """Update for all Tk events.
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
        """ This is a hack to prevent the double redraw on first plots. """
        # There is a mysterious Expose event that appears on the
        # idle list, but not until the Tk loop actually becomes idle.
        # The only approach that seems to work is to set this flag
        # and to ignore the event.
        # This is ugly but appears to work as far as I can tell.
        if not self.__firstPlotDone:
            self.__mca.ignoreNextRedraw = 1
            self.__firstPlotDone = 1

    def prepareToRedraw(self):
        """This is a hook for things that need to be done before the redraw
           from metacode.  We'll simply clear drawBuffer."""
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
        self.clearMplData()

    def clearPage(self):
        """Clear buffer for new page"""
        self.drawBuffer.reset()
        self.clearMplData()

    def isPageBlank(self):
        """Returns true if this page is blank"""
        # or, could use: return len(self.drawBuffer) == 0
        return len(self.__normLines) == 0 and \
            len(self.__normPatches) == 0 and \
            len(self.__fig.texts) == 0

    # -----------------------------------------------
    # Overrides of GkiInteractiveTkBase functions

    def activate(self):
        """Not really needed for Tkplot widgets (used to set OpenGL win)"""
        pass

    # -----------------------------------------------
    # GkiKernel implementation

    def incrPlot(self):
        """Plot any new commands in the buffer"""
        # This step slows us down but is needed, e.g. 'T' in implot.
        # So, save it for ONLY after we have allowed drawing.  This can
        # seriously hinder performance in interactive tasks but at least
        # we can avoid taking that hit until after gcur() is 1st called and
        # we are waiting on a human.  We *could* look into checking what the
        # actual incr/change was and see if it is worth redrawing.
        if self.gwidget and (self.__allowDrawing or self._forceNextDraw):
            active = self.gwidget.isSWCursorActive()
            if active:
                self.gwidget.deactivateSWCursor()
            # Render any new contents of draw buffer (this is costly).
            self.__mca.draw()  # in mpl v0.99, .draw() == .show()
            # Do NOT add the logic here (as in redraw()) to loop through the
            # drawBuffer func-arg pairs, calling apply(), using the
            # __skipPlotAppends attr. Do not do so since the MPL kernel version
            # keeps its own data cache and doesn't use the drawBuffer that way.
            if active:
                self.gwidget.activateSWCursor()
            # reset this no matter what
            self._forceNextDraw = False

    # special methods that go into the function tables

    def _plotAppend(self, plot_function, *args):
        """ Append a 2-tuple (plot_function, args) to the draw buffer """
        # Allow for this draw buffer append to be skipped at times
        if not self.__skipPlotAppends:
            self.drawBuffer.append((plot_function, args))

        # Run _noteGkiCmd here as well, as almost all gki_* funcs call us
#       self._noteGkiCmd(plot_function)

#   def _noteGkiCmd(self, cmdFunc):
#       """ Append the func to our history, but keep the len constant. """
# Track any and all gki commands - this is used for pattern watching
# in the gki stream, not for redraws.  Track the func itself.
# Since we track everything, we can't just use the drawBuffer here.
#       self.__lastGkiCmds = self.__lastGkiCmds[1:] + (cmdFunc,)

    def gki_clearws(self, arg):

        # don't put clearws command in the draw buffer, just clear the display
        self.clear()
        # clear the canvas
        self.clearMplData()
        self.__mca.draw()

        # Note this explicitly (not for redrawing) since _plotAppend isn't used
#       self._noteGkiCmd(self.gki_clearws)

    def gki_cancel(self, arg):

        self.gki_clearws(arg)

        # Note this explicitly (not for redrawing) since _plotAppend isn't used
#       self._noteGkiCmd(self.gki_cancel)

    def gki_flush(self, arg, force=False):
        """ Asked to render current plot immediately.  Also used by redraw().
        NOTE: This is called multiple times (~8) for a single prow
        call.  There is a performance improvement gained by skipping the
        resize calculation between taskStart() and taskDone().  This class
        adds the 'force' arg which forces it to redraw once whether we are
        "saving draws" or not. """
        # don't put flush command into the draw buffer
        if self.__allowDrawing or force:
            self.resizeGraphics(self.__xsz,
                                self.__ysz)  # do NOT use adjusted y!
            self.__mca.draw()
            self.__mca.flush()

        # Note this explicitly (not for redrawing) since _plotAppend isn't used
#       self._noteGkiCmd(self.gki_flush)

    def gki_polyline(self, arg):
        """ Instructed to draw a GKI polyline """
        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_polyline, arg)

        # commit pending WCS changes when draw is found
        self.wcs.commit()

        # Reshape to get x's and y's
        # arg[0] is the num pairs, so: len(arg)-1 == 2*arg[0]
        verts = gki.ndc(arg[1:])
        rshpd = verts.reshape(arg[0], 2)
        xs = rshpd[:, 0]
        ys = rshpd[:, 1]

        # Put the normalized data into a Line2D object, append to our list.
        # Later we will scale it and append it to the fig.  For the sake of
        # performance, don't draw now, it slows things down.
        # Note that for each object we make and store here (which is
        # normalized), there will be a second (sized) copy of the same object
        # created in resizeGraphics().  We could consider storing this data
        # in some other way for speed, but perf. tests for #122 showed
        # that this use of multiple object creation wasn't a big hit at all.
        ll = Line2D(xs,
                    ys,
                    linestyle=self.lineAttributes.linestyle,
                    linewidth=GKI_TO_MPL_LINEWIDTH *
                    self.lineAttributes.linewidth,
                    color=self.lineAttributes.color)
        self.__normLines.append(ll)

        # While we are here and obviously getting drawing commands from the
        # task, set our draw-saving flag.  This covers the case of the
        # interactive task during a redraw from a user-typed 'r'.  That entire
        # case goes: 1) no drawing during initial plot creation, 2) task is
        # done giving us gki commands when gcur() seen, so drawing is allowed
        # 3) user types 'r' or similar to cause a redraw so this turns off
        # drawing again (to speed it up) until the next gcur() is seen.
        self.__allowDrawing = False

    def gki_polymarker(self, arg):
        """ Instructed to draw a GKI polymarker.  IRAF only implements
        points for polymarker, so that makes it simple. """
        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_polymarker, arg)

        # commit pending WCS changes when draw is found
        self.wcs.commit()

        # Reshape to get x's and y's
        # arg[0] is the num pairs, so: len(arg)-1 == 2*arg[0]
        verts = gki.ndc(arg[1:])
        rshpd = verts.reshape(arg[0], 2)
        xs = rshpd[:, 0]
        ys = rshpd[:, 1]

        # put the normalized data into a Line2D object, append to our list
        # later we will scale it and append it to the fig.  See performance
        # note in gki_polyline()
        ll = Line2D(xs,
                    ys,
                    linestyle='',
                    marker='.',
                    markersize=3.0,
                    markeredgewidth=0.0,
                    markerfacecolor=self.markerAttributes.color,
                    color=self.markerAttributes.color)
        self.__normLines.append(ll)

    def calculateMplTextAngle(self, charUp, textPath):
        """ From the given GKI charUp and textPath values, calculate the
        rotation angle to be used for text.  Oddly, it seems that textPath
        and charUp both serve similar purposes, so we will have to look at
        them both in order to figure the rotation angle.  One might have
        assumed that textPath could have meant "L to R" vs. "R to L", but
        that does not seem to be the case - it seems to be rotation angle. """

        # charUp range
        if charUp < 0:
            charUp += 360.
        charUp = math.fmod(charUp, 360.)

        # get angle from textPath
        angle = charUp + 270.  # deflt CHARPATH_RIGHT
        if textPath == textattrib.CHARPATH_UP:
            angle = charUp
        elif textPath == textattrib.CHARPATH_LEFT:
            angle = charUp + 90.
        elif textPath == textattrib.CHARPATH_DOWN:
            angle = charUp + 180.

        # return from 0-360
        return math.fmod(angle, 360.)

    def gki_text(self, arg):
        """ Instructed to draw some GKI text """
        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_text, arg)

        # commit pending WCS changes
        self.wcs.commit()

        # add the text
        x = gki.ndc(arg[0])
        y = gki.ndc(arg[1])
        text = arg[3:].astype(numpy.int8).tobytes().encode('ascii')
        ta = self.textAttributes

        # For now, force this to be non-bold for decent looking plots.  It
        # seems (oddly) that IRAF/GKI tends to overuse boldness in graphics.
        # A fix to mpl (near 0.91.2) makes bold text show as reeeeally bold.
        # However, assume the user knows what they are doing with their
        # settings if they have set a non-standard (1.0) charSize.
        weight = 'normal'
        if (MPL_MAJ_MIN < 0.91) or (abs(ta.charSize - 1.0) > .0001):
            # only on these cases do we pay attention to 'bold' in textFont
            if ta.textFont.find('bold') >= 0:
                weight = 'bold'

        style = 'italic'
        if ta.textFont.find('italic') < 0:
            style = 'normal'
        # Calculate initial fontsize
        fsz = self.getTextPointSize(ta.charSize, self.__xsz, self.__ysz)
        # figure rotation angle
        rot = self.calculateMplTextAngle(ta.charUp, ta.textPath)
        # Kludge alert - only use the GKI_TEXT_Y_OFFSET in cases where
        # we know the text is a simple level label (not in a contour, etc)
        yOffset = 0.0
        if abs(rot) < .0001 and ta.textHorizontalJust == 'center':
            yOffset = GKI_TEXT_Y_OFFSET
        # Note that we add the text here in NDC (0.0-1.0) x,y and that
        # the fig takes care of resizing for us.
        t = self.__fig.text(
            x,
            y - yOffset,
            text,
            color=ta.textColor,
            rotation=rot,
            horizontalalignment=ta.textHorizontalJust,
            verticalalignment=ta.textVerticalJust,
            fontweight=weight,  # [ 'normal' | 'bold' | ... ]
            fontstyle=style,  # [ 'normal' | 'italic' | 'oblique']
            fontsize=fsz)
        # To this Text object just created, we need to attach the GKI charSize
        # scale factor, since we will need it later during a resize.  Mpl
        # knows nothing about this, but we support it for GKI.
        t.gkiTextSzFactor = ta.charSize  # add attribute

    def gki_fillarea(self, arg):
        """ Instructed to draw a GKI fillarea """
        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_fillarea, arg)

        # commit pending WCS changes
        self.wcs.commit()

        # plot the fillarea
        fa = self.fillAttributes
        verts = gki.ndc(arg[1:])
        # fillstyle 0=clear,  1=hollow,  2=solid,  3-6=hatch
        # default case is 'solid' (fully filled solid color)
        # 'hatch' case seems to be unused
        ec = fa.color
        fc = fa.color
        fll = 1
        if fa.fillstyle == 0:  # 'clear' (fully filled with black)
            ec = self.colorManager.setDrawingColor(0)
            fc = ec
            fll = 1
        if fa.fillstyle == 1:  # 'hollow' (just the rectangle line, empty)
            ec = fa.color
            fc = None
            fll = 0
        lowerleft = (verts[0], verts[1])
        width = verts[4] - verts[0]
        height = verts[5] - verts[1]
        rr = Rectangle(lowerleft,
                       width,
                       height,
                       edgecolor=ec,
                       facecolor=fc,
                       fill=fll)
        self.__normPatches.append(rr)

    def gki_putcellarray(self, arg):

        self.wcs.commit()
        self.errorMessage(gki.standardNotImplemented % "GKI_PUTCELLARRAY")

    def gki_setcursor(self, arg):

        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_setcursor, arg)

        # get x and y
        x = gki.ndc(arg[1])
        y = gki.ndc(arg[2])
        # Update the sw cursor object (A clear example of why this update
        # is needed is how 'apall' re-centers the cursor w/out changing y, when
        # the user types 'r'; without this update, the two cursors separate.)
        swCurObj = self.__mca.getSWCursor()
        if swCurObj:
            swCurObj.moveTo(x, y, SWmove=1)
        # wutil.moveCursorTo uses 0,0 <--> upper left, need to convert
        sx = int(x * self.gwidget.winfo_width())
        sy = int((1 - y) * self.gwidget.winfo_height())
        rx = self.gwidget.winfo_rootx()
        ry = self.gwidget.winfo_rooty()
        # call the wutil version to move the cursor
        moveCursorTo(self.gwidget.winfo_id(), rx, ry, sx, sy)

    def gki_plset(self, arg):

        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_plset, arg)

        # Handle case where some terms (eg. xgterm) allow higher values,
        # by looping over the possible visible patterns.  (ticket #172)
        arg0 = arg[0]
        if arg0 >= len(GKI_TO_MPL_LINESTYLE):
            num_visible = len(GKI_TO_MPL_LINESTYLE) - 1
            arg0 = 1 + (arg0 % num_visible)

        # Note that GkiTkplotKernel saves color (arg[2]) in numeric format,
        # but we keep it in the rgb strng form which mpl can readily use.
        # Same note for linestyle, changed from number to mpl symbol.
        self.lineAttributes.set(
            GKI_TO_MPL_LINESTYLE[arg0],  # linestyle
            arg[1] / gki.GKI_FLOAT_FACTOR,  # linewidth
            self.colorManager.setDrawingColor(arg[2]))

    def gki_pmset(self, arg):

        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_pmset, arg)

        # set attrs.  See notes about GKI_TO_MPL_MARKTYPE
        self.markerAttributes.set(
            0,  # GKI_TO_MPL_MARKTYPE[arg[0]] ! type unused
            0,  # gki.ndc(arg[1])             ! size unused
            self.colorManager.setDrawingColor(arg[2]))

    def gki_txset(self, arg):

        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_txset, arg)

        # Set text attrs
        # charSize: To quote from tkplottext.py:
        #    "We draw the line at fontSizes less than 1/2! Get real."
        # without the 0.5 floor, "contour dev$pix" ticklabels are too small
        charUp = float(arg[0])  # default: 90.0
        charSize = max(0.5, arg[1] / gki.GKI_FLOAT_FACTOR)  # default: 1.0
        charSpace = arg[2] / gki.GKI_FLOAT_FACTOR  # unused yet (0.0)
        textPath = arg[3]  # leave as GKI code
        # btw, in unit testsing never saw a case where textPath != 3
        textHorizontalJust = GKI_TO_MPL_HALIGN[arg[4]]
        textVerticalJust = GKI_TO_MPL_VALIGN[arg[5]]
        textFont = GKI_TO_MPL_FONTATTR[arg[6]]
        textQuality = GKI_TO_MPL_FONTATTR[arg[7]]  # unused ? (lo,md,hi)
        textColor = self.colorManager.setDrawingColor(arg[8])
        self.textAttributes.set(charUp, charSize, charSpace, textPath,
                                textHorizontalJust, textVerticalJust, textFont,
                                textQuality, textColor)

    def gki_faset(self, arg):

        # record this operation as a tuple in the draw buffer
        self._plotAppend(self.gki_faset, arg)

        # set the fill attrs
        self.fillAttributes.set(
            arg[0],  # fillstyle
            self.colorManager.setDrawingColor(arg[1]))

    def gki_getcursor(self, arg):

        raise NotImplementedError(gki.standardNotImplemented % "GKI_GETCURSOR")

    def gki_getcellarray(self, arg):

        raise NotImplementedError(gki.standardNotImplemented %
                                  "GKI_GETCELLARRAY")

    def gki_unknown(self, arg):

        self.errorMessage(gki.standardWarning % "GKI_UNKNOWN")

        # Note this explicitly (not for redrawing) since _plotAppend isn't used
#       self._noteGkiCmd(self.gki_unknown)

    def gRedraw(self):

        if self.gwidget:
            self.gwidget.tkRedraw()

    def redraw(self, o=None):
        """Redraw for expose or resize events, also called when page menu is
        used.  This method generally should not be called directly -- call
        gwidget.tkRedraw() instead since it does some other
        preparations.
        """
        # Argument o is not needed because we only get redraw
        # events for our own gwidget.
        #
        # DESIGN NOTE:  Make sure this is not getting called for window
        # resizes!  Using the drawBuffer is too slow and unnecessary.  Resizes
        # should only be hooking into resizeGraphics() for performance sake.

        # See if we need to force the flush (of course wait until the end)
        frc = self._forceNextDraw
        self._forceNextDraw = False

        # Clear the screen
        self.clearMplData()
        # Plot the current buffer
        self.__skipPlotAppends = True
        for (function, args) in self.drawBuffer.get():
            function(*args)
        self.__skipPlotAppends = False
        self.gki_flush(None, force=frc)  # does: resize-calc's; draw; flush


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
        """Not needed for Tkplot, a noop"""
        pass

    def setCursorColor(self, irafColorIndex=None):
        """Set crosshair cursor color to given index.
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
