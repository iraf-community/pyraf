####
#       Class FileDialog
#
#       Purpose
#       -------
#
#       FileDialog's are widgets that allow one to select file names by
#       clicking on file names, directory names, filters, etc.
#
#       Standard Usage
#       --------------
#
#       F = FileDialog(widget, some_title, some_filter)
#       if F.Show() != 1:
#               F.DialogCleanup()
#       return
#               file_name = F.GetFileName()
#               F.DialogCleanup()
####
"""
$Id$
"""
import os
from . import capable

from subprocess import getoutput  # nosec

if capable.OF_GRAPHICS:
    import tkinter as TKNTR
    from . import alert
    from .dialog import *  # noqa
else:
    ModalDialog = object


class FileDialog(ModalDialog):

    # constructor

    lastWrtPrtChoice = None

    def __init__(self, widget, title, filter="*", initWProtState=None):
        """ Supply parent widget, title, filter, and initWProtState (True or
        False).  Set initWProtState to None to hide the write-protect
        check-box. """
        self.widget = widget
        self.filter = filter.strip()
        self.orig_dir = os.getcwd()
        self.cwd = os.getcwd()       # the logical current working directory
        self.showChmod = initWProtState is not None
        # normally we use persistence for lastWrtPrtChoice; use this 1st time
        if FileDialog.lastWrtPrtChoice is None:
            FileDialog.lastWrtPrtChoice = initWProtState
        # Allow a start-directory as part of the given filter
        if self.filter.find(os.sep) >= 0:
            self.cwd = os.path.dirname(self.filter)
            self.filter = os.path.basename(self.filter) # do this second!
        # main Dialog code
        Dialog.__init__(self, widget)

    # setup routine called back from Dialog

    def SetupDialog(self):

        # directory label

        self.dirFrame = Frame(self.top)
        self.dirFrame['relief'] = 'raised'
        self.dirFrame['bd']      = '2'
        self.dirFrame.pack({'expand':'no', 'side':'top', 'fill':'both'})
        self.dirLabel = Label(self.dirFrame)
        self.dirLabel["text"] = "Directory:"
        self.dirLabel.pack({'expand':'no', 'side':'left', 'fill':'none'})

        # editable filter

        self.filterFrame = Frame(self.top)
        self.filterFrame['relief'] = 'raised'
        self.filterFrame['bd']   = '2'
        self.filterFrame.pack({'expand':'no', 'side':'top', 'fill':'both'})
        self.filterLabel = Label(self.filterFrame)
        self.filterLabel["text"] = "Filter:"
        self.filterLabel.pack({'expand':'no', 'side':'left', 'fill':'none'})
        self.filterEntry = Entry(self.filterFrame)
        self.filterEntry.bind('<Return>', self.FilterReturnKey)
        self.filterEntry["width"]  = "40"
        self.filterEntry["relief"] = "ridge"
        self.filterEntry.pack({'expand':'yes', 'side':'right', 'fill':'x'})
        self.filterEntry.insert(0, self.filter)

        # the directory and file listboxes

        self.listBoxFrame = Frame(self.top)
        self.listBoxFrame['relief'] = 'raised'
        self.listBoxFrame['bd']  = '2'
        self.listBoxFrame.pack({'expand':'yes', 'side' :'top',
                'pady' :'2', 'padx': '0', 'fill' :'both'})
        self.CreateDirListBox()
        self.CreateFileListBox()
        self.UpdateListBoxes()

        # write-protect option

        junk = FileDialog.lastWrtPrtChoice
        if junk is None:
            junk = 0
        self.wpVar = IntVar(value=junk) # use class attr
        if self.showChmod:
            self.writeProtFrame = Frame(self.top)
            self.writeProtFrame['relief'] = 'raised'
            self.writeProtFrame['bd'] = '2'
            self.writeProtFrame.pack({'expand':'no','side':'top','fill':'both'})
            self.wpButton = Checkbutton(self.writeProtFrame,
                                        text="Write-protect after save",
                                        command=self.wrtPrtClick,
                                        var=self.wpVar)
            self.wpButton.pack({'expand':'no', 'side':'left'})

        # editable filename

        self.fileNameFrame = Frame(self.top)
        self.fileNameFrame.pack({'expand':'no', 'side':'top', 'fill':'both'})
        self.fileNameFrame['relief'] = 'raised'
        self.fileNameFrame['bd']         = '2'
        self.fileNameLabel = Label(self.fileNameFrame)
        self.fileNameLabel["text"] = "File:"
        self.fileNameLabel.pack({'expand':'no', 'side':'left', 'fill':'none'})
        self.fileNameEntry = Entry(self.fileNameFrame)
        self.fileNameEntry["width"]  = "40"
        self.fileNameEntry["relief"] = "ridge"
        self.fileNameEntry.pack({'expand':'yes', 'side':'right', 'fill':'x',
                                 'pady': '2'})
        self.fileNameEntry.bind('<Return>', self.FileNameReturnKey)

        # buttons - ok, filter, cancel

        self.buttonFrame = Frame(self.top)
        self.buttonFrame['relief'] = 'raised'
        self.buttonFrame['bd']   = '2'
        self.buttonFrame.pack({'expand':'no', 'side':'top', 'fill':'x'})
        self.okButton = Button(self.buttonFrame)
        self.okButton["text"]     = "OK"
        self.okButton["command"]   = self.OkPressed
        self.okButton["width"] = 8
        self.okButton.pack({'expand':'yes', 'pady':'2', 'side':'left'})
        self.filterButton = Button(self.buttonFrame)
        self.filterButton["text"]         = "Filter"
        self.filterButton["command"]   = self.FilterPressed
        self.filterButton["width"] = 8
        self.filterButton.pack({'expand':'yes', 'pady':'2', 'side':'left'})
        button = Button(self.buttonFrame)
        button["text"] = "Cancel"
        button["command"] = self.CancelPressed
        button["width"] = 8
        button.pack({'expand':'yes', 'pady':'2', 'side':'left'})

    # create the directory list box

    def CreateDirListBox(self):
        frame = Frame(self.listBoxFrame)
        frame.pack({'expand':'yes', 'side' :'left', 'pady' :'1',
                'fill' :'both'})
        frame['relief'] = 'raised'
        frame['bd']      = '2'
        filesFrame = Frame(frame)
        filesFrame['relief'] = 'flat'
        filesFrame['bd']         = '2'
        filesFrame.pack({'side':'top', 'expand':'no', 'fill':'x'})
        label = Label(filesFrame)
        label['text'] = 'Directories:'
        label.pack({'side':'left', 'expand':'yes', 'anchor':'w',
                'fill':'none'})
        scrollBar = Scrollbar(frame, {'orient':'vertical'})
        scrollBar.pack({'expand':'no', 'side':'right', 'fill':'y'})
        self.dirLb = Listbox(frame, {'yscroll':scrollBar.set})
        self.dirLb.pack({'expand':'yes', 'side' :'top', 'pady' :'1',
                'fill' :'both'})
        self.dirLb.bind('<1>', self.DoSelection)
        self.dirLb.bind('<Double-Button-1>', self.DoDoubleClickDir)
        scrollBar['command'] = self.dirLb.yview

    # create the files list box

    def CreateFileListBox(self):
        frame = Frame(self.listBoxFrame)
        frame['relief'] = 'raised'
        frame['bd']      = '2'
        frame.pack({'expand':'yes', 'side' :'left', 'pady' :'1', 'padx' :'1',
                'fill' :'both'})
        filesFrame = Frame(frame)
        filesFrame['relief'] = 'flat'
        filesFrame['bd']         = '2'
        filesFrame.pack({'side':'top', 'expand':'no', 'fill':'x'})
        label = Label(filesFrame)
        label['text'] = 'Files:'
        label.pack({'side':'left', 'expand':'yes', 'anchor':'w',
                'fill':'none'})
        scrollBar = Scrollbar(frame, {'orient':'vertical'})
        scrollBar.pack({'side':'right', 'fill':'y'})
        self.fileLb = Listbox(frame, {'yscroll':scrollBar.set})
        self.fileLb.pack({'expand':'yes', 'side' :'top', 'pady' :'0',
                'fill' :'both'})
        self.fileLb.bind('<1>', self.DoSelection)
        self.fileLb.bind('<Double-Button-1>', self.DoDoubleClickFile)
        scrollBar['command'] = self.fileLb.yview

    # update the listboxes and directory label after a change of directory

    def UpdateListBoxes(self):
        cwd = self.cwd
        self.fileLb.delete(0, self.fileLb.size())
        filter = self.filterEntry.get()
        # '*' will list recursively, we don't want that.
        if filter == '*':
            filter = ''
        cmd = "/bin/ls " + os.path.join(cwd, filter)
        cmdOutput = getoutput(cmd)  # nosec
        files = cmdOutput.split("\n")
        files.sort()
        for i in range(len(files)):
            if os.path.isfile(os.path.join(cwd, files[i])):
                self.fileLb.insert('end', os.path.basename(files[i]))
        self.dirLb.delete(0, self.dirLb.size())
        files = os.listdir(cwd)
        if cwd != '/':
            files.append('..')
        files.sort()
        for i in range(len(files)):
            if os.path.isdir(os.path.join(cwd, files[i])):
                self.dirLb.insert('end', files[i])
        self.dirLabel['text'] = "Directory:" + self.cwd_print()

    # selection handlers

    def DoSelection(self, event):
        lb = event.widget
        field = self.fileNameEntry
        field.delete(0, AtEnd())
        field.insert(0, os.path.join(self.cwd_print(), lb.get(lb.nearest(event.y))))
        if TKNTR.TkVersion >= 4.0:
            lb.select_clear(0, "end")
            lb.select_anchor(lb.nearest(event.y))
        else:
            lb.select_clear()
            lb.select_from(lb.nearest(event.y))

    def DoDoubleClickDir(self, event):
        lb = event.widget
        self.cwd = os.path.join(self.cwd, lb.get(lb.nearest(event.y)))
        self.UpdateListBoxes()

    def DoDoubleClickFile(self, event):
        self.OkPressed()

    def OkPressed(self):
        self.TerminateDialog(1)

    def wrtPrtClick(self):
        FileDialog.lastWrtPrtChoice = self.wpVar.get() # update class attr

    def FileNameReturnKey(self, event):
        # if its a relative path then include the cwd in the name
        name = self.fileNameEntry.get().strip()
        if not os.path.isabs(os.path.expanduser(name)):
            self.fileNameEntry.delete(0, 'end')
            self.fileNameEntry.insert(0, os.path.join(self.cwd_print(), name))
        self.okButton.flash()
        self.OkPressed()

    def FilterReturnKey(self, event):
        filter = self.filterEntry.get().strip()
        self.filterEntry.delete(0, 'end')
        self.filterEntry.insert(0, filter)
        self.filterButton.flash()
        self.UpdateListBoxes()

    def FilterPressed(self):
        self.UpdateListBoxes()

    def CancelPressed(self):
        self.TerminateDialog(0)

    def GetFileName(self):
        return self.fileNameEntry.get()

    def GetWriteProtectChoice(self):
        return bool(self.wpVar.get())

    # return the logical current working directory in a printable form
    # ie. without all the X/.. pairs. The easiest way to do this is to
    # chdir to cwd and get the path there.

    def cwd_print(self):
        os.chdir(self.cwd)
        p = os.getcwd()
        os.chdir(self.orig_dir)
        return p
