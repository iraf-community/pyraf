"""module 'editpar.py' -- main module for generating the EPAR task editor

$Id$

Taken from pyraf/lib/epar.py, originally signed "M.D. De La Pena, 2000 Feb. 4"
"""
import os
import sys
import tempfile
import time

from . import capable

if capable.OF_GRAPHICS:
    from tkinter import  _default_root
    from tkinter import *
    from tkinter.filedialog import asksaveasfilename
    from tkinter.messagebox import askokcancel, askyesno, showwarning

# stsci.tools modules
from .irafglobals import userWorkingHome
from . import basicpar, eparoption, irafutils, taskpars

# Constants
MINVIEW     = 500
MINPARAMS   = 25
INPUTWIDTH  = 10
VALUEWIDTH  = 21
PROMPTWIDTH = 55
DFT_OPT_FILE = "epar.optionDB"
TIP = "rollover"
DBG = "debug"

# The following action types are used within the GUI code.  They define what
# kind of GUI action actually caused a parameter's value to be adjusted.
# This is meant to be like an enum.  These values may appear in a task's
# task.cfgspc file in a rule.  In that file, the value 'always' may be used, in
# addition to these values, to indicate a match to all possible action types.
GROUP_ACTIONS = ('defaults','init','fopen','entry')
# init     -> startup of the GUI
# defaults -> the user clicked the Defaults or Reset button
# fopen    -> the user loaded a config file
# entry    -> the user actually edited a parameter (via mouse or keyboard)

# Use these values for startup geometry ***for now***
# PARENT is the main editor window
PARENTX = 50
PARENTY = 50

# DCHILD[XY] are amounts each successive child shifts
DCHILDX = 50
DCHILDY = 50

# CHILD[XY] is a PSET window
CHILDX = PARENTX
CHILDY = PARENTY

# HELP[XY] is for the help as displayed in a window
HELPX   = 300
HELPY   = 25


class UnfoundParamError(Exception):
    pass


class EditParDialog:

    def __init__(self, theTask, parent=None, isChild=0,
                 title="Parameter Editor", childList=None,
                 resourceDir='.'):

        # Initialize status message stuff first thing
        self._leaveStatusMsgUntil = 0
        self._msgHistory = [] # all msgs, of all kinds, since we opened
        self._statusMsgsToShow = [] # keep a *small* number of late msgs
        self.debug('Starting up the GUI!')

        # Call our (or a subclass's) _setTaskParsObj() method
        self._setTaskParsObj(theTask)

        # Now go back and ensure we have the full taskname; set up other items
        self._canceled = False
        self._executed = False
        self._guiName = title
        self.taskName = self._taskParsObj.getName()
        self.pkgName = self._taskParsObj.getPkgname()
        theParamList = self._taskParsObj.getParList(docopy=1)
        self._rcDir = resourceDir
        self.debug('TASK: '+self.taskName+', PKG: '+self.pkgName+ \
                   ', RC: '+self._rcDir)
        # setting _tmwm=1 is the slowest motion, 7 seems OK, 10 maybe too fast
        self._tmwm = int(os.getenv('TEAL_MOUSE_WHEEL_MULTIPLIER', 7))

        # Get default parameter values for unlearn - watch return value
        # NOTE - this may edit/reorder the working paramList
        if not self._setupDefaultParamList():
            return

        # Ignore the last parameter which is $nargs
        self.numParams = len(theParamList) - 1

        # Set all default master GUI settings, then
        # allow subclasses to override them
        self._appName             = "Par Editor"
        self._appHelpString       = "No help yet created for this GUI editor"
        self._useSimpleAutoClose  = False # certain buttons close GUI also
        self._showExecuteButton   = True
        self._showSaveCloseOnExec = True
        self._saveAndCloseOnExec  = True
        self._showFlaggingChoice  = True
        self._flagNonDefaultVals  = None # default not yet set
        self._showExtraHelpButton = False
        self._showHelpInBrowser   = False
        self._knowTaskHelpIsHtml  = False
        self._unpackagedTaskTitle = "Task"
        self._writeProtectOnSaveAs= True
        self._defaultsButtonTitle = "Defaults"
        self._optFile             = DFT_OPT_FILE
        self._defSaveAsExt        = '.cfg'

        # Colors
        self._frmeColor = None  # frame of window
        self._taskColor = None  # task label area
        self._bboxColor = None  # button area
        self._entsColor = None  # entries area
        self._flagColor = "red" # non-default values

        # give the subclass a chance to disagree
        self._overrideMasterSettings() # give the subclass a chance to disagree

        # any settings which depend on overrides
        if self._flagNonDefaultVals is None:
            self._flagNonDefaultVals = self._showFlaggingChoice # default

        # Create the root window as required, but hide it
        self.parent = parent
        if self.parent is None:
            global _default_root
            if _default_root is None:
                _default_root = irafutils.init_tk_default_root()

        # Track whether this is a parent or child window
        self.isChild = isChild

        # Set up a color for each of the backgrounds
        if self.isChild:
        #    self._frmeColor = "LightSteelBlue"
            self.iconLabel = "EPAR Child"
        else:
            self.iconLabel = "EPAR Parent"

        # help windows do not exist yet
        self.eparHelpWin = None
        self.irafHelpWin = None
        self.logHistWin = None

        # no last focus widget
        self.lastFocusWidget = None

        # Generate the top epar window
        self.top = top = Toplevel(self.parent,bg=self._frmeColor,visual="best")
        self.top.withdraw() # hide it while we fill it up with stuff

        if len(self.pkgName):
            self.updateTitle(self.pkgName+"."+self.taskName)
        else:
            self.updateTitle(self.taskName)
        self.top.iconname(self.iconLabel)

        # Read in the tk options database file
        try:
            # User's current directory
            self.top.option_readfile(os.path.join(os.curdir, self._optFile))
        except TclError:
            try:
                # User's startup directory
                self.top.option_readfile(os.path.join(userWorkingHome,
                                                      self._optFile))
            except TclError:
                try:
                    # App default
                    self.top.option_readfile(os.path.join(self._rcDir,
                                                          self._optFile))
                except TclError:
                    if self._optFile != DFT_OPT_FILE:
                        pass
                    else:
                        raise

        # Create an empty list to hold child dialogs
        # *** Not a good way, REDESIGN with Mediator!
        # Also, build the parent menu bar
        if self.parent is None:
            self.top.childList = []
        elif childList is not None:
            # all children share a list
            self.top.childList = childList

        # Build the EPAR menu bar
        self.makeMenuBar(self.top)

        # Create a spacer
        Frame(self.top, bg=self._taskColor, height=10).pack(side=TOP, fill=X)

        # Print the package and task names
        self.printNames(self.top, self.taskName, self.pkgName)

        # Insert a spacer between the static text and the buttons
        Frame(self.top, bg=self._taskColor, height=15).pack(side=TOP, fill=X)

        # Set control buttons at the top of the frame
        self.buttonBox(self.top)

        # Insert a spacer between the static text and the buttons
        Frame(self.top, bg=self._entsColor, height=15).pack(side=TOP, fill=X)

        # Set up an information Frame at the bottom of the EPAR window
        # RESIZING is currently disabled.
        # Do this here so when resizing to a smaller sizes, the parameter
        # panel is reduced - not the information frame.
        self.top.status = Label(self.top, text="", relief=SUNKEN,
                                borderwidth=1, anchor=W, bg=self._frmeColor)
        self.top.status.pack(side=BOTTOM, fill=X, padx=0, pady=3, ipady=3)

        # Set up a Frame to hold a scrollable Canvas
        self.top.f = frame = Frame(self.top, relief=RIDGE, borderwidth=1,
                                   bg=self._entsColor)

        # Overlay a Canvas which will hold a Frame
        self.top.f.canvas = canvas = Canvas(self.top.f, width=100, height=100,
            takefocus=FALSE, bg=self._entsColor,
            highlightbackground=self._entsColor)
