""" Read-Only tkinter Text Widget.  This is a variation of the tkinter Text
widget in that the text itself is not editable (it is read-only), but it allows
selection for cut/paste to other apps.  Cut-paste may currently only work
under X11. (9/2015 enabled under OSX by adding 'c' to ALLOWED_SYMS)

A vastly simpler way of doing this is to use a tkinter.Text widget and set
it to DISABLED, but then you cannot select text.
$Id$
"""
import sys
import tkinter as TKNTR

ALLOWED_SYMS = ('c', 'Up', 'Down', 'Left', 'Right', 'Home', 'End', 'Prior',
                'Next', 'Shift_L', 'Shift_R')


class ROText(TKNTR.Text):

    def __init__(self, master, **kw):
        """  defer most of __init__ to the base class """
        self._fbto = None
        if 'focusBackTo' in kw:
            self._fbto = kw['focusBackTo']
            del kw['focusBackTo']
        TKNTR.Text.__init__(self, master, **kw)
        # override some bindings to return a "break" string
        self.bind("<Key>", self.ignoreMostKeys)
        self.bind("<Button-2>", lambda e: "break")
        self.bind("<Button-3>", lambda e: "break")
        if self._fbto:
            self.bind("<Leave>", self.mouseLeft)
        self.config(insertwidth=0)

    # disallow common insert calls, but allow a backdoor when needed
    def insert(self, index, text, *tags, **kw):
        if 'force' in kw and kw['force']:
            TKNTR.Text.insert(self, index, text, *tags)

    # disallow common delete calls, but allow a backdoor when needed
    def delete(self, start, end=None, force=False):
        if force:
            TKNTR.Text.delete(self, start, end)

    # a way to disable text manip
    def ignoreMostKeys(self, event):
        if event.keysym not in ALLOWED_SYMS:
            return "break"  # have to return this string to stop the event
        # To get copy/paste working on OSX we allow 'c' so that
        # they can type 'Command-c', but don't let a regular 'c' through.
        if event.keysym in ('c', 'C'):
            if (sys.platform == 'darwin' and hasattr(event, 'state') and
                    event.state != 0):
                pass  # allow this through, it is Command-c
            else:
                return "break"

    def mouseLeft(self, event):
        if self._fbto:
            self._fbto.focus_set()
        return "break"  # have to return this string to stop the event
