"""Contains python routines to do special Window manipulations not
possible in tkinter.
These are python stubs that are overloaded by a c version implementations.
If the c versions do not exist, then these routines will do nothing

"""


import struct
import sys
import os
import fcntl


# empty placeholder versions for X
def getFocalWindowID():
    return None


def drawCursor(WindowID, x, y, w, h):
    pass


def moveCursorTo(WindowID, rx, ry, x, y):
    pass


def setFocusTo(WindowID):
    pass


def setBackingStore(WindowID):
    pass


def getPointerPosition(WindowID):
    pass


def getWindowAttributes(WindowID):
    pass


def getParentID(WindowID):
    pass


def getDeepestVisual():
    return 24


def initGraphics():
    pass


def closeGraphics():
    pass


# On OSX, a terminal with no display causes us to fail pretty abruptly:
# "INIT_Processeses(), could not establish the default connection to the WindowServer.Abort".
# Give the user (Mac or other) a way to still run remotely with no display.
from stsci.tools import capable
_skipDisplay = not capable.OF_GRAPHICS

# Are we on MacOS X ?  Windows ?
WUTIL_ON_MAC = sys.platform == 'darwin'
WUTIL_ON_WIN = sys.platform.startswith('win')

# WUTIL_USING_X: default to using X on most platforms, tho surely not on windows
WUTIL_USING_X = not WUTIL_ON_WIN

# More on this for OSX: for now we support both versions (X or Aqua) on OSX
# Allow environment variable so any user can force their preference.
if WUTIL_ON_MAC and not _skipDisplay:
    # default to aqua as it is the 98% case now (post v2.1.9), X11 users will need the env. var
    WUTIL_USING_X = 'PYRAF_WUTIL_USING_X' in os.environ

# Experimental new (2012) mode some have requested (OSX mostly) where all
# graphics windows drawn are popped to the foreground and left there with
# the focus (focus not placed back onto terminal).  Except the splash win.
GRAPHICS_ALWAYS_ON_TOP = 'PYRAF_GRAPHICS_ALWAYS_ON_TOP' in os.environ

# attempt to override with xutil or aqua versions
_has_aqutil = 0
_has_xutil = 0
try:
    if WUTIL_USING_X and not _skipDisplay:
        # set an env var before importing xutil (see PyRAF FAQ on this)
        os.environ['XLIB_SKIP_ARGB_VISUALS'] = '1'
        from . import xutil
        # initGraphics = initXGraphics
        xutil.initXGraphics()  # call here for lack of a better place for n

        # Check to make sure a valid XWindow ID was initialized
        # Attach closeGraphics to XWindow methods
        # ONLY if an XWindow was successfully initialized.
        #  WJH (10June2004)
        if xutil.getFocalWindowID() == -1:
            raise OSError()

        # Successful intialization. Reset dummy methods with
        # those from 'xutil' now.
        from pyraf.xutil import *
        _has_xutil = 1  # Flag to mark successful initialization of XWindow
        closeGraphics = closeXGraphics

    else:
        # Start with a basic empty non-X implementation (e.g. Cygwin?, OSX, ?)
        def getWindowIdZero():
            return 0

        getFocalWindowID = getWindowIdZero

        # If on OSX w/out X11, use aqutil
        if WUTIL_ON_MAC and not _skipDisplay:  # as opposed to the PC (future?)
            try:
                from . import aqutil
                # override the few Mac-specific functions needed
                from .aqutil import getFocalWindowID, setFocusTo, getParentID
                from .aqutil import moveCursorTo, getPointerPosition
                _has_aqutil = 1
            except ImportError:
                _has_aqutil = 0
                print("Could not import aqutil")

except ImportError:
    _has_xutil = 0  # Unsuccessful init of XWindow
except OSError:
    _has_xutil = 0  # Unsuccessful init of XWindow

# Clean up the namespace a bit...
try:
    del xutil
except NameError:
    pass  # may not have imported it

import termios
magicConstant = termios.TIOCGWINSZ


def getScreenDepth():
    return getDeepestVisual()


# maintain a dictionary of top level IDs to avoid repeated effort here
topIDmap = {}


