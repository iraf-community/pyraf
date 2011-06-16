#!/usr/bin/env python

""" This file is meant to be run by itself, demonstrating the Python-to-IRAF
API for use in testing, starting with the very simplest of function calls.
This test is useful in special installations, such as one without IRAF. """

from pyraf import iraf
import pyraf
print("pwd is...")
iraf.pwd() # will print
print("ver is...")
print(pyraf.__version__)
print("imheader of dev$pix is ... (requires IRAF)")
iraf.images(_doprint=0) # load images
iraf.imutil(_doprint=0) # load imutil
iraf.imheader("dev$pix")
