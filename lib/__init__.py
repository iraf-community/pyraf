""" __init__.py: main Pyraf package initialization


Checks sys.argv[0] == 'pyraf' to determine whether IRAF initialization
is done verbosely or quietly.

$Id$

R. White, 2000 February 18
"""
from __future__ import division # confidence high

__version__ = "1.8.1dev (Oct 2009 and on)"

import os, sys, __main__

def usage():
    print __main__.__doc__
    sys.stdout.flush()
    irafimport.restoreBuiltins()
    sys.exit()

# set search path to include current directory

if "." not in sys.path: sys.path.insert(0, ".")

# Grab the terminal window's id at the earliest possible moment
import wutil

# Modify the standard import mechanism to make it more
# convenient for the iraf module
import irafimport

# this gives more useful tracebacks for CL scripts
import cllinecache

import irafnames

# initialization is silent unless program name is 'pyraf' or
# silent flag is set on command line

# follow links to get to the real executable filename
executable = sys.argv[0]
while os.path.islink(executable):
    executable = os.readlink(executable)
_pyrafMain = os.path.split(executable)[1] != 'pyraf'
del executable

import irafexecute, clcache
from pytools import capable

# set up exit handler to close caches
def _cleanup():
    if iraf: iraf.gflush()
    if hasattr(irafexecute,'processCache'):
        del irafexecute.processCache
    if hasattr(clcache,'codeCache'):
        del clcache.codeCache

import atexit
atexit.register(_cleanup)
del atexit

# now get ready to do the serious IRAF initialization

if _pyrafMain:
    # if not executing as pyraf main, just initialize iraf module
    # quietly load initial iraf symbols and packages
    import iraf
    iraf.Init(doprint=0, hush=1)
else:
    # special initialization when this is the main program

    # command-line options

    import pyrafglobals as _pyrafglobals
    import getopt
    try:
        optlist, args = getopt.getopt(sys.argv[1:], "imvhsne",
            ["commandwrapper=", "verbose", "help", "silent", "nosplash","ipython", "ecl"])
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
            elif opt in ("-v", "--verbose"):
                verbose = verbose + 1
            elif opt in ("-h", "--help"):
                usage()
            elif opt in ("-s", "--silent"):
                _silent = 1
            elif opt in ("-n", "--nosplash"):
                _dosplash = 0
            elif opt == "--ipython":
                _use_ipython_shell = 1
            elif opt in ["-e", "--ecl"]:
                _pyrafglobals._use_ecl = True
            else:
                print "Program bug, uninterpreted option", opt
                raise SystemExit

    if "epyraf" in sys.argv[0]:  # See also -e and --ecl switches
        _pyrafglobals._use_ecl = True

    import iraf
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

    # load initial iraf symbols and packages
    if args:
        iraf.Init(savefile=args[0], **_initkw)
    else:
        iraf.Init(**_initkw)
    del args

    if _splash:
        _splash.Destroy()
    del _splash, _silent, _dosplash

help = iraf.help

