"""pyrafTk.py: modify Tkinter root to print short PyRAF tracebacks

$Id$

R. L. White, 2000 November 17
"""
from __future__ import division # confidence high

import sys, Tkinter, wutil

class _PyrafTk(Tkinter.Tk):

    """Modified Tk class that prints short pyraf tracebacks"""

    def __init__(self, function):
        self._pyraf_showtraceback = function
        Tkinter.Tk.__init__(self)

    def report_callback_exception(self, exc, val, tb):
        sys.stderr.write("Exception in Tkinter callback\n")
        sys.last_type = exc
        sys.last_value = val
        sys.last_traceback = tb
        self._pyraf_showtraceback()


def setTkErrorHandler(function):
    """Create Tk root with error handler modified to call function
    If Tk root already exists, this function has no effect.
    """

    if Tkinter._default_root is None and wutil.hasGraphics:
        try:
            root = _PyrafTk(function)
            root.withdraw()
        except Tkinter.TclError:
            pass
