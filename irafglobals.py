"""module irafglobals.py -- widely used IRAF constants and objects

yes, no			Boolean values
EOF				End-of-file string
IrafError		Standard IRAF exception
Verbose			Flag indicating verbosity level
pyrafDir		Directory with these Pyraf programs
userIrafHome	User's IRAF home directory (./ or ~/iraf/)
userWorkingHome	User's working home directory (the directory
				when this module gets imported.)
INDEF			Undefined object

This is defined so it is safe to say 'from irafglobals import *'

$Id$

R. White, 2000 January 5
"""

import os, sys
_os = os
_sys = sys
del os, sys

yes = 1
no = 0
EOF = 'EOF'

class IrafError(Exception):
	pass

# -----------------------------------------------------
# Verbose: verbosity flag
# -----------------------------------------------------

# make Verbose an instance of a class so it can be imported
# into other modules and changed by them

class _VerboseClass:
	"""Container class for verbosity (or other) value"""
	def __init__(self, value=0): self.value = value
	def set(self, value): self.value = value
	def get(self): return self.value
	def __cmp__(self, other): return cmp(self.value, other)
	def __nonzero__(self): return (self.value != 0)

Verbose = _VerboseClass()

# -----------------------------------------------------
# pyrafDir is directory containing this script
# -----------------------------------------------------

if __name__ == "__main__":
	pyrafDir = _os.path.dirname(_sys.argv[0])
else:
	pyrafDir = _os.path.dirname(__file__)

if not pyrafDir: pyrafDir = _os.getcwd()
if not _os.path.isabs(pyrafDir):
	# change relative directory paths to absolute
	pyrafDir = _os.path.join(_os.getcwd(), pyrafDir)

# -----------------------------------------------------
# userIrafHome is location of user's IRAF home directory
# -----------------------------------------------------

# If login.cl exists here, use this directory as home.
# Otherwise look for ~/iraf.

if _os.path.exists('./login.cl'):
	userIrafHome = _os.path.join(_os.getcwd(),'')
else:
	userIrafHome = _os.path.join(_os.environ['HOME'],'iraf','')
	if not _os.path.exists(userIrafHome):
		# no ~/iraf, just use '.' as home
		userIrafHome = _os.path.join(_os.getcwd(),'')

# -----------------------------------------------------
# userWorkingHome is current working directory
# -----------------------------------------------------

userWorkingHome = _os.getcwd()

# -----------------------------------------------------
# define IRAF-like INDEF object
# -----------------------------------------------------

class _INDEFClass:
	"""Class of singleton INDEF (undefined) object"""
	def __init__(self):
		global INDEF
		if INDEF is not None:
			# only allow one to be created
			raise RuntimeError("Use INDEF object, not _INDEFClass")

	def __cmp__(self, other):
		if other is INDEF:
			# this probably never gets called since Python checks
			# whether the objects are identical before calling __cmp__
			return 0
		else:
			#XXX Note this implies INDEF is equivalent to +infinity
			#XXX This is the only way to get the right answer
			#XXX on tests of equality to INDEF
			#XXX Replace this once rich comparisons (__gt__, __lt__, etc.)
			#XXX are available (Python 1.6?)
			return 1

	def __repr__(self): return "INDEF"
	def __str__(self): return "INDEF"

	__oct__ = __str__
	__hex__ = __str__

	def __nonzero__(self): return 0

	# all operations on INDEF return INDEF

	def __add__(self, other): return self

	__sub__    = __add__
	__mul__    = __add__
	__rmul__   = __add__
	__div__    = __add__
	__mod__    = __add__
	__divmod__ = __add__
	__pow__    = __add__
	__lshift__ = __add__
	__rshift__ = __add__
	__and__    = __add__
	__xor__    = __add__
	__or__     = __add__

	__radd__    = __add__
	__rsub__    = __add__
	__rmul__    = __add__
	__rrmul__   = __add__
	__rdiv__    = __add__
	__rmod__    = __add__
	__rdivmod__ = __add__
	__rpow__    = __add__
	__rlshift__ = __add__
	__rrshift__ = __add__
	__rand__    = __add__
	__rxor__    = __add__
	__ror__     = __add__

	def __neg__(self): return self

	__pos__    = __neg__
	__abs__    = __neg__
	__invert__ = __neg__

	# it is a bit nasty having these functions not return
	# the promised int, float, etc. -- but it is required that
	# this object act just like an undefined value for one of
	# those types, so I need to pretend it really is a legal
	# int or float

	__int__    = __neg__
	__long__   = __neg__
	__float__  = __neg__


# initialize INDEF to None first so singleton scheme works

INDEF = None
INDEF = _INDEFClass()

