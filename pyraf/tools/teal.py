""" Main module for the ConfigObj version of the parameter task editor: TEAL.
$Id$
"""
import os
import sys
import traceback
from . import configobj, cfgpars, editpar, vtor_checks
from .cfgpars import APP_NAME
from .irafutils import printColsAuto, rglob, setWritePrivs
from . import capable

if capable.OF_GRAPHICS:
    from tkinter.filedialog import askopenfilename
    from tkinter.messagebox import showerror, showwarning


# tool help
tealHelpString = """\
The TEAL (Task Editor And Launcher) GUI is used to edit task parameters in a
parameter-dependent way.  After editing, it allows the user to launch
(execute) the task.  It also allows the user to view task help in a separate
window that remains accessible while the parameters are being edited.


Editing Parameters
--------------------

Parameter values are modified using various GUI widgets that depend on the
parameter properties.  It is possible to edit parameters using either the mouse
or the keyboard.  Most parameters have a context-dependent menu accessible via
right-clicking that enables resetting the parameter (restoring its value to
the task default), clearing the value, or even activating a file browser that
allows a filename to be selected and entered into the parameter field.  Some
items on the right-click pop-up menu may be disabled depending on the parameter
type (e.g. the file browser cannot be used for numeric parameters.)

The mouse-editing behavior should be intuitive, so the notes below focus on
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
             Start the task running with the currently edited parameter values.
             If the Option "Save and Close on Execute" is set, this will save
             all the parameters and close the editor window.
    Save
             Save the parameters to the file named in the title bar.  This
             does not close the editor window, nor does it execute the task.
             If however, this button appears as "Save & Quit", then it will
             in fact close the editor window after saving.
    Save As...
             Save the parameters to a user-specified file.  This does not
             close the editor window, nor does it execute the task.
    Defaults
             Reset all parameters to the system default values for this
             task.  Note that individual parameters can be reset using the
             menu shown by right-clicking on the parameter entry.
    Close
             Close the parameter editor.  If there are unsaved changes, the
             user is prompted to save them.  Either way, this action returns
             to the calling routine a Python dict of the currently selected
             parameter values.
    Cancel
             Cancel the editing session by exiting the parameter editor.  All
             recent changes that were made to the parameters are lost (going
             back until the last Save or Save As).  This action returns
             a Python None to the calling routine.

Open... menu:
     Load and edit parameters from any applicable file found for the current
     task.  This changes the current file being edited (see the name listed
     in the title bar) to the one selected to be opened.  If no such files
     are found, this menu is not shown.

Options menu:
    Display Task Help in a Window
             Help on the task is available through the Help menu.  If this
             option is selected, the help text is displayed in a pop-up window.
             This is the default behavior.
    Display Task Help in a Browser
             If this option is selected, instead of a pop-up window, help is
             displayed in the user's web browser.  This requires access to
             the internet and is a somewhat experimental feature.  Any HTML
             version of the task's help need to be provided by the task.
    Save and Close on Execute
             If this option is selected, the parameter editing window will be
             closed right before task execution as if the Close button had
             been clicked.  This is the default behavior.  For short-running
             tasks, it may be interesting to leave TEAL open and continue to
             execute while tweaking certain parameter values.

Help menu:
    Task Help
             Display help on the task whose parameters are being edited.
             By default the help pops up in a new window, but the help can also
             be displayed in a web browser by modifying the Options.
    TEAL Help
             Display this help.
    Show Log
             Display the historical log of all the status messages that so
             far have been displayed in the status area at the very bottom
             of the user interface.


Toolbar Buttons
-----------------

The Toolbar contains a set of buttons that provide shortcuts for the most
common menu bar actions.  Their names are the same as the menu items given
above: Execute, Save (or Save & Quit), Close, Cancel, and Defaults.

Note that the toolbar buttons are accessible from the keyboard using the Tab
and Shift-Tab keys.  They are located in sequence before the first parameter.
If the first parameter is selected, Shift-Tab backs up to the "Task Help"
button, and if the last parameter is selected then Tab wraps around and selects
the "Execute" button.
"""


# Starts a GUI session, or simply loads a file
def teal(theTask, parent=None, loadOnly=False, returnAs="dict",
         canExecute=True, strict=False, errorsToTerm=False,
         autoClose=True, defaults=False):
#        overrides=None):
    """ Start the GUI session, or simply load a task's ConfigObj. """
    if loadOnly: # this forces returnAs="dict"
        obj = None
        try:
            obj = cfgpars.getObjectFromTaskArg(theTask, strict, defaults)
#           obj.strictUpdate(overrides) # ! would need to re-verify after this !
        except Exception as re: # catches RuntimeError and KeyError and ...
            # Since we are loadOnly, don't pop up the GUI for this
            if strict:
                raise
            else:
                print(re.message.replace('\n\n','\n'))
        return obj
    else:
        if returnAs not in ("dict", "status", None):
            raise ValueError("Invalid value for returnAs arg: " + str(returnAs))
        dlg = None
        try:
            # if setting to all defaults, go ahead and load it here, pre-GUI
            if defaults:
                theTask = cfgpars.getObjectFromTaskArg(theTask, strict, True)
            # now create/run the dialog
            dlg = ConfigObjEparDialog(theTask, parent=parent,
                                      autoClose=autoClose,
                                      strict=strict,
                                      canExecute=canExecute)
