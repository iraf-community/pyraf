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

@(#)pyraf.py v1.6 99/01/26

R. White, 1999 Jan 25
"""

import sys, monty, iraf

# load initial iraf symbols and packages (we could
# do this automatically in iraf.py)

iraf.init()

# make sure images and tv packages are loaded
# (they should be if login.cl is found)

iraf.load("tv",doprint=0)
iraf.load("images",doprint=0)

# get the imstat, imhead, disp tasks

imstat = iraf.getTask("imstatistics")
imhead = iraf.getTask("imheader")
disp = iraf.getTask("display")

if __name__ == "__main__":
	#
	# start up monty keeping definitions in local name space
	#
	print 'Pyraf, Python front end to IRAF (copyright AURA 1999)'
	print 'Python: ' + sys.copyright
	m = monty.monty(locals=locals())
	m.start()
