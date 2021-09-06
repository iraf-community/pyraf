"""module iraftask.py -- defines IrafTask and IrafPkg classes

R. White, 2000 June 26

iraftask defines the original PyRAF task functionality which pre-dates
the creation of IRAF ECL.  irafecl is closely related and derived from
iraftask,  providing drop-in replacements for the Task classes defined
here which also support ECL syntax like "iferr" and $errno.
"""


import fnmatch
import os
import sys
import copy
import re
from stsci.tools import basicpar, minmatch, irafutils, irafglobals, taskpars
from stsci.tools.irafglobals import IrafError, Verbose
from . import subproc
from . import irafinst
from . import irafpar
from . import irafexecute
from . import cl2py
from . import iraf

# may be set to function to monitor task execution
# function gets called for every task execution
executionMonitor = None

# -----------------------------------------------------
# IRAF task class
# -----------------------------------------------------

# basic IrafTask attributes
_IrafTask_attr_dict = {
    '_name': None,
    '_pkgname': None,
    '_pkgbinary': None,
    '_hidden': 0,
    '_hasparfile': 1,
    '_tbflag': 0,
    # full path names and parameter list get filled in on demand
    '_fullpath': None,
    # parameters have a current set of values and a default set
    '_currentParList': None,
    '_defaultParList': None,
    '_runningParList': None,
    '_currentParpath': None,
    '_defaultParpath': None,
    '_scrunchParpath': None,
    '_parDictList': None,
    '_foreign': 0,
}

# This is a list of all the IrafTask objects that have been created.
# There are variables in iraffunctions that superficially
# resemble this, but none of them contain the complete list, so I
# keep it here.  This is currently used only for the "taskinfo"
# operation.
#
# We generally approach this list interactively and with a wildcards.
# I don't see any particularly useful indexing, so it is just a plain
# linear search.
#
all_task_definitions = []

# use empty "tag" class from irafglobals as base class


