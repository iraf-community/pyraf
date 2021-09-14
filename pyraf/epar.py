""" Main module for the PyRAF-version of the Epar parameter editor

M.D. De La Pena, 2000 February 04
"""


from stsci.tools import capable
if capable.OF_GRAPHICS:
    from tkinter.messagebox import askokcancel, showwarning, showerror
    import os
    import io
    from stsci.tools import listdlg, eparoption, editpar, irafutils
    from . import iraf
    from . import irafpar
    from . import irafhelp
    from . import wutil
    from .pyrafglobals import pyrafDir
else:
    wutil = None

    class editpar():

        class EditParDialog():
            pass  # dummy so that code below can import


from stsci.tools.irafglobals import IrafError

# tool help
eparHelpString = """\
The PyRAF Parameter Editor window is used to edit IRAF parameter sets.  It
allows multiple parameter sets to be edited concurrently (e.g., to edit IRAF
Psets).  It also allows the IRAF task help to be displayed in a separate window
that remains accessible while the parameters are being edited.


Editing Parameters
--------------------

Parameter values are modified using various GUI widgets that depend on the
parameter properties.  It is possible to edit parameters using either the mouse
or the keyboard.  Most parameters have a context-dependent menu accessible via
right-clicking that enables unlearning the parameter (restoring its value to
the task default), clearing the value, and activating a file browser that
allows a filename to be selected and entered in the parameter field.  Some
items on the right-click pop-up menu may be disabled depending on the parameter
type (e.g., the file browser cannot be used for numeric parameters.)

The mouse-editing behavior should be familiar, so the notes below focus on
keyboard-editing.  When the editor starts, the first parameter is selected.  To
select another parameter, use the Tab key (Shift-Tab to go backwards) or Return
to move the focus from item to item. The Up and Down arrow keys also move
between fields.  The toolbar buttons can also be selected with Tab.  Use the
space bar to "push" buttons or activate menus.

Enumerated Parameters
        Parameters that have a list of choices use a drop-down menu.  The space
        bar causes the menu to appear; once it is present, the up/down arrow
        keys can be used to select different items.  Items in the list have
        accelerators (underlined, generally the first letter) that can be typed
        to jump directly to that item.  When editing is complete, hit Return or
        Tab to accept the changes, or type Escape to close the menu without
        changing the current parameter value.

Boolean Parameters
        Boolean parameters appear as Yes/No radio buttons.  Hitting the space
        bar toggles the setting, while 'y' and 'n' can be typed to select the
        desired value.

Parameter Sets
        Parameter sets (Psets) appear as a button which, when clicked, brings
        up a new editor window.  Note that two (or more) parameter lists can be
        edited concurrently.  The Package and Task identification are shown
        in the window and in the title bar.

Text Entry Fields
        Strings, integers, floats, etc. appear as text-entry fields.  Values
        are verified to to be legal before being stored in the parameter. If an
        an attempt is made to set a parameter to an illegal value, the program
        beeps and a warning message appears in the status bar at the bottom of
        the window.

        To see the value of a string that is longer than the entry widget,
        either use the left mouse button to do a slow "scroll" through the
        entry or use the middle mouse button to "pull" the value in the entry
        back and forth quickly.  In either case, just click in the entry widget
        with the mouse and then drag to the left or right.  If there is a
        selection highlighted, the middle mouse button may paste it in when
        clicked.  It may be necessary to click once with the left mouse
        button to undo the selection before using the middle button.

        You can also use the left and right arrow keys to scroll through the
        selection.  Control-A jumps to the beginning of the entry, and
        Control-E jumps to the end of the entry.


The Menu Bar
--------------

File menu:
    Execute
             Save all the parameters, close the editor windows, and start the
             IRAF task.  This is disabled in the secondary windows used to edit
             Psets.
    Save & Quit
             Save the parameters and close the editor window.  The task is not
             executed.
    Save As...
             Save the parameters to a user-specified file.  The task is not
             executed.
    Unlearn/Defaults
             Restore all parameters to the system default values for this
             task.  Note that individual parameters can be unlearned using the
             menu shown by right-clicking on the parameter entry.
    Cancel
             Cancel editing session and exit the parameter editor.  Changes
             that were made to the parameters are not saved; the parameters
             retain the values they had when the editor was started.

Open... menu:
     Load parameters from any applicable user file found.  Values are not
     stored unless Execute or Save is then selected.  If no such files are
     found, this menu is not shown.

Options menu:
    Display Task Help in a Window
             Help on the IRAF task is available through the Help menu.  If this
             option is selected, the help text is displayed in a pop-up window.
             This is the default behavior.
    Display Task Help in a Browser
             If this option is selected, instead of a pop-up window help is
             displayed in the user's web browser.  This requires access to
             the internet and is a somewhat experimental feature.  The HTML
             version of help does have some nice features such as links to
             other IRAF tasks.

Help menu:
    Task Help
             Display help on the IRAF task whose parameters are being edited.
             By default the help pops up in a new window, but the help can also
             be displayed in a web browser by modifying the Options.
    EPAR Help
             Display this help.
    Show Log
             Display the historical log of all the status messages that so
             far have been displayed in the status area at the very bottom
             of the user interface.


Toolbar Buttons
-----------------

The Toolbar contains a set of buttons that provide shortcuts for the most
common menu bar actions.  Their names are the same as the menu items given
above: Execute, Save & Quit, Defaults, Cancel, and Task Help.  The Execute
button is disabled in the secondary windows used to edit Psets.

Note that the toolbar buttons are accessible from the keyboard using the Tab
and Shift-Tab keys.  They are located in sequence before the first parameter.
If the first parameter is selected, Shift-Tab backs up to the "Task Help"
button, and if the last parameter is selected then Tab wraps around and selects
the "Execute" button.
"""


