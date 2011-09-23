#!/usr/bin/env python

""" This file is meant to be run by itself, demonstrating the Python-to-IRAF
API for use in testing, starting with the very simplest of function calls.
This test is useful in special installations, such as one without IRAF. """

import sys
print("1 - about to import iraf ...")
from pyraf import iraf
print("2 - about to import pyraf ...") # should be essentially a no-op
import pyraf
print("3 - ver is ...")
print(pyraf.__version__)
print("4 - pwd is ...")
iraf.pwd() # will print
print("5 - imheader of dev$pix is ... (requires IRAF)")
iraf.images(_doprint=0) # load images
iraf.imutil(_doprint=0) # load imutil
iraf.imheader("dev$pix")
sys.exit(0)