class IrafTask(irafglobals.IrafTask, taskpars.TaskPars):
    """IRAF task class"""

    # We remember parameters to the __init__ function
    #
    # prefix
    #       ? - see obj._saved_prefix
    #
    # name
    #       the name of the task.  We don't actually save this, but
    #       obj._name contains the name as we may have modified it.
    #
    # suffix
    #       ? - see obj._saved_suffix
    #
    # filename
    #       ? - obviously more than just a file name.  obj._filename
    #       is the modified value
    #
    # pkgname
    #       the name of the package that this task is in.  see obj._pkgname
    #
    # pkgbinary
    #       places that the binary may be.  see obj._pkgbinary
    #

    def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):

        # for this heavily used code, pull out the dictionary and
        # initialize it directly to avoid calls to __setattr__
        #
        # b.t.w. do not try to set the attributes directly - it doesn't
        # work. (not sure if that is a bug or a "feature")
        objdict = self.__dict__

        # remember the task definition in case we want to see it later
        all_task_definitions.append(self)

        objdict['_saved_suffix'] = suffix
        objdict['_saved_prefix'] = prefix

        # stuff all the parameters into the object
        objdict.update(_IrafTask_attr_dict)
        sname = name.replace('.', '_')
        if sname != name:
            print("Warning: '.' illegal in task name, changing", name, "to",
                  sname)
        spkgname = pkgname.replace('.', '_')
        if spkgname != pkgname:
            print("Warning: '.' illegal in pkgname, changing", pkgname, "to",
                  spkgname)
        objdict['_name'] = sname
        objdict['_pkgname'] = spkgname
        objdict['_pkgbinary'] = []
        self.addPkgbinary(pkgbinary)
        # tasks with names starting with '_' are implicitly hidden
        if name[0:1] == '_':
            objdict['_hidden'] = 1
        if prefix == '$':
            objdict['_hasparfile'] = 0
        if suffix == '.tb':
            objdict['_tbflag'] = 1
        if filename and filename[0] == '$':
            # this is a foreign task
            objdict['_foreign'] = 1
            objdict['_filename'] = filename[1:]
            # handle weird syntax for names
            if self._filename == 'foreign':
                objdict['_filename'] = name
            elif self._filename[:8] == 'foreign ':
                objdict['_filename'] = name + self._filename[7:]
            elif filename[:2] == '$0':
                objdict['_filename'] = name + filename[2:]
        else:
            objdict['_filename'] = filename

    def initTask(self, force=0):
        """Fill in full pathnames of files and read parameter file(s)

        Force indicates whether shortcut initialization can be used
        or not.  (No difference for base IrafTask.)
        """
        if self._filename and not self._fullpath:
            if irafinst.EXISTS:
                self._initFullpath()  # allow to throw on error
            else:  # be more accommodating
                try:
                    self._initFullpath()
                except IrafError:
                    self._initNoIrafTask()
        if self._currentParList is None:
            self._initParpath()
            self._initParList()

    def _initNoIrafTask(self):
        """ Special-case handle the initialization that is going awry due
        to a missing IRAF installation. """
        # Handle non-IRAF installs - could not find the file anywhere
        # Handle .par files differently from other types
        orig = self._filename
        base = os.path.basename(self._filename)
        base = base[1 + base.rfind('$'):]
        if base and base.endswith('.par'):
            self._filename = irafinst.tmpParFile(base)
        else:
            self._filename = irafinst.NO_IRAF_PFX + base  # to be built on the fly
        if Verbose > 1:
            print('Task "' + self._name + '" needed "' + orig + '" got: ' +
                  self._filename)

    # =========================================================
    # public accessor methods for attributes
    # =========================================================

    # ---------------------------------------------------------
    # first set returns current values (which may be None if
    # initTask has not been executed yet)
    # ---------------------------------------------------------

    def getName(self):
        return self._name

    def getPkgname(self):
        return self._pkgname

    def getPkgbinary(self):
        return self._pkgbinary

    def isHidden(self):
        return self._hidden

    def hasParfile(self):
        return self._hasparfile

    def getTbflag(self):
        return self._tbflag

    def getForeign(self):
        return self._foreign

    def getFilename(self):
        return self._filename

    # ---------------------------------------------------------
    # second set initializes task variables (which were deferred to
    # speed up initial instance creation)
    # ---------------------------------------------------------

    def getFullpath(self):
        """Return full path name of executable"""
        self.initTask()
        return self._fullpath

    def getParpath(self):
        """Return full path name of parameter file"""
        self.initTask()
        return self._currentParpath

    def getParList(self, docopy=0):
        """Return list of all parameter objects"""
        self.initTask(force=1)
        plist = self._runningParList or self._currentParList
        if plist:
            return plist.getParList(docopy=docopy)
        else:
            return []

    def getDefaultParList(self):
        """Return default list of all parameter objects"""
        self.initTask(force=1)
        plist = self._defaultParList
        if plist:
            return plist.getParList()
        else:
            return []

    def getParDict(self):
        """Return (min-match) dictionary of all parameter objects"""
        self.initTask(force=1)
        plist = self._runningParList or self._currentParList
        if plist:
            return plist.getParDict()
        else:
            return minmatch.MinMatchDict()

    def getParObject(self, paramname, exact=0, alldict=0):
        """Get the IrafPar object for a parameter

        If exact is set, param name must match exactly.
        If alldict is set, look in all dictionaries (default is
        just this task's dictionaries.)
        """
        self.initTask()

        # search the standard dictionaries for the parameter
        # most of the time it will be in the active task dictionary
        try:
            paramdict = self.getParDict()
            if paramdict._has(paramname, exact=exact):
                return paramdict[paramname]
        except minmatch.AmbiguousKeyError as e:
            # re-raise the error with a bit more info
            raise IrafError(f"Cannot get parameter `{paramname}'\n{str(e)}")

        if alldict:
            # OK, the easy case didn't work -- now initialize the
            # complete parDictList (if necessary) and search them all

            if self._parDictList is None:
                self._setParDictList()
            for dictname, paramdict in self._parDictList:
                if paramdict._has(paramname, exact=exact):
                    return paramdict[paramname]

        raise IrafError("Unknown parameter requested: " + paramname)

    def getAllMatches(self, param):
        """Return list of names of all parameters that may match param"""
        self.initTask(force=1)
        plist = self._runningParList or self._currentParList
        if plist:
            return plist.getAllMatches(param)
        else:
            return []

    # ---------------------------------------------------------
    # modify and test attributes
    # ---------------------------------------------------------

    def addPkgbinary(self, pkgbinary):
        """Add another entry in list of possible package binary locations

        Parameter can be a string or a list of strings"""

        if not pkgbinary:
            return
        elif isinstance(pkgbinary, str):
            if pkgbinary and (pkgbinary not in self._pkgbinary):
                self._pkgbinary.append(pkgbinary)
        else:
            for pbin in pkgbinary:
                if pbin and (pbin not in self._pkgbinary):
                    self._pkgbinary.append(pbin)

    def setHidden(self, value=1):
        """set hidden attribute, which can be specified in
        a separate 'hide' statement
        """
        self._hidden = value

    def isConsistent(self, other):
        """Returns true if this task is consistent with another task object"""
        return self.__class__ == other.__class__ and \
            self.getFilename() == other.getFilename() and \
            self.hasParfile()  == other.hasParfile() and \
            self.getForeign()  == other.getForeign() and \
            self.getTbflag()   == other.getTbflag()

    # ---------------------------------------------------------
    # run the task
    # ---------------------------------------------------------

    def run(self, *args, **kw):
        """Execute this task with the specified arguments"""

        self.initTask(force=1)

        # Special _save keyword turns on parameter-saving.
        # Default is *not* to save parameters (so it is necessary
        # to use _save=1 to get parameter changes to be persistent.)
        if '_save' in kw:
            save = kw['_save']
            del kw['_save']
        else:
            save = 0

        # Handle other special keywords
        specialKW = self._specialKW(kw)

        # Special Stdout, Stdin, Stderr keywords are used to redirect IO
        redirKW, closeFHList = iraf.redirProcess(kw)

        # Set parameters ...
        # The setParList call sets _runningParList, which is a copy that is
        # only intended to live for the lifetime of the running task.  The
        # _currentParList version lives longer - it represents the on-disk
        # copy of the par list, during the life of this PyRAF session.
        kw['_setMode'] = 1
        self.setParList(*args, **kw)

        if Verbose > 1:
            print(f"run {self._name} ({self.__class__.__name__}: "
                  f"{self._fullpath})", file=sys.stderr)
            if self._runningParList:
                self._runningParList.lParam()

        # delete list of param dictionaries so it will be
        # recreated in up-to-date version if needed
        self._parDictList = None
        # apply IO redirection
        resetList = self._applyRedir(redirKW)
        try:
            # Hook for execution monitor
            if executionMonitor:
                executionMonitor(self)
            self._run(redirKW, specialKW)
            self._updateParList(save)
            if Verbose > 1:
                print('Successful task termination', file=sys.stderr)
        finally:
            rv = self._resetRedir(resetList, closeFHList)
            self._deleteRunningParList()
            if self._parDictList:
                self._parDictList[0] = (self._name, self.getParDict())
            if executionMonitor:
                executionMonitor()
        return rv

    def getMode(self, parList=None):
        """Returns mode string for this task

        Searches up the task, package, cl hierarchy for automatic modes
        """
        if parList is not None:
            mode = parList.getValue('mode', prompt=0)
        else:
            pdict = self.getParDict()
            if pdict:
                mode = pdict['mode'].get(prompt=0)
            else:
                mode = "a"
        if mode[:1] != "a":
            return mode

        # cl is the court of last resort, don't look at its packages
        if self is iraf.cl:
            return "h"

        # package name is undefined only at very start of initialization
        # just use the standard default
        if not self._pkgname:
            return "ql"

        # up we go -- look in parent package
        pkg = iraf.getPkg(self._pkgname)
        # clpackage is at top and is its own parent
        if pkg is not self:
            return pkg.getMode()
        # didn't find it in the package hierarchy, so use cl mode
        mode = iraf.cl.mode
        # default is hidden if automatic all the way to top
        if mode[:1] == "a":
            return "h"
        else:
            return mode

    def setParList(self, *args, **kw):
        """Set arguments to task in _runningParList copy of par list

        Creates a copy of the task parameter list and sets the
        parameters.  It is up to subsequent code (in the run method)
        to propagate these changes to the persistent parameter list.

        Special arguments:
        _setMode=1 to set modes of automatic parameters
        ParList can be used to pass in an entire parameter list object
        """
        self.initTask(force=1)

        if self._currentParList is None:
            return None

        # Special ParList parameter is used to pass in an entire
        # parameter list
        if 'ParList' in kw:
            parList = kw['ParList']
            del kw['ParList']
            if isinstance(parList, str):
                # must be a .par filename
                filename = parList
                parList = irafpar.IrafParList(self.getName(), filename)
            elif parList and not isinstance(parList, irafpar.IrafParList):
                raise TypeError("ParList parameter must be a filename or "
                                "an IrafParList object")
        else:
            parList = None

        if self._runningParList is not None:
            # only one runningParList at a time -- all tasks use it
            newParList = self._runningParList
            parList = None
        else:
            if parList:
                newParList = copy.deepcopy(parList)
            else:
                newParList = copy.deepcopy(self._currentParList)

        if '_setMode' in kw:
            _setMode = kw['_setMode']
            del kw['_setMode']
        else:
            _setMode = 0

        # create parlist copies for pset tasks too
        for p in newParList.getParList():
            if isinstance(p, irafpar.IrafParPset):
                p.get().setParList()

        # now, finally, set the passed-in parameters
        newParList.setParList(*args, **kw)
        if _setMode:
            # set mode of automatic parameters
            mode = self.getMode(newParList)
            for p in newParList.getParList():
                p.mode = p.mode.replace("a", mode)
        if parList:
            # XXX Set all command-line flags for parameters when a
            # XXX parlist is supplied so that it does not prompt for
            # XXX missing parameters.  Is this the preferred behavior?
            newParList.setAllFlags()

        self._runningParList = newParList

    # ---------------------------------------------------------
    # task parameter access
    # ---------------------------------------------------------

    def setParam(self,
                 qualifiedName,
                 newvalue,
                 check=1,
                 exact=0,
                 scope='',
                 idxHint=None):
        """Set parameter specified by qualifiedName to newvalue.

        qualifiedName can be a simple parameter name or can be
        [[package.]task.]paramname[.field].
        If check is set to zero, does not check value to make sure it
        satisfies min-max range or choice list.  scope, idxHint are ignored.
        """

        package, task, paramname, pindex, field = _splitName(qualifiedName)

        # special syntax for package parameters
        if task == "_":
            task = self._pkgname

        if task or package:
            if not package:
                # maybe this task is the name of one of the dictionaries?
                if self._parDictList is None:
                    self._setParDictList()
                for dictname, paramdict in self._parDictList:
                    if dictname == task:
                        if paramname in paramdict:
                            paramdict[paramname].set(newvalue,
                                                     index=pindex,
                                                     field=field,
                                                     check=check)
                            return
                        else:
                            raise IrafError(
                                "Attempt to set unknown parameter " +
                                qualifiedName + ' for task ' + task)
            # Not one of our dictionaries, so must find the relevant task
            if package:
                task = package + '.' + task
            try:
                tobj = iraf.getTask(task)
                # reattach the index and/or field
                if pindex:
                    paramname = paramname + '[' + repr(pindex + 1) + ']'
                if field:
                    paramname = paramname + '.' + field
                tobj.setParam(paramname, newvalue, check=check)
                return
            except KeyError:
                raise IrafError("Could not find task " + task +
                                " to get parameter " + qualifiedName)
            except IrafError as e:
                raise IrafError(
                    str(e) + "\nFailed to set parameter " + qualifiedName)

        # no task specified, just search the standard dictionaries
        # most of the time it will be in the active task dictionary

        paramdict = self.getParDict()
        if paramdict._has(paramname, exact=exact):
            paramdict[paramname].set(newvalue,
                                     index=pindex,
                                     field=field,
                                     check=check)
            return

        # OK, the easy case didn't work -- now initialize the
        # complete parDictList (if necessary) and search them all

        if self._parDictList is None:
            self._setParDictList()
        for dictname, paramdict in self._parDictList:
            if paramdict._has(paramname, exact=exact):
                paramdict[paramname].set(newvalue,
                                         index=pindex,
                                         field=field,
                                         check=check)
                return
        else:
            raise IrafError("Attempt to set unknown lone parameter " +
                            qualifiedName)

    def getParam(self, qualifiedName, native=1, mode=None, exact=0, prompt=1):
        """Return parameter specified by qualifiedName.

        qualifiedName can be a simple parameter name or can be
        [[package.]task.]paramname[.field].
        Paramname can also have an optional subscript, "param[1]".
        If native is non-zero (default), returns native format (e.g. float
        for floating point parameter.), otherwise returns string value.
        If exact is set, parameter name must match exactly.  Default
        is to do minimum match.
        If prompt is 0, does not prompt for parameter value (even if
        parameter is undefined.)
        """

        #       DBG "GP:", str(self._name), qualifiedName, native, mode, exact, prompt
        package, task, paramname, pindex, field = _splitName(qualifiedName)

        if (not task) or (task == self._name):
            # no task specified, just search the standard dictionaries
            return self._getParValue(paramname,
                                     pindex,
                                     field,
                                     native,
                                     mode,
                                     exact=exact,
                                     prompt=prompt)

        # when task is specified, ignore exact flag -- always do minmatch

        # special syntax for package parameters
        if task == "_":
            task = self._pkgname

        if not package:
            # maybe this task is the name of one of the dictionaries?
            if self._parDictList is None:
                self._setParDictList()
            for dictname, paramdict in self._parDictList:
                if dictname == task:
                    if paramname in paramdict:
                        return self._getParFromDict(paramdict,
                                                    paramname,
                                                    pindex,
                                                    field,
                                                    native,
                                                    mode="h",
                                                    prompt=prompt)
                    else:
                        raise IrafError("Unknown parameter requested: " +
                                        qualifiedName)

        # Not one of our dictionaries, so must find the relevant task
        if package:
            task = package + '.' + task
        try:
            tobj = iraf.getTask(task)
            return tobj._getParValue(paramname,
                                     pindex,
                                     field,
                                     native,
                                     mode="h",
                                     prompt=prompt)
        except KeyError:
            raise IrafError("Could not find task " + task +
                            " to get parameter " + qualifiedName)
        except IrafError as e:
            raise IrafError(
                str(e) + "\nFailed to get parameter " + qualifiedName)

    def _getParValue(self,
                     paramname,
                     pindex,
                     field,
                     native,
                     mode,
                     exact=0,
                     prompt=1):
        # search the standard dictionaries for the parameter
        # most of the time it will be in the active task dictionary
        paramdict = self.getParDict()
        try:
            if paramdict._has(paramname, exact=exact):
                return self._getParFromDict(paramdict,
                                            paramname,
                                            pindex,
                                            field,
                                            native,
                                            mode=mode,
                                            prompt=prompt)
        except minmatch.AmbiguousKeyError as e:
            # re-raise the error with a bit more info
            raise IrafError(f"Cannot get parameter `{paramname}'\n{str(e)}")

        # OK, the easy case didn't work -- now initialize the
        # complete parDictList (if necessary) and search them all
        if self._parDictList is None:
            self._setParDictList()
        for dictname, paramdict in self._parDictList:
            if paramdict._has(paramname, exact=exact):
                return self._getParFromDict(paramdict,
                                            paramname,
                                            pindex,
                                            field,
                                            native,
                                            mode="h",
                                            prompt=prompt)
        else:
            raise IrafError(f'Unknown parameter requested: "{paramname}" '
                            f'for task: "{self._name}" '
                            f'in pkg: "{self._pkgname}"')

    # ---------------------------------------------------------
    # task parameter utility methods
    # ---------------------------------------------------------

    def lParam(self, verbose=0):
        """List the task parameters"""
        self.initTask(force=1)
        plist = self._runningParList or self._currentParList
        if plist:
            plist.lParam(verbose=verbose)
        else:
            sys.stderr.write(f"Task {self._name} has no parameter file\n")
            sys.stderr.flush()

    def eParam(self):
        """Edit the task parameters,  PyRAF Tk style"""
        self.initTask(force=1)
        # XXX always runs on current par list, not running par list?
        if self._currentParList:
            from . import epar
            epar.epar(self)
        else:
            sys.stderr.write(f"Task {self._name} has no parameter file\n")
            sys.stderr.flush()

    def tParam(self):
        """Edit the task parameters, IRAF curses style"""
        self.initTask(force=1)
        # XXX always runs on current par list, not running par list?
        if self._currentParList:
            from . import tpar
            tpar.tpar(self)
        else:
            sys.stderr.write(f"Task {self._name} has no parameter file\n")
            sys.stderr.flush()

    def dParam(self, cl=1):
        """Dump the task parameters

        Default is to write CL version of code; if cl parameter is
        false, writes Python executable code instead.
        """
        self.initTask(force=1)
        plist = self._runningParList or self._currentParList
        if plist:
            if cl:
                taskname = self._name
            else:
                taskname = f"iraf.{self._name}"
            plist.dParam(taskname, cl=cl)
        else:
            sys.stderr.write(f"Task {self._name} has no parameter file\n")
            sys.stderr.flush()

    def saveParList(self, filename=None, comment=None):
        """Write task parameters in .par format to filename (name or handle)

        If filename is omitted, writes to uparm scrunch file (if possible)
        Returns a string with the results.
        """
        self.initTask()
        # XXX always runs on current par list, not running par list?
        if not self._currentParList:
            return f"No parameters to save for task {self._name}"
        if filename is None:
            if self._scrunchParpath:
                filename = self._scrunchParpath
            else:
                status = f"Unable to save parameters for task {self._name}"
                if Verbose > 0:
                    print(status, file=sys.stderr)
                return status
        rv = self._currentParList.saveParList(filename, comment)
        return rv

    def unlearn(self):
        """Reset task parameters to their default values"""
        self.initTask(force=1)
        # XXX always runs on current par list, not running par list?
        if not self._currentParList:
            return
        if self._defaultParList is not None:
            # update defaultParList from file if necessary
            self._defaultParList.Update()
            if self._scrunchParpath and \
                    (self._scrunchParpath == self._currentParpath):
                try:
                    os.remove(iraf.Expand(self._scrunchParpath, noerror=1))
                except OSError:
                    pass
            self._currentParList = copy.deepcopy(self._defaultParList)
            self._currentParpath = self._defaultParpath
        else:
            raise IrafError("Cannot find default .par file for task " +
                            self._name)

    def scrunchName(self):
        """Return scrunched version of filename (used for uparm files)

        Scrunched version of filename is chars 1,2,last from package
        name and chars 1-5,last from task name.
        """
        s = self._pkgname[0:2]
        if len(self._pkgname) > 2:
            s = s + self._pkgname[-1:]
        s = s + self._name[0:5]
        if len(self._name) > 5:
            s = s + self._name[-1:]
        return s

    # =========================================================
    # special methods to give desired object syntax
    # =========================================================

    # parameters are accessible as attributes

    def __getattr__(self, name):
        if name[:1] == '_':
            raise AttributeError(name)
        self.initTask()
        try:
            return self.getParam(name, native=1)
        except SyntaxError as e:
            raise AttributeError(str(e))

    def __setattr__(self, name, value):
        # hidden Python parameters go into the standard dictionary
        # (hope there are none of these in IRAF tasks)
        if name[:1] == '_':
            self.__dict__[name] = value
        elif self.is_pseudo(name):
            self.__dict__[name] = value
        else:
            self.initTask()
            self.setParam(name, value)

    def is_pseudo(self, paramname):
        """Hook enabling ECL pseudos... always returns False"""
        return False

    # allow running task using taskname() or with
    # parameters as arguments, including keyword=value form.

    def __call__(self, *args, **kw):
        return self.run(*args, **kw)

    def __repr__(self):
        s = (f'<{self.__class__.__name__} {self._name} ({self._filename}) '
             f'Pkg: {self._pkgname} Bin: {":".join(self._pkgbinary)}')
        if self._foreign:
            s = s + ' Foreign'
        if self._hidden:
            s = s + ' Hidden'
        if self._hasparfile == 0:
            s = s + ' No parfile'
        if self._tbflag:
            s = s + ' .tb'
        return s + '>'

    def __str__(self):
        return repr(self)

    # =========================================================
    # private methods -- may be used by subclasses, but should
    # not be needed outside this module
    # =========================================================

    def _specialKW(self, kw):
        """Return dictionary of any special keywords (subclass hook)"""
        return {}

    def _applyRedir(self, redirKW):
        """Apply I/O redirection (irafexecute does this for executables)

        Return a list of redirections that need to be restored when done.
        """
        return []

    def _resetRedir(self, resetList, closeFHList):
        """Restore redirected I/O and close files"""
        return iraf.redirReset(resetList, closeFHList)

    def _run(self, redirKW, specialKW):
        """Execute task after parameters, I/O redirection are prepared.

        The implementation of this can differ for each type of task.
        """
        try:
            irafexecute.IrafExecute(self, iraf.getVarDict(), **redirKW)
        except irafexecute.IrafProcessError as value:
            raise IrafError("Error running IRAF task " + self._name + "\n" +
                            str(value))

    def _updateParList(self, save=0):
        """Update parameter list after successful task completion

        Updates parameter save file if any parameters change.  If save
        flag is set, all changes are saved; if save flag is false, only
        explicit parameter changes requested by the task are saved.
        """
        if not (self._currentParList and self._runningParList):
            return
        newParList = self._runningParList
        self._runningParList = None
        mode = self.getMode(newParList)
        changed = 0
        for par in newParList.getParList():
            if par.name != "$nargs" and (par.isChanged() or
                                         (save and par.isCmdline() and
                                          par.isLearned(mode))):
                changed = 1
                # get task parameter object
                tpar = self._currentParList.getParObject(par.name)
                # set its value -- don't bother with type checks since
                # the new and old parameters must be identical
                tpar.value = par.value
                # propagate other mutable fields too
                # don't propagate modes since I changed them
                # (note IRAF does not propagate prompt, which I consider a bug)
                tpar.min = par.min
                tpar.max = par.max
                tpar.choice = par.choice
                tpar.prompt = par.prompt
                tpar.setChanged()
            if isinstance(par, irafpar.IrafParPset):
                par.get()._updateParList(save)
        # save to disk if there were changes
        if changed:
            rv = self.saveParList()
            if Verbose > 1:
                print(rv, file=sys.stderr)

    def _deleteRunningParList(self):
        """Delete the _runningParList parameter list for this and psets"""
        if self._currentParList and self._runningParList:
            newParList = self._runningParList
            self._runningParList = None
            for par in newParList.getParList():
                if isinstance(par, irafpar.IrafParPset):
                    par.get()._deleteRunningParList()

    def _setParDictList(self):
        """Set the list of (up to 3) parameter dictionaries for task execution.

        Parameter dictionaries for execution consist of this
        task's parameters (which includes any psets
        referenced), all the parameters for the task of the package
        loaded for the current task, and the cl parameters.  Each
        dictionary has an associated name (because parameters could be
        asked for as task.parname as well as just parname).

        Create this list anew for each execution in case the
        list of loaded packages has changed.  It is stored as
        an attribute of this object so it can be accessed by
        the getParam() and setParam() methods.
        """

        # Start with the parameters for the current task
        self.initTask()
        parDictList = [(self._name, self.getParDict())]

        # Next, parameters from the package to which the current task belongs
        # [Ticket 59: mimic behavior of param.c:lookup_param()]
        task = iraf.getTask(self.getPkgname())
        pd = task.getParDict()
        if pd:  # do not include null dictionaries
            parDictList.append((self.getPkgname(), pd))

        # Lastly, cl parameters
        cl = iraf.cl
        if cl is not None:
            parDictList.append((cl.getName(), cl.getParDict()))

        # Done
        self._parDictList = parDictList

    def _getParFromDict(self, paramdict, paramname, pindex, field, native,
                        mode, prompt):
        # helper method for getting parameter value (with indirection)
        # once we find a dictionary that contains it
        par = paramdict[paramname]
        pmode = par.mode[:1]
        if pmode == "a":
            pmode = mode or self.getMode()
        v = par.get(index=pindex,
                    field=field,
                    native=native,
                    mode=pmode,
                    prompt=prompt)
        if isinstance(v, str) and v[:1] == ")":

            # parameter indirection: call getParam recursively
            # I'm making the assumption that indirection in a
            # field (e.g. in the min or max value) is allowed
            # and that it uses exactly the same syntax as
            # the argument to getParam, i.e. ')task.param'
            # refers to the p_value of the parameter,
            # ')task.param.p_min' refers to the min or
            # choice string, etc.

            return self.getParam(v[1:], native=native, mode="h", prompt=prompt)
        else:
            return v

    def _initFullpath(self):
        """Fill in full pathname of executable"""

        # This follows the search strategy used by findexe in
        # cl/exec.c: first it checks in the BIN directory for the
        # "installed" version of the executable, and if that is not
        # found it tries the pathname given in the TASK declaration.
        # Expand iraf variables.  We will try both paths if the expand fails.
        try:
            exename1 = iraf.Expand(self._filename)
            # get name of executable file without path
            basedir, basename = os.path.split(exename1)
        except IrafError as e:
            if Verbose > 0:
                print("Error searching for executable for: " + self._name,
                      file=sys.stderr)
                print(str(e), file=sys.stderr)
            exename1 = ""
            # make our best guess that the basename is what follows the
            # last '$' in _filename
            s = self._filename.split("$")
            basename = s[-1]
        if basename == "":
            self._fullpath = ""
            raise IrafError(f"No filename in task {self._name} definition: "
                            f"`{self._filename}'")
        # for foreign tasks, just set path to filename (XXX will
        # want to improve this by checking os path for existence)
        if self._foreign:
            self._fullpath = self._filename
        else:
            # first look in the task binary directories
            exelist = []
            for pbin in self._pkgbinary:  # e.g. ['bin$']
                try:
                    exelist.append(iraf.Expand(pbin + basename))
                except IrafError as e:
                    if Verbose > 0:
                        print("Error finding executable for: " + self._name,
                              file=sys.stderr)
                        print(str(e), file=sys.stderr)
            for exename2 in exelist:
                if os.path.exists(exename2):
                    self._fullpath = exename2
                    break
            else:
                if os.path.exists(exename1):
                    self._fullpath = exename1
                else:
                    self._fullpath = ""
                    exelist.append(exename1)
                    raise IrafError(
                        f"Cannot find executable for task {self._name}\n"
                        f"Tried " + ", ".join(exelist))

    def _initParpath(self):
        """Initialize parameter file paths"""

        if not self._filename:
            # if filename is missing we won't be able to find parameter file
            # set hasparfile flag to zero if that is OK
            self._noParFile()
            self._hasparfile = 0

        if not self._hasparfile:
            # no parameter file
            self._defaultParpath = ""
            self._currentParpath = ""
            self._scrunchParpath = ""
            return

        try:
            exename1 = iraf.Expand(self._filename)
            basedir, basename = os.path.split(exename1)
            if basedir == "":
                basedir = "."
        except IrafError as e:
            if Verbose > 0:
                print("Error expanding executable name for task " +
                      self._name + ", tried: " + self._filename,
                      file=sys.stderr)
                print(str(e), file=sys.stderr)
            exename1 = ""
            basedir = ""

        # default parameters are found with task
        self._defaultParpath = os.path.join(basedir, self._name + ".par")
        if not os.path.exists(iraf.Expand(self._defaultParpath, noerror=1)):
            self._noParFile()
            self._defaultParpath = ""

        # uparm has scrunched version of par filename with saved parameters
        # (also handle if they forgot the end-slash on the uparm var)
        self._scrunchParpath = "uparm$/" + self.scrunchName() + ".par"

    def _noParFile(self):
        """Decide what to do if .par file is not found"""
        # Here I raise an exception, but subclasses (e.g., CL tasks)
        # can do something different.
        raise IrafError("Cannot find .par file for task " + self._name +
                        ", tried: " + self._defaultParpath + ", for file: " +
                        self._filename)

    def _initParList(self):
        """Initialize parameter list by reading parameter file"""

        if not self._hasparfile:
            return

        self._defaultParList = irafpar.IrafParList(
            self._name, iraf.Expand(self._defaultParpath, noerror=1))

        codePath = 'a'
        if self._scrunchParpath and os.path.exists(
                iraf.Expand(self._scrunchParpath, noerror=1)):
            self._currentParpath = self._scrunchParpath
            self._currentParList = irafpar.IrafParList(
                self._name, iraf.Expand(self._currentParpath, noerror=1))
            # are lists consistent?
            if not self._isConsistentPar():
                sys.stderr.write("uparm parameter list "
                                 f"`{self._currentParpath}' inconsistent with "
                                 "default parameters for "
                                 f"{self.__class__.__name__} `{self._name}'\n")
                sys.stderr.flush()
                # XXX just toss it for now -- later can try to merge new,old
                try:
                    os.remove(iraf.Expand(self._scrunchParpath, noerror=1))
                except OSError:
                    pass
                self._currentParpath = self._defaultParpath
                self._currentParList = copy.deepcopy(self._defaultParList)
        else:
            self._currentParpath = self._defaultParpath
            self._currentParList = copy.deepcopy(self._defaultParList)
            codePath = 'b'

        assert self._defaultParList._dlen() == \
            self._currentParList._dlen(), "Bad deep copy? "+ \
            str(self._defaultParList._dlen())+" != "+ \
            str(self._currentParList._dlen())+", cpath="+codePath

    def _isConsistentPar(self):
        """Check current par list and default par list for consistency"""
        return (not self._currentParList) or \
            self._currentParList.isConsistent(self._defaultParList)


