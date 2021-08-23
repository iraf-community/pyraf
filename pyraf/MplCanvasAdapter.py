import matplotlib
matplotlib.use('TkAgg')  # set backend
import matplotlib.backends.backend_tkagg as tkagg
from .Ptkplot import hideTkCursor
from .Ptkplot import FullWindowCursor
import tk
from .wutil import moveCursorTo, WUTIL_USING_X


class MplCanvasAdapter(tkagg.FigureCanvasTkAgg):
    """ Is a FigureCanvasTkAgg, with extra methods to look like Canvas """

    def __init__(self, gkikernel, figure, master=None):
        tkagg.FigureCanvasTkAgg.__init__(self, figure, master)
        # members
        self.__theGwidget = self.get_tk_widget()  # THE gwidget
        self.__gkiKernel = gkikernel
        self.__doIdleRedraw = 0
        self.__doIdleSWCursor = 0
        self.ignoreNextRedraw = 0  # used externally to this class ...

        # Add a placeholder software cursor attribute. If it is None,
        # that means no software cursor is in effect. If it is not None,
        # then it will be used to render the cursor.
        self.__isSWCursorActive = 0
        self.__SWCursor = None

        # Basic bindings for the virtual trackball.
        # ! Do NOT set these without undergoing a major GkiMpl design
        # check !  Binding Expose to tkExpose forces tkRedraw to be
        # called WAY too many times during a window resize. This uses the
        # draw buffer, which is slow and unnecessary for resizes.
        #       self.__theGwidget.bind('<Expose>', self.tkExpose)
        #       self.__theGwidget.bind('<Configure>', self.tkExpose) # init draw issue
        self.__theGwidget.bind('<Configure>', self.resize_widget, True)

    def pack(self, **kw):
        """ delegate to the gwidget """
        self.__theGwidget.pack(kw)

    def winfo_id(self):
        """ delegate to the gwidget """
        self.__theGwidget.winfo_id()

    def gwidgetize(self, width, height):
        """ This is a one-stop shopping spot to add all the extra attributes
        to the gwidget object it needs to be seen as a "gwidget" in the GKI
        sense. See requirements in GkiInteractiveTkBase. """

        gw = self.__theGwidget

        # Add attributes to the gwidget
        gw.lastX = None
        gw.lastY = None
        gw.width = width
        gw.height = height

        # Add our functions to the gwidget
        gw.activateSWCursor = self.activateSWCursor
        gw.deactivateSWCursor = self.deactivateSWCursor
        gw.isSWCursorActive = self.isSWCursorActive
        gw.getSWCursor = self.getSWCursor
        gw.moveCursorTo = self.moveCursorTo
        gw.tkRedraw = self.tkRedraw

    def resize_widget(self, event):
        width, height = event.width, event.height
        # See also get/set_size_inches, figure.get_window_extent().  The latter
        # is Bbox, use .width/.height()
        #
        #  before rsz: w = self.figure.get_window_extent().width # not func .98
        #  before rsz: h = self.figure.get_window_extent().height() # is in .91
        # Need to deactivate cursor before resizing, then re-act. after
        self.wrappedRedrawOrResize(w=width, h=height)

        # also update the widget's w/h attrs; we will need this for the cursor
        self.__theGwidget.width = width
        self.__theGwidget.height = height

        # compute desired figure size in inches
        dpival = self.figure.dpi
        winch = width / dpival
        hinch = height / dpival
        self.figure.set_size_inches(winch, hinch, forward=False)

        self._tkcanvas.delete(self._tkphoto)
        self._tkphoto = tk.PhotoImage(master=self._tkcanvas,
                                      width=int(width),
                                      height=int(height))
        self._tkcanvas.create_image(int(width / 2),
                                    int(height / 2),
                                    image=self._tkphoto)
        self.resize_event()

    def flush(self):

        self.__doIdleRedraw = 0

    # draw could be defined to catch events before passing through


