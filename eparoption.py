"""module 'eparoption.py' -- module for defining the various parameter display
   options to be used for the parameter editor task.  The widget that is used
   for entering the parameter value is the variant.

   Parameter types: 
   string  - Entry widget
   *gcur   - NOT IMPLEMENTED AT THIS TIME
   ukey    - NOT IMPLEMENTED AT THIS TIME
   pset    - Action button
   real    - Entry widget
   int     - Entry widget
   boolean - Radiobutton widget
   array real - NOT IMPLEMENTED AT THIS TIME
   array int  - NOT IMPLEMENTED AT THIS TIME

   Enumerated lists - Menubutton/Menu widget

$Id$

M.D. De La Pena, 1999 August 05
"""
# System level modules
from Tkinter import *
import os, sys, string, commands
import FileDialog, tkFileDialog

# Community modules
import filedlg

# PYRAF modules
import iraftask, epar

# Constants 
MAXLIST  =  15
MAXLINES = 100

class EparOption:

    # Chosen option 
    choiceClass = StringVar

    def entryCheck(self, event = None):
        pass

    def __init__(self, master, statusBar, paramInfo, fieldWidths):

        # Connect to the information/status Label
        self.status = statusBar

        # A new Frame is created for each parameter entry
        self.master       = master
        self.master.frame = Frame(self.master)
        self.paramInfo    = paramInfo
        self.inputWidth   = fieldWidths.get('inputWidth')
        self.valueWidth   = fieldWidths.get('valueWidth')
        self.promptWidth  = fieldWidths.get('promptWidth')

        self.choice = self.choiceClass(self.master.frame)

        self.name  = self.paramInfo.get(field = "p_name", native = 0, 
                     prompt = 0) 
        self.value = self.paramInfo.get(field = "p_filename", native = 0, 
                     prompt = 0) 

        # Generate the input label
        self.inputLabel = Label(self.master.frame, anchor = W, 
                                text  = self.name, 
                                width = self.inputWidth)
        self.inputLabel.pack(side = LEFT, fill = X, expand = TRUE)

        # Get the prompt string and determine if special handling is needed
        self.prompt = self.paramInfo.get(field = "p_prompt", native = 0, 
                      prompt = 0) 

        #self.promptLabel = Label(self.master.frame, anchor = W,
        #    text = self.paramInfo.get(field = "p_prompt", native = 1, prompt = 0), 
        #           width = self.promptWidth)
        #self.promptLabel.pack(side = RIGHT)

        # Check the prompt to determine how many lines of valid text exist
        lines       = string.split(self.prompt, "\n")
        nlines      = len(lines)
        promptLines = lines[0]
        infoLines   = ""
        blankLineNo = MAXLINES
        if (nlines > 1):
  
            # Keep all the lines of text before the blank line for the prompt
            for i in range(1, nlines):
                ntokens = string.split(lines[i])
                if ntokens != []:
                   promptLines = string.join([promptLines, lines[i]], "\n")
                else:
                   blankLineNo = i
                   break

        # Generate the prompt label
        self.promptLabel = Label(self.master.frame, anchor = W,
                                 text = promptLines, width = self.promptWidth)
        self.promptLabel.pack(side = RIGHT, fill = X, expand = TRUE)

        # Generate the input widget depending upon the datatype
        self.makeInputWidget()

        # Pack the parameter entry Frame
        self.master.frame.pack(side = TOP)

        # If there is more text associated with this entry, join all the 
        # lines of text with the blank line.  This is the "special" text 
        # information.
        if (blankLineNo < (nlines - 1)):

            # Put the text after the blank line into its own Frame
            self.master.infoText = Frame(self.master)

            for j in range(blankLineNo + 1, nlines):
                ntokens = string.split(lines[j])
                if ntokens != []:
                    infoLines = string.join([infoLines, lines[j]], "\n")
                else:
                    break

            # Assign the informational text to the label and pack
            self.master.infoText.label = Label(self.master.infoText, 
                                               text = infoLines, 
                                               anchor = W)
            self.master.infoText.label.pack(side = LEFT)
            self.master.infoText.pack(side = TOP, anchor = W)

    def unlearnOption(self, newParamInfo):

        self.newParamInfo = newParamInfo

        # Clear the Entry widget and obtain the default value
        self.entry.delete(0, END)

        self.newValue = self.newParamInfo.get(field = "p_filename", native = 0, 
                                              prompt = 0) 
        self.choice.set(self.newValue)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)


class EnumEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, fieldWidths)

    def makeInputWidget(self):

        # Set the initial value for the button
        self.choice.set(self.value)

        # Need to adjust the value width so the menu button is the
        # aligned properly
        self.valueWidth = self.valueWidth - 5

        # Generate the button
        self.button = Menubutton(self.master.frame, 
                                 width  = self.valueWidth,
                                 text   = self.choice.get(),      # label
                                 relief = RAISED,           
                                 anchor = W,                      # alignment
                                 textvariable = self.choice,      # var to sync 
                                 indicatoron  = 1)                # tiny box

        self.button.menu = Menu(self.button,  
                                tearoff = 0,
                                background = "white",
                                activebackground = "gainsboro")

        # Generate the menu options
        for option in (self.paramInfo.choice):
            self.button.menu.add_radiobutton(label    = option,
                                             value    = option, 
                                             variable = self.choice, 
                                             indicatoron = 0)

        # set up a pointer from the menubutton back to the menu
        self.button['menu'] = self.button.menu

        self.button.pack(side = LEFT)

    def unlearnOption(self, newParamInfo):

        self.newParamInfo = newParamInfo
        self.newValue = self.newParamInfo.get(field = "p_filename", native = 0, 
                                           prompt = 0) 
        self.choice.set(self.newValue)


class BooleanEparOption(EparOption):

    # Override base close option 
    choiceClass = BooleanVar

    def __init__(self, master, statusBar, paramInfo, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, fieldWidths)

    def makeInputWidget(self):

        # Need to buffer the value width so the radio buttons and
        # the adjoining labels are aligned properly
        self.valueWidth = self.valueWidth + 10
        self.padWidth   = self.valueWidth / 2

        # Check as some boolean parameters have no default value
        # This could happen if the parameter is a consequence of 
        # an interactive mode query which must be answered.
        if (self.value == ""):
            self.choice.set("no")
        else:
            self.choice.set(self.value)

        self.frame = Frame(self.master.frame, relief = FLAT, width = self.valueWidth)
        self.rbyes = Radiobutton(self.frame, text = "Yes",
                                 variable    = self.choice,
                                 value       = "yes",  
                                 selectcolor = "SpringGreen",
                                 anchor      = E)
        self.rbyes.pack(side = LEFT, ipadx = self.padWidth)
        self.rbno  = Radiobutton(self.frame, text = "No", 
                                 variable    = self.choice,
                                 value       = "no",  
                                 selectcolor = "SpringGreen",
                                 anchor      = W)
        self.rbno.pack(side = RIGHT, ipadx = self.padWidth)
        self.frame.pack(side = LEFT)

    def unlearnOption(self, newParamInfo):

        self.newParamInfo = newParamInfo
        self.newValue = self.newParamInfo.get(field = "p_filename", native = 0, 
                                              prompt = 0) 
        # Check if boolean is not set
        if (self.newValue == ""):
            self.choice.set("no")
        else:
            self.choice.set(self.newValue)


class StringEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, fieldWidths)

    def makeInputWidget(self):

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT, fill = X, expand = TRUE)
        self.entry.bind('<Return>', self.entrySet)
        self.entry.bind('<Button-3>', self.popupChoices)

    # Add code to handle other "strings"

    def entrySet(self, event):

        pass

    def popupChoices(self, event):
 
        self.menu = Menu(self.entry, tearoff = 0, background = "white",
                         activebackground = "gainsboro")
        self.menu.add_command(label   = "File Browser",
                              command = self.fileBrowser)
        self.menu.add_separator()
        self.menu.add_command(label   = "Clear",
                              command = self.clearEntry)
        self.menu.add_command(label   = "Unlearn",
                              state   = DISABLED,
                              command = self.unlearnEntry)

        # Get the current coordinates of the Entry 
        xcoord = self.entry.winfo_rootx()
        ycoord = self.entry.winfo_rooty()
        # print xcoord, ycoord

        # Display the Menu as a popup as it is not associated with a Button
        self.menu.tk_popup(xcoord, ycoord)


    def fileBrowser(self):

        # *** Invoke a Community Tkinter generic File Dialog FOR NOW ***
        self.fd = filedlg.LoadFileDialog(self.entry, "File Browser", "*")
        if self.fd.Show() != 1:
                    self.fd.DialogCleanup()
                    return
        self.fname = self.fd.GetFileName()
        self.fd.DialogCleanup()
        self.choice.set(self.fname)


    # Clear just this Entry
    def clearEntry(self):

        self.entry.delete(0, END)

    # Unlearn just this Entry
    def unlearnEntry(self):
        pass

class IntEparOption(EparOption):

    # Override base close option 
    #choiceClass = IntVar

    def __init__(self, master, statusBar, paramInfo, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, fieldWidths)

    def makeInputWidget(self):

        # Retain the original parameter value in case of bad entry
        self.previousValue = self.value

        self.min = self.paramInfo.get(field  = "p_minimum", 
                                      native = 0, 
                                      prompt = 0)
        self.max = self.paramInfo.get(field  = "p_maximum", 
                                      native = 0, 
                                      prompt = 0)

        # If not INDEF, convert to an integer.
        if (self.min != "INDEF"):
            self.min = string.atoi(self.min)
        if (self.max != "INDEF"):
            self.max = string.atoi(self.max)

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT)

        # Set up key bindings
        self.entry.bind('<Return>', self.entryCheck)

    # Check the validity of the entry
    def entryCheck(self, event = None):

        # Ensure any INDEF entry is uppercase
        if (self.choice.get() == "indef"):
            self.choice.set("INDEF")
     
        # Check the range if min and/or max are defined
        if ((self.choice.get() != "INDEF") and 
            (self.min != "INDEF" or self.max != "INDEF")):
            try:
                if ((self.min != "INDEF") and 
                    (string.atoi(self.choice.get()) < self.min)):

                    # Reset the entry to the previous (presumably valid) value
                    self.choice.set(self.previousValue)

                    # Set up the error message
                    errorMsg = "Parameter " + `self.name` + ":" 

                    if (self.max != "INDEF"):
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: " + \
                                   `self.min` + " Maximum: " + `self.max`
                    else:
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: " + \
                                   `self.min` + " Maximum: -"
                    self.status.bell()
                    self.status.config(text = errorMsg)

                if ((self.max != "INDEF") and 
                    (string.atoi(self.choice.get()) > self.max)):

                    # Reset the entry to the previous (presumably valid) value
                    self.choice.set(self.previousValue)

                    # Set up the error message
                    errorMsg = "Parameter " + `self.name` + ":" 

                    if (self.min != "INDEF"):
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: " + \
                                   `self.min` + " Maximum: " + `self.max`
                    else:
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: - " + \
                                   " Maximum: " + `self.max`
                    self.status.bell()
                    self.status.config(text = errorMsg)

            except ValueError:
                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                errorMsg = "Parameter " + `self.name` + \
                      ": Input value is the wrong data type."
                self.status.bell()
                self.status.config(text = errorMsg)

        # Make sure the input is not a string
        if (self.choice.get() != "INDEF"):
            try:
                string.atoi(self.choice.get())
            except ValueError:
                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                errorMsg = "Parameter " + `self.name` + \
                      ": Input value is the wrong data type."
                self.status.bell()
                self.status.config(text = errorMsg)