#                                     overrides=overrides)
        except cfgpars.NoCfgFileError as ncf:
            log_last_error()
            if errorsToTerm:
                print(str(ncf).replace('\n\n','\n'))
            else:
                popUpErr(parent=parent,message=str(ncf),title="Unfound Task")
        except Exception as re: # catches RuntimeError and KeyError and ...
            log_last_error()
            if errorsToTerm:
                print(re.message.replace('\n\n','\n'))
            else:
                popUpErr(parent=parent, message=re.message,
                         title="Bad Parameters")

        # Return, depending on the mode in which we are operating
        if returnAs is None:
            return

        if returnAs == "dict":
            if dlg is None or dlg.canceled():
                return None
            else:
                return dlg.getTaskParsObj()

        # else, returnAs == "status"
        if dlg is None or dlg.canceled():
            return -1
        if dlg.executed():
            return 1
        return 0 # save/closed
        # Note that you should be careful not to use "status" and
        # autoClose=False, because the user can Save then Cancel


def load(theTask, canExecute=True, strict=True, defaults=False):
    """ Shortcut to load TEAL .cfg files for non-GUI access where
    loadOnly=True. """
    return teal(theTask, parent=None, loadOnly=True, returnAs="dict",
                canExecute=canExecute, strict=strict, errorsToTerm=True,
                defaults=defaults)


def log_last_error():
    import time
    f = open(cfgpars.getAppDir()+os.sep+'last_error.txt','w')
    f.write(time.asctime()+'\n\n')
    f.write(traceback.format_exc()+'\n')
    f.close()


def unlearn(taskPkgName, deleteAll=False):
    """ Find the task named taskPkgName, and delete any/all user-owned
    .cfg files in the user's resource directory which apply to that task.
    Like a unix utility, this returns 0 on success (no files found or only
    1 found but deleted).  For multiple files found, this uses deleteAll,
    returning the file-name-list if deleteAll is False (to indicate the
    problem) and without deleting any files.  MUST check return value.
    This does not prompt the user or print to the screen. """

    # this WILL throw an exception if the taskPkgName isn't found
    flist = cfgpars.getUsrCfgFilesForPyPkg(taskPkgName) # can raise
    if flist is None or len(flist) == 0:
        return 0
    if len(flist) == 1:
        os.remove(flist[0])
        return 0
    # at this point, we know more than one matching file was found
    if deleteAll:
        for f in flist:
            os.remove(f)
        return 0
    else:
        return flist # let the caller know this is an issue


def diffFromDefaults(theTask, report=False):
    """ Load the given file (or existing object), and return a dict
    of its values which are different from the default values.  If report
    is set, print to stdout the differences. """
    # get the 2 dicts (trees: dicts of dicts)
    defaultTree = load(theTask, canExecute=False, strict=True, defaults=True)
    thisTree    = load(theTask, canExecute=False, strict=True, defaults=False)
    # they must be flattenable
    defaultFlat = cfgpars.flattenDictTree(defaultTree)
    thisFlat    = cfgpars.flattenDictTree(thisTree)
    # use the "set" operations till there is a dict.diff()
    # thanks to:  http://stackoverflow.com/questions/715234
    diffFlat = dict( set(thisFlat.items()) - \
                     set(defaultFlat.items()) )
    if report:
        defaults_of_diffs_only = {}
#       { k:defaultFlat[k] for k in diffFlat.keys() }
        for k in diffFlat:
            defaults_of_diffs_only[k] = defaultFlat[k]
        msg = 'Non-default values of "'+str(theTask)+'":\n'+ \
              _flat2str(diffFlat)+ \
              '\n\nDefault values:\n'+ \
              _flat2str(defaults_of_diffs_only)
        print(msg)
    return diffFlat

def _flat2str(fd): # waiting for a nice pretty-print
    rv = '{\n'
    for k in fd.keys(): rv += repr(k)+': '+repr(fd[k])+'\n'
    return rv+'}'

def _isInstalled(fullFname):
    """ Return True if the given file name is located in an
    installed area (versus a user-owned file) """
    if not fullFname: return False
    if not os.path.exists(fullFname): return False

    import site
    instAreas = site.getsitepackages()

    if len(instAreas) < 1:
        instAreas = [ os.path.dirname(os.__file__) ]
    for ia in instAreas:
        if fullFname.find(ia) >= 0:
            return True
    return False


def popUpErr(parent=None, message="", title="Error"):
    # withdraw root, could standardize w/ EditParDialog.__init__()
    if parent is None:
        import tkinter
        root = tkinter.Tk()
#       root.lift()
        root.after_idle(root.withdraw)
    showerror(message=message, title=title, parent=parent)

# We'd love to somehow force the dialog to the front here in popUpErr (on OSX)
# but cannot since the Python process started from the Terminal is not an
# Aqua app (unless it became so within PyRAF).  This thread
#    http://objectmix.com/python/350288-tkinter-osx-lift.html
# describes it well.


def execEmbCode(SCOPE, NAME, VAL, TEAL, codeStr):
    """ .cfgspc embedded code execution is done here, in a relatively confined
        space.  The variables available to the code to be executed are:
              SCOPE, NAME, VAL, PARENT, TEAL
        The code string itself is expected to set a var named OUT
    """
    PARENT = None
    if TEAL:
        PARENT = TEAL.top
    OUT = None
    ldict = locals()  # will have OUT in it
    exec(codeStr, globals(), ldict)  # nosec
    return ldict['OUT']


