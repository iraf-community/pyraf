""" Contains the ConfigObjPars class and any related functionality.

$Id$
"""
import copy
import glob
import os
import stat
import sys

# ConfigObj modules
from . import configobj, validate

# Local modules
from . import basicpar, eparoption, irafutils, taskpars, vtor_checks

# Globals and useful functions

APP_NAME = 'TEAL'
TASK_NAME_KEY = '_task_name_'


class DuplicateKeyError(Exception):
    pass


class NoCfgFileError(Exception):
    pass


def getAppDir():
    """ Return our application dir.  Create it if it doesn't exist. """
    # Be sure the resource dir exists
    theDir = os.path.expanduser('~/.')+APP_NAME.lower()
    if not os.path.exists(theDir):
        try:
            os.mkdir(theDir)
        except OSError:
            print('Could not create "'+theDir+'" to save GUI settings.')
            theDir = "./"+APP_NAME.lower()
    return theDir


def getObjectFromTaskArg(theTask, strict, setAllToDefaults):
    """ Take the arg (usually called theTask), which can be either a subclass
    of ConfigObjPars, or a string package name, or a .cfg filename - no matter
    what it is - take it and return a ConfigObjPars object.
    strict - bool - warning severity, passed to the ConfigObjPars() ctor
    setAllToDefaults - bool - if theTask is a pkg name, force all to defaults
    """

    # Already in the form we need (instance of us or of subclass)
    if isinstance(theTask, ConfigObjPars):
        if setAllToDefaults:
            raise RuntimeError('Called getObjectFromTaskArg with existing'+\
                  ' object AND setAllToDefaults - is unexpected use case.')
        # If it is an existing object, make sure it's internal param list is
        # up to date with it's ConfigObj dict, since the user may have manually
        # edited the dict before calling us.
        theTask.syncParamList(False) # use strict somehow?
        # Note - some validation is done here in IrafPar creation, but it is
        # not the same validation done by the ConfigObj s/w (no check funcs).
        # Do we want to do that too here?
        return theTask

    # For example, a .cfg file
    if os.path.isfile(str(theTask)):
        try:
            return ConfigObjPars(theTask, strict=strict,
                                 setAllToDefaults=setAllToDefaults)
        except KeyError:
            # this might just be caused by a file sitting in the local cwd with
            # the same exact name as the package we want to import, let's see
            if theTask.find('.') > 0: # it has an extension, like '.cfg'
                raise # this really was an error
            # else we drop down to the next step - try it as a pkg name

    # Else it must be a Python package name to load
    if isinstance(theTask, str) and setAllToDefaults:
        # NOTE how we pass the task name string in setAllToDefaults
        return ConfigObjPars('', setAllToDefaults=theTask, strict=strict)
    else:
        return getParsObjForPyPkg(theTask, strict)


def getEmbeddedKeyVal(cfgFileName, kwdName, dflt=None):
    """ Read a config file and pull out the value of a given keyword. """
    # Assume this is a ConfigObj file.  Use that s/w to quickly read it and
    # put it in dict format.  Assume kwd is at top level (not in a section).
    # The input may also be a .cfgspc file.
    #
    # Only use ConfigObj here as a tool to generate a dict from a file - do
    # not use the returned object as a ConfigObj per se.  As such, we can call
    # with "simple" format, ie. no cfgspc, no val'n, and "list_values"=False.
    try:
        junkObj = configobj.ConfigObj(cfgFileName, list_values=False)
    except:
        if kwdName == TASK_NAME_KEY:
            raise KeyError('Can not parse as a parameter config file: '+ \
                           '\n\t'+os.path.realpath(cfgFileName))
        else:
            raise KeyError('Unfound key "'+kwdName+'" while parsing: '+ \
                           '\n\t'+os.path.realpath(cfgFileName))

    if kwdName in junkObj:
        retval = junkObj[kwdName]
        del junkObj
        return retval
    # Not found
    if dflt is not None:
        del junkObj
        return dflt
    else:
        if kwdName == TASK_NAME_KEY:
            raise KeyError('Can not parse as a parameter config file: '+ \
                           '\n\t'+os.path.realpath(cfgFileName))
        else:
            raise KeyError('Unfound key "'+kwdName+'" while parsing: '+ \
                           '\n\t'+os.path.realpath(cfgFileName))


def findCfgFileForPkg(pkgName, theExt, pkgObj=None, taskName=None):
    """ Locate the configuration files for/from/within a given python package.
    pkgName is a string python package name.  This is used unless pkgObj
    is given, in which case pkgName is taken from pkgObj.__name__.
    theExt is either '.cfg' or '.cfgspc'. If the task name is known, it is
    given as taskName, otherwise one is determined using the pkgName.
    Returns a tuple of (package-object, cfg-file-name). """
    # arg check
    ext = theExt
    if ext[0] != '.': ext = '.'+theExt

    # Do the import, if needed
    pkgsToTry = {}
    if pkgObj:
        pkgsToTry[pkgObj.__name__] = pkgObj
    else:
        # First try something simple like a regular or dotted import
        try:
            fl = []
            if pkgName.find('.') > 0:
                fl = [ pkgName[:pkgName.rfind('.')], ]
            pkgsToTry[str(pkgName)] = __import__(str(pkgName), fromlist=fl)
        except:
            throwIt = True
            # One last case to try is something like "csc_kill" from
            # "acstools.csc_kill", but this convenience capability will only be
            # allowed if the parent pkg (acstools) has already been imported.
            if isinstance(pkgName, str) and pkgName.find('.') < 0:
                matches = [x for x in sys.modules.keys()
                           if x.endswith("."+pkgName)]
                if len(matches)>0:
                    throwIt = False
                    for mmm in matches:
                        pkgsToTry[mmm] = sys.modules[mmm]
            if throwIt:
                raise NoCfgFileError("Unfound package or "+ext+" file via: "+\
                                     "import "+str(pkgName))

    # Now that we have the package object (or a few of them to try), for each
    # one find the .cfg or .cfgspc file, and return
    # Return as soon as ANY match is found.
    for aPkgName in pkgsToTry:
        aPkg = pkgsToTry[aPkgName]
        path = os.path.dirname(aPkg.__file__)
        if len(path) < 1: path = '.'
        flist = irafutils.rglob(path, "*"+ext)
        if len(flist) < 1:
            continue

        # Go through these and find the first one for the assumed or given task
        # name.  The task name for 'BigBlackBox.drizzle' would be 'drizzle'.
        if taskName is None:
            taskName = aPkgName.split(".")[-1]
        flist.sort()
        for f in flist:
            # A .cfg file gets checked for _task_name_=val, but a .cfgspc file
            # will have a string check function signature as the val.
            if ext == '.cfg':
                itsTask = getEmbeddedKeyVal(f, TASK_NAME_KEY, '')
            else: # .cfgspc
                sigStr  = getEmbeddedKeyVal(f, TASK_NAME_KEY, '')
                # .cfgspc file MUST have an entry for TASK_NAME_KEY w/ a default
                itsTask = vtor_checks.sigStrToKwArgsDict(sigStr)['default']
            if itsTask == taskName:
                # We've found the correct file in an installation area.  Return
                # the package object and the found file.
                return aPkg, f

    # What, are you still here?
    raise NoCfgFileError('No valid '+ext+' files found in package: "'+ \
                         str(pkgName)+'" for task: "'+str(taskName)+'"')


