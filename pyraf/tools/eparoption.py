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
import sys
import string

from . import capable

if capable.OF_GRAPHICS:
    from tkinter import *
    from tkinter.filedialog import askdirectory, askopenfilename
else:
    StringVar = None

# Are we using X? (see description of logic in pyraf's wutil.py)
USING_X = True
if sys.platform == 'darwin':
    junk = ",".join(sys.path)
    USING_X = junk.lower().find('/pyobjc') < 0
    del junk

# Constants
MAXLIST  =  15
MAXLINES = 100
XSHIFT   = 110
DSCRPTN_FLAG = ' (***)'


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

    def __init__(self, master, statusBar, paramInfo, defaultParamInfo,
                 doScroll, fieldWidths, defaultsVerb, bg,
                 indent=False, helpCallbackObj=None, mainGuiObj=None):

        # Connect to the information/status Label
        self.status = statusBar

        # Hook to allow scroll when this widget gets focus
        self.doScroll = doScroll
        # Track selection at the last FocusOut event
        self.lastSelection = (0,END)

        # A new Frame is created for each parameter entry
        self.master       = master
        self.bkgColor     = bg
        self.master_frame = Frame(self.master, bg=self.bkgColor)
        self.paramInfo    = paramInfo
        self.defaultParamInfo = defaultParamInfo
        self.defaultsVerb = defaultsVerb
        self.inputWidth   = fieldWidths.get('inputWidth')
        self.valueWidth   = fieldWidths.get('valueWidth')
        self.promptWidth  = fieldWidths.get('promptWidth')

        self.choice = self.choiceClass(self.master_frame)
        self.name = self.paramInfo.name
        self.value = self.paramInfo.get(field = "p_filename", native = 0,
                                        prompt = 0)
        self.previousValue = self.value
        self._editedCallbackObj = None
        self._helpCallbackObj = helpCallbackObj
        self._mainGuiObj = mainGuiObj
        self._lastWidgetEditedVal = None
        self._flagNonDefaultVals = False
        self._flaggedColor = "red"

        # DISABLE any indent for now - not sure why but this causes odd text
        # field sizes in other (unrelated and unindented) parameters...  Maybe
        # because it messes with the total width of the window...
        if 0 and indent:
            self.spacer = Label(self.master_frame, anchor=W, takefocus=0,
                                text="", width=3, bg=self.bkgColor)
            self.spacer.pack(side=LEFT, fill=X, expand=TRUE)

        # Generate the input label
        if self.paramInfo.get(field = "p_mode") == "h":
            self.inputLabel = Label(self.master_frame, anchor = W,
                                    text  = "("+self.getShowName()+")",
                                    width = self.inputWidth, bg=self.bkgColor)
        else:
            self.inputLabel = Label(self.master_frame, anchor = W,
                                    text  = self.getShowName(),
                                    width = self.inputWidth, bg=self.bkgColor)
        self.inputLabel.pack(side = LEFT, fill = X, expand = TRUE)

        # Get the prompt string and determine if special handling is needed
        # Use the prompt/description from the default version, in case they
        # have edited theirs - this is not editable - see ticket #803
        self.prompt = self.defaultParamInfo.get(field="p_prompt", native=0,
                                                prompt=0)

        # Check the prompt to determine how many lines of valid text exist
        lines       = self.prompt.split("\n")
        nlines      = len(lines)
        promptLines = " " + lines[0]
        infoLines   = ""
        blankLineNo = MAXLINES
        if (nlines > 1):
            # Keep all the lines of text before the blank line for the prompt
            for i in range(1, nlines):
                ntokens = lines[i].split()
                if ntokens != []:
                    promptLines = "\n".join([promptLines, lines[i]])
                else:
                    blankLineNo = i
                    break
        self._flagged = False
        if promptLines.endswith(DSCRPTN_FLAG):
            promptLines = promptLines[:-len(DSCRPTN_FLAG)]
            self._flagged = True
        fgColor = "black"
        # turn off this red coloring for the DSCRPTN_FLAG - see #803
