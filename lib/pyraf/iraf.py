"""module iraf.py -- home for all the IRAF tasks and basic access functions

$Id$

R. White, 1999 Jan 25
"""
from __future__ import division, print_function

from iraffunctions import *

# a few CL tasks have modified names (because they start with '_')
import iraffunctions

_curpack = iraffunctions.curpack
_allocate = iraffunctions.clAllocate
_deallocate = iraffunctions.clDeallocate
_devstatus = iraffunctions.clDevstatus

del iraffunctions