def findAllCfgTasksUnderDir(aDir):
    """ Finds all installed tasks by examining any .cfg files found on disk
        at and under the given directory, as an installation might be.
        This returns a dict of { file name : task name }
    """
    retval = {}
    for f in irafutils.rglob(aDir, '*.cfg'):
        retval[f] = getEmbeddedKeyVal(f, TASK_NAME_KEY, '')
    return retval


def getCfgFilesInDirForTask(aDir, aTask, recurse=False):
    """ This is a specialized function which is meant only to keep the
        same code from needlessly being much repeated throughout this
        application.  This must be kept as fast and as light as possible.
        This checks a given directory for .cfg files matching a given
        task.  If recurse is True, it will check subdirectories.
        If aTask is None, it returns all files and ignores aTask.
    """
    if recurse:
        flist = irafutils.rglob(aDir, '*.cfg')
    else:
        flist = glob.glob(aDir+os.sep+'*.cfg')
    if aTask:
        retval = []
        for f in flist:
            try:
                if aTask == getEmbeddedKeyVal(f, TASK_NAME_KEY, ''):
                    retval.append(f)
            except Exception as e:
                print('Warning: '+str(e))
        return retval
    else:
        return flist


def getParsObjForPyPkg(pkgName, strict):
    """ Locate the appropriate ConfigObjPars (or subclass) within the given
        package. NOTE this begins the same way as getUsrCfgFilesForPyPkg().
        Look for .cfg file matches in these places, in this order:
          1 - any named .cfg file in current directory matching given task
          2 - if there exists a ~/.teal/<taskname>.cfg file
          3 - any named .cfg file in SOME*ENV*VAR directory matching given task
          4 - the installed default .cfg file (with the given package)
    """
    # Get the python package and it's .cfg file - need this no matter what
    installedPkg, installedFile = findCfgFileForPkg(pkgName, '.cfg')
    theFile = None
    tname = getEmbeddedKeyVal(installedFile, TASK_NAME_KEY)

    # See if the user has any of their own .cfg files in the cwd for this task
    if theFile is None:
        flist = getCfgFilesInDirForTask(os.getcwd(), tname)
        if len(flist) > 0:
            if len(flist) == 1: # can skip file times sort
                theFile = flist[0]
            else:
                # There are a few different choices.  In the absence of
                # requirements to the contrary, just take the latest.  Set up a
                # list of tuples of (mtime, fname) so we can sort by mtime.
                ftups = [ (os.stat(f)[stat.ST_MTIME], f) for f in flist]
                ftups.sort()
                theFile = ftups[-1][1]

    # See if the user has any of their own app-dir .cfg files for this task
    if theFile is None:
        flist = getCfgFilesInDirForTask(getAppDir(), tname) # verifies tname
        flist = [f for f in flist if os.path.basename(f) == tname+'.cfg']
        if len(flist) > 0:
            theFile = flist[0]
            if len(flist) != 1:  # should never happen
                raise ValueError(str(flist))

    # Add code to check an env. var defined area?  (speak to users first)

    # Did we find one yet?  If not, use the installed version
    useInstVer = False
    if theFile is None:
        theFile = installedFile
        useInstVer = True

    # Create a stand-in instance from this file.  Force a read-only situation
    # if we are dealing with the installed, (expected to be) unwritable file.
    return ConfigObjPars(theFile, associatedPkg=installedPkg,
                         forceReadOnly=useInstVer, strict=strict)


def getUsrCfgFilesForPyPkg(pkgName):
    """ See if the user has one of their own local .cfg files for this task,
        such as might be created automatically during the save of a read-only
        package, and return their names. """
    # Get the python package and it's .cfg file
    thePkg, theFile = findCfgFileForPkg(pkgName, '.cfg')
    # See if the user has any of their own local .cfg files for this task
    tname = getEmbeddedKeyVal(theFile, TASK_NAME_KEY)
    flist = getCfgFilesInDirForTask(getAppDir(), tname)
    return flist


def checkSetReadOnly(fname, raiseOnErr = False):
    """ See if we have write-privileges to this file.  If we do, and we
    are not supposed to, then fix that case. """
    if os.access(fname, os.W_OK):
        # We can write to this but it is supposed to be read-only. Fix it.
        # Take away usr-write, leave group and other alone, though it
        # may be simpler to just force/set it to: r--r--r-- or r--------
        irafutils.setWritePrivs(fname, False, ignoreErrors= not raiseOnErr)


def flattenDictTree(aDict):
    """ Takes a dict of vals and dicts (so, a tree) as input, and returns
    a flat dict (only one level) as output.  All key-vals are moved to
    the top level.  Sub-section dict names (keys) are ignored/dropped.
    If there are name collisions, an error is raised. """
    retval = {}
    for k in aDict:
        val = aDict[k]
        if isinstance(val, dict):
            # This val is a dict, get its data (recursively) into a flat dict
            subDict = flattenDictTree(val)
            # Merge its dict of data into ours, watching for NO collisions
            rvKeySet  = set(retval.keys())
            sdKeySet = set(subDict.keys())
            intr = rvKeySet.intersection(sdKeySet)
            if len(intr) > 0:
                raise DuplicateKeyError("Flattened dict already has "+ \
                    "key(s): "+str(list(intr))+" - cannot flatten this.")

            else:
                retval.update(subDict)
        else:
            if k in retval:
                raise DuplicateKeyError("Flattened dict already has key: "+\
                                        k+" - cannot flatten this.")
            else:
                retval[k] = val
    return retval


def countKey(theDict, name):
    """ Return the number of times the given par exists in this dict-tree,
    since the same key name may be used in different sections/sub-sections. """

    retval = 0
    for key in theDict:
        val = theDict[key]
        if isinstance(val, dict):
            retval += countKey(val, name) # recurse
        else:
            if key == name:
                retval += 1
                # can't break, even tho we found a hit, other items on
                # this level will not be named "name", but child dicts
                # may have further counts
    return retval


