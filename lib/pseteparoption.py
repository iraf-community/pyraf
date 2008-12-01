"""pseteparoption.py: module for defining the specific parameter display
   options to be used for PSETs in the parameter editor task.  Code was 
   broken out from eparoption.py.

$Id: pseteparoption.py 941 2008-11-07 21:10:42Z sontag $
"""

# System level modules
from Tkinter import *

# local modules
from pytools import eparoption
import epar


class PsetEparOption(eparoption.EparOption):

    def makeInputWidget(self):

        # For a PSET self.value is actually an IrafTask object
        # Use task name to label button
        self.buttonText = self.value.getName()

        # Need to adjust the value width so the button is aligned properly
        self.valueWidth = self.valueWidth - 3

        # Generate the button
        self.entry = Button(self.master.frame,
                                 width   = self.valueWidth,
                                 text    = "PSET " + self.buttonText,
                                 relief  = RAISED,
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
        childPsetHandle = epar.EparDialog(self.buttonText,
                                          parent  = self.master.frame,
                                          isChild = 1,
                                          childList = parentToplevel.childList,
                                          title   = "PSET Parameter Editor")
        parentToplevel.childList.append(childPsetHandle)

    # Method called with the "unlearn" menu option is chosen from the
    # popup menu.  Used to unlearn a single parameter value.
    def unlearnValue(self):
        pass
