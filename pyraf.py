#! /usr/local/bin/python -i 
"""
Start up pyraf (Python IRAF front end)

Brief help:

	To load a package:
		iraf.load("images")
		iraf.run("images")
	The .run version does not list the tasks after loading.
	You can also do iraf.load("images",doprint=0) or just
	iraf.load("images",0) to skip printing.

	To get short-hand task object:
		imstat = iraf.getTask("imstatistics")
		imhead = iraf.getTask("imheader")

	To set task parameters:
		imstat.set("images","dev$pix")
		imhead.setParList("dev$pix",longheader="yes")

	To run task:
		imstat()
		imstat.run()
		iraf.run("imstat")
		imhead("dev$pix",longheader="yes")

Other forms will be added later.

$Id$

R. White, 1999 March 4
"""

import os, sys, monty, iraf

# load initial iraf symbols and packages (we could
# do this automatically in iraf.py)

iraf.init()

yes = 1
no = 0
flpr = "This is not the IRAF cl!  Forget those old bad habits!"
retall = "This is not IDL..."

# set search path to include directory containing this script
# and current directory

dirname = os.path.dirname(sys.argv[0])
if not dirname: dirname = os.getcwd()
if dirname not in sys.path:
	sys.path.insert(0, dirname)
	sys.path.insert(0, '.')
del dirname

if __name__ == "__main__":
	#
	# start up monty keeping definitions in local name space
	#
	print 'Pyraf, Python front end to IRAF (copyright AURA 1999)'
	print 'Python: ' + sys.copyright
	m = monty.monty(locals=locals())
	m.start()
