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

# There are different calling sequences/requirements in 10.4 vs. 10.5.
# See what the Darwin major version number is.
__objcReqsVoids = os.uname()[2]  # str: darwin num
__objcReqsVoids = int(__objcReqsVoids.split('.')[0])  # int: darwin maj
__objcReqsVoids = __objcReqsVoids > 8  # bool: if 9+

# module variables
__thisPSN = None
__termPSN = None
__screenHeight = 0
__initialized = False


def focusOnGui():
    """ Set focus to GUI """
    global __thisPSN
    err = SetFrontProcess(__thisPSN)
    if err:
        raise Exception("SetFrontProcess: " + str(err))


def focusOnTerm(after=0):
    """ Set focus to terminal """
    global __termPSN
    if after > 0:
        time.sleep(after)
    err = SetFrontProcess(__termPSN)
    if err:
        raise Exception("SetFrontProcess: " + str(err))


def guiHasFocus(after=0):
    """ Return True if GUI has focus """
    global __objcReqsVoids
    if after > 0:
        time.sleep(after)
    if __objcReqsVoids:
        err, aPSN = GetFrontProcess(None)
    else:
        err, aPSN = GetFrontProcess()

    if err:
        raise Exception("GetFrontProcess: " + str(err))
    return aPSN == __thisPSN


def termHasFocus():
    """ Return True if terminal has focus """
    global __objcReqsVoids
    if __objcReqsVoids:
        err, aPSN = GetFrontProcess(None)
    else:
        err, aPSN = GetFrontProcess()

    if err:
        raise Exception("GetFrontProcess: " + str(err))
    return aPSN == __termPSN


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
    global __termPSN, __objcReqsVoids
    oldval = __termPSN
    if __objcReqsVoids:
        err, __termPSN = GetFrontProcess(None)
    else:
        err, __termPSN = GetFrontProcess()
    if err:
        __termPSN = oldval
        raise Exception("GetFrontProcess: " + str(err))


def __doPyobjcWinInit():
    """ Initialize the Pyobjc bridging and make some calls to get our PSN and
    the parent terminal's PSN. Do only ONCE per process. """

    # for #108, also see
    #   http://www.fruitstandsoftware.com/blog/2012/08/quick-and-easy-debugging-of-unrecognized-selector-sent-to-instance/
    # and
    #   http://www.raywenderlich.com/10209/my-app-crashed-now-what-part-1

    global __thisPSN, __termPSN, __screenHeight, __initialized, __objcReqsVoids
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
        # These are public API
        ('GetCurrentProcess', OSErr + OUTPSN),
        ('GetFrontProcess', OSErr + OUTPSN),
        #        ( u'GetProcessPID', OSStat+INPSN+OUTPID), # see OUTPID note
        ('SetFrontProcess', OSErr + INPSN),
        ('CGWarpMouseCursorPosition', WARPSIG),
        ('CGMainDisplayID', objc._C_PTR + objc._C_VOID),
        ('CGDisplayPixelsHigh', objc._C_ULNG + objc._C_ULNG),
        ('CGDisplayHideCursor', CGErr + objc._C_ULNG),
        ('CGDisplayShowCursor', CGErr + objc._C_ULNG),
        # This is undocumented API
        ('CPSSetProcessName', OSErr + INPSN + objc._C_CHARPTR),
        ('CPSEnableForegroundOperation', OSErr + INPSN),
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
    # Or use GetProcessInformation w/ __thisPSN, then pinfo.processLauncher
    if __objcReqsVoids:
        err, __termPSN = GetFrontProcess(None)
    else:
        err, __termPSN = GetFrontProcess()
    if err:
        raise Exception("GetFrontProcess: " + str(err))

    # Get our PSN
    # [debug PSN numbers (get pid's) via psn2pid, or use GetProcessPID()]
    if __objcReqsVoids:
        err, __thisPSN = GetCurrentProcess(None)
    else:
        err, __thisPSN = GetCurrentProcess()
    if err:
        raise Exception("GetCurrentProcess: " + str(err))

    # Set Proc name
    err = CPSSetProcessName(__thisPSN, b'PyRAF')
    if err:
        raise Exception("CPSSetProcessName: " + str(err))
    # Make us a FG app (need to be in order to use SetFrontProcess on us)
    # This must be done unless we are called with pythonw.
    # Apparently the 1010 error is more of a warning...
    err = CPSEnableForegroundOperation(__thisPSN)
    if err and err != 1010:
        raise Exception("CPSEnableForegroundOperation: " + str(err))

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