# -----------------------------------------------------
# IRAF graphics kernel class
# -----------------------------------------------------


class IrafGKITask(IrafTask):
    """IRAF graphics kernel class (special case of IRAF task)"""

    def __init__(self, name, filename):
        """Initialize: only name and executable filename are needed"""
        IrafTask.__init__(self, '', name, '', filename, 'clpackage', 'bin$')
        self.setHidden()
        # all graphics kernel  tasks have the same parameters
        pars = irafpar.IrafParList(name)
        makepar = irafpar.makeIrafPar
        pars.addParam(makepar('', datatype='string', name='input', mode='ql'))
        pars.addParam(makepar('', datatype='string', name='device', mode='h'))
        pars.addParam(makepar('yes', datatype='bool', name='generic',
                              mode='h'))
        self._defaultParList = pars
        self._currentParList = pars

    def saveParList(self, filename=None):
        """Never save parameters for kernels"""
        return ""


# -----------------------------------------------------
# IRAF Pset class
# -----------------------------------------------------


class IrafPset(IrafTask):
    """IRAF pset class (special case of IRAF task)"""

    def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
        IrafTask.__init__(self, prefix, name, suffix, filename, pkgname,
                          pkgbinary)
        # check that parameters are consistent with pset:
        # - not a foreign task
        # - has a parameter file
        if self.getForeign():
            raise IrafError(
                f"Bad filename for pset {self.getName()}: {filename}")
        if not self.hasParfile():
            raise KeyError(f"Pset {self.getName()} has no parameter file")

    def _run(self, redirKW, specialKW):
        # executing a pset
        self.eParam()  # the cl runs the param editor here; so shall we

    def __str__(self):
        # when coerced to a string, pset is name of task
        # this makes assignment of a pset to a string do the right thing
        return self.getName()