def print_tasknames(pkgName, aDir, term_width=80, always=False,
                    hidden=None):
    """ Print a message listing TEAL-enabled tasks available under a
        given installation directory (where pkgName resides).
        If always is True, this will always print when tasks are
        found; otherwise it will only print found tasks when in interactive
        mode.
        The parameter 'hidden' supports a list of input tasknames that should
        not be reported even though they still exist.
    """
    # See if we can bail out early
    # sys.ps1 is only defined in interactive mode
    if not always and not hasattr(sys, 'ps1'):
        return  # leave here, we're in someone's script

    # Check for tasks
    taskDict = cfgpars.findAllCfgTasksUnderDir(aDir)
    tasks = [x for x in taskDict.values() if len(x) > 0]
    if hidden: # could even account for a single taskname as input here if needed
        for x in hidden:
            if x in tasks: tasks.remove(x)
    # only be verbose if there something found
    if len(tasks) > 0:
        sortedUniqTasks = sorted(set(tasks))
        if len(sortedUniqTasks) == 1:
            tlines = 'The following task in the '+pkgName+\
                     ' package can be run with TEAL:\n'
        else:
            tlines = 'The following tasks in the '+pkgName+\
                     ' package can be run with TEAL:\n'
        tlines += printColsAuto(sortedUniqTasks, term_width=term_width,
                                min_pad=2)
        print(tlines)

def getHelpFileAsString(taskname,taskpath):
    """
    This functions will return useful help as a string read from a file
    in the task's installed directory called "<module>.help".

    If no such file can be found, it will simply return an empty string.

    Notes
    -----
    The location of the actual help file will be found under the task's
    installed directory using 'irafutils.rglob' to search all sub-dirs to
    find the file. This allows the help file to be either in the tasks
    installed directory or in any sub-directory, such as a "help/" directory.

    Parameters
    ----------
    taskname: string
        Value of `__taskname__` for a module/task

    taskpath: string
        Value of `__file__` for an installed module which defines the task

    Returns
    -------
    helpString: string
        multi-line string read from the file '<taskname>.help'

    """
    #get the local library directory where the code is stored
    pathsplit=os.path.split(taskpath) # taskpath should be task's __file__
    if taskname.find('.') > -1: # if taskname is given as package.taskname...
        helpname=taskname.split(".")[1]    # taskname should be __taskname__ from task's module
    else:
        helpname = taskname
    localdir = pathsplit[0]
    if localdir == '':
       localdir = '.'
    helpfile=rglob(localdir,helpname+".help")[0]

    if os.access(helpfile,os.R_OK):
        fh=open(helpfile,'r')
        ss=fh.readlines()
        fh.close()
        helpString=""
        for line in ss:
            helpString+=line
    else:
        helpString= ''

    return helpString


def cfgGetBool(theObj, name, dflt):
    """ Get a stringified val from a ConfigObj obj and return it as bool """
    strval = theObj.get(name, None)
    if strval is None:
        return dflt
    return strval.lower().strip() == 'true'


# Main class
class ConfigObjEparDialog(editpar.EditParDialog): # i.e. TEAL
    """ The TEAL GUI. """

    FALSEVALS = (None, False, '', 0, 0.0, '0', '0.0', 'OFF', 'Off', 'off',
                 'NO', 'No', 'no', 'N', 'n', 'FALSE', 'False', 'false')

    def __init__(self, theTask, parent=None, title=APP_NAME,
                 isChild=0, childList=None, autoClose=False,
                 strict=False, canExecute=True):
#                overrides=None,
        self._do_usac = autoClose

        # Keep track of any passed-in args before creating the _taskParsObj