#           highlightcolor="black" # black must be the default, since it is blk

        # Always build the scrollbar, even if number of parameters is small,
        # to allow window to be resized.

        # Attach a vertical Scrollbar to the Frame/Canvas
        self.top.f.vscroll = Scrollbar(self.top.f, orient=VERTICAL,
             width=11, relief=SUNKEN, activerelief=RAISED,
             takefocus=FALSE, bg=self._entsColor)
        canvas['yscrollcommand'] = self.top.f.vscroll.set
        self.top.f.vscroll['command'] = canvas.yview

        # Pack the Scrollbar
        self.top.f.vscroll.pack(side=RIGHT, fill=Y)

        # enable Page Up/Down keys
        scroll = canvas.yview_scroll
        top.bind('<Next>', lambda event, fs=scroll: fs(1, "pages"))
        top.bind('<Prior>', lambda event, fs=scroll: fs(-1, "pages"))

        # make up, down arrows and return/shift-return do same as Tab, Shift-Tab
        top.bind('<Up>', self.focusPrev)
        top.bind('<MouseWheel>', self.mwl) # on OSX, rolled up or down
        top.bind('<Button-4>', self.mwl)   # on Linux, rolled up
        top.bind('<Button-5>', self.mwl)   # on Linux, rolled down
        top.bind('<Down>', self.focusNext)
        top.bind('<Shift-Return>', self.focusPrev)
        top.bind('<Return>', self.focusNext)
        try:
            # special shift-tab binding needed for (some? all?) linux systems
            top.bind('<KeyPress-ISO_Left_Tab>', self.focusPrev)
        except TclError:
            # Ignore exception here, the binding can't be relevant
            # if ISO_Left_Tab is unknown.
            pass

        # Pack the Frame and Canvas
        canvas.pack(side=TOP, expand=TRUE, fill=BOTH)
        self.top.f.pack(side=TOP, expand=TRUE, fill=BOTH)

        # Define a Frame to contain the parameter information
        canvas.entries = Frame(canvas, bg=self._entsColor)

        # Generate the window to hold the Frame which sits on the Canvas
        cWindow = canvas.create_window(0, 0,
                           anchor=NW,
                           window=canvas.entries)

        # Insert a spacer between the Canvas and the information frame
        Frame(self.top, bg=self._entsColor, height=4).pack(side=TOP, fill=X)

        # The parent has the control, unless there are children
        # Fix the geometry of where the windows first appear on the screen
        if self.parent is None:
            #self.top.grab_set()

            # Position this dialog relative to the parent
            self.top.geometry("+%d+%d" % (PARENTX, PARENTY))
        else:
            #self.parent.grab_release()
            #self.top.grab_set()

            # Declare the global variables so they can be updated
            global CHILDX
            global CHILDY

            # Position this dialog relative to the parent
            CHILDX = CHILDX + DCHILDX
            CHILDY = CHILDY + DCHILDY
            self.top.geometry("+%d+%d" % (CHILDX, CHILDY))


        #
        # Now fill in the Canvas Window
        #

        # The makeEntries method creates the parameter entry Frame
        self.makeEntries(canvas.entries, self.top.status)

        # Force an update of the entry Frame
        canvas.entries.update()

        # Determine the size of the entry Frame
        width = canvas.entries.winfo_width()
        height = canvas.entries.winfo_height()

        # Reconfigure the Canvas size based on the Frame.
        if (self.numParams <= MINPARAMS):
            viewHeight = height
        else:
            # Set the minimum display
            viewHeight = MINVIEW

        # Scrollregion is based upon the full size of the entry Frame
        canvas.config(scrollregion=(0, 0, width, height))
        # Smooth scroll
        self.yscrollincrement = 5 # changed Mar2010, had been 50 a long time
        canvas.config(yscrollincrement=self.yscrollincrement)

        # Set the actual viewable region for the Canvas
        canvas.config(width=width, height=viewHeight)

        # Force an update of the Canvas
        canvas.update()

        # Associate deletion of the main window to a Abort
        self.top.protocol("WM_DELETE_WINDOW", self.abort)

        # Trigger all widgets one time before starting in case they have
        # values which would run a trigger
        self.checkAllTriggers('init')

        # Set focus to first parameter
        self.setViewAtTop()

        # Finally show it
        self.top.update()
        self.top.deiconify()

        # Enable interactive resizing in height
        self.top.resizable(width=FALSE, height=TRUE)

        # Limit maximum window height
        width = self.top.winfo_width()
        height = self.top.winfo_height() + height - viewHeight
        self.top.maxsize(width=width, height=height)

        self.debug('showing '+self._appName+' main window')

        # run the mainloop
        if not self.isChild:
            self._preMainLoop()
            self.top.mainloop()
            self._postMainLoop()


    def _overrideMasterSettings(self):
        """ Hook for subclasses to override some attributes if wished. """
        return


    def _preMainLoop(self):
        """ Hook for subclasses to override if wished. """
        return


    def _postMainLoop(self):
        """ Hook for subclasses to override if wished. """
        return


    def _showOpenButton(self):
        """ Should we show the "Open..." button?  Subclasses override. """
        return True


    def _setTaskParsObj(self, theTask):
        """ This method, meant to be overridden by subclasses, generates the
        _taskParsObj object. theTask can often be either a file name or a
        TaskPars subclass object. """

        # Here we catch if this version is run by accident
        raise NotImplementedError("EditParDialog is not to be used directly")


    def _saveGuiSettings(self):
        """ Hook for subclasses to save off GUI settings somewhere. """
        return # skip this by default


    def updateTitle(self, atitle):
        if atitle:
            self.top.title('%s:  %s' % (self._guiName, atitle))
        else:
            self.top.title('%s' % (self._guiName))


    def checkAllTriggers(self, action):
        """ Go over all widgets and let them know they have been edited
            recently and they need to check for any trigger actions.  This
            would be used right after all the widgets have their values
            set or forced (e.g. via setAllEntriesFromParList). """
        for entry in self.entryNo:
            entry.widgetEdited(action=action, skipDups=False)


    def freshenFocus(self):
        """ Did something which requires a new look.  Move scrollbar up.
            This often needs to be delayed a bit however, to let other
            events in the queue through first. """
        self.top.update_idletasks()
        self.top.after(10, self.setViewAtTop)


    def setViewAtTop(self):
        self.entryNo[0].focus_set()
        self.top.f.canvas.xview_moveto(0.0)
        self.top.f.canvas.yview_moveto(0.0)


    def getTaskParsObj(self):
        """ Simple accessor.  Return the _taskParsObj object. """
        return self._taskParsObj

    def mwl(self, event):
        """Mouse Wheel - under tkinter we seem to need Tk v8.5+ for this """
        if event.num == 4: # up on Linux
            self.top.f.canvas.yview_scroll(-1*self._tmwm, 'units')
        elif event.num == 5: # down on Linux
            self.top.f.canvas.yview_scroll(1*self._tmwm, 'units')
        else: # assume event.delta has the direction, but reversed sign
            self.top.f.canvas.yview_scroll(-(event.delta)*self._tmwm, 'units')

