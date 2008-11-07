"""
Tk gui implementation for the gki plot widget

$Id$
"""

import numpy, os, sys, string, wutil, time
import Tkinter, msgiobuffer
from pytools import filedlg
import gki, textattrib, irafgwcs
from irafglobals import IrafError, pyrafDir, userWorkingHome
import tkMessageBox, tkSimpleDialog

nIrafColors = 16

#-----------------------------------------------

helpString = """\
PyRAF graphics windows provide the capability to recall previous plots, print
the current plot, save and load metacode to a file, undo/redo edits to plots,
and create new graphics windows.  The windows are active at all times (not just
in interactive cursor mode) and can be resized.

The status bar at the bottom of the window displays messages from the task and
is used for input.  Note that it has a scroll bar so that old messages can be
recalled.

File menu:
    Print
             Print the current plot to the IRAF stdplot device.
    Save...
             Save metacode for the current plot to a user-specified file.
    Load...
             Load metacode from to a user-specified file.
    Close Window
             Close (iconify) the window.
    Quit Window
             Destroy this window.  Note that if the window is destroyed while
             a graphics task is running, the results are unpredictable.

Edit menu:
    Undo
             Undo the last editable change to the plot.  Most changes added by
             the task (e.g., overplotted lines) cannot currently be undone, but
             user changes (text annotations, marks) can be undone.  You can make
             overplots undoable by inserting blank annotations.
    Redo
             Redo the last change.
    Undo All
             Remove all undoable changes.
    Refresh
             Redraw the plot.
    Delete Plot
             Delete this plot.  (This is not undoable.)  Note that plots are
             renumbered in the Page listing.
    Delete All Plots
             Delete all plots.  User is prompted to be sure.

Page menu:
    (tearoff)
             Selecting the dotted tearoff line at the top of the menu creates a
             separate page-selector window.
    Next
             Go to the next page in the list of plots.
    Back
             Go to the previous page in the list of plots.
    First
             Go to the first page in the list of plots.
    Last
             Go to the last page in the list of plots.
    (page list)
             Go directly to the selected page.  Pages are labelled with the name
             of the task that created them.  If there are many pages, a subset
             around the currently active page is shown; selecting a page (or
             using First, Last, etc.) changes the displayed subset.

Window menu:
    New...
             Create a new graphics window.  Prompts for a name; if no name is
             given, the new name will be 'graphics<N>' where <N> is a unique
             number.  If a window with the given name already exists, it simply
             switches the graphics focus to the new window.
    (window list)
             Switch graphics focus to the selected window.  Subsequent plots
             will appear in that window.  The results are unpredictable if the
             window is changed while an interactive graphics task is running.

Help menu:
    Help...
             Display this help.
"""

#-----------------------------------------------


