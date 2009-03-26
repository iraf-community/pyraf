""" Main module for the PyRAF-version of the Epar parameter editor

$Id$

M.D. De La Pena, 2000 February 04
"""

# system level modules
from Tkinter import *
from tkMessageBox import askokcancel, showwarning
import os, sys, cStringIO

# local modules
from pytools import filedlg, listdlg, eparoption, editpar
from pytools.irafglobals import IrafError
import iraf, irafpar, irafhelp, wutil, pseteparoption
from pyrafglobals import pyrafDir


def epar(theTask, parent=None, isChild=0):

    if not wutil.hasGraphics:
        raise IrafError("Cannot run epar without graphics windows")

    if not isChild:
        oldFoc = wutil.getFocalWindowID()
        wutil.forceFocusToNewWindow()

    PyrafEparDialog(theTask, parent, isChild)

    if not isChild:
        wutil.setFocusTo(oldFoc)


class PyrafEparDialog(editpar.EditParDialog):

    def __init__(self, theTask, parent=None, isChild=0,
                 title="PyRAF Parameter Editor", childList=None):

        # Init base - calls _setTaskParsObj(), sets self.taskName, etc
        editpar.EditParDialog.__init__(self, theTask, parent, isChild,
                                       title, childList, resourceDir=pyrafDir)

    def _setTaskParsObj(self, theTask):
        """ Overridden version, so as to use Iraf tasks and IrafParList """

        if isinstance(theTask, irafpar.IrafParList):
            # IrafParList acts as an IrafTask for our purposes
            self._taskParsObj = theTask
        else:
            # theTask must be a string name of, or an IrafTask object
            self._taskParsObj = iraf.getTask(theTask)

    def _doActualSave(self, filename, comment):
        """ Overridden version, so as to check for a special case. """
        # Skip the save if the thing being edited is an IrafParList without
        # an associated file (in which case the changes are just being
        # made in memory.)
        if isinstance(self._taskParsObj,irafpar.IrafParList) and \
           not self._taskParsObj.getFilename():
            return '' # skip it
        else:
            return self._taskParsObj.saveParList(filename=filename,
                                                 comment=comment)

    def _showOpenButton(self):
        """ Override this so that we can use rules in irafpar. """
        # See if there exist any special versions on disk to load
        # Note that irafpar caches the list of these versions
        return irafpar.haveSpecialVersions(self.taskName, self.pkgName)

    def _overrideMasterSettings(self):
        """ Override this to tailor the GUI specifically for epar. """
        self._useSimpleAutoClose  = True

        self._saveAndCloseOnExec  = True
        self._showSaveCloseOnExec = False

        self._showExtraHelpButton = True

        self._appName             = "Epar"
        self._unpackagedTaskTitle = "Filename"
        self._defaultsButtonTitle = "Unlearn"

    def _nonStandardEparOptionFor(self, paramTypeStr):
        """ Override to allow use of PsetEparOption.
            Return None or a class which derives from EparOption. """
        if paramTypeStr == "pset":
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
        if fname == None: return

        # Now load it: "Loading "+self.taskName+" param values from: "+fname
        newParList = irafpar.IrafParList(self.taskName, fname)

        # Set the GUI entries to these values (let the user Save after)
        self.setAllEntriesFromParList(newParList)


    def _getSaveAsFilter(self):
        """ Return a string to be used as the filter arg to the save file
            dialog during Save-As. """
        filt = '*.par'
        upx = iraf.envget("uparm_aux","")
        if 'UPARM_AUX' in os.environ: upx = os.environ['UPARM_AUX']
        if len(upx) > 0:  filt = iraf.Expand(upx)+"/*.par"
        return filt


    def _saveAsPreSave_Hook(self, fnameToBeUsed):
        """ Override to check for (and warn about) PSETs. """
        # Notify them that pset children will not be saved as part of 
        # their special version
        pars = []
        for par in self.paramList:
            if par.type == "pset": pars.append(par.name)
        if len(pars):
            msg = "If you have made any changes to the PSET "+ \
                  "values for:\n\n"
            for p in pars: msg += "\t\t"+p+"\n"
            msg = msg+"\nthose changes will NOT be explicitly saved to:"+ \
                  '\n\n"'+fnameToBeUsed+'"'
            showwarning(message=msg, title='PSET Save-As Not Yet Supported')


    def _saveAsPostSave_Hook(self, fnameToBeUsed):
        """ Override this to notify irafpar. """
        # Notify irafpar that there is a new special-purpose file on the scene
        irafpar.newSpecialParFile(self.taskName, self.pkgName, fnameToBeUsed)


    def htmlHelp(self, event=None):
        """ Overridden version, use irafhelp to invoke the HTML help """
        # Invoke the STSDAS HTML help
        irafhelp.help(self.taskName, html=1)


    # Get the task help in a string (RLW)
    def getHelpString(self, taskname):
        """ Override this - in PyRAF we'll always use use iraf system help.
            Do not query the task object. """
        fh = cStringIO.StringIO()
        iraf.system.help(taskname, page=0, Stdout=fh, Stderr=fh)
        result = fh.getvalue()
        fh.close()
        return result