# -----------------------------------------------------
# IRAF Python task class
# -----------------------------------------------------


class IrafPythonTask(IrafTask):
    """IRAF Python task class"""

    def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary,
                 function):
        # filename is the .par file for this task
        IrafTask.__init__(self, prefix, name, suffix, filename, pkgname,
                          pkgbinary)
        if self.getForeign():
            raise IrafError(f"Python task `{self.getName()}' cannot be foreign"
                            f" (filename=`{filename}')")
        self.__dict__['_pyFunction'] = function

    def isConsistent(self, other):
        """Returns true if this task is consistent with another task object"""
        return IrafTask.isConsistent(self, other) and \
            self._pyFunction == other._pyFunction

    # =========================================================
    # special methods
    # =========================================================

    def __getstate__(self):
        """Return state for pickling

        Note that __setstate__ is not needed because
        returned state is a dictionary
        """

        # Dictionary is OK except for function pointer, which can't
        # be restored unless function is in the pyraf package
        if self._pyFunction is None:
            return self.__dict__
        try:
            module = self._pyFunction.__globals__['__name__']
            if module[:6] == 'pyraf.':
                return self.__dict__
        except KeyError:
            pass
        # oh well, replace _pyFunction in shallow copy of dictionary
        sdict = self.__dict__.copy()
        sdict['_pyFunction'] = None
        return sdict

    # =========================================================
    # private methods
    # =========================================================

    def _applyRedir(self, redirKW):
        """Apply I/O redirection"""
        return iraf.redirApply(redirKW)

    def _run(self, redirKW, specialKW):
        """Execute task after parameters, I/O redirection are prepared."""
        # extract all parameters
        parList = self.getParList()
        pl = []
        for par in parList:
            if par.name not in ['mode', '$nargs']:
                if isinstance(par, irafpar.IrafParL):
                    # list parameters get passed as objects
                    pl.append(par)
                elif par.mode == "h" and not par.isLegal():
                    # illegal hidden value (generally undefined) passed as None
                    pl.append(None)
                else:
                    # other parameters get passed by value
                    pl.append(par.get(native=1))
        # run function on the parameters
        self._pyFunction(*pl)


