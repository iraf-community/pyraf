#XXX some rlw notes

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
XSHIFT   = 110

# This value is dependent upon the yscroll increment.  This is a test
# implementation.
SDOWNLIMIT = 680

class EparOption:

    # Chosen option 
    choiceClass = StringVar

    def __init__(self, master, statusBar, paramInfo, defaultParamInfo, isScrollable, fieldWidths):

        # Connect to the information/status Label
        self.status = statusBar

        # A new Frame is created for each parameter entry
        self.master       = master
        self.master.frame = Frame(self.master)
        self.paramInfo    = paramInfo
        self.defaultParamInfo = defaultParamInfo
        self.isScrollable = isScrollable
        self.inputWidth   = fieldWidths.get('inputWidth')
        self.valueWidth   = fieldWidths.get('valueWidth')
        self.promptWidth  = fieldWidths.get('promptWidth')

        self.choice = self.choiceClass(self.master.frame)

        self.name  = self.paramInfo.name
        self.value = self.paramInfo.get(field = "p_filename", native = 0, 
                     prompt = 0) 
        self.previousValue = self.value

        # Generate the input label
        if (self.paramInfo.get(field = "p_mode") == "h"):
            self.inputLabel = Label(self.master.frame, anchor = W, 
                                    text  = "(" + self.name + ")", 
                                    width = self.inputWidth)
        else:
            self.inputLabel = Label(self.master.frame, anchor = W, 
                                    text  = self.name, 
                                    width = self.inputWidth)
        self.inputLabel.pack(side = LEFT, fill = X, expand = TRUE)

        # Get the prompt string and determine if special handling is needed
        self.prompt = self.paramInfo.get(field = "p_prompt", native = 0, 
                      prompt = 0) 

        # Check the prompt to determine how many lines of valid text exist
        lines       = string.split(self.prompt, "\n")
        nlines      = len(lines)
        promptLines = " " + lines[0]
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
        self.master.frame.pack(side = TOP, ipady = 1)

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

    # Method called with the "unlearn" menu option is chosen from the 
    # popup menu.  Used to unlearn a single parameter value.
    def unlearnValue(self):
 
        defaultValue = self.defaultParamInfo.get(field = "p_filename", 
                            native = 0, prompt = 0) 
        self.choice.set(defaultValue)


    # If using the Tab key to move down the parameter panel, scroll the panel
    # down to ensure the input widget with focus is visible.
    def scrollDown(self, event):

        widgetWithFocus = self.master.frame.focus_get()
        ylocation       = widgetWithFocus.winfo_rooty()
        if (ylocation > SDOWNLIMIT):
            parentToplevel  = self.master.winfo_toplevel()
            parentToplevel.f.canvas.yview_scroll(1, "units") 


    # Check the validity of the entry
    # If valid, changes the value of the parameter (note that this
    # is a copy, so change is not permanent until save)
    # Parameter change also sets the isChanged flag.
    def entryCheck(self, event = None):

        value = self.choice.get()
        try:
            if value != self.previousValue:
                self.paramInfo.set(value)
            return None
        except ValueError, exceptionInfo:
            # Reset the entry to the previous (presumably valid) value
            self.choice.set(self.previousValue)
            errorMsg = str(exceptionInfo)
            self.status.bell()
            if (event != None):
                self.status.config(text = errorMsg)
            return [self.name, value, self.previousValue]


    # Generate the the input widget as appropriate to the parameter datatype
    def makeInputWidget(self):
        pass


