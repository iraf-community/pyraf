""" Contains Python routines to do special Aqua (OSX) window manipulations
not possible in Tkinter.  In general, an attempt is made to use the Pyobjc
bridging package so that compiling another C extension is not needed.

$Id: sontag $
"""

import Tkinter
import objc
from Foundation import NSBundle


# module variables
__thisPSN = None
__termPSN = None
__initialized = False


def focusOnGui():
    global __thisPSN
    err = SetFrontProcess(__thisPSN)
    if err: raise Exception("SetFrontProcess: "+`err`)


def focusOnTerm():
    global __termPSN
    err = SetFrontProcess(__termPSN)
    if err: raise Exception("SetFrontProcess: "+`err`)


def __doPyobjcWinInit():
    global __thisPSN, __termPSN, __initialized
    # Guard against accidental second calls
    if __initialized: return
    print "\n\n !!! INIT !!! \n\n" # !!!

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
    focusOnGui() # always want to do this at start, right?
    __initialized = True