def findFirstPar(theDict, name, _depth=0):
    """ Find the given par.  Return tuple: (its own (sub-)dict, its value).
    Returns the first match found, without checking whether the given key name
    is unique or whether it is used in multiple sections. """

    for key in theDict:
        val = theDict[key]
#       print _depth*'   ', key, str(val)[:40]
        if isinstance(val, dict):
            retval = findFirstPar(val, name, _depth=_depth+1) # recurse
            if retval is not None:
                return retval
            # else keep looking
        else:
            if key == name:
                return theDict, theDict[name]
            # else keep looking
    # if we get here then we have searched this whole (sub)-section and its
    # descendants, and found no matches.  only raise if we are at the top.
    if _depth == 0:
        raise KeyError(name)
    else:
        return None


def findScopedPar(theDict, scope, name):
    """ Find the given par.  Return tuple: (its own (sub-)dict, its value). """
    # Do not search (like findFirstPar), but go right to the correct
    # sub-section, and pick it up.  Assume it is there as stated.
    if len(scope):
        theDict = theDict[scope] # ! only goes one level deep - enhance !
    return theDict, theDict[name] # KeyError if unfound


def setPar(theDict, name, value):
    """ Sets a par's value without having to give its scope/section. """
    section, previousVal = findFirstPar(theDict, name)
    # "section" is the actual object, not a copy
    section[name] = value


def mergeConfigObj(configObj, inputDict):
    """ Merge the inputDict values into an existing given configObj instance.
    The inputDict is a "flat" dict - it has no sections/sub-sections.  The
    configObj may have sub-sections nested to any depth.  This will raise a
    DuplicateKeyError if one of the inputDict keys is used more than once in
    configObj (e.g. within two different sub-sections). """
    # Expanded upon Warren's version in astrodrizzle

    # Verify that all inputDict keys in configObj are unique within configObj
    for key in inputDict:
        if countKey(configObj, key) > 1:
            raise DuplicateKeyError(key)
    # Now update configObj with each inputDict item
    for key in inputDict:
        setPar(configObj, key, inputDict[key])


def integrityTestAllPkgCfgFiles(pkgObj, output=True):
    """ Given a package OBJECT, inspect it and find all installed .cfg file-
    using tasks under it.  Then them one at a time via
    integrityTestTaskCfgFile, and report any/all errors. """
    if type(pkgObj) != type(os):
        raise ValueError("Expected module arg, got: " + str(type(pkgObj)))
    taskDict = findAllCfgTasksUnderDir(os.path.dirname(pkgObj.__file__))
    # taskDict is { cfgFileName : taskName }
    errors = []
    for fname in taskDict:
        taskName = taskDict[fname]
        try:
            if taskName:
                if output:
                    print('In '+pkgObj.__name__+', checking task: '+
                           taskName+', file: '+fname)
                integrityTestTaskCfgFile(taskName, fname)
        except Exception as e:
            errors.append(str(e))

    if len(errors) != 0:
        raise ValueError('Errors found while integrity testing .cfg ' +
                         'file(s) found under "' + pkgObj.__name__ + '":\n' +
                         ('\n'.join(errors)))


def integrityTestTaskCfgFile(taskName, cfgFileName=None):
    """ For a given task, inspect the given .cfg file (or simply find/use its
    installed .cfg file), and check those values against the defaults
    found in the installed .cfgspc file.  They should be the same.
    If the file name is not given, the installed one is found and used. """

    from . import teal # don't import above, to avoid circular import (may need to mv)
    if not cfgFileName:
        ignored, cfgFileName = findCfgFileForPkg(taskName, '.cfg')
    diffDict = teal.diffFromDefaults(cfgFileName, report=False)
    if len(diffDict) < 1:
        return # no error
    msg = 'The following par:value pairs from "'+cfgFileName+ \
          '" are not the correct defaults: '+str(diffDict)
    raise RuntimeError(msg)


