"""
OpenGL implementation of the gki kernel class

$Id$
"""

import Numeric, os, sys, string, re, wutil
import Tkinter, msgiobuffer
from OpenGL.GL import *
import toglcolors
import gki, openglgcur, opengltext, irafgwcs
from irafglobals import IrafError, pyrafDir, userWorkingHome
import tkMessageBox, tkSimpleDialog
import filedlg

nIrafColors = 16

#-----------------------------------------------

standardWarning = """
The graphics kernel for IRAF tasks has just received a metacode
instruction (%s) it never expected to see.  Please inform the
STSDAS group of this occurrence."""

standardNotImplemented = \
"""This IRAF task requires a graphics kernel facility not implemented
in the Pyraf graphics kernel (%s)."""

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


class GkiInteractiveBase(gki.GkiKernel, wutil.FocusEntity):

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

    lastX, lastY            Last cursor position, initially None
    rgbamode                Flag indicating RGB (if true) or indexed color mode
    activate()              Make this the focus of plots

    activateSWCursor()      Various methods for handling the crosshair cursor
    deactivateSWCursor()    (Should rename and clean these up)
    isSWCursorActive()

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
        self.name = 'OpenGL'
        self._errorMessageCount = 0
        self.irafGkiConfig = _irafGkiConfig
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
        self.linestyles = IrafLineStyles()
        self.hatchfills = IrafHatchFills()
        self.textAttributes = opengltext.TextAttributes()
        self.lineAttributes = LineAttributes()
        self.fillAttributes = FillAttributes()
        self.markerAttributes = MarkerAttributes()

        self.StatusLine = StatusLine(self.top.status, self.windowName)
        self.history = [(self.gkibuffer, self.wcs, "", self.getHistory())]
        self._currentPage = 0
        self.pageVar = Tkinter.IntVar()
        self.pageVar.set(self._currentPage)
        # _setPageVar is callback for changes to pageVar
        self.pageVar.trace('w', self._setPageVar)
        windowID = self.gwidget.winfo_id()
        wutil.setBackingStore(windowID)
        self.flush()

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
        metacode = Numeric.fromstring(fh.read(), Numeric.Int16)
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
        # Define the Listbox and setup the Scrollbar
        hb.list = Tkinter.Listbox(hb,
                                                        relief = Tkinter.FLAT,
                                                        height = 25,
                                                        width = 70,
                                                        selectmode = Tkinter.SINGLE,
                                                        selectborderwidth = 0)

        scroll = Tkinter.Scrollbar(hb, command=hb.list.yview)
        hb.list.configure(yscrollcommand=scroll.set)
        hb.list.pack(side=Tkinter.LEFT)
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

        return  wutil.getTopID(wutil.getWindowID()) == \
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
        gwidget = self.gwidget
        if gwidget:
            if gwidget.lastX is None:
                gwidget.lastX = gwidget.winfo_width()/2
                gwidget.lastY = gwidget.winfo_height()/2
            wutil.moveCursorTo(gwidget.winfo_id(),gwidget.lastX,gwidget.lastY)
            gwidget.focus_force()

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
        self.stderr = FilterStderr()
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
        self.top.tkraise()

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
            self.stderr = FilterStderr()

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

#-----------------------------------------------

