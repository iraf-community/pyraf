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

    def _skipParSave_Hook(self):
        """ Overridden version, so as to check for a special case. """
        # Skip the save if the thing being edited is an IrafParList without
        # an associated file (in which case the changes are just being
        # made in memory.)
        if isinstance(self._taskParsObj,irafpar.IrafParList) and \
           not self._taskParsObj.getFilename():
            return True
        else:
            return False

    def _showOpenButton(self):
        """ Override this so that we can use rules in irafpar. """
        # See if there exist any special versions on disk to load
        # Note that irafpar caches the list of these versions
        return irafpar.haveSpecialVersions(self.taskName, self.pkgName)


    def _nonStandardEparOptionFor(self, paramTypeStr):
        """ Override to allow use of PsetEparOption.
            Return None or a class which derives from EparOption. """
        if paramTypeStr == "pset":
            return pseteparoption.PsetEparOption
        else:
            return None


    # Two overrides of deafult behavior, related to unpackaged "tasks"
    def _getUnpackagedTaskTitle(self): return "Filename"
    def _isUnpackagedTask(self):
        return isinstance(self._taskParsObj, irafpar.IrafParList)


    # OPEN: load parameter settings from a user-specified file
    def pfopen(self, event=None):
        """ Load the parameter settings from a user-specified file.  Any
        changes here must be coordinated with the corresponding tpar pfopen
        function. """

        flist = irafpar.getSpecialVersionFiles(self.taskName, self.pkgName)
        if len(flist) <= 0:
            msg = "No special-purpose parameter files found for "+self.taskName
            showwarning(message=msg, title='File not found')
            return

        fname = None
        if len(flist) == 1:
            if askokcancel("Confirm",
                           "One special-purpose parameter file found.\n"+ \
                           "Load file?\n\n"+flist[0]):
                fname = flist[0]
        else: # >1 file, need a select dialog
            flist.sort()
            ld = listdlg.ListSingleSelectDialog("Select Parameter File",
                         "Select which parameter file to load for "+ \
                         self.pkgName+"."+self.taskName, flist, self.top)
            fname = ld.getresult() # will be None or a string fname

        # check-point
        if fname == None: return

        # Now load it: "Loading "+self.taskName+" param values from: "+fname
        newParList = irafpar.IrafParList(self.taskName, fname)

        # Set the GUI entries to these values (let the user Save after)
        self.setAllEntriesFromParList(newParList)


    # SAVE AS: save the parameter settings to a user-specified file
    def saveAs(self, event=None):
        """ Save the parameter settings to a user-specified file.  Any
        changes here must be coordinated with the corresponding tpar save_as
        function. """

        # The user wishes to save to a different name
        # (could use Tkinter's FileDialog, but this one is prettier)
        filt = '*.par'
        upx = iraf.envget("uparm_aux","")
        if 'UPARM_AUX' in os.environ: upx = os.environ['UPARM_AUX']
        if len(upx) > 0:  filt = upx+"/*.par"
        fd = filedlg.SaveFileDialog(self.top, "Save Parameter File As", filt)
        if fd.Show() != 1:
            fd.DialogCleanup()
            return
        fname = fd.GetFileName()
        fd.DialogCleanup()

        # First check the child parameters, aborting save if
        # invalid entries were encountered
        if self.checkSetSaveChildren():
            return

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
                  '\n\n"'+fname+'"'
            showwarning(message=msg, title='PSET Save-As Not Yet Supported')

        # Verify all the entries (without save), keeping track of the invalid
        # entries which have been reset to their original input values
        self.badEntriesList = self.checkSetSaveEntries(doSave=False)

        # If there were invalid entries, prepare the message dialog
        if (self.badEntriesList):
            ansOKCANCEL = self.processBadEntries(self.badEntriesList,
                          self.taskName)
            if not ansOKCANCEL:
                return

        # If there were no invalid entries or the user says OK, finally
        # save to their stated file.  Since we have already processed the
        # bad entries, there should be none returned.
        mstr = "TASKMETA: task="+self.taskName+" package="+self.pkgName
        if self.checkSetSaveEntries(doSave=True, filename=fname, comment=mstr):
            raise Exception("Unexpected bad entries for: "+self.taskName)

        # Notify irafpar that there is a new special-purpose file on the scene
        irafpar.newSpecialParFile(self.taskName, self.pkgName, fname)


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