def getTopID(WindowID):
    """Find top level windows ID, parent of given window.
    If window is already top (or not implemented), it returns its own ID.
    If the input Id represents the root window then it will just
    return itself"""
    wid = WindowID
    if wid <= 0:
        return wid

    # a "top ID" makes less sense if we are not using X
    if not WUTIL_USING_X:
        if _has_aqutil:
            return aqutil.getTopIdFor(wid)
        else:
            return wid  # everything is its own top

    if wid in topIDmap:
        return topIDmap[wid]
    try:
        oid = wid
        while True:
            pid = getParentID(wid)
            if (not pid) or (pid == wid):
                topIDmap[oid] = wid
                return wid
            else:
                wid = pid
    except OSError:
        return None


def forceFocusToNewWindow():
    """ This is used to make sure that a window which just popped up is
    actually in the front, where focus would be.  With X, any new window
    comes to the front anyway, so this is a no-op.  Currently this is
    only necessary under Aqua. """
    if _has_aqutil:
        aqutil.focusOnGui()


def isViewable(WindowID):

    if not WUTIL_USING_X:
        return 1  # native OSX code still under dev.; make everything viewable
    attrdict = getWindowAttributes(WindowID)
    if attrdict:
        return attrdict['viewable']
    else:
        return 1


def getTermWindowSize():
    """return a tuple containing the y,x (rows,cols) size of the terminal window
    in characters"""

    if magicConstant is None:
        raise Exception("platform isn't supported: " + sys.platform)

    # define string to serve as memory area to receive copy of structure
    # created by IOCTL call
    tstruct = ' ' * 20  # that should be more than enough memory
    try:
        rstruct = fcntl.ioctl(sys.stdout.fileno(), magicConstant, tstruct)
        ysize, xsize = struct.unpack('hh', rstruct[0:4])
        # handle bug in konsole (and maybe other bad cases)
        if ysize <= 0:
            ysize = 24
        if xsize <= 0:
            xsize = 80
        return ysize, xsize
    except OSError:
        return (24, 80)  # assume generic size


class FocusEntity:
    """Represents an interface to peform focus manipulations on a variety of
    window objects. This allows the windows to be handled by code that does
    not need to know the specifics of how to set focus to, restore focus
    to, warp the cursor to, etc. Since nothing is implemented, it isn't
    necessary to inherit it, but inheriting it does allow type checks to
    see if an object is a subclass of FocusEntity.
    """

    def saveCursorPos(self):
        """When this method is called, the object should know how to save
        the current position of the cursor in the window. If the cursor is
        not in the window or the window does not currently have focus, it
        should do nothing."""
        # raise exceptions to ensure implemenation of required methods
        raise NotImplementedError("class FocusEntity cannot be used directly")

    def forceFocus(self, cursorToo=True):
        """When called, the object should force focus to the window it
        represents and warp the cursor to it using the last saved cursor
        position."""
        raise NotImplementedError("class FocusEntity cannot be used directly")

    def getWindowID(self):
        """return a window ID that can be used to find the top window
        of the window heirarchy."""
        raise NotImplementedError("class FocusEntity cannot be used directly")