class EnumEparOption(EparOption):

    def makeInputWidget(self):

        # Set the initial value for the button
        self.choice.set(self.value)

        # Need to adjust the value width so the menu button is the
        # aligned properly
        self.valueWidth = self.valueWidth - 4

        # Generate the button
        self.button = Menubutton(self.master.frame, 
                                 width  = self.valueWidth,
                                 text   = self.choice.get(),      # label
                                 relief = RAISED,           
                                 anchor = W,                      # alignment
                                 textvariable = self.choice,      # var to sync 
                                 indicatoron  = 1,
                                 takefocus    = 1,
                                 highlightthickness = 1)

        self.button.menu = Menu(self.button, tearoff = 0)

        # Generate the menu options
        for option in (self.paramInfo.choice):
            self.button.menu.add_radiobutton(label    = option,
                                             value    = option, 
                                             variable = self.choice, 
                                             indicatoron = 0)

        # set up a pointer from the menubutton back to the menu
        self.button['menu'] = self.button.menu

        self.button.pack(side = LEFT)

        # Bind the button to a popup menu of choices
        self.button.bind('<Button-3>', self.popupChoices)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.button.bind('<Tab>', self.scrollDown, "+")

    def popupChoices(self, event):
 
        self.menu = Menu(self.button, tearoff = 0)
        self.menu.add_command(label   = "File Browser",
                              state   = DISABLED)
        self.menu.add_separator()
        self.menu.add_command(label   = "Clear",
                              state   = DISABLED)
        self.menu.add_command(label   = "Unlearn",
                             command = self.unlearnValue)

        # Get the current y-coordinate of the Entry 
        ycoord = self.button.winfo_rooty()

        # Get the current x-coordinate of the cursor
        xcoord = self.button.winfo_pointerx() - XSHIFT

        # Display the Menu as a popup as it is not associated with a Button
        self.menu.tk_popup(xcoord, ycoord)



class BooleanEparOption(EparOption):

    def makeInputWidget(self):

        # Need to buffer the value width so the radio buttons and
        # the adjoining labels are aligned properly
        self.valueWidth = self.valueWidth + 10
        self.padWidth   = self.valueWidth / 2

        # boolean parameters have 3 values: yes, no & undefined
        # Just display two choices (but variable may initially be
        # undefined)
        self.choice.set(self.value)

        self.frame = Frame(self.master.frame, 
                           relief    = FLAT, 
                           width     = self.valueWidth,
                           takefocus = 1,
                           highlightthickness = 1)

        self.rbyes = Radiobutton(self.frame, text = "Yes",
                                 variable    = self.choice,
                                 value       = "yes",  
                                 anchor      = E,
                                 takefocus   = 0)
        self.rbyes.pack(side = LEFT, ipadx = self.padWidth)
        self.rbno  = Radiobutton(self.frame, text = "No", 
                                 variable    = self.choice,
                                 value       = "no",  
                                 anchor      = W,
                                 takefocus   = 0)
        self.rbno.pack(side = RIGHT, ipadx = self.padWidth)
        self.frame.pack(side = LEFT)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.frame.bind('<Tab>', self.scrollDown, "+")


class StringEparOption(EparOption):

    def makeInputWidget(self):

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT, fill = X, expand = TRUE)

        # Bind the entry to a popup menu of choices
        self.entry.bind('<Button-3>', self.popupChoices)

        # Set up key bindings
        self.entry.bind('<Return>', self.entryCheck)
        self.entry.bind('<Tab>', self.entryCheck, "+")

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.entry.bind('<Tab>', self.scrollDown, "+")


    def popupChoices(self, event):
 
        self.menu = Menu(self.entry, tearoff = 0)
        self.menu.add_command(label   = "File Browser",
                              command = self.fileBrowser)
        self.menu.add_separator()
        self.menu.add_command(label   = "Clear",
                              command = self.clearEntry)
        self.menu.add_command(label   = "Unlearn",
                              command = self.unlearnValue)

        # Get the current y-coordinate of the Entry 
        ycoord = self.entry.winfo_rooty()

        # Get the current x-coordinate of the cursor
        xcoord = self.entry.winfo_pointerx() - XSHIFT

        # Display the Menu as a popup as it is not associated with a Button
        self.menu.tk_popup(xcoord, ycoord)


    def fileBrowser(self):

        # *** Invoke a Community Tkinter generic File Dialog FOR NOW ***
        self.fd = filedlg.PersistLoadFileDialog(self.entry, "Directory Browser", "*")
        if self.fd.Show() != 1:
                    self.fd.DialogCleanup()
                    return
        self.fname = self.fd.GetFileName()
        self.fd.DialogCleanup()
        self.choice.set(self.fname)


    # Clear just this Entry
    def clearEntry(self):

        self.entry.delete(0, END)