class ConfigObjPars(taskpars.TaskPars, configobj.ConfigObj):
    """ This represents a task's dict of ConfigObj parameters. """

    def __init__(self, cfgFileName, forUseWithEpar=True,
                 setAllToDefaults=False, strict=True,
                 associatedPkg=None, forceReadOnly=False):
        """
        cfgFileName - string path/name of .cfg file
        forUseWithEpar - bool - will this be used in EPAR?
        setAllToDefaults - <True, False, or string> string is pkg name to import
        strict - bool - level of error/warning severity
        associatedPkg - loaded package object
        forceReadOnly - bool - make the .cfg file read-only
        """

        self._forUseWithEpar = forUseWithEpar
        self._rcDir = getAppDir()
        self._allTriggers = None # all known triggers in this object
        self._allDepdcs = None   # all known dependencies in this object
        self._allExecutes = None # all known codes-to-execute in this object
        self._neverWrite = []    # all keys which are NOT written out to .cfg
        self._debugLogger = None
        self._debugYetToPost = []
        self.__assocPkg = associatedPkg

        # The __paramList pointer remains the same for the life of this object
        self.__paramList = []

        # Set up ConfigObj stuff
        if not setAllToDefaults and not os.path.isfile(cfgFileName):
            raise ValueError("Config file not found: " + cfgFileName)
        self.__taskName = ''
        if setAllToDefaults:
            # they may not have given us a real file name here since they
            # just want defaults (in .cfgspc) so don't be too picky about
            # finding and reading the file.
            if isinstance(setAllToDefaults, str):
                # here they have very clearly said to load only the defaults
                # using the given name as the package name - below we will
                # have it imported in _findAssociatedConfigSpecFile()
                self.__taskName = setAllToDefaults
                setAllToDefaults = True
                cfgFileName = '' # ignore any given .cfg file, don't need one
            else:
                possible = os.path.splitext(os.path.basename(cfgFileName))[0]
                if os.path.isfile(cfgFileName):
                    self.__taskName = getEmbeddedKeyVal(cfgFileName,
                                      TASK_NAME_KEY, possible)
                else:
                    self.__taskName = possible
        else:
            # this is the real deal, expect a real file name
            self.__taskName = getEmbeddedKeyVal(cfgFileName, TASK_NAME_KEY)
            if forceReadOnly:
                checkSetReadOnly(cfgFileName)

        # Find the associated .cfgspc file (first make sure we weren't
        # given one by mistake)
        if not cfgFileName.endswith('.cfg') and \
           self.__taskName.find('(default=') >= 0:
            # Handle case where they gave us a .cfgspc by mistake (no .cfg)
            # (basically reset a few things)
            cfgSpecPath = os.path.realpath(cfgFileName)
            setAllToDefaults = True
            cfgFileName = ''
            sigStr  = getEmbeddedKeyVal(cfgSpecPath, TASK_NAME_KEY, '')
            self.__taskName = vtor_checks.sigStrToKwArgsDict(sigStr)['default']
        else:
            cfgSpecPath = self._findAssociatedConfigSpecFile(cfgFileName)
        if not os.path.exists(cfgSpecPath):
            raise ValueError("Matching configspec not found!  Expected: " + cfgSpecPath)

        self.debug('ConfigObjPars: .cfg='+str(cfgFileName)+ \
                   ', .cfgspc='+str(cfgSpecPath)+ \
                   ', defaults='+str(setAllToDefaults)+', strict='+str(strict))

        # Run the ConfigObj ctor.  The result of this (if !setAllToDefaults)
        # is the exact copy of the input file as a dict (ConfigObj).  If the
        # infile had extra pars or missing pars, they are still that way here.
        if setAllToDefaults:
            configobj.ConfigObj.__init__(self, configspec=cfgSpecPath)
        else:
            configobj.ConfigObj.__init__(self, os.path.abspath(cfgFileName),
                                         configspec=cfgSpecPath)

        # Before we validate (and fill in missing pars), find any lost pars
        # via this (somewhat kludgy) method suggested by ConfigObj folks.
        missing = '' # assume no .cfg file
        if strict and (not setAllToDefaults):
            # don't even populate this if not strict
            missing = findTheLost(os.path.abspath(cfgFileName), cfgSpecPath)

        # Validate it here.  We can't skip this step even if we are just
        # setting all to defaults, since this sets the values.
        # NOTE - this fills in values for any missing pars !  AND, if our
        # .cfgspc sets defaults vals, then missing pars are not an error...
        self._vtor = validate.Validator(vtor_checks.FUNC_DICT)
        # 'ans' will be True, False, or a dict (anything but True is bad)
        ans = self.validate(self._vtor, preserve_errors=True,
                            copy=setAllToDefaults)
        # Note: before the call to validate(), the list returned from
        # self.keys() is in the order found in self.filename.  If that file
        # was missing items that are in the .cfgspc, they will now show up
        # in self.keys(), but not necessarily in the same order as the .cfgspc
        hasTypeErr = ans != True
        extra = self.listTheExtras(True)

        # DEAL WITH ERRORS (in this way)
        #
        # wrong par type:
        #     strict -> severe error*
        #     not -> severe error
        # extra par(s) found:
        #     strict -> severe error
        #     not -> warn*
        # missing par(s):
        #     strict -> warn
        #     not - be silent
        #
        # *severe - if in GUI, pop up error & stop (e.g. file load), else raise
        # *warn - if in GUI, pop up warning, else print it to screen

        if extra or missing or hasTypeErr:
            flatStr = ''
            if ans == False:
                flatStr = "All values are invalid!"
            if ans != True and ans != False:
                flatStr = flattened2str(configobj.flatten_errors(self, ans))
            if missing:
                flatStr += "\n\n"+missing
            if extra:
                flatStr += "\n\n"+extra
            msg = "Validation warnings for: "
            if hasTypeErr or (strict and extra):
                msg = "Validation errors for: "
            msg = msg+os.path.realpath(cfgFileName)+\
                  "\n\n"+flatStr.strip('\n')
            if hasTypeErr or (strict and extra):
                raise RuntimeError(msg)
            else:
                # just inform them, but don't throw anything
                print(msg.replace('\n\n','\n'))

        # get the initial param list out of the ConfigObj dict
        self.syncParamList(True)

        # take note of all trigger logic
        self.debug(self.triggerLogicToStr())

        # see if we are using a package with it's own run() function
        self._runFunc = None
        self._helpFunc = None
        if self.__assocPkg is not None:
            if hasattr(self.__assocPkg, 'run'):
                self._runFunc = self.__assocPkg.run
            if hasattr(self.__assocPkg, 'getHelpAsString'):
                self._helpFunc = self.__assocPkg.getHelpAsString


    def setDebugLogger(self, obj):
        # set the object we can use to post debugging info
        self._debugLogger = obj
        # now that we have one, post anything we have saved up (and clear list)
        if obj and len(self._debugYetToPost) > 0:
            for msg in self._debugYetToPost:
                self._debugLogger.debug(msg)
        self._debugYetToPost = []

    def debug(self, msg):
        if self._debugLogger:
            self._debugLogger.debug(msg)
        else:
            # else just hold onto it until we do have a logger -during the
            # init phase we may not yet have a logger, yet have stuff to log
            self._debugYetToPost.append(msg) # add to our little cache

    def getDefaultSaveFilename(self, stub=False):
        """ Return name of file where we are expected to be saved if no files
        for this task have ever been saved, and the user wishes to save.  If
        stub is True, the result will be <dir>/<taskname>_stub.cfg instead of
        <dir>/<taskname>.cfg. """
        if stub:
            return self._rcDir+os.sep+self.__taskName+'_stub.cfg'
        else:
            return self._rcDir+os.sep+self.__taskName+'.cfg'

    def syncParamList(self, firstTime, preserve_order=True):
        """ Set or reset the internal param list from the dict's contents. """
        # See the note in setParam about this design.

        # Get latest par values from dict.  Make sure we do not
        # change the id of the __paramList pointer here.
        new_list = self._getParamsFromConfigDict(self, initialPass=firstTime)
                                               # dumpCfgspcTo=sys.stdout)
        # Have to add this odd last one for the sake of the GUI (still?)
        if self._forUseWithEpar:
            new_list.append(basicpar.IrafParS(['$nargs','s','h','N']))

        if len(self.__paramList) > 0 and preserve_order:
            # Here we have the most up-to-date data from the actual data
            # model, the ConfigObj dict, and we need to use it to fill in
            # our param list.  BUT, we need to preserve the order our list
            # has had up until now (by unique parameter name).
            namesInOrder = [p.fullName() for p in self.__paramList]
            if len(namesInOrder) != len(new_list):
                raise ValueError(
                    'Mismatch in num pars, had: ' + str(len(namesInOrder)) +
                    ', now we have: ' + str(len(new_list)) + ', ' +
                    str([p.fullName() for p in new_list]))
            self.__paramList[:] = [] # clear list, keep same pointer
            # create a flat dict view of new_list, for ease of use in next step
            new_list_dict = {} # can do in one step in v2.7
            for par in new_list: new_list_dict[par.fullName()] = par
            # populate
            for fn in namesInOrder:
                self.__paramList.append(new_list_dict[fn])
        else:
            # Here we just take the data in whatever order it came.
            self.__paramList[:] = new_list # keep same list pointer

    def getName(self): return self.__taskName

    def getPkgname(self):  return '' # subclasses override w/ a sensible value

    def getParList(self, docopy=False):
        """ Return a list of parameter objects.  docopy is ignored as the
        returned value is not a copy. """
        return self.__paramList

    def getDefaultParList(self):
        """ Return a par list just like ours, but with all default values. """
        # The code below (create a new set-to-dflts obj) is correct, but it
        # adds a tenth of a second to startup.  Clicking "Defaults" in the
        # GUI does not call this.  But this can be used to set the order seen.

        # But first check for rare case of no cfg file name
        if self.filename is None:
            # this is a .cfgspc-only kind of object so far
            self.filename = self.getDefaultSaveFilename(stub=True)
            return copy.deepcopy(self.__paramList)

        tmpObj = ConfigObjPars(self.filename, associatedPkg=self.__assocPkg,
                               setAllToDefaults=True, strict=False)
        return tmpObj.getParList()

    def getFilename(self):
        if self.filename in (None, ''):
            return self.getDefaultSaveFilename()
        else:
            return self.filename

    def getAssocPkg(self):
        return self.__assocPkg

    def canExecute(self):
        return self._runFunc is not None

    def isSameTaskAs(self, aCfgObjPrs):
        """ Return True if the passed in object is for the same task as
        we are. """
        return aCfgObjPrs.getName() == self.getName()

