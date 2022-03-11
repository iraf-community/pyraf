####
#       Class AlertDialog
#
#       Purpose
#       -------
#
#       AlertDialog's are widgets that allow one to pop up warnings, one line
#       questions etc. They return a set of standard action numbers being :-
#       0 => Cancel was pressed
#       1 => Yes was pressed
#       2 => No was pressed
#
#       Standard Usage
#       --------------
#
#       F = AlertDialog(widget, message)
#       action = F.Show()
####
"""
$Id$
"""
from .dialog import *


class AlertDialog(ModalDialog):

    def __init__(self, widget, msg):
        self.widget = widget
        self.msgString = msg
        Dialog.__init__(self, widget)

    def SetupDialog(self):
        upperFrame = Frame(self.top)
        upperFrame['relief'] = 'raised'
        upperFrame['bd']         = 1
        upperFrame.pack({'expand':'yes', 'side':'top', 'fill':'both' })
        self.bitmap = Label(upperFrame)
        self.bitmap.pack({'side':'left'})
        msgList = self.msgString.split("\n")
        for i in range(len(msgList)):
            msgText = Label(upperFrame)
            msgText["text"]   = msgList[i]
            msgText.pack({'expand':'yes', 'side':'top', 'anchor':'nw',
                    'fill':'x' })
        self.lowerFrame = Frame(self.top)
        self.lowerFrame['relief'] = 'raised'
        self.lowerFrame['bd']    = 1
        self.lowerFrame.pack({'expand':'yes', 'side':'top', 'pady':'2',
                'fill':'both' })

    def OkPressed(self):
        self.TerminateDialog(1)

    def CancelPressed(self):
        self.TerminateDialog(0)

    def NoPressed(self):
        self.TerminateDialog(2)

    def CreateButton(self, text, command):
        self.button = Button(self.lowerFrame)
        self.button["text"]       = text
        self.button["command"]   = command
        self.button.pack({'expand':'yes', 'pady':'2', 'side':'left'})

####
#       Class ErrorDialog
#
#       Purpose
#       -------
#
#       To pop up an error message
####

class ErrorDialog(AlertDialog):

    def SetupDialog(self):
        AlertDialog.SetupDialog(self)
        self.bitmap['bitmap'] = 'error'
        self.CreateButton("OK", self.OkPressed)

####
#       Class WarningDialog
#
#       Purpose
#       -------
#
#       To pop up a warning message.
####

class WarningDialog(AlertDialog):

    def SetupDialog(self):
        AlertDialog.SetupDialog(self)
        self.bitmap['bitmap'] = 'warning'
        self.CreateButton("Yes", self.OkPressed)
        self.CreateButton("No", self.CancelPressed)

####
#       Class QuestionDialog
#
#       Purpose
#       -------
#
#       To pop up a simple question
####

class QuestionDialog(AlertDialog):

    def SetupDialog(self):
        AlertDialog.SetupDialog(self)
        self.bitmap['bitmap'] = 'question'
        self.CreateButton("Yes", self.OkPressed)
        self.CreateButton("No", self.NoPressed)
        self.CreateButton("Cancel", self.CancelPressed)

####
#       Class MessageDialog
#
#       Purpose
#       -------
#
#       To pop up a message.
####

class MessageDialog(AlertDialog):

    def SetupDialog(self):
        AlertDialog.SetupDialog(self)
        self.bitmap['bitmap'] = 'warning'
        self.CreateButton("Dismiss", self.CancelPressed)