# A bug appeared in Python 2.3 that caused tk_focusNext and
# tk_focusPrev to fail. The follwoing two routines now will
# trap this error and call "fixed" versions of these tk routines
# instead in the event of such errors.

    def focusNext(self, event):
        """Set focus to next item in sequence"""
        try:
            event.widget.tk_focusNext().focus_set()
        except TypeError:
            # see tkinter equivalent code for tk_focusNext to see
            # commented original version
            name = event.widget.tk.call('tk_focusNext', event.widget._w)
            event.widget._nametowidget(str(name)).focus_set()

    def focusPrev(self, event):
        """Set focus to previous item in sequence"""
        try:
            event.widget.tk_focusPrev().focus_set()
        except TypeError:
            # see tkinter equivalent code for tk_focusPrev to see
            # commented original version
            name = event.widget.tk.call('tk_focusPrev', event.widget._w)
            event.widget._nametowidget(str(name)).focus_set()

    def doScroll(self, event):
        """Scroll the panel down to ensure widget with focus to be visible

        Tracks the last widget that doScroll was called for and ignores
        repeated calls.  That handles the case where the focus moves not
        between parameter entries but to someplace outside the hierarchy.
        In that case the scrolling is not expected.

        Returns false if the scroll is ignored, else true.
        """
        canvas = self.top.f.canvas
        widgetWithFocus = event.widget
        if widgetWithFocus is self.lastFocusWidget:
            return FALSE
        self.lastFocusWidget = widgetWithFocus
        if widgetWithFocus is None:
            return TRUE
        # determine distance of widget from top & bottom edges of canvas
        y1 = widgetWithFocus.winfo_rooty()
        y2 = y1 + widgetWithFocus.winfo_height()
        cy1 = canvas.winfo_rooty()
        cy2 = cy1 + canvas.winfo_height()
        yinc = self.yscrollincrement
        if y1<cy1:
            # this will continue to work when integer division goes away
            sdist = int((y1-cy1-yinc+1.)/yinc)
            canvas.yview_scroll(sdist, "units")
        elif cy2<y2:
            sdist = int((y2-cy2+yinc-1.)/yinc)
            canvas.yview_scroll(sdist, "units")
        return TRUE


    def _handleParListMismatch(self, probStr, extra=False):
        """ Handle the situation where two par lists do not match.
        This is meant to allow subclasses to override. Note that this only
        handles "missing" pars and "extra" pars, not wrong-type pars. """

        errmsg = 'ERROR: mismatch between default and current par lists ' + \
               'for task "'+self.taskName+'"'
        if probStr:
            errmsg += '\n\t'+probStr
        errmsg += '\n(try: "unlearn '+self.taskName+'")'
        print(errmsg)
        return False


    def _setupDefaultParamList(self):
        """ This creates self.defaultParamList.  It also does some checks
        on the paramList, sets its order if needed, and deletes any extra
        or unknown pars if found. We assume the order of self.defaultParamList
        is the correct order. """

        # Obtain the default parameter list
        self.defaultParamList = self._taskParsObj.getDefaultParList()
        theParamList = self._taskParsObj.getParList()

        # Lengths are probably equal but this isn't necessarily an error
        # here, so we check for differences below.
        if len(self.defaultParamList) != len(theParamList):
            # whoa, lengths don't match (could be some missing or some extra)
            pmsg = 'Current list not same length as default list'
            if not self._handleParListMismatch(pmsg):
                return False

        # convert current par values to a dict of { par-fullname:par-object }
        # for use below
        ourpardict = {}
        for par in theParamList: ourpardict[par.fullName()] = par

        # Sort our paramList according to the order of the defaultParamList
        # and repopulate the list according to that order. Create sortednames.
        sortednames = [p.fullName() for p in self.defaultParamList]

        # Rebuild par list sorted into correct order.  Also find/flag any
        # missing pars or any extra/unknown pars.  This automatically deletes
        # "extras" by not adding them to the sorted list in the first place.
        migrated = []
        newList = []
        for fullName in sortednames:
            if fullName in ourpardict:
                newList.append(ourpardict[fullName])
                migrated.append(fullName) # make sure all get moved over
            else: # this is a missing par - insert the default version
                theDfltVer = \
                    [p for p in self.defaultParamList if p.fullName()==fullName]
                newList.append(copy.deepcopy(theDfltVer[0]))

        # Update!  Next line writes to the self._taskParsObj.getParList() obj
        theParamList[:] = newList # fill with newList, keep same mem pointer

        # See if any got left out
        extras = [fn for fn in ourpardict if not fn in migrated]
        for fullName in extras:
            # this is an extra/unknown par - let subclass handle it
            if not self._handleParListMismatch('Unexpected par: "'+\
                        fullName+'"', extra=True):
                return False
            print('Ignoring unexpected par: "'+p+'"')

        # return value indicates that all is well to continue
        return True


    # Method to create the parameter entries
    def makeEntries(self, master, statusBar):

        # Get model data, the list of pars
        theParamList = self._taskParsObj.getParList()

        # Determine the size of the longest input string
        inputLength = INPUTWIDTH
        for i in range(self.numParams):
            inputString = theParamList[i].name
            if len(inputString) > inputLength:
                inputLength = len(inputString)

        # Set up the field widths
        # Allow extra spaces for buffer and in case the longest parameter
        # has the hidden parameter indicator
        self.fieldWidths = {}
        self.fieldWidths['inputWidth'] = inputLength + 4
        self.fieldWidths['valueWidth'] = VALUEWIDTH
        self.fieldWidths['promptWidth'] = PROMPTWIDTH

        # Loop over the parameters to create the entries
        self.entryNo = [None] * self.numParams
        dfltsVerb = self._defaultsButtonTitle
        if dfltsVerb[-1]=='s': dfltsVerb = dfltsVerb[:-1]
        for i in range(self.numParams):
            scope = theParamList[i].scope
            eparOpt = self._nonStandardEparOptionFor(theParamList[i].type)
            cbo = self._defineEditedCallbackObjectFor(scope,
                                                      theParamList[i].name)
            hcbo = None
            if self._knowTaskHelpIsHtml:
                hcbo = self
            self.entryNo[i] = eparoption.eparOptionFactory(master, statusBar,
                                  theParamList[i], self.defaultParamList[i],
                                  self.doScroll, self.fieldWidths,
                                  plugIn=eparOpt, editedCallbackObj=cbo,
                                  helpCallbackObj=hcbo, mainGuiObj=self,
                                  defaultsVerb=dfltsVerb, bg=self._entsColor,
                                  indent = scope not in (None, '', '.'),
                                  flagging = self._flagNonDefaultVals,
                                  flaggedColor=self._flagColor)


    def _nonStandardEparOptionFor(self, paramTypeStr):
        """ Hook to allow subclasses to employ their own GUI option type.
            Return None or a class which derives from EparOption. """
        return None


    def _defineEditedCallbackObjectFor(self, parScope, parName):
        """ Hook to allow subclasses to set their own callback-containing
            object to be used when a given option/parameter is edited.
            See notes in EparOption. """
        return None


    def _isUnpackagedTask(self):
        """ Hook to allow subclasses to state that this is a rogue task, not
            affiliated with a specific package, affecting its display. """
        return self.pkgName is None or len(self.pkgName) < 1


    def _toggleSectionActiveState(self, sectionName, state, skipList):
        """ Make an entire section (minus skipList items) either active or
            inactive.  sectionName is the same as the param's scope. """

        # Get model data, the list of pars
        theParamList = self._taskParsObj.getParList()

        # Loop over their assoc. entries
        for i in range(self.numParams):
            if theParamList[i].scope == sectionName:
                if skipList and theParamList[i].name in skipList:
#                   self.entryNo[i].setActiveState(True) # these always active
                    pass # if it started active, we don't need to reactivate it
                else:
                    self.entryNo[i].setActiveState(state)


    # Method to print the package and task names and to set up the menu
    # button for the choice of the display for the task help page
    def printNames(self, top, taskName, pkgName):

        topbox = Frame(top, bg=self._taskColor)
        textbox = Frame(topbox, bg=self._taskColor)
