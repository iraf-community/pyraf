""" __init__.py: main Pyraf package initialization


Checks sys.argv[0] == 'pyraf' to determine whether IRAF initialization
is done verbosely or quietly.

$Id$

R. White, 2000 February 18
"""
from __future__ import division # confidence high

__version__ = "1.12.dev"

try:
    from pyraf.svninfo import (__svn_version__, __full_svn_info__,
                               __setup_datetime__)
    __version__ += "-r"+__svn_version__
except:
    pass

import os, sys, __main__

# Dump version and exit here, if requested
if '-V' in sys.argv or '--version' in sys.argv:
    print __version__
    sys.stdout.flush()
    os._exit(0) # see note in usage()

# Do a quick, non-intrusive check to see how verbose we are.  This is
# just for here.  This does not correctly count -v vs. -vv, -vvv, etc.
_verbosity_ = len([j for j in sys.argv if j in ('--verbose','-v','-vv','-vvv')])

# Show version at earliest possible moment when in debugging/verbose mode.
if _verbosity_ > 0: print 'pyraf version '+__version__

def usage():
    print __main__.__doc__
    sys.stdout.flush()
    irafimport.restoreBuiltins()
    # exit with prejudice, not a raised exc; we don't want/need anything
    # to be run at this point - else we'd see run-time import warnings
    os._exit(0)

# set search path to include current directory
if "." not in sys.path: sys.path.insert(0, ".")

# Grab the terminal window's id at the earliest possible moment
import wutil

# Since numpy as absolutely required for any PyRAF use, go ahead and
# import it now, just to check it
if _verbosity_ > 0: print "pyraf: importing numpy"
try:
    import numpy
except ImportError:
    print "The numpy package is required by PyRAF and was not found.  Please visit http://numpy.scipy.org"
    os._exit(1)
if _verbosity_ > 0: print "pyraf: imported numpy"

# Modify the standard import mechanism to make it more
# convenient for the iraf module
if _verbosity_ > 0: print "pyraf: importing irafimport"
import irafimport
if _verbosity_ > 0: print "pyraf: imported irafimport"

# this gives more useful tracebacks for CL scripts
import cllinecache

import irafnames

# initialization is silent unless program name is 'pyraf' or
# silent flag is set on command line
if _verbosity_ > 0: print "pyraf: setting _pyrafMain"

# follow links to get to the real executable filename
executable = sys.argv[0]
while os.path.islink(executable):
    executable = os.readlink(executable)
_pyrafMain = os.path.split(executable)[1] in ('pyraf', 'runpyraf.py')
del executable

runCmd = None
import irafexecute, clcache
from stsci.tools import capable

if _verbosity_ > 0: print "pyraf: setting exit handler"
# set up exit handler to close caches
def _cleanup():
    if iraf: iraf.gflush()
    if hasattr(irafexecute,'processCache'):
        del irafexecute.processCache
    if hasattr(clcache,'codeCache'):
        del clcache.codeCache

# Register the exit handler, but only if 'pyraf' is going to import fully
# But, always register it when in Python-API mode (CNSHD817031)
if not _pyrafMain or ('-h' not in sys.argv and '--help' not in sys.argv):
    import atexit
    atexit.register(_cleanup)
    del atexit

if _verbosity_ > 0: print "pyraf: finished all work prior to IRAF use"
# now get ready to do the serious IRAF initialization
if not _pyrafMain:
    # if not executing as pyraf main, just initialize iraf module
    # quietly load initial iraf symbols and packages
    if _verbosity_ > 0: print "pyraf: initializing IRAF"
    import iraf
    if _verbosity_ > 0: print "pyraf: imported iraf"
    iraf.Init(doprint=0, hush=1)
    if _verbosity_ > 0: print "pyraf: initialized IRAF"
else:
    if _verbosity_ > 0: print "pyraf: is main program"
    # special initialization when this is the main program

    # command-line options
    import pyrafglobals as _pyrafglobals
    import getopt
    try:
        optlist, args = getopt.getopt(sys.argv[1:], "imc:vhsney",
            ["commandwrapper=", "command=", "verbose", "help", "silent", "nosplash","ipython", "ecl"])
        if len(args) > 1:
            print 'Error: more than one savefile argument'
            usage()
    except getopt.error, e:
        print str(e)
        usage()
    verbose = 0
    doCmdline = 1
    _silent = 0
    _dosplash = capable.OF_GRAPHICS
    _use_ipython_shell = 0
    if optlist:
        for opt, value in optlist:
            if opt == "-i":
                doCmdline = 0
            elif opt == "-m":
                doCmdline = 1
            elif opt == "--commandwrapper":
                if value in ("yes", "y"):
                    doCmdline = 1
                elif value in ("no", "n"):
                    doCmdline = 0
                else:
                    usage()
            elif opt in ("-c", "--command"):
                if value != None and len(value) > 0:
                    runCmd = value
                else:
                    usage()
            elif opt in ("-v", "--verbose"):
                verbose = verbose + 1
            elif opt in ("-h", "--help"):
                usage()
            elif opt in ("-s", "--silent"):
                _silent = 1
            elif opt in ("-n", "--nosplash"):
                _dosplash = 0
            elif opt in ("-y", "--ipython"):
                _use_ipython_shell = 1
            elif opt in ("-e", "--ecl"):
                _pyrafglobals._use_ecl = True
            else:
                print "Program bug, uninterpreted option", opt
                raise SystemExit

    if "epyraf" in sys.argv[0]:  # See also -e and --ecl switches
        _pyrafglobals._use_ecl = True

    if _verbosity_ > 0: print "pyraf: finished arg parsing"

    import iraf
    if _verbosity_ > 0: print "pyraf: imported iraf"
    iraf.setVerbose(verbose)
    del getopt, verbose, usage, optlist

    # If not silent and graphics is available, use splash window
    if _silent:
        _splash = None
        _initkw = {'doprint': 0, 'hush': 1}
    else:
        _initkw = {}
        if _dosplash:
            import splash
            _splash = splash.splash('PyRAF '+__version__)
        else:
            _splash = None

    if _verbosity_ > 0: print "pyraf: splashed"

    # load initial iraf symbols and packages
    if args:
        iraf.Init(savefile=args[0], **_initkw)
    else:
        iraf.Init(**_initkw)
    del args
    if _verbosity_ > 0: print "pyraf: finished iraf.Init"

    if _splash:
        _splash.Destroy()
    del _splash, _silent, _dosplash

del _verbosity_
help = iraf.help
