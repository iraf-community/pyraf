""" Contains Python routines to do special Aqua (OSX) window manipulations
not possible in Tkinter.  In general, an attempt is made to use the Pyobjc
bridging package so that compiling another C extension is not needed.

$Id: sontag $
"""

import Tkinter
import objc
from Foundation import NSBundle


# Arbitrary module constants for term vs. gui.  0 and negative numbers have
# special meanings when queried elsewhere (e.g. wutil).  It is assumed that
# these two values are very unlikely to collide with actual Tk widget id's.
WIN_ID_TERM = 101
WIN_ID_GUI  = 102


# module variables
__thisPSN = None
__termPSN = None
__initialized = False


def focusOnGui():
    """ Set focus to GUI """
    global __thisPSN
    err = SetFrontProcess(__thisPSN)
    if err: raise Exception("SetFrontProcess: "+`err`)


def focusOnTerm():
    """ Set focus to terminal """
    global __termPSN
    err = SetFrontProcess(__termPSN)
    if err: raise Exception("SetFrontProcess: "+`err`)


def guiHasFocus():
    """ Return True if GUI has focus """
    err, aPSN = GetFrontProcess()
    if err: raise Exception("GetFrontProcess: "+`err`)
    return aPSN == __thisPSN


def termHasFocus():
    """ Return True if terminal has focus """
    err, aPSN = GetFrontProcess()
    if err: raise Exception("GetFrontProcess: "+`err`)
    return aPSN == __termPSN


def getTopIdFor(winId):
    """ In Aqua we only use the two IDs and they are both "top-level" ids."""
    if winId == WIN_ID_TERM:
        return WIN_ID_TERM # its either the terminal window
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
        return WIN_ID_GUI   # 2 == any GUI window


def setFocusTo(windowID):
    """ Move the focus to the given window ID (see getFocalWindowID docs) """
    # We could do something fancy like create unique window id's out of the
    # process serial numbers (PSN's), but for now stick with WIN_ID_*
    if not windowID in (WIN_ID_TERM, WIN_ID_GUI):
        raise RuntimeError("Bug: unexpected OSX windowID: "+str(windowID))
    if windowID == WIN_ID_TERM:
        focusOnTerm()
    else:
        focusOnGui()


def moveCursorTo(windowID, x, y): pass
#   print "MCT called! id,x,y: "+`(windowID, x, y)`


def getPointerPostion(windowID):
    print "GPP called!  id: "+`windowID`
    return None


def __doPyobjcWinInit():
    """ Initialize the Pyobjc bridging and make some calls to get our PSN and
    the parent terminal's PSN. Do only ONCE per process. """

    global __thisPSN, __termPSN, __initialized
    # Guard against accidental second calls
    if __initialized: return

    # Taken in part from PyObjc's Examples/Scripts/wmEnable.py
    OSErr  = objc._C_SHT
    OSStat = objc._C_INT
    INPSN  = 'n^{ProcessSerialNumber=LL}'
    OUTPSN = 'o^{ProcessSerialNumber=LL}'
    OUTPID = 'o^_C_ULNG'
    FUNCTIONS=[
         # These are public API
         ( u'GetCurrentProcess', OSErr+OUTPSN),
         ( u'GetFrontProcess', OSErr+OUTPSN),
         ( u'GetProcessPID', OSStat+INPSN+OUTPID),
         ( u'SetFrontProcess', OSErr+INPSN),
         # This is undocumented SPI
         ( u'CPSSetProcessName', OSErr+INPSN+objc._C_CHARPTR),
         ( u'CPSEnableForegroundOperation', OSErr+INPSN),
         ( u'CGWarpMouseCursorPosition', 'v{CGPoint=ff}'),
    ]

    bndl = NSBundle.bundleWithPath_(objc.pathForFramework(
           u'/System/Library/Frameworks/ApplicationServices.framework'))
    if bndl is None: raise Exception("Error in bundleWithPath_")

    # Load the functions into the global (module) namespace
    objc.loadBundleFunctions(bndl, globals(), FUNCTIONS)
    for (fn, sig) in FUNCTIONS:
        if fn not in globals(): raise Exception("Not found: "+str(fn))

    # Get terminal's PSN (on OSX assume terminal is now frontmost process)
    # Do this before even setting the PyRAF process to a FG app.
    # Or use GetProcessInformation w/ __thisPSN, then pinfo.processLauncher
    err, __termPSN = GetFrontProcess()
    if err: raise Exception("GetFrontProcess: "+`err`)

    # Get our PSN
    # [debug PSN numbers (get pid's) via psn2pid, or use GetProcessPID()]
    err, __thisPSN = GetCurrentProcess()
    if err: raise Exception("GetCurrentProcess: "+`err`)

    # Set Proc name
    err = CPSSetProcessName(__thisPSN, 'PyRAF')
    if err: raise Exception("CPSSetProcessName: "+`err`)
    # Make us a FG app (need to be in order to use SetFrontProcess on us)
    # This must be done unless we are called with pythonw.
    # Apparently the 1010 error is more of a warning...
    err = CPSEnableForegroundOperation(__thisPSN)
    if err and err != 1010:
        raise Exception("CPSEnableForegroundOperation: "+`err`)


#
# Must be done exactly once, at the very start of the run
#
if not __initialized:
    __doPyobjcWinInit()
    __initialized = True
