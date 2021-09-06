"""
Graphics window manager, creates multiple toplevel togl widgets for
use by python plotting

"""


import os
from stsci.tools import capable
if capable.OF_GRAPHICS:
    import tkinter
from . import wutil
from . import gki


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
        while True:
            windowName = root + str(number)
            if windowName not in self.windows:
                return windowName
            number = number + 1

    def window(self, windowName=None):

        if windowName is not None:
            windowName = str(windowName).strip()
        if not windowName:
            windowName = self.getNewWindowName()
        if windowName not in self.windows:
            self.windows[windowName] = self.GkiKernelClass(windowName, self)
            self.createList.append(windowName)
        if self.windowVar is None:
            # create Tk string variable with active window name
            self.windowVar = tkinter.StringVar()
            self.windowVar.trace('w', self._setWindowVar)
        self.windowVar.set(windowName)

    def _setWindowVar(self, *args):
        windowName = self.windowVar.get().strip()
        if not windowName:
            self.stdgraph = None
        else:
            self.stdgraph = self.windows[windowName]
            self.stdgraph.activate()
            # register with focus manager
            wutil.focusController.addFocusEntity(windowName, self.stdgraph)

    def windowNames(self):
        """Return list of all window names"""
        return list(self.windows.keys())

    def getWindowVar(self):
        """Return Tk variable associated with selected window"""
        return self.windowVar

    def delete(self, windowName):

        windowName = str(windowName).strip()
        window = self.windows.get(windowName)
        if window is None:
            print(f"error: graphics window `{windowName}' doesn't exist")
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
                    if wname in self.windows:
                        self.createList.append(wname)
                        break
                else:
                    # something's messed up
                    # change to randomly selected active window
                    wname = list(self.windows.keys())[0]
                self.windowVar.set(wname)
            wutil.focusController.removeFocusEntity(windowName)

    def flush(self):
        for window in self.windows.values():
            window.flush()

    def openKernel(self):
        self.window()


#
# Module-level functions
#


def _setGraphicsWindowManager():
    """ Decide which graphics kernel to use and generate a GWM object.
    This is only meant to be called internally! """
    if wutil.hasGraphics:
        # see which kernel to use
        if 'PYRAFGRAPHICS' in os.environ:
            kernelname = os.environ['PYRAFGRAPHICS'].lower()
            if kernelname == "tkplot":
                from . import gkitkplot
                kernel = gkitkplot.GkiTkplotKernel
            elif kernelname == "opengl":
                print("OpenGL kernel no longer exists, using default instead")
                kernelname = "default"
            elif kernelname == "matplotlib":
                try:
                    from . import GkiMpl
                    kernel = GkiMpl.GkiMplKernel
                except ImportError:
                    print("matplotlib is not installed, using default instead")
                    kernelname = "default"
            else:
                print('Graphics kernel specified by "PYRAFGRAPHICS=' +
                      kernelname + '" not found.')
                print("Using default kernel instead.")
                kernelname = "default"
        else:
            kernelname = "default"

        if 'PYRAFGRAPHICS_TEST' in os.environ:
            print("Using graphics kernel: " + kernelname)
        if kernelname == "default":
            from . import gkitkplot
            kernel = gkitkplot.GkiTkplotKernel
        wutil.isGwmStarted = 1
        return GraphicsWindowManager(kernel)
    else:
        wutil.isGwmStarted = 0
        return None


# Create a module instance of the GWM object that can be referred to
# by anything that imports this module. It is in effect a singleton
# object intended to be instantiated only once and be accessible from
# the module.
_g = _setGraphicsWindowManager()


#
# Public routines to access windows managed by _g
#
def _resetGraphicsWindowManager():
    """ For development only (2010), risky but useful in perf tests """
    global _g
    _g = _setGraphicsWindowManager()


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


def getActiveWindowGwidget():
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
        # XXX top is implementation-specific
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
