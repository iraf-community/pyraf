"""pseteparoption.py: module for defining the specific parameter display
   options to be used for PSETs in the parameter editor task.  Code was
   broken out from eparoption.py.
"""


# local modules
from stsci.tools import eparoption
from . import epar


class PsetEparOption(eparoption.ActionEparButton):

    def getButtonLabel(self):

        # Return the string to show on the button.  This happens to be
        # a great time to set self.psetName

        # For a PSET self.value is actually an IrafTask object
        # Use task name to label button
        self.psetName = self.value.getName()

        return "PSET " + self.psetName

    def clicked(self):  # use to be called childEparDialog()

        # Get a reference to the parent TopLevel
        parentToplevel = self.master.winfo_toplevel()

        # Don't create multiple windows for the same task
        for child in parentToplevel.childList:
            if child.taskName == self.psetName:
                child.top.deiconify()
                child.top.tkraise()
                return

        childPsetHandle = epar.PyrafEparDialog(
            self.psetName,
            parent=self.master_frame,
            isChild=1,
            childList=parentToplevel.childList,
            title="PSET Parameter Editor")
        parentToplevel.childList.append(childPsetHandle)