class GkiOpenGlKernel(GkiInteractiveBase):

    """OpenGL graphics kernel implementation"""

    def makeGWidget(self, width=600, height=420):

        """Make the graphics widget"""

        # Ptogl is local substitute for OpenGL.Tk
        # (to remove goofy 3d cursor effects)
        # Import is placed here since it can be slow, so delay import to
        # a time that a window is really needed. Subsequent imports will
        # be fast.
        import Ptogl
        self.gwidget = Ptogl.Ptogl(self.top,width=width,height=height)
        self.gwidget.firstPlotDone = 0
        self.colorManager = glColorManager(self.irafGkiConfig,
                                self.gwidget.rgbamode)
        self.startNewPage()
        self._gcursorObject = openglgcur.Gcursor(self)
        self.gRedraw()

    def gcur(self):

        """Return cursor value after key is typed"""

        return self._gcursorObject()

    def gcurTerminate(self, msg='Window destroyed by user'):

        """Terminate active gcur and set EOF flag"""

        if self._gcursorObject.active:
            self._gcursorObject.eof = msg
            # end the gcur mainloop -- this is what allows
            # closing the window to act the same as EOF
            self.top.quit()

    def taskDone(self, name):

        """Called when a task is finished"""

        # Hack to prevent the double redraw after first Tk plot
        self.doubleRedrawHack()

    def update(self):

        """Update for all Tk events

        This should not be called unless necessary since it can
        cause double redraws.  It is used in the imcur task to
        allow window resize (configure) events to be caught
        while a task is running.  Possibly it should be called
        during long-running tasks too, but that will probably
        lead to more extra redraws"""

        # Hack to prevent the double redraw after first Tk plot
        self.doubleRedrawHack()
        self.top.update()

    def doubleRedrawHack(self):

        # This is a hack to prevent the double redraw on first plots.
        # There is a mysterious Expose event that appears on the
        # idle list, but not until the Tk loop actually becomes idle.
        # The only approach that seems to work is to set this flag
        # and to ignore the event.
        # This is ugly but appears to work as far as I can tell.
        gwidget = self.gwidget
        if gwidget and not gwidget.firstPlotDone:
            gwidget.ignoreNextRedraw = 1
            gwidget.firstPlotDone = 1

    def prepareToRedraw(self):

        """Clear glBuffer in preparation for complete redraw from metacode"""

        self.glBuffer.reset()

    def getHistory(self):

        """Additional information for page history"""

        return self.glBuffer

    def setHistory(self, info):

        """Restore using additional information from page history"""

        self.glBuffer = info

    def startNewPage(self):

        """Setup for new page"""

        self.glBuffer = GLBuffer()

    def clearPage(self):

        """Clear buffer for new page"""

        self.glBuffer.reset()

    def isPageBlank(self):

        """Returns true if this page is blank"""

        return len(self.glBuffer) == 0

    # -----------------------------------------------
    # GkiKernel implementation

    def incrPlot(self):

        """Plot any new commands in the buffer"""

        gwidget = self.gwidget
        if gwidget:
            active = gwidget.isSWCursorActive()
            if active:
                gwidget.deactivateSWCursor()
            # render new contents of glBuffer
            self.activate()
            for (function, args) in self.glBuffer.getNewCalls():
                apply(function, args)
            gwidget.flush()
            if active:
                gwidget.activateSWCursor()

    # special methods that go into the function tables

    def _glAppend(self, gl_function, *args):

        """append a 2-tuple (gl_function, args) to the glBuffer"""

        self.glBuffer.append((gl_function,args))

    def gki_clearws(self, arg):

        # don't put clearws command in the gl buffer, just clear the display
        self.clear()

    def gki_cancel(self, arg):

        self.gki_clearws(arg)

    def gki_flush(self, arg):

        # don't put flush command in gl buffer
        # render current plot immediately on flush
        self.incrPlot()

    def gki_polyline(self, arg):

        # commit pending WCS changes when draw is found
        self.wcs.commit()
        self._glAppend(self.gl_polyline, gki.ndc(arg[1:]))

    def gki_polymarker(self, arg):

        self.wcs.commit()
        self._glAppend(self.gl_polymarker, gki.ndc(arg[1:]))

    def gki_text(self, arg):

        self.wcs.commit()
        x = gki.ndc(arg[0])
        y = gki.ndc(arg[1])
        text = arg[3:].astype(Numeric.Int8).tostring()
        self._glAppend(self.gl_text, x, y, text)

    def gki_fillarea(self, arg):

        self.wcs.commit()
        self._glAppend(self.gl_fillarea, gki.ndc(arg[1:]))

    def gki_putcellarray(self, arg):

        self.wcs.commit()
        self.errorMessage(standardNotImplemented % "GKI_PUTCELLARRAY")

    def gki_setcursor(self, arg):

        cursorNumber = arg[0]
        x = gki.ndc(arg[1])
        y = gki.ndc(arg[2])
        self._glAppend(self.gl_setcursor, cursorNumber, x, y)

    def gki_plset(self, arg):

        linetype = arg[0]
        linewidth = arg[1]/gki.GKI_FLOAT_FACTOR
        color = arg[2]
        self._glAppend(self.gl_plset, linetype, linewidth, color)

    def gki_pmset(self, arg):

        marktype = arg[0]
        #XXX Is this scaling for marksize correct?
        marksize = gki.ndc(arg[1])
        color = arg[2]
        self._glAppend(self.gl_pmset, marktype, marksize, color)

    def gki_txset(self, arg):

        charUp = float(arg[0])
        charSize = arg[1]/gki.GKI_FLOAT_FACTOR
        charSpace = arg[2]/gki.GKI_FLOAT_FACTOR
        textPath = arg[3]
        textHorizontalJust = arg[4]
        textVerticalJust = arg[5]
        textFont = arg[6]
        textQuality = arg[7]
        textColor = arg[8]
        self._glAppend(self.gl_txset, charUp, charSize, charSpace, textPath,
                textHorizontalJust, textVerticalJust, textFont,
                textQuality, textColor)

    def gki_faset(self, arg):

        fillstyle = arg[0]
        color = arg[1]
        self._glAppend(self.gl_faset, fillstyle, color)

    def gki_getcursor(self, arg):

        raise RuntimeError(standardNotImplemented %  "GKI_GETCURSOR")

    def gki_getcellarray(self, arg):

        raise RuntimeError(standardNotImplemented % "GKI_GETCELLARRAY")

    def gki_unknown(self, arg):

        self.errorMessage(standardWarning % "GKI_UNKNOWN")

    def gRedraw(self):

        if self.gwidget:
            self.gwidget.tkRedraw()

    def redraw(self, o=None):

        """Redraw for expose or resize events

        This method generally should not be called directly -- call
        gwidget.tkRedraw() instead since it does some other
        preparations.
        """

        # Note argument o is not needed because we only get redraw
        # events for our own gwidget
        ta = self.textAttributes
        ta.setFontSize(self)
        cm = self.colorManager
        if cm.rgbamode:
            glClearColor(0,0,0,0)
        else:
            glClearIndex(cm.indexmap[0])
        glClear(GL_COLOR_BUFFER_BIT | GL_DEPTH_BUFFER_BIT)
        glMatrixMode(GL_PROJECTION)
        glLoadIdentity()
        glOrtho(0,1,0,1,-1,1)
        glDisable(GL_LIGHTING)
        glDisable(GL_DITHER)
        glShadeModel(GL_FLAT)

        # finally ready to do the drawing
        self.activate()
        for (function, args) in self.glBuffer.get():
            apply(function, args)
        self.gwidget.flush()

    #-----------------------------------------------
    # These are the routines for the innermost loop in the redraw
    # function.  They are supposed to be stripped down to make
    # redraws as fast as possible.  (Still could be improved.)

    def gl_flush(self, arg):

        self.gwidget.flush()

    def gl_polyline(self, vertices):

        # First, set all relevant attributes
        la = self.lineAttributes
        glPointSize(1.0)
        glDisable(GL_LINE_SMOOTH)
        glLineWidth(la.linewidth)
        stipple = 0
        clear = 0
        if la.linestyle == 0:
            clear = 1 # "clear" linestyle, don't draw!
        elif la.linestyle == 1:
            pass # solid line
        elif 2 <= la.linestyle < len(self.linestyles.patterns):
            glEnable(GL_LINE_STIPPLE)
            stipple = 1
            glLineStipple(1,self.linestyles.patterns[la.linestyle])
        glBegin(GL_LINE_STRIP)
        try:
            if not clear:
                self.colorManager.setDrawingColor(la.color)
            else:
                self.colorManager.setDrawingColor(0)
            glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
        finally:
            glEnd()
            if stipple:
                glDisable(GL_LINE_STIPPLE)

    def gl_polymarker(self, vertices):

        # IRAF only implements points for poly marker, that makes it simple
        ma = self.markerAttributes
        clear = 0
        glPointSize(1)
        if not clear:
            self.colorManager.setDrawingColor(ma.color)
        else:
            self.colorManager.setDrawingColor(0)
        glBegin(GL_POINTS)
        try:
            glVertex(Numeric.reshape(vertices, (len(vertices)/2,2)))
        finally:
            glEnd()

    def gl_text(self, x, y, text):

        opengltext.softText(self,x,y,text)

    def gl_fillarea(self, vertices):

        fa = self.fillAttributes
        clear = 0
        polystipple = 0
        if fa.fillstyle == 0: # clear region
            clear = 1
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
        elif fa.fillstyle == 1: # hollow
            glPolygonMode(GL_FRONT_AND_BACK, GL_LINE)
        elif fa.fillstyle >= 2: # solid
            glPolygonMode(GL_FRONT_AND_BACK, GL_FILL)
    #       elif fa.fillstyle > 2: # hatched
    # This is commented out since PyOpenGL does not currently support
    # glPolygonStipple!
    #               if fa.fillstyle > 6: fa.fillstyle = 6
    #               t = self.hatchfills
    #               print t
    #               tp = t.patterns
    #               print tp, "patterns"
    #               fill = self.hatchfills.patterns[fa.fillstyle]
    #               print fill, "fill"
    #               polystipple = 1
    #               glEnable(GL_POLYGON_STIPPLE)
    #               glPolygonStipple(fill)
        if not clear:
            self.colorManager.setDrawingColor(fa.color)
        else:
            self.colorManager.setDrawingColor(0)
            # glColor3f(0.,0.,0.)
        # not a simple rectangle
        glBegin(GL_POLYGON)
        try:
            glVertex(Numeric.reshape(vertices,(len(vertices)/2,2)))
        finally:
            glEnd()
            if polystipple:
                glDisable(GL_POLYGON_STIPPLE)

    def gl_setcursor(self, cursornumber, x, y):

        gwidget = self.gwidget
        # wutil.MoveCursorTo uses 0,0 <--> upper left, need to convert
        sx = int(  x   * gwidget.winfo_width())
        sy = int((1-y) * gwidget.winfo_height())
        wutil.moveCursorTo(gwidget.winfo_id(), sx, sy)

    def gl_plset(self, linestyle, linewidth, color):

        self.lineAttributes.set(linestyle, linewidth, color)

    def gl_pmset(self, marktype, marksize, color):

        self.markerAttributes.set(marktype, marksize, color)

    def gl_txset(self, charUp, charSize, charSpace, textPath,
                    textHorizontalJust, textVerticalJust,
                    textFont, textQuality, textColor):

        self.textAttributes.set(charUp, charSize, charSpace,
                textPath, textHorizontalJust, textVerticalJust, textFont,
                textQuality, textColor)

    def gl_faset(self, fillstyle, color):

        self.fillAttributes.set(fillstyle, color)