# -----------------------------------------------------
# parDictList search class (helper for IrafCLTask)
# -----------------------------------------------------


class ParDictListSearch:

    def __init__(self, taskObj):
        self.__dict__['_taskObj'] = taskObj

    def __getattr__(self, paramname):
        if self._taskObj.is_pseudo(paramname):
            return getattr(self._taskObj, paramname)
        if paramname[:1] == '_':
            raise AttributeError(paramname)
        # try exact match
        try:
            return self._taskObj.getParam(paramname,
                                          native=1,
                                          mode="h",
                                          exact=1)
        except IrafError:
            pass
        # try minimum match
        try:
            p = self._taskObj.getParObject(paramname, alldict=1)
        except IrafError as e:
            # not found at all
            raise AttributeError(str(e))
        # it was found, but we don't allow min-match in CL scripts
        # print a more useful message
        raise AttributeError(f"Unknown parameter `{paramname}' "
                             f"(possibly intended `{p.name}'?)")

    def getParObject(self, paramname):
        # try exact match
        try:
            return self._taskObj.getParObject(paramname, exact=1, alldict=1)
        except IrafError:
            pass
        # try minimum match
        try:
            p = self._taskObj.getParObject(paramname, alldict=1)
        except IrafError as e:
            # not found at all
            raise AttributeError(str(e))
        # it was found, but we don't allow min-match in CL scripts
        # print a more useful message
        raise AttributeError(f"Unknown parameter `{paramname}' "
                             f"(possibly intended `{p.name}'?)")

    def __setattr__(self, paramname, value):
        if self._taskObj.is_pseudo(paramname):
            return setattr(self._taskObj, paramname, value)
        if paramname[:1] == '_':
            raise AttributeError(paramname)
        # try exact match
        try:
            return self._taskObj.setParam(paramname, value, exact=1)
        except IrafError:
            pass
        # try minimum match
        try:
            p = self._taskObj.getParObject(paramname, alldict=1)
        except IrafError as e:
            # not found at all
            raise AttributeError(str(e))
        # it was found, but we don't allow min-match in CL scripts
        # print a more useful message
        raise AttributeError(f"Unknown parameter `{paramname}' "
                             f"(possibly intended `{p.name}'?)")