class TerminalFocusEntity(FocusEntity):
    """Implementation of FocusEntity interface for the originating
    terminal window"""

    def __init__(self):
        """IMPORTANT: This class must be instantiated while focus
        is in the terminal window"""
        self.lastScreenX = None
        self.lastScreenY = None
        try:
            self.windowID = getFocalWindowID()
            if self.windowID == -1:
                self.windowID = None
            if _has_aqutil:
                scrnPosDict = aqutil.getPointerGlobalPosition()
                self.lastScreenX = scrnPosDict['x']
                self.lastScreenY = scrnPosDict['y']
        except OSError:
            self.windowID = None
        self.lastX = 30
        self.lastY = 30

    def getWindowID(self):
        return self.windowID

    def forceFocus(self, cursorToo=True):
        if WUTIL_ON_MAC and WUTIL_USING_X:
            return  # X ver. under dev. on OSX...  (was broken anyway)
        if not (self.windowID and isViewable(self.windowID)):
            # no window or not viewable
            return
        if self.windowID == getFocalWindowID():
            # focus is already here
            return
        if _has_aqutil:
            if self.lastScreenX is not None and cursorToo:
                moveCursorTo(self.windowID, self.lastScreenX, self.lastScreenY,
                             0, 0)
        else:  # WUTIL_USING_X
            if self.lastX is not None and cursorToo:
                moveCursorTo(self.windowID, 0, 0, self.lastX, self.lastY)
        if not GRAPHICS_ALWAYS_ON_TOP:
            setFocusTo(self.windowID)

    def saveCursorPos(self):
        if (not self.windowID) or (self.windowID != getFocalWindowID()):
            return
        if _has_aqutil:
            scrnPosDict = aqutil.getPointerGlobalPosition()
            self.lastScreenX = scrnPosDict['x']
            self.lastScreenY = scrnPosDict['y']
            return
        if not WUTIL_USING_X:
            return  # some of the following xutil methods are undefined

        # This also won't work on a Mac if running from the Terminal app
        # but it WILL work on a Mac from an X11 xterm window
        if WUTIL_USING_X and WUTIL_ON_MAC and self.windowID < 2:
            return

        posdict = getPointerPosition(self.windowID)
        if posdict:
            x = posdict['win_x']
            y = posdict['win_y']
        else:
            return
        windict = getWindowAttributes(self.windowID)
        if windict and windict['width'] > 0:
            maxX = windict['width']
            maxY = windict['height']
        else:
            return
        # do nothing if position out of window
        if x < 0 or y < 0 or x >= maxX or y >= maxY:
            return
        self.lastX = x
        self.lastY = y

    # some extra utility methods

    def updateWindowID(self, id=None):
        """Update terminal window ID (to current window if id is not given)"""
        if id is None:
            id = getFocalWindowID()
        self.windowID = id

    def getWindowSize(self):
        """return a tuple containing the x,y size of the terminal window
        in characters"""

        # define string to serve as memory area to receive copy of structure
        # created by IOCTL call
        tstruct = ' ' * 20  # that should be more than enough memory
        # xxx exception handling needed (but what exception to catch?)
        rstruct = fcntl.ioctl(sys.stdout.fileno(), magicConstant, tstruct)
        xsize, ysize = struct.unpack('hh', rstruct[0:4])
        return xsize, ysize