#-----------------------------------------------

class glColorManager:

    """Encapsulates the details of setting the graphic's windows colors.

    Needed since we may be using rgba mode or color index mode and we
    do not want any of the graphics programs to have to deal with the
    mode being used. The current design applies the same colors to all
    graphics windows for color index mode (but it isn't required).
    An 8-bit display depth results in color index mode, otherwise rgba
    mode is used.  If no new colors are available, we take what we can
    get. We do not attempt to get a private colormap.
    """

    def __init__(self, config, rgbamode):

        self.config = config
        self.rgbamode = rgbamode
        self.indexmap = len(self.config.defaultColors)*[None]
        # call setColors to allocate colors after widget is created

    def setColors(self, widget):

        """Does nothing in rgba mode, allocates colors in index mode"""

        if not self.rgbamode:
            colorset = self.config.defaultColors
            for i in xrange(len(self.indexmap)):
                self.indexmap[i] = toglcolors.AllocateColor(widget.toglStruct,
                                                   colorset[i][0],
                                                   colorset[i][1],
                                                   colorset[i][2])
        self.setCursorColor()

    def setCursorColor(self, irafColorIndex=None):

        """Set crosshair cursor color to given index

        Only has an effect in index color mode."""
        import Ptogl
        if irafColorIndex is not None:
            self.config.setCursorColor(irafColorIndex)
        if self.rgbamode:
            Ptogl.cursorTrue = self.config.defaultColors[self.config.cursorColor]
        else:
            Ptogl.cursorColor = self.indexmap[self.config.cursorColor]

    def setDrawingColor(self, irafColorIndex):

        """Apply the specified iraf color to the current OpenGL drawing

        state using the appropriate mode."""
        if self.rgbamode:
            color = self.config.defaultColors[irafColorIndex]
            glColor3f(color[0], color[1], color[2])
        else:
            glIndex(self.indexmap[irafColorIndex])

