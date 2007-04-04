"""module irafglobals.py -- widely used IRAF constants and objects

yes, no         Boolean values
IrafError       Standard IRAF exception
Verbose         Flag indicating verbosity level
pyrafDir        Directory with these Pyraf programs
userIrafHome    User's IRAF home directory (./ or ~/iraf/)
userWorkingHome User's working home directory (the directory
                when this module gets imported.)
EOF             End-of-file indicator object
INDEF           Undefined object
IrafTask        "Tag" class for IrafTask type.
IrafPkg         "Tag" class for IrafPkg type

This is defined so it is safe to say 'from irafglobals import *'

The tag classes do nothing except allow checks of types via (e.g.)
isinstance(o,IrafTask).  Including it here decouples the other classes
from the module that actually implements IrafTask, greatly reducing the
need for mutual imports of modules by one another.

$Id$

R. White, 2000 January 5
"""

import os, sys
_os = os
_sys = sys
del os, sys

_use_ecl = _os.environ.get("PYRAF_USE_ECL", False)

class IrafError(Exception):
    def __init__(self, msg, errno=-1, errmsg="", errtask=""):
        Exception.__init__(self, msg)
        self.errno = errno
        self.errmsg = errmsg or msg
        self.errtask = errtask

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
    def __str__(self): return str(self.value)

Verbose = _VerboseClass()

# -----------------------------------------------------
# userWorkingHome is current working directory
# -----------------------------------------------------

userWorkingHome = _os.getcwd()

# -----------------------------------------------------
# pyrafDir is directory containing this script
# -----------------------------------------------------

if __name__ == "__main__":
    thisfile = _sys.argv[0]
else:
    thisfile = __file__
# follow links to get to the real filename
while _os.path.islink(thisfile):
    thisfile = _os.readlink(thisfile)
pyrafDir = _os.path.dirname(thisfile)
del thisfile

if not pyrafDir: pyrafDir = userWorkingHome
# change relative directory paths to absolute and normalize path
pyrafDir = _os.path.normpath(_os.path.join(userWorkingHome, pyrafDir))

# -----------------------------------------------------
# userIrafHome is location of user's IRAF home directory
# -----------------------------------------------------

# If login.cl exists here, use this directory as home.
# Otherwise look for ~/iraf.

if _os.path.exists('./login.cl'):
    userIrafHome = _os.path.join(userWorkingHome,'')
else:
    userIrafHome = _os.path.join(_os.environ['HOME'],'iraf','')
    if not _os.path.exists(userIrafHome):
        # no ~/iraf, just use '.' as home
        userIrafHome = _os.path.join(userWorkingHome,'')

# -----------------------------------------------------
# Boolean constant class
# -----------------------------------------------------

class _Boolean:
    """Class of boolean constant object"""
    def __init__(self, value):
        # change value to 1 or 0
        if value:
            self.__value = 1
        else:
            self.__value = 0
        self.__strvalue = ["no", "yes"][self.__value]

    def __copy__(self):
        """Don't bother to make a copy"""
        return self

    def __deepcopy__(self, memo=None):
        """Don't bother to make a copy"""
        return self

    def __cmp__(self, other):
        if isinstance(other,str):
            # If a string, compare with string value of this parameter
            # Allow uppercase "YES", "NO" as well as lowercase
            # Also allows single letter abbrevation "y" or "n"
            ovalue = other.lower()
            if len(ovalue) == 1:
                return cmp(self.__strvalue[0], ovalue)
            else:
                return cmp(self.__strvalue, ovalue)
        else:
            # for all other types (int, float, bool, etc) treat this
            # value like an integer
            return cmp(self.__value, other)

    def __nonzero__(self): return self.__value
    def __repr__(self): return self.__strvalue
    def __str__(self): return self.__strvalue
    def __int__(self): return self.__value
    def __float__(self): return float(self.__value)

# create yes, no boolean values

yes = _Boolean(1)
no = _Boolean(0)


# -----------------------------------------------------
# define end-of-file object
# if printed, says 'EOF'
# if converted to integer, has value -2 (special IRAF value)
# Implemented as a singleton, although the singleton
# nature is not really essential
# -----------------------------------------------------

class _EOFClass:
    """Class of singleton EOF (end-of-file) object"""
    def __init__(self):
        global EOF
        if EOF is not None:
            # only allow one to be created
            raise RuntimeError("Use EOF object, not _EOFClass")

    def __copy__(self):
        """Not allowed to make a copy"""
        return self

    def __deepcopy__(self, memo=None):
        """Not allowed to make a copy"""
        return self

    def __cmp__(self, other):
        if isinstance(other, self.__class__):
            # Despite trying to create only one EOF object, there
            # could be more than one.  All EOFs are equal.
            return 0
        elif isinstance(other,str):
            # If a string, compare with 'EOF'
            return cmp("EOF", other)
        elif isinstance(other,(int,float,long)):
            # If a number, compare with -2
            return cmp(-2, other)
        else:
            return 1

    def __repr__(self): return "EOF"
    def __str__(self): return "EOF"
    def __int__(self): return -2
    def __float__(self): return -2.0