####
#       Class LoadFileDialog
#
#       Purpose
#       -------
#
#       Specialisation of FileDialog for loading files.
####

class LoadFileDialog(FileDialog):

    def __init__(self, master, title, filter):
        FileDialog.__init__(self, master, title, filter)
        self.top.title(title)

    def OkPressed(self):
        fileName = self.GetFileName()
        if os.path.exists(fileName) == 0:
            msg = 'File ' + fileName + ' not found.'
            errorDlg = alert.ErrorDialog(self.top, msg)
            errorDlg.Show()
            errorDlg.DialogCleanup()
            return
        FileDialog.OkPressed(self)

####
#       Class SaveFileDialog
#
#       Purpose
#       -------
#
#       Specialisation of FileDialog for saving files.
####

class SaveFileDialog(FileDialog):

    def __init__(self, master, title, filter):
        FileDialog.__init__(self, master, title, filter)
        self.top.title(title)

    def OkPressed(self):
        fileName = self.GetFileName()
        if os.path.exists(fileName) == 1:
            msg = 'File ' + fileName + ' exists.\nDo you wish to overwrite it?'
            warningDlg = alert.WarningDialog(self.top, msg)
            if warningDlg.Show() == 0:
                warningDlg.DialogCleanup()
                return
            warningDlg.DialogCleanup()
        FileDialog.OkPressed(self)

