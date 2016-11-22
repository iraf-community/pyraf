"""pyrafTk.py: modify tkinter root to print short PyRAF tracebacks

$Id$

R. L. White, 2000 November 17
"""
from __future__ import division # confidence high

import sys
import Tkinter as TKNTR # requires 2to3
import wutil

class _PyrafTk(TKNTR.Tk):

    """Modified Tk class that prints short pyraf tracebacks"""

    def __init__(self, function):
        self._pyraf_showtraceback = function
        TKNTR.Tk.__init__(self)

    def report_callback_exception(self, exc, val, tb):
        sys.stderr.write("Exception in tkinter callback\n")
        sys.last_type = exc
        sys.last_value = val
        sys.last_traceback = tb
        self._pyraf_showtraceback()


def setTkErrorHandler(function):
    """Create Tk root with error handler modified to call function
    If Tk root already exists, this function has no effect.
    """

    if TKNTR._default_root is None and wutil.hasGraphics:
        try:
            root = _PyrafTk(function)
            root.withdraw()
        except TKNTR.TclError:
            pass