#       helpbox = Frame(topbox, bg=self._taskColor)

        # Set up the information strings
        if self._isUnpackagedTask():
            # label for a parameter list is just filename
            packString = " "+self._unpackagedTaskTitle+" = "+taskName
            Label(textbox, text=packString, bg=self._taskColor).pack(side=TOP,
                  anchor=W)
        else:
            # labels for task
            packString = "  Package = " + pkgName.upper()
            Label(textbox, text=packString, bg=self._taskColor).pack(side=TOP,
                  anchor=W)

            taskString = "       Task = " + taskName.upper()
            Label(textbox, text=taskString, bg=self._taskColor).pack(side=TOP,
                  anchor=W)
        textbox.pack(side=LEFT, anchor=W)
        topbox.pack(side=TOP, expand=FALSE, fill=X)

    # Method to set up the parent menu bar
    def makeMenuBar(self, top):

        menubar = Frame(top, bd=1, relief=GROOVE, bg=self._frmeColor)

        # Generate the menus
        fileMenu = self.makeFileMenu(menubar)

        if self._showOpenButton():
            openMenu = self.makeOpenMenu(menubar)

        # When redesigned, optionsMenu should only be on the parent
        #if not self.isChild:
        #    optionsMenu = self.makeOptionsMenu(menubar)
        optionsMenu = self.makeOptionsMenu(menubar)

        helpMenu = self.makeHelpMenu(menubar)

        menubar.pack(fill=X)


    # Method to generate a "File" menu
    def makeFileMenu(self, menubar):

        fileButton = Menubutton(menubar, text='File', bg=self._frmeColor)
        fileButton.pack(side=LEFT, padx=2)

        fileButton.menu = Menu(fileButton, tearoff=0)