#       if self._flagged: fgColor = "red"

        # Generate the prompt label
        self.promptLabel = Label(self.master_frame, anchor=W, fg=fgColor,
                                 text=promptLines, width=self.promptWidth,
                                 bg=self.bkgColor)
        self.promptLabel.pack(side=RIGHT, fill=X, expand=TRUE)

        # Settings for subclasses to override in the makeInputWidget method
        self.isSelectable = True # ie widget has text (num or str) to select

        # Default is none of items on popup menu are activated
        # These can be changed by the makeInputWidget method to customize
        # behavior for each widget.
        self.browserEnabled = DISABLED
        self.clearEnabled = DISABLED
        self.unlearnEnabled = DISABLED
        self.helpEnabled = DISABLED
        if self._helpCallbackObj is not None:
            self.helpEnabled = NORMAL

        # Generate the input widget depending upon the datatype
        self.makeInputWidget()
#       print(self.name, self.__class__) # DBG line

        self.entry.bind('<FocusOut>', self.focusOut, "+")
        self.entry.bind('<FocusIn>', self.focusIn, "+")

        # Trap keys that leave field and validate entry
        self.entry.bind('<Return>', self.entryCheck, "+")
        self.entry.bind('<Shift-Return>', self.entryCheck, "+")
        self.entry.bind('<Tab>', self.entryCheck, "+")
        self.entry.bind('<Shift-Tab>', self.entryCheck, "+")
        self.entry.bind('<Up>', self.entryCheck, "+")
        self.entry.bind('<Down>', self.entryCheck, "+")
        try:
            # special shift-tab binding needed for (some? all?) linux systems
            self.entry.bind('<KeyPress-ISO_Left_Tab>', self.entryCheck, "+")
        except TclError:
            # Ignore exception here, the binding can't be relevant
            # if ISO_Left_Tab is unknown.
            pass

        # Bind the right button to a popup menu of choices
        if USING_X:
            self.entry.bind('<Button-3>', self.popupChoices)
        else:
            self.entry.bind('<Button-2>', self.popupChoices)

        # Pack the parameter entry Frame
        self.master_frame.pack(side=TOP, fill=X, ipady=1)

        # If there is more text associated with this entry, join all the
        # lines of text with the blank line.  This is the "special" text
        # information.
        if (blankLineNo < (nlines - 1)):

            # Put the text after the blank line into its own Frame
            self.master.infoText = Frame(self.master)

            for j in range(blankLineNo + 1, nlines):
                ntokens = lines[j].split()
                if ntokens != []:
                    infoLines = "\n".join([infoLines, lines[j]])
                else:
                    break

            # Assign the informational text to the label and pack
            self.master.infoText.label = Label(self.master.infoText,
                                               text = infoLines,
                                               anchor = W,
                                               bg = self.bkgColor)
            self.master.infoText.label.pack(side = LEFT)
            self.master.infoText.pack(side = TOP, anchor = W)

    def setFlaggedColor(self, colorstr):
        self._flaggedColor = colorstr

    def setIsFlagging(self, isFlagging, redrawImmediately):
        self._flagNonDefaultVals = isFlagging
        if redrawImmediately:
            if self._flagNonDefaultVals:
                curVal = self.choice.get()
            else: # otheriwse we don't care; use None; is ok and faster
                curVal = None
            self.flagThisPar(curVal, True)

    def getShowName(self):
        """ Return the name to be shown in the GUI for this par/option. """
        return self.name

    def extraBindingsForSelectableText(self):
        """ Collect in 1 place the bindings needed for watchTextSelection() """
        # See notes in watchTextSelection
        self.entry.bind('<FocusIn>', self.watchTextSelection, "+")
        self.entry.bind('<ButtonRelease-1>', self.watchTextSelection, "+")
        self.entry.bind('<B1-Motion>', self.watchTextSelection, "+")
        self.entry.bind('<Shift_L>', self.watchTextSelection, "+")
        self.entry.bind('<Left>', self.watchTextSelection, "+")
        self.entry.bind('<Right>', self.watchTextSelection, "+")

    def convertToNative(self, aVal):
        """ The basic type is natively a string. """
        return None if aVal is None else str(aVal)

    def focusOut(self, event=None):
        """Clear selection (if text is selected in this widget)"""
        # do nothing if this isn't a text-enabled widget
        if not self.isSelectable:
            return
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
            if USING_X and sys.platform == 'darwin':
                pass # do nothing here - we need it left selected for cut/paste
            else:
                entry.selection_clear()
        else:
            return "break"

    def watchTextSelection(self, event=None):
        """ Callback used to see if there is a new text selection. In certain
        cases we manually add the text to the clipboard (though on most
        platforms the correct behavior happens automatically). """
        # Note that this isn't perfect - it is a key click behind when
        # selections are made via shift-arrow.  If this becomes important, it
        # can likely be fixed with after().
        if self.entry.selection_present(): # entry must be text entry type
            i1 = self.entry.index(SEL_FIRST)
            i2 = self.entry.index(SEL_LAST)
            if i1 >= 0 and i2 >= 0 and i2 > i1:
                sel = self.entry.get()[i1:i2]
                # Add to clipboard on platforms where necessary.
                print('selected: "'+sel+'"')
