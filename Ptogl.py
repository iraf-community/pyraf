#!/usr/bin/env python


"""
Adapted from that distributed in the Tk.__init__ file that came with
PyOpenGL. (to get rid of 3-d cursor effects among other things)

$Id$
"""

import os, toglcolors
from OpenGL.GL import *
from OpenGL.GLU import *
from Tkinter import _default_root
from Tkinter import *

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
    Tk().tk.call('package', 'require', 'Togl')
    _default_root = Tkinter._default_root
    _default_root.withdraw()
    del Tkinter
else:
    _default_root.tk.call('package', 'require', 'Togl')

# This code is needed to avoid faults on sys.exit()
# [DAA, Jan 1998]
import sys
oldexitfunc = None
if hasattr(sys, 'exitfunc'):
    oldexitfunc = sys.exitfunc
def cleanup():
    from Tkinter import _default_root, TclError
    import Tkinter
    try:
        if _default_root: _default_root.destroy()
    except TclError:
        pass
    Tkinter._default_root = None
    if oldexitfunc: oldexitfunc()
sys.exitfunc = cleanup
# [end DAA]
toglcolors.init() # posts the togl widget create callback function

# visuals that use true colors
truevis = {
          'truecolor' : 1,
          'directcolor' : 1,
          }

# crosshair cursor color (only has an effect in indexed color mode)
# this is global so that it applies to all Ptogl widgets
cursorColor = 1
cursorTrueColor = (1.0, 0.0, 0.0)

class RawOpengl(Widget, Misc):
    """Widget without any sophisticated bindings by Tom Schwaller

    Modified by Perry Greenfield to remove interactive behavior of
    original widget, to minimize redraws when backing store is
    not being used, and to invoke a software cursor.
    """

    def __init__(self, master=None, cnf=None, **kw):
        # choose rgb mode that is compatible with master widget
        top = master or _default_root
        visual = top.winfo_visual()
        if truevis.has_key(visual):
            kw['rgba'] = 1
        else:
            kw['rgba'] = 0
        if cnf is None: cnf = {}
        Widget.__init__(self, master, 'togl', cnf, kw)
        self.rgbamode = kw['rgba']
        self.doIdleRedraw = 0
        self.doIdleSWCursor = 0
        self.ignoreNextRedraw = 0
        self.toglStruct = toglcolors.getToglStruct()
        # Add a placeholder software cursor attribute. If it is None,
        # that means no software cursor is in effect. If it is not None,
        # then it will be used to render the cursor.
        self.__isSWCursorActive = 0
        self.__SWCursor = None

    def flush(self):
        glFlush()
        self.doIdleRedraw = 0

    def immediateRedraw(self):
        self.tk.call(self._w, 'makecurrent')
        glPushMatrix()
        try:
            # need to indicate cursor is not visible before redraw, since
            # cursor sleeps are now issued by redraw. The presumption is that
            # redraw will wipe out cursor visibility, so we set it first
            if self.__isSWCursorActive:
                # deactivate cursor for duration of redraw
                # otherwise it slows the redraw to a glacial pace
                cursorActivate = 1
                x = self.__SWCursor.lastx
                y = self.__SWCursor.lasty
                self.deactivateSWCursor()
            else:
                cursorActivate = 0
            self.redraw(self)
            if cursorActivate:
                self.activateSWCursor(x,y)
            glFlush()
        finally:
            glPopMatrix()
        self.tk.call(self._w, 'swapbuffers')

    def tkRedraw(self, *dummy):
        self.doIdleRedraw = 1
        self.after_idle(self.idleRedraw)

    def idleRedraw(self):
        """Do a redraw, then set buffer so no more happen on this idle cycle"""
        if self.doIdleRedraw:
            self.doIdleRedraw = 0
            self.immediateRedraw()

    def isSWCursorActive(self):
        return self.__isSWCursorActive

    def activateSWCursor(self, x=0.5, y=0.5, type=None):
        # Load a blank cursor from a file (isn't there a better way
        # to disable a cursor in Tk?).
        # XBM file for cursor is in same directory as this module
        global _blankcursor
        self['cursor'] = '@' + _blankcursor + ' black'
        # ignore type for now since only one type of software cursor
        # is implemented
        self.activate()
        if not self.__isSWCursorActive:
            if not self.__SWCursor:
                self.__SWCursor = FullWindowCursor(x,y,self.rgbamode)
            self.__isSWCursorActive = 1
            self.bind("<Motion>",self.moveCursor)
        if not self.__SWCursor.isVisible:
            self.__SWCursor.draw()
            self.update_idletasks()

    def deactivateSWCursor(self):
        if self.__isSWCursorActive:
            self.activate()
            self.__SWCursor.erase()
            self.unbind("<Motion>")
            self.__isSWCursorActive = 0
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
        if self.__isSWCursorActive:
            self.activate()
            self.__SWCursor.draw()

    def moveCursor(self, event):
        """Call back for mouse motion events"""
        x = event.x
        y = event.y
        winSizeX = self.winfo_width()
        winSizeY = self.winfo_height()
        ndcX = (x+0.5)/winSizeX
        ndcY = (winSizeY-0.5-y)/winSizeY
        self.activate()
        self.__SWCursor.moveTo(ndcX,ndcY)