#-----------------------------------------------

class GLBuffer:

    """implement a buffer for GL commands which allocates memory in blocks
    so that a new memory allocation is not needed everytime functions are
    appended"""

    INCREMENT = 500

    def __init__(self):

        self.buffer = None
        self.bufferSize = 0
        self.bufferEnd = 0
        self.nextTranslate = 0

    def __len__(self):

        return self.bufferEnd

    def reset(self):

        """Discard everything up to nextTranslate pointer"""

        newEnd = self.bufferEnd - self.nextTranslate
        if newEnd > 0:
            self.buffer[0:newEnd] = self.buffer[self.nextTranslate:self.bufferEnd]
            self.bufferEnd = newEnd
        else:
            self.buffer = None
            self.bufferSize = 0
            self.bufferEnd = 0
        self.nextTranslate = 0

    def append(self, funcargs):

        """Append a single (function,args) tuple to the list"""

        if self.bufferSize < self.bufferEnd + 1:
            # increment buffer size and copy into new array
            self.bufferSize = self.bufferSize + self.INCREMENT
            newbuffer = self.bufferSize*[None]
            if self.bufferEnd > 0:
                newbuffer[0:self.bufferEnd] = self.buffer[0:self.bufferEnd]
            self.buffer = newbuffer
        self.buffer[self.bufferEnd] = funcargs
        self.bufferEnd = self.bufferEnd + 1

    def get(self):

        """Get current contents of buffer

        Note that this returns a view into the Numeric array,
        so if the return value is modified the buffer will change too.
        """

        if self.buffer:
            return self.buffer[0:self.bufferEnd]
        else:
            return []

    def getNewCalls(self):

        """Return tuples (function, args) with all new calls in buffer"""

        ip = self.nextTranslate
        if ip < self.bufferEnd:
            self.nextTranslate = self.bufferEnd
            return self.buffer[ip:self.bufferEnd]
        else:
            return []