# -----------------------------------------------------
# IRAF CL task class
# -----------------------------------------------------


class IrafCLTask(IrafTask):
    """IRAF CL task class"""

    def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
        # allow filename to be a filehandle or a filename
        if isinstance(filename, str):
            fh = None
        else:
            if not hasattr(filename, 'read'):
                raise TypeError(
                    'filename must be either a string or a filehandle')
            fh = filename
            if hasattr(fh, 'name'):
                filename = fh.name
            else:
                filename = None
        IrafTask.__init__(self, prefix, name, suffix, filename, pkgname,
                          pkgbinary)
        if self.getForeign():
            raise IrafError(f"CL task `{self.getName()}' cannot be foreign "
                            f"(filename=`{filename}')")
        # placeholder for Python translation of CL code
        # (lazy instantiation)
        self.__dict__['_pycode'] = None
        self.__dict__['_codeObject'] = None
        self.__dict__['_clFunction'] = None
        if fh is not None:
            # if filehandle was specified, go ahead and do the
            # initialization now
            self.initTask(filehandle=fh)

    # =========================================================
    # new public methods for CL task
    # =========================================================

    def getCode(self):
        """Return a string with the Python code for this task"""
        self.initTask(force=1)
        return self._pycode.code

    def reCompile(self):
        """Force recompilation of CL code"""
        if self._pycode is not None:
            self._pycode.index = None
        cl2py.codeCache.remove(self)
        self.initTask(force=1)

    # =========================================================
    # other public methods
    # =========================================================

    def initTask(self, force=0, filehandle=None):
        """Fill in full pathnames of files, read par file, compile CL code

        If filehandle is specified, reads CL code from there
        """

        if (not force) and (self._pycode is not None):
            # quick return if recheck of source code is not forced
            return

        if self._filename is None and filehandle is None and \
           self._pycode is not None:
            # another quick return -- if filename and filehandle are
            # both None and pycode is defined, input must have come
            # from a filehandle.  Then pycode does not need to be
            # recreated (and in fact, it cannot be recreated.)
            return

        if filehandle is not None and self._filename:
            self._fullpath = iraf.Expand(self._filename)

        IrafTask.initTask(self)

        if filehandle is None:
            filehandle = self._fullpath

        justMade = False
        fcopy = self._filename
        if not irafinst.EXISTS and fcopy.startswith(irafinst.NO_IRAF_PFX):
            # translate code to python
            if Verbose > 0:
                print("Compiling No-IRAF CL task: " + self._name,
                      file=sys.stderr)
            fcopy = os.path.basename(fcopy)
            self._codeObject = None
            self._pycode = cl2py.cl2py(None,
                                       string=irafinst.getNoIrafClFor(fcopy),
                                       parlist=self._defaultParList,
                                       parfile=self._defaultParpath)
            justMade = True

        if not justMade and not cl2py.checkCache(filehandle, self._pycode):
            # File has changed, force recompilation
            self._pycode = None
            if Verbose > 1:
                print("Cached version out-of-date: " + self._name,
                      file=sys.stderr)

        if self._pycode is None:
            # translate code to python
            if Verbose > 1:
                print("Compiling CL task ",
                      self._name,
                      id(self),
                      file=sys.stderr)
            self._codeObject = None
            self._pycode = cl2py.cl2py(filehandle,
                                       parlist=self._defaultParList,
                                       parfile=self._defaultParpath)

        if self._codeObject is None:
            # No code object, which can happen if function has not
            # been compiled or if compilation failed.  Try compiling
            # again in any case.
            self._clFunction = None
            if self._pkgname:
                scriptname = f'<CL script {self._pkgname}.{self._name}>'
            else:
                # null pkgname -- just use task in name
                scriptname = f'<CL script {self._name}>'
            # force compile to inherit future div. so we don't rely on 2.x div.
            self._codeObject = compile(self._pycode.code, scriptname, 'exec',
                                       0, 0)

        if self._clFunction is None:
            # Execute the code to define the Python function in clDict
            clDict = {}
            exec(self._codeObject, clDict)
            self._clFunction = clDict[self._pycode.vars.proc_name]

            # get parameter list from CL code
            # This may replace an existing list -- that's OK since
            # the cl2py code has already checked it for consistency.
            self._defaultParList = self._pycode.vars.parList
            # use currentParList from .par file if exists and consistent
            if self._currentParpath:
                if not self._defaultParList.isConsistent(self._currentParList):
                    sys.stderr.write(
                        f"uparm parameter list `{self._currentParpath}' "
                        "inconsistent with default parameters for "
                        f"{self.__class__.__name__} `{self._name}'\n")
                    sys.stderr.flush()
                    # XXX just toss it for now -- later can try to merge new,old
                    if self._currentParpath == self._scrunchParpath:
                        try:
                            os.remove(iraf.Expand(self._scrunchParpath,
                                                  noerror=1))
                        except OSError:
                            pass
                    self._currentParpath = self._defaultParpath
                    self._currentParList = copy.deepcopy(self._defaultParList)
            else:
                self._currentParList = copy.deepcopy(self._pycode.vars.parList)
                self._currentParpath = self._defaultParpath

    # =========================================================
    # special methods
    # =========================================================

    def __getstate__(self):
        """Return state for pickling"""
        # Dictionary is OK except for function pointer
        # Note that __setstate__ is not needed because
        # returned state is a dictionary
        if self._clFunction is None:
            return self.__dict__
        # replace _clFunction in shallow copy of dictionary
        sdict = self.__dict__.copy()
        sdict['_clFunction'] = None
        return sdict

    # =========================================================
    # private methods
    # =========================================================

    def _applyRedir(self, redirKW):
        """Apply I/O redirection"""
        return iraf.redirApply(redirKW)

    def _run(self, redirKW, specialKW):
        """Execute task after parameters, I/O redirection are prepared."""
        self._runCode()

    def _runCode(self, parList=None, kw={}):
        """Run the procedure with current parameters"""
        # add the searchable task object to keywords
        kw['taskObj'] = ParDictListSearch(self)
        if parList is None:
            parList = self.getParList()
        # XXX
        # It might be better to pass all parameters as
        # keywords instead of as positional arguments?
        # That would be more robust against some errors
        # but would also not allow certain IRAF-like
        # behaviors (where the .par file gives a different
        # name for the parameter.)
        # XXX
        self._clFunction(*parList, **kw)

    def _noParFile(self):
        """Decide what to do if .par file is not found"""
        # For CL tasks, it is OK if no .par
        pass

    def _isConsistentPar(self):
        """Check current par list and default par list for consistency"""
        # they do not have to be consistent for CL task (at least not
        # where this is called, in IrafTask.initTask).
        # XXX This is a bit lax, eh?  Need something a bit stricter.
        return 1


