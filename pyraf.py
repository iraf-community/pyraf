#! /usr/local/bin/python -i
#  #! /usr/bin/env python -i
# twiddle area to tickle cvs to update version number
"""
pyraf: Python IRAF front end

Usage: pyraf [options]
  where options are one or more of:
  -p  Packages are defined as variables (default)
  -t  Both tasks and packages are defined as variables
  -n  Keep user namespace clean, don't define tasks or packages as variables
  -i  Do not run Monty command line wrapper, just run standard Python front end
  -m  Run Monty command line wrapper to provide extra capabilities (default)
  -v  Set verbosity level (may be repeated to increase verbosity)
  -h  Print this message

Brief help:

To load a package, use any of:
    iraf.load("images")
    iraf.run("images")
    pkg = iraf.getPkg("images")
    pkg()
You can also do iraf.load("images",doprint=0) or just
iraf.load("images",0) to skip printing.  pkg(_doprint=0)
has the same effect (note the '_' in front of the keyword,
which is necessary because you can also include package
parameters as arguments.)

To get short-hand task or package object:
    imstat = iraf.getTask("imstat")
    imhead = iraf.getTask("imheader")
    sts = iraf.getPkg("stsdas")
Note minimum match is used for task names.  Packages are accessible
using either getTask() or getPkg(), while tasks are available only
through getTask().

If the -p option is used (the default), packages are defined as
objects with the package name.  E.g. after startup you can load
stsdas by saying
    stsdas()
Note there is no minimum match in this case, you must type the
entire package name.  Tasks are available as attributes of the
package, e.g.
    restore()
    restore.lucy.lpar()
When accessed this way, minimum match is used for the task names.
Both tasks directly in the package and tasks in subpackages that
have already been loaded are accessible (so images.imhead() works
even though imheader is in the imutil package.)

Similarly, if you set the -t option then both tasks and packages are
defined as variables, so this will work:
    stsdas()
    restore()
    lucy.lpar()

If you set the -n option, neither tasks nor packages are defined
as variables in your namespace (maximally clean but maximally
inconvenient too.)

To set task parameters there are various syntaxes:
    imhead.long = "yes"
    imstat.image = "dev$pix"
    imstat.set("images","dev$pix")
    imhead.setParList("dev$pix",longhe="yes")
As usual, minimum match is used for parameter names (so we can
use just 'long' rather than 'longheader').

To run tasks, use one of these forms:
    imstat()
    imstat.run()
    iraf.run("imstat")
    imhead("dev$pix",long="yes")

$Id$

R. White, 1999 May 27
"""

import os, sys

# set search path to include directory containing this script
# and current directory

dirname = os.path.dirname(sys.argv[0])
if not dirname: dirname = os.getcwd()
if dirname not in sys.path: sys.path.insert(0, dirname)
if "." not in sys.path: sys.path.insert(0, ".")
del dirname

# The following is to grab the terminal window's id at the earliest
# possible moment
import wutil
del wutil

# This modifies the standard import mechanism to make it more
# convenient for the iraf module
import irafimport
del irafimport

import iraf

help = iraf.help

__version__ = "$Revision$"

yes = 1
no = 0
INDEF = "INDEF"
flpr = "This is not the IRAF cl!  Forget those old bad habits!"
retall = "This is not IDL..."

def usage():
	print __doc__
	sys.stdout.flush()
	sys.exit()


if __name__ != "__main__":
	# if not main program, just initialize iraf module

	# XXX Should we set clean name strategy if not main?
	# irafnames.setCleanStrategy()

	# quietly load initial iraf symbols and packages
	iraf.Init(doprint=0, hush=1)
else:
	# special initialization when this is the main program

	# read the user's startup file (if there is one)
	if os.environ.has_key("PYTHONSTARTUP") and \
			os.path.isfile(os.environ["PYTHONSTARTUP"]):
		execfile(os.environ["PYTHONSTARTUP"])

	# use command-line options to define behavior for iraf namespaces
	# -p  Add packages to namespace (default)
	# -t  Add tasks (and packages) to namespace
	# -n  Don't add anything to namespace
	# -v  Increment verbosity (note can use multiple times to make
	#     more verbose, e.g. -v -v)

	import getopt, irafnames
	try:
		optlist, args = getopt.getopt(sys.argv[1:], "ptnimvh")
	except getopt.error, e:
		print str(e)
		usage()
	verbose = 0
	doMonty = 1
	if optlist:
		for opt, value in optlist:
			if opt == "-p":
				irafnames.setPkgStrategy()
			elif opt == "-t":
				irafnames.setTaskStrategy()
			elif opt == "-n":
				irafnames.setCleanStrategy()
			elif opt == "-m":
				doMonty = 1
			elif opt == "-i":
				doMonty = 0
			elif opt == "-v":
				verbose = verbose + 1
			elif opt == "-h":
				usage()
	iraf.setVerbose(verbose)
	del getopt, irafnames, verbose, usage, optlist, args

	# load initial iraf symbols and packages

	iraf.Init()

	print "Pyraf, Python front end to IRAF,", __version__, "(copyright AURA 1999)"
	print "Python: " + sys.copyright
	if doMonty:
		#
		# start up monty keeping definitions in local name space
		#
		exit = 'Use ".exit" to exit'
		quit = exit
		logout = exit
		import monty
		_monty = monty.monty(locals=locals())
		del doMonty, monty
		_monty.start()
	else:
		del doMonty

