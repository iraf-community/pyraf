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

    def __init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths):

        # Connect to the information/status Label
        self.status = statusBar

        # A new Frame is created for each parameter entry
        self.master       = master
        self.master.frame = Frame(self.master)
        self.paramInfo    = paramInfo
        self.isScrollable = isScrollable
        self.inputWidth   = fieldWidths.get('inputWidth')
        self.valueWidth   = fieldWidths.get('valueWidth')
        self.promptWidth  = fieldWidths.get('promptWidth')

        self.choice = self.choiceClass(self.master.frame)

        self.name  = self.paramInfo.get(field = "p_name", native = 0, 
                     prompt = 0) 
        self.value = self.paramInfo.get(field = "p_filename", native = 0, 
                     prompt = 0) 

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
 
        self.defaultValue = self.defaultParamInfo.get(field = "p_filename", 
                            native = 0, prompt = 0) 
        self.choice.set(self.defaultValue)


    # If using the Tab key to move down the parameter panel, scroll the panel
    # down to ensure the input widget with focus is visible.
    def scrollDown(self, event):

        widgetWithFocus = self.master.frame.focus_get()
        ylocation       = widgetWithFocus.winfo_rooty()
        if (ylocation > SDOWNLIMIT):
            parentToplevel  = self.master.winfo_toplevel()
            parentToplevel.f.canvas.yview_scroll(1, "units") 


    # Check the validity of the entry
    def entryCheck(self, event = None):
        pass


    # Generate the the input widget as appropriate to the parameter datatype
    def makeInputWidget(self):
        pass


    # Method called when the UNLEARN action button is invoked to
    # unlearn the values of all the task parameters.
    def unlearnOption(self, newParamInfo):

        self.newParamInfo = newParamInfo

        # Clear the Entry widget and obtain the default value
        #self.entry.delete(0, END)

        self.newValue = self.newParamInfo.get(field = "p_filename", native = 0, 
                                              prompt = 0) 
        self.choice.set(self.newValue)


class EnumEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, defaultParamInfo, isScrollable, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths)

        self.defaultParamInfo = defaultParamInfo

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

        self.button.menu = Menu(self.button,  
                                tearoff = 0,
                                background = "WhiteSmoke",
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

        # Bind the button to a popup menu of choices
        self.button.bind('<Button-3>', self.popupChoices)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.button.bind('<Tab>', self.scrollDown, "+")

    def popupChoices(self, event):
 
        self.menu = Menu(self.button, tearoff = 0, background = "WhiteSmoke",
                         activebackground = "gainsboro")
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

    # Override base close option 
    choiceClass = BooleanVar

    def __init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths)

    def makeInputWidget(self):

        # Need to buffer the value width so the radio buttons and
        # the adjoining labels are aligned properly
        self.valueWidth = self.valueWidth + 10
        self.padWidth   = self.valueWidth / 2

        # If no default value, self.value == ""
        # That's OK, just leave it with no choice
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
                                 takefocus   = 0,
                                 selectcolor = "black")
        self.rbyes.pack(side = LEFT, ipadx = self.padWidth)
        self.rbno  = Radiobutton(self.frame, text = "No", 
                                 variable    = self.choice,
                                 value       = "no",  
                                 anchor      = W,
                                 takefocus   = 0,
                                 selectcolor = "black")
        self.rbno.pack(side = RIGHT, ipadx = self.padWidth)
        self.frame.pack(side = LEFT)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.frame.bind('<Tab>', self.scrollDown, "+")

    # Method called with the "unlearn" menu option is chosen from the 
    # popup menu.  Used to unlearn a single parameter value.
    def unlearnValue(self):
        pass



#XXX For string parameters, we currently lose the information that
#XXX a parameter is undefined.  The initialization gets the string
#XXX value of the parameter, which is "" for an undefined value.
#XXX But "" is also a legal string.  Somehow need to preserve the
#XXX info that a value was None going in.
#XXX Possible approaches -- store values in native format instead of
#XXX as strings; do a special test when initializing strings to
#XXX see if old value was None.

class StringEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, defaultParamInfo, isScrollable, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths)

        self.defaultParamInfo = defaultParamInfo

    def makeInputWidget(self):

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     background   = "WhiteSmoke",
                     textvariable = self.choice)
        self.entry.pack(side = LEFT, fill = X, expand = TRUE)

        # Bind the entry to a popup menu of choices
        self.entry.bind('<Button-3>', self.popupChoices)

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.entry.bind('<Tab>', self.scrollDown, "+")


    def popupChoices(self, event):
 
        self.menu = Menu(self.entry, tearoff = 0, background = "WhiteSmoke",
                         activebackground = "gainsboro")
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



class IntEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, defaultParamInfo, isScrollable, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths)

        self.defaultParamInfo = defaultParamInfo

    def notNull(self, value):
        return value not in ["", "INDEF"]
        #XXX could also check for value[:1] == ')' here, which
        #XXX indicates parameter indirection?  That check
        #XXX should be done somewhere, at any rate

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
        if self.notNull(self.min):
            self.min = int(self.min)
        if self.notNull(self.max):
            self.max = int(self.max)

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     background   = "WhiteSmoke",
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
 
        self.menu = Menu(self.entry, tearoff = 0, background = "WhiteSmoke",
                         activebackground = "gainsboro")
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
    def entryCheck(self, event = None):

        #XXX better approach here would be to use the checkValue or
        #XXX checkOneValue methods of the paramInfo object
        #XXX I should clean up my error messages to match these first

        # Ensure any INDEF entry is uppercase
        if (self.choice.get() == "indef"):
            self.choice.set("INDEF")

        # Make sure the input is legal
        value = self.choice.get()
        if not self.notNull(value):
            return
        else:
            try:
                value = int(value)
            except ValueError:
                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)
                errorMsg = "Parameter " + `self.name` + \
                      ": Input value is the wrong data type."
                self.status.bell()
                self.status.config(text = errorMsg)
                return

        # Check the range if min and/or max are defined
        if self.notNull(self.min) or self.notNull(self.max):
            if self.notNull(self.min) and (value < self.min):

                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                # Set up the error message
                errorMsg = "Parameter " + `self.name` + ":" 

                if self.notNull(self.max):
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: " + \
                               `self.min` + " Maximum: " + `self.max`
                else:
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: " + \
                               `self.min` + " Maximum: -"
                self.status.bell()
                self.status.config(text = errorMsg)
                return

            if self.notNull(self.max) and (value > self.max):

                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                # Set up the error message
                errorMsg = "Parameter " + `self.name` + ":" 

                if self.notNull(self.min):
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: " + \
                               `self.min` + " Maximum: " + `self.max`
                else:
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: - " + \
                               " Maximum: " + `self.max`
                self.status.bell()
                self.status.config(text = errorMsg)


class RealEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, defaultParamInfo, isScrollable, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths)

        self.defaultParamInfo = defaultParamInfo

    def notNull(self, value):
        return value not in ["", "INDEF"]
        #XXX could also check for value[:1] == ')' here, which
        #XXX indicates parameter indirection?  That check
        #XXX should be done somewhere, at any rate

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
        if self.notNull(self.min):
            self.min = float(self.min)
        if self.notNull(self.max):
            self.max = float(self.max)

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     background   = "WhiteSmoke",
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
 
        self.menu = Menu(self.entry, tearoff = 0, background = "WhiteSmoke",
                         activebackground = "gainsboro")
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
    def entryCheck(self, event = None):

        #XXX better approach here would be to use the checkValue or
        #XXX checkOneValue methods of the paramInfo object
        #XXX It handles some other formats too (e.g. sexagesimal hh:mm:ss)
        #XXX I should clean up my error messages to match these first

        # Ensure any INDEF entry is uppercase
        if (self.choice.get() == "indef"):
            self.choice.set("INDEF")

        # Make sure the input is legal
        value = self.choice.get()
        if not self.notNull(value):
            return
        else:
            try:
                value = float(value)
            except ValueError:
                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)
                errorMsg = "Parameter " + `self.name` + \
                      ": Input value is the wrong data type."
                self.status.bell()
                self.status.config(text = errorMsg)
                return

        # Check the range if min and/or max are defined
        if self.notNull(self.min) or self.notNull(self.max):
            if self.notNull(self.min) and (value < self.min):

                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                # Set up the error message
                errorMsg = "Parameter " + `self.name` + ":" 

                if self.notNull(self.max):
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: " + \
                               `self.min` + " Maximum: " + `self.max`
                else:
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: " + \
                               `self.min` + " Maximum: -"
                self.status.bell()
                self.status.config(text = errorMsg)
                return

            if self.notNull(self.max) and (value > self.max):

                # Reset the entry to the previous (presumably valid) value
                self.choice.set(self.previousValue)

                # Set up the error message
                errorMsg = "Parameter " + `self.name` + ":" 

                if self.notNull(self.min):
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: " + \
                               `self.min` + " Maximum: " + `self.max`
                else:
                    errorMsg = errorMsg + \
                               " Value is out of range.  Minimum: - " + \
                               " Maximum: " + `self.max`
                self.status.bell()
                self.status.config(text = errorMsg)


class PsetEparOption(EparOption):

    def __init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths):
        EparOption.__init__(self, master, statusBar, paramInfo, isScrollable, fieldWidths)

    def makeInputWidget(self):

        # For a PSET self.value is actually an IrafTask object
        # Need to get the filename to label the button
        #XXX No -- just use name to label button here too?
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

        if (self.isScrollable == "yes"):
            # Piggyback additional functionality to the Tab key
            self.button.bind('<Tab>', self.scrollDown, "+")

    def childEparDialog(self):
        
        # Get a reference to the parent TopLevel
        parentToplevel  = self.master.winfo_toplevel()
        childPsetHandle = epar.EparDialog(self.buttonText, 
                                          parent  = self.master.frame, 
                                          isChild = "yes", 
                                          title   = "PSET Parameter Editor") 
        parentToplevel.childList.append(childPsetHandle)

    # Method called with the "unlearn" menu option is chosen from the 
    # popup menu.  Used to unlearn a single parameter value.
    def unlearnValue(self):
        pass