#   def strictUpdate(self, aDict):
#       """ Override the current values with those in the given dict.  This
#           is like dict's update, except it doesn't allow new keys and it
#           verifies the values (it does?!) """
#       if aDict is None:
#           return
#       for k in aDict:
#           v = aDict[k]
#           print("Skipping ovverride key = "+k+", val = "+str(v))

    def setParam(self, name, val, scope='', check=1, idxHint=None):
        """ Find the ConfigObj entry.  Update the __paramList. """
        theDict, oldVal = findScopedPar(self, scope, name)

        # Set the value, even if invalid.  It needs to be set before
        # the validation step (next).
        theDict[name] = val

        # If need be, check the proposed value.  Ideally, we'd like to
        # (somehow elegantly) only check this one item. For now, the best
        # shortcut is to only validate this section.
        if check:
            ans=self.validate(self._vtor, preserve_errors=True, section=theDict)
            if ans != True:
                flatStr = "All values are invalid!"
                if ans != False:
                    flatStr = flattened2str(configobj.flatten_errors(self, ans))
                raise RuntimeError("Validation error: "+flatStr)

        # Note - this design needs work.  Right now there are two copies
        # of the data:  the ConfigObj dict, and the __paramList ...
        # We rely on the idxHint arg so we don't have to search the __paramList
        # every time this is called, which could really slows things down.
        if idxHint is None:
            raise ValueError("ConfigObjPars relies on a valid idxHint")
        if name != self.__paramList[idxHint].name:
            raise ValueError(
                'Error in setParam, name: "' + name + '" != name at idxHint: "' +
                self.__paramList[idxHint].name + '", idxHint: ' + str(idxHint))
        self.__paramList[idxHint].set(val)

    def saveParList(self, *args, **kw):
        """Write parameter data to filename (string or filehandle)"""
        if 'filename' in kw:
            filename = kw['filename']
        if not filename:
            filename = self.getFilename()
        if not filename:
            raise ValueError("No filename specified to save parameters")

        if hasattr(filename,'write'):
            fh = filename
            absFileName = os.path.abspath(fh.name)
        else:
            absFileName = os.path.expanduser(filename)
            absDir = os.path.dirname(absFileName)
            if len(absDir) and not os.path.isdir(absDir): os.makedirs(absDir)
            fh = open(absFileName,'w')
        numpars = len(self.__paramList)
        if self._forUseWithEpar: numpars -= 1
        if not self.final_comment: self.final_comment = [''] # force \n at EOF
        # Empty the ConfigObj version of section.defaults since that is based
        # on an assumption incorrect for us, and override with our own list.
        # THIS IS A BIT OF MONKEY-PATCHING!  WATCH FUTURE VERSION CHANGES!
        # See Trac ticket #762.
        while len(self.defaults):
            self.defaults.pop(-1) # empty it, keeping ref
        for key in self._neverWrite:
            self.defaults.append(key)
        # Note also that we are only overwriting the top/main section's
        # "defaults" list, but EVERY [sub-]section has such an attribute...

        # Now write to file, delegating work to ConfigObj (note that ConfigObj
        # write() skips any items listed by name in the self.defaults list)
        self.write(fh)
        fh.close()
        retval = str(numpars) + " parameters written to " + absFileName
        self.filename = absFileName # reset our own ConfigObj filename attr
        self.debug('Keys not written: '+str(self.defaults))
        return retval

    def run(self, *args, **kw):
        """ This may be overridden by a subclass. """
        if self._runFunc is not None:
            # remove the two args sent by EditParDialog which we do not use
            if 'mode' in kw: kw.pop('mode')
            if '_save' in kw: kw.pop('_save')
            return self._runFunc(self, *args, **kw)
        else:
            raise taskpars.NoExecError('No way to run task "'+self.__taskName+\
                '". You must either override the "run" method in your '+ \
                'ConfigObjPars subclass, or you must supply a "run" '+ \
                'function in your package.')

    def triggerLogicToStr(self):
        """ Print all the trigger logic to a string and return it. """
        try:
            import json
        except ImportError:
            return "Cannot dump triggers/dependencies/executes (need json)"
        retval = "TRIGGERS:\n"+json.dumps(self._allTriggers, indent=3)
        retval += "\nDEPENDENCIES:\n"+json.dumps(self._allDepdcs, indent=3)
        retval += "\nTO EXECUTE:\n"+json.dumps(self._allExecutes, indent=3)
        retval += "\n"
        return retval


    def getHelpAsString(self):
        """ This may be overridden by a subclass. """
        if self._helpFunc is not None:
            return self._helpFunc()
        else:
            return 'No help string found for task "'+self.__taskName+ \
            '".  \n\nThe developer must either override the '+\
            'getHelpAsString() method in their ConfigObjPars \n'+ \
            'subclass, or they must supply such a function in their package.'

    def _findAssociatedConfigSpecFile(self, cfgFileName):
        """ Given a config file, find its associated config-spec file, and
        return the full pathname of the file. """

        # Handle simplest 2 cases first: co-located or local .cfgspc file
        retval = "."+os.sep+self.__taskName+".cfgspc"
        if os.path.isfile(retval): return retval

        retval = os.path.dirname(cfgFileName)+os.sep+self.__taskName+".cfgspc"
        if os.path.isfile(retval): return retval

        # Also try the resource dir
        retval = self.getDefaultSaveFilename()+'spc' # .cfgspc
        if os.path.isfile(retval): return retval

        # Now try and see if there is a matching .cfgspc file in/under an
        # associated package, if one is defined.
        if self.__assocPkg is not None:
            x, theFile = findCfgFileForPkg(None, '.cfgspc',
                                           pkgObj = self.__assocPkg,
                                           taskName = self.__taskName)
            return theFile

        # Finally try to import the task name and see if there is a .cfgspc
        # file in that directory
        x, theFile = findCfgFileForPkg(self.__taskName, '.cfgspc',
                                       taskName = self.__taskName)
        if os.path.exists(theFile):
            return theFile

        # unfound
        raise NoCfgFileError('Unfound config-spec file for task: "'+ \
                             self.__taskName+'"')


    def _getParamsFromConfigDict(self, cfgObj, scopePrefix='',
                                 initialPass=False, dumpCfgspcTo=None):
        """ Walk the given ConfigObj dict pulling out IRAF-like parameters into
        a list. Since this operates on a dict this can be called recursively.
        This is also our chance to find and pull out triggers and such
        dependencies. """
        # init
        retval = []
        if initialPass and len(scopePrefix) < 1:
            self._posArgs = [] # positional args [2-tuples]: (index,scopedName)
            # FOR SECURITY: the following 3 chunks of data,
            #     _allTriggers, _allDepdcs, _allExecutes,
            # are collected ONLY from the .cfgspc file
            self._allTriggers = {}
            self._allDepdcs = {}
            self._allExecutes = {}

        # start walking ("tell yer story walkin, buddy")
        # NOTE: this relies on the "in" operator returning keys in the
        # order that they exist in the dict (which depends on ConfigObj keeping
        # the order they were found in the original file)
        for key in cfgObj:
            val = cfgObj[key]

            # Do we need to skip this - if not a par, like a rule or something
            toBeHidden = isHiddenName(key)
            if toBeHidden:
                if key not in self._neverWrite and key != TASK_NAME_KEY:
                    self._neverWrite.append(key)
                    # yes TASK_NAME_KEY is hidden, but it IS output to the .cfg

            # a section
            if isinstance(val, dict):
                if not toBeHidden:
                    if len(list(val.keys()))>0 and len(retval)>0:
                        # Here is where we sneak in the section comment
                        # This is so incredibly kludgy (as the code was), it
                        # MUST be revamped eventually! This is for the epar GUI.
                        prevPar = retval[-1]
                        # Use the key (or its comment?) as the section header
                        prevPar.set(prevPar.get('p_prompt')+'\n\n'+key,
                                    field='p_prompt', check=0)
                    if dumpCfgspcTo:
                        dumpCfgspcTo.write('\n['+key+']\n')
                    # a logical grouping (append its params)
                    pfx = scopePrefix+'.'+key
                    pfx = pfx.strip('.')
                    retval = retval + self._getParamsFromConfigDict(val, pfx,
                                      initialPass, dumpCfgspcTo) # recurse
            else:
                # a param
                fields = []
                choicesOrMin = None
                fields.append(key) # name
                dtype = 's'
                cspc = None
                if cfgObj.configspec:
                    cspc = cfgObj.configspec.get(key) # None if not found
                chk_func_name = ''
                chk_args_dict = {}
                if cspc:
                    chk_func_name = cspc[:cspc.find('(')]
                    chk_args_dict = vtor_checks.sigStrToKwArgsDict(cspc)
                if chk_func_name.find('option') >= 0:
                    dtype = 's'
                    # convert the choices string to a list (to weed out kwds)
                    x = cspc[cspc.find('(')+1:-1] # just the options() args