#               The following is unneeded if the selected text stays selected
#               when focus is lost or another app is bought to the forground.
#               if sel and USING_X and sys.platform == 'darwin':
#                   clipboard_helper.put(sel, 'PRIMARY')

    def focusIn(self, event=None):
        """Select all text (if applicable) on taking focus"""
        try:
            # doScroll returns false if the call was ignored because the
            # last call also came from this widget.  That avoids unwanted
            # scrolls and text selection when the focus moves in and out
            # of the window.
            if self.doScroll(event):
                self.entry.selection_range(0, END) # select all text in widget
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
    def entryCheck(self, event=None, repair=True):

        # Make sure the input is legal
        value = self.choice.get()
        try:
            if value != self.previousValue:
                # THIS will likely get into IrafPar's _coerceOneValue()
                self.paramInfo.set(value)
            # fire any applicable triggers, whether value has changed or not
            self.widgetEdited(action='entry')
            return None
        except ValueError as exceptionInfo:
            # Reset the entry to the previous (presumably valid) value
            if repair:
                self.choice.set(self.previousValue)
                self.status.bell()
            errorMsg = str(exceptionInfo)
            if event is not None:
                self.status.config(text = errorMsg)
            # highlight the text again and terminate processing so
            # focus stays in this widget
            self.focusIn(event)
            return "break"


    def widgetEdited(self, event=None, val=None, action='entry', skipDups=True):
        """ A general method for firing any applicable triggers when
            a value has been set.  This is meant to be easily callable from any
            part of this class (or its subclasses), so that it can be called
            as soon as need be (immed. on click?).  This is smart enough to
            be called multiple times, itself handling the removal of any/all
            duplicate successive calls (unless skipDups is False). If val is
            None, it will use the GUI entry's current value via choice.get().
            See teal.py for a description of action.
        """

        # be as lightweight as possible if obj doesn't care about this stuff
        if not self._editedCallbackObj and not self._flagNonDefaultVals:
            return

        # get the current value
        curVal = val # take this first, if it is given
        if curVal is None:
            curVal = self.choice.get()

        # do any flagging
        self.flagThisPar(curVal, False)

        # see if this is a duplicate successive call for the same value
        if skipDups and curVal==self._lastWidgetEditedVal: return

        # pull trigger
        if not self._editedCallbackObj: return
        self._editedCallbackObj.edited(self.paramInfo.scope,
                                       self.paramInfo.name,
                                       self.previousValue, curVal,
                                       action)
        # for our duplicate checker
        self._lastWidgetEditedVal = curVal


    def focus_set(self, event=None):
        """Set focus to input widget"""
        self.entry.focus_set()


    # Generate the the input widget as appropriate to the parameter datatype
    def makeInputWidget(self):
        pass

    def popupChoices(self, event=None):
        """Popup right-click menu of special parameter operations

        Relies on browserEnabled, clearEnabled, unlearnEnabled, helpEnabled
        instance attributes to determine which items are available.
        """
        # don't bother if all items are disabled
        if NORMAL not in (self.browserEnabled, self.clearEnabled,
                          self.unlearnEnabled, self.helpEnabled):
            return

        self.menu = Menu(self.entry, tearoff = 0)
        if self.browserEnabled != DISABLED:
            # Handle file and directory in different functions (tkFileDialog)
            if capable.OF_TKFD_IN_EPAR:
                self.menu.add_command(label   = "File Browser",
                                      state   = self.browserEnabled,
                                      command = self.fileBrowser)
                self.menu.add_command(label   = "Directory Browser",
                                      state   = self.browserEnabled,
                                      command = self.dirBrowser)
            # Handle file and directory in the same function (filedlg)
            else:
                self.menu.add_command(label   = "File/Directory Browser",
                                      state   = self.browserEnabled,
                                      command = self.fileBrowser)
            self.menu.add_separator()
        self.menu.add_command(label   = "Clear",
                              state   = self.clearEnabled,
                              command = self.clearEntry)
        self.menu.add_command(label   = self.defaultsVerb,
                              state   = self.unlearnEnabled,
                              command = self.unlearnValue)
        self.menu.add_command(label   = 'Help',
                              state   = self.helpEnabled,
                              command = self.helpOnParam)

        # Get the current y-coordinate of the Entry
        ycoord = self.entry.winfo_rooty()

        # Get the current x-coordinate of the cursor
        xcoord = self.entry.winfo_pointerx() - XSHIFT

        # Display the Menu as a popup as it is not associated with a Button
        self.menu.tk_popup(xcoord, ycoord)

    def fileBrowser(self):
        """Invoke a tkinter file dialog"""
        if capable.OF_TKFD_IN_EPAR:
           fname = askopenfilename(parent=self.entry, title="Select File")
        else:
            from . import filedlg
            self.fd = filedlg.PersistLoadFileDialog(self.entry,
                              "Select File", "*")
            if self.fd.Show() != 1:
                self.fd.DialogCleanup()
                return
            fname = self.fd.GetFileName()
            self.fd.DialogCleanup()
        if not fname: return # canceled

        self.choice.set(fname)
        # don't select when we go back to widget to reduce risk of
        # accidentally typing over the filename
        self.lastSelection = None

    def dirBrowser(self):
        """Invoke a tkinter directory dialog"""
        if capable.OF_TKFD_IN_EPAR:
            fname = askdirectory(parent=self.entry, title="Select Directory")
        else:
            raise NotImplementedError('Fix popupChoices() logic.')

        if not fname:
            return # canceled

        self.choice.set(fname)
        # don't select when we go back to widget to reduce risk of
        # accidentally typing over the filename
        self.lastSelection = None

    def clearEntry(self):
        """Clear just this Entry"""
        self.entry.delete(0, END)

    def forceValue(self, newVal, noteEdited=False):
        """Force-set a parameter entry to the given value"""
        if newVal is None:
            newVal = ""
        self.choice.set(newVal)
        if noteEdited:
            self.widgetEdited(val=newVal, skipDups=False)
        # WARNING: the value of noteEdited really should be false (default)
        # in most cases because we need the widgetEdited calls to be arranged
        # at one level higher than we are (single param).  We need to allow the
        # caller to first loop over all eparoptions, setting their values
        # without triggering anything, and THEN go through again and run any
        # triggers.

    def unlearnValue(self):
        """Unlearn a parameter value by setting it back to its default"""
        defaultValue = self.defaultParamInfo.get(field = "p_filename",
                            native = 0, prompt = 0)
        self.choice.set(defaultValue)

    def helpOnParam(self):
        """ Try to display help specific to this parameter. """
        if self._helpCallbackObj is not None:
            self._helpCallbackObj.showParamHelp(self.name)

    def setEditedCallbackObj(self, ecbo):
        """ Sets a callback object to be triggred when this option/parameter
            is edited.  The object is expected to have an "edited()" method
            which takes args as shown where it is called in widgetEdited. """
        self._editedCallbackObj = ecbo

    def setActiveState(self, active):
        """ Use this to enable or disable (grey out) a parameter. """
        st = DISABLED
        if active: st = NORMAL
        self.entry.configure(state=st)
        self.inputLabel.configure(state=st)
        self.promptLabel.configure(state=st)

    def flagThisPar(self, currentVal, force):
        """ If this par's value is different from the default value, it is here
        that we flag it somehow as such.  This basic version simply makes the
        surrounding text red (or returns it to normal). May be overridden.
        Leave force at False if you want to allow this mehtod to make smart
        time-saving decisions about when it can skip recoloring because it is
        already the right color. Set force to true if you think we got out
        of sync and need to be fixed. """

        # Get out ASAP if we can
        if (not force) and (not self._flagNonDefaultVals): return

        # handle simple case before comparing values (quick return)
        if force and not self._flagNonDefaultVals:
            self._flagged = False
            self.promptLabel.configure(fg="black")
            return

        # Get/format values to compare
        currentNative = self.convertToNative(currentVal)
        defaultNative = self.convertToNative(self.defaultParamInfo.value)
        # par.value is same as par.get(native=1,prompt=0)

        # flag or unflag as needed
        if currentNative != defaultNative:
            if not self._flagged or force:
                self._flagged = True
                self.promptLabel.configure(fg=self._flaggedColor) # was red
        else: # same as def
            if self._flagged or force:
                self._flagged = False
                self.promptLabel.configure(fg="black")
        # ['red','blue','green','purple','yellow','orange','black']


