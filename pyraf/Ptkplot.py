import os
from tkinter import _default_root
from tkinter import TclError, Canvas
from . import wutil

# XBM file for cursor is in same directory as this module
_blankcursor = 'blankcursor.xbm'
dirname = os.path.dirname(__file__)
if os.path.isabs(dirname):
    _blankcursor = os.path.join(dirname, _blankcursor)
else:
    # change relative directory paths to absolute
    _blankcursor = os.path.join(os.getcwd(), dirname, _blankcursor)
del dirname

_TK_HAS_NONE_CURSOR = True  # assume True until we learn otherwise

if _default_root is None:
    from stsci.tools import irafutils
    _default_root = irafutils.init_tk_default_root()

# This code is needed to avoid faults on sys.exit()
# [DAA, Jan 1998]
# [Modified by RLW to use new atexit module, Dec 2001]


def cleanup():
    try:
        from tkinter import _default_root, TclError
        import tkinter
        try:
            if _default_root:
                _default_root.destroy()
        except TclError:
            pass
        tkinter._default_root = None
    except SystemError:
        # If cleanup() is called before pyraf fully loads, we will
        # see: "SystemError: Parent module 'pyraf' not loaded".  In that case,
        # since nothing was done yet w/ _default_root, we can safely skip this.
        pass


import atexit
atexit.register(cleanup)
# [end DAA]

# crosshair cursor color (only has an effect in indexed color mode)
# this is global so that it applies to all Ptkplot widgets
cursorColor = 1
cursorTrueColor = (1.0, 0.0, 0.0)
# visuals that use true colors
truevis = {
    'truecolor': 1,
    'directcolor': 1,
}


def hideTkCursor(theCanvas):
    """ Make the existing cursor disappear. """
    # Make the existing cursor disappear.  There currently isn't a
    # better way to disable a cursor in Tk. In Tk 8.5, there will be a
    # 'none' option to set the cursor to.  Until then, load a blank cursor
    # from an XBM file - is in same directory as this module. Might, on OSX
    # only, be able to use: CGDisplay[Hide,Show]Cursor() - the problem with
    # this is that the cursor s gone even when trying to use menu items, as
    # long as the GUI is the front process.
    #
    # Note - the blankcursor format is causing errors on some non-Linux
    # platforms, so we need to use 'none' or 'tcross' for now.

    global _TK_HAS_NONE_CURSOR
    global _blankcursor

    if _TK_HAS_NONE_CURSOR:
        # See if this supports the 'none' cursor
        try:
            theCanvas['cursor'] = 'none'
            return
        except TclError:
            _TK_HAS_NONE_CURSOR = False

    # If we get here, the 'none' cursor is not yet supported.  Load the blank
    # one, or use 'tcross'.
    if wutil.WUTIL_USING_X:
        theCanvas['cursor'] = '@' + _blankcursor + ' black'
    else:
        theCanvas['cursor'] = 'tcross'  # this'll do for now


