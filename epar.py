"""module 'epar.py' -- main module for generating the epar task editor

$Id$

M.D. De La Pena, 2000 February 04
"""
# System level modules
from Tkinter import *
from types import *
import os, sys, string

# PYRAF modules
import iraf, irafpar, iraftask, irafhelp, irafgcur, irafukey, cStringIO
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

# CHILD[XY] is a PSET window
CHILDX  = 600
CHILDY  = 0

# HELP[XY] is for the help as displayed in a window
HELPX   = 300
HELPY   = 0

def epar(taskName, parent = None, isChild = "no"):

    EparDialog(taskName, parent, isChild) 

class EparDialog:
    def __init__(self, taskName, parent = None, isChild = "no", 
                 title = "PYRAF Parameter Editor"):

        # Declare the global variables so they can be updated
        global CHILDX
        global CHILDY

        # Create the root window as required, but hide it
        self.parent = parent
        if (self.parent == None):
            root = Tk()
            root.withdraw()

        # Track whether this is a parent or child window
        self.isChild = isChild

        # Set up a color for the background to differeniate parent and child
        if (self.isChild == "yes"):
            self.bkgColor  = "LightSteelBlue"
            self.iconLabel = "EPAR Child"
        else:
            self.bkgColor  = "SlateGray3"
            self.iconLabel = "EPAR Parent"

        # Generate the top epar window
        self.top = Toplevel(self.parent, bg = self.bkgColor) 
        self.top.title(title)
        self.top.iconname(self.iconLabel)

        # Disable interactive resizing
        self.top.resizable(width = FALSE, height = FALSE)

        # Create an empty list to hold child EparDialogs
        # *** Not a good way, REDESIGN with Mediator!
        # Also, build the parent menu bar
        if (self.parent == None):
            self.top.childList = []

        # Build the EPAR menu bar
        self.makeMenuBar(self.top, self.isChild)

        # Get the Iraftask object to determine the package name
        if isinstance(taskName, iraftask.IrafTask):
            self.taskObject = taskName
        else:
            self.taskName   = string.lower(taskName)
            self.taskObject = iraf.getTask(taskName)

        # Now go back and ensure we have the full taskname
        self.taskName   = self.taskObject.getName()
        self.pkgName    = self.taskObject.getPkgname()
        self.paramList  = self.taskObject.getParList()

        # Obtain the default parameter list - THIS IS NOT A GOOD WAY. OK NOW
        self.defaultParamList = self.taskObject._defaultParList.getParList()

        # Ignore the last parameter which is $nargs
        self.numParams  = len(self.paramList) - 1

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

        # Set up an information Frame after the spacer
        self.top.status = Label(self.top, text = "", relief = SUNKEN,
                           borderwidth = 1, anchor = W)
        self.top.status.pack(side = BOTTOM, fill = X, padx = 0, pady = 3,
                             ipady = 3) 

        # The parent has the control, unless there are children
        # Fix the geometry of where the windows first appear on the screen
        if (self.parent == None):
            #self.top.grab_set()

            # Position this dialog relative to the parent
            self.top.geometry("+%d+%d" % (PARENTX, PARENTY))
        else:
            #self.parent.grab_release()
            #self.top.grab_set()

            CHILDX = CHILDX - 100
            CHILDY = CHILDY + 150

            # Position this dialog relative to the parent
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
        if (self.isChild == "no"):
            self.top.mainloop()


    # Method to create the parameter entries
    def makeEntries(self, master, statusBar):

        # Determine the size of the longest input string
        inputLength = INPUTWIDTH
        for i in range(self.numParams):
            inputString = self.paramList[i].get(field = "p_name", 
                          native = 0, prompt = 0)
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
                                   self.paramList[i],
                                   self.isScrollable, self.fieldWidths)

            # *GCUR 
            #elif (self.paramList[i].type == "*gcur"):
            #    self.entryNo[i] = GcurEparOption(master, statusBar,
            #                      self.paramList[i],
            #                      self.isScrollable, self.fieldWidths)

            # *UKEY
            #elif (self.paramList[i].type == "*ukey"):
            #    self.entryNo[i] = UkeyEparOption(master, statusBar,
            #                      self.paramList[i],
            #                      self.isScrollable, self.fieldWidths)

            # BOOLEAN
            elif (self.paramList[i].type == 'b'):
                self.entryNo[i] = BooleanEparOption(master, statusBar,
                                  self.paramList[i],
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

        """
        # Set up the menu for the HELP viewing choice
        self.helpChoice = StringVar()
        self.helpChoice.set("WINDOW")

        # Generate the a Help button with a menu.  Choice of help page
        # displayed in another window or in a browser
        buttonHelpView = Menubutton(helpbox,
                                    relief       = RAISED,           
                                    text         = self.helpChoice.get(),
                                    textvariable = self.helpChoice,
                                    padx         = 6,
                                    pady         = 6,
                                    indicatoron  = 1) 

        buttonHelpView.menu = Menu(buttonHelpView,  
                                   tearoff    = 0,
                                   background = "white",
                                   activebackground = "gainsboro")

        # Set up the menu options
        buttonHelpView.menu.add_radiobutton(label = "Display Help in a window",
                                            value    = "WINDOW",
                                            variable = self.helpChoice,
                                            indicatoron = 0)
        buttonHelpView.menu.add_radiobutton(label = "Display Help in a browser",
                                            value    = "BROWSER",
                                            variable = self.helpChoice,
                                            indicatoron = 0)

        # set up a pointer from the menubutton back to the menu
        buttonHelpView['menu'] = buttonHelpView.menu

        buttonHelpView.pack(side = RIGHT, anchor = E, padx = 5, pady = 5)
        helpbox.pack(side = RIGHT, anchor = E)
        topbox.pack(side = TOP, expand = TRUE, fill = X)

        buttonHelpView.bind("<Enter>", self.printHelpViewInfo)
        """

        topbox.pack(side = TOP, expand = TRUE, fill = X)

    # Method to set up the parent menu bar
    def makeMenuBar(self, top, isChild):

        menubar = Frame(top, bd = 1, relief = GROOVE)

        # Generate the menus
        fileMenu = self.makeFileMenu(menubar, isChild)

        # When redesigned, optionsMenu should only be on the parent
        #if (isChild == "no"):
        #    optionsMenu = self.makeOptionsMenu(menubar)
        optionsMenu = self.makeOptionsMenu(menubar)

        menubar.pack(fill = X)


    # Method to generate a "File" menu
    def makeFileMenu(self, menubar, isChild):

        fileButton = Menubutton(menubar, text = 'File')
        fileButton.pack(side = LEFT, padx = 2)
        
        fileButton.menu = Menu(fileButton, tearoff = 0)

        if (isChild == "no"):
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
                                          value       = "WINDOW",
                                          selectcolor = "black",
                                          variable    = self.helpChoice)
        optionButton.menu.add_radiobutton(label = "Display Help in a Browser",
                                          value       = "BROWSER",
                                          selectcolor = "black",
                                          variable    = self.helpChoice)

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
        if (self.isChild == "no"):
            # Execute the task
            buttonExecute = Button(box, text = "EXECUTE", fg = "black",
                                   relief = RAISED, command = self.execute)
            buttonExecute.pack(side = LEFT, padx = 5, pady = 7)
            buttonExecute.bind("<Enter>", self.printExecuteInfo)

        # Save the parameter settings and exit from epar
        buttonQuit = Button(box, text = "SAVE", fg = "black",
                            relief = RAISED, command = self.quit)
        buttonQuit.pack(side = LEFT, padx = 5, pady = 7)
        buttonQuit.bind("<Enter>", self.printQuitInfo)

        # Unlearn all the parameter settings (set back to the defaults)
        buttonUnlearn = Button(box, text = "UNLEARN", fg = "black", 
                            relief = RAISED, command = self.unlearn)
        buttonUnlearn.pack(side = LEFT, padx = 5, pady = 7)
        buttonUnlearn.bind("<Enter>", self.printUnlearnInfo)

        # Abort this edit session.  Currently, if an UNLEARN has already
        # been done, the UNLEARN is kept.
        buttonAbort = Button(box, text = "ABORT", fg = "black",
                              relief = RAISED, command = self.abort) 
        buttonAbort.pack(side = LEFT, padx = 5, pady = 7)
        buttonAbort.bind("<Enter>", self.printAbortInfo)

        # Generate the a Help button
        buttonHelp = Button(box, text = "HELP", fg = "black",
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


    # QUIT: save the parameter settings and exit epar
    def quit(self, event = None):

        #if not self.top.validate():
        #    self.top.initial_focus.focus_set()
        #    return

        # save all the entries and verify them 
        try:
            self.saveEntries()
        finally:

            # Remove the main epar window
            self.top.focus_set()
            self.top.withdraw()
            self.top.destroy()

            if (self.isChild == "no"):
                self.top.quit()


    # EXECUTE: save the parameter settings and run the task
    def execute(self, event=None):

        # Declare the global variables so they can be updated
        global CHILDX
        global CHILDY

        # Need to get all the entries and verify them 
        # First save the parameter values of the children
        for n in range(len(self.top.childList)):
            self.top.childList[n].saveEntries()

        # Now save the parameter values of the parent
        self.saveEntries()

        # Remove the main epar window
        self.top.focus_set()
        self.top.withdraw()
        self.top.destroy()
 
        # Reset to the start location
        CHILDX = 600
        CHILDY = 0

        print "\nTask %s is running...\n" % self.taskName

        # Run the task
        try:
            self.runTask()
        finally:
            self.top.quit()


    # ABORT: abort this epar session
    def abort(self, event = None):

        # Declare the global variables so they can be updated
        global CHILDX
        global CHILDY

        # Reset to the start location
        CHILDX = 600
        CHILDY = 0

        # Give focus back to parent window and abort
        self.top.focus_set()
        self.top.withdraw()
        self.top.destroy()
        if (self.isChild == "no"):
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

        """
        # Old method from RLW - still works
        buffer = cStringIO.StringIO()
        sys.stdout = buffer
        try:
            iraf.system.help(taskname)
        finally:
            sys.stdout = sys.__stdout__
        result = buffer.getvalue()
        buffer.close()
        return result
        """

        fh = cStringIO.StringIO()
        iraf.system.help(taskname, page = 0, Stdout = fh)
        result = fh.getvalue()
        fh.close()
        return result

    # Set up the help dialog (browser)
    def helpBrowser(self, helpString):

        # Generate a new Toplevel window for the browser
        self.hb = Toplevel(self.top, bg = "SlateGray3")
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
                 width = 11, relief = SUNKEN, activerelief = SUNKEN)
 
        # Define the Listbox and setup the Scrollbar
        self.hb.frame.list = Listbox(self.hb.frame, 
                                     relief            = FLAT,
                                     height            = 25,
                                     width             = 80,
                                     background        = "white",
                                     selectmode        = SINGLE,
                                     selectborderwidth = 0,
                                     selectbackground  = "white")
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

        # Obtain the parameter list anew
        #self.newParamList = self.taskObject.getParList()

        # Loop over the parameters to reset the values
        for i in range(self.numParams):
            self.entryNo[i].unlearnOption(self.defaultParamList[i])
            #self.entryNo[i].unlearnOption(self.newParamList[i])


    # Read, save, and validate the entries
    def saveEntries(self):

        # Loop over the parameters to obtain the modified information
        for i in range(self.numParams):

            # Verify the value is valid. If it is numeric and invalid,
            # the value will be converted to its original valid value.
            self.entryNo[i].entryCheck()

            # Cannot change an entry if it is a PSET, just skip
            if (self.paramList[i].type != "pset"):

                # Determine the type of entry variable
                classType = self.entryNo[i].choiceClass

                # Acquire the value for update of the parameter entry
                # The BooleanVar might be a null string which is VALID, 
                # so catch the exception.  If not a boolean, rethrow 
                # the exception.
                try:
                    value = self.entryNo[i].choice.get()
                except TclError, exceptionInfo:
                    if (classType == BooleanVar):
                        value = ""
                    else:
                        raise TclError, exceptionInfo

                # If the parameter is not a native type of string, it
                # must be converted.
                self.taskObject.setParam(self.paramList[i].get(field = "p_name",
                                    native = 1, prompt = 0), value)

        # save results to the uparm directory
        self.taskObject.save()

    # Run the task
    def runTask(self):

        # Use the run method of the IrafTask class
        # Set mode='h' so it does not prompt for parameters (like IRAF epar)
        # Also turn on parameter saving
        self.taskObject.run(mode='h', _save=1)