class IntEparOption(EparOption):

    def notNull(self, value):
        return value not in ["", "INDEF"]

    def makeInputWidget(self):

        # Retain the original parameter value in case of bad entry
        self.previousValue = self.value

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT)

        # Set up key bindings
        self.entry.bind('<Return>', self.entryCheck)
        self.entry.bind('<Tab>', self.entryCheck, "+")

        # Bind the button to a popup menu of choices
        self.entry.bind('<Button-3>', self.popupChoices)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.entry.bind('<Tab>', self.scrollDown, "+")


    def popupChoices(self, event):
 
        self.menu = Menu(self.entry, tearoff = 0)
        self.menu.add_command(label   = "File Browser",
                              state   = DISABLED)
        self.menu.add_separator()
        self.menu.add_command(label   = "Clear",
                              command = self.clearEntry)
        self.menu.add_command(label   = "Unlearn",
                             command = self.unlearnValue)

        # Get the current y-coordinate of the Entry 
        ycoord = self.entry.winfo_rooty()

        # Get the current x-coordinate of the cursor
        xcoord = self.entry.winfo_pointerx() - XSHIFT

        # Display the Menu as a popup as it is not associated with a Button
        self.menu.tk_popup(xcoord, ycoord)

    # Clear just this Entry
    def clearEntry(self):

        self.entry.delete(0, END)


    # Check the validity of the entry
    # Note that doing this using the parameter set method
    # automatically checks max, min, special value (INDEF,
    # parameter indirection), etc.

    def entryCheck(self, event = None, *args):

        # Ensure any INDEF entry is uppercase
        if (self.choice.get() == "indef"):
            self.choice.set("INDEF")

        # Make sure the input is legal
        value = self.choice.get()
        try:
            if value != self.previousValue:
                self.paramInfo.set(value)
            return None
        except ValueError, e:
            # Reset the entry to the previous (presumably valid) value
            self.choice.set(self.previousValue)
            errorMsg = str(e)
            self.status.bell()
            if (event != None):
                self.status.config(text = errorMsg)
            return [self.name, value, self.previousValue]

class RealEparOption(EparOption):

    def notNull(self, value):
        return value not in ["", "INDEF"]

    def makeInputWidget(self):

        # Retain the original parameter value in case of bad entry
        self.previousValue = self.value

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT)

        # Set up key bindings
        self.entry.bind('<Return>', self.entryCheck)
        self.entry.bind('<Tab>', self.entryCheck, "+")

        # Bind the button to a popup menu of choices
        self.entry.bind('<Button-3>', self.popupChoices)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.entry.bind('<Tab>', self.scrollDown, "+")


    def popupChoices(self, event):
 
        self.menu = Menu(self.entry, tearoff = 0)
        self.menu.add_command(label   = "File Browser",
                              state   = DISABLED)
        self.menu.add_separator()
        self.menu.add_command(label   = "Clear",
                              command = self.clearEntry)
        self.menu.add_command(label   = "Unlearn",
                             command = self.unlearnValue)

        # Get the current y-coordinate of the Entry 
        ycoord = self.entry.winfo_rooty()

        # Get the current x-coordinate of the cursor
        xcoord = self.entry.winfo_pointerx() - XSHIFT

        # Display the Menu as a popup as it is not associated with a Button
        self.menu.tk_popup(xcoord, ycoord)

    # Clear just this Entry
    def clearEntry(self):

        self.entry.delete(0, END)


    # Check the validity of the entry
    def entryCheck(self, event = None, *args):

        # Ensure any INDEF entry is uppercase
        if (self.choice.get() == "indef"):
            self.choice.set("INDEF")

        # Make sure the input is legal
        value = self.choice.get()
        try:
            if value != self.previousValue:
                self.paramInfo.set(value)
            return None
        except ValueError, e:
            # Reset the entry to the previous (presumably valid) value
            self.choice.set(self.previousValue)
            errorMsg = str(e)
            self.status.bell()
            if (event != None):
                self.status.config(text = errorMsg)
            return [self.name, value, self.previousValue]


class PsetEparOption(EparOption):

    def makeInputWidget(self):

        # For a PSET self.value is actually an IrafTask object
        # Use task name to label button
        self.buttonText = self.value.getName()

        # Need to adjust the value width so the button is aligned properly
        self.valueWidth = self.valueWidth - 3

        # Generate the button
        self.psetButton = Button(self.master.frame,
                                 width   = self.valueWidth,
                                 text    = "PSET " + self.buttonText,
                                 relief  = RAISED,           
                                 command = self.childEparDialog)
        self.psetButton.pack(side = LEFT)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.psetButton.bind('<Tab>', self.scrollDown, "+")

    def childEparDialog(self):
        
        # Get a reference to the parent TopLevel
        parentToplevel  = self.master.winfo_toplevel()

        # Don't create multiple windows for the same task
        name = self.value.getName()
        for child in parentToplevel.childList:
            if child.taskName == name:
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
