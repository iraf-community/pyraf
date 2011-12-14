"""pseteparoption.py: module for defining the specific parameter display
   options to be used for PSETs in the parameter editor task.  Code was
   broken out from eparoption.py.

$Id$
"""
from __future__ import division # confidence high

# System level modules
from Tkinter import *

# local modules
from stsci.tools import eparoption
import epar


class PsetEparOption(eparoption.EparOption):

    def makeInputWidget(self):

        # For a PSET self.value is actually an IrafTask object
        # Use task name to label button
        self.buttonText = self.value.getName()

        # Need to adjust the value width so the button is aligned properly
        if eparoption.USING_X:
            self.valueWidth = self.valueWidth - 3
        else:
            self.valueWidth = self.valueWidth - 6

        self.isSelectable = False

        # Generate the button
        self.entry = Button(self.master_frame,
                                 width   = self.valueWidth,
                                 text    = "PSET " + self.buttonText,
                                 relief  = RAISED,
                                 background = self.bkgColor,
                                 highlightbackground = self.bkgColor,
                                 command = self.childEparDialog)
        self.entry.pack(side = LEFT)

    def childEparDialog(self):

        # Get a reference to the parent TopLevel
        parentToplevel  = self.master.winfo_toplevel()

        # Don't create multiple windows for the same task
        name = self.value.getName()
        for child in parentToplevel.childList:
            if child.taskName == name:
                child.top.deiconify()
                child.top.tkraise()
                return
        childPsetHandle = epar.PyrafEparDialog(self.buttonText,
                                          parent  = self.master_frame,
                                          isChild = 1,
                                          childList = parentToplevel.childList,
                                          title   = "PSET Parameter Editor")
        parentToplevel.childList.append(childPsetHandle)

    # Method called with the "unlearn" menu option is chosen from the
    # popup menu.  Used to unlearn a single parameter value.
    def unlearnValue(self):
        pass