#       fileButton.menu.add_command(label="Open...", command=self.pfopen)

        if self._showExecuteButton:
            fileButton.menu.add_command(label="Execute", command=self.execute)
            if self.isChild:
                fileButton.menu.entryconfigure(0, state=DISABLED)

        saqlbl ="Save"
        if self._useSimpleAutoClose: saqlbl += " & Quit"
        fileButton.menu.add_command(label=saqlbl,
                                    command=self.saveAndClose)
        if not self.isChild:
            fileButton.menu.add_command(label="Save As...", command=self.saveAs)
        fileButton.menu.add_separator()
        fileButton.menu.add_command(label=self._defaultsButtonTitle,
                                    command=self.unlearn)
        fileButton.menu.add_separator()
        if not self._useSimpleAutoClose:
            fileButton.menu.add_command(label="Close", command=self.closeGui)
        fileButton.menu.add_command(label="Cancel", command=self.abort)

        # Associate the menu with the menu button
        fileButton["menu"] = fileButton.menu

        return fileButton

    def _updateOpen(self):
        # Get new data
        flist = self._getOpenChoices()

        # Delete old choices
        if self._numOpenMenuItems > 0:
            self._openMenu.delete(0, self._numOpenMenuItems-1)

        # Add all new choices
        self._numOpenMenuItems = len(flist)
        if self._numOpenMenuItems > 0:
            for ff in flist:
                if ff[-3:] == '...':
                    self._openMenu.add_separator()
                    self._numOpenMenuItems += 1
                self._openMenu.add_radiobutton(label=ff, command=self.pfopen,
                                               variable=self._openMenuChoice,
                                               indicatoron=0)
                                               # value=ff) ... (same as label)
            self._openMenuChoice.set(0) # so nothing has check mark next to it
        else:
            showwarning(title="No Files To Open", message="No extra "+ \
                'parameter files found for task "'+self.taskName+'".')

    def _getOpenChoices(self):
        """ Get the current list of file name choices for the Open button.
            This is meant for subclasses to override. """
        return []

    # Method to generate an "Open" menu
    def makeOpenMenu(self, menubar):

        self._openMenuChoice = StringVar() # this is used till GUI closes
        self._numOpenMenuItems = 1 # see dummy

        openBtn = Menubutton(menubar, text='Open...', bg=self._frmeColor)
        openBtn.bind("<Enter>", self.printOpenInfo)
        openBtn.pack(side=LEFT, padx=2)

        openBtn.menu = Menu(openBtn, tearoff=0, postcommand=self._updateOpen)
        openBtn.menu.bind("<Enter>", self.printOpenInfo)
        openBtn.menu.add_radiobutton(label=' ', # dummy, no command
                                     variable=self._openMenuChoice)
                                     # value=fname ... (same as label)

        if self.isChild:
            openBtn.menu.entryconfigure(0, state=DISABLED)

        # Associate the menu with the menu button
        openBtn["menu"] = openBtn.menu

        # Keep a ref for ourselves
        self._openMenu = openBtn.menu

        return openBtn

    # Method to generate the "Options" menu for the parent EPAR only
    def makeOptionsMenu(self, menubar):

        # Set up the menu for the various choices they have
        self._helpChoice = StringVar()
        if self._showHelpInBrowser:
            self._helpChoice.set("BROWSER")
        else:
            self._helpChoice.set("WINDOW")

        if self._showSaveCloseOnExec:
            self._execChoice = IntVar()
            self._execChoice.set(int(self._saveAndCloseOnExec))

        optionButton = Menubutton(menubar, text="Options", bg=self._frmeColor)
        optionButton.pack(side=LEFT, padx=2)
        optionButton.menu = Menu(optionButton, tearoff=0)
        optionButton.menu.add_radiobutton(label="Display Task Help in a Window",
                                     value="WINDOW", command=self.setHelpType,
                                     variable=self._helpChoice)
        optionButton.menu.add_radiobutton(label="Display Task Help in a Browser",
                                     value="BROWSER", command=self.setHelpType,
                                     variable=self._helpChoice)

        if self._showExecuteButton and self._showSaveCloseOnExec:
            optionButton.menu.add_separator()
            optionButton.menu.add_checkbutton(label="Save and Close on Execute",
                                              command=self.setExecOpt,
                                              variable=self._execChoice)
        if self._showFlaggingChoice:
            self._flagChoice = IntVar()
            self._flagChoice.set(int(self._flagNonDefaultVals))
            optionButton.menu.add_separator()
            optionButton.menu.add_checkbutton(label="Flag Non-default Values",
                                              command=self.setFlagOpt,
                                              variable=self._flagChoice)

        # Associate the menu with the menu button
        optionButton["menu"] = optionButton.menu

        return optionButton

    def capTaskName(self):
        """ Return task name with first letter capitalized. """
        return self.taskName[:1].upper() + self.taskName[1:]

    def makeHelpMenu(self, menubar):

        button = Menubutton(menubar, text='Help', bg=self._frmeColor)
        button.bind("<Enter>", self.printHelpInfo)
        button.pack(side=RIGHT, padx=2)
        button.menu = Menu(button, tearoff=0)
        button.menu.bind("<Enter>", self.printHelpInfo)
        button.menu.add_command(label=self.capTaskName()+" Help",
                                command=self.showTaskHelp)
        button.menu.add_command(label=self._appName+" Help",
                                command=self.eparHelp)
        button.menu.add_separator()
        button.menu.add_command(label='Show '+self._appName+' Log',
                                command=self.showLogHist)
        button["menu"] = button.menu
        return button

    # Method to set up the action buttons
    # Create the buttons in an order for good navigation
    def buttonBox(self, top):

        box = Frame(top, bg=self._bboxColor, bd=1, relief=SUNKEN)

        # When the Button is exited, the information clears, and the
        # Button goes back to the nonactive color.
        top.bind("<Leave>", self.clearInfo)

        # Execute the task
        if self._showExecuteButton:
            buttonExecute = Button(box, text="Execute", bg=self._bboxColor,
                                   relief=RAISED, command=self.execute,
                                   highlightbackground=self._bboxColor)
            buttonExecute.pack(side=LEFT, padx=5, pady=7)
            buttonExecute.bind("<Enter>", self.printExecuteInfo)
            if not self._useSimpleAutoClose:
                # separate this button from the others - it's unusual
                strut = Label(box, text="", bg=self._bboxColor)
                strut.pack(side=LEFT, padx=20)

            # EXECUTE button is disabled for child windows
            if self.isChild:
                buttonExecute.configure(state=DISABLED)

        # Save the parameter settings and exit from epar
        saqlbl ="Save"
        if self._useSimpleAutoClose: saqlbl += " & Quit"
        btn = Button(box, text=saqlbl, relief=RAISED, command=self.saveAndClose,
                     bg=self._bboxColor, highlightbackground=self._bboxColor)
        btn.pack(side=LEFT, padx=5, pady=7)
        btn.bind("<Enter>", self.printSaveQuitInfo)

        # Unlearn all the parameter settings (set back to the defaults)
        buttonUnlearn = Button(box, text=self._defaultsButtonTitle,
                               relief=RAISED, command=self.unlearn,
                               bg=self._bboxColor,
                               highlightbackground=self._bboxColor)
        if self._showExtraHelpButton:
            buttonUnlearn.pack(side=LEFT, padx=5, pady=7)
        else:
            buttonUnlearn.pack(side=RIGHT, padx=5, pady=7)
        buttonUnlearn.bind("<Enter>", self.printUnlearnInfo)


        # Buttons to close versus abort this edit session.
        if not self._useSimpleAutoClose:
            buttonClose = Button(box, text="Close",
                                 relief=RAISED, command=self.closeGui,
                                 bg=self._bboxColor,
                                 highlightbackground=self._bboxColor)
            buttonClose.pack(side=LEFT, padx=5, pady=7)
            buttonClose.bind("<Enter>", self.printCloseInfo)

        buttonAbort = Button(box, text="Cancel", bg=self._bboxColor,
                             relief=RAISED, command=self.abort,
                             highlightbackground=self._bboxColor)
        buttonAbort.pack(side=LEFT, padx=5, pady=7)
        buttonAbort.bind("<Enter>", self.printAbortInfo)

        # Generate the Help button
        if self._showExtraHelpButton:
            buttonHelp = Button(box, text=self.capTaskName()+" Help",
                                relief=RAISED, command=self.showTaskHelp,
                                bg=self._bboxColor,
                                highlightbackground=self._bboxColor)
            buttonHelp.pack(side=RIGHT, padx=5, pady=7)
            buttonHelp.bind("<Enter>", self.printHelpInfo)

        # Pack
        box.pack(fill=X, expand=FALSE)

    def setExecOpt(self, event=None):
        self._saveAndCloseOnExec = bool(self._execChoice.get())

    def setFlagOpt(self, event=None):
        self._flagNonDefaultVals = bool(self._flagChoice.get())
        for entry in self.entryNo:
            entry.setIsFlagging(self._flagNonDefaultVals, True)

    def setHelpType(self, event=None):
        """ Determine which method of displaying the help pages was
        chosen by the user.  WINDOW displays in a task generated scrollable
        window.  BROWSER invokes the task's HTML help pages and displays
        in a browser. """
        self._showHelpInBrowser = bool(self._helpChoice.get() == "BROWSER")


    def eparHelp(self, event=None):     self._showAnyHelp('epar')
    def showTaskHelp(self, event=None): self._showAnyHelp('task')
    def showParamHelp(self, parName):   self._showAnyHelp('task', tag=parName)
    def showLogHist(self, event=None):  self._showAnyHelp('log')


    #
    # Define flyover help text associated with the action buttons
    #

    def clearInfo(self, event):
        self.showStatus("")

    def printHelpInfo(self, event):
        self.showStatus("Display the help page", cat=TIP)

    def printUnlearnInfo(self, event):
        self.showStatus("Set all parameter values to their default settings",
                        cat=TIP)

    def printSaveQuitInfo(self, event):
        if self._useSimpleAutoClose:
            self.showStatus("Save current entries and exit this edit session",
                            cat=TIP)
        else:
            self.showStatus("Save the current entries to "+ \
                            self._taskParsObj.getFilename(), cat=TIP)

    def printOpenInfo(self, event):
        self.showStatus(
            "Load and edit parameter values from a user-specified file",
            cat=TIP)

    def printCloseInfo(self, event):
        self.showStatus("Close this edit session.  Save first?", cat=TIP)

    def printAbortInfo(self, event):
        self.showStatus(
            "Abort this edit session, discarding any unsaved changes.",cat=TIP)

    def printExecuteInfo(self, event):
        if self._saveAndCloseOnExec:
            self.showStatus(
                 "Execute the task, and save and exit this edit session",
                 cat=TIP)
        else:
            self.showStatus("Execute the task; this window will remain open",
                            cat=TIP)


    # Process invalid input values and invoke a query dialog
    def processBadEntries(self, badEntriesList, taskname, canCancel=True):

        badEntriesString = "Task " + taskname.upper() + " --\n" \
            "Invalid values have been entered.\n\n" \
            "Parameter   Bad Value   Reset Value\n"

        for i in range (len(badEntriesList)):
            badEntriesString = badEntriesString + \
                "%15s %10s %10s\n" % (badEntriesList[i][0], \
                badEntriesList[i][1], badEntriesList[i][2])

        if canCancel:
            badEntriesString += '\n"OK" to continue using'+ \
            ' the reset values, or "Cancel" to re-enter values?\n'
        else:
            badEntriesString += \
            "\n All invalid values will return to their 'Reset Value'.\n"

        # Invoke the modal message dialog
        if canCancel:
            return askokcancel("Notice", badEntriesString)
        else:
            return showwarning("Notice", badEntriesString)


    def hasUnsavedChanges(self):
        """ Determine if there are any edits in the GUI that have not yet been
        saved (e.g. to a file).  This needs to be overridden by a subclass.
        In the meantime, just default (on the safe side) to everything being
        ready-to-save. """
        return True


    def closeGui(self, event=None):
        self.saveAndClose(askBeforeSave=True, forceClose=True)


    # SAVE/QUIT: save the parameter settings and exit epar
    def saveAndClose(self, event=None, askBeforeSave=False, forceClose=False):

        # First, see if we can/should skip the save
        doTheSave = True
        if askBeforeSave:
            if self.hasUnsavedChanges():
                doTheSave = askyesno('Save?', 'Save before closing?')
            else: # no unsaved changes, so no need to save OR even to prompt
                doTheSave = False # no need to save OR prompt

        # first save the child parameters, aborting save if
        # invalid entries were encountered
        if doTheSave and self.checkSetSaveChildren():
            return

        # Save all the entries and verify them, keeping track of the
        # invalid entries which have been reset to their original input values
        self.badEntriesList = None
        if doTheSave:
            self.badEntriesList = self.checkSetSaveEntries()
            # Note, there is a BUG here - if they hit Cancel, the save to
            # file has occurred anyway (they may not care) - need to refactor.

        # If there were invalid entries, prepare the message dialog
        if self.badEntriesList:
            ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                          self.taskName)
            if not ansOKCANCEL: return

        # If there were no invalid entries or the user says OK, continue...

        # Save any GUI settings we care about.  This is a good time to do so
        # even if the window isn't closing, but especially if it is.
        self._saveGuiSettings()

        # Done saving.  Only close the window if we are running in that mode.
        if not (self._useSimpleAutoClose or forceClose):
            return

        # Remove the main epar window
        self.top.focus_set()
        self.top.withdraw()

        # If not a child window, quit the entire session
        if not self.isChild:
            self.top.destroy()
            self.top.quit()

        # Declare the global variables so they can be updated
        global CHILDX
        global CHILDY

        # Reset to the start location
        CHILDX = PARENTX
        CHILDY = PARENTY


    # OPEN: load parameter settings from a user-specified file
    def pfopen(self, event=None):
        """ Load the parameter settings from a user-specified file.  Any epar
        changes here should be coordinated with the corresponding tpar pfopen
        function. """
        raise NotImplementedError("EditParDialog is not to be used directly")


    def _getSaveAsFilter(self):
        """ Return a string to be used as the filter arg to the save file
            dialog during Save-As. Override for more specific behavior. """
        return "*.*"


    def _saveAsPreSave_Hook(self, fnameToBeUsed):
        """ Allow a subclass any specific checks right before the save. """
        return None


    def _saveAsPostSave_Hook(self, fnameToBeUsed):
        """ Allow a subclass any specific checks right after the save. """
        return None


    # SAVE AS: save the parameter settings to a user-specified file
    def saveAs(self, event=None):
        """ Save the parameter settings to a user-specified file.  Any
        changes here must be coordinated with the corresponding tpar save_as
        function. """

        self.debug('Clicked Save as...')
        # On Linux Pers..Dlg causes the cwd to change, so get a copy of current
        curdir = os.getcwd()

        # The user wishes to save to a different name
        writeProtChoice = self._writeProtectOnSaveAs
        if capable.OF_TKFD_IN_EPAR:
            # Prompt using native looking dialog
            fname = asksaveasfilename(parent=self.top,
                    title='Save Parameter File As',
                    defaultextension=self._defSaveAsExt,
                    initialdir=os.path.dirname(self._getSaveAsFilter()))
        else:
            # Prompt. (could use tkinter's FileDialog, but this one is prettier)
            # initWProtState is only used in the 1st call of a session
            from . import filedlg
            fd = filedlg.PersistSaveFileDialog(self.top,
                         "Save Parameter File As", self._getSaveAsFilter(),
                         initWProtState=writeProtChoice)
            if fd.Show() != 1:
                fd.DialogCleanup()
                os.chdir(curdir) # in case file dlg moved us
                return
            fname = fd.GetFileName()
            writeProtChoice = fd.GetWriteProtectChoice()
            fd.DialogCleanup()

        if not fname: return # canceled

        # First check the child parameters, aborting save if
        # invalid entries were encountered
        if self.checkSetSaveChildren():
            os.chdir(curdir) # in case file dlg moved us
            return

        # Run any subclass-specific steps right before the save
        self._saveAsPreSave_Hook(fname)

        # Verify all the entries (without save), keeping track of the invalid
        # entries which have been reset to their original input values
        self.badEntriesList = self.checkSetSaveEntries(doSave=False)

        # If there were invalid entries, prepare the message dialog
        if self.badEntriesList:
            ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                          self.taskName)
            if not ansOKCANCEL:
                os.chdir(curdir) # in case file dlg moved us
                return

        # If there were no invalid entries or the user says OK, finally
        # save to their stated file.  Since we have already processed the
        # bad entries, there should be none returned.
        mstr = "TASKMETA: task="+self.taskName+" package="+self.pkgName
        if self.checkSetSaveEntries(doSave=True, filename=fname, comment=mstr,
                                    set_ro=writeProtChoice,
                                    overwriteRO=True):
            os.chdir(curdir) # in case file dlg moved us
            raise Exception("Unexpected bad entries for: "+self.taskName)

        # Run any subclass-specific steps right after the save
        self._saveAsPostSave_Hook(fname)

        os.chdir(curdir) # in case file dlg moved us


    # EXECUTE: save the parameter settings and run the task
    def execute(self, event=None):

        self.debug('Clicked Execute')
        # first save the child parameters, aborting save if
        # invalid entries were encountered
        if self.checkSetSaveChildren():
            return

        # If we are only executing (no save and close) do so here and return
        if not self._saveAndCloseOnExec:
            # First check the parameter values
            self.badEntriesList = self.checkSetSaveEntries(doSave=False)
            # If there were invalid entries, show the message dialog
            if self.badEntriesList:
                ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                              self.taskName)
                if not ansOKCANCEL: return
            self.showStatus("Task "+self.taskName+" is running...", keep=2)
            self._executed = True # note for later use
            self.runTask()
            return

        # Now save the parameter values of the parent
        self.badEntriesList = self.checkSetSaveEntries()

        # If there were invalid entries in the parent epar dialog, prepare
        # the message dialog
        if self.badEntriesList:
            ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                          self.taskName)
            if not ansOKCANCEL: return

        # If there were no invalid entries or the user said OK

        # Save any GUI settings we care about since window is closing
        self._saveGuiSettings()

        # Remove the main epar window
        self.top.focus_set()
        self.top.withdraw()
        self.top.destroy()

        print("\nTask "+self.taskName+" is running...\n")

        # Run the task
        try:
            self._executed = True # note for later use
            self.runTask()
        finally:
            self.top.quit()

        # Declare the global variables so they can be updated
        global CHILDX
        global CHILDY

        # Reset to the start location
        CHILDX = PARENTX
        CHILDY = PARENTY


    # ABORT: abort this epar session
    def abort(self, event=None):

        # Declare the global variables so they can be updated
        global CHILDX
        global CHILDY

        # Reset to the start location
        CHILDX = PARENTX
        CHILDY = PARENTY

        # Give focus back to parent window and abort
        self.top.focus_set()
        self.top.withdraw()

        self._canceled = True # note for later use

        # Do not destroy the window, just hide it for now.
        # This is so EXECUTE will not get an error - properly use Mediator.
        #self.top.destroy()
        if not self.isChild:
            self.top.destroy()
            self.top.quit()


    # UNLEARN: unlearn all the parameters by setting their values
    # back to the system default
    def unlearn(self, event=None):

        self.debug('Clicked Unlearn')
        # Reset the values of the parameters
        self.unlearnAllEntries(self.top.f.canvas.entries)
        self.freshenFocus()


    # HTMLHELP: invoke the HTML help
    def htmlHelp(self, helpString=None, title=None, istask=False, tag=None):
        """ Pop up the help in a browser window.  By default, this tries to
        show the help for the current task.  With the option arguments, it can
        be used to show any help string. """
        # Check the help string.  If it turns out to be a URL, launch that,
        # if not, dump it to a quick and dirty tmp html file to make it
        # presentable, and pass that file name as the URL.
        if not helpString:
            helpString = self.getHelpString(self.pkgName+'.'+self.taskName)
        if not title:
            title = self.taskName
        lwr = helpString.lower()
        if lwr.startswith("http:") or lwr.startswith("https:") or \
           lwr.startswith("file:"):
            url = helpString
            if tag and url.find('#') < 0:
                url += '#'+tag