#       self._overrides = overrides
        self._canExecute = canExecute
        self._strict = strict

        # Init base - calls _setTaskParsObj(), sets self.taskName, etc
        # Note that this calls _overrideMasterSettings()
        editpar.EditParDialog.__init__(self, theTask, parent, isChild,
                                       title, childList,
                                       resourceDir=cfgpars.getAppDir())
        # We don't return from this until the GUI is closed


    def _overrideMasterSettings(self):
        """ Override so that we can run in a different mode. """
        # config-obj dict of defaults
        cod = self._getGuiSettings()

        # our own GUI setup
        self._appName              = APP_NAME
        self._appHelpString        = tealHelpString
        self._useSimpleAutoClose   = self._do_usac
        self._showExtraHelpButton  = False
        self._saveAndCloseOnExec   = cfgGetBool(cod, 'saveAndCloseOnExec', True)
        self._showHelpInBrowser    = cfgGetBool(cod, 'showHelpInBrowser', False)
        self._writeProtectOnSaveAs = cfgGetBool(cod, 'writeProtectOnSaveAsOpt', True)
        self._flagNonDefaultVals   = cfgGetBool(cod, 'flagNonDefaultVals', None)
        self._optFile              = APP_NAME.lower()+".optionDB"

        # our own colors
        # prmdrss teal: #00ffaa, pure cyan (teal) #00ffff (darker) #008080
        # "#aaaaee" is a darker but good blue, but "#bbbbff" pops
        ltblu = "#ccccff" # light blue
        drktl = "#008888" # darkish teal
        self._frmeColor = cod.get('frameColor', drktl)
        self._taskColor = cod.get('taskBoxColor', ltblu)
        self._bboxColor = cod.get('buttonBoxColor', ltblu)
        self._entsColor = cod.get('entriesColor', ltblu)
        self._flagColor = cod.get('flaggedColor', 'brown')

        # double check _canExecute, but only if it is still set to the default
        if self._canExecute and self._taskParsObj: # default _canExecute=True
            self._canExecute = self._taskParsObj.canExecute()
        self._showExecuteButton = self._canExecute

        # check on the help string - just to see if it is HTML
        # (could use HTMLParser here if need be, be quick and simple tho)
        hhh = self.getHelpString(self.pkgName+'.'+self.taskName)
        if hhh:
            hhh = hhh.lower()
            if hhh.find('<html') >= 0 or hhh.find('</html>') > 0:
                self._knowTaskHelpIsHtml = True
            elif hhh.startswith('http:') or hhh.startswith('https:'):
                self._knowTaskHelpIsHtml = True
            elif hhh.startswith('file:') and \
                 (hhh.endswith('.htm') or hhh.endswith('.html')):
                self._knowTaskHelpIsHtml = True


    def _preMainLoop(self):
        """ Override so that we can do some things right before activating. """
        # Put the fname in the title. EditParDialog doesn't do this by default
        self.updateTitle(self._taskParsObj.filename)


    def _doActualSave(self, fname, comment, set_ro=False, overwriteRO=False):
        """ Override this so we can handle case of file not writable, as
            well as to make our _lastSavedState copy. """
        self.debug('Saving, file name given: '+str(fname)+', set_ro: '+\
                   str(set_ro)+', overwriteRO: '+str(overwriteRO))
        cantWrite = False
        inInstArea = False
        if fname in (None, ''): fname = self._taskParsObj.getFilename()
        # now do some final checks then save
        try:
            if _isInstalled(fname): # check: may be installed but not read-only
                inInstArea = cantWrite = True
            else:
                # in case of save-as, allow overwrite of read-only file
                if overwriteRO and os.path.exists(fname):
                    setWritePrivs(fname, True, True) # try make writable
                # do the save
                rv=self._taskParsObj.saveParList(filename=fname,comment=comment)
        except IOError:
            cantWrite = True

        # User does not have privs to write to this file. Get name of local
        # choice and try to use that.
        if cantWrite:
            fname = self._taskParsObj.getDefaultSaveFilename()
            # Tell them the context is changing, and where we are saving
            msg = 'Read-only config file for task "'
            if inInstArea:
                msg = 'Installed config file for task "'
            msg += self._taskParsObj.getName()+'" is not to be overwritten.'+\
                  '  Values will be saved to: \n\n\t"'+fname+'".'
            showwarning(message=msg, title="Will not overwrite!")
            # Try saving to their local copy
            rv=self._taskParsObj.saveParList(filename=fname, comment=comment)

        # Treat like a save-as (update title for ALL save ops)
        self._saveAsPostSave_Hook(fname)

        # Limit write privs if requested (only if not in the rc dir)
        if set_ro and os.path.dirname(os.path.abspath(fname)) != \
                                      os.path.abspath(self._rcDir):
            cfgpars.checkSetReadOnly(fname)

        # Before returning, make a copy so we know what was last saved.
        # The dict() method returns a deep-copy dict of the keyvals.
        self._lastSavedState = self._taskParsObj.dict()
        return rv


    def _saveAsPostSave_Hook(self, fnameToBeUsed_UNUSED):
        """ Override this so we can update the title bar. """
        self.updateTitle(self._taskParsObj.filename) # _taskParsObj is correct


    def hasUnsavedChanges(self):
        """ Determine if there are any edits in the GUI that have not yet been
        saved (e.g. to a file). """

        # Sanity check - this case shouldn't occur
        if self._lastSavedState is None:
            raise RuntimeError("BUG: Please report this as it should never occur.")

        # Force the current GUI values into our model in memory, but don't
        # change anything.  Don't save to file, don't even convert bad
        # values to their previous state in the gui.  Note that this can
        # leave the GUI in a half-saved state, but since we are about to exit
        # this is OK.  We only want prompting to occur if they decide to save.
        badList = self.checkSetSaveEntries(doSave=False, fleeOnBadVals=True,
                                           allowGuiChanges=False)
        if badList:
            return True

        # Then compare our data to the last known saved state.  MAKE SURE
        # the LHS is the actual dict (and not 'self') to invoke the dict
        # comparison only.
        return self._lastSavedState != self._taskParsObj


    # Employ an edited callback for a given item?
    def _defineEditedCallbackObjectFor(self, parScope, parName):
        """ Override to allow us to use an edited callback. """

        # We know that the _taskParsObj is a ConfigObjPars
        triggerStrs = self._taskParsObj.getTriggerStrings(parScope, parName)

        # Some items will have a trigger, but likely most won't
        if triggerStrs and len(triggerStrs) > 0:
            return self
        else:
            return None


    def _nonStandardEparOptionFor(self, paramTypeStr):
        """ Override to allow use of TealActionParButton.
        Return None or a class which derives from EparOption. """

        if paramTypeStr == 'z':
            from . import teal_bttn
            return teal_bttn.TealActionParButton
        else:
            return None


    def updateTitle(self, atitle):
        """ Override so we can append read-only status. """
        if atitle and os.path.exists(atitle):
            if _isInstalled(atitle):
                atitle += '  [installed]'
            elif not os.access(atitle, os.W_OK):
                atitle += '  [read only]'
        super(ConfigObjEparDialog, self).updateTitle(atitle)


    def edited(self, scope, name, lastSavedVal, newVal, action):
        """ This is the callback function invoked when an item is edited.
            This is only called for those items which were previously
            specified to use this mechanism.  We do not turn this on for
            all items because the performance might be prohibitive.
            This kicks off any previously registered triggers. """

        # Get name(s) of any triggers that this par triggers
        triggerNamesTup = self._taskParsObj.getTriggerStrings(scope, name)
        if not triggerNamesTup:
            raise ValueError('Empty trigger name for: "' + name + '", consult the .cfgspc file.')

        # Loop through all trigger names - each one is a trigger to kick off -
        # in the order that they appear in the tuple we got.  Most cases will
        # probably only have a single trigger in the tuple.
        for triggerName in triggerNamesTup:
            # First handle the known/canned trigger names
