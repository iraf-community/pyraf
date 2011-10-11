#!/usr/bin/env python

""" This file is meant to be run by itself, demonstrating the Python-to-IRAF
API for use in testing, starting with the very simplest of function calls.
This test is useful in special installations, such as one without IRAF. """

import sys
print("simple #1 - about to: from pyraf import iraf ...")
from pyraf import iraf
print("simple #2 - about to import pyraf ...") # should be essentially a no-op
import pyraf
print("simple #3 - ver is ...")
print(pyraf.__version__)
print("simple #4 - pwd is ...")
iraf.pwd() # will print
print("simple #5 - has IRAF is ...")
from pyraf import irafinst
print(str(irafinst.EXISTS))
if not irafinst.EXISTS:
   sys.exit(0)

print("simple #6 - imaccess to dev$pix is ... (requires IRAF)")
iraf.images(_doprint=0) # load images
iraf.imutil(_doprint=0) # load imutil
print(iraf.imaccess("dev$pix"))
print("simple #7 - imheader of dev$pix is ... (requires IRAF)")
iraf.imheader("dev$pix")

sys.exit(0)