class GkiInteractiveTkBase(gki.GkiKernel, wutil.FocusEntity):

    """Base class for interactive graphics kernel implementation

    This class implements the supporting functionality for the
    interactive graphics kernel: menu bar, status line, page
    caching, etc.

    The actual graphics pane is implemented in a separate class,
    which extends this class and must have the attributes:

    makeGWidget()           Create the gwidget Tk object and colorManager object
    redraw()                Redraw method (don't call this directly, used by
                            the gwidget class)
    gRedraw()               Redraw that defers to gwidget
    gcur()                  Wait for key to be typed and return cursor value
    gcurTerminate()         Terminate active gcur so window can be destroyed
    incrPlot()              Plot the stuff added to buffer since last draw
    prepareToRedraw()       Prepare for complete redraw from metacode
    getHistory()            Get information that needs to be saved in page history
    setHistory()            Restore page using getHistory info
    clearPage()             Clear page (for initialization)
    startNewPage()          Setup for new page
    isPageBlank()           Returns true if current page is blank
    gki_*()                 Implement various GKI metacode commands

    The gwidget object (created by makeGWidget) should have these
    attributes (in addition to the usual Tk methods):

    lastX, lastY            Last cursor position (int), initially None
    rgbamode                Flag indicating RGB (if true) or indexed color mode
    activate()              Make this the focus of plots

    activateSWCursor()      Various methods for handling the crosshair cursor
    deactivateSWCursor()    (Should rename and clean these up)
    isSWCursorActive()
    getSWCursor()

    #XXX
    Still need to work on the ColorManager class, which has a bunch
    of OpenGL specific stuff embedded in it.  Could also probably
    integrate the gl_ functions into a class and use introspection
    to create the dispatch table, just like for the gki functions.
    #XXX
    """

    # GKI control functions that are ignored on redraw
    _controlOps = [
            gki.GKI_OPENWS,
            gki.GKI_CLOSEWS,
            gki.GKI_REACTIVATEWS,
            gki.GKI_DEACTIVATEWS,
            gki.GKI_MFTITLE,
            gki.GKI_CLEARWS,
            gki.GKI_CANCEL,
            gki.GKI_FLUSH,
            ]

    # maximum number of error messages for a plot
    MAX_ERROR_COUNT = 3

    def __init__(self, windowName, manager):

        gki.GkiKernel.__init__(self)
        self.name = 'Tkplot'
        self._errorMessageCount = 0
        self._slowraise = 0
        self.irafGkiConfig = gki._irafGkiConfig
        self.windowName = windowName
        self.manager = manager

        # redraw table ignores control functions
        self.redrawFunctionTable = self.functionTable[:]
        for opcode in self._controlOps:
            self.redrawFunctionTable[opcode] = None

        # Create the root window as required, but hide it
        if Tkinter._default_root is None:
            root = Tkinter.Tk()
            root.withdraw()
        # note size is just an estimate that helps window manager place window
        self.top = Tkinter.Toplevel(visual='best',width=600,height=485)
        # Read the epar options database file
        optfile = "epar.optionDB"
        try:
            self.top.option_readfile(os.path.join(os.curdir,optfile))
        except Tkinter.TclError:
            try:
                self.top.option_readfile(os.path.join(userWorkingHome,optfile))
            except Tkinter.TclError:
                self.top.option_readfile(os.path.join(pyrafDir,optfile))
        self.top.title(windowName)
        self.top.iconname(windowName)
        self.top.protocol("WM_DELETE_WINDOW", self.gwdestroy)
        self.makeMenuBar()
        self.makeGWidget()
        self.makeStatus()
        self.gwidget.redraw = self.redraw
        self.gwidget.pack(side=Tkinter.TOP, expand=1, fill=Tkinter.BOTH)

        self.colorManager.setColors(self.gwidget)
        self.wcs = irafgwcs.IrafGWcs()
        self.linestyles = gki.IrafLineStyles()
        self.hatchfills = gki.IrafHatchFills()
        self.textAttributes = gki.TextAttributes()
        self.lineAttributes = gki.LineAttributes()
        self.fillAttributes = gki.FillAttributes()
        self.markerAttributes = gki.MarkerAttributes()

        self.StatusLine = gki.StatusLine(self.top.status, self.windowName)
        self.history = [(self.gkibuffer, self.wcs, "", self.getHistory())]
        self._currentPage = 0
        self.pageVar = Tkinter.IntVar()
        self.pageVar.set(self._currentPage)
        # _setPageVar is callback for changes to pageVar
        self.pageVar.trace('w', self._setPageVar)
        windowID = self.gwidget.winfo_id()
        self.flush()
        if os.uname()[0] != 'Darwin': # this step is unneeded on OSX
            wutil.setBackingStore(windowID)

    # -----------------------------------------------

    def makeStatus(self):

        """Make status display at bottom of window"""

        self.top.status = msgiobuffer.MsgIOBuffer(self.top, width=600)
        self.top.status.msgIO.pack(side=Tkinter.BOTTOM, fill = Tkinter.X)

    # -----------------------------------------------
    # Menu bar definitions

    def makeMenuBar(self):

        """Make menu bar at top of window"""

        self.menubar = Tkinter.Frame(self.top, bd=1, relief=Tkinter.FLAT)
        self.fileMenu = self.makeFileMenu(self.menubar)
        self.editMenu = self.makeEditMenu(self.menubar)
        self.pageMenu = self.makePageMenu(self.menubar)
        self.windowMenu = self.makeWindowMenu(self.menubar)
        self.helpMenu = self.makeHelpMenu(self.menubar)
        self.menubar.pack(side=Tkinter.TOP, fill=Tkinter.X)

    def makeFileMenu(self, menubar):

        button = Tkinter.Menubutton(menubar, text='File')
        button.pack(side=Tkinter.LEFT, padx=2)
        button.menu = Tkinter.Menu(button, tearoff=0)
        button.menu.add_command(label="Print", command=self.doprint)
        button.menu.add_command(label="Save...", command=self.save)
        button.menu.add_command(label="Load...", command=self.load)
        button.menu.add_command(label="Close Window", command=self.iconify)
        button.menu.add_command(label="Quit Window", command=self.gwdestroy)
        button["menu"] = button.menu
        return button

    def doprint(self):

        stdout = sys.stdout
        sys.stdout = self.StatusLine
        try:
            gki.printPlot(self)
        finally:
            sys.stdout = stdout

    def save(self):

        """Save metacode in a file"""

        fd = filedlg.PersistSaveFileDialog(self.top, "Save Metacode", "*")
        if fd.Show() != 1:
            fd.DialogCleanup()
            return
        fname = fd.GetFileName()
        fd.DialogCleanup()
        fh = open(fname, 'w')
        fh.write(self.gkibuffer.get().tostring())
        fh.close()

    def load(self, fname=None):

        """Load metacode from a file"""

        if fname is None:
            fd = filedlg.PersistLoadFileDialog(self.top, "Load Metacode", "*")
            if fd.Show() != 1:
                fd.DialogCleanup()
                return
            fname = fd.GetFileName()
            fd.DialogCleanup()
        fh = open(fname, 'r')
        metacode = numpy.fromstring(fh.read(), numpy.int16)
        fh.close()
        self.clear(name=fname)
        self.append(metacode,isUndoable=1)

    def iconify(self):

        self.top.iconify()

    def makeEditMenu(self, menubar):

        button = Tkinter.Menubutton(menubar, text='Edit')
        button.pack(side=Tkinter.LEFT, padx=2)
        button.menu = Tkinter.Menu(button, tearoff=0,
                postcommand=self.editMenuInit)
        num = 0
        button.menu.add_command(label="Undo", command=self.undoN)
        button.undoNum = num

        button.menu.add_command(label="Redo", command=self.redoN)
        num = num+1
        button.redoNum = num

        button.menu.add_command(label="Undo All", command=self.redrawOriginal)
        num = num+1
        button.redrawOriginalNum = num

        button.menu.add_command(label="Refresh", command=self.gRedraw)
        num = num+1
        button.redrawNum = num

        button.menu.add_separator()
        num = num+1

        button.menu.add_command(label="Delete Plot",
                command=self.deletePlot)
        num = num+1
        button.deleteNum = num

        button.menu.add_command(label="Delete All Plots",
                command=self.deleteAllPlots)
        num = num+1
        button.deleteAllNum = num

        button["menu"] = button.menu
        return button

        #XXX additional items:
        # annotate (add annotation to plot using gcur -- need
        #   to migrate annotation code to this module?)
        # zoom, etc (other IRAF capital letter equivalents)
        #XXX

    def editMenuInit(self):

        button = self.editMenu
        # disable Undo item if not undoable
        buffer = self.getBuffer()
        if buffer.isUndoable():
            self.editMenu.menu.entryconfigure(button.undoNum,
                    state=Tkinter.NORMAL)
            self.editMenu.menu.entryconfigure(button.redrawOriginalNum,
                    state=Tkinter.NORMAL)
        else:
            self.editMenu.menu.entryconfigure(button.undoNum,
                    state=Tkinter.DISABLED)
            self.editMenu.menu.entryconfigure(button.redrawOriginalNum,
                    state=Tkinter.DISABLED)
        # disable Redo item if not redoable
        if buffer.isRedoable():
            self.editMenu.menu.entryconfigure(button.redoNum,
                    state=Tkinter.NORMAL)
        else:
            self.editMenu.menu.entryconfigure(button.redoNum,
                    state=Tkinter.DISABLED)
        # disable Delete items if no plots
        if len(self.history)==1 and self.isPageBlank():
            self.editMenu.menu.entryconfigure(button.deleteNum,
                    state=Tkinter.DISABLED)
            self.editMenu.menu.entryconfigure(button.deleteAllNum,
                    state=Tkinter.DISABLED)
        else:
            self.editMenu.menu.entryconfigure(button.deleteNum,
                    state=Tkinter.NORMAL)
            self.editMenu.menu.entryconfigure(button.deleteAllNum,
                    state=Tkinter.NORMAL)

    def deletePlot(self):

        # delete current plot
        del self.history[self._currentPage]
        if len(self.history)==0:
            # that was the last plot
            # clear all buffers and put them back on the history
            self.gkibuffer.reset()
            self.clearPage()
            self.wcs.set()
            self.history = [(self.gkibuffer, self.wcs, "", self.getHistory())]
        n = max(0, min(self._currentPage, len(self.history)-1))
        # ensure that redraw happens
        self._currentPage = -1
        self.pageVar.set(n)

    def deleteAllPlots(self):

        if tkMessageBox.askokcancel("", "Delete all plots?"):
            del self.history[:]
            # clear all buffers and put them back on the history
            self.gkibuffer.reset()
            self.clearPage()
            self.wcs.set()
            self.history = [(self.gkibuffer, self.wcs, "", self.getHistory())]
            # ensure that redraw happens
            self._currentPage = -1
            self.pageVar.set(0)

    def makePageMenu(self, menubar):

        button = Tkinter.Menubutton(menubar, text='Page')
        button.pack(side=Tkinter.LEFT, padx=2)
        button.menu = Tkinter.Menu(button, tearoff=1,
                postcommand=self.pageMenuInit)
        num = 1 # tearoff is entry 0 on menu
        button.nextNum = num
        num = num+1
        button.menu.add_command(label="Next", command=self.nextPage)
        button.backNum = num
        num = num+1
        button.menu.add_command(label="Back", command=self.backPage)
        button.firstNum = num
        num = num+1
        button.menu.add_command(label="First", command=self.firstPage)
        button.lastNum = num
        num = num+1
        button.menu.add_command(label="Last", command=self.lastPage)
        # need to add separator here because menu.delete always
        # deletes at least one item
        button.sepNum = num
        num = num+1
        button.menu.add_separator()
        button["menu"] = button.menu
        return button

    def pageMenuInit(self):

        button = self.pageMenu
        menu = button.menu
        page = self._currentPage
        # Next
        if page < len(self.history)-1:
            menu.entryconfigure(button.nextNum, state=Tkinter.NORMAL)
        else:
            menu.entryconfigure(button.nextNum, state=Tkinter.DISABLED)
        # Back
        if page>0:
            menu.entryconfigure(button.backNum, state=Tkinter.NORMAL)
        else:
            menu.entryconfigure(button.backNum, state=Tkinter.DISABLED)
        # First
        if page>0:
            menu.entryconfigure(button.firstNum, state=Tkinter.NORMAL)
        else:
            menu.entryconfigure(button.firstNum, state=Tkinter.DISABLED)
        # Last
        if page < len(self.history)-1:
            menu.entryconfigure(button.lastNum, state=Tkinter.NORMAL)
        else:
            menu.entryconfigure(button.lastNum, state=Tkinter.DISABLED)
        # Delete everything past the separator
        menu.delete(button.sepNum,10000)
        menu.add_separator()
        # Add radio buttons for pages
        # Only show limited window around active page
        halfsize = 10
        pmin = self._currentPage-halfsize
        pmax = self._currentPage+halfsize+1
        lhis = len(self.history)
        if pmin<0:
            pmax = pmax-pmin
            pmin = 0
        elif pmax>lhis:
            pmin = pmin-(pmax-lhis)
            pmax = lhis
        pmax = min(pmax, lhis)
        pmin = max(0, pmin)
        h = self.history
        for i in range(pmin,pmax):
            task = h[i][2]
            if i==pmin and pmin>0:
                label = "<< %s" % task
            elif i==pmax-1 and pmax<lhis:
                label = ">> %s" % task
            else:
                label = "%2d %s" % (i+1,task)
            menu.add_radiobutton(label=label, value=i, variable=self.pageVar)
        # Make sure pageVar matches the real index value
        self.pageVar.set(self._currentPage)

    def _setPageVar(self, *args):

        """Called when pageVar is changed (by .set() or by Page menu)"""

        n = self.pageVar.get()
        n = max(0, min(n, len(self.history)-1))
        if self._currentPage != n:
            self._currentPage = n
            self.gkibuffer, self.wcs, name, otherHistory = \
                            self.history[self._currentPage]
            self.setHistory(otherHistory)
            self.gRedraw()
            self.pageMenuInit()

    def backPage(self):

        self.pageVar.set(max(0,self._currentPage-1))

    def nextPage(self):

        self.pageVar.set(
                max(0,min(self._currentPage+1, len(self.history)-1)))

    def firstPage(self):

        self.pageVar.set(0)

    def lastPage(self):

        self.pageVar.set(len(self.history)-1)

    def makeWindowMenu(self, menubar):

        button = Tkinter.Menubutton(menubar, text='Window')
        button.pack(side=Tkinter.LEFT, padx=2)
        button.menu = Tkinter.Menu(button, tearoff=0,
                postcommand=self.windowMenuInit)
        button.menu.add_command(label="New...", command=self.createNewWindow)
        # need to add separator here because menu.delete always
        # deletes at least one item
        button.menu.add_separator()
        button["menu"] = button.menu
        return button

    def windowMenuInit(self):

        menu = self.windowMenu.menu
        winVar = self.manager.getWindowVar()
        winList = self.manager.windowNames()
        winList.sort()
        # Delete everything past the separator
        menu.delete(1,10000)
        menu.add_separator()
        # Add radio buttons for windows
        for i in range(len(winList)):
            menu.add_radiobutton(label=winList[i], value=winList[i],
                    variable=winVar)

    def createNewWindow(self):

        import newWindowHack  # Fixes lockup in askstring() with Tk8.4
        newname = tkSimpleDialog.askstring("New Graphics Window",
                "Name of new graphics window",
                initialvalue=self.manager.getNewWindowName())
        if newname is not None:
            self.manager.window(newname)

    def makeHelpMenu(self, menubar):

        button = Tkinter.Menubutton(menubar, text='Help')
        button.pack(side=Tkinter.RIGHT, padx=2)
        button.menu = Tkinter.Menu(button, tearoff=0)
        button.menu.add_command(label="Help...", command=self.getHelp)
        button["menu"] = button.menu
        return button

    def getHelp(self):

        """Display window with help on graphics"""

        hb = Tkinter.Toplevel(self.top, visual='best')
        hb.title("PyRAF Graphics Help")
        hb.iconname("PyRAF Graphics Help")

        # Set up the Menu Bar with 'Close' button
        hb.menubar = Tkinter.Frame(hb, relief=Tkinter.RIDGE, borderwidth=0)
        hb.menubar.button = Tkinter.Button(hb.menubar, text="Close",
                                     relief=Tkinter.RAISED,
                                     command=hb.destroy)
        hb.menubar.button.pack()
        hb.menubar.pack(side=Tkinter.BOTTOM, padx=5, pady=5)

        # Define the Listbox and setup the Scrollbar
        hb.list = Tkinter.Listbox(hb,
                                                        relief = Tkinter.FLAT,
                                                        height = 25,
                                                        width = 80,
                                                        selectmode = Tkinter.SINGLE,
                                                        selectborderwidth = 0)

        scroll = Tkinter.Scrollbar(hb, command=hb.list.yview)
        hb.list.configure(yscrollcommand=scroll.set)
        hb.list.pack(side=Tkinter.LEFT, fill=Tkinter.BOTH, expand=1)
        scroll.pack(side=Tkinter.RIGHT, fill=Tkinter.Y)

        # Insert each line of the helpString into the box
        listing = string.split(helpString, '\n')
        for line in listing:
            hb.list.insert(Tkinter.END, line)

    # -----------------------------------------------
    # start general functionality (independent of graphics panel
    #   implementation)

    def activate(self):

        """Make this the active window"""

        self.gwidget.activate()

    def errorMessage(self,text):

        """Truncate number of error messages produced in a plot."""

        if self._errorMessageCount < self.MAX_ERROR_COUNT:
            print text
            self._errorMessageCount = self._errorMessageCount + 1
        elif self._errorMessageCount == self.MAX_ERROR_COUNT:
            print "\nAdditional graphics error messages suppressed"
            self._errorMessageCount = self._errorMessageCount + 1

    def flush(self):

        """Flush any pending graphics requests"""

        try:
            if self.gwidget:
                self.gwidget.update_idletasks()
        except Tkinter.TclError:
            pass

    def hasFocus(self):

        """Returns true if this window currently has focus"""
        return  wutil.getTopID(wutil.getFocalWindowID()) == \
                wutil.getTopID(self.getWindowID())

    def setDrawingColor(self, irafColorIndex):

        self.colorManager.setDrawingColor(irafColorIndex)

    def setCursorColor(self, irafColorIndex):

        self.colorManager.setCursorColor(irafColorIndex)

    def getWindowName(self):

        return self.windowName

    def gwdestroy(self):

        """Delete this object from the manager window list"""

        # if gcur is active, terminate it
        self.gcurTerminate()
        self.gwidget = None
        self.top.after_idle(self.manager.delete, self.windowName)

    # -----------------------------------------------
    # the following methods implement the FocusEntity interface
    # used by wutil.FocusController

    def saveCursorPos(self):

        """save current position if window has focus and cursor is
        in window, otherwise do nothing"""

        if not self.hasFocus():
            # window does not have focus
            return
        gwidget = self.gwidget
        if gwidget:
            x = gwidget.winfo_pointerx()-gwidget.winfo_rootx()
            y = gwidget.winfo_pointery()-gwidget.winfo_rooty()
            maxX = gwidget.winfo_width()
            maxY = gwidget.winfo_height()
            if x < 0 or y < 0 or x >= maxX or y >= maxY:
                return
            gwidget.lastX = x
            gwidget.lastY = y

    def forceFocus(self):

        # only force focus if window is viewable
        if not wutil.isViewable(self.top.winfo_id()):
            return
        # warp cursor
        # if no previous position, move to center
        gw = self.gwidget
        if gw:
            if gw.lastX is None or \
               (gw.lastX == 0 and gw.lastY == 0):
                swCurObj = gw.getSWCursor()
                if swCurObj:
                    gw.lastX = int(swCurObj.lastx*gw.winfo_width())
                    gw.lastY = int((1.-swCurObj.lasty)*gw.winfo_height())
                else:
                    gw.lastX = int(gw.winfo_width()/2.)
                    gw.lastY = int(gw.winfo_height()/2.)
            wutil.moveCursorTo(gw.winfo_id(),
                               gw.winfo_rootx(),
                               gw.winfo_rooty(),
                               gw.lastX,
                               gw.lastY)

            # On non-X, "focus_force()" places focus on the gwidget canvas, but
            # this may not have the global focus; it may only be the widget seen
            # when the application itself has focus.  We may need to force the
            # app itself to have focus first, so we do that here too.
            wutil.forceFocusToNewWindow()
            gw.focus_force()

    def getWindowID(self):

        if self.gwidget:
            return self.gwidget.winfo_id()

    # -----------------------------------------------
    # GkiKernel methods

    def clear(self, name=None):

        """Clear the plot and start a new page"""

        # don't create new plot if current plot is empty
        if not self.isPageBlank():
            # ignore any pending WCS changes
            self.wcs.clearPending()
            self.gkibuffer = self.gkibuffer.split()
            self.wcs = irafgwcs.IrafGWcs()
            self.startNewPage()
            if name is None:
                if gki.tasknameStack:
                    name = gki.tasknameStack[-1]
                else:
                    name = ""
            self.history.append(
                    (self.gkibuffer, self.wcs, name, self.getHistory()) )
            self.pageVar.set(len(self.history)-1)
            self.StatusLine.write(text=" ")
            self.flush()
        elif (self.history[-1][2] == "") and gki.tasknameStack:
            # plot is empty but so is name -- set name
            h = self.history[-1]
            self.history[-1] = h[0:2] + (gki.tasknameStack[-1],) + h[3:]

    def translate(self, gkiMetacode, redraw=0):

        if redraw:
            table = self.redrawFunctionTable
        else:
            table = self.functionTable
        gki.gkiTranslate(gkiMetacode, table)
        # render new stuff immediately
        self.incrPlot()

    def control_openws(self, arg):

        self._errorMessageCount = 0
        mode = arg[0]
        ta = self.textAttributes
        ta.setFontSize(self)
        self.raiseWindow()
        # redirect stdin & stdout to status line
        self.stdout = self.StatusLine
        self.stdin = self.stdout
        # disable stderr while graphics is active (to supress xgterm gui
        # messages)
        self.stderr = gki.FilterStderr()
        if mode == 5:
            # clear the display
            self.clear()
        elif mode == 4:
            # append, i.e., do nothing!
            pass
        elif mode == 6:
            # Tee mode (?), ignore for now
            pass

    def raiseWindow(self):

        if self.top.state() != Tkinter.NORMAL:
            self.top.deiconify()
        if self._slowraise == 0:
            # Get start time for tkraise...
            _stime = time.time()

            self.top.tkraise()
            _etime = time.time()
            # If it takes longer than 1 second to raise the window (ever),
            # set _slowraise to 1 so that tkraise will never be called again
            # during this session.
            if int(_etime - _stime) > 1: self._slowraise = 1

    def control_clearws(self, arg):

        # apparently this control routine is not used?
        self.clear()

    def control_reactivatews(self, arg):

        self._errorMessageCount = 0
        self.raiseWindow()
        if not self.stdout:
            # redirect stdout if not already
            self.stdout = self.StatusLine
            self.stdin = self.stdout
        if not self.stderr:
            self.stderr = gki.FilterStderr()

    def control_deactivatews(self, arg):

        if self.stdout:
            self.stdout.close()
            self.stdout = None
            self.stdin = None
        if self.stderr:
            self.stderr.close()
            self.stderr = None

    def control_setwcs(self, arg):

        self.wcs.set(arg)

    def gki_setwcs(self, arg):

        # Ordinarily the control_setwcs opcode sets the WCS, but
        # when we are loading saved metacode only the gki_setwcs
        # code remains.  (I think that sometimes the gki_setwcs
        # metacode is absent.)  But doing this redundant operation
        # doesn't cost much.

        self.wcs.set(arg)

    def control_getwcs(self, arg):

        if not self.wcs:
            self.errorMessage("Error: can't append to a nonexistent plot!")
            raise IrafError
        if self.returnData:
            self.returnData = self.returnData + self.wcs.pack()
        else:
            self.returnData = self.wcs.pack()

    def control_closews(self, arg):

        gwidget = self.gwidget
        if gwidget:
            gwidget.deactivateSWCursor()  # turn off software cursor
            if self.stdout:
                self.stdout.close()
                self.stdout = None
                self.stdin = None
            if self.stderr:
                self.stderr.close()
                self.stderr = None
        wutil.focusController.restoreLast()