#           print (scope, name, newVal, action, triggerName) # DBG: debug line

            # _section_switch_
            if triggerName == '_section_switch_':
                # Try to uniformly handle all possible par types here, not
                # just boolean (e.g. str, int, float, etc.)
                # Also, see logic in _BooleanMixin._coerceOneValue()
                state = newVal not in self.FALSEVALS
                self._toggleSectionActiveState(scope, state, (name,))
                continue

            # _2_section_switch_ (see notes above in _section_switch_)
            if triggerName == '_2_section_switch_':
                state = newVal not in self.FALSEVALS
                # toggle most of 1st section (as usual) and ALL of next section
                self._toggleSectionActiveState(scope, state, (name,))
                # get first par of next section (fpons) - is a tuple
                fpons = self.findNextSection(scope, name)
                nextSectScope = fpons[0]
                if nextSectScope:
                    self._toggleSectionActiveState(nextSectScope, state, None)
                continue

            # Now handle rules with embedded code (eg. triggerName=='_rule1_')
            if '_RULES_' in self._taskParsObj and \
               triggerName in self._taskParsObj['_RULES_'].configspec:
                # Get codeStr to execute it, but before we do so, check 'when' -
                # make sure this is an action that is allowed to cause a trigger
                ruleSig = self._taskParsObj['_RULES_'].configspec[triggerName]
                chkArgsDict = vtor_checks.sigStrToKwArgsDict(ruleSig)
                codeStr = chkArgsDict.get('code') # or None if didn't specify
                when2run = chkArgsDict.get('when') # or None if didn't specify

                greenlight = False # do we have a green light to eval the rule?
                if when2run is None:
                    greenlight = True # means run rule for any possible action
                else: # 'when' was set to something so we need to check action
                    # check value of action (poor man's enum)
                    if action not in editpar.GROUP_ACTIONS:
                        raise ValueError("Unknown action: " + str(action) +
                                         ', expected one of: ' +
                                         str(editpar.GROUP_ACTIONS))
                    # check value of 'when' (allow them to use comma-sep'd str)
                    # (readers be aware that values must be those possible for
                    #  'action', and 'always' is also allowed)
                    whenlist = when2run.split(',')
                    # warn for invalid values
                    for w in whenlist:
                        if not w in editpar.GROUP_ACTIONS and w != 'always':
                           print('WARNING: skipping bad value for when kwd: "'+\
                                  w+'" in trigger/rule: '+triggerName)
                    # finally, do the correlation
                    greenlight = 'always' in whenlist or action in whenlist

                # SECURITY NOTE: because this part executes arbitrary code, that
                # code string must always be found only in the configspec file,
                # which is intended to only ever be root-installed w/ the pkg.
                if codeStr:
                    if not greenlight:
                        continue # not an error, just skip this one
                    self.showStatus("Evaluating "+triggerName+' ...') #dont keep
                    self.top.update_idletasks() #allow msg to draw prior to exec
                    # execute it and retrieve the outcome
                    try:
                        outval = execEmbCode(scope, name, newVal, self, codeStr)
                    except Exception as ex:
                        outval = 'ERROR in '+triggerName+': '+str(ex)
                        print(outval)
                        msg = outval+':\n'+('-'*99)+'\n'+traceback.format_exc()
                        msg += 'CODE:  '+codeStr+'\n'+'-'*99+'\n'
                        self.debug(msg)
                        self.showStatus(outval, keep=1)

                    # Leave this debug line in until it annoys someone
                    msg = 'Value of "'+name+'" triggered "'+triggerName+'"'
                    stroutval = str(outval)
                    if len(stroutval) < 30: msg += '  -->  "'+stroutval+'"'
                    self.showStatus(msg, keep=0)
                    # Now that we have triggerName evaluated to outval, we need
                    # to look through all the parameters and see if there are
                    # any items to be affected by triggerName (e.g. '_rule1_')
                    self._applyTriggerValue(triggerName, outval)
                    continue

            # If we get here, we have an unknown/unusable trigger
            raise RuntimeError('Unknown trigger for: "'+name+'", named: "'+ \
                  str(triggerName)+'".  Please consult the .cfgspc file.')


    def findNextSection(self, scope, name):
        """ Starts with given par (scope+name) and looks further down the list
        of parameters until one of a different non-null scope is found.  Upon
        success, returns the (scope, name) tuple, otherwise (None, None). """
        # first find index of starting point
        plist = self._taskParsObj.getParList()
        start = 0
        for i in range(len(plist)):
            if scope == plist[i].scope and name == plist[i].name:
                start = i
                break
        else:
            print('WARNING: could not find starting par: '+scope+'.'+name)
            return (None, None)

        # now find first different (non-null) scope in a par, after start
        for i in range(start, len(plist)):
            if len(plist[i].scope) > 0 and plist[i].scope != scope:
                return (plist[i].scope, plist[i].name)
        # else didn't find it
        return (None, None)


    def _setTaskParsObj(self, theTask):
        """ Overridden version for ConfigObj. theTask can be either
            a .cfg file name or a ConfigObjPars object. """
        # Create the ConfigObjPars obj
        self._taskParsObj = cfgpars.getObjectFromTaskArg(theTask,
                                    self._strict, False)
        # Tell it that we can be used for catching debug lines
        self._taskParsObj.setDebugLogger(self)

        # Immediately make a copy of it's un-tampered internal dict.
        # The dict() method returns a deep-copy dict of the keyvals.
        self._lastSavedState = self._taskParsObj.dict()
        # do this here ??!! or before _lastSavedState ??!!