# cspc e.g.: option_kw("poly5","nearest","linear", default="poly5", comment="Interpolant (poly5,nearest,linear)")
                    x = x.split(',') # tokenize
                    # but! comment value may have commas in it, find it
                    # using it's equal sign, rm all after it
                    has_eq = [i for i in x if i.find('=')>=0]
                    if len(has_eq) > 0:
                        x = x[: x.index(has_eq[0]) ]
                    # rm spaces, extra quotes; rm kywd arg pairs
                    x = [i.strip("' ") for i in x if i.find('=')<0]
                    choicesOrMin = '|'+'|'.join(x)+'|' # IRAF format for enums
                elif chk_func_name.find('boolean') >= 0:     dtype = 'b'
                elif chk_func_name.find('float_or_') >= 0:   dtype = 'r'
                elif chk_func_name.find('float') >= 0:       dtype = 'R'
                elif chk_func_name.find('integer_or_') >= 0: dtype = 'i'
                elif chk_func_name.find('integer') >= 0:     dtype = 'I'
                elif chk_func_name.find('action') >= 0:      dtype = 'z'
                fields.append(dtype)
                fields.append('a')
                if type(val)==bool:
                    if val: fields.append('yes')
                    else:   fields.append('no')
                else:
                    fields.append(val)
                fields.append(choicesOrMin)
                fields.append(None)
                # Primarily use description from .cfgspc file (0). But, allow
                # overrides from .cfg file (1) if different.
                dscrp0 = chk_args_dict.get('comment','').strip() # ok if missing
                dscrp1 = cfgObj.inline_comments[key]
                if dscrp1 is None:
                    dscrp1 = ''

                while len(dscrp1) > 0 and dscrp1[0] in (' ','#'):
                    dscrp1 = dscrp1[1:] # .cfg file comments start with '#'

                dscrp1 = dscrp1.strip()
                # Now, decide what to do/say about the descriptions
                if len(dscrp1) > 0:
                    dscrp = dscrp0
                    if dscrp0 != dscrp1: # allow override if different
                        dscrp = dscrp1+eparoption.DSCRPTN_FLAG # flag it
                        if initialPass:
                            if dscrp0 == '' and cspc is None:
                                # this is a case where this par isn't in the
                                # .cfgspc; ignore, it is caught/error later
                                pass
                            else:
                                self.debug('Description of "'+key+ \
                                    '" overridden, from:  '+repr(dscrp0)+\
                                    '  to:  '+repr(dscrp1))
                    fields.append(dscrp)
                else:
                    # set the field for the GUI
                    fields.append(dscrp0)
                    # ALSO set it in the dict so it is written to file later
                    cfgObj.inline_comments[key] = '# '+dscrp0
                # This little section, while never intended to be used during
                # normal operation, could save a lot of manual work.
                if dumpCfgspcTo:
                    junk = cspc
                    junk = key+' = '+junk.strip()
                    if junk.find(' comment=')<0:
                        junk = junk[:-1]+", comment="+ \
                               repr(irafutils.stripQuotes(dscrp1.strip()))+")"
                    dumpCfgspcTo.write(junk+'\n')
                # Create the par
                if not toBeHidden or chk_func_name.find('action')==0:
                    par = basicpar.parFactory(fields, True)
                    par.setScope(scopePrefix)
                    retval.append(par)
                # else this is a hidden key

                # The next few items require a fully scoped name
                absKeyName = scopePrefix+'.'+key # assumed to be unique
                # Check for pars marked to be positional args
                if initialPass:
                    pos = chk_args_dict.get('pos')
                    if pos:
                        # we'll sort them later, on demand
                        self._posArgs.append( (int(pos), scopePrefix, key) )
                # Check for triggers and/or dependencies
                if initialPass:
                    # What triggers what? (thats why theres an 's' in the kwd)
                    # try "trigger" (old)
                    if chk_args_dict.get('trigger'):
                        print("WARNING: outdated version of .cfgspc!! for "+
                              self.__taskName+", 'trigger' unused for "+
                              absKeyName)
                    # try "triggers"
                    trgs = chk_args_dict.get('triggers')
                    if trgs and len(trgs)>0:
                        # eg. _allTriggers['STEP2.xy'] == ('_rule1_','_rule3_')
                        if absKeyName in self._allTriggers:
                            raise ValueError('More than 1 of these in .cfgspc?: ' + absKeyName)
                        # we force this to always be a sequence
                        if isinstance(trgs, (list,tuple)):
                            self._allTriggers[absKeyName] = trgs
                        else:
                            self._allTriggers[absKeyName] = (trgs,)
                    # try "executes"
                    excs = chk_args_dict.get('executes')
                    if excs and len(excs)>0:
                        # eg. _allExecutes['STEP2.xy'] == ('_rule1_','_rule3_')
                        if absKeyName in self._allExecutes:
                            raise ValueError('More than 1 of these in .cfgspc?: ' + absKeyName)
                        # we force this to always be a sequence
                        if isinstance(excs, (list,tuple)):
                            self._allExecutes[absKeyName] = excs
                        else:
                            self._allExecutes[absKeyName] = (excs,)

                    # Dependencies? (besides these used here, may someday
                    # add: 'range_from', 'warn_if', etc.)
                    depName = None
                    if not depName:
                        depType = 'active_if'
                        depName = chk_args_dict.get(depType) # e.g. =='_rule1_'
                    if not depName:
                        depType = 'inactive_if'
                        depName = chk_args_dict.get(depType)
                    if not depName:
                        depType = 'is_set_by'
                        depName = chk_args_dict.get(depType)
                    if not depName:
                        depType = 'set_yes_if'
                        depName = chk_args_dict.get(depType)
                    if not depName:
                        depType = 'set_no_if'
                        depName = chk_args_dict.get(depType)
                    if not depName:
                        depType = 'is_disabled_by'
                        depName = chk_args_dict.get(depType)
                    # NOTE - the above few lines stops at the first dependency
                    # found (depName) for a given par.  If, in the future a
                    # given par can have >1 dependency than we need to revamp!!
                    if depName:
                        # Add to _allDepdcs dict: (val is dict of pars:types)
                        #
                        # e.g. _allDepdcs['_rule1_'] == \
                        #        {'STEP3.ra':      'active_if',
                        #         'STEP3.dec':     'active_if',
                        #         'STEP3.azimuth': 'inactive_if'}
                        if depName in self._allDepdcs:
                            thisRulesDict = self._allDepdcs[depName]
                            if absKeyName in thisRulesDict:
                                raise ValueError(
                                    'Cant yet handle multiple actions for the ' +
                                    'same par and the same rule.  For "' + depName +
                                    '" dict was: ' + str(thisRulesDict) +
                                    ' while trying to add to it: ' +
                                    str({absKeyName: depType}))
                            thisRulesDict[absKeyName] = depType
                        else:
                            self._allDepdcs[depName] = {absKeyName:depType}
                    # else no dependencies found for this chk_args_dict
        return retval


    def getTriggerStrings(self, parScope, parName):
        """ For a given item (scope + name), return all strings (in a tuple)
        that it is meant to trigger, if any exist.  Returns None is none. """
        # The data structure of _allTriggers was chosen for how easily/quickly
        # this particular access can be made here.
        fullName = parScope+'.'+parName
        return self._allTriggers.get(fullName) # returns None if unfound


    def getParsWhoDependOn(self, ruleName):
        """ Find any parameters which depend on the given trigger name. Returns
        None or a dict of {scopedName: dependencyName} from _allDepdcs. """
        # The data structure of _allDepdcs was chosen for how easily/quickly
        # this particular access can be made here.
        return self._allDepdcs.get(ruleName)


    def getExecuteStrings(self, parScope, parName):
        """ For a given item (scope + name), return all strings (in a tuple)
        that it is meant to execute, if any exist.  Returns None is none. """
        # The data structure of _allExecutes was chosen for how easily/quickly
        # this particular access can be made here.
        fullName = parScope+'.'+parName
        return self._allExecutes.get(fullName) # returns None if unfound


    def getPosArgs(self):
        """ Return a list, in order, of any parameters marked with "pos=N" in
            the .cfgspc file. """
        if len(self._posArgs) < 1: return []
        # The first item in the tuple is the index, so we now sort by it
        self._posArgs.sort()
        # Build a return list
        retval = []
        for idx, scope, name in self._posArgs:
            theDict, val = findScopedPar(self, scope, name)
            retval.append(val)
        return retval


    def getKwdArgs(self, flatten = False):
        """ Return a dict of all normal dict parameters - that is, all
            parameters NOT marked with "pos=N" in the .cfgspc file.  This will
            also exclude all hidden parameters (metadata, rules, etc). """

        # Start with a full deep-copy.  What complicates this method is the
        # idea of sub-sections.  This dict can have dicts as values, and so on.
        dcopy = self.dict() # ConfigObj docs say this is a deep-copy

        # First go through the dict removing all positional args
        for idx,scope,name in self._posArgs:
            theDict, val = findScopedPar(dcopy, scope, name)
            # 'theDict' may be dcopy, or it may be a dict under it
            theDict.pop(name)

        # Then go through the dict removing all hidden items ('_item_name_')
        for k in list(dcopy.keys()):
            if isHiddenName(k):
                dcopy.pop(k)

        # Done with the nominal operation
        if not flatten:
            return dcopy

        # They have asked us to flatten the structure - to bring all parameters
        # up to the top level, even if they are in sub-sections.  So we look
        # for values that are dicts.  We will throw something if we end up
        # with name collisions at the top level as a result of this.
        return flattenDictTree(dcopy)


    def canPerformValidation(self):
        """ Override this so we can do our own validation. tryValue() will
            be called as a result. """
        return True


    def knowAsNative(self):
        """ Override so we can keep native types in the internal dict. """
        return True


    def tryValue(self, name, val, scope=''):
        """ For the given item name (and scope), we are being asked to try
            the given value to see if it would pass validation.  We are not
            to set it, but just try it.  We return a tuple:
            If it fails, we return: (False,  the last known valid value).
            On success, we return: (True, None). """

        # SIMILARITY BETWEEN THIS AND setParam() SHOULD BE CONSOLIDATED!

        # Set the value, even if invalid.  It needs to be set before
        # the validation step (next).
        theDict, oldVal = findScopedPar(self, scope, name)
        if oldVal == val: return (True, None) # assume oldVal is valid
        theDict[name] = val

        # Check the proposed value.  Ideally, we'd like to
        # (somehow elegantly) only check this one item. For now, the best
        # shortcut is to only validate this section.
        ans=self.validate(self._vtor, preserve_errors=True, section=theDict)

        # No matter what ans is, immediately return the item to its original
        # value since we are only checking the value here - not setting.
        theDict[name] = oldVal

        # Now see what the validation check said
        errStr = ''
        if ans != True:
            flatStr = "All values are invalid!"
            if ans != False:
                flatStr = flattened2str(configobj.flatten_errors(self, ans))
            errStr = "Validation error: "+flatStr # for now this info is unused

        # Done
        if len(errStr): return (False, oldVal) # was an error
        else:           return (True, None)    # val is OK


    def listTheExtras(self, deleteAlso):
        """ Use ConfigObj's get_extra_values() call to find any extra/unknown
        parameters we may have loaded.  Return a string similar to findTheLost.
        If deleteAlso is True, this will also delete any extra/unknown items.
        """
        # get list of extras
        extras = configobj.get_extra_values(self)
        # extras is in format: [(sections, key), (sections, key), ]
        # but we need: [(sections, key, result), ...] - set all results to
        # a bool just to make it the right shape.  BUT, since we are in
        # here anyway, make that bool mean something - hide info in it about
        # whether that extra item is a section (1) or just a single par (0)
        #
        # simplified, this is:  expanded = [ (x+(abool,)) for x in extras]
        expanded = [ (x+ \
                       ( bool(len(x[0])<1 and hasattr(self[x[1]], 'keys')), ) \
                     ) for x in extras]
        retval = ''
        if expanded:
            retval = flattened2str(expanded, extra=1)
        # but before we return, delete them (from ourself!) if requested to
        if deleteAlso:
            for tup_to_del in extras:
                target = self
                # descend the tree to the dict where this items is located.
                # (this works because target is not a copy (because the dict
                #  type is mutable))
                location = tup_to_del[0]
                for subdict in location: target = target[subdict]
                # delete it
                target.pop(tup_to_del[1])

        return retval