class EnumEparOption(EparOption):

    def makeInputWidget(self):

        self.unlearnEnabled = NORMAL
        self.isSelectable = False

        # Set the initial value for the button
        self.choice.set(self.value)

        # Need to adjust the value width so the menu button is
        # aligned properly
        if USING_X:
            self.valueWidth = self.valueWidth - 4
        else:
            pass
#           self.valueWidth = self.valueWidth - 0 # looks right on Aqua

        # Generate the button
        self.entry = Menubutton(self.master_frame,
                                 width  = self.valueWidth,
                                 text   = self.choice.get(),      # label
                                 relief = RAISED,
                                 anchor = W,                      # alignment
                                 textvariable = self.choice,      # var to sync
                                 indicatoron  = 1,
                                 takefocus    = 1,
                                 highlightthickness = 1,
                                 activeforeground='black',
                                 fg='black',
                                 bg=self.bkgColor)

        self.entry.menu = Menu(self.entry, tearoff=0,
                               postcommand=self.postcmd,
                               fg = 'black',
                               bg=self.bkgColor)

        # Generate the dictionary of shortcuts using first letter,
        # second if first not available, etc.
        self.shortcuts = {}
        trylist = self.paramInfo.choice
        underline = {}
        charset = string.ascii_lowercase + string.digits
        i = 0
        while trylist:
            trylist2 = []
            for option in trylist:
                # shortcuts dictionary is case-insensitive
                letter = option[i:i+1].lower()
                if letter in self.shortcuts:
                    # will try again with next letter
                    trylist2.append(option)
                elif letter:
                    if letter in charset:
                        self.shortcuts[letter] = option
                        self.shortcuts[letter.upper()] = option
                        underline[option] = i
                    else:
                        # only allow letters, numbers to be shortcuts
                        # keep going in case this is an embedded blank (e.g.)
                        trylist2.append(option)
                else:
                    # no letters left, so no shortcut for this item
                    underline[option] = -1
            trylist = trylist2
            i = i+1

        # Generate the menu options with shortcuts underlined
        for option in self.paramInfo.choice:
            lbl = option
            if lbl=='-': lbl = ' -' # Tk treats '-' as a separator request
            self.entry.menu.add_radiobutton(label       = lbl,
                                            value       = option,
                                            variable    = self.choice,
                                            command     = self.selected,
                                            indicatoron = 0,
                                            underline   = underline[option])

        # set up a pointer from the menubutton back to the menu
        self.entry['menu'] = self.entry.menu

        self.entry.pack(side = LEFT)

        # shortcut keys jump to items
        for letter in self.shortcuts:
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

    def selected(self):
        """They have chosen an enumerated option."""
        self.widgetEdited(action='entry') # kick off any checks that need doin