#-----------------------------------------------

class FilterStderr:

    """Filter GUI messages out of stderr during plotting"""

    pat = re.compile('\031[^\035]*\035\037')

    def __init__(self):
        self.fh = sys.stderr

    def write(self, text):
        # remove GUI junk
        edit = self.pat.sub('',text)
        if edit: self.fh.write(edit)

    def flush(self):
        self.fh.flush()

    def close(self):
        pass

#-----------------------------------------------

class StatusLine:

    def __init__(self, status, name):
        self.status = status
        self.windowName = name

    def readline(self):
        """Shift focus to graphics, read line from status, restore focus"""
        wutil.focusController.setFocusTo(self.windowName)
        rv = self.status.readline()
        return rv

    def read(self, n=0):
        """Return up to n bytes from status line

        Reads only a single line.  If n<=0, just returns the line.
        """
        s = self.readline()
        if n>0:
            return s[:n]
        else:
            return s

    def write(self, text):
        self.status.updateIO(text=string.strip(text))

    def flush(self):
        self.status.update_idletasks()

    def close(self):
        # clear status line
        self.status.updateIO(text="")

    def isatty(self):
        return 1

#-----------------------------------------------

class IrafGkiConfig:

    """Holds configurable aspects of IRAF plotting behavior

    This gets instantiated as a singleton instance so all windows
    can share the same configuration.
    """

    def __init__(self):

        # All set to constants for now, eventually allow setting other
        # values

        # h = horizontal font dimension, v = vertical font dimension

        # ratio of font height to width
        self.fontAspect = 42./27.
        self.fontMax2MinSizeRatio = 4.

        # Empirical constants for font sizes
        self.UnitFontHWindowFraction = 1./80
        self.UnitFontVWindowFraction = 1./45

        # minimum unit font size in pixels (set to None if not relevant)
        self.minUnitHFontSize = 5.
        self.minUnitVFontSize = self.minUnitHFontSize * self.fontAspect

        # maximum unit font size in pixels (set to None if not relevant)
        self.maxUnitHFontSize = \
                self.minUnitHFontSize * self.fontMax2MinSizeRatio
        self.maxUnitVFontSize = self.maxUnitHFontSize * self.fontAspect

        # offset constants to match iraf's notion of where 0,0 is relative
        # to the coordinates of a character
        self.vFontOffset = 0.0
        self.hFontOffset = 0.0

        # font sizing switch
        self.isFixedAspectFont = 1

        # List of rgb tuples (0.0-1.0 range) for the default IRAF set of colors
        self.defaultColors = [
                (0.,0.,0.),  # black
                (1.,1.,1.),  # white
                (1.,0.,0.),  # red
                (0.,1.,0.),  # green
                (0.,0.,0.1), # blue
                (0.,1.,1.),  # cyan
                (1.,1.,0.),  # yellow
                (1.,0.,1.),  # magenta
                (1.,1.,1.),  # white
                # (0.32,0.32,0.32),  # gray32
                (0.18,0.31,0.31),  # IRAF blue-green
                (1.,1.,1.),  # white
                (1.,1.,1.),  # white
                (1.,1.,1.),  # white
                (1.,1.,1.),  # white
                (1.,1.,1.),  # white
                (1.,1.,1.),  # white
        ]
        self.cursorColor = 2  # red
        if len(self.defaultColors) != nIrafColors:
            raise ValueError("defaultColors should have %d elements (has %d)" %
                (nIrafColors, len(self.defaultColors)))

        # old colors
        #       (1.,0.5,0.),      # coral
        #       (0.7,0.19,0.38),  # maroon
        #       (1.,0.65,0.),     # orange
        #       (0.94,0.9,0.55),  # khaki
        #       (0.85,0.45,0.83), # orchid
        #       (0.25,0.88,0.82), # turquoise
        #       (0.91,0.53,0.92), # violet
        #       (0.96,0.87,0.72)  # wheat

    def setCursorColor(self, color):
        if not 0 <= color < len(self.defaultColors):
            raise ValueError("Bad cursor color (%d) should be >=0 and <%d" %
                (color, len(self.defaultColors)-1))
        self.cursorColor = color

    def fontSize(self, gwidget):

        """Determine the unit font size for the given setup in pixels.
        The unit size refers to the horizonal size of fixed width characters
        (allow for proportionally sized fonts later?).

        Basically, if font aspect is not fixed, the unit font size is
        proportional to the window dimension (for v and h independently),
        with the exception that if min or max pixel sizes are enabled,
        they are 'clipped' at the specified value. If font aspect is fixed,
        then the horizontal size is the driver if the window is higher than
        wide and vertical size for the converse.
        """

        hwinsize = gwidget.winfo_width()
        vwinsize = gwidget.winfo_height()
        hsize = hwinsize * self.UnitFontHWindowFraction
        vsize = vwinsize * self.UnitFontVWindowFraction
        if self.minUnitHFontSize is not None:
            hsize = max(hsize,self.minUnitHFontSize)
        if self.minUnitVFontSize is not None:
            vsize = max(vsize,self.minUnitVFontSize)
        if self.maxUnitHFontSize is not None:
            hsize = min(hsize,self.maxUnitHFontSize)
        if self.maxUnitVFontSize is not None:
            vsize = min(vsize,self.maxUnitVFontSize)
        if not self.isFixedAspectFont:
            fontAspect = vsize/hsize
        else:
            hsize = min(hsize, vsize/self.fontAspect)
            vsize = hsize * self.fontAspect
            fontAspect = self.fontAspect
        return (hsize, fontAspect)

    def getIrafColors(self):

        return self.defaultColors

