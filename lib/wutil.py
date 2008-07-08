"""Contains python routines to do special Window manipulations not
possible in Tkinter.
These are python stubs that are overloaded by a c version implementations.
If the c versions do not exist, then these routines will do nothing


$Id$
"""

import struct, fcntl, sys, os
from irafglobals import IrafError

# empty placeholder versions for X
def getFocalWindowID(): return None
def drawCursor(WindowID, x, y, w, h): pass
def moveCursorTo(WindowID, rx, ry, x, y): pass
def setFocusTo(WindowID): pass
def setBackingStore(WindowID): pass
def getPointerPosition(WindowID): pass
def getWindowAttributes(WindowID): pass
def getParentID(WindowID): pass
def getDeepestVisual(): return 24
def initGraphics(): pass
def closeGraphics(): pass

# Are we on MacOS X ?
WUTIL_ON_MAC = False
if os.uname()[0] == 'Darwin':
    WUTIL_ON_MAC = True

# For a little while we may support both versions (X or Aqua) on OSX
WUTIL_USING_X = True
if WUTIL_ON_MAC and os.environ.has_key('PYRAF_WUTIL_USING_AQUA'):
    WUTIL_USING_X = False
# On OSX, a terminal with no display causes us to fail pretty abruptly:
# "INIT_Processeses(), could not establish the default connection to the WindowServer.Abort".
# Give the user (Mac or other) a way to still run remotely with no display.
_skipDisplay = os.environ.has_key('PYRAF_NO_DISPLAY')

# attempt to override with xutil or aqua versions
_hasAqua = 0
_hasXWin = 0
try:
    if WUTIL_USING_X and not _skipDisplay:
        import xutil
        #initGraphics = initXGraphics
        xutil.initXGraphics() # call here for lack of a better place for n

        # Check to make sure a valid XWindow ID was initialized
        # Attach closeGraphics to XWindow methods
        #ONLY if an XWindow was successfully initialized.
        #  WJH (10June2004)
        if xutil.getFocalWindowID() == -1:
            raise EnvironmentError

        # Successful intialization. Reset dummy methods with
        # those from 'xutil' now.
        from xutil import *
        _hasXWin = 1 # Flag to mark successful initialization of XWindow
        closeGraphics = closeXGraphics

    else:
        # Start with a basic empty non-X implementation (e.g. Cygwin?, OSX, ?)
        def getWindowIdZero(): return 0
        getFocalWindowID = getWindowIdZero

        # If on OSX, use aqutil
        if WUTIL_ON_MAC and not _skipDisplay: # as opposed to the PC (future?)
            try:
                import aqutil
                # override the few Mac-specific functions needed
                from aqutil import getFocalWindowID, setFocusTo, getParentID
                from aqutil import moveCursorTo, getPointerPosition
                _hasAqua = 1
            except:
                _hasAqua = 0
                print "ERROR importing aqutil"

except ImportError:
    _hasXWin = 0 # Unsuccessful init of XWindow
except EnvironmentError:
    _hasXWin = 0 # Unsuccessful init of XWindow

# Clean up the namespace a bit...
try:
    del xutil
except NameError:
    pass # may not have imported it

magicConstant = None
try:
    import IOCTL
    magicConstant = IOCTL.TIOCGWINSZ
except ImportError:
    platform = sys.platform
    if platform == 'sunos5':
        magicConstant = ord('T')*256 + 104
    elif platform == 'linux2':
        magicConstant = 0x5413
    elif platform == 'linux-i386':
        magicConstant = 0x5413
    elif platform[:4] == 'osf1':
        magicConstant = 0x40087468
    elif platform == 'darwin':
        try:
            import termios
            magicConstant = termios.TIOCGWINSZ
        except ImportError:
            magicConstant = 1074275912
    else:
        raise ImportError(
                "wutil.py: Needs definition of TIOCGWINSZ constant for platform %s"
                % platform)


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
        if _hasAqua:
            return aqutil.getTopIdFor(wid)
        else:
            return wid # everything is its own top

    if topIDmap.has_key(wid):
        return topIDmap[wid]
    try:
        oid = wid
        while 1:
            pid = getParentID(wid)
            if (not pid) or (pid==wid):
                topIDmap[oid] = wid
                return wid
            else:
                wid = pid
    except EnvironmentError:
        return None

def forceFocusToNewWindow():
    """ This is used to make sure that a window which just popped up is
    actually in the front, where focus would be.  With X, any new window
    comes to the front anyway, so this is a no-op.  Currently this is
    only necessary under Aqua. """
    if _hasAqua:
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
        raise Exception("platform isn't supported: "+platform)

    # define string to serve as memory area to receive copy of structure
    # created by IOCTL call
    tstruct = ' '*20 # that should be more than enough memory
    try:
        rstruct = fcntl.ioctl(sys.stdout.fileno(), magicConstant, tstruct)
        ysize, xsize = struct.unpack('hh',rstruct[0:4])
        # handle bug in konsole (and maybe other bad cases)
        if ysize <= 0: ysize = 24
        if xsize <= 0: xsize = 80
        return ysize, xsize
    except (IOError, AttributeError):
        return (24,80) # assume generic size


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
        raise RuntimeError("Bug: class FocusEntity cannot be used directly")

    def forceFocus(self):
        """When called, the object should force focus to the window it
        represents and warp the cursor to it using the last saved cursor
        position."""
        raise RuntimeError("Bug: class FocusEntity cannot be used directly")

    def getWindowID(self):
        """return a window ID that can be used to find the top window
        of the window heirarchy."""
        raise RuntimeError("Bug: class FocusEntity cannot be used directly")


