"""__init__.py: main Pyraf package initialization

Checks sys.argv[0] == 'pyraf' to determine whether IRAF initialization
is done verbosely or quietly.

$Id$

R. White, 2000 February 18
"""
__version__ = "v0.9.2 (2001Dec12)"

import os, sys, __main__

def usage():
    print __main__.__doc__
    sys.stdout.flush()
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

# Set clean name strategy
import irafnames
irafnames.setCleanStrategy()

# set up exit handler to close caches
import irafexecute, clcache
_oldexitfunc = getattr(sys, 'exitfunc', None)
def _cleanup(last_exit = _oldexitfunc):
    iraf.gflush()
    del irafexecute.processCache
    del clcache.codeCache
    if last_exit: last_exit()
sys.exitfunc = _cleanup

# now get ready to do the serious IRAF initialization

import iraf

_pname = os.path.split(sys.argv[0])[1]
if _pname != "pyraf":
    # if not executing as pyraf main, just initialize iraf module
    # quietly load initial iraf symbols and packages
    iraf.Init(doprint=0, hush=1)
else:
    # special initialization when this is the main program

    # command-line options

    import getopt
    try:
        optlist, args = getopt.getopt(sys.argv[1:], "imvh")
        if len(args) > 1:
            print 'Error: more than one savefile argument'
            usage()
    except getopt.error, e:
        print str(e)
        usage()
    verbose = 0
    doCmdline = 1
    if optlist:
        for opt, value in optlist:
            if opt == "-i":
                doCmdline = 0
            elif opt == "-m":
                doCmdline = 1
            elif opt == "-v":
                verbose = verbose + 1
            elif opt == "-h":
                usage()
            else:
                print "Program bug, uninterpreted option", opt
                raise SystemExit
    iraf.setVerbose(verbose)
    del getopt, verbose, usage, optlist

    # load initial iraf symbols and packages
    if args:
        iraf.Init(savefile=args[0])
    else:
        iraf.Init()
    del args

help = iraf.help