#----------------------------------------------------------------------------

#############################################################################
#
# Class:   PersistFileDialog
# Purpose: Essentially the same as FileDialog, except this class contains
#          a class variable (lastAccessedDir) which keeps track of the last
#          directory from which a file was chosen.  Subsequent invocations of
#          this dialog in the same Python session will start up in the last
#          directory where a file was successfully chosen, rather than in the
#          current working directory.
#
# History: M.D. De La Pena, 08 June 2000
#
#############################################################################

class PersistFileDialog(FileDialog):

    # Define a class variable to track the last accessed directory
    lastAccessedDir = None

    def __init__(self, widget, title, filter="*", initWProtState=None):

        FileDialog.__init__(self, widget, title, filter, initWProtState)

        # If the last accessed directory were not None, start up
        # the file browser in the last accessed directory.
        if self.__class__.lastAccessedDir:
            self.cwd      = self.__class__.lastAccessedDir

    # Override the OkPressed method from the parent in order to
    # update the class variable.
    def OkPressed(self):
        self.__class__.lastAccessedDir = self.cwd_print()
        self.TerminateDialog(1)


#############################################################################
#
# Class:   PersistLoadFileDialog
# Purpose: Essentially the same as LoadFileDialog, except this class invokes
#          PersistFileDialog instead of FileDialog.
#
# History: M.D. De La Pena, 08 June 2000
#
#############################################################################

