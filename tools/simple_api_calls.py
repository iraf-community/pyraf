#!/usr/bin/env python

""" This file is meant to be run by itself, demonstrating the Python-to-IRAF
API for use in testing, starting with the very simplest of function calls.
This test is useful in special installations, such as one without IRAF. """

import sys
print("Simple #1 - about to: from pyraf import iraf ...")
from pyraf import iraf
print("Simple #2 - about to import pyraf ...") # should be essentially a no-op
import pyraf
print("Simple #3 - ver is ...")
print(pyraf.__version__)
print("Simple #4 - pwd is ...")
iraf.pwd() # will print
print("Simple #5 - has IRAF is ...")
from pyraf import irafinst
print(str(irafinst.EXISTS))
if not irafinst.EXISTS:
   sys.exit(0)

print("Simple #6 - files output is ... (the rest require IRAF)")
iraf.files('file_a.txt,file-b.txt,file.c.txt,,filed.txt')
print("Simple #7 - loading imutil")
iraf.images(_doprint=0) # load images
iraf.imutil(_doprint=0) # load imutil
print("Simple #8 - imaccess to dev$pix is ...")
print(iraf.imaccess("dev$pix"))
print("Simple #9 - imheader of dev$pix is ...")
iraf.imheader("dev$pix")

sys.exit(0)
