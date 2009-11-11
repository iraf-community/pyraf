"""
Graphics window manager, creates multiple toplevel togl widgets for
use by python plotting

$Id$
"""
from __future__ import division # confidence high

import os, string, wutil
from pytools import capable
if capable.OF_GRAPHICS:
    import Tkinter
import gki

class GWMError(Exception):
    pass

class GraphicsWindowManager(gki.GkiProxy):

    """Proxy for active graphics window and manager of multiple windows

    Each window is an instance of a graphics kernel.  stdgraph
    holds the active window pointer.
    """

    def __init__(self, GkiKernelClass):

        """GkiKernelClass is the class of kernel objects created

        Class must implement both GkiKernel and FocusEntity interfaces
        and must have:

        - activate() method to make widget active
        - raiseWindow() method to deiconify and raise window
        - gwidget attribute with the actual widget
        - top attribute with the top level widget

        The last 2 seem unneccesarily implemenation-specific and
        probably should be eliminated if possible.
        """

        gki.GkiProxy.__init__(self)
        self.GkiKernelClass = GkiKernelClass
        self.windows = {}
        # save list of window names in order of creation
        self.createList = []
        self.windowVar = None

    def getNewWindowName(self, root="graphics"):
        """Return a new (unused) window name of form root+number"""
        number = 1
        while 1:
            windowName = root + str(number)
            if not self.windows.has_key(windowName):
                return windowName
            number = number + 1

    def window(self, windowName=None):

        if windowName is not None:
            windowName = string.strip(str(windowName))
        if not windowName:
            windowName = self.getNewWindowName()
        if not self.windows.has_key(windowName):
            self.windows[windowName] = self.GkiKernelClass(windowName, self)
            self.createList.append(windowName)
        if self.windowVar is None:
            # create Tk string variable with active window name
            self.windowVar = Tkinter.StringVar()
            self.windowVar.trace('w', self._setWindowVar)
        self.windowVar.set(windowName)

    def _setWindowVar(self, *args):
        windowName = string.strip(self.windowVar.get())
        if not windowName:
            self.stdgraph = None
        else:
            self.stdgraph = self.windows[windowName]
            self.stdgraph.activate()
            # register with focus manager
            wutil.focusController.addFocusEntity(windowName,self.stdgraph)

    def windowNames(self):
        """Return list of all window names"""
        return self.windows.keys()

    def getWindowVar(self):
        """Return Tk variable associated with selected window"""
        return self.windowVar

    def delete(self, windowName):

        windowName = string.strip(str(windowName))
        window = self.windows.get(windowName)
        if window is None:
            print "error: graphics window `%s' doesn't exist" % (windowName,)
        else:
            changeActiveWindow = (self.stdgraph == window)
            window.top.destroy()
            del self.windows[windowName]
            try:
                self.createList.remove(windowName)
            except ValueError:
                pass
            if len(self.windows) == 0:
                self.windowVar.set('')
            elif changeActiveWindow:
                # change to most recently created window
                while self.createList:
                    wname = self.createList.pop()
                    if self.windows.has_key(wname):
                        self.createList.append(wname)
                        break
                else:
                    # something's messed up
                    # change to randomly selected active window
                    wname = self.windows.keys()[0]
                self.windowVar.set(wname)
            wutil.focusController.removeFocusEntity(windowName)

    def flush(self):
        for window in self.windows.values():
            window.flush()

    def openKernel(self):
        self.window()


# Create a module instance of the GWM object that can be referred
# by anything that imports this module. It is in effect a singleton
# object intended to be instantiated only once and be accessible from
# the module.

if wutil.hasGraphics:
    # see which kernel to use
    if os.environ.has_key('PYRAFGRAPHICS'):
        kernelname = os.environ['PYRAFGRAPHICS'].lower()
        if kernelname == "tkplot":
            import gkitkplot
            kernel = gkitkplot.GkiTkplotKernel
        elif kernelname == "opengl":
            print "OpenGL kernel is no longer supported, using default instead"
            kernelname = "default"
        elif kernelname == "matplotlib":
            try:
                import GkiMpl
                kernel = GkiMpl.GkiMplKernel
            except ImportError:
                print "matplotlib module not installed, using default instead"
                kernelname = "default"
        else:
            print 'Graphics kernel specified by "PYRAFGRAPHICS='+ \
                   kernelname+'" not found.'
            print "Using default kernel instead."
            kernelname = "default"
    else:
        kernelname = "default"
    if kernelname == "default":
        import gkitkplot
        kernel = gkitkplot.GkiTkplotKernel
    _g = GraphicsWindowManager(kernel)
    wutil.isGwmStarted = 1
    if os.environ.has_key('PYRAFGRAPHICS_TEST'):
        print "Using graphics kernel: "+kernelname
    del kernelname
else:
    _g = None
    wutil.isGwmStarted = 0

#
# Public routines to access windows managed by _g
#

def getGraphicsWindowManager():

    """Return window manager object (None if none defined)"""

    return _g

def window(windowName=None):

    """Create a new graphics window if the named one doesn't exist or
    make it the active one if it does. If no argument is given a new
    name is constructed."""

    if not _g:
        raise GWMError("No graphics window manager is available")
    _g.window(windowName)

def delete(windowName=None):

    """Delete the named window (or active window if none specified)"""

    if not _g:
        raise GWMError("No graphics window manager is available")
    if windowName is None:
        windowName = getActiveWindowName()
    if windowName is not None:
        _g.delete(windowName)

def getActiveWindowName():

    """Return name of active window (None if none defined)"""

    if _g and _g.windowVar:
        return _g.windowVar.get() or None

def getActiveWindow():

    """Get the active window widget (None if none defined)"""

    if _g and _g.stdgraph:
        return _g.stdgraph.gwidget

def getActiveGraphicsWindow():

    """Get the active graphics kernel object (None if none defined)"""

    if _g and _g.stdgraph:
        return _g.stdgraph

def getActiveWindowTop():

    """Get the top window (None if none defined)"""

    if _g and _g.stdgraph:
        #XXX top is implementation-specific
        return _g.stdgraph.top

def raiseActiveWindow():

    """Deiconify if not mapped, and raise to top"""

    stdgraph = getActiveGraphicsWindow()
    if not stdgraph:
        raise GWMError("No plot has been created yet")
    stdgraph.raiseWindow()

def resetFocusHistory():

    """Reset focus history after an error occurs"""

    wutil.focusController.resetFocusHistory()