#   def draw(self):  tkagg.FigureCanvasTkAgg.draw(self)

    def wrappedRedrawOrResize(self, w=None, h=None):
        """Wrap the redraw (or resize) with a deactivate and then re-activate
        of the cursor.  If w or h are provided then we are only resizing."""

        # need to indicate cursor is not visible before this, since
        # cursor sleeps are now issued by redraw. The presumption is that
        # redraw/resize will affect cursor visibility, so we set it first
        resizing = w is not None
        cursorActivate = 0

        if self.__isSWCursorActive:
            # deactivate cursor for duration of redraw
            # otherwise it slows the redraw to a glacial pace
            cursorActivate = 1
            x = self.__SWCursor.lastx
            y = self.__SWCursor.lasty
            self.deactivateSWCursor()

        if resizing:
            self.__gkiKernel.resizeGraphics(w, h)
        else:
            # should document how this line gets to GkiMplKernel.redraw()
            self.__theGwidget.redraw(self.__theGwidget)

        if cursorActivate:
            # Need to activate it, but don't draw it if only resizing, there is
            # a bug where the previous crosshair cursor is drawn too.
            self.activateSWCursor(x, y, drawToo=(not resizing))

    # tkRedraw() is used as if it belonged to the gwidget's class
    def tkRedraw(self, *dummy):
        """ delegate to the gwidget """
        gw = self.__theGwidget
        self.__doIdleRedraw = 1
        gw.after_idle(self.idleRedraw)

    def idleRedraw(self):
        """Do a redraw, then set buffer so no more happen on this idle cycle"""
        if self.__doIdleRedraw:
            self.__doIdleRedraw = 0
            self.wrappedRedrawOrResize()

    # isSWCursorActive() is used as if it belonged to the gwidget's class
    def isSWCursorActive(self):
        """ getter """
        return self.__isSWCursorActive

    # activateSWCursor() is used as if it belonged to the gwidget's class
    def activateSWCursor(self, x=None, y=None, type=None, drawToo=True):

        gw = self.__theGwidget
        hideTkCursor(gw)  # from Ptkplot
        # ignore type for now since only one type of software cursor
        # is implemented
        gw.update_idletasks()
        if not self.__isSWCursorActive:
            if not self.__SWCursor:
                self.__SWCursor = FullWindowCursor(0.5, 0.5, gw)
            self.__isSWCursorActive = 1
            gw.bind("<Motion>", self.moveCursor)
        if drawToo and not self.__SWCursor.isVisible():
            self.__SWCursor.draw()

    # deactivateSWCursor() is used as if it belonged to the gwidget's class
    def deactivateSWCursor(self):

        gw = self.__theGwidget
        gw.update_idletasks()
        if self.__isSWCursorActive:
            self.__SWCursor.erase()
            gw.unbind("<Motion>")
            self.__SWCursor.isLastSWmove = 1
            self.__isSWCursorActive = 0
            gw['cursor'] = 'arrow'  # set back to normal

    # getSWCursor() is used as if it belonged to the gwidget's class
    def getSWCursor(self):
        """ getter """
        return self.__SWCursor

    def SWCursorWake(self):
        """ Wake cursor only after idle """
        self.__doIdleSWCursor = 1
        self.after_idle(self.idleSWCursorWake)

    def idleSWCursorWake(self):
        """Do cursor redraw, then reset so no more happen on this idle cycle"""
        if self.__doIdleSWCursor:
            self.__doIdleSWCursor = 0
            self.SWCursorImmediateWake()

    def SWCursorImmediateWake(self):

        if self.__isSWCursorActive:
            self.__SWCursor.draw()

    def moveCursor(self, event):
        """Call back for mouse motion events"""
        # Kludge to handle the fact that MacOS X (X11) doesn't remember
        # software driven moves, the first move will just move nothing
        # but will properly update the coordinates.  Do not do this under Aqua.
        gw = self.__theGwidget
        if WUTIL_USING_X and self.__SWCursor.isLastSWmove:
            x = self.__SWCursor.lastx
            y = self.__SWCursor.lasty
            # call the wutil version
            moveCursorTo(gw.winfo_id(), gw.winfo_rootx(), gw.winfo_rooty(),
                         int(x * gw.winfo_width()),
                         int((1. - y) * gw.winfo_height()))
        else:
            x = (event.x + 0.5) / gw.winfo_width()
            y = 1. - (event.y + 0.5) / gw.winfo_height()
        self.__SWCursor.moveTo(x, y, SWmove=0)

    # moveCursorTo() is used as if it belonged to the gwidget's class
    def moveCursorTo(self, x, y, SWmove=0):

        self.__SWCursor.moveTo(
            float(x) / self.__theGwidget.width,
            float(y) / self.__theGwidget.height, SWmove)

    def activate(self):
        """Not really needed for Tkplot widgets"""
        pass

    def tkExpose(self, *dummy):
        """Redraw the widget upon the tkExpose event.
        Make it active, update tk events, call redraw procedure."""
        if self.ignoreNextRedraw:
            self.ignoreNextRedraw = 0
        else:
            self.tkRedraw()