def epar(theTask, parent=None, isChild=0):

    if wutil is None or not wutil.hasGraphics:
        raise IrafError("Cannot run epar without graphics windows")

    if not isChild:
        oldFoc = wutil.getFocalWindowID()
        wutil.forceFocusToNewWindow()

    PyrafEparDialog(theTask, parent, isChild)

    if not isChild:
        wutil.setFocusTo(oldFoc)


class PyrafEparDialog(editpar.EditParDialog):

    def __init__(self,
                 theTask,
                 parent=None,
                 isChild=0,
                 title="PyRAF Parameter Editor",
                 childList=None):

        # Init base - calls _setTaskParsObj(), sets self.taskName, etc
        editpar.EditParDialog.__init__(self,
                                       theTask,
                                       parent,
                                       isChild,
                                       title,
                                       childList,
                                       resourceDir=pyrafDir)

    def _setTaskParsObj(self, theTask):
        """ Overridden version, so as to use Iraf tasks and IrafParList """

        if isinstance(theTask, irafpar.IrafParList):
            # IrafParList acts as an IrafTask for our purposes
            self._taskParsObj = theTask
        else:
            # theTask must be a string name of, or an IrafTask object
            self._taskParsObj = iraf.getTask(theTask)

    def _doActualSave(self,
                      filename,
                      comment,
                      set_ro=False,
                      overwriteRO=False):
        """ Overridden version, so as to check for a special case. """
        # Skip the save if the thing being edited is an IrafParList without
        # an associated file (in which case the changes are just being
        # made in memory.)
        if isinstance(self._taskParsObj, irafpar.IrafParList) and \
           not self._taskParsObj.getFilename():
            return ''  # skip it
        else:
            retval = ''
            try:
                if filename and os.path.exists(filename) and overwriteRO:
                    irafutils.setWritePrivs(filename, True)
                retval = self._taskParsObj.saveParList(filename=filename,
                                                       comment=comment)
            except OSError:
                retval = "Error saving to " + str(
                    filename) + ".  Please check privileges."
                showerror(message=retval, title='Error Saving File')
            if set_ro:
                irafutils.setWritePrivs(filename, False, ignoreErrors=True)
            return retval

    def _showOpenButton(self):
        """ Override this so that we can use rules in irafpar. """
        # See if there exist any special versions on disk to load
        # Note that irafpar caches the list of these versions
        return irafpar.haveSpecialVersions(self.taskName, self.pkgName)

    def _overrideMasterSettings(self):
        """ Override this to tailor the GUI specifically for epar. """
        self._useSimpleAutoClose = True

        self._saveAndCloseOnExec = True
        self._showSaveCloseOnExec = False
        self._showFlaggingChoice = False

        self._showExtraHelpButton = True

        self._appName = "EPAR"
        self._appHelpString = eparHelpString
        self._unpackagedTaskTitle = "Filename"
        self._defaultsButtonTitle = "Unlearn"
        self._defSaveAsExt = '.par'

        if not wutil.WUTIL_USING_X:
            x = "#ccccff"
            self._frmeColor = x
            self._taskColor = x
            self._bboxColor = x
            self._entsColor = x

    def _nonStandardEparOptionFor(self, paramTypeStr):
        """ Override to allow use of PsetEparOption.
            Return None or a class which derives from EparOption. """
        if paramTypeStr == "pset":
            from . import pseteparoption
            return pseteparoption.PsetEparOption
        else:
            return None

    # Two overrides of deafult behavior, related to unpackaged "tasks"
    def _isUnpackagedTask(self):
        return isinstance(self._taskParsObj, irafpar.IrafParList)

    def _getOpenChoices(self):
        return irafpar.getSpecialVersionFiles(self.taskName, self.pkgName)

    # OPEN: load parameter settings from a user-specified file
    def pfopen(self, event=None):
        """ Load the parameter settings from a user-specified file.  Any
        changes here must be coordinated with the corresponding tpar pfopen
        function. """

        fname = self._openMenuChoice.get()
        if fname is None:
            return

        newParList = irafpar.IrafParList(self.taskName, fname)

        # Set the GUI entries to these values (let the user Save after)
        self.setAllEntriesFromParList(newParList)
        self.freshenFocus()
        self.showStatus("Loaded parameter values from: " + fname, keep=2)

    def _getSaveAsFilter(self):
        """ Return a string to be used as the filter arg to the save file
            dialog during Save-As. """
        filt = '*.par'
        upx = iraf.envget("uparm_aux", "")
        if 'UPARM_AUX' in os.environ:
            upx = os.environ['UPARM_AUX']
        if len(upx) > 0:
            filt = iraf.Expand(upx) + "/*.par"
        return filt

    def _saveAsPreSave_Hook(self, fnameToBeUsed):
        """ Override to check for (and warn about) PSETs. """
        # Notify them that pset children will not be saved as part of
        # their special version
        pars = []
        for par in self._taskParsObj.getParList():
            if par.type == "pset":
                pars.append(par.name)
        if len(pars):
            msg = "If you have made any changes to the PSET "+ \
                  "values for:\n\n"
            for p in pars:
                msg += "\t\t" + p + "\n"
            msg = msg+"\nthose changes will NOT be explicitly saved to:"+ \
                '\n\n"'+fnameToBeUsed+'"'
            showwarning(message=msg, title='PSET Save-As Not Yet Supported')

    def _saveAsPostSave_Hook(self, fnameToBeUsed):
        """ Override this to notify irafpar. """
        # Notify irafpar that there is a new special-purpose file on the scene
        irafpar.newSpecialParFile(self.taskName, self.pkgName, fnameToBeUsed)

    def htmlHelp(self, helpString=None, title=None, istask=False, tag=None):
        """ Overridden version, use irafhelp to invoke the HTML help """
        # Help on EPAR itself will use helpString and title.  If so, defer
        # to base, otherwise call irafhelp.help() for task specific text.
        if helpString and title:
            editpar.EditParDialog.htmlHelp(self,
                                           helpString,
                                           title,
                                           istask=istask,
                                           tag=tag)
        else:
            # Invoke the STSDAS HTML help
            irafhelp.help(self.taskName, html=1)

    # Get the task help in a string (RLW)
    def getHelpString(self, taskname):
        """ Override this - in PyRAF we'll always use use iraf system help.
            Do not query the task object. """
        fh = io.StringIO()
        iraf.system.help(taskname, page=0, Stdout=fh, Stderr=fh)
        result = fh.getvalue()
        fh.close()
        return result
