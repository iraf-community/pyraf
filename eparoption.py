"""eparoption.py: module for defining the various parameter display
   options to be used for the parameter editor task.  The widget that is used
   for entering the parameter value is the variant.  Instances should be
   created using the eparOptionFactory function defined at the end of the
   module.

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
import epar

# Constants
MAXLIST  =  15
MAXLINES = 100
XSHIFT   = 110

class EparOption:

    """EparOption base class

    Implementation for a specific parameter type must implement
    the makeInputWidget method and must create an attribute `entry'
    with the base widget created.  The entry widget is used for
    focus setting and automatic scrolling.  doScroll is a callback to
    do the scrolling when tab changes focus.
    """

    # Chosen option
    choiceClass = StringVar

    def __init__(self, master, statusBar, paramInfo, defaultParamInfo, doScroll, fieldWidths):

        # Connect to the information/status Label
        self.status = statusBar

        # Hook to allow scroll when this widget gets focus
        self.doScroll = doScroll
        # Track selection at the last FocusOut event
        self.lastSelection = (0,END)

        # A new Frame is created for each parameter entry
        self.master       = master
        self.master.frame = Frame(self.master)
        self.paramInfo    = paramInfo
        self.defaultParamInfo = defaultParamInfo
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

        # Default is none of items on popup menu are activated
        # These can be changed by the makeInputWidget method to customize
        # behavior for each widget.
        self.browserEnabled = DISABLED
        self.clearEnabled = DISABLED
        self.unlearnEnabled = DISABLED

        # Generate the input widget depending upon the datatype
        self.makeInputWidget()

        self.entry.bind('<FocusOut>', self.focusOut, "+")
        self.entry.bind('<FocusIn>', self.focusIn, "+")

        # Trap keys that leave field and validate entry
        self.entry.bind('<Return>', self.entryCheck, "+")
        self.entry.bind('<Shift-Return>', self.entryCheck, "+")
        self.entry.bind('<Tab>', self.entryCheck, "+")
        self.entry.bind('<Shift-Tab>', self.entryCheck, "+")
        self.entry.bind('<KeyPress-ISO_Left_Tab>', self.entryCheck, "+")
        self.entry.bind('<Up>', self.entryCheck, "+")
        self.entry.bind('<Down>', self.entryCheck, "+")

        # Bind the right button to a popup menu of choices
        self.entry.bind('<Button-3>', self.popupChoices)

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

    def focusOut(self, event=None):
        """Clear selection (if text is selected in this widget)"""
        if self.entryCheck(event) is None:
            # Entry value is OK
            # Save the last selection so it can be restored if we
            # come right back to this widget.  Then clear the selection
            # before moving on.
            entry = self.entry
            try:
                if not entry.selection_present():
                    self.lastSelection = None
                else:
                    self.lastSelection = (entry.index(SEL_FIRST),
                                          entry.index(SEL_LAST))
            except AttributeError:
                pass
            entry.selection_clear()
        else:
            return "break"

    def focusIn(self, event=None):
        """Select all text (if applicable) on taking focus"""
        try:
            # doScroll returns false if the call was ignored because the
            # last call also came from this widget.  That avoids unwanted
            # scrolls and text selection when the focus moves in and out
            # of the window.
            if self.doScroll(event):
                self.entry.selection_range(0, END)
            else:
                # restore selection to what it was on the last FocusOut
                if self.lastSelection:
                    self.entry.selection_range(*self.lastSelection)
        except AttributeError:
            pass

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
            # highlight the text again and terminate processing so
            # focus stays in this widget
            self.focusIn(event)
            return "break"

    def focus_set(self, event=None):
        """Set focus to input widget"""
        self.entry.focus_set()

    # Generate the the input widget as appropriate to the parameter datatype
    def makeInputWidget(self):
        pass

    def popupChoices(self, event=None):
        """Popup right-click menu of special parameter operations

        Relies on browserEnabled, clearEnabled, unlearnEnabled
        instance attributes to determine which items are available.
        """
        # don't bother if all items are disabled
        if NORMAL not in [self.browserEnabled,
                          self.clearEnabled,
                          self.unlearnEnabled]:
            return

        self.menu = Menu(self.entry, tearoff = 0)
        self.menu.add_command(label   = "File Browser",
                              state   = self.browserEnabled,
                              command = self.fileBrowser)
        self.menu.add_separator()
        self.menu.add_command(label   = "Clear",
                              state   = self.clearEnabled,
                              command = self.clearEntry)
        self.menu.add_command(label   = "Unlearn",
                              state   = self.unlearnEnabled,
                              command = self.unlearnValue)

        # Get the current y-coordinate of the Entry
        ycoord = self.entry.winfo_rooty()

        # Get the current x-coordinate of the cursor
        xcoord = self.entry.winfo_pointerx() - XSHIFT

        # Display the Menu as a popup as it is not associated with a Button
        self.menu.tk_popup(xcoord, ycoord)

    def fileBrowser(self):
        """Invoke a Community Tkinter generic File Dialog"""
        self.fd = filedlg.PersistLoadFileDialog(self.entry,
                        "Directory Browser", "*")
        if self.fd.Show() != 1:
            self.fd.DialogCleanup()
            return
        self.fname = self.fd.GetFileName()
        self.fd.DialogCleanup()
        self.choice.set(self.fname)
        # don't select when we go back to widget to reduce risk of
        # accidentally typing over the filename
        self.lastSelection = None

    def clearEntry(self):
        """Clear just this Entry"""
        self.entry.delete(0, END)

    def unlearnValue(self):
        """Unlearn a parameter value by setting it back to its default"""
        defaultValue = self.defaultParamInfo.get(field = "p_filename",
                            native = 0, prompt = 0)
        self.choice.set(defaultValue)


class EnumEparOption(EparOption):

    def makeInputWidget(self):

        self.unlearnEnabled = NORMAL

        # Set the initial value for the button
        self.choice.set(self.value)

        # Need to adjust the value width so the menu button is
        # aligned properly
        self.valueWidth = self.valueWidth - 4

        # Generate the button
        self.entry = Menubutton(self.master.frame,
                                 width  = self.valueWidth,
                                 text   = self.choice.get(),      # label
                                 relief = RAISED,
                                 anchor = W,                      # alignment
                                 textvariable = self.choice,      # var to sync
                                 indicatoron  = 1,
                                 takefocus    = 1,
                                 highlightthickness = 1)

        self.entry.menu = Menu(self.entry, tearoff=0, postcommand=self.postcmd)

        # Generate the dictionary of shortcuts using first letter,
        # second if first not available, etc.
        self.shortcuts = {}
        trylist = self.paramInfo.choice
        underline = {}
        i = 0
        while trylist:
            trylist2 = []
            for option in trylist:
                # shortcuts dictionary is case-insensitive
                letter = option[i:i+1].lower()
                if self.shortcuts.has_key(letter):
                    # will try again with next letter
                    trylist2.append(option)
                elif letter:
                    self.shortcuts[letter] = option
                    self.shortcuts[letter.upper()] = option
                    underline[option] = i
                else:
                    # no letters left, so no shortcut for this item
                    underline[option] = -1
            trylist = trylist2
            i = i+1

        # Generate the menu options with shortcuts underlined
        for option in self.paramInfo.choice:
            self.entry.menu.add_radiobutton(label    = option,
                                             value    = option,
                                             variable = self.choice,
                                             indicatoron = 0,
                                             underline = underline[option])

        # set up a pointer from the menubutton back to the menu
        self.entry['menu'] = self.entry.menu

        self.entry.pack(side = LEFT)

        # shortcut keys jump to items
        for letter in self.shortcuts.keys():
            self.entry.bind('<%s>' % letter, self.keypress)

        # Left button sets focus (as well as popping up menu)
        self.entry.bind('<Button-1>', self.focus_set)

    def keypress(self, event):
        """Allow keys typed in widget to select items"""
        try:
            self.choice.set(self.shortcuts[event.keysym])
        except KeyError:
            # key not found (probably a bug, since we intend to catch
            # only events from shortcut keys, but ignore it anyway)
            pass

    def postcmd(self):
        """Make sure proper entry is activated when menu is posted"""
        value = self.choice.get()
        try:
            index = self.paramInfo.choice.index(value)
            self.entry.menu.activate(index)
        except ValueError:
            # initial null value may not be in list
            pass


class BooleanEparOption(EparOption):

    def makeInputWidget(self):

        self.unlearnEnabled = NORMAL

        # Need to buffer the value width so the radio buttons and
        # the adjoining labels are aligned properly
        self.valueWidth = self.valueWidth + 10
        self.padWidth   = self.valueWidth / 2

        # boolean parameters have 3 values: yes, no & undefined
        # Just display two choices (but variable may initially be
        # undefined)
        self.choice.set(self.value)

        self.entry = Frame(self.master.frame,
                           relief    = FLAT,
                           width     = self.valueWidth,
                           takefocus = 1,
                           highlightthickness = 1)

        self.rbyes = Radiobutton(self.entry, text = "Yes",
                                 variable    = self.choice,
                                 value       = "yes",
                                 anchor      = E,
                                 takefocus   = 0,
                                 underline   = 0)
        self.rbyes.pack(side = LEFT, ipadx = self.padWidth)
        self.rbno  = Radiobutton(self.entry, text = "No",
                                 variable    = self.choice,
                                 value       = "no",
                                 anchor      = W,
                                 takefocus   = 0,
                                 underline   = 0)
        self.rbno.pack(side = RIGHT, ipadx = self.padWidth)
        self.entry.pack(side = LEFT)

        # keyboard accelerators
        # Y/y sets yes, N/n sets no, space toggles selection
        self.entry.bind('<y>', self.set)
        self.entry.bind('<Y>', self.set)
        self.entry.bind('<n>', self.unset)
        self.entry.bind('<N>', self.unset)
        self.entry.bind('<space>', self.toggle)
        # When variable changes, make sure widget gets focus
        self.choice.trace("w", self.trace)

        # Right-click menu is bound to individual widgets too
        self.rbno.bind('<Button-3>', self.popupChoices)
        self.rbyes.bind('<Button-3>', self.popupChoices)

    def trace(self, *args):
        self.entry.focus_set()

    def set(self, event=None):
        """Set value to Yes"""
        self.rbyes.select()

    def unset(self, event=None):
        """Set value to No"""
        self.rbno.select()

    def toggle(self, event=None):
        """Toggle value between Yes and No"""
        if self.choice.get() == "yes":
            self.rbno.select()
        else:
            self.rbyes.select()

class StringEparOption(EparOption):

    def makeInputWidget(self):

        self.browserEnabled = NORMAL
        self.clearEnabled = NORMAL
        self.unlearnEnabled = NORMAL

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT, fill = X, expand = TRUE)


class IntEparOption(EparOption):

    def notNull(self, value):
        return value not in ["", "INDEF"]

    def makeInputWidget(self):

        self.clearEnabled = NORMAL
        self.unlearnEnabled = NORMAL

        # Retain the original parameter value in case of bad entry
        self.previousValue = self.value

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT)

    # Check the validity of the entry
    # Note that doing this using the parameter set method
    # automatically checks max, min, special value (INDEF,
    # parameter indirection), etc.

    def entryCheck(self, event = None):

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
            # highlight the text again and terminate processing so
            # focus stays in this widget
            self.focusIn(event)
            return "break"

class RealEparOption(EparOption):

    def notNull(self, value):
        return value not in ["", "INDEF"]

    def makeInputWidget(self):

        self.clearEnabled = NORMAL
        self.unlearnEnabled = NORMAL

        # Retain the original parameter value in case of bad entry
        self.previousValue = self.value

        self.choice.set(self.value)
        self.entry = Entry(self.master.frame, width = self.valueWidth,
                     textvariable = self.choice)
        self.entry.pack(side = LEFT)


    # Check the validity of the entry
    def entryCheck(self, event = None):

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
            # highlight the text again and terminate processing so
            # focus stays in this widget
            self.focusIn(event)
            return "break"

class PsetEparOption(EparOption):

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


# EparOption values for non-string types
_eparOptionDict = { "b": BooleanEparOption,
                    "r": RealEparOption,
                    "d": RealEparOption,
                    "i": IntEparOption,
                    "pset": PsetEparOption,
                  }

def eparOptionFactory(master, statusBar, param, defaultParam,
                      doScroll, fieldWidths):

    """Return EparOption item of appropriate type for the parameter param"""

    # If there is an enumerated list, regardless of datatype, use
    # the EnumEparOption
    if (param.choice != None):
        eparOption = EnumEparOption
    else:
        # Use String for types not in the dictionary
        eparOption = _eparOptionDict.get(param.type, StringEparOption)
    return eparOption(master, statusBar, param, defaultParam,
                      doScroll, fieldWidths)