#           print('LAUNCHING: '+url) # DBG
            irafutils.launchBrowser(url, subj=title)
        else:
            # Write it to a temp HTML file to display
            (fd, fname) = tempfile.mkstemp(suffix='.html', prefix='editpar_')
            os.close(fd)
            f = open(fname, 'w')
            if istask and self._knowTaskHelpIsHtml:
                f.write(helpString)
            else:
                f.write('<html><head><title>'+title+'</title></head>\n')
                f.write('<body><h3>'+title+'</h3>\n')
                f.write('<pre>\n'+helpString+'\n</pre></body></html>')
            f.close()
            irafutils.launchBrowser("file://"+fname, subj=title)


    def _showAnyHelp(self, kind, tag=None):
        """ Invoke task/epar/etc. help and put the page in a window.
        This same logic is used for GUI help, task help, log msgs, etc. """

        # sanity check
        if kind not in ('epar', 'task', 'log'):
            raise ValueError('Unknown help kind: ' + str(kind))

        #-----------------------------------------
        # See if they'd like to view in a browser
        #-----------------------------------------
        if self._showHelpInBrowser or (kind == 'task' and
                                       self._knowTaskHelpIsHtml):
            if kind == 'epar':
                self.htmlHelp(helpString=self._appHelpString,
                              title='Parameter Editor Help')
            if kind == 'task':
                self.htmlHelp(istask=True, tag=tag)
            if kind == 'log':
                self.htmlHelp(helpString='\n'.join(self._msgHistory),
                              title=self._appName+' Event Log')
            return

        #-----------------------------------------
        # Now try to pop up the regular Tk window
        #-----------------------------------------
        wins = {'epar':self.eparHelpWin,
                'task':self.irafHelpWin,
                'log': self.logHistWin, }
        window = wins[kind]
        try:
            if window.state() != NORMAL:
                window.deiconify()
            window.tkraise()
            return
        except (AttributeError, TclError):
            pass

        #---------------------------------------------------------
        # That didn't succeed (window is still None), so build it
        #---------------------------------------------------------
        if kind == 'epar':
            self.eparHelpWin = self.makeHelpWin(self._appHelpString,
                                                title='Parameter Editor Help')
        if kind == 'task':
            # Acquire the task help as a string
            # Need to include the package name for the task to
            # avoid name conflicts with tasks from other packages. WJH
            self.irafHelpWin = self.makeHelpWin(self.getHelpString(
                                                self.pkgName+'.'+self.taskName))
        if kind == 'log':
            self.logHistWin = self.makeHelpWin('\n'.join(self._msgHistory),
                                               title=self._appName+' Event Log')


    def canceled(self):
        """ Did the user click Cancel? (or close us via the window manager) """
        return self._canceled


    def executed(self):
        """ Did the user click Execute? """
        return self._executed


    # Get the task help in a string
    def getHelpString(self, taskname):
        """ Provide a task-specific help string. """
        return self._taskParsObj.getHelpAsString()


    # Set up the help dialog (browser)
    def makeHelpWin(self, helpString, title="Parameter Editor Help Browser"):

        # Generate a new Toplevel window for the browser
        # hb = Toplevel(self.top, bg="SlateGray3")
        hb = Toplevel(self.top, bg=None)
        hb.title(title)
        hb.iconLabel = title

        # Set up the Menu Bar
        hb.menubar = Frame(hb, relief=RIDGE, borderwidth=0)
        hb.menubar.button = Button(hb.menubar, text="Close",
                                     relief=RAISED,
                                     command=hb.destroy)
        hb.menubar.button.pack()
        hb.menubar.pack(side=BOTTOM, padx=5, pady=5)

        # Define the Frame for the scrolling Listbox
        hb.frame = Frame(hb, relief=RIDGE, borderwidth=1)

        # Attach a vertical Scrollbar to the Frame
        hb.frame.vscroll = Scrollbar(hb.frame, orient=VERTICAL,
                 width=11, relief=SUNKEN, activerelief=RAISED,
                 takefocus=FALSE)

        # Define the Listbox and setup the Scrollbar
        hb.frame.list = Listbox(hb.frame,
                                relief=FLAT,
                                height=25,
                                width=80,
                                takefocus=FALSE,
                                selectmode=SINGLE,
                                selectborderwidth=0)
        hb.frame.list['yscrollcommand'] = hb.frame.vscroll.set

        hb.frame.vscroll['command'] = hb.frame.list.yview
        hb.frame.vscroll.pack(side=RIGHT, fill=Y)
        hb.frame.list.pack(side=TOP, expand=TRUE, fill=BOTH)
        hb.frame.pack(side=TOP, fill=BOTH, expand=TRUE)

        # Insert each line of the helpString onto the Frame
        listing = helpString.split('\n')
        for line in listing:

            # Filter the text *** DO THIS A BETTER WAY ***
            line = line.replace("\x0e", "")
            line = line.replace("\x0f", "")
            line = line.replace("\f", "")

            # Insert the text into the Listbox
            hb.frame.list.insert(END, line)

        # When the Listbox appears, the listing will be at the beginning
        y = hb.frame.vscroll.get()[0]
        hb.frame.list.yview(int(y))

        # enable Page Up/Down keys
        scroll = hb.frame.list.yview_scroll
        hb.bind('<Next>', lambda event, fs=scroll: fs(1, "pages"))
        hb.bind('<Prior>', lambda event, fs=scroll: fs(-1, "pages"))

        # Position this dialog relative to the parent
        hb.geometry("+%d+%d" % (self.top.winfo_rootx() + HELPX,
                                     self.top.winfo_rooty() + HELPY))
        return hb

    def validate(self):

        return 1


    def setAllEntriesFromParList(self, aParList, updateModel=False):
        """ Set all the parameter entry values in the GUI to the values
            in the given par list. If 'updateModel' is True, the internal
            param list will be updated to the new values as well as the GUI
            entries (slower and not always necessary). Note the
            corresponding TparDisplay method. """

        # Get model data, the list of pars
        theParamList = self._taskParsObj.getParList() # we may modify members

        if len(aParList) != len(theParamList):
            showwarning(message="Attempting to set parameter values from a "+ \
                        "list of different length ("+str(len(aParList))+ \
                        ") than the number shown here ("+ \
                        str(len(theParamList))+").  Be aware.",
                        title="Parameter List Length Mismatch")

        # LOOP THRU GUI PAR LIST
        for i in range(self.numParams):
            par = theParamList[i]
            if par.type == "pset":
                continue # skip PSET's for now
            gui_entry = self.entryNo[i]

            # Set the value in the paramList before setting it in the GUI
            # This may be in the form of a list, or an IrafParList (getValue)
            if isinstance(aParList, list):
                # Since "aParList" can have them in different order and number
                # than we do, we'll have to first find the matching param.
                found = False
                for newpar in aParList:
                    if newpar.name==par.name and newpar.scope==par.scope:
                        par.set(newpar.value) # same as .get(native=1,prompt=0)
                        found = True
                        break

                # Now see if newpar was found in our list
                if not found:
                    pnm = par.name
                    if len(par.scope): pnm = par.scope+'.'+par.name
                    raise UnfoundParamError('Error - Unfound Parameter! \n\n'+\
                      'Expected parameter "'+pnm+'" for task "'+ \
                      self.taskName+'". \nThere may be others...')

            else: # assume has getValue()
                par.set(aParList.getValue(par.name, native=1, prompt=0))

            # gui holds a str, but par.value is native; conversion occurs
            gui_entry.forceValue(par.value, noteEdited=False) # no triggers yet

        if updateModel:
            # Update the model values via checkSetSaveEntries
            self.badEntriesList = self.checkSetSaveEntries(doSave=False)

            # If there were invalid entries, prepare the message dialog
            if self.badEntriesList:
                self.processBadEntries(self.badEntriesList,
                                       self.taskName, canCancel=False)


    def unlearnAllEntries(self, master):
        """ Method to "unlearn" all the parameter entry values in the GUI
            and set the parameter back to the default value """
        for entry in self.entryNo:
            entry.unlearnValue()


    def getValue(self, name, scope=None, native=False):
        """ Return current par value from the GUI. This does not do any
        validation, and it it not necessarily the same value saved in the
        model, which is always behind the GUI setting, in time. This is NOT
        to be used to get all the values - it would not be efficient. """

        # Get model data, the list of pars
        theParamList = self._taskParsObj.getParList()

        # NOTE: If par scope is given, it will be used, otherwise it is
        # assumed to be unneeded and the first name-match is returned.
        fullName = basicpar.makeFullName(scope, name)

        # Loop over the parameters to find the requested par
        for i in range(self.numParams):
            par = theParamList[i] # IrafPar or subclass
            entry = self.entryNo[i] # EparOption or subclass
            if par.fullName() == fullName or \
               (scope is None and par.name == name):
                if native:
                    return entry.convertToNative(entry.choice.get())
                else:
                    return entry.choice.get()
        # We didn't find the requested par
        raise RuntimeError('Could not find par: "'+fullName+'"')


    # Read, save, and validate the entries
    def checkSetSaveEntries(self, doSave=True, filename=None, comment=None,
                            fleeOnBadVals=False, allowGuiChanges=True,
                            set_ro=False, overwriteRO=False):

        self.badEntries = []
        asNative = self._taskParsObj.knowAsNative()

        # Get model data, the list of pars
        theParamList = self._taskParsObj.getParList()

        # Loop over the parameters to obtain the modified information
        for i in range(self.numParams):

            par = theParamList[i] # IrafPar or subclass
            entry = self.entryNo[i] # EparOption or subclass
            # Cannot change an entry if it is a PSET, just skip
            if par.type == "pset":
                continue

            # get current state of par in the gui
            value = entry.choice.get()

            # Set new values for changed parameters - a bit tricky,
            # since changes that weren't followed by a return or
            # tab have not yet been checked.  If we eventually
            # use a widget that can check all changes, we will
            # only need to check the isChanged flag.
            if par.isChanged() or value != entry.previousValue:

                # CHECK: Verify the value. If its invalid (and allowGuiChanges),
                # the value will be converted to its original valid value.
                # Maintain a list of the reset values for user notification.
                # Always call entryCheck, no matter what type of _taskParsObj,
                # since entryCheck can do some basic type checking.
                failed = False
                if entry.entryCheck(repair=allowGuiChanges):
                    failed = True
                    self.badEntries.append([entry.name, value,
                                           entry.choice.get()])
                    if fleeOnBadVals: return self.badEntries
                # See if we need to do a more serious validity check
                elif self._taskParsObj.canPerformValidation():
                    # if we are planning to save in native type, test that way
                    if asNative:
                        try:
                            value = entry.convertToNative(value)
                        except:
                            failed = True
                            prev = entry.previousValue
                            self.badEntries.append([entry.name, value, prev])
                            if fleeOnBadVals: return self.badEntries
                            if allowGuiChanges: entry.choice.set(prev)
                    # now try the val in it's validator
                    if not failed:
                        valOK, prev = self._taskParsObj.tryValue(entry.name,
                                                        value, scope=par.scope)
                        if not valOK:
                            failed = True
                            self.badEntries.append([entry.name,str(value),prev])
                            if fleeOnBadVals: return self.badEntries
                            if allowGuiChanges: entry.choice.set(prev)

                # get value again in case it changed - this version IS valid
                value = entry.choice.get()
                if asNative: value = entry.convertToNative(value)

                # SET: Update the task parameter (also does the conversion
                # from string)
                self._taskParsObj.setParam(par.name, value, scope=par.scope,
                                           check=0, idxHint=i)

        # SAVE: Save results to the given file
        if doSave:
            self.debug('Saving...')
            out = self._doActualSave(filename, comment, set_ro=set_ro,
                                     overwriteRO=overwriteRO)
            if len(out):
                self.showStatus(out, keep=2) # inform user on saves

        return self.badEntries


    def _doActualSave(self, fname, comment, set_ro=False):
        """ Here we call the method on the _taskParsObj to do the actual
        save.  Return a string result to be printed to the screen. """
        # do something like
