#! /usr/local/bin/python -i
# #! /usr/bin/python -i
# #! /usr/bin/env python -i
# # twiddle area to tickle cvs to update version number
"""
pyraf: Python IRAF front end

Usage: pyraf [options] [savefile]
  where savefile is an optional save file to start from and
  options are one or more of:
  -i  Do not run command line wrapper, just run standard Python front end
  -m  Run command line wrapper to provide extra capabilities (default)
  -v  Set verbosity level (may be repeated to increase verbosity)
  -h  Print this message

Brief help:

To load a package, use any of:
	iraf.images()
    iraf.load("images")
    iraf.run("images")
    pkg = iraf.images; pkg()
    pkg = iraf.getPkg("images"); pkg()
You can also do iraf.load("images",doprint=0) or just
iraf.load("images",0) to skip printing.  pkg(_doprint=0)
has the same effect (note the '_' in front of the keyword,
which is necessary because you can also include package
parameters as arguments.)

To get short-hand task or package object:
	imstat = iraf.imstat
    imstat = iraf.getTask("imstat")
    imhead = iraf.getTask("imheader")
    sts = iraf.getPkg("stsdas")
Note minimum match is used for task names.  Packages are accessible
using either getTask() or getPkg(), while tasks are available only
through getTask().  Both packages and tasks are available as attributes
of the iraf module.

Tasks are available as attributes of the package, e.g.
    iraf.restore()
    iraf.restore.lucy.lpar()
When accessed this way, minimum match is still used for the task names.
Both tasks directly in the package and tasks in subpackages that
have already been loaded are accessible (so images.imhead() works
even though imheader is in the imutil package.)

To set task parameters there are various syntaxes:
    imhead.long = "yes"
    imstat.image = "dev$pix"
    imstat.set("images","dev$pix")
As usual, minimum match is used for parameter names (so we can
use just 'long' rather than 'longheader').

To run tasks, use one of these forms:
    imstat()
    imstat.run()
    iraf.run("imstat")
    imhead("dev$pix",long="yes")

$Id$

R. White, 2000 January 21
"""

import os, sys
from irafglobals import yes, no, INDEF, pyrafDir

__version__ = "$Revision$"

def usage():
	print __doc__
	sys.stdout.flush()
	sys.exit()

# if this script is being executed as __main__, add it as module 'pyraf'
# too so 'import pyraf' gets the same module

if __name__ == "__main__":
	sys.modules['pyraf'] = sys.modules['__main__']

# set search path to include directory containing this script
# and current directory

if pyrafDir not in sys.path: sys.path.insert(0, pyrafDir)
if "." not in sys.path: sys.path.insert(0, ".")

# The following is to grab the terminal window's id at the earliest
# possible moment
import wutil
del wutil

# This modifies the standard import mechanism to make it more
# convenient for the iraf module
import irafimport
del irafimport

import iraf

# this gives more useful tracebacks for CL scripts
import cllinecache
del cllinecache

# Set clean name strategy
import irafnames
irafnames.setCleanStrategy()
del irafnames

if __name__ != "__main__":
	# if not main program, just initialize iraf module
	# quietly load initial iraf symbols and packages
	iraf.Init(doprint=0, hush=1)
else:
	# special initialization when this is the main program
	# read the user's startup file (if there is one)
	if os.environ.has_key("PYTHONSTARTUP") and \
			os.path.isfile(os.environ["PYTHONSTARTUP"]):
		execfile(os.environ["PYTHONSTARTUP"])

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

if __name__ == "__main__":
	print "Pyraf, Python front end to IRAF,", __version__, "(copyright AURA 1999)"
	print "Python: " + sys.copyright
	if doCmdline:
		#
		# start up command line wrapper keeping definitions in local name space
		#
		exit = 'Use ".exit" to exit'
		quit = exit
		logout = exit
		import pycmdline, cStringIO
		from irafpar import makeIrafPar
		_pycmdline = pycmdline.PyCmdLine(locals=locals())
		del pycmdline
		del doCmdline
		_pycmdline.start()
		del _pycmdline
	else:
		del doCmdline

