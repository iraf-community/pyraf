"""module 'epar.py' -- main module for generating the epar task editor

$Id$

M.D. De La Pena, 2000 February 04
"""
# System level modules
from Tkinter import *
from types import *
from tkMessageBox import askokcancel
import os, sys, string

# PyRAF modules
# For some reason I do not understand, it is necessary to import
# openglgcur here even though it is not used.  If omitted it dies during
# startup. (rlw)
# import iraf, irafpar, iraftask, irafhelp, cStringIO
import iraf, irafpar, iraftask, irafhelp, openglgcur, cStringIO
from irafglobals import pyrafDir, userWorkingHome

from eparoption import *

# Constants
MINVIEW     = 500
MINPARAMS   = 25
INPUTWIDTH  = 10
VALUEWIDTH  = 21
PROMPTWIDTH = 55

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
HELPY   = 0

def epar(taskName, parent = None, isChild = 0):

    EparDialog(taskName, parent, isChild)

class EparDialog:
    def __init__(self, taskName, parent = None, isChild = 0,
                 title = "PyRAF Parameter Editor", childList = None):

        # Get the Iraftask object to determine the package name
        if isinstance(taskName, iraftask.IrafTask):
            self.taskObject = taskName
        else:
            self.taskName   = string.lower(taskName)
            self.taskObject = iraf.getTask(taskName)

        # Now go back and ensure we have the full taskname
        self.taskName   = self.taskObject.getName()
        self.pkgName    = self.taskObject.getPkgname()
        self.paramList  = self.taskObject.getParList(docopy=1)

        # Ignore the last parameter which is $nargs
        self.numParams  = len(self.paramList) - 1

        # Get default parameter values for unlearn
        self.getDefaultParamList()

        # Create the root window as required, but hide it
        self.parent = parent
        if (self.parent == None):
            root = Tk()
            root.withdraw()

        # Track whether this is a parent or child window
        self.isChild = isChild

        # Set up a color for the background to differeniate parent and child
        if self.isChild:
        #    self.bkgColor  = "LightSteelBlue"
            self.iconLabel = "EPAR Child"
        else:
        #    self.bkgColor  = "SlateGray3"
            self.iconLabel = "EPAR Parent"
        self.bkgColor = None

        # Generate the top epar window
        self.top = Toplevel(self.parent, bg = self.bkgColor, visual="best")
        self.top.title(title)
        self.top.iconname(self.iconLabel)

        # Read in the epar options database file
        optfile = "epar.optionDB"
        try:
             # User's current directory
             self.top.option_readfile(os.path.join(os.curdir,optfile))
        except TclError:
            try:
                 # User's startup directory
                 self.top.option_readfile(os.path.join(userWorkingHome,optfile))
            except TclError:
                 # PyRAF default
                 self.top.option_readfile(os.path.join(pyrafDir,optfile))

        # Disable interactive resizing
        self.top.resizable(width = FALSE, height = FALSE)

        # Create an empty list to hold child EparDialogs
        # *** Not a good way, REDESIGN with Mediator!
        # Also, build the parent menu bar
        if (self.parent == None):
            self.top.childList = []
        elif childList is not None:
            # all children share a list
            self.top.childList = childList

        # Build the EPAR menu bar
        self.makeMenuBar(self.top)

        # Create a spacer
        Frame(self.top, bg = self.bkgColor, height = 10).pack(side = TOP,
              fill = X)

        # Print the package and task names
        self.printNames(self.top, self.taskName, self.pkgName)

        # Insert a spacer between the static text and the buttons
        Frame(self.top, bg = self.bkgColor, height = 15).pack(side = TOP,
              fill = X)

        # Set control buttons at the top of the frame
        self.buttonBox(self.top)

        # Insert a spacer between the static text and the buttons
        Frame(self.top, bg = self.bkgColor, height = 15).pack(side = TOP,
              fill = X)

        # Set up an information Frame at the bottom of the EPAR window
        # RESIZING is currently disabled.
        # Do this here so when resizing to a smaller sizes, the parameter
        # panel is reduced - not the information frame.
        self.top.status = Label(self.top, text = "", relief = SUNKEN,
                           borderwidth = 1, anchor = W)
        self.top.status.pack(side = BOTTOM, fill = X, padx = 0, pady = 3,
                             ipady = 3)

        # Set up a Frame to hold a scrollable Canvas
        self.top.f = Frame(self.top, relief = RIDGE, borderwidth = 1)

        # Overlay a Canvas which will hold a Frame
        self.top.f.canvas = Canvas(self.top.f, width = 100, height = 100)

        # Only build the scrollbar, if there is something to scroll
        self.isScrollable = "no"
        if (self.numParams > MINPARAMS):

            # Attach a vertical Scrollbar to the Frame/Canvas
            self.top.f.vscroll = Scrollbar(self.top.f, orient = VERTICAL,
                 width = 11, relief = SUNKEN, activerelief = RAISED,
                 takefocus = FALSE)
            self.top.f.canvas['yscrollcommand']  = self.top.f.vscroll.set
            self.top.f.vscroll['command'] = self.top.f.canvas.yview

            # Pack the Scrollbar
            self.top.f.vscroll.pack(side = RIGHT, fill = Y)

            # Reset the variable used to reveal the canvas on Tab
            self.isScrollable = "yes"

        # Pack the Frame and Canvas
        self.top.f.canvas.pack(side = TOP, expand = TRUE, fill = BOTH)
        self.top.f.pack(side = TOP, fill = BOTH, expand = TRUE)

        # Define a Frame to contain the parameter information
        self.top.f.canvas.entries = Frame(self.top.f.canvas)

        # Generate the window to hold the Frame which sits on the Canvas
        cWindow = self.top.f.canvas.create_window(0, 0,
                           anchor = NW,
                           window = self.top.f.canvas.entries)

        # Insert a spacer between the Canvas and the information frame
        Frame(self.top, bg = self.bkgColor, height = 4).pack(side = TOP,
              fill = X)

        # The parent has the control, unless there are children
        # Fix the geometry of where the windows first appear on the screen
        if (self.parent == None):
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
        self.makeEntries(self.top.f.canvas.entries, self.top.status)

        # Force an update of the entry Frame
        self.top.f.canvas.entries.update()

        # Determine the size of the entry Frame
        width  = self.top.f.canvas.entries.winfo_width()
        height = self.top.f.canvas.entries.winfo_height()

        # Reconfigure the Canvas size based on the Frame.
        if (self.numParams <= MINPARAMS):
            viewHeight = height
        else:

            # Set the minimum display
            viewHeight = MINVIEW

            # Scrollregion is based upon the full size of the entry Frame
            self.top.f.canvas.config(scrollregion = (0, 0, width, height))

            # Smooth scroll
            self.top.f.canvas.config(yscrollincrement = 50)

        # Set the actual viewable region for the Canvas
        self.top.f.canvas.config(width = width, height = viewHeight)

        # Force an update of the Canvas
        self.top.f.canvas.update()

        # Associate deletion of the main window to a Abort
        self.top.protocol("WM_DELETE_WINDOW", self.abort)

        # run the mainloop
        if not self.isChild:
            self.top.mainloop()

    def getDefaultParamList(self):

        # Obtain the default parameter list
        dlist = self.taskObject.getDefaultParList()
        if len(dlist) != len(self.paramList):
            # whoops, lengths don't match
            raise ValueError("Mismatch between default, current par lists"
                " for task %s (try unlearn)" % self.taskName)
        dict = {}
        for par in dlist:
            dict[par.name] = par

        # Build default list sorted into same order as current list
        try:
            dsort = []
            for par in self.paramList:
                dsort.append(dict[par.name])
        except KeyError:
            raise ValueError("Mismatch between default, current par lists"
                " for task %s (try unlearn)" % self.taskName)
        self.defaultParamList = dsort

    # Method to create the parameter entries
    def makeEntries(self, master, statusBar):

        # Determine the size of the longest input string
        inputLength = INPUTWIDTH
        for i in range(self.numParams):
            inputString = self.paramList[i].name
            if (len(inputString) > inputLength):
                inputLength = len(inputString)

        # Set up the field widths
        # Allow extra spaces for buffer and in case the longest parameter
        # has the hidden parameter indicator
        self.fieldWidths = {}
        self.fieldWidths['inputWidth']  = inputLength + 4
        self.fieldWidths['valueWidth']  = VALUEWIDTH
        self.fieldWidths['promptWidth'] = PROMPTWIDTH

        # Loop over the parameters to create the entries
        self.entryNo = [None] * self.numParams
        for i in range(self.numParams):

            # If there is an enumerated list, regardless of datatype, use
            # the EnumEparOption
            if (self.paramList[i].choice != None):
                self.entryNo[i] = EnumEparOption(master, statusBar,
                                  self.paramList[i], self.defaultParamList[i],
                                  self.isScrollable, self.fieldWidths)

            # PSET
            elif (self.paramList[i].type == "pset"):
                 self.entryNo[i] = PsetEparOption(master, statusBar,
                                   self.paramList[i], self.defaultParamList[i],
                                   self.isScrollable, self.fieldWidths)

            # *GCUR
            #elif (self.paramList[i].type == "*gcur"):
            #    self.entryNo[i] = GcurEparOption(master, statusBar,
            #                      self.paramList[i], self.defaultParamList[i],
            #                      self.isScrollable, self.fieldWidths)

            # *UKEY
            #elif (self.paramList[i].type == "*ukey"):
            #    self.entryNo[i] = UkeyEparOption(master, statusBar,
            #                      self.paramList[i], self.defaultParamList[i],
            #                      self.isScrollable, self.fieldWidths)

            # BOOLEAN
            elif (self.paramList[i].type == 'b'):
                self.entryNo[i] = BooleanEparOption(master, statusBar,
                                  self.paramList[i], self.defaultParamList[i],
                                  self.isScrollable, self.fieldWidths)

            # STRING (s, f, struct, *imcur, *struct, *s, *i)
            elif (self.paramList[i].type in irafpar._string_types):
                self.entryNo[i] = StringEparOption(master, statusBar,
                                  self.paramList[i], self.defaultParamList[i],
                                  self.isScrollable, self.fieldWidths)

            # REAL
            elif (self.paramList[i].type in irafpar._real_types):
                self.entryNo[i] = RealEparOption(master, statusBar,
                                  self.paramList[i], self.defaultParamList[i],
                                  self.isScrollable, self.fieldWidths)

            # INT
            elif (self.paramList[i].type == 'i'):
                self.entryNo[i] = IntEparOption(master, statusBar,
                                  self.paramList[i], self.defaultParamList[i],
                                  self.isScrollable, self.fieldWidths)

            else:
                self.entryNo[i] = StringEparOption(master, statusBar,
                                  self.paramList[i], self.defaultParamList[i],
                                  self.isScrollable, self.fieldWidths)
                # Need to keep commented out until *gcur and such are resolved
                #raise SyntaxError("Cannot handle parameter type" + type)


    # Method to print the package and task names and to set up the menu
    # button for the choice of the display for the IRAF help page
    def printNames(self, top, taskName, pkgName):

        topbox  = Frame(top, bg = self.bkgColor)
        textbox = Frame(topbox, bg = self.bkgColor)
        helpbox = Frame(topbox, bg = self.bkgColor)

        # Set up the information strings
        packString = "  Package = " + string.upper(pkgName)
        Label(textbox, text = packString, bg = self.bkgColor).pack(side = TOP,
              anchor = W)

        taskString = "       Task = " + string.upper(taskName)
        Label(textbox, text = taskString, bg = self.bkgColor).pack(side = TOP,
              anchor = W)
        textbox.pack(side = LEFT, anchor = W)

        topbox.pack(side = TOP, expand = TRUE, fill = X)

    # Method to set up the parent menu bar
    def makeMenuBar(self, top):

        menubar = Frame(top, bd = 1, relief = GROOVE)

        # Generate the menus
        fileMenu = self.makeFileMenu(menubar)

        # When redesigned, optionsMenu should only be on the parent
        #if not self.isChild:
        #    optionsMenu = self.makeOptionsMenu(menubar)
        optionsMenu = self.makeOptionsMenu(menubar)

        menubar.pack(fill = X)


    # Method to generate a "File" menu
    def makeFileMenu(self, menubar):

        fileButton = Menubutton(menubar, text = 'File')
        fileButton.pack(side = LEFT, padx = 2)

        fileButton.menu = Menu(fileButton, tearoff = 0)

        if not self.isChild:
            fileButton.menu.add_command(label = "Execute", command=self.execute)

        fileButton.menu.add_command(label = "Save",    command=self.quit)
        fileButton.menu.add_command(label = "Unlearn", command=self.unlearn)
        fileButton.menu.add_separator()
        fileButton.menu.add_command(label = "Help",    command=self.setHelpViewer)
        fileButton.menu.add_separator()
        fileButton.menu.add_command(label = "Abort/Exit", command=self.abort)

        # Associate the menu with the menu button
        fileButton["menu"] = fileButton.menu

        return fileButton

    # Method to generate the "Options" menu for the parent EPAR only
    def makeOptionsMenu(self, menubar):

        # Set up the menu for the HELP viewing choice
        self.helpChoice = StringVar()
        self.helpChoice.set("WINDOW")

        optionButton = Menubutton(menubar, text = "Options")
        optionButton.pack(side = LEFT, padx = 2)

        optionButton.menu = Menu(optionButton, tearoff = 0)

        optionButton.menu.add_radiobutton(label = "Display Help in a Window",
                                          value    = "WINDOW",
                                          variable = self.helpChoice)
        optionButton.menu.add_radiobutton(label = "Display Help in a Browser",
                                          value    = "BROWSER",
                                          variable = self.helpChoice)

        # Associate the menu with the menu button
        optionButton["menu"] = optionButton.menu

        return optionButton


    # Method to set up the action buttons
    # Create the buttons in an order for good navigation
    def buttonBox(self, top):

        box = Frame(top, bg = self.bkgColor, bd = 1, relief = SUNKEN)

        # When the Button is exited, the information clears, and the
        # Button goes back to the nonactive color.
        top.bind("<Leave>", self.clearInfo)

        # Determine if the EXECUTE button should be present
        if not self.isChild:
            # Execute the task
            buttonExecute = Button(box, text = "EXECUTE",
                                   relief = RAISED, command = self.execute)
            buttonExecute.pack(side = LEFT, padx = 5, pady = 7)
            buttonExecute.bind("<Enter>", self.printExecuteInfo)

        # Save the parameter settings and exit from epar
        buttonQuit = Button(box, text = "SAVE",
                            relief = RAISED, command = self.quit)
        buttonQuit.pack(side = LEFT, padx = 5, pady = 7)
        buttonQuit.bind("<Enter>", self.printQuitInfo)

        # Unlearn all the parameter settings (set back to the defaults)
        buttonUnlearn = Button(box, text = "UNLEARN",
                            relief = RAISED, command = self.unlearn)
        buttonUnlearn.pack(side = LEFT, padx = 5, pady = 7)
        buttonUnlearn.bind("<Enter>", self.printUnlearnInfo)

        # Abort this edit session.  Currently, if an UNLEARN has already
        # been done, the UNLEARN is kept.
        buttonAbort = Button(box, text = "ABORT",
                              relief = RAISED, command = self.abort)
        buttonAbort.pack(side = LEFT, padx = 5, pady = 7)
        buttonAbort.bind("<Enter>", self.printAbortInfo)

        # Generate the a Help button
        buttonHelp = Button(box, text = "HELP",
                            relief = RAISED, command = self.setHelpViewer)
        buttonHelp.pack(side = RIGHT, padx = 5, pady = 7)
        buttonHelp.bind("<Enter>", self.printHelpInfo)

        box.pack(fill = X, expand = TRUE)


    # Determine which method of displaying the IRAF help pages was
    # chosen by the user.  WINDOW displays in a task generated scrollable
    # window.  BROWSER invokes the STSDAS HTML help pages and displays
    # in a browser.
    def setHelpViewer(self, event = None):

        value = self.helpChoice.get()
        if value == "WINDOW":
            self.help()
        else:
            self.htmlHelp()


    #
    # Define flyover help text associated with the action buttons
    #

    def clearInfo(self, event):
        self.top.status.config(text = "")

    def printHelpViewInfo(self, event):
        self.top.status.config(text =
             " Choice of display for the IRAF help page: a window or a browser")

    def printHelpInfo(self, event):
        self.top.status.config(text =
             " Display the IRAF help page")

    def printUnlearnInfo(self, event):
        self.top.status.config(text =
             " Set all parameter values to system default settings")

    def printQuitInfo(self, event):
        self.top.status.config(text =
             " Save the current entries and exit this edit session")

    def printAbortInfo(self, event):
        self.top.status.config(text = " Abort this edit session")

    def printExecuteInfo(self, event):
        self.top.status.config(text =
             " Execute the task and exit this edit session")


    # Process invalid input values and invoke a query dialog
    def processBadEntries(self, badEntriesList, taskname):

        badEntriesString = "Task " + string.upper(taskname) + " --\n" \
            "Invalid values have been entered.\n\n" \
            "Parameter   Bad Value   Reset Value\n"

        for i in range (len(badEntriesList)):
            badEntriesString = badEntriesString + \
                "%15s %10s %10s\n" % (badEntriesList[i][0], \
                badEntriesList[i][1], badEntriesList[i][2])

        badEntriesString = badEntriesString + "\nOK to continue using"\
            " the reset\nvalues or cancel to re-enter\nvalues?\n"

        # Invoke the modal message dialog
        return (askokcancel("Notice", badEntriesString))


    # QUIT: save the parameter settings and exit epar
    def quit(self, event = None):

        # first save the child parameters, aborting save if
        # invalid entries were encountered
        if self.saveChildren():
            return

        # Save all the entries and verify them, keeping track of the
        # invalid entries which have been reset to their original input values
        self.badEntriesList = self.saveEntries()

        # If there were invalid entries, prepare the message dialog
        if (self.badEntriesList):
            ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                          self.taskName)
            if not ansOKCANCEL:
                return

        # If there were no invalid entries or the user says OK

        # Remove the main epar window
        self.top.focus_set()
        self.top.withdraw()

        # Do not destroy the window, just hide it for now.
        # This is so EXECUTE will not get an error - properly use Mediator.
        #self.top.destroy()

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


    # EXECUTE: save the parameter settings and run the task
    def execute(self, event=None):

        # first save the child parameters, aborting save if
        # invalid entries were encountered
        if self.saveChildren():
            return

        # Now save the parameter values of the parent
        self.badEntriesList = self.saveEntries()

        # If there were invalid entries in the parent epar dialog, prepare
        # the message dialog
        ansOKCANCEL = FALSE
        if (self.badEntriesList):
            ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                          self.taskName)
            if not ansOKCANCEL:
                return

        # If there were no invalid entries or the user says OK

        # Remove the main epar window
        self.top.focus_set()
        self.top.withdraw()
        self.top.destroy()

        print "\nTask %s is running...\n" % self.taskName

        # Run the task
        try:
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
    def abort(self, event = None):

        # Declare the global variables so they can be updated
        global CHILDX
        global CHILDY

        # Reset to the start location
        CHILDX = PARENTX
        CHILDY = PARENTY

        # Give focus back to parent window and abort
        self.top.focus_set()
        self.top.withdraw()

        # Do not destroy the window, just hide it for now.
        # This is so EXECUTE will not get an error - properly use Mediator.
        #self.top.destroy()

        if not self.isChild:
            self.top.destroy()
            self.top.quit()


    # UNLEARN: unlearn all the parameters by setting their values
    # back to the system default
    def unlearn(self, event = None):

        ## This sets the memory objects back to the defaults
        #self.taskObject.unlearn()

        # Reset the view of the parameters
        self.unlearnAllEntries(self.top.f.canvas.entries)


    # HTMLHELP: invoke the HTML help
    def htmlHelp(self, event = None):

        # Invoke the STSDAS HTML help
        irafhelp.help(self.taskName, html = 1)


    # HELP: invoke help and put the page in a window
    def help(self, event = None):

        # Acquire the IRAF help as a string
        self.helpString = self.getHelpString(self.taskName)
        self.helpBrowser(self.helpString)


    # Get the IRAF help in a string (RLW)
    def getHelpString(self, taskname):

        fh = cStringIO.StringIO()
        iraf.system.help(taskname, page = 0, Stdout = fh, Stderr = fh)
        result = fh.getvalue()
        fh.close()
        return result

    # Set up the help dialog (browser)
    def helpBrowser(self, helpString):

        # Generate a new Toplevel window for the browser
        #self.hb = Toplevel(self.top, bg = "SlateGray3")
        self.hb = Toplevel(self.top, bg = None)
        self.hb.title("IRAF Help Browser")

        # Set up the Menu Bar
        self.menubar = Frame(self.hb, relief = RIDGE, borderwidth = 0)
        self.menubar.button = Button(self.menubar, text = "QUIT",
                                     relief  = RAISED,
                                     command = self.hbQuit)
        self.menubar.button.pack(side = LEFT)
        self.menubar.pack(side = TOP, anchor = W, padx = 5, pady = 5)

        # Define the Frame for the scrolling Listbox
        self.hb.frame = Frame(self.hb, relief = RIDGE, borderwidth = 1)

        # Attach a vertical Scrollbar to the Frame
        self.hb.frame.vscroll = Scrollbar(self.hb.frame, orient = VERTICAL,
                 width = 11, relief = SUNKEN, activerelief = RAISED,
                 takefocus = FALSE)

        # Define the Listbox and setup the Scrollbar
        self.hb.frame.list = Listbox(self.hb.frame,
                                     relief            = FLAT,
                                     height            = 25,
                                     width             = 80,
                                     selectmode        = SINGLE,
                                     selectborderwidth = 0)
        self.hb.frame.list['yscrollcommand']  = self.hb.frame.vscroll.set

        self.hb.frame.vscroll['command'] = self.hb.frame.list.yview
        self.hb.frame.vscroll.pack(side = RIGHT, fill = Y)
        self.hb.frame.list.pack(side = TOP, expand = TRUE, fill = BOTH)
        self.hb.frame.pack(side = TOP, fill = BOTH, expand = TRUE)

        # Insert each line of the helpString onto the Frame
        listing = string.split(helpString, '\n')
        for line in listing:

            # Filter the text *** DO THIS A BETTER WAY ***
            line = string.replace(line, "\x0e", "")
            line = string.replace(line, "\x0f", "")
            line = string.replace(line, "\f", "")

            # Insert the text into the Listbox
            self.hb.frame.list.insert(END, line)

        # When the Listbox appears, the listing will be at the beginning
        y = self.hb.frame.vscroll.get()[0]
        self.hb.frame.list.yview(int(y))

        # Position this dialog relative to the parent
        self.hb.geometry("+%d+%d" % (self.top.winfo_rootx() + HELPX,
                                     self.top.winfo_rooty() + HELPY))

    # QUIT: Quit the help browser window
    def hbQuit(self, event = None):

        self.hb.focus_set()
        self.hb.destroy()


    def validate(self):

        return 1


    # Method to "unlearn" all the parameter entry values in the GUI
    # and set the parameter back to the default value
    def unlearnAllEntries(self, master):
        for entry in self.entryNo:
            entry.unlearnValue()


    # Read, save, and validate the entries
    def saveEntries(self):

        self.badEntries = []

        # Loop over the parameters to obtain the modified information
        for i in range(self.numParams):

            par = self.paramList[i]
            entry = self.entryNo[i]
            # Cannot change an entry if it is a PSET, just skip
            if par.type == "pset":
                continue

            value = entry.choice.get()

            # Set new values for changed parameters - a bit tricky,
            # since changes that weren't followed by a return or
            # tab have not yet been checked.  If we eventually
            # use a widget that can check all changes, we will
            # only need to check the isChanged flag.
            if par.isChanged() or value != entry.previousValue:
                # Verify the value is valid. If it is invalid,
                # the value will be converted to its original valid value.
                # Maintain a list of the reset values for user notification.
                resetValue = entry.entryCheck(event = None)
                if (resetValue != None):
                   self.badEntries.append(resetValue)

                # Determine the type of entry variable
                classType = entry.choiceClass

                # get value again in case it changed
                value = entry.choice.get()

                # Update the task parameter (also does the conversion
                # from string)
                self.taskObject.setParam(par.name, value)

        # save results to the uparm directory
        self.taskObject.save()

        return self.badEntries

    def saveChildren(self):
        """Save the parameter settings for all child (pset) windows.

        Prompts if any problems are found.  Returns None
        on success, list of bad entries on failure.
        """
        if self.isChild:
            return

        # Need to get all the entries and verify them.
        # Save the children in backwards order to coincide with the
        # display of the dialogs (LIFO)
        for n in range (len(self.top.childList)-1, -1, -1):
            self.badEntriesList = self.top.childList[n].saveEntries()
            if (self.badEntriesList):
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

    # Run the task
    def runTask(self):

        # Use the run method of the IrafTask class
        # Set mode='h' so it does not prompt for parameters (like IRAF epar)
        # Also turn on parameter saving
        self.taskObject.run(mode='h', _save=1)