class RealEparOption(EparOption):

    # Override base close option 
    #choiceClass = DoubleVar

    def __init__(self, master, statusBar, paramInfo, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, fieldWidths)

    def makeInputWidget(self):

        # Retain the original parameter value in case of bad entry
        self.previousValue = self.value

        self.min = self.paramInfo.get(field  = "p_minimum", 
                                      native = 0, 
                                      prompt = 0)
        self.max = self.paramInfo.get(field  = "p_maximum", 
                                      native = 0, 
                                      prompt = 0)

        # If not INDEF, convert to a real.
        if (self.min != "INDEF"):
            self.min = string.atof(self.min)
        if (self.max != "INDEF"):
            self.max = string.atof(self.max)

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT)

        # Set up key bindings
        self.entry.bind('<Return>', self.entryCheck)

    # Check the validity of the entry
    def entryCheck(self, event = None):

        # Ensure any INDEF entry is uppercase
        if (self.choice.get() == "indef"):
            self.choice.set("INDEF")

        # Check the range if min and/or max are defined
        if ((self.choice.get() != "INDEF") and 
            (self.min != "INDEF" or self.max != "INDEF")):
            try:
                if ((self.min != "INDEF") and 
                    (string.atof(self.choice.get()) < self.min)):

                    # Reset the entry to the previous (presumably valid) value
                    self.choice.set(self.previousValue)

                    # Set up the error message
                    errorMsg = "Parameter " + `self.name` + ":" 

                    if (self.max != "INDEF"):
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: " + \
                                   `self.min` + " Maximum: " + `self.max`
                    else:
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: " + \
                                   `self.min` + " Maximum: -"
                    self.status.bell()
                    self.status.config(text = errorMsg)

                if ((self.max != "INDEF") and 
                    (string.atof(self.choice.get()) > self.max)):

                    # Reset the entry to the previous (presumably valid) value
                    self.choice.set(self.previousValue)

                    # Set up the error message
                    errorMsg = "Parameter " + `self.name` + ":" 

                    if (self.min != "INDEF"):
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: " + \
                                   `self.min` + " Maximum: " + `self.max`
                    else:
                        errorMsg = errorMsg + \
                                   " Value is out of range.  Minimum: - " + \
                                   " Maximum: " + `self.max`
                    self.status.bell()
                    self.status.config(text = errorMsg)

            except ValueError:
                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                errorMsg = "Parameter " + `self.name` + \
                      ": Input value is the wrong data type."
                self.status.bell()
                self.status.config(text = errorMsg)

        # Make sure the input is not a string
        if (self.choice.get() != "INDEF"):
            try:
                string.atof(self.choice.get())
            except ValueError:
                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                errorMsg = "Parameter " + `self.name` + \
                      ": Input value is the wrong data type."
                self.status.bell()
                self.status.config(text = errorMsg)
 

class PsetEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, fieldWidths)

    def makeInputWidget(self):

        # For a PSET self.value is actually an IrafTask object
        # Need to get the filename to label the button
        fileName = self.value.getFilename()

        # Strip of any leading environment variable indicator and
        # any trailing file extension
        splitfileName  = string.split(fileName, ".")
        splitfileName2 = string.split(splitfileName[0], "$")
        if len(splitfileName2) > 1:
           self.buttonText = splitfileName2[len(splitfileName2) - 1]
        else:
           self.buttonText = splitfileName2[0]

        # Need to adjust the value width so the button is aligned properly
        self.valueWidth = self.valueWidth - 3

        # Generate the button
        self.button = Button(self.master.frame, background = "SlateGray3",
                                 width   = self.valueWidth,
                                 text    = "PSET " + self.buttonText,
                                 relief  = RAISED,           
                                 command = self.childEparDialog)
        self.button.pack(side = LEFT)

    def childEparDialog(self):
        epar.EparDialog(self.buttonText, parent = self.master.frame, 
                        child = "yes", 
                        title = "PSET Parameter Editor") 

    def unlearnOption(self, newParamInfo):

        self.newParamInfo = newParamInfo
        self.newValue = self.newParamInfo.get(field = "p_filename", native = 0, 
                                           prompt = 0) 
        self.choice.set(self.newValue)