#       self._taskParsObj.strictUpdate(self._overrides)


    def _getSaveAsFilter(self):
        """ Return a string to be used as the filter arg to the save file
            dialog during Save-As. """
        # figure the dir to use, start with the one from the file
        absRcDir = os.path.abspath(self._rcDir)
        thedir = os.path.abspath(os.path.dirname(self._taskParsObj.filename))
        # skip if not writeable, or if is _rcDir
        if thedir == absRcDir or not os.access(thedir, os.W_OK):
            thedir = os.path.abspath(os.path.curdir)
        # create save-as filter string
        filt = thedir+'/*.cfg'
        envVarName = APP_NAME.upper()+'_CFG'
        if envVarName in os.environ:
            upx = os.environ[envVarName]
            if len(upx) > 0:  filt = upx+"/*.cfg"
        # done
        return filt


    def _getOpenChoices(self):
        """ Go through all possible sites to find applicable .cfg files.
            Return as an iterable. """
        tsk = self._taskParsObj.getName()
        taskFiles = set()
        dirsSoFar = [] # this helps speed this up (skip unneeded globs)

        # last dir
        aDir = os.path.dirname(self._taskParsObj.filename)
        if len(aDir) < 1: aDir = os.curdir
        dirsSoFar.append(aDir)
        taskFiles.update(cfgpars.getCfgFilesInDirForTask(aDir, tsk))

        # current dir
        aDir = os.getcwd()
        if aDir not in dirsSoFar:
            dirsSoFar.append(aDir)
            taskFiles.update(cfgpars.getCfgFilesInDirForTask(aDir, tsk))

        # task's python pkg dir (if tsk == python pkg name)
        try:
            x, pkgf = cfgpars.findCfgFileForPkg(tsk, '.cfg', taskName=tsk,
                              pkgObj=self._taskParsObj.getAssocPkg())
            taskFiles.update( (pkgf,) )
        except cfgpars.NoCfgFileError:
            pass # no big deal - maybe there is no python package

        # user's own resourceDir
        aDir = self._rcDir
        if aDir not in dirsSoFar:
            dirsSoFar.append(aDir)
            taskFiles.update(cfgpars.getCfgFilesInDirForTask(aDir, tsk))

        # extra loc - see if they used the app's env. var
        aDir = dirsSoFar[0] # flag to skip this if no env var found
        envVarName = APP_NAME.upper()+'_CFG'
        if envVarName in os.environ: aDir = os.environ[envVarName]
        if aDir not in dirsSoFar:
            dirsSoFar.append(aDir)
            taskFiles.update(cfgpars.getCfgFilesInDirForTask(aDir, tsk))

        # At the very end, add an option which we will later interpret to mean
        # to open the file dialog.
        taskFiles = list(taskFiles) # so as to keep next item at end of seq
        taskFiles.sort()
        taskFiles.append("Other ...")

        return taskFiles


    # OPEN: load parameter settings from a user-specified file
    def pfopen(self, event=None):
        """ Load the parameter settings from a user-specified file. """

        # Get the selected file name
        fname = self._openMenuChoice.get()

        # Also allow them to simply find any file - do not check _task_name_...
        # (could use tkinter's FileDialog, but this one is prettier)
        if fname[-3:] == '...':
            if capable.OF_TKFD_IN_EPAR:
                fname = askopenfilename(title="Load Config File",
                                        parent=self.top)
            else:
                from . import filedlg
                fd = filedlg.PersistLoadFileDialog(self.top,
                                                   "Load Config File",
                                                   self._getSaveAsFilter())
                if fd.Show() != 1:
                    fd.DialogCleanup()
                    return
                fname = fd.GetFileName()
                fd.DialogCleanup()

        if not fname: return # canceled
        self.debug('Loading from: '+fname)

        # load it into a tmp object (use associatedPkg if we have one)
        try:
            tmpObj = cfgpars.ConfigObjPars(fname, associatedPkg=\
                                           self._taskParsObj.getAssocPkg(),
                                           strict=self._strict)
        except Exception as ex:
            showerror(message=ex.message, title='Error in '+os.path.basename(fname))
            self.debug('Error in '+os.path.basename(fname))
            self.debug(traceback.format_exc())
            return

        # check it to make sure it is a match
        if not self._taskParsObj.isSameTaskAs(tmpObj):
            msg = 'The current task is "'+self._taskParsObj.getName()+ \
                  '", but the selected file is for task "'+ \
                  str(tmpObj.getName())+'".  This file was not loaded.'
            showerror(message=msg, title="Error in "+os.path.basename(fname))
            self.debug(msg)
            self.debug(traceback.format_exc())
            return

        # Set the GUI entries to these values (let the user Save after)
        newParList = tmpObj.getParList()
        try:
            self.setAllEntriesFromParList(newParList, updateModel=True)
                # go ahead and updateModel, even though it will take longer,
                # we need it updated for the copy of the dict we make below
        except editpar.UnfoundParamError as pe:
            showwarning(message=str(pe), title="Error in "+os.path.basename(fname))
        # trip any triggers
        self.checkAllTriggers('fopen')

        # This new fname is our current context
        self.updateTitle(fname)
        self._taskParsObj.filename = fname # !! maybe try setCurrentContext() ?
        self.freshenFocus()
        self.showStatus("Loaded values from: "+fname, keep=2)

        # Since we are in a new context (and have made no changes yet), make
        # a copy so we know what the last state was.
        # The dict() method returns a deep-copy dict of the keyvals.
        self._lastSavedState = self._taskParsObj.dict()


    def unlearn(self, event=None):
        """ Override this so that we can set to default values our way. """
        self.debug('Clicked defaults')
        self._setToDefaults()
        self.freshenFocus()


    def _handleParListMismatch(self, probStr, extra=False):
        """ Override to include ConfigObj filename and specific errors.
        Note that this only handles "missing" pars and "extra" pars, not
        wrong-type pars.  So it isn't that big of a deal. """

        # keep down the duplicate errors
        if extra:
            return True # the base class is already stating it will be ignored

        # find the actual errors, and then add that to the generic message
        errmsg = 'Warning: '
        if self._strict:
            errmsg = 'ERROR: '
        errmsg = errmsg+'mismatch between default and current par lists ' + \
                 'for task "'+self.taskName+'".'
        if probStr:
            errmsg += '\n\t'+probStr
        errmsg += '\nTry editing/deleting: "' + \
                  self._taskParsObj.filename+'").'
        print(errmsg)
        return True # as we said, not that big a deal


    def _setToDefaults(self):
        """ Load the default parameter settings into the GUI. """

        # Create an empty object, where every item is set to it's default value
        try:
            tmpObj = cfgpars.ConfigObjPars(self._taskParsObj.filename,
                                           associatedPkg=\
                                           self._taskParsObj.getAssocPkg(),
                                           setAllToDefaults=self.taskName,
                                           strict=False)
        except Exception as ex:
            msg = "Error Determining Defaults"
            showerror(message=msg+'\n\n'+ex.message, title="Error Determining Defaults")
            return

        # Set the GUI entries to these values (let the user Save after)
        tmpObj.filename = self._taskParsObj.filename = '' # name it later
        newParList = tmpObj.getParList()
        try:
            self.setAllEntriesFromParList(newParList) # needn't updateModel yet
            self.checkAllTriggers('defaults')
            self.updateTitle('')
            self.showStatus("Loaded default "+self.taskName+" values via: "+ \
                 os.path.basename(tmpObj._original_configspec), keep=1)
        except editpar.UnfoundParamError as pe:
            showerror(message=str(pe), title="Error Setting to Default Values")

    def getDict(self):
        """ Retrieve the current parameter settings from the GUI."""
        # We are going to have to return the dict so let's
        # first make sure all of our models are up to date with the values in
        # the GUI right now.
        badList = self.checkSetSaveEntries(doSave=False)
        if badList:
            self.processBadEntries(badList, self.taskName, canCancel=False)
        return self._taskParsObj.dict()

    def loadDict(self, theDict):
        """ Load the parameter settings from a given dict into the GUI. """
        # We are going to have to merge this info into ourselves so let's
        # first make sure all of our models are up to date with the values in
        # the GUI right now.
        badList = self.checkSetSaveEntries(doSave=False)
        if badList:
            if not self.processBadEntries(badList, self.taskName):
                return
        # now, self._taskParsObj is up-to-date
        # So now we update _taskParsObj with the input dict
        cfgpars.mergeConfigObj(self._taskParsObj, theDict)
        # now sync the _taskParsObj dict with its par list model
        #    '\n'.join([str(jj) for jj in self._taskParsObj.getParList()])
        self._taskParsObj.syncParamList(False)

        # Set the GUI entries to these values (let the user Save after)
        try:
            self.setAllEntriesFromParList(self._taskParsObj.getParList(),
                                          updateModel=True)
            self.checkAllTriggers('fopen')
            self.freshenFocus()
            self.showStatus('Loaded '+str(len(theDict))+ \
                ' user par values for: '+self.taskName, keep=1)
        except Exception as ex:
            showerror(message=ex.message, title="Error Setting to Loaded Values")


    def _getGuiSettings(self):
        """ Return a dict (ConfigObj) of all user settings found in rcFile. """
        # Put the settings into a ConfigObj dict (don't use a config-spec)
        rcFile = self._rcDir+os.sep+APP_NAME.lower()+'.cfg'
        if os.path.exists(rcFile):
            try:
                return configobj.ConfigObj(rcFile)
            except:
                raise RuntimeError('Error parsing: '+os.path.realpath(rcFile))

            # tho, for simple types, unrepr=True eliminates need for .cfgspc
            # also, if we turn unrepr on, we don't need cfgGetBool
        else:
            return {}


    def _saveGuiSettings(self):
        """ The base class doesn't implement this, so we will - save settings
        (only GUI stuff, not task related) to a file. """
        # Put the settings into a ConfigObj dict (don't use a config-spec)
        rcFile = self._rcDir+os.sep+APP_NAME.lower()+'.cfg'
        #
        if os.path.exists(rcFile): os.remove(rcFile)
        co = configobj.ConfigObj(rcFile) # can skip try-block, won't read file

        co['showHelpInBrowser']       = self._showHelpInBrowser
        co['saveAndCloseOnExec']      = self._saveAndCloseOnExec
        co['writeProtectOnSaveAsOpt'] = self._writeProtectOnSaveAs
        co['flagNonDefaultVals']      = self._flagNonDefaultVals
        co['frameColor']              = self._frmeColor
        co['taskBoxColor']            = self._taskColor
        co['buttonBoxColor']          = self._bboxColor
        co['entriesColor']            = self._entsColor
        co['flaggedColor']            = self._flagColor

        co.initial_comment = ['Automatically generated by '+\
            APP_NAME+'.  All edits will eventually be overwritten.']
        co.initial_comment.append('To use platform default colors, delete each color line below.')
        co.final_comment = [''] # ensure \n at EOF
        co.write()


    def _applyTriggerValue(self, triggerName, outval):
        """ Here we look through the entire .cfgspc to see if any parameters
        are affected by this trigger. For those that are, we apply the action
        to the GUI widget.  The action is specified by depType. """

        # First find which items are dependent upon this trigger (cached)
        # e.g. { scope1.name1 : dep'cy-type, scope2.name2 : dep'cy-type, ... }
        depParsDict = self._taskParsObj.getParsWhoDependOn(triggerName)
        if not depParsDict: return
        if 0: print("Dependent parameters:\n"+str(depParsDict)+"\n")

        # Get model data, the list of pars
        theParamList = self._taskParsObj.getParList()

        # Then go through the dependent pars and apply the trigger to them
        settingMsg = ''
        for absName in depParsDict:
            used = False
            # For each dep par, loop to find the widget for that scope.name
            for i in range(self.numParams):
                scopedName = theParamList[i].scope+'.'+theParamList[i].name # diff from makeFullName!!
                if absName == scopedName: # a match was found
                    depType = depParsDict[absName]
                    if depType == 'active_if':
                        self.entryNo[i].setActiveState(outval)
                    elif depType == 'inactive_if':
                        self.entryNo[i].setActiveState(not outval)
                    elif depType == 'is_set_by':
                        self.entryNo[i].forceValue(outval, noteEdited=True)
                        # WARNING! noteEdited=True may start recursion!
                        if len(settingMsg) > 0: settingMsg += ", "
                        settingMsg += '"'+theParamList[i].name+'" to "'+\
                                      outval+'"'
                    elif depType in ('set_yes_if', 'set_no_if'):
                        if bool(outval):
                            newval = 'yes'
                            if depType == 'set_no_if': newval = 'no'
                            self.entryNo[i].forceValue(newval, noteEdited=True)
                            # WARNING! noteEdited=True may start recursion!
                            if len(settingMsg) > 0: settingMsg += ", "
                            settingMsg += '"'+theParamList[i].name+'" to "'+\
                                          newval+'"'
                        else:
                            if len(settingMsg) > 0: settingMsg += ", "
                            settingMsg += '"'+theParamList[i].name+\
                                          '" (no change)'
                    elif depType == 'is_disabled_by':
                        # this one is only used with boolean types
                        on = self.entryNo[i].convertToNative(outval)
                        if on:
                            # do not activate whole section or change
                            # any values, only activate this one
                            self.entryNo[i].setActiveState(True)
                        else:
                            # for off, set the bool par AND grey WHOLE section
                            self.entryNo[i].forceValue(outval, noteEdited=True)
                            self.entryNo[i].setActiveState(False)
                            # we'd need this if the par had no _section_switch_
#                           self._toggleSectionActiveState(
#                                theParamList[i].scope, False, None)
                            if len(settingMsg) > 0: settingMsg += ", "
                            settingMsg += '"'+theParamList[i].name+'" to "'+\
                                          outval+'"'
                    else:
                        raise RuntimeError('Unknown dependency: "'+depType+ \
                                           '" for par: "'+scopedName+'"')
                    used = True
                    break

            # Or maybe it is a whole section
            if absName.endswith('._section_'):
                scope = absName[:-10]
                depType = depParsDict[absName]
                if depType == 'active_if':
                    self._toggleSectionActiveState(scope, outval, None)
                elif depType == 'inactive_if':
                    self._toggleSectionActiveState(scope, not outval, None)
                used = True

            # Help to debug the .cfgspc rules
            if not used:
                raise RuntimeError('UNUSED "'+triggerName+'" dependency: '+ \
                      str({absName:depParsDict[absName]}))

        if len(settingMsg) > 0:
# why ?!    self.freshenFocus()
            self.showStatus('Automatically set '+settingMsg, keep=1)