# create the singleton instance

_irafGkiConfig = IrafGkiConfig()

#-----------------------------------------------

class IrafLineStyles:

    def __init__(self):

        self.patterns = [0x0000,0xFFFF,0x00FF,0x5555,0x33FF]

class IrafHatchFills:

    def __init__(self):

        # Each fill pattern is a 32x4 ubyte array (represented as 1-d).
        # These are computed on initialization rather than using a
        # 'data' type initialization since they are such simple patterns.
        # these arrays are stored in a pattern list. Pattern entries
        # 0-2 should never be used since they are not hatch patterns.

        # so much for these, currently PyOpenGL does not support
        # glPolygonStipple()! But adding it probably is not too hard.

        self.patterns = [None]*7
        # pattern 3, vertical stripes
        p = Numeric.zeros(128,Numeric.Int8)
        p[0:4] = [0x92,0x49,0x24,0x92]
        for i in xrange(31):
            p[(i+1)*4:(i+2)*4] = p[0:4]
        self.patterns[3] = p
        # pattern 4, horizontal stripes
        p = Numeric.zeros(128,Numeric.Int8)
        p[0:4] = [0xFF,0xFF,0xFF,0xFF]
        for i in xrange(10):
            p[(i+1)*12:(i+1)*12+4] = p[0:4]
        self.patterns[4] = p
        # pattern 5, close diagonal striping
        p = Numeric.zeros(128,Numeric.Int8)
        p[0:12] = [0x92,0x49,0x24,0x92,0x24,0x92,0x49,0x24,0x49,0x24,0x92,0x49]
        for i in xrange(9):
            p[(i+1)*12:(i+2)*12] = p[0:12]
        p[120:128] = p[0:8]
        self.patterns[5] = p
        # pattern 6, diagonal stripes the other way
        p = Numeric.zeros(128,Numeric.Int8)
        p[0:12] = [0x92,0x49,0x24,0x92,0x49,0x24,0x92,0x49,0x24,0x92,0x49,0x24]
        for i in xrange(9):
            p[(i+1)*12:(i+2)*12] = p[0:12]
        p[120:128] = p[0:8]
        self.patterns[6] = p

class LineAttributes:

    def __init__(self):

        self.linestyle = 1
        self.linewidth = 1.0
        self.color = 1

    def set(self, linestyle, linewidth, color):

        self.linestyle = linestyle
        self.linewidth = linewidth
        self.color = color

class FillAttributes:

    def __init__(self):

        self.fillstyle = 1
        self.color = 1

    def set(self, fillstyle, color):

        self.fillstyle = fillstyle
        self.color = color

class MarkerAttributes:

    def __init__(self):

        # the first two attributes are not currently used in IRAF, so ditch'em
        self.color = 1

    def set(self, markertype, size, color):

        self.color = color