#   def setActiveState(self, active):
#       [...]
#       for i in range(len(self.paramInfo.choice)):  # this doesn't seem to
#           self.entry.menu.entryconfig(i, state=st) # make the menu text grey
#       [...]



class BooleanEparOption(EparOption):

    def convertToNative(self, aVal):
        """ Convert to native bool; interpret certain strings. """
        if aVal is None:
            return None
        if isinstance(aVal, bool): return aVal
        # otherwise interpret strings
        return str(aVal).lower() in ('1','on','yes','true')

    def makeInputWidget(self):

        self.unlearnEnabled = NORMAL
        self.isSelectable = False

        # Need to buffer the value width so the radio buttons and
        # the adjoining labels are aligned properly
        self.valueWidth = self.valueWidth + 10
        if USING_X:
            self.padWidth = (self.valueWidth // 2) + 5 # looks right
        else:
            self.padWidth = 2 # looks right on Aqua

        # boolean parameters have 3 values: yes, no & undefined
        # Just display two choices (but variable may initially be
        # undefined)
        self.choice.set(self.value)

        self.entry = Frame(self.master_frame,
                           relief    = FLAT,
                           width     = self.valueWidth,
                           takefocus = 1,
                           highlightthickness = 1,
                           bg=self.bkgColor,
                           highlightbackground=self.bkgColor)
        if not USING_X:
            spacerL= Label(self.entry, takefocus=0, text="", width=2,
                           bg=self.bkgColor)
            spacerL.pack(side=LEFT, fill=X, expand=TRUE)
        self.rbyes = Radiobutton(self.entry, text = "Yes",
                                 variable    = self.choice,
                                 value       = "yes",
                                 anchor      = W,
                                 takefocus   = 0,
                                 underline   = 0,
                                 bg = self.bkgColor,
                                 highlightbackground=self.bkgColor)
        self.rbyes.pack(side=LEFT, ipadx=self.padWidth)
        if not USING_X:
            spacerM= Label(self.entry, takefocus=0, text="", width=3,
                           bg=self.bkgColor)
            spacerM.pack(side=LEFT, fill=X, expand=TRUE)
            spacerR = Label(self.entry, takefocus=0, text="", width=2,
                           bg=self.bkgColor)
            spacerR.pack(side=RIGHT, fill=X, expand=TRUE)
        self.rbno  = Radiobutton(self.entry, text = "No",
                                 variable    = self.choice,
                                 value       = "no",
                                 anchor      = W,
                                 takefocus   = 0,
                                 underline   = 0,
                                 bg = self.bkgColor,
                                 highlightbackground=self.bkgColor)
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
        if USING_X:
            self.rbno.bind('<Button-3>', self.popupChoices)
            self.rbyes.bind('<Button-3>', self.popupChoices)
        else:
            self.rbno.bind('<Button-2>', self.popupChoices)
            self.rbyes.bind('<Button-2>', self.popupChoices)
            spacerM.bind('<Button-2>', self.popupChoices)

        # Regular selection - allow immediate trigger/check
        self.rbyes.bind('<Button-1>', self.boolWidgetEditedYes)
        self.rbno.bind('<Button-1>', self.boolWidgetEditedNo)

    def trace(self, *args):
        self.entry.focus_set()

    # Only needed over widgetEdited because the Yes isn't set yet
    def boolWidgetEditedYes(self, event=None): self.widgetEdited(val="yes")

    # Only needed over widgetEdited because the No isn't set yet
    def boolWidgetEditedNo(self, event=None): self.widgetEdited(val="no")

    def set(self, event=None):
        """Set value to Yes"""
        self.rbyes.select()
        self.widgetEdited()

    def unset(self, event=None):
        """Set value to No"""
        self.rbno.select()
        self.widgetEdited()

    def toggle(self, event=None):
        """Toggle value between Yes and No"""
        if self.choice.get() == "yes":
            self.rbno.select()
        else:
            self.rbyes.select()
        self.widgetEdited()

    def setActiveState(self, active):
        st = DISABLED
        if active: st = NORMAL
        self.rbyes.configure(state=st)
        self.rbno.configure(state=st)
        self.inputLabel.configure(state=st)
        self.promptLabel.configure(state=st)


class StringEparOption(EparOption):

    def makeInputWidget(self):

        self.browserEnabled = NORMAL
        self.clearEnabled = NORMAL
        self.unlearnEnabled = NORMAL

        self.choice.set(self.value)
        self.entry = Entry(self.master_frame, width = self.valueWidth,
                     textvariable = self.choice) # , bg=self.bkgColor)
        self.entry.pack(side = LEFT, fill = X, expand = TRUE)
#       self.extraBindingsForSelectableText() # do not use yet


class ActionEparButton(EparOption):

    def getButtonLabel(self):
        return self.value

    def makeInputWidget(self):
#       self.choice.set(self.value)

        self.browserEnabled = DISABLED
        self.clearEnabled = DISABLED
        self.unlearnEnabled = DISABLED
        self.helpEnabled = NORMAL

        # Need to adjust the value width so the button is aligned properly
        if USING_X:
            self.valueWidth = self.valueWidth - 3
        else:
            self.valueWidth = self.valueWidth - 2

        self.isSelectable = False

        # Generate the button
        self.entry = Button(self.master_frame,
                            width   = self.valueWidth,
                            text    = self.getButtonLabel(),
                            relief  = RAISED,
                            background = self.bkgColor,
                            highlightbackground = self.bkgColor,
                            command = self.clicked)
        self.entry.pack(side = LEFT)

    def clicked(self):
        raise NotImplementedError('clicked() must be implemented')

    def unlearnValue(self):
        pass


# widget class that works for numbers and arrays of numbers

class NumberEparOption(EparOption):

    def convertToNative(self, aVal):
        """ Natively as an int. """
        if aVal in (None, '', 'None', 'NONE', 'INDEF'): return None
        return int(aVal)

    def notNull(self, value):
        vsplit = value.split()
        return vsplit.count("INDEF") != len(vsplit)

    def makeInputWidget(self):

        self.browserEnabled = DISABLED
        self.clearEnabled = NORMAL
        self.unlearnEnabled = NORMAL

        # Retain the original parameter value in case of bad entry
        self.previousValue = self.value

        self.choice.set(self.value)
        self.entry = Entry(self.master_frame, width = self.valueWidth,
                           textvariable = self.choice) #, bg=self.bkgColor)
        self.entry.pack(side = LEFT)
#       self.extraBindingsForSelectableText() # do not use yet

    # Check the validity of the entry
    # Note that doing this using the parameter set method automatically
    # checks max, min, special value (INDEF, parameter indirection), etc.
    def entryCheck(self, event = None, repair = True):
        """ Ensure any INDEF entry is uppercase, before base class behavior """
        valupr = self.choice.get().upper()
        if valupr.strip() == 'INDEF':
            self.choice.set(valupr)
        return EparOption.entryCheck(self, event, repair = repair)

# numeric widget class specific to floats

class FloatEparOption(NumberEparOption):

    def convertToNative(self, aVal):
        """ Natively as a float. """
        if aVal in (None, '', 'None', 'NONE', 'INDEF'): return None
        return float(aVal)


# EparOption values for non-string types
_eparOptionDict = { "b": BooleanEparOption,
                    "r": FloatEparOption,
                    "R": FloatEparOption,
                    "d": FloatEparOption,
                    "I": NumberEparOption,
                    "i": NumberEparOption,
                    "z": ActionEparButton,
                    "ar": FloatEparOption,
                    "ai": NumberEparOption,
                  }

def eparOptionFactory(master, statusBar, param, defaultParam,
                      doScroll, fieldWidths,
                      plugIn=None, editedCallbackObj=None,
                      helpCallbackObj=None, mainGuiObj=None,
                      defaultsVerb="Default", bg=None, indent=False,
                      flagging=False, flaggedColor=None):

    """Return EparOption item of appropriate type for the parameter param"""

    # Allow passed-in overrides
    if plugIn is not None:
        eparOption = plugIn

    # If there is an enumerated list, regardless of datatype use EnumEparOption
    elif param.choice is not None:
        eparOption = EnumEparOption

    else:
        # Use String for types not in the dictionary
        eparOption = _eparOptionDict.get(param.type, StringEparOption)

    # Create it
    eo = eparOption(master, statusBar, param, defaultParam, doScroll,
                    fieldWidths, defaultsVerb, bg,
                    indent=indent, helpCallbackObj=helpCallbackObj,
                    mainGuiObj=mainGuiObj)
    eo.setEditedCallbackObj(editedCallbackObj)
    eo.setIsFlagging(flagging, False)
    if flaggedColor:
        eo.setFlaggedColor(flaggedColor)
    return eo