# initialize EOF to None first so singleton scheme works

EOF = None
EOF = _EOFClass()

# -----------------------------------------------------
# define IRAF-like INDEF object
# -----------------------------------------------------

class _INDEFClass(object):
    """Class of singleton INDEF (undefined) object"""

    def __new__(cls):
        # Guido's example Singleton pattern
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        # this use of super gets the correct version of __new__ for the
        # int and float subclasses too
        cls.__it__ = it = super(_INDEFClass, cls).__new__(cls)
        return it

    def __copy__(self):
        """Not allowed to make a copy"""
        return self

    def __deepcopy__(self, memo=None):
        """Not allowed to make a copy"""
        return self

    def __lt__(self, other): return INDEF
    def __le__(self, other): return INDEF
    def __gt__(self, other): return INDEF
    def __ge__(self, other): return INDEF

    def __eq__(self, other):
        # Despite trying to create only one INDEF object, there
        # could be more than one.  All INDEFs are equal.
        return isinstance(other, _INDEFClass)

    def __ne__(self, other):
        return not isinstance(other, _INDEFClass)

    def __repr__(self): return "INDEF"
    def __str__(self): return "INDEF"

    __oct__ = __str__
    __hex__ = __str__

    # type conversions return various types of INDEF objects
    # this is necessary for Python 2.4

    def __int__(self): return _INDEF_int
    def __long__(self): return _INDEF_int
    def __float__(self): return _INDEF_float

    def __nonzero__(self): return 0

    # all operations on INDEF return INDEF

    def __add__(self, other): return INDEF

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

    def __neg__(self): return INDEF

    __pos__    = __neg__
    __abs__    = __neg__
    __invert__ = __neg__

INDEF = _INDEFClass()

# Classes that inherit from built-in types are required for Python 2.4
# so that int and float conversion functions work correctly.
# Unfortunately, if you call int(_INDEF_int) it ignores the
# __int__ method and returns zero, so these objects should be
# used sparingly and replaced with standard INDEF whereever
# possible.

class _INDEFClass_int(_INDEFClass, int): pass
class _INDEFClass_float(_INDEFClass, float): pass
_INDEF_int = _INDEFClass_int()
_INDEF_float = _INDEFClass_float()

# -----------------------------------------------------
# define IRAF-like EPSILON object
# -----------------------------------------------------

class _EPSILONClass(object):
    """Class of singleton EPSILON object, for floating-point comparison"""

    def __new__(cls):
        # Guido's example Singleton pattern
        it = cls.__dict__.get("__it__")
        if it is not None:
            return it
        cls.__it__ = it = super(_EPSILONClass, cls).__new__(cls)
        return it

    def __init__(self):
        self.__dict__["_value"] = None

    def setvalue(self):
        DEFAULT_VALUE = 1.192e-7
        hlib = _os.environ.get("hlib")
        if hlib is None:
            self._value = DEFAULT_VALUE
            return
        fd = open(_os.path.join(hlib, "mach.h"))
        lines = fd.readlines()
        fd.close()
        foundit = 0
        for line in lines:
            words = line.split()
            if len(words) < 1 or words[0] == "#":
                continue
            if words[0] == "define" and words[1] == "EPSILONR":
                strvalue = words[2]
                if strvalue[0] == "(":
                    strvalue = strvalue[1:-1]
                self._value = float(strvalue)
                foundit = 1
                break
        if not foundit:
            self._value = DEFAULT_VALUE

    def __copy__(self):
        """Not allowed to make a copy"""
        return self

    def __deepcopy__(self, memo=None):
        """Not allowed to make a copy"""
        return self

    def __setattr__(self, name, value):
        """Not allowed to modify the value or add a new attribute"""
        if name == "_value":
            if self.__dict__["_value"] is None:
                self.__dict__["_value"] = value
            else:
                raise RuntimeError, "epsilon cannot be modified"
        else:
            pass

    def __delattr__(self, value):
        """Not allowed to delete the value"""
        pass

    def __cmp__(self, other):
        return cmp(self._value, other)

    def __repr__(self): return "%.6g" % self._value
    def __str__(self): return "%.6g" % self._value

    __oct__ = None
    __hex__ = None

    def __int__(self): return 0
    def __long__(self): return 0
    def __float__(self): return self._value

    def __nonzero__(self): return 1

epsilon = _EPSILONClass()
epsilon.setvalue()

# -----------------------------------------------------
# tag classes
# -----------------------------------------------------

class IrafTask:
    pass

class IrafPkg(IrafTask):
    pass
