#!/usr/bin/env python


"""
Adapted from that distributed in the Tk.__init__ file that came with
PyOpenGL. (to get rid of 3-d cursor effects among other things)

$Id$
"""

from OpenGL.GL import *
from OpenGL.GLU import *
from Tkinter import _default_root
from Tkinter import *
import gki

eventCount = 0 #
REDRAW_DELAY = 100 # in milliseconds

if _default_root is None:
    Tk().tk.call('package', 'require', 'Togl')
    createdRoot = 1
else:
    _default_root.tk.call('package', 'require', 'Togl')
    createdRoot = 0
	
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

class RawOpengl(Widget, Misc):
  """Widget without any sophisticated bindings\
     by Tom Schwaller"""

  def __init__(self, master=None, cnf={}, **kw):
    Widget.__init__(self, master, 'togl', cnf, kw)
    self.bind('<Map>', self.tkMap)
    self.bind('<Expose>', self.tkExpose)
    self.bind('<Configure>', self.tkExpose)

  def immediateRedraw(self):
       self.tk.call(self._w, 'makecurrent')
       glPushMatrix()
       self.update_idletasks()
       self.redraw(self)
       glFlush()
       glPopMatrix()
       self.tk.call(self._w, 'swapbuffers')

  def delayedRedraw(self, eventNumber):
    if eventNumber == eventCount:
       # No events since the event that generated this delayed call;
       # perform the redraw
       self.immediateRedraw()
    else:
       # New events, do nothing
       return

  def tkRedraw(self, *dummy):
    global eventCount
    eventCount = eventCount + 1
    if eventCount > 2000000000: eventCount = 0 # yes, unlikely
    self.after(REDRAW_DELAY, self.delayedRedraw, eventCount)

  def tkMap(self, *dummy):
    self.tkExpose()

  def tkExpose(self, *dummy):
    self.tkRedraw()

class Ptogl(RawOpengl):
  """
Subclassing the togl widget
"""

  def __init__(self, master=None, cnf={}, **kw):
    """
    Create an opengl widget.
    Arrange for redraws when the window is exposed or when
    it changes size."""

    #Widget.__init__(self, master, 'togl', cnf, kw)
    apply(RawOpengl.__init__, (self, master, cnf), kw)
#   self.gki = gki.gki(gkimetacode)
#   self.redraw = self.gki.redraw
    self.initialised = 0

    # The _back color
    self.r_back = 1.
    self.g_back = 0.
    self.b_back = 1.

    # Basic bindings for the virtual trackball
    self.bind('<Map>', self.tkMap)
    self.bind('<Expose>', self.tkExpose)
    self.bind('<Configure>', self.tkExpose)

  def activate(self):
    """Cause this Opengl widget to be the current destination for drawing."""

    self.tk.call(self._w, 'makecurrent')

  # This should almost certainly be part of some derived class.
  # But I have put it here for convenience.

  def basic_lighting(self):
    """\
    Set up some basic lighting (single infinite light source).

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

  def report_opengl_errors(message = "OpenGL error:"):
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

  def tkMap(self, *dummy):
    """Cause the opengl widget to redraw itself."""

    self.tkExpose()

  def tkExpose(self, *dummy):
    """Redraw the widget.
    Make it active, update tk events, call redraw procedure and
    swap the buffers.  Note: swapbuffers is clever enough to
    only swap double buffered visuals."""

    self.activate()
    if not self.initialised:
      self.basic_lighting()
      self.initialised = 1
    self.tkRedraw()



