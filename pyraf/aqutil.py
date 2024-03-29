""" Contains Python routines to do special Aqua (OSX) window manipulations
not possible in tkinter.  In general, an attempt is made to use the Pyobjc
bridging package so that compiling another C extension is not needed.
"""



import os
import struct
import time
import objc
import AppKit

# Arbitrary module constants for term vs. gui.  0 and negative numbers have
# special meanings when queried elsewhere (e.g. wutil).  It is assumed that
# these two values are very unlikely to collide with actual Tk widget id's.
WIN_ID_TERM = 101
WIN_ID_GUI = 102

# module variables
__thisApp = None
__termApp = None
__screenHeight = 0
__initialized = False


def focusOnGui():
    """ Set focus to GUI """
    global __thisApp
    __thisApp.activateWithOptions_(2)


def focusOnTerm(after=0):
    """ Set focus to terminal """
    global __termApp
    if after > 0:
        time.sleep(after)
    __termApp.activateWithOptions_(2)


def guiHasFocus(after=0):
    """ Return True if GUI has focus """
    global __thisApp
    if after > 0:
        time.sleep(after)
    return __thisApp.isActive()


def termHasFocus():
    """ Return True if terminal has focus """
    global __termApp
    return __termApp.isActive()


def getTopIdFor(winId):
    """ In Aqua we only use the two IDs and they are both "top-level" ids."""
    if winId == WIN_ID_TERM:
        return WIN_ID_TERM  # its either the terminal window
    else:
        return WIN_ID_GUI  # or some kind of gui (e.g. all Tk winfo id values)


def getParentID(winId):
    """ In Aqua we only use the two IDs and they are both "top-level" ids."""
    return winId


def getFocalWindowID():
    """ Return the window ID for the window which currently has the focus.
    On OSX, the actual window ID's are not important here.  We only
    need to distinguish between the terminal and the GUI.  In fact, we treat
    all GUI windows as having the same ID. """
    if termHasFocus():
        return WIN_ID_TERM  # 1 == terminal
    else:
        return WIN_ID_GUI  # 2 == any GUI window


def setFocusTo(windowID):
    """ Move the focus to the given window ID (see getFocalWindowID docs) """
    # We could do something fancy like create unique window id's out of the
    # process serial numbers (PSN's), but for now stick with WIN_ID_*
    if windowID not in (WIN_ID_TERM, WIN_ID_GUI):
        raise RuntimeError("Bug: unexpected OSX windowID: " + str(windowID))
    if windowID == WIN_ID_TERM:
        focusOnTerm()
    else:
        focusOnGui()


def moveCursorTo(windowID, rx, ry, x, y):
    """ Move the cursor to the given location.  This (non-X) version does
    not use the windowID for a GUI location - it uses rx and ry. """
    loc = (rx + x, ry + y)
    err = CGWarpMouseCursorPosition(loc)  # CG is for CoreGraphics (Quartz)
    if err:
        raise Exception("CGWarpMouseCursorPosition: " + str(err))


def getPointerGlobalPosition():
    """ Gets value of the mouse/cursor loc on screen; origin = top left. """

    global __screenHeight
    # We could use CGSGetCurrentCursorLocation (CGS: CoreGraphics Services) to
    # get cursor position, but it is a private, questionable API (June 2008).

    # NSEvent supports a class-method to always hold the cursor loc.
    # It gives us the values in NSPoint coords (pixels).  These are fine,
    # except that the NSPoint origin is the bottom left of the screen, so we
    # need to convert to the top-left origin.
    pos = AppKit.NSEvent.mouseLocation()  # current mouse location
    if __screenHeight <= 0:
        raise Exception("Bug: aqutil module uninitialized")
    return {'x': pos.x, 'y': __screenHeight - pos.y}


def getPointerPosition(windowID):
    """ Cursor position with respect to a window corner is not supported. """
    return None


def redeclareTerm():
    """ Sometimes the terminal process isn't chosen correctly.  This is used
    to fix that by declaring again which process is the terminal.  Call this
    from the terminal ONLY when it is foremost on the desktop. """
    global __termApp
    __termApp = AppKit.NSWorkspace.shared.frontmostApplication()


def __doPyobjcWinInit():
    """ Initialize the Pyobjc bridging and make some calls to get our PSN and
    the parent terminal's PSN. Do only ONCE per process. """

    # for #108, also see
    #   http://www.fruitstandsoftware.com/blog/2012/08/quick-and-easy-debugging-of-unrecognized-selector-sent-to-instance/
    # and
    #   http://www.raywenderlich.com/10209/my-app-crashed-now-what-part-1

    global __thisApp, __termApp, __screenHeight, __initialized
    # Guard against accidental second calls
    if __initialized:
        return

    # Taken in part from PyObjc's Examples/Scripts/wmEnable.py
    # Be aware that '^' means objc._C_PTR
    #
    #  input par: n^<argtype>
    # output par: o^<argtype>
    #  inout par: N^<argtype>
    # return values are the first in the list, and 'v' is void
    #
    OSErr = objc._C_SHT
    CGErr = objc._C_INT
    INPSN = b'n^{ProcessSerialNumber=LL}'
    OUTPSN = b'o^{ProcessSerialNumber=LL}'
    #   OUTPID = b'o^_C_ULNG'  # invalid as of objc v3.2
    WARPSIG = b'v{CGPoint=ff}'
    if struct.calcsize("l") > 4:  # is 64-bit python
        WARPSIG = b'v{CGPoint=dd}'

    FUNCTIONS = [
        ('CGWarpMouseCursorPosition', WARPSIG),
        ('CGMainDisplayID', objc._C_PTR + objc._C_VOID),
        ('CGDisplayPixelsHigh', objc._C_ULNG + objc._C_ULNG),
        ('CGDisplayHideCursor', CGErr + objc._C_ULNG),
        ('CGDisplayShowCursor', CGErr + objc._C_ULNG),
    ]

    bndl = AppKit.NSBundle.bundleWithPath_(
        objc.pathForFramework(
            '/System/Library/Frameworks/ApplicationServices.framework'))
    if bndl is None:
        raise Exception("Error in aqutil with bundleWithPath_")

    # Load the functions into the global (module) namespace
    objc.loadBundleFunctions(bndl, globals(), FUNCTIONS)
    for (fn, sig) in FUNCTIONS:
        if fn not in globals():
            raise Exception("Not found: " + str(fn))

    # Get terminal's PSN (on OSX assume terminal is now frontmost process)
    # Do this before even setting the PyRAF process to a FG app.
    __termApp = AppKit.NSWorkspace.sharedWorkspace().frontmostApplication()

    # Get our PSN
    __thisApp = AppKit.NSRunningApplication.currentApplication()

    # Set Proc name
    AppKit.NSProcessInfo.processInfo().setProcessName_("PyRAF")

    # Get the display's absolute height (pixels).
    # The next line assumes the tkinter root window has already been created
    # (and withdrawn), but it may have not yet been.
#   __screenHeight = tkinter._default_root.winfo_screenheight()
# So, we will use the less-simple but just as viable CoreGraphics funcs.
    dispIdPtr = CGMainDisplayID()  # no need to keep around?
    __screenHeight = CGDisplayPixelsHigh(dispIdPtr)


#
# Must be done exactly once, at the very start of the run
#
if not __initialized:
    __doPyobjcWinInit()
    __initialized = True
