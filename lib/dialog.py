####
#       Class Dialog
#
#       Purpose
#       Base class for many dialog box classes.
####

from Tkinter import *

class Dialog:

    def __init__(self, master):
        self.master = master
        self.top = Toplevel(self.master)
        self.top.title(self.__class__.__name__)
        self.top.minsize(1, 1)
        self.myWaitVar = `self.top` + 'EndDialogVar'

    def Show(self):
        self.SetupDialog()
        self.CenterDialog()
        self.top.deiconify()
        self.top.focus()

    def TerminateDialog(self, withValue):
        self.top.setvar(self.myWaitVar, withValue)
        self.top.withdraw()

    def DialogCleanup(self):
        self.top.destroy()
        self.master.focus()

    def SetupDialog(self):
        pass

    def CenterDialog(self):
        self.top.withdraw()
        self.top.update_idletasks()
        w = self.top.winfo_screenwidth()
        h = self.top.winfo_screenheight()
        reqw = self.top.winfo_reqwidth()
        reqh = self.top.winfo_reqheight()
        centerx = `(w-reqw)/2`
        centery = `(h-reqh)/2 - 100`
        geomStr = "+" + centerx + "+" + centery
        self.top.geometry(geomStr)

####
#       Class ModalDialog
#
#       Purpose
#       Base class for many modal dialog box classes.
####

class ModalDialog(Dialog):

    def __init__(self, master):
        Dialog__init__(self, master)

    def Show(self):
        import string
        self.SetupDialog()
        self.CenterDialog()
        self.top.grab_set()
        self.top.focus()
        self.top.deiconify()
        self.top.waitvar(self.myWaitVar)
        try:
            return string.atoi(self.top.getvar(self.myWaitVar))
        except TypeError:
            return int(self.top.getvar(self.myWaitVar))