# XXXX find more portable scheme for handling absence of FCNTL

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
            if _hasAqua:
                scrnPosDict = aqutil.getPointerGlobalPosition()
                self.lastScreenX = scrnPosDict['x']
                self.lastScreenY = scrnPosDict['y']
        except EnvironmentError, e:
            self.windowID = None
        self.lastX = 30
        self.lastY = 30

    def getWindowID(self):
        return self.windowID

    def forceFocus(self):
        if WUTIL_ON_MAC and WUTIL_USING_X:
            return # X ver. under dev. on OSX...  (was broken anyway)
        if not (self.windowID and isViewable(self.windowID)):
            # no window or not viewable
            return
        if self.windowID == getFocalWindowID():
            # focus is already here
            return
        if _hasAqua:
            if self.lastScreenX is not None:
                moveCursorTo(self.windowID, self.lastScreenX, self.lastScreenY,
                             0, 0)
        else: # WUTIL_USING_X
            if self.lastX is not None:
                moveCursorTo(self.windowID, 0, 0, self.lastX, self.lastY)
        setFocusTo(self.windowID)

    def saveCursorPos(self):
        if (not self.windowID) or (self.windowID != getFocalWindowID()):
            return
        if _hasAqua:
            scrnPosDict = aqutil.getPointerGlobalPosition()
            self.lastScreenX = scrnPosDict['x']
            self.lastScreenY = scrnPosDict['y']
            return
        if not WUTIL_USING_X:
            return # some of the following xutil methods are undefined

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

        if magicConstant is None:
            raise Exception("platform isn't supported: "+platform)

        # define string to serve as memory area to receive copy of structure
        # created by IOCTL call
        tstruct = ' '*20 # that should be more than enough memory
        # xxx exception handling needed (but what exception to catch?)
        rstruct = fcntl.ioctl(sys.stdout.fileno(), magicConstant, tstruct)
        xsize, ysize = struct.unpack('hh',rstruct[0:4])
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
        self.focusEntities = {'terminal':termwindow}
        self.focusStack = [termwindow]
        self.hasGraphics = termwindow.getWindowID() is not None

    def addFocusEntity(self, name, focusEntity):
        if name == 'terminal':
            return # ignore any attempts to change terminal entity
        if self.focusEntities.has_key(name):
            return # ignore for now, not sure what proper behavior is
        self.focusEntities[name] = focusEntity

    def removeFocusEntity(self, focusEntityName):

        if self.focusEntities.has_key(focusEntityName):
            entity = self.focusEntities[focusEntityName]
            del self.focusEntities[focusEntityName]
            try:
                while 1:
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
        for name,focusEntity in self.focusEntities.items():
            if getTopID(focusEntity.getWindowID()) == currentTopID:
                return name, focusEntity
        else:
            return None, None

    def saveCursorPos(self):

        if self.hasGraphics:
            name, focusEntity = self.getCurrentFocusEntity()
            if focusEntity:
                focusEntity.saveCursorPos()

    def setFocusTo(self,focusTarget,always=0):

        """focusTarget can be a string or a FocusEntity. It is possible to
        give a FocusEntity that is not in focusEntities (so it isn't
        considered part of the focus family, but is part of the restore
        chain.)

        If always is true, target is added to stack even if it is already
        the focus (useful for pairs of setFocusTo/restoreLast calls.)
        """
        if (focusTarget == None) or (not self.hasGraphics):
            return
        if not WUTIL_USING_X:
            if hasattr(focusTarget, 'gwidget'): # gwidget is a Canvas
                focusTarget.gwidget.focus_set()

        current = self.focusStack[-1]
        if type(focusTarget) == type(""):
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

# Do we have access to a graphics display?
hasGraphics = None
if _skipDisplay:
    # A common _skipDisplay case is pyraf being imported in a script,
    # in which case we keep quiet about the lack of graphics.
    if sys.argv[0].find('pyraf') >= 0: # but do warn for interactive sessions
        print "No graphics display intended for this session."
else:
    if _hasXWin or _hasAqua:
        hasGraphics = focusController.hasGraphics
    elif WUTIL_ON_MAC:
        # Handle case where we are on the Mac with no X and no PyObjc.  We can
        # still run, albeit without automatic mouse moving and focus jumping.
        hasGraphics = focusController.hasGraphics
        if hasGraphics:
            print "\nLimited graphics available (aqutil not loaded)\n"

    if not hasGraphics:
        print ""
        print "No graphics display available for this session."
        print "Graphics tasks that attempt to plot to an interactive " + \
                          "screen will fail."
        print ""