class PersistLoadFileDialog(PersistFileDialog):

    def __init__(self, master, title, filter):
        PersistFileDialog.__init__(self, master, title, filter)
        self.top.title(title)

    def OkPressed(self):
        fileName = self.GetFileName()
        if os.path.exists(fileName) == 0:
            msg = 'File ' + fileName + ' not found.'
            errorDlg = alert.ErrorDialog(self.top, msg)
            errorDlg.Show()
            errorDlg.DialogCleanup()
            return
        PersistFileDialog.OkPressed(self)


#############################################################################
#
# Class:   PersistSaveFileDialog
# Purpose: Essentially the same as SaveFileDialog, except this class invokes
#          PersistFileDialog instead of FileDialog.
#
#############################################################################

class PersistSaveFileDialog(PersistFileDialog):

    def __init__(self, master, title, filter, initWProtState=None):
        PersistFileDialog.__init__(self, master, title, filter, initWProtState)
        self.top.title(title)

    def OkPressed(self):
        fileName = self.GetFileName()
        if os.path.exists(fileName) == 1:
            msg = 'File ' + fileName + ' exists.\nDo you wish to overwrite it?'
            warningDlg = alert.WarningDialog(self.top, msg)
            if warningDlg.Show() == 0:
                warningDlg.DialogCleanup()
                return
            warningDlg.DialogCleanup()
        PersistFileDialog.OkPressed(self)