# -----------------------------------------------------
# IRAF package class
# -----------------------------------------------------

# use empty "tag" class from irafglobals as base class


class IrafPkg(IrafCLTask, irafglobals.IrafPkg):
    """IRAF package class (special case of IRAF task)"""

    def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
        IrafCLTask.__init__(self, prefix, name, suffix, filename, pkgname,
                            pkgbinary)
        self._loaded = 0
        self._tasks = minmatch.MinMatchDict()
        self._subtasks = minmatch.MinMatchDict()
        self._pkgs = minmatch.MinMatchDict()

    # =========================================================
    # new public methods for package
    # =========================================================

    def __str__(self):
        """ Describe this object. """
        retval = "IrafPkg:  name="+self.getName()+", pkg="+self.getPkgname()+ \
                 ", file="+self.getFilename()+"\n"
        retval += "tasks: " + str(self._tasks) + "\n"
        retval += "subtasks: " + str(self._subtasks) + "\n"
        retval += "packages: " + str(self._pkgs) + "\n"
        return retval

    def isLoaded(self):
        """Returns true if this package has already been loaded"""
        return self._loaded

    def addTask(self, task, fullname):
        """Add a task to the task list for this package

        Just store the name of the task to avoid cycles
        """
        name = task.getName()
        self._tasks.add(name, fullname)
        # sub-packages get added to a separate list
        if isinstance(task, IrafPkg):
            self._pkgs.add(name, name)

    # =========================================================
    # other public methods
    # =========================================================

    def getAllMatches(self, name, triedpkgs=None):
        """Return list of names of all parameters/tasks that may match name"""
        self.initTask(force=1)
        plist = self._runningParList or self._currentParList
        if plist:
            matches = plist.getAllMatches(name)
        else:
            matches = []
        if self._loaded:
            # tasks in this package
            if name == "":
                matches.extend(list(self._tasks.keys()))
            else:
                matches.extend(self._tasks.getallkeys(name, []))
            # tasks in subpackages
            if not triedpkgs:
                triedpkgs = {}
            triedpkgs[id(self)] = 1
            getPkg = iraf.getPkg
            getTried = triedpkgs.get
            for fullname in self._pkgs.values():
                p = getPkg(fullname)
                if p._loaded and (not getTried(id(p))):
                    try:
                        matches.extend(
                            p.getAllMatches(name, triedpkgs=triedpkgs))
                    except AttributeError:
                        pass
        return matches

    def unlearn(self):
        """Resets parameters for all tasks in the package to their default values"""
        # If package isn't loaded, just unlearn the top-level package parameters,
        # otherwise unlearn top-level ones AND all sub tasks.
        IrafCLTask.unlearn(self)
        if self._loaded:
            # Loop over all tasks in the package
            for task in self._tasks.keys():
                iraf.getTask(task).unlearn()

    def __getattr__(self, name):
        """Return the task or param 'name' from this package (if it exists)."""
        if name[:1] == '_':
            raise AttributeError(name)
        self.initTask()
        # return package parameter if it exists
        plist = self._runningParList or self._currentParList
        if plist and plist.hasPar(name):
            return plist.getValue(name, native=1, mode=self.getMode())
        # else search for task with the given name
        if not self._loaded:
            raise AttributeError("Package " + self.getName() +
                                 " has not been loaded; no tasks are defined")
        fullname = self._getTaskFullname(name)
        if fullname:
            return iraf.getTask(fullname)
        else:
            raise AttributeError(f"Parameter {name} not found")

    # =========================================================
    # private methods
    # =========================================================

    def _getTaskFullname(self, name, triedpkgs=None):
        """Return the full name (pkg.task) of task 'name' from this package

        Returns None if task is not found.

        Also searches subpackages for the task.  triedpkgs is
        a dictionary with all the packages that have already been
        tried.  It is used to avoid infinite recursion when
        packages contain themselves.

        Tasks that are found are added to _tasks dictionary to speed
        repeated searches.
        """
        if not self._loaded:
            return None
        task = self._tasks.get(name)
        if task:
            return task
        # try subpackages
        task = self._subtasks.get(name)
        if task:
            return task
        # search subpackages
        if not triedpkgs:
            triedpkgs = {}
        triedpkgs[id(self)] = 1
        getPkg = iraf.getPkg
        getTried = triedpkgs.get
        for fullname in self._pkgs.values():
            p = getPkg(fullname)
            if p._loaded and (not getTried(id(p))):
                task = p._getTaskFullname(name, triedpkgs=triedpkgs)
                if task:
                    self._subtasks.add(name, task)
                    return task
        return None

    def _specialKW(self, kw):
        """Handle special _doprint, _hush keywords"""

        # Special _hush keyword is used to suppress most output when loading
        # packages.  Default is to print output.
        # Implement by redirecting stdout to /dev/null (but don't override
        # other redirection requests)
        if '_hush' in kw:
            if kw['_hush'] and \
                    not (('Stdout' in kw) or ('StdoutAppend' in kw)):
                kw['Stdout'] = '/dev/null'
            del kw['_hush']
        # Special _doprint keyword is used to control whether tasks are listed
        # after package has been loaded.  Default is to list them if cl.menus
        # is set, or not to list them if it is not set.
        if '_doprint' in kw:
            doprint = kw['_doprint']
            del kw['_doprint']
        else:
            doprint = iraf.cl.menus
        return {'doprint': doprint}

    def _run(self, redirKW, specialKW):
        """Execute task after parameters, I/O redirection are prepared."""
        doprint = specialKW['doprint']
        # if already loaded, just add to iraf.loadedPath
        iraf.loadedPath.append(self)
        if not self._loaded:
            self._loaded = 1
            iraf.addLoaded(self)
            if Verbose > 1:
                print("Loading pkg: " + self.getName() + "(" +
                      self.getFullpath() + ")",
                      file=sys.stderr)
            menus = iraf.cl.menus
            try:
                iraf.cl.menus = 0
                self._runCode()
                # if other packages were loaded, put this on the
                # loadedPath list one more time
                if iraf.loadedPath[-1] is not self:
                    iraf.loadedPath.append(self)
                if doprint:
                    iraf.listTasks(self)
            finally:
                iraf.cl.menus = menus

    # -----------------------------------------------------
    # Turn an IrafCLTask into an IrafPkg
    # This is necessary because sometimes package scripts
    # are incorrectly defined as simple CL tasks.  (Currently
    # the only example I know of is the imred/ccdred/ccdtest
    # package, but there could be others.)  Need to keep
    # the same object (because there may be multiple references
    # to it) but repair the mistake by changing its class.
    #
    # A bit scary, but it works (at least in the current version
    # of Python.)
    #
    # This doesn't do everything that might be necessary.  E.g., it does
    # not print the package contents after loading and does not put the
    # package on the list of loaded pcakges.  Leave that up to the calling
    # routine.
    # -----------------------------------------------------