# ---------------------------- helper functions --------------------------------


def findTheLost(config_file, configspec_file, skipHidden=True):
    """ Find any lost/missing parameters in this cfg file, compared to what
    the .cfgspc says should be there. This method is recommended by the
    ConfigObj docs. Return a stringified list of item errors. """
    # do some sanity checking, but don't (yet) make this a serious error
    if not os.path.exists(config_file):
        print("ERROR: Config file not found: "+config_file)
        return []
    if not os.path.exists(configspec_file):
        print("ERROR: Configspec file not found: "+configspec_file)
        return []
    tmpObj = configobj.ConfigObj(config_file, configspec=configspec_file)
    simval = configobj.SimpleVal()
    test = tmpObj.validate(simval)
    if test == True:
        return []
    # If we get here, there is a dict returned of {key1: bool, key2: bool}
    # which matches the shape of the config obj.  We need to walk it to
    # find the Falses, since they are the missing pars.
    missing = []
    flattened = configobj.flatten_errors(tmpObj, test)
    # But, before we move on, skip/eliminate any 'hidden' items from our list,
    # since hidden items are really supposed to be missing from the .cfg file.
    if len(flattened) > 0 and skipHidden:
        keepers = []
        for tup in flattened:
            keep = True
            # hidden section
            if len(tup[0])>0 and isHiddenName(tup[0][-1]):
                keep = False
            # hidden par (in a section, or at the top level)
            elif tup[1] is not None and isHiddenName(tup[1]):
                keep = False
            if keep:
                keepers.append(tup)
        flattened = keepers
    flatStr = flattened2str(flattened, missing=True)
    return flatStr


