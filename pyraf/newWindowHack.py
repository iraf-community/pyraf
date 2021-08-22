"""
This module hacks tkSimpleDialog to make askstring() work
even when the root window has been withdrawn.

w/o this hack,  Python-2.4.3/Tk8.4 locks up for the following
code:  the dialog is created,  but it is withdrawn just like the
root window (!) so there is nothing to interact with and the system
hangs.

import tkinter
tk = tkinter.Tk()
tk.withdraw()
import tkSimpleDialog
tkSimpleDialog.askstring("window title", "question?")
"""


import tkinter.simpledialog
from tkinter import Toplevel, Frame


def __init__(self, parent, title=None):
    '''Initialize a dialog.

    Arguments:

    parent -- a parent window (the application window)

    title -- the dialog title
    '''
    Toplevel.__init__(self, parent)

    if parent.winfo_viewable():  # XXX this condition is the only "fix".
        self.transient(parent)

    if title:
        self.title(title)

    self.parent = parent

    self.result = None

    body = Frame(self)
    self.initial_focus = self.body(body)
    body.pack(padx=5, pady=5)

    self.buttonbox()

    self.wait_visibility()  # window needs to be visible for the grab
    self.grab_set()

    if not self.initial_focus:
        self.initial_focus = self

    self.protocol("WM_DELETE_WINDOW", self.cancel)

    if self.parent is not None:
        self.geometry("+{:d}+{:d}".format(parent.winfo_rootx() + 50,
                                          parent.winfo_rooty() + 50))

    self.initial_focus.focus_set()

    self.wait_window(self)


tkinter.simpledialog.Dialog.__init__ = __init__
"""
Here are some more notes from my "investigation":

====================================================================================

http://mail.python.org/pipermail/python-list/2005-April/275761.html

tkinter "withdraw" and "askstring" problem
Jeff Epler jepler at unpythonic.net
Tue Apr 12 15:58:22 CEST 2005

    * Previous message: tkinter "withdraw" and "askstring" problem
    * Next message: os.open() i flaga lock
    * Messages sorted by: [ date ] [ thread ] [ subject ] [ author ]

The answer has to do with a concept Tk calls "transient".
    wm transient window ?master?
        If master is specified, then the window manager is informed that
        window  is  a  transient window (e.g. pull-down menu) working on
        behalf of master (where master is the path name for a  top-level
        window).   If master is specified as an empty string then window
        is marked as not being a transient window any  more.   Otherwise
        the command returns the path name of s current master, or
        an empty string if window t currently a transient window.  A
        transient  window  will  mirror  state changes in the master and
        inherit the state of the master when initially mapped. It is  an
        error to attempt to make a window a transient of itself.

In tkSimpleDialog, the dialog window is unconditionally made transient
for the master.  Windows is simply following the documentation: The
askstring window "inherit[s] the state of the master [i.e., withdrawn]
when initially mapped".

The fix is to modify tkSimpleDialog.Dialog.__init__ to only make the
dialog transient for its master when the master is viewable.  This
mirrors what is done in dialog.tcl in Tk itself.  You can either change
tkSimpleDialog.py, or you can include a new definition of __init__ with
these lines at the top, and the rest of the function the same:

    def __init__(self, parent, title = None):
        ''' the docstring ... '''
        Toplevel.__init__(self, parent)
        if parent.winfo_viewable():
            self.transient(parent)
        ...

    # Thanks for being so dynamic, Python!
    tkSimpleDialog.Dialog.__init__ = __init__; del __init__

Jeff


"""