def mutateCLTask2Pkg(o, loaded=1, klass=IrafPkg):
    """Hack an IRAF CL task object into an IRAF package object"""

    if isinstance(o, IrafPkg):
        return
    if not isinstance(o, IrafCLTask):
        raise TypeError("Cannot turn object `{repr(o)}' into an IrafPkg")

    # add the extra attributes used in IrafPkg
    # this is usually called while actually loading the package, so by
    # default loaded flag is set to true
    o._loaded = loaded
    o._tasks = minmatch.MinMatchDict()
    o._pkgs = minmatch.MinMatchDict()

    # Presto, you're an IrafPkg!
    o.__class__ = klass


# -----------------------------------------------------
# IRAF foreign task class
# -----------------------------------------------------

# regular expressions for parameter substitution
_re_foreign_par = re.compile(r'\$' + r'((?P<n>[0-9]+)' + r'|(?P<all>\*)' +
                             r'|(\((?P<paren>[0-9]+)\))' +
                             r'|(\((?P<allparen>\*)\))' + r')')


class IrafForeignTask(IrafTask):
    """IRAF foreign task class"""

    def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
        IrafTask.__init__(self, prefix, name, suffix, filename, pkgname,
                          pkgbinary)
        # check that parameters are consistent with foreign task:
        # - foreign flag set
        # - no parameter file
        if not self.getForeign():
            raise IrafError(f"Bad filename for foreign task {self.getName()}: "
                            f"{filename}")
        if self.hasParfile():
            if Verbose > 0:
                print("Foreign task " + self.getName() +
                      " cannot have a parameter file",
                      file=sys.stderr)
            self._hasparfile = 0

    def setParList(self, *args, **kw):
        """Set arguments to task

        Does not use IrafParList structure -- just keeps list of
        the arguments
        """
        if '_setMode' in kw:
            del kw['_setMode']
        if len(kw) > 0:
            raise ValueError(f'Illegal keyword parameters {list(kw.keys())} '
                             f'for task {self._name}')
        # self._args = args
        # Insure that all arguments passed to ForeignTasks are
        # converted to strings, including objects which are not
        # naturally converted to strings.
        # self._args = map(re.escape,map(str,args))
        self._args = list(map(self._str_escape, args))

    # =========================================================
    # private methods
    # =========================================================
    def _str_escape(self, arg):
        if not isinstance(arg, str):
            _arg = re.escape(str(arg))
        else:
            _arg = arg
        return _arg

    def _applyRedir(self, redirKW):
        """Apply I/O redirection"""
        return iraf.redirApply(redirKW)

    def _run(self, redirKW, specialKW):
        """Execute task after parameters, I/O redirection are prepared."""
        args = self._args
        self._nsub = 0
        # create command line
        cmdline = _re_foreign_par.sub(self._parSub, self._filename)
        if self._nsub == 0 and args:
            # no argument substitution, just append all args
            cmdline = cmdline + ' ' + ' '.join(args)
        if Verbose > 1:
            print("Running foreign task: " + cmdline, file=sys.stderr)
        # create and run the sub-process
        subproc.subshellRedir(cmdline)

    def _parSub(self, mo):
        """Substitute an argument for this match object"""
        self._nsub = self._nsub + 1
        n = mo.group('n')
        if n is not None:
            # $n -- simple substitution
            n = int(n)
            if n > len(self._args):
                return ''
            elif n == 0:
                return self._name
            else:
                return self._args[n - 1]
        n = mo.group('paren')
        if n is not None:
            # $(n) -- expand IRAF virtual filenames
            n = int(n)
            if n > len(self._args):
                return ''
            elif n == 0:
                return self._name
            else:
                return iraf.Expand(self._args[n - 1])
        n = mo.group('all')
        if n is not None:
            # $* -- append all arguments
            return ' '.join(self._args)
        n = mo.group('allparen')
        if n is not None:
            # $(*) -- append all arguments with virtual filenames converted
            return ' '.join(map(iraf.Expand, self._args))
        raise IrafError(f"Cannot handle foreign string `{self._filename}' "
                        f"for task {self._name}")


# -----------------------------------------------------
# Utility function to split qualified names into components
# -----------------------------------------------------


def _splitName(qualifiedName):
    """Split qualifiedName into components.

    qualifiedName looks like [[package.]task.]paramname[subscript][.field],
    where subscript is an index in brackets.  Returns a tuple with
    (package, task, paramname, subscript, field). IRAF one-based subscript
    is changed to Python zero-based subscript.
    """
    # name components may have had 'PY' appended if they match Python keywords
    slist = list(map(irafutils.untranslateName, qualifiedName.split('.')))

    # add field=None if not present

    if len(slist) == 1 or not basicpar.isParField(slist[-1]):
        # no field
        slist.append(None)
    if len(slist) > 4:
        raise IrafError("Illegal syntax for parameter: " + qualifiedName)
    slist = [None] * (4 - len(slist)) + slist

    # parse possible subscript and insert into list

    paramname = slist[2]
    pstart = paramname.find('[')
    if pstart >= 0:
        try:
            pend = paramname.rindex(']')
            pindex = int(paramname[pstart + 1:pend]) - 1
            slist[2:3] = [paramname[:pstart], pindex]
        except (TypeError, ValueError):
            raise IrafError("Illegal syntax for array parameter: " +
                            qualifiedName)
    else:
        slist[3:3] = [None]
    return slist


#
# When a user has a problem, I often wonder where the task they are
# using came from and how it is defined.  This set of tools shows a
# hierarchy of the task/package definitions that led us here.
#
# (I would also like to know what file contained the task definition, but
# that information is not available)
#
# This is used by the task "taskinfo" in iraffunctions.py; there is some
# user documentation there.
#


# find all the task definitions that match a particular wildcard
def gettask(name):
    return [x for x in all_task_definitions if fnmatch.fnmatch(x._name, name)]


# make a printable line about a single task object - this doesn't say everything,
# but it may say enough without being too cluttered.
def printable_task_def(x):
    cl = str(x.__class__)
    if '.' in cl:
        cl = cl.split('.')[-1]

    # I wonder if there is a significance to using getFullpath instead of _filename

    s = f"{x._name} : {x.getFullpath()} - pkgbinary={x._pkgbinary} class={cl}"
    return s


# show a task line, then show the package that task may have come from, then where
# that came from, and so on.  The top level is normally "clpackage" which is its
# own parent.
def showtasklong(name, level=0):
    l = gettask(name)
    if len(l) < 1:
        print(("    " * level) + f'{name} : NOT FOUND')
    else:
        l.sort()
        for x in l:
            print(("    " * level) + printable_task_def(x))
            next_name = x._pkgname
            if (next_name == name) or (level > 15):
                pass
            else:
                showtasklong(next_name, level=level + 1)
