#!/usr/bin/env python


"""
$Id$
"""

import os
from Tkinter import _default_root
from Tkinter import *
import xutil, wutil
import sys, time

# XBM file for cursor is in same directory as this module
_blankcursor = 'blankcursor.xbm'
dirname = os.path.dirname(__file__)
if os.path.isabs(dirname):
    _blankcursor = os.path.join(dirname, _blankcursor)
else:
    # change relative directory paths to absolute
    _blankcursor = os.path.join(os.getcwd(), dirname, _blankcursor)
del dirname

if _default_root is None:
    # create the initial Tk window and immediately withdraw it
    import Tkinter
    if not Tkinter._default_root:
        _default_root = Tkinter.Tk()
    else:
        _default_root = Tkinter._default_root
    _default_root.withdraw()
    del Tkinter

# This code is needed to avoid faults on sys.exit()
# [DAA, Jan 1998]
# [Modified by RLW to use new atexit module, Dec 2001]

def cleanup():
    from Tkinter import _default_root, TclError
    import Tkinter
    try:
        if _default_root: _default_root.destroy()
    except TclError:
        pass
    Tkinter._default_root = None
import atexit
atexit.register(cleanup)
# [end DAA]

# crosshair cursor color (only has an effect in indexed color mode)
# this is global so that it applies to all Ptogl widgets
cursorColor = 1
cursorTrueColor = (1.0, 0.0, 0.0)
# visuals that use true colors
truevis = {
          'truecolor' : 1,
          'directcolor' : 1,
          }

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
        self.width  = self.winfo_width() # to avoid repeated calls
        self.height = self.winfo_height()

        # Basic bindings for the virtual trackball
        self.bind('<Expose>', self.tkExpose)
        self.bind('<Configure>', self.tkExpose)
        #self.after_idle(self.refresh_cursor)

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
            self.activateSWCursor(x,y)

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
        # Load a blank cursor from a file (isn't there a better way
        # to disable a cursor in Tk?).
        # XBM file for cursor is in same directory as this module
        global _blankcursor
        self['cursor'] = '@' + _blankcursor + ' black'
        # ignore type for now since only one type of software cursor
        # is implemented
        self.update_idletasks()
        if not self._isSWCursorActive:
            if not self._SWCursor:
                self._SWCursor = FullWindowCursor(0.5, 0.5, self)
            self._isSWCursorActive = 1
            self.bind("<Motion>",self.moveCursor)
        if not self._SWCursor.isVisible:
            self._SWCursor.draw()

    def deactivateSWCursor(self):
        self.update_idletasks()
        if self._isSWCursorActive:
            self._SWCursor.erase()
            self.unbind("<Motion>")
            self._SWCursor.isLastSWmove = 1
            self._isSWCursorActive = 0
            self['cursor'] = 'arrow'

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

        # Kludge to handle the fact that Mac OS X x doesn't remember
        # software driven moves, the first move will just move nothing
        # but will properly update the coordinates
        if self._SWCursor.isLastSWmove:
            x = self._SWCursor.lastx
            y = self._SWCursor.lasty
            wutil.moveCursorTo(self.winfo_id(),
                               int(x*self.winfo_width()),
                               int((1.-y)*self.winfo_height()))
        else:
            x = (event.x+0.5)/self.winfo_width()
            y = 1.-(event.y+0.5)/self.winfo_height()
        self._SWCursor.moveTo(x,y,SWmove=0)

    def moveCursorTo(self, x, y, width, height, SWmove=0):
        self._SWCursor.moveTo(float(x)/width,
                              float(y)/height,
                              SWmove)

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
    """This implements a  full window crosshair cursor"""
    # Perhaps this should inherit from an abstract Cursor class eventually

    def __init__(self, x, y, window=None):

        """Display the cursor for the first time"""

        self.lastx = x
        self.lasty = y
        self.window = window
        self.isVisible = 0
        self.isLastSWmove = 1 # indicates if last position driven by
                              # sofware command or by mouse events.
                              # Kludgy, and used by modules using the
                              # cursor position.
        self.draw()

    def xorDraw(self):

        xutil.drawCursor(self.window.winfo_id(), self.lastx, self.lasty,
                         self.window.width, self.window.height)

    def erase(self):

        if self.isVisible:
            self.xorDraw()
            self.isVisible = 0

    def draw(self):

        if not self.isVisible:
            self.xorDraw()
            self.isVisible = 1

    def moveTo(self,x,y, SWmove=0):

        if (self.lastx != x) or (self.lasty != y):
            self.erase() # erase previous cursor
            self.lastx = x
            self.lasty = y
            self.draw() # xdraw new position
        if SWmove:
            self.isLastSWmove = 1
        else:
            self.isLastSWmove = 0