def isHiddenName(astr):
    """ Return True if this string name denotes a hidden par or section """
    if astr is not None and len(astr) > 2 and astr.startswith('_') and \
       astr.endswith('_'):
        return True
    else:
        return False


def flattened2str(flattened, missing=False, extra=False):
    """ Return a pretty-printed multi-line string version of the output of
    flatten_errors. Know that flattened comes in the form of a list
    of keys that failed. Each member of the list is a tuple::

        ([list of sections...], key, result)

    so we turn that into a string. Set missing to True if all the input
    problems are from missing items.  Set extra to True if all the input
    problems are from extra items. """

    if flattened is None or len(flattened) < 1:
        return ''
    retval = ''
    for sections, key, result in flattened:
        # Name the section and item, to start the message line
        if sections is None or len(sections) == 0:
            retval += '\t"'+key+'"'
        elif len(sections) == 1:
            if key is None:
                # a whole section is missing at the top-level; see if hidden
                junk = sections[0]
                if isHiddenName(junk):
                    continue # this missing or extra section is not an error
                else:
                    retval += '\tSection "'+sections[0]+'"'
            else:
                retval += '\t"'+sections[0]+'.'+key+'"'
        else: # len > 1
            joined = '.'.join(sections)
            joined = '"'+joined+'"'
            if key is None:
                retval +=  '\tSection '+joined
            else:
                retval +=  '\t"'+key+'" from '+joined
        # End the msg line with "what seems to be the trouble" with this one
        if missing and result==False:
            retval += ' is missing.'
        elif extra:
            if result:
                retval += ' is an unexpected section. Is your file out of date?'
            else:
                retval += ' is an unexpected parameter. Is your file out of date?'
        elif isinstance(result, bool):
            retval += ' has an invalid value'
        else:
            retval += ' is invalid, '+result.message
        retval += '\n\n'
    return retval.rstrip()