#       return self._taskParsObj.saveParList(filename=fname, comment=comment)
        raise NotImplementedError("EditParDialog is not to be used directly")


    def checkSetSaveChildren(self, doSave=True):
        """Check, then set, then save the parameter settings for
        all child (pset) windows.

        Prompts if any problems are found.  Returns None
        on success, list of bad entries on failure.
        """
        if self.isChild:
            return

        # Need to get all the entries and verify them.
        # Save the children in backwards order to coincide with the
        # display of the dialogs (LIFO)
        for n in range (len(self.top.childList)-1, -1, -1):
            self.badEntriesList = self.top.childList[n]. \
                                  checkSetSaveEntries(doSave=doSave)
            if self.badEntriesList:
                ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                              self.top.childList[n].taskName)
                if not ansOKCANCEL:
                    return self.badEntriesList
            # If there were no invalid entries or the user says OK,
            # close down the child and increment to the next child
            self.top.childList[n].top.focus_set()
            self.top.childList[n].top.withdraw()
            del self.top.childList[n]
        # all windows saved successfully
        return


    def _pushMessages(self):
        """ Internal callback used to make sure the msg list keeps moving. """
        # This continues to get itself called until no msgs are left in list.
        self.showStatus('')
        if len(self._statusMsgsToShow) > 0:
            self.top.after(200, self._pushMessages)


    def debug(self, msg):
        """ Convenience function.  Use showStatus without puting into GUI. """
        self.showStatus(msg, cat=DBG)


    def showStatus(self, msg, keep=0, cat=None):
        """ Show the given status string, but not until any given delay from
            the previous message has expired. keep is a time (secs) to force
            the message to remain without being overwritten or cleared. cat
            is a string category used only in the historical log. """
        # prep it, space-wise
        msg = msg.strip()
        if len(msg) > 0:
            # right here is the ideal place to collect a history of messages
            forhist = msg
            if cat: forhist = '['+cat+'] '+msg
            forhist = time.strftime("%a %H:%M:%S")+': '+forhist
            self._msgHistory.append(forhist)
            # now set the spacing
            msg = '  '+msg

        # stop here if it is a category not shown in the GUI
        if cat == DBG:
            return

        # see if we can show it
        now = time.time()
        if now >= self._leaveStatusMsgUntil: # we are clear, can show a msg
            # first see if this msg is '' - if so we will show an important
            # waiting msg instead of the '', and then pop it off our list
            if len(msg) < 1 and len(self._statusMsgsToShow) > 0:
                msg, keep = self._statusMsgsToShow[0] # overwrite both args
                del self._statusMsgsToShow[0]
            # now actuall print the status out to the status widget
            self.top.status.config(text = msg)
            # reset our delay flag
            self._leaveStatusMsgUntil = 0
            if keep > 0:
                self._leaveStatusMsgUntil = now + keep
        else:
            # there is a previous message still up, is this one important?
            if len(msg) > 0 and keep > 0:
                # Uh-oh, this is an important message that we don't want to
                # simply skip, but on the other hand we can't show it yet...
                # So we add it to _statusMsgsToShow and show it later (asap)
                if (msg,keep) not in self._statusMsgsToShow:
                    if len(self._statusMsgsToShow) < 7:
                        self._statusMsgsToShow.append( (msg,keep) ) # tuple
                        # kick off timer loop to get this one pushed through
                        if len(self._statusMsgsToShow) == 1:
                            self._pushMessages()
                    else:
                        # should never happen, but just in case
                        print("Lost message!: "+msg+" (too far behind...)")

    # Run the task
    def runTask(self):

        # Use the run method of the IrafTask class
        # Set mode='h' so it does not prompt for parameters (like IRAF epar)
        # Also turn on parameter saving
        try:
            self._taskParsObj.run(mode='h', _save=1)
        except taskpars.NoExecError as nee:  # catch only this, let all else thru
            showwarning(message="No way found to run task\n\n"+\
                        str(nee), title="Can Not Run Task")