class FocusController:
    """A mediator that allows different components to give responsibility
    to this class for deciding how to manipulate focus. It is this class
    that knows what elements are available and where focus should be returned
    to when asked to restore the previous focus and cursor position. The
    details of doing it for different windows are encapsulated in descendants
    of the FocusEntity objects that it contains. Since this is properly
    a singleton, it is created by the wutil module itself and accessed
    as an object of wutil"""

    def __init__(self, termwindow):
        self.focusEntities = {'terminal': termwindow}
        self.focusStack = [termwindow]
        self.hasGraphics = termwindow.getWindowID() is not None

    def addFocusEntity(self, name, focusEntity):
        if name == 'terminal':
            return  # ignore any attempts to change terminal entity
        if name in self.focusEntities:
            return  # ignore for now, not sure what proper behavior is
        self.focusEntities[name] = focusEntity

    def removeFocusEntity(self, focusEntityName):

        if focusEntityName in self.focusEntities:
            entity = self.focusEntities[focusEntityName]
            del self.focusEntities[focusEntityName]
            try:
                while True:
                    self.focusStack.remove(entity)
            except ValueError:
                pass

    def restoreLast(self):

        if not self.hasGraphics:
            return
        if len(self.focusStack) > 1:
            # update current position if we're in the correct window
            current = self.focusStack.pop()
            if current.getWindowID() == getFocalWindowID():
                current.saveCursorPos()
        if self.focusInFamily():
            self.focusStack[-1].forceFocus()

    def setCurrent(self, force=0):
        """This is to be used in cases where focus has been lost to
        a window not part of this scheme (dialog boxes for example)
        and it is desired to return focus to the entity currently considered
        active."""
        if self.hasGraphics and (force or self.focusInFamily()):
            self.focusStack[-1].forceFocus()

    def resetFocusHistory(self):
        # self.focusStack = [self.focusEntities['terminal']]
        last = self.focusStack[-1]
        self.focusStack = self.focusStack[:1]
        if last != self.focusStack[-1]:
            self.setCurrent()

    def getCurrentFocusEntity(self):
        """Return the focus entity that currently has focus.
        Return None if focus is not in the focus family"""
        if not self.hasGraphics:
            return None, None
        currentFocusWinID = getFocalWindowID()
        currentTopID = getTopID(currentFocusWinID)
        for name, focusEntity in self.focusEntities.items():
            if getTopID(focusEntity.getWindowID()) == currentTopID:
                return name, focusEntity
        else:
            return None, None

    def saveCursorPos(self):

        if self.hasGraphics:
            name, focusEntity = self.getCurrentFocusEntity()
            if focusEntity:
                focusEntity.saveCursorPos()

    def setFocusTo(self, focusTarget, always=0):
        """focusTarget can be a string or a FocusEntity. It is possible to
        give a FocusEntity that is not in focusEntities (so it isn't
        considered part of the focus family, but is part of the restore
        chain.)

        If always is true, target is added to stack even if it is already
        the focus (useful for pairs of setFocusTo/restoreLast calls.)
        """
        if (focusTarget is None) or (not self.hasGraphics):
            return
        if not WUTIL_USING_X:
            if hasattr(focusTarget, 'gwidget'):  # gwidget is a Canvas
                focusTarget.gwidget.focus_set()

        current = self.focusStack[-1]
        if isinstance(focusTarget, str):
            next = self.focusEntities[focusTarget]
        else:
            next = focusTarget
        # only append if focus stack last entry different from new
        if next != self.focusStack[-1] or always:
            self.focusStack.append(next)
        if self.focusInFamily():
            current.saveCursorPos()
            next.forceFocus()

    def getFocusEntity(self, FEName):
        """See if named Focus Entity is currently registered. Return it
        if it exists, None otherwise"""

        return self.focusEntities.get(FEName)

    def focusInFamily(self):
        """Determine if current focus is within the pyraf family
        (as defined by self.focusEntities)"""
        if not self.hasGraphics:
            return 0
        currentFocusWinID = getFocalWindowID()
        currentTopID = getTopID(currentFocusWinID)
        for focusEntity in self.focusEntities.values():
            fwid = focusEntity.getWindowID()
            if fwid:
                if getTopID(fwid) == currentTopID:
                    return 1
        return 0  # not in family

    def getCurrentMark(self):
        """Returns mark that can be used to restore focus to current setting"""
        return len(self.focusStack)

    def restoreToMark(self, mark):
        """Restore focus to value at mark"""
        last = self.focusStack[-1]
        self.focusStack = self.focusStack[:mark]
        if last != self.focusStack[-1]:
            self.setCurrent()


terminal = TerminalFocusEntity()
focusController = FocusController(terminal)