class PyrafCanvas(Canvas):
    """Widget"""

    def __init__(self, master=None, **kw):

        Canvas.__init__(self, master, kw)
        self.doIdleRedraw = 0
        self.doIdleSWCursor = 0
        self.ignoreNextRedraw = 0
        # Add a placeholder software cursor attribute. If it is None,
        # that means no software cursor is in effect. If it is not None,
        # then it will be used to render the cursor.
        self._isSWCursorActive = 0
        self._SWCursor = None
        self.initialised = 0

        # to save last cursor position if switching to another window
        self.lastX = None
        self.lastY = None
        self.width = self.winfo_width()  # to avoid repeated calls
        self.height = self.winfo_height()

        # Basic bindings for the virtual trackball
        self.bind('<Expose>', self.tkExpose)
        self.bind('<Configure>', self.tkExpose)
        # self.after_idle(self.refresh_cursor)

    def flush(self):

        self.doIdleRedraw = 0

    def immediateRedraw(self):

        # need to indicate cursor is not visible before redraw, since
        # cursor sleeps are now issued by redraw. The presumption is that
        # redraw will wipe out cursor visibility, so we set it first
        if self._isSWCursorActive:
            # deactivate cursor for duration of redraw
            # otherwise it slows the redraw to a glacial pace
            cursorActivate = 1
            x = self._SWCursor.lastx
            y = self._SWCursor.lasty
            self.deactivateSWCursor()
        else:
            cursorActivate = 0
        self.redraw(self)
        if cursorActivate:
            self.activateSWCursor(x, y)

    def tkRedraw(self, *dummy):
        self.doIdleRedraw = 1
        self.after_idle(self.idleRedraw)

    def idleRedraw(self):
        """Do a redraw, then set buffer so no more happen on this idle cycle"""
        if self.doIdleRedraw:
            self.doIdleRedraw = 0
            self.immediateRedraw()

    def isSWCursorActive(self):
        return self._isSWCursorActive

    def activateSWCursor(self, x=None, y=None, type=None):
        hideTkCursor(self)
        # ignore type for now since only one type of software cursor
        # is implemented
        self.update_idletasks()
        if not self._isSWCursorActive:
            if not self._SWCursor:
                self._SWCursor = FullWindowCursor(0.5, 0.5, self)
            self._isSWCursorActive = 1
            self.bind("<Motion>", self.moveCursor)
        if not self._SWCursor.isVisible():
            self._SWCursor.draw()

    def deactivateSWCursor(self):
        self.update_idletasks()
        if self._isSWCursorActive:
            self._SWCursor.erase()
            self.unbind("<Motion>")
            self._SWCursor.isLastSWmove = 1
            self._isSWCursorActive = 0
            self['cursor'] = 'arrow'

    def getSWCursor(self):
        return self._SWCursor

    def SWCursorWake(self):
        self.doIdleSWCursor = 1
        self.after_idle(self.idleSWCursorWake)

    def idleSWCursorWake(self):
        """Do cursor redraw, then reset so no more happen on this idle cycle"""
        if self.doIdleSWCursor:
            self.doIdleSWCursor = 0
            self.SWCursorImmediateWake()

    def SWCursorImmediateWake(self):
        if self._isSWCursorActive:
            self._SWCursor.draw()

    def moveCursor(self, event):
        """Call back for mouse motion events"""

        # Kludge to handle the fact that MacOS X (X11) doesn't remember
        # software driven moves, the first move will just move nothing
        # but will properly update the coordinates.  Do not do this under Aqua.
        if wutil.WUTIL_USING_X and self._SWCursor.isLastSWmove:
            x = self._SWCursor.lastx
            y = self._SWCursor.lasty
            wutil.moveCursorTo(self.winfo_id(), self.winfo_rootx(),
                               self.winfo_rooty(), int(x * self.winfo_width()),
                               int((1. - y) * self.winfo_height()))
        else:
            x = (event.x + 0.5) / self.winfo_width()
            y = 1. - (event.y + 0.5) / self.winfo_height()
        self._SWCursor.moveTo(x, y, SWmove=0)

    def moveCursorTo(self, x, y, SWmove=0):
        self._SWCursor.moveTo(
            float(x) / self.width,
            float(y) / self.height, SWmove)

    def activate(self):
        """Not really needed for Tkplot widgets (used to set OpenGL win)"""
        pass

    def set_background(self, r, g, b):
        """Change the background color of the widget."""

        self.tkRedraw()

    def tkExpose(self, *dummy):
        """Redraw the widget.
        Make it active, update tk events, call redraw procedure and
        swap the buffers.  Note: swapbuffers is clever enough to
        only swap double buffered visuals."""
        self.width = self.winfo_width()
        self.height = self.winfo_height()
        if self.ignoreNextRedraw:
            self.ignoreNextRedraw = 0
        else:
            if not self.initialised:
                self.initialised = 1
            self.tkRedraw()


class FullWindowCursor:
    """This implements a full window crosshair cursor.  This class can
       operate in the xutil-wrapping mode or in a tkinter-only mode. """

    # Perhaps this should inherit from an abstract Cursor class eventually

    def __init__(self, x, y, window):
        """Display the cursor for the first time.  The passed in window
           also needs to act as a Tk Canvas object."""

        self.lastx = x
        self.lasty = y
        self.__useX11 = wutil.WUTIL_USING_X and (not wutil.WUTIL_ON_MAC)
        self.__window = window
        self.__isVisible = 0
        self.isLastSWmove = 1  # indicates if last position driven by
        # sofware command or by mouse events.
        # Kludgy, and used by modules using the
        # cursor position.
        self.__tkHorLine = None
        self.__tkVerLine = None
        self.draw()

    def _xutilXorDraw(self):

        wutil.drawCursor(self.__window.winfo_id(), self.lastx, self.lasty,
                         int(self.__window.width), int(self.__window.height))

    def _tkDrawCursor(self):

        self._tkEraseCursor()

        # coords and window sizes
        ww = self.__window.width
        wh = self.__window.height
        x = self.lastx * ww
        y = (1.0 - self.lasty) * wh

        # Draw the crosshairs.  __window is a Tk Canvas object
        self.__tkHorLine = self.__window.create_line(0, y, ww, y, fill='red')
        self.__tkVerLine = self.__window.create_line(x, 0, x, wh, fill='red')

    def _tkEraseCursor(self):

        if self.__tkHorLine is not None:
            self.__window.delete(self.__tkHorLine)
            self.__tkHorLine = None
        if self.__tkVerLine is not None:
            self.__window.delete(self.__tkVerLine)
            self.__tkVerLine = None

    def isVisible(self):
        return self.__isVisible

    def erase(self):

        if self.__isVisible:
            if self.__useX11:
                self._xutilXorDraw()
            else:
                self._tkEraseCursor()
        self.__isVisible = 0

    def draw(self):

        if not self.__isVisible:
            if self.__useX11:
                self._xutilXorDraw()
            else:
                self._tkDrawCursor()
        self.__isVisible = 1

    def moveTo(self, x, y, SWmove=0):

        if (self.lastx != x) or (self.lasty != y):
            self.erase()  # erase previous cursor
            self.lastx = x
            self.lasty = y
            self.draw()  # xdraw new position
        if SWmove:
            self.isLastSWmove = 1
        else:
            self.isLastSWmove = 0