class Ptogl(RawOpengl):

    """Subclassing the togl widget"""

    def __init__(self, master=None, cnf=None, **kw):
        """Create an opengl widget.
        Arrange for redraws when the window is exposed or when
        it changes size."""

        apply(RawOpengl.__init__, (self, master, cnf), kw)
        self.initialised = 0

        # The _back color
        self.r_back = 1.
        self.g_back = 0.
        self.b_back = 1.

        # to save last cursor position if switching to another window
        self.lastX = None
        self.lastY = None

        # Basic bindings for the virtual trackball
        self.bind('<Expose>', self.tkExpose)
        self.bind('<Configure>', self.tkExpose)

    def activate(self):
        """Cause this Opengl widget to be the current destination for drawing."""

        self.tk.call(self._w, 'makecurrent')

        # This should almost certainly be part of some derived class.
        # But I have put it here for convenience.

    def basic_lighting(self):
        """Set up some basic lighting (single infinite light source).

        Also switch on the depth buffer."""

        self.activate()
        light_position = (1, 1, 1, 0);
        glLightf(GL_LIGHT0, GL_POSITION, light_position);
        glEnable(GL_LIGHTING);
        glEnable(GL_LIGHT0);
        glDepthFunc(GL_LESS);
        glEnable(GL_DEPTH_TEST);
        glMatrixMode(GL_MODELVIEW);
        glLoadIdentity()

    def report_opengl_errors(self, message = "OpenGL error:"):
        """Report any opengl errors that occured while drawing."""

        while 1:
            err_value = glGetError()
            if not err_value: break
            print message, gluErrorString(err_value)

    def set_background(self, r, g, b):
        """Change the background colour of the widget."""

        self.r_back = r
        self.g_back = g
        self.b_back = b

        self.tkRedraw()

    def tkExpose(self, *dummy):
        """Redraw the widget.
        Make it active, update tk events, call redraw procedure and
        swap the buffers.  Note: swapbuffers is clever enough to
        only swap double buffered visuals."""
        if self.ignoreNextRedraw:
            self.ignoreNextRedraw = 0
        else:
            self.activate()
            if not self.initialised:
                self.basic_lighting()
                self.initialised = 1
            self.tkRedraw()

class FullWindowCursor:

    """This implements a  full window crosshair cursor"""
    # Perhaps this should inherit from an abstract Cursor class eventually
    # Coordinates are in IRAF NDC coordinates (same as OpenGL for now,
    # but if we use OpenGL coordinate transforms to implement zooming
    # and translation, they won't be.

    def __init__(self, x, y, rgbamode):

        """Display the cursor for the first time"""

        self.lastx = x
        self.lasty = y
        self.isVisible = 0
        self.rgbamode = rgbamode
        self.draw()

    def setPosition(self, x, y):

        self.lastx = x
        self.lasty = y

    def xorDraw(self):

        if self.rgbamode:
            glEnable(GL_COLOR_LOGIC_OP)
            glLogicOp(GL_XOR)
            glColor3f(cursorTrue[0], cursorTrue[1], cursorTrue[2])
        else:
            glEnable(GL_INDEX_LOGIC_OP)
            glLogicOp(GL_XOR)
            glIndex(cursorColor)
        glBegin(GL_LINES)
        glVertex2f(0,self.lasty)
        glVertex2f(1,self.lasty)
        glVertex2f(self.lastx,0)
        glVertex2f(self.lastx,1)
        glEnd()
        if self.rgbamode:
            glDisable(GL_COLOR_LOGIC_OP)
        else:
            glDisable(GL_INDEX_LOGIC_OP)
        glFlush()

    def erase(self):

        if self.isVisible:
            self.xorDraw()
            self.isVisible = 0

    def draw(self):

        if not self.isVisible:
            self.xorDraw()
            self.isVisible = 1

    def moveTo(self,x,y):

        if (self.lastx != x) or (self.lasty != y):
            self.erase() # erase previous cursor
            self.lastx = x
            self.lasty = y
            self.draw() # draw new position