# debug helper
def dumpspecs(outstream=None, skip_volatiles=False):
    """ Dump various flags, settings, values to the terminal.  This is not to
    be used internal to this module - it must wait until the module is fully
    imported for all the values to be finalized.  If outstream is not given,
    this will simply dump to sys.stdout. """

    pyrver = 'unknown'
    try:
        from pyraf import __version__ as pyrver
    except ImportError:
        pass

    out = "python exec = " + str(sys.executable)
    if skip_volatiles:
        out += "\npython ver = " + '.'.join(
            [str(v) for v in sys.version_info[0:2]])
    else:
        out += "\npython ver = " + '.'.join(
            [str(v) for v in sys.version_info[0:3]])
    out += "\nplatform = " + str(sys.platform)
    if not skip_volatiles:
        out += "\nPyRAF ver = " + pyrver
    out += "\nc.OF_GRAPHICS = " + str(capable.OF_GRAPHICS)
    dco = 'not yet known'
    if skip_volatiles:
        out += "\n/dev/console owner = <skipped>"
    else:
        dco = capable.get_dc_owner(False, True)
        out += "\n/dev/console owner = " + str(dco)

    if not capable.OF_GRAPHICS:
        out += "\ntkinter use unattempted."
    else:
        import tkinter
        out += "\nTclVersion = " + str(tkinter.TclVersion)
        out += "\nTkVersion = " + str(tkinter.TkVersion)
        out += "\nWUTIL_ON_MAC = " + str(WUTIL_ON_MAC)
        out += "\nWUTIL_ON_WIN = " + str(WUTIL_ON_WIN)
        out += "\nWUTIL_USING_X = " + str(WUTIL_USING_X)
        try:  # the try/except handling here will be unneccessary after stsci.tools 3.4.2
            out += "\nis_darwin_and_x = " + str(capable.is_darwin_and_x())
            if WUTIL_ON_MAC:
                out += "\nwhich_darwin_linkage = " + str(
                    capable.which_darwin_linkage())
                out += "\nwhich_darwin_linkage2 = " + str(
                    capable.which_darwin_linkage(force_otool_check=True))
            else:
                out += "\nwhich_darwin_linkage = (not darwin)"
        except Exception:
            out += "\ndarwin linkage check threw exception"
        out += "\nskip display = " + str(_skipDisplay)
        out += "\nhas graphics = " + str(hasGraphics)
        out += "\nimported aqutil = " + str(bool(_has_aqutil))
        out += "\nimported xutil = " + str(bool(_has_xutil))

        # Case of WUTIL_USING_X and not _has_xutil means either they don't have
        # xutil library installed, or they do but they can't draw to screen
        if WUTIL_USING_X and capable.OF_GRAPHICS and \
           not _skipDisplay and not bool(_has_xutil):
            # quick debug help here for case where xutil didn't build
            out += '\n\tWARNING!  PyRAF may be missing the "xutil" library. See PyRAF FAQ 1.9'
        if 'PYRAFGRAPHICS' in os.environ:
            val = os.environ['PYRAFGRAPHICS']
            out += "\nPYRAFGRAPHICS = " + val
            if val == "matplotlib":
                mpl_ok = False
                try:
                    import matplotlib as mpl
                    mpl_ok = True
                except ImportError:
                    out += "\nCannot import matplotlib"
                if mpl_ok:
                    if hasattr(mpl, 'tk_window_focus'):
                        out += "\nmpl.tk_window_focus = " + str(
                            mpl.tk_window_focus())
                    else:
                        out += "\nmpl.tk_window_focus = function not supported"
                    mpldir = os.path.split(mpl.__file__)[0]
                    import glob
                    flist = glob.glob(mpldir + os.path.sep + 'backends' +
                                      os.path.sep + '*.so')
                    flist = [os.path.split(f)[1] for f in flist]
                    out += "\nmpl backends = " + str(flist)
                    tkaggbknd = mpldir + '/backends/_tkagg.so'
                    if os.path.exists(tkaggbknd):
                        out += "\ntry: /usr/bin/otool -L " + tkaggbknd
        else:
            out += "\nPYRAFGRAPHICS not set"

    if outstream:
        outstream.write(out + '\n')
    else:
        print(out)


# Finally, do we have access to a graphics display?
hasGraphics = None
if _skipDisplay:
    # A common _skipDisplay case is pyraf being imported in a script,
    # in which case we keep quiet about the lack of graphics.
    # But DO warn for interactive sessions where they didn't use '-s'
    if sys.argv[0].find('pyraf') >= 0 and \
       '-s' not in sys.argv and '--silent' not in sys.argv:
        # Warn, but be specific about why
        if 'PYRAF_NO_DISPLAY' in os.environ:
            print("No graphics/display intended for this session.")
        else:
            print("No graphics/display possible for this session.")
else:
    if _has_xutil or _has_aqutil:
        hasGraphics = focusController.hasGraphics
    elif WUTIL_ON_MAC:  # on a Mac but loaded no graphcs libs (aqutil/xutil)
        # Handle case where we are on the Mac with no X and no PyObjc.  We can
        # still run, albeit without automatic mouse moving and focus jumping.
        hasGraphics = focusController.hasGraphics
        if hasGraphics:
            try:  # the try/except handling here will be unneccessary after stsci.tools 3.4.2
                if capable.which_darwin_linkage() == 'aqua':
                    print(
                        "\nLimited graphics available on OSX (aqutil not loaded)\n"
                    )
                else:
                    print(
                        "\nLimited graphics available on OSX (xutil not loaded)\n"
                    )
            except Exception:
                print(
                    "\nLimited graphics available on OSX (library not loaded)\n"
                )
    elif WUTIL_ON_WIN:
        hasGraphics = 1  # try this, tho VERY limited (epar only I guess)
        print("\nLimited graphics available on win32 platform\n")

    if not hasGraphics:
        print("")
        print("No graphics display available for this session.")
        print("Graphics tasks that attempt to plot to an interactive "
              "screen will fail.")
        print('For help, search "PyRAF FAQ 5.13"')
        print("")
