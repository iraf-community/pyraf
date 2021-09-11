"""module iraffunctions.py -- IRAF emulation tasks and functions

This is not usually used directly -- the relevant public classes and
functions get included in iraf.py.  The implementations are kept here
to avoid possible problems with name conflicts in iraf.py (which is the
home for all the IRAF task and package names.)  Private routines have
names beginning with '_' and do not get imported by the iraf module.

The exception is that iraffunctions can be used directly for modules
that must be compiled and executed early, before the pyraf module
initialization is complete.

R. White, 2000 January 20
"""


# define INDEF, yes, no, EOF, Verbose, IrafError, userIrafHome

from stsci.tools.irafglobals import *
from .subproc import SubprocessError

# -----------------------------------------------------
# setVerbose: set verbosity level
# -----------------------------------------------------


def setVerbose(value=1, **kw):
    """Set verbosity level when running tasks.
    Level 0 (default) prints almost nothing.
    Level 1 prints warnings.
    Level 2 prints info on progress.
    This accepts **kw so it can be used on the PyRAF command-line.  This
    cannot avail itself of the decorator which wraps redirProcess since it
    needs to be defined here up front.
    """
    if isinstance(value, str):
        try:
            value = int(value)
        except ValueError:
            pass
    Verbose.set(value)


def _writeError(msg):
    """Write a message to stderr"""
    _sys.stdout.flush()
    _sys.stderr.write(msg)
    if msg[-1:] != "\n":
        _sys.stderr.write("\n")


# -----------------------------------------------------
# now it is safe to import other iraf modules
# -----------------------------------------------------

# hide these modules so we can use 'from iraffunctions import *'
import sys as _sys
import os as _os
import string as _string
import re as _re
import math as _math
import struct as _struct
import types as _types
import time as _time
import fnmatch as _fnmatch
import glob as _glob
import tempfile as _tempfile
import linecache as _linecache
import pickle as _pickle
import io as _io
import stsci.tools.minmatch as _minmatch
import stsci.tools.irafutils as _irafutils
import stsci.tools.teal as _teal
import numpy as _numpy
from . import subproc as _subproc
from . import wutil as _wutil
from . import irafnames as _irafnames
from . import irafinst as _irafinst
from . import irafpar as _irafpar
from . import iraftask as _iraftask
from . import irafexecute as _irafexecute
from . import cl2py as _cl2py
from . import gki
from . import irafecl
try:
    from . import sscanf
except OSError:
    # basic usage does not actually require sscanf
    sscanf = None
    print("Warning: sscanf library not installed on " + sys.platform)


# Number of bits per long
BITS_PER_LONG = _struct.calcsize('l') * 8  # is 64 on a 64-bit machine

# FP_EPSILON is the smallest number such that: 1.0 + epsilon > 1.0;  Use None
# in the finfo ctor to make it use the default precision for a Python float.
FP_EPSILON = _numpy.finfo(None).eps

# -----------------------------------------------------
# private dictionaries:
#
# _varDict: dictionary of all IRAF cl variables (defined with set name=value)
# _tasks: all IRAF tasks (defined with task name=value)
# _mmtasks: minimum-match dictionary for tasks
# _pkgs: min-match dictionary for all packages (defined with
#        task name.pkg=value)
# _loaded: loaded packages
# -----------------------------------------------------

# Will want to enhance this to allow a "bye" function that unloads packages.
# That might be done using a stack of definitions for each task.

_varDict = {}
_tasks = {}
_mmtasks = _minmatch.MinMatchDict()
_pkgs = _minmatch.MinMatchDict()
_loaded = {}

# -----------------------------------------------------
# public variables:
#
# loadedPath: list of loaded packages in order of loading
#                       Used as search path to find fully qualified task name
# -----------------------------------------------------

loadedPath = []

# cl is the cl task pointer (frequently used because cl parameters
# are always available)

cl = None

# -----------------------------------------------------
# help: implemented in irafhelp.py
# -----------------------------------------------------

from .irafhelp import help

# -----------------------------------------------------
# Init: basic initialization
# -----------------------------------------------------

# This could be executed automatically when the module first
# gets imported, but that would not allow control over output
# (which is available through the doprint and hush parameters.)


def Init(doprint=1, hush=0, savefile=None):
    """Basic initialization of IRAF environment"""
    global _pkgs, cl
    if savefile is not None:
        restoreFromFile(savefile, doprint=doprint)
        return
    if len(_pkgs) == 0:
        try:
            iraf = _os.environ['iraf']
        except KeyError:
            # iraf or IRAFARCH environment variable not defined
            # try to get them from cl startup file
            try:
                d = _getIrafEnv()
                for key, value in d.items():
                    if key not in _os.environ:
                        _os.environ[key] = value
                iraf = _os.environ['iraf']
            except OSError:
                raise OSError("""
Your "iraf" environment variable is not defined and could not be
determined from /usr/local/bin/cl.  This is are needed to find IRAF
tasks.  Before starting pyraf, define ot by doing (for example):

    export iraf=/iraf/iraf/

at the Unix command line. Actual values will depend on your IRAF installation,
and they are set during the IRAF user installation (see https://iraf-community.github.io).
Also be sure to run the "mkiraf" command to create a logion.cl
(http://www.google.com/search?q=mkiraf).
""")

        arch = _os.environ.get('IRAFARCH', '')

        # stacksize problem on linux
        # https://iraf-community.github.io/iraf-v216/issues/61
        if arch in ('redhat', 'linux', 'linuxppc', 'suse'):
            import resource
            try:
                hardlimit = resource.getrlimit(resource.RLIMIT_STACK)[1]
                resource.setrlimit(resource.RLIMIT_STACK, (hardlimit, hardlimit))
            except (ValueError, OSError):
                pass  # Ignore the error and hope the best...

        # ensure trailing slash is present
        iraf = _os.path.join(iraf, '')
        host = _os.environ.get('host', _os.path.join(iraf, 'unix', ''))
        hlib = _os.environ.get('hlib', _os.path.join(host, 'hlib', ''))
        tmp = _os.environ.get('tmp', '/tmp/')
        set(iraf=iraf)
        set(host=host)
        set(hlib=hlib)
        set(tmp=tmp)
        if arch and arch[0] != '.':
            arch = '.' + arch
        set(arch=arch)
        global userIrafHome
        set(home=userIrafHome)

        # define initial symbols
        if _irafinst.EXISTS:
            clProcedure(Stdin='hlib$zzsetenv.def')

        # define clpackage
        global clpkg
        clpkg = IrafTaskFactory('', 'clpackage', '.pkg', 'hlib$clpackage.cl',
                                'clpackage', 'bin$')

        # add the cl as a task, because its parameters are sometimes needed,
        # but make it a hidden task
        # cl is implemented as a Python task
        cl = IrafTaskFactory('',
                             'cl',
                             '',
                             'cl$cl.par',
                             'clpackage',
                             'bin$',
                             function=_clProcedure)
        cl.setHidden()

        # load clpackage
        clpkg.run(_doprint=0, _hush=hush, _save=1)

        if access('login.cl'):
            fname = _os.path.abspath('login.cl')
        elif access('home$login.cl'):
            fname = 'home$login.cl'
        elif access(_os.path.expanduser('~/.iraf/login.cl')):
            fname = _os.path.expanduser('~/.iraf/login.cl')
        elif access('/etc/iraf/login.cl'):
            fname = '/etc/iraf/login.cl'
        elif not _irafinst.EXISTS:
            fname = _irafinst.getNoIrafClFor('login.cl', useTmpFile=True)
        else:
            fname = None

        if fname:
            # define and load user package
            userpkg = IrafTaskFactory('', 'user', '.pkg', fname, 'clpackage',
                                      'bin$')
            userpkg.run(_doprint=0, _hush=hush, _save=1)
        else:
            _writeError("Warning: no login.cl found")

        # make clpackage the current package
        loadedPath.append(clpkg)
        if doprint:
            listTasks('clpackage')


def _getIrafEnv(file='/usr/local/bin/cl', vars=('IRAFARCH', 'iraf')):
    """Returns dictionary of environment vars defined in cl startup file"""
    if not _irafinst.EXISTS:
        return {'iraf': '/iraf/is/not/here/', 'IRAFARCH': 'arch_is_unused'}
    if not _os.path.exists(file):
        raise OSError(f"CL startup file {file} does not exist")
    lines = open(file).readlines()
    # replace commands that exec cl with commands to print environment vars
    pat = _re.compile(r'^\s*exec\s+')
    newlines = []
    nfound = 0
    for line in lines:
        if pat.match(line):
            nfound += 1
            for var in vars:
                newlines.append(f'echo "{var}=${var}"\n')
            newlines.append('exit 0\n')
        else:
            newlines.append(line)
    if nfound == 0:
        raise OSError(f"No exec statement found in script {file}")
    # write new script to temporary file
    (fd, newfile) = _tempfile.mkstemp()
    _os.close(fd)
    f = open(newfile, 'w')
    f.writelines(newlines)
    f.close()
    _os.chmod(newfile, 0o700)
    # run new script and capture output
    fh = _io.StringIO()
    status = clOscmd(newfile, Stdout=fh)
    if status:
        raise OSError(f"Execution error in script {newfile} (derived from {file})")
    _os.remove(newfile)
    result = fh.getvalue().split('\n')
    fh.close()
    # extract environment variables from the output
    d = {}
    for entry in result:
        if entry.find('=') >= 0:
            key, value = entry.split('=', 1)
            d[key] = value
    return d


# module variables that don't get saved (they get
# initialized when this module is imported)

unsavedVars = [
    'BITS_PER_LONG',
    'EOF',
    'FP_EPSILON',
    'IrafError',
    'SubprocessError',
    '_NullFileList',
    '_NullPath',
    '__builtins__',
    '__doc__',
    '__package__',
    '__file__',
    '__name__',
    '__re_var_match',
    '__re_var_paren',
    '_badFormats',
    '_backDir',
    '_clearString',
    '_denode_pat',
    '_exitCommands',
    '_nscan',
    '_fDispatch',
    '_radixDigits',
    '_re_taskname',
    '_reFormat',
    '_sttyArgs',
    '_tmpfileCounter',
    '_clExecuteCount',
    '_unsavedVarsDict',
    'IrafTask',
    'IrafPkg',
    'cl',
    'division',
    'epsilon',
    'iraf',
    'no',
    'yes',
    'userWorkingHome',
]
_unsavedVarsDict = {}
for v in unsavedVars:
    _unsavedVarsDict[v] = 1
del unsavedVars, v

# there are a few tricky things here:
#
# - I restore userIrafHome, which therefore can be inconsistent with
#   with the IRAF environment variable.
#
# - I do not restore userWorkingHome, so it always tells where the
#   user actually started this pyraf session.  Is that the right thing
#   to do?
#
# - I am restoring the INDEF object, which means that there could be
#   multiple versions of this supposed singleton floating around.
#   I changed the __cmp__ method for INDEF so it produces 'equal'
#   if the two objects are both INDEFs -- I hope that will take care
#   of any possible problems.


def saveToFile(savefile, **kw):
    """Save IRAF environment to pickle file

    savefile may be a filename or a file handle.
    Set clobber keyword (or CL environment variable) to overwrite an
    existing file.
    """
    if hasattr(savefile, 'write'):
        fh = savefile

        if hasattr(savefile, 'name'):
            savefile = fh.name
        doclose = 0
    else:
        # if clobber is not set, do not overwrite file
        savefile = Expand(savefile)
        if (not kw.get('clobber')) and envget(
                "clobber", "") != yes and _os.path.exists(savefile):
            raise OSError(f"Output file `{savefile}' already exists")
        # open binary pickle file
        fh = open(savefile, 'wb')
        doclose = 1
    # make a shallow copy of the dictionary and edit out
    # functions, modules, and objects named in _unsavedVarsDict
    gdict = globals().copy()
    for key in gdict.keys():
        item = gdict[key]
        if isinstance(item, (_types.FunctionType, _types.ModuleType)) or \
                key in _unsavedVarsDict:
            del gdict[key]


#   print('\n\n\n',gdict.keys()) # DBG: debug line
# save just the value of Verbose, not the object
    global Verbose
    gdict['Verbose'] = Verbose.get()
    p = _pickle.Pickler(fh, 1)
    p.dump(gdict)
    if doclose:
        fh.close()


def restoreFromFile(savefile, doprint=1, **kw):
    """Initialize IRAF environment from pickled save file (or file handle)"""
    if hasattr(savefile, 'read'):
        fh = savefile
        if hasattr(savefile, 'name'):
            savefile = fh.name
        doclose = 0
    else:
        savefile = Expand(savefile)
        fh = open(savefile, 'rb')
        doclose = 1
    u = _pickle.Unpickler(fh)
    udict = u.load()
    if doclose:
        fh.close()

    # restore the value of Verbose

    global Verbose
    Verbose.set(udict['Verbose'])
    del udict['Verbose']

    # replace the contents of loadedPath
    global loadedPath
    loadedPath[:] = udict['loadedPath']
    del udict['loadedPath']

    # update the values
    globals().update(udict)

    # replace INDEF everywhere we can find it
    # this does not replace references in parameters, unfortunately
    INDEF = udict['INDEF']
    from stsci.tools import irafglobals
    import __main__
    import pyraf
    from . import irafpar
    from . import cltoken
    for module in (__main__, pyraf, irafpar, irafglobals, cltoken):
        if hasattr(module, 'INDEF'):
            module.INDEF = INDEF

    # replace cl in the iraf module (and possibly other locations)
    global cl
    _addTask(cl)

    if doprint:
        listCurrent()


# -----------------------------------------------------
# _addPkg: Add an IRAF package to the pkgs list
# -----------------------------------------------------


def _addPkg(pkg):
    """Add an IRAF package to the packages list"""
    global _pkgs
    name = pkg.getName()
    _pkgs.add(name, pkg)
    # add package to global namespaces
    _irafnames.strategy.addPkg(pkg)
    # packages are tasks too, so add to task lists
    _addTask(pkg)


# -----------------------------------------------------
# _addTask: Add an IRAF task to the tasks list
# -----------------------------------------------------


def _addTask(task, pkgname=None):
    """Add an IRAF task to the tasks list"""
    global _tasks, _mmtasks
    name = task.getName()
    if not pkgname:
        pkgname = task.getPkgname()
    fullname = pkgname + '.' + name
    _tasks[fullname] = task
    _mmtasks.add(name, fullname)
    # add task to global namespaces
    _irafnames.strategy.addTask(task)
    # add task to list for its package
    getPkg(pkgname).addTask(task, fullname)


# --------------------------------------------------------------------------
# Use decorators to consolidate repeated code used in command-line functions.
# (09/2009)
# These decorator functions are not the simplest form in that they each also
# define a function (the actual wrapper) and return that function.  This
# is needed to get to both the before and after parts of the target.  This
# approach was performance tested to ensure that PyRAF functionality would
# not suffer for the sake of code maintainability.  The results showed (under
# Python 2.4/.5/.6) that performance can be degraded (by 65%) for only the very
# simplest target function (e.g. "pass"), but that for functions which take
# any amount of time to do their work (e.g. taking 0.001 sec), the performance
# degradation is effectively unmeasurable.  This same approach can be done
# with a decorator class instead of a decorator function, but the performance
# degradation is always greater by a factor of at least 3.
#
# These decorators could all be combined into a single function with arguments
# deciding their different capabilities, but that would add another level (i.e.
# a function within a function within a function) and for the sake of simplicity
# and robustness as we move into PY3K, we'll write them out separately for now.
# --------------------------------------------------------------------------


def handleRedirAndSaveKwds(target):
    """ This decorator is used to consolidate repeated code used in
        command-line functions, concerning standard pipe redirection.
        Typical 'target' functions will: take 0 or more positional arguments,
        take NO keyword args (except redir's &  _save), and return nothing.
    """

    # create the wrapper function here which handles the redirect keywords,
    # and return it so it can replace 'target'
    def wrapper(*args, **kw):
        # handle redirection and save keywords
        redirKW, closeFHList = redirProcess(kw)
        if '_save' in kw:
            del kw['_save']
        if len(kw):
            raise TypeError('unexpected keyword argument: ' +
                            repr(list(kw.keys())))
        resetList = redirApply(redirKW)
        try:
            # call 'target' to do the interesting work of this function
            target(*args)
        finally:
            rv = redirReset(resetList, closeFHList)
        return rv

    # return wrapper so it can replace 'target'
    return wrapper


def handleRedirAndSaveKwdsPlus(target):
    """ This decorator is used to consolidate repeated code used in
        command-line functions, concerning standard pipe redirection.
        Typical 'target' functions will: take 0 or more positional arguments,
        take AT LEAST ONE keyword arg (not including redir's &  _save), and
        return nothing.
    """

    # create the wrapper function here which handles the redirect keywords,
    # and return it so it can replace 'target'
    def wrapper(*args, **kw):
        # handle redirection and save keywords
        redirKW, closeFHList = redirProcess(kw)
        if '_save' in kw:
            del kw['_save']
        # the missing check here on len(kw) is the main difference between
        # this and handleRedirAndSaveKwds (also the sig. of target())
        resetList = redirApply(redirKW)
        try:
            # call 'target' to do the interesting work of this function
            target(*args, **kw)
        finally:
            rv = redirReset(resetList, closeFHList)
        return rv

    # return wrapper so it can replace 'target'
    return wrapper


# -----------------------------------------------------
# addLoaded: Add an IRAF package to the loaded pkgs list
# -----------------------------------------------------

# This is public because Iraf Packages call it to register
# themselves when they are loaded.


def addLoaded(pkg):
    """Add an IRAF package to the loaded pkgs list"""
    global _loaded
    _loaded[pkg.getName()] = len(_loaded)


# -----------------------------------------------------
# load: Load an IRAF package by name
# -----------------------------------------------------


def load(pkgname, args=(), kw=None, doprint=1, hush=0, save=1):
    """Load an IRAF package by name"""
    if isinstance(pkgname, _iraftask.IrafPkg):
        p = pkgname
    else:
        p = getPkg(pkgname)
    if kw is None:
        kw = {}
    if '_doprint' not in kw:
        kw['_doprint'] = doprint
    if '_hush' not in kw:
        kw['_hush'] = hush
    if '_save' not in kw:
        kw['_save'] = save
    p.run(*tuple(args), **kw)


# -----------------------------------------------------
# run: Run an IRAF task by name
# -----------------------------------------------------


def run(taskname, args=(), kw=None, save=1):
    """Run an IRAF task by name"""
    if isinstance(taskname, _iraftask.IrafTask):
        t = taskname
    else:
        t = getTask(taskname)
    if kw is None:
        kw = {}
    if '_save' not in kw:
        kw['_save'] = save
    #  if '_parent' not in kw:
    #      kw['parent'] = "'iraf.cl'"
    t.run(*tuple(args), **kw)


# -----------------------------------------------------
# getAllTasks: Get list of all IRAF tasks that match partial name
# -----------------------------------------------------


def getAllTasks(taskname):
    """Returns list of names of all IRAF tasks that may match taskname"""
    return _mmtasks.getallkeys(taskname, [])


# -----------------------------------------------------
# getAllPkgs: Get list of all IRAF pkgs that match partial name
# -----------------------------------------------------


def getAllPkgs(pkgname):
    """Returns list of names of all IRAF pkgs that may match pkgname"""
    return _pkgs.getallkeys(pkgname, [])


# -----------------------------------------------------
# getTask: Find an IRAF task by name
# -----------------------------------------------------
def getTask(taskname, found=0):
    """Find an IRAF task by name using minimum match

    Returns an IrafTask object.  Name may be either fully qualified
    (package.taskname) or just the taskname.  taskname is also allowed
    to be an IrafTask object, in which case it is simply returned.
    Does minimum match to allow abbreviated names.  If found is set,
    returns None when task is not found; default is to raise exception
    if task is not found.
    """

    if isinstance(taskname, _iraftask.IrafTask):
        return taskname
    elif not isinstance(taskname, str):
        raise TypeError(
            "Argument to getTask is not a string or IrafTask instance")

    # undo any modifications to the taskname
    taskname = _irafutils.untranslateName(taskname)

    # Try assuming fully qualified name first
    task = _tasks.get(taskname)
    if task is not None:
        if Verbose > 1:
            print('found', taskname, 'in task list')
        return task

    # Look it up in the minimum-match dictionary
    # Note _mmtasks.getall returns list of full names of all matching tasks
    fullname = _mmtasks.getall(taskname)
    if not fullname:
        if found:
            return None
        else:
            raise KeyError("Task " + taskname + " is not defined")

    if len(fullname) == 1:
        # unambiguous match
        task = _tasks[fullname[0]]
        if Verbose > 1:
            print('found', task.getName(), 'in task list')
        return task

    # Ambiguous match is OK only if taskname is the full name
    # or if all matched tasks have the same task name.  For example,
    # (1) 'mem' matches package 'mem0' and task 'restore.mem' -- return
    #     'restore.mem'.
    # (2) 'imcal' matches tasks named 'imcalc' in several different
    #     packages -- return the most recently loaded version.
    # (3) 'imcal' matches several 'imcalc's and also 'imcalculate'.
    #     That is an error.

    # look for exact matches, <pkg>.<taskname>
    trylist = []
    pkglist = []
    for name in fullname:
        sp = name.split('.')
        if sp[-1] == taskname:
            trylist.append(name)
            pkglist.append(sp[0])
    # return a single exact match
    if len(trylist) == 1:
        return _tasks[trylist[0]]

    if not trylist:
        # no exact matches, see if all tasks have same name
        sp = fullname[0].split('.')
        name = sp[-1]
        pkglist = [sp[0]]
        for i in range(len(fullname) - 1):
            sp = fullname[i + 1].split('.')
            if name != sp[-1]:
                if len(fullname) > 3:
                    fullname[3:] = ['...']
                if found:
                    return None
                else:
                    raise _minmatch.AmbiguousKeyError(
                        f"Task `{taskname}' is ambiguous, "
                        f"could be {', '.join(fullname)}")
            pkglist.append(sp[0])
        trylist = fullname

    # trylist has a list of several candidate tasks that differ
    # only in package.  Search loaded packages in reverse to find
    # which one was loaded most recently.
    for i in range(len(loadedPath)):
        pkg = loadedPath[-1 - i].getName()
        if pkg in pkglist:
            # Got it at last
            j = pkglist.index(pkg)
            return _tasks[trylist[j]]
    # None of the packages are loaded?  This presumably cannot happen
    # now, but could happen if package unloading is implemented.
    if found:
        return None
    else:
        raise KeyError("Task " + taskname + " is not in a loaded package")


# -----------------------------------------------------
# getPkg: Find an IRAF package by name
# -----------------------------------------------------


def getPkg(pkgname, found=0):
    """Find an IRAF package by name using minimum match

    Returns an IrafPkg object.  pkgname is also allowed
    to be an IrafPkg object, in which case it is simply
    returned.  If found is set, returns None when package
    is not found; default is to raise exception if package
    is not found.
    """
    try:
        if isinstance(pkgname, _iraftask.IrafPkg):
            return pkgname
        if not pkgname:
            raise TypeError(f"Bad package name `{repr(pkgname)}'")
        # undo any modifications to the pkgname
        pkgname = _irafutils.untranslateName(pkgname)
        return _pkgs[pkgname]
    except _minmatch.AmbiguousKeyError as e:
        # re-raise the error with a bit more info
        raise e.__class__("Package " + pkgname + ": " + str(e))
    except KeyError:
        if found:
            return None
        raise KeyError(f"Package `{pkgname}' not found")


# -----------------------------------------------------
# Miscellaneous access routines:
# getTaskList: Get list of names of all defined IRAF tasks
# getPkgList: Get list of names of all defined IRAF packages
# getLoadedList: Get list of names of all loaded IRAF packages
# getVarList: Get list of names of all defined IRAF variables
# -----------------------------------------------------


def getTaskList():
    """Returns list of names of all defined IRAF tasks"""
    return list(_tasks.keys())


def getTaskObjects():
    """Returns list of all defined IrafTask objects"""
    return list(_tasks.values())


def getPkgList():
    """Returns list of names of all defined IRAF packages"""
    return list(_pkgs.keys())


def getLoadedList():
    """Returns list of names of all loaded IRAF packages"""
    return list(_loaded.keys())


def getVarDict():
    """Returns dictionary all IRAF variables"""
    return _varDict


def getVarList():
    """Returns list of names of all IRAF variables"""
    return list(_varDict.keys())


# -----------------------------------------------------
# listAll, listPkg, listLoaded, listTasks, listCurrent, listVars:
# list contents of the dictionaries
# -----------------------------------------------------


@handleRedirAndSaveKwds
def listAll(hidden=0):
    """List IRAF packages, tasks, and variables"""
    print('Packages:')
    listPkgs()
    print('Loaded Packages:')
    listLoaded()
    print('Tasks:')
    listTasks(hidden=hidden)
    print('Variables:')
    listVars()


@handleRedirAndSaveKwds
def listPkgs():
    """List IRAF packages"""
    keylist = getPkgList()
    if len(keylist) == 0:
        print('No IRAF packages defined')
    else:
        keylist.sort()
        # append '/' to identify packages
        for i in range(len(keylist)):
            keylist[i] = keylist[i] + '/'
        _irafutils.printCols(keylist)


@handleRedirAndSaveKwds
def listLoaded():
    """List loaded IRAF packages"""
    keylist = getLoadedList()
    if len(keylist) == 0:
        print('No IRAF packages loaded')
    else:
        keylist.sort()
        # append '/' to identify packages
        for i in range(len(keylist)):
            keylist[i] = keylist[i] + '/'
        _irafutils.printCols(keylist)


@handleRedirAndSaveKwdsPlus
def listTasks(pkglist=None, hidden=0, **kw):
    """List IRAF tasks, optionally specifying a list of packages to include

    Package(s) may be specified by name or by IrafPkg objects.
    """
    keylist = getTaskList()
    if len(keylist) == 0:
        print('No IRAF tasks defined')
        return
    # make a dictionary of pkgs to list
    if pkglist is None:
        pkgdict = _pkgs
    else:
        pkgdict = {}
        if isinstance(pkglist, (str, _iraftask.IrafPkg)):
            pkglist = [pkglist]
        for p in pkglist:
            try:
                pthis = getPkg(p)
                if pthis.isLoaded():
                    pkgdict[pthis.getName()] = 1
                else:
                    _writeError(f'Package {pthis.getName()}'
                                ' has not been loaded')
            except KeyError as e:
                _writeError(str(e))
    if not len(pkgdict):
        print('No packages to list')
        return

    # print each package separately
    keylist.sort()
    lastpkg = ''
    tlist = []
    for tname in keylist:
        pkg, task = tname.split('.')
        tobj = _tasks[tname]
        if hidden or not tobj.isHidden():
            if isinstance(tobj, _iraftask.IrafPkg):
                task = task + '/'
            elif isinstance(tobj, _iraftask.IrafPset):
                task = task + '@'
            if pkg == lastpkg:
                tlist.append(task)
            else:
                if len(tlist) and lastpkg in pkgdict:
                    print(lastpkg + '/:')
                    _irafutils.printCols(tlist)
                tlist = [task]
                lastpkg = pkg
    if len(tlist) and lastpkg in pkgdict:
        print(lastpkg + '/:')
        _irafutils.printCols(tlist)


@handleRedirAndSaveKwds
def listCurrent(n=1, hidden=0):
    """List IRAF tasks in current package (equivalent to '?' in the cl)
    If parameter n is specified, lists n most recent packages."""
    if len(loadedPath):
        if n > len(loadedPath):
            n = len(loadedPath)
        plist = n * [None]
        for i in range(n):
            plist[i] = loadedPath[-1 - i].getName()
        listTasks(plist, hidden=hidden)
    else:
        print('No IRAF tasks defined')


@handleRedirAndSaveKwdsPlus
def listVars(prefix="", equals="\t= "):
    """List IRAF variables"""
    keylist = getVarList()
    if len(keylist) == 0:
        print('No IRAF variables defined')
    else:
        keylist.sort()
        for word in keylist:
            print(f"{prefix}{word}{equals}{envget(word)}")


@handleRedirAndSaveKwds
def gripes():
    """ Hide the system call """
    print("No gripes")


gripe = gripes


@handleRedirAndSaveKwds
def which(*args):
    """ Emulate the which function in IRAF. """
    for arg in args:
        try:
            print(getTask(arg).getPkgname())
            # or: getTask(arg).getPkgname()+"."+getTask(arg).getName()
        except _minmatch.AmbiguousKeyError as e:
            print(str(e))
        except (KeyError, TypeError):
            if deftask(arg):
                print('language')  # handle, e.g. 'which which', 'which cd'
            else:
                _writeError(arg + ": task not found.")


@handleRedirAndSaveKwds
def whereis(*args):
    """ Emulate the whereis function in IRAF. """
    for arg in args:
        matches = _mmtasks.getall(arg)
        if matches:
            matches.reverse()  # this reverse isn't necessary - they arrive
            # in the right order, but CL seems to do this
            print(" ".join(matches))
        else:
            _writeError(arg + ": task not found.")


@handleRedirAndSaveKwds
def taskinfo(*args):
    '''
    show information about task definitions

    taskinfo [ pattern(s) ]

        pattern is a glob pattern describing the package or task
        name that you are interested in.

        The output is a hierarchical view of the task definitions
        that match the input pattern.  Each line shows the task
        name, the file name, pkgbinary and class.

        pkgbinary is a list of where you look for the file if it
        is not where you expect.

        class is the type of task definition from iraftask.py

        At this point, this is not exactly friendly for an end-user,
        but an SE could use it or ask the user to run it and send in
        the output.
    '''

    for x in args:
        _iraftask.showtasklong(x)


# -----------------------------------------------------
# IRAF utility functions
# -----------------------------------------------------

# these do not have extra keywords because they should not
# be called as tasks


def clParGet(paramname, pkg=None, native=1, mode=None, prompt=1):
    """Return value of IRAF parameter

    Parameter can be a cl task parameter, a package parameter for
    any loaded package, or a fully qualified (task.param) parameter
    from any known task.
    """
    if pkg is None:
        pkg = loadedPath[-1]
    # if taskname is '_', use current package as task
    if paramname[:2] == "_.":
        paramname = pkg.getName() + paramname[1:]
    return pkg.getParam(paramname, native=native, mode=mode, prompt=prompt)


def envget(var, default=None):
    """Get value of IRAF or OS environment variable"""
    try:
        return _varDict[var]
    except KeyError:
        try:
            return _os.environ[var]
        except KeyError:
            if default is not None:
                return default
            elif var == 'TERM':
                # Return a default value for TERM
                # TERM gets caught as it is found in the default
                # login.cl file setup by IRAF.
                print("Using default TERM value for session.")
                return 'xterm'
            else:
                raise KeyError(f"Undefined environment variable `{var}'")


_tmpfileCounter = 0


def mktemp(root):
    """Make a temporary filename starting with root"""
    global _tmpfileCounter
    basename = root + repr(_os.getpid())
    while True:
        _tmpfileCounter = _tmpfileCounter + 1
        if _tmpfileCounter <= 26:
            # use letters to start
            suffix = chr(ord("a") + _tmpfileCounter - 1)
        else:
            # use numbers once we've used up letters
            suffix = "_" + repr(_tmpfileCounter - 26)
        file = basename + suffix
        if not _os.path.exists(Expand(file)):
            return file


_NullFileList = ["dev$null", "/dev/null"]
_NullPath = None


def isNullFile(s):
    """Returns true if this is the CL null file"""
    global _NullFileList, _NullPath
    if s in _NullFileList:
        return 1
    sPath = Expand(s)
    if _NullPath is None:
        _NullPath = Expand(_NullFileList[0])
        _NullFileList.append(_NullPath)
    if sPath == _NullPath:
        return 1
    else:
        return 0


def substr(s, first, last):
    """Return sub-string using IRAF 1-based indexing"""
    if s == INDEF:
        return INDEF
    # If the first index is zero, always return a zero-length string
    if first == 0:
        return ''
    return s[first - 1:last]


def strlen(s):
    """Return length of string"""
    if s == INDEF:
        return INDEF
    return len(s)


def isindef(s):
    """Returns true if argument is INDEF"""
    if s == INDEF:
        return 1
    else:
        return 0


def stridx(test, s):
    """Return index of first occurrence of any of the characters in 'test'
    that are in 's' using IRAF 1-based indexing"""
    if INDEF in (s, test):
        return INDEF
    _pos2 = len(s)
    for _char in test:
        _pos = s.find(_char)
        if _pos != -1:
            _pos2 = min(_pos2, _pos)
    if _pos2 == len(s):
        return 0
    else:
        return _pos2 + 1


def strldx(test, s):
    """Return index of last occurrence of any of the characters in 'test'
    that are in 's' using IRAF 1-based indexing"""
    if INDEF in (s, test):
        return INDEF
    _pos2 = -1
    for _char in test:
        _pos = s.rfind(_char)
        if _pos != -1:
            _pos2 = max(_pos2, _pos)
    return _pos2 + 1


def strlwr(s):
    """Return string converted to lower case"""
    if s == INDEF:
        return INDEF
    return s.lower()


def strupr(s):
    """Return string converted to upper case"""
    if s == INDEF:
        return INDEF
    return s.upper()


def strstr(str1, str2):
    """Search for first occurrence of 'str1' in 'str2', returns index
    of the start of 'str1' or zero if not found.  IRAF 1-based indexing"""
    if INDEF in (str1, str2):
        return INDEF
    return str2.find(str1) + 1


def strlstr(str1, str2):
    """Search for last occurrence of 'str1' in 'str2', returns index
    of the start of 'str1' or zero if not found.  IRAF 1-based indexing"""
    if INDEF in (str1, str2):
        return INDEF
    return str2.rfind(str1) + 1


def trim(str, trimchars=None):
    """Trim any of the chars in 'trimchars' (default = whitesspace) from
    both ends of 'str'."""
    if INDEF in (str, trimchars):
        return INDEF
    return str.strip(trimchars)


def triml(str, trimchars=None):
    """Trim any of the chars in 'trimchars' (default = whitesspace) from
    the left side of 'str'."""
    if INDEF in (str, trimchars):
        return INDEF
    return str.lstrip(trimchars)


def trimr(str, trimchars=None):
    """Trim any of the chars in 'trimchars' (default = whitesspace) from
    the right side of 'str'."""
    if INDEF in (str, trimchars):
        return INDEF
    return str.rstrip(trimchars)


def frac(x):
    """Return fractional part of x"""
    if x == INDEF:
        return INDEF
    frac_part, int_part = _math.modf(x)
    return frac_part


def real(x):
    """Return real/float representation of x"""
    if x == INDEF:
        return INDEF
    elif isinstance(x, str):
        x = x.strip()
        if x.find(':') >= 0:
            # ...handle the special a:b:c case here...
            sign = 1
            if x[0] in ["-", "+"]:
                if x[0] == "-":
                    sign = -1.
                x = x[1:]
            m = _re.search(r"[^0-9:.]", x)
            if m:
                x = x[0:m.start()]
            f = map(float, x.split(":"))
            f = list(map(abs, f))
            return sign * clSexagesimal(*f)
        else:
            x = _re.sub("[EdD]", "e", x, count=1)
            m = _re.search(r"[^0-9.e+-]", x)
            if m:
                x = x[0:m.start()]
            return float(x)
    else:
        return float(x)


def integer(x):
    """Return integer representation of x"""
    if x == INDEF:
        return INDEF
    elif isinstance(x, str):
        x = x.strip()
        i = 0
        j = len(x)
        if x[0] in ["+", "-"]:
            i = 1
        x = _re.sub("[EdD]", "e", x, count=1)
        m = _re.search(r"[^0-9.e+-]", x[i:])
        if m:
            j = i + m.start()
        return int(float(x[:j]))
    else:
        return int(x)


def mod(a, b):
    """Return a modulo b"""
    if INDEF in (a, b):
        return INDEF
    return (a % b)


def nint(x):
    """Return nearest integer of x"""
    if x == INDEF:
        return INDEF
    return int(round(x))


_radixDigits = list(_string.digits + _string.ascii_uppercase)


def radix(value, base=10, length=0):
    """Convert integer value to string expressed using given base

    If length is given, field is padded with leading zeros to reach length.
    Note that if value is negative, this routine returns the actual
    bit-pattern of the twos-complement integer (even for base 10) rather
    than a signed value.  This is consistent with IRAF's behavior.
    """
    if INDEF in (value, base, length):
        return INDEF
    if not (2 <= base <= 36):
        raise ValueError("base must be between 2 and 36 (inclusive)")
    ivalue = int(value)
    if ivalue == 0:
        # handle specially so don't have to worry about it below
        return f'{ivalue:0{length:d}d}'
    # convert to an unsigned long integer
    hexIvalue = hex(ivalue)  # hex() can return a string for an int or a long
    isLong = hexIvalue[-1] == 'L'
    if not isLong:
        hexIvalue += 'L'
    lvalue = eval(hexIvalue)
    outdigits = []
    while lvalue > 0 or lvalue < -1:
        lvalue, digit = divmod(lvalue, base)
        outdigits.append(int(digit))
    outdigits = [_radixDigits[index] for index in outdigits]
    # zero-pad if needed (automatically do so for negative numbers)
    if ivalue < 0:
        maxlen = 32
        if isLong:
            maxlen = BITS_PER_LONG
        outdigits.extend((maxlen - len(outdigits)) * ["1"])
    if length > len(outdigits):
        outdigits.extend((length - len(outdigits)) * ["0"])
    outdigits.reverse()
    return ''.join(outdigits)


def rad(value):
    """Convert arg in degrees to radians"""
    if value == INDEF:
        return INDEF
    else:
        return _math.radians(value)


def deg(value):
    """Convert arg in radians to degrees"""
    if value == INDEF:
        return INDEF
    else:
        return _math.degrees(value)


def sin(value):
    """Trigonometric sine function.  Input in radians."""
    if value == INDEF:
        return INDEF
    else:
        return _math.sin(value)


def asin(value):
    """Trigonometric arc sine function.  Result in radians."""
    if value == INDEF:
        return INDEF
    else:
        return _math.asin(value)


def cos(value):
    """Trigonometric cosine function.  Input in radians."""
    if value == INDEF:
        return INDEF
    else:
        return _math.cos(value)


def acos(value):
    """Trigonometric arc cosine function.  Result in radians."""
    if value == INDEF:
        return INDEF
    else:
        return _math.acos(value)


def tan(value):
    """Trigonometric tangent function.  Input in radians."""
    if value == INDEF:
        return INDEF
    else:
        return _math.tan(value)


def atan2(x, y):
    """Trigonometric 2-argument arctangent function.  Result in radians."""
    if INDEF in (x, y):
        return INDEF
    else:
        return _math.atan2(x, y)


def dsin(value):
    """Trigonometric sine function.  Input in degrees."""
    if value == INDEF:
        return INDEF
    else:
        return _math.sin(_math.radians(value))


def dasin(value):
    """Trigonometric arc sine function.  Result in degrees."""
    if value == INDEF:
        return INDEF
    else:
        return _math.degrees(_math.asin(value))


def dcos(value):
    """Trigonometric cosine function.  Input in degrees."""
    if value == INDEF:
        return INDEF
    else:
        return _math.cos(_math.radians(value))


def dacos(value):
    """Trigonometric arc cosine function.  Result in degrees."""
    if value == INDEF:
        return INDEF
    else:
        return _math.degrees(_math.acos(value))


def dtan(value):
    """Trigonometric tangent function.  Input in degrees."""
    if value == INDEF:
        return INDEF
    else:
        return _math.tan(_math.radians(value))


def datan2(x, y):
    """Trigonometric 2-argument arctangent function.  Result in degrees."""
    if INDEF in (x, y):
        return INDEF
    else:
        return _math.degrees(_math.atan2(x, y))


def exp(value):
    """Exponential function"""
    if value == INDEF:
        return INDEF
    else:
        return _math.exp(value)


def log(value):
    """Natural log function"""
    if value == INDEF:
        return INDEF
    else:
        return _math.log(value)


def log10(value):
    """Base 10 log function"""
    if value == INDEF:
        return INDEF
    else:
        return _math.log10(value)


def sqrt(value):
    """Square root function"""
    if value == INDEF:
        return INDEF
    else:
        return _math.sqrt(value)


def absvalue(value):
    """Absolute value function"""
    if value == INDEF:
        return INDEF
    else:
        return abs(value)


def minimum(*args):
    """Minimum of list of arguments"""
    if INDEF in args:
        return INDEF
    else:
        return min(*args)


def maximum(*args):
    """Maximum of list of arguments"""
    if INDEF in args:
        return INDEF
    else:
        return max(*args)


def hypot(x, y):
    """Return the Euclidean distance, sqrt(x*x + y*y)."""
    if INDEF in (x, y):
        return INDEF
    else:
        return _math.hypot(x, y)


def sign(value):
    """Sign of argument (-1 or 1)"""
    if value == INDEF:
        return INDEF
    if value >= 0.0:
        return 1
    else:
        return -1


def clNot(value):
    """Bitwise boolean NOT of an integer"""
    if value == INDEF:
        return INDEF
    return ~(int(value))


def clAnd(x, y):
    """Bitwise boolean AND of two integers"""
    if INDEF in (x, y):
        return INDEF
    return x & y


def clOr(x, y):
    """Bitwise boolean OR of two integers"""
    if INDEF in (x, y):
        return INDEF
    return x | y


def clXor(x, y):
    """Bitwise eXclusive OR of two integers"""
    if INDEF in (x, y):
        return INDEF
    return x ^ y


def osfn(filename):
    """Convert IRAF virtual path name to OS pathname"""

    # Try to emulate the CL version closely:
    #
    # - expands IRAF virtual file names
    # - strips blanks around path components
    # - if no slashes or relative paths, return relative pathname
    # - otherwise return absolute pathname

    if filename == INDEF:
        return INDEF
    ename = Expand(filename)
    dlist = [s.strip() for s in ename.split(_os.sep)]
    if len(dlist) == 1 and dlist[0] not in [_os.curdir, _os.pardir]:
        return dlist[0]

    # I use string.join instead of os.path.join here because
    # os.path.join("","") returns "" instead of "/"

    epath = _os.sep.join(dlist)
    fname = _os.path.abspath(epath)
    # append '/' if relative directory was at end or filename ends with '/'
    if fname[-1] != _os.sep and dlist[-1] in ['', _os.curdir, _os.pardir]:
        fname = fname + _os.sep
    return fname


def clSexagesimal(d, m, s=0):
    """Convert d:m:s value to float"""
    return (d + (m + s / 60.0) / 60.0)


def clDms(x, digits=1, seconds=1):
    """Convert float to d:m:s.s

    Number of decimal places on seconds is set by digits.
    If seconds is false, prints just d:m.m (omits seconds).
    """
    if x < 0:
        sign = '-'
        x = -x
    else:
        sign = ''
    if seconds:
        d = int(x)
        x = 60 * (x - d)
    m = int(x)
    s = 60 * (x - m)
    # round to avoid printing (e.g.) 60.0 seconds
    digits = max(digits, 0)
    if s + 0.5 / 10**digits >= 60:
        s = 0.0
        m = m + 1
        if seconds and m == 60:
            m = 0
            d = d + 1
    if digits == 0:
        secform = "%02d"
    else:
        secform = "%%0%d.%df" % (digits + 3, digits)
    if seconds:
        return ("%s%2d:%02d:" + secform) % (sign, d, m, s)
    else:
        return ("%s%02d:" + secform) % (sign, m, s)


def defpar(paramname):
    """Returns true if parameter is defined"""
    if paramname == INDEF:
        return INDEF
    try:
        clParGet(paramname, prompt=0)
        return 1
    except IrafError:
        # treat all errors (including ambiguous task and parameter names)
        # as a missing parameter
        return 0


def access(filename):
    """Returns true if file exists"""
    if filename == INDEF:
        return INDEF
    filename = _denode(filename)
    # Magic values that trigger special behavior
    magicValues = {"STDIN": 1, "STDOUT": 1, "STDERR": 1}
    return filename in magicValues or _os.path.exists(Expand(filename))


def fp_equal(x, y):
    """Floating point compare  to within machine precision. This logic is
       taken directly from IRAF's fp_equald function."""
    # Check the easy answers first
    if INDEF in (x, y):
        return INDEF
    if x == y:
        return True

    # We can't normalize zero, so handle the zero operand cases first.
    # Note that the case where 0 equals 0 is handled above.
    if x == 0.0 or y == 0.0:
        return False

    # Now normalize the operands and do an epsilon comparison
    normx, ex = _fp_norm(x)
    normy, ey = _fp_norm(y)

    # Here is an easy false check
    if ex != ey:
        return False

    # Finally compare the values
    x1 = 1.0 + abs(normx - normy)
    x2 = 1.0 + (32.0 * FP_EPSILON)
    return x1 <= x2


def _fp_norm(x):
    """Normalize a floating point number x to the value normx, in the
       range [1-10).  expon is returned such that:
       x = normx * (10.0 ** expon)
       This logic is taken directly from IRAF's fp_normd function."""
    # See FP_EPSILON description elsewhere.
    tol = FP_EPSILON * 10.0
    absx = abs(x)
    expon = 0

    if absx > 0:
        while absx < (1.0 - tol):
            absx *= 10.0
            expon -= 1
            if absx == 0.0:  # check for underflow to zero
                return 0, 0
        while absx >= (10.0 + tol):
            absx /= 10.0
            expon += 1

    if x < 0:
        normx = -absx
    else:
        normx = absx

    return normx, expon


_denode_pat = _re.compile(r'[^/]*!')


def _denode(filename):
    """Remove IRAF "node!" specification from filename"""
    mm = _denode_pat.match(filename)
    if mm is None:
        return filename
    else:
        return filename[len(mm.group()):]


def _imextn():
    """Returns list of image types and extensions

    The return value is (ktype, globlist) where ktype is
    the image kernel (oif, fxf, etc.) and globlist is a list
    of glob-style patterns that match extensions.
    """
    # imextn environment variable has list (or use default)
    s = envget("imextn", "oif:imh fxf:fits,fit plf:pl qpf:qp stf:hhh,??h")
    fields = s.split()
    extlist = []
    for f in fields:
        ilist = f.split(":")
        if len(ilist) != 2:
            raise IrafError(f"Illegal field `{f}' in IRAF variable imextn")
        exts = ilist[1].split(",")
        extlist.append((ilist[0], exts))
    return extlist


def _checkext(ext, extlist):
    """Returns image type if ext is in extlist, else returns None

    Assumes ext starts with a '.' (as returned by os.path.split) and
    that null extensions can't match.
    """
    if not ext:
        return None
    ext = ext[1:]
    for ktype, elist in extlist:
        for pat in elist:
            if _fnmatch.fnmatch(ext, pat):
                return ktype
    return None


def _searchext(root, extlist):
    """Returns image type if file root.ext is found (ext from extlist)"""
    for ktype, elist in extlist:
        for pat in elist:
            flist = _glob.glob(root + '.' + pat)
            if flist:
                return ktype
    return None


def imaccess(filename):
    """Returns true if image matching name exists and is readable"""

    if filename == INDEF:
        return INDEF
    # See if the filename contains any wildcard characters.
    # First strip any extension or section specification.
    tfilename = filename
    i = tfilename.find('[')
    if i >= 0:
        tfilename = filename[:i]
    if '*' in tfilename or '?' in tfilename:
        return 0
    # Edge case not handled below:
    if filename.find('[]') != -1:
        return 0
    # If we get this far, use imheader to test existence.
    # Any error output is taken to mean failure.
    sout = _io.StringIO()
    serr = _io.StringIO()
    from . import iraf
    iraf.imhead(filename, Stdout=sout, Stderr=serr)
    errstr = serr.getvalue().lower()
    outstr = sout.getvalue().lower()
    if errstr:
        # Handle exceptional cases:
        # 1) ambiguous files (imaccess accepts this)
        # 2) non specification of extension # for multi-extension fits files
        #    (imaccess doesn't require)
        # This approach, while adaptable, is brittle in its dependency on
        # IRAF error strings
        if ((errstr.find('must specify which fits extension') >= 0) or
            (errstr.find('ambiguous')) >= 0):
            return 1
        else:
            return 0
    elif outstr:
        # If the filename string is blank(s), imhead writes "no images found"
        # to Stdout
        if (outstr.find('no images found') >= 0):
            return 0
        else:
            return 1


def defvar(varname):
    """Returns true if CL variable is defined"""
    if varname == INDEF:
        return INDEF
    return varname in _varDict or varname in _os.environ


def deftask(taskname):
    """Returns true if CL task is defined"""
    if taskname == INDEF:
        return INDEF
    try:
        from . import iraf
        getattr(iraf, taskname)
        return 1
    except AttributeError:
        # treat all errors (including ambiguous task names) as a missing task
        return 0


def defpac(pkgname):
    """Returns true if CL package is defined and loaded"""
    if pkgname == INDEF:
        return INDEF
    try:
        t = getPkg(pkgname)
        return t.isLoaded()
    except KeyError:
        # treat all errors (including ambiguous package names) as a missing pkg
        return 0


def curpack():
    """Returns name of current CL package"""
    if loadedPath:
        return loadedPath[-1].getName()
    else:
        return ""


def curPkgbinary():
    """Returns name pkgbinary directory for current CL package"""
    if loadedPath:
        return loadedPath[-1].getPkgbinary()
    else:
        return ""


# utility functions for boolean conversions


def bool2str(value):
    """Convert IRAF boolean value to a string"""
    if value in [None, INDEF]:
        return "INDEF"
    elif value:
        return "yes"
    else:
        return "no"


def boolean(value):
    """Convert Python native types (string, int, float) to IRAF boolean

    Accepts integer/float values 0,1 or string 'no','yes'
    Also allows INDEF as value, or existing IRAF boolean type.
    """
    if value in [0, 1]:
        return value
    elif value in (no, yes):
        return int(value)
    elif value in [INDEF, "", None]:
        return INDEF
    if isinstance(value, str):
        v2 = _irafutils.stripQuotes(value.strip())
        if v2 == "INDEF":
            return INDEF
        ff = v2.lower()
        if ff == "no":
            return 0
        elif ff == "yes":
            return 1
    elif isinstance(value, float):
        # try converting to integer
        try:
            ival = int(value)
            if (ival == value) and (ival == 0 or ival == 1):
                return ival
        except (ValueError, OverflowError):
            pass
    raise ValueError(f"Illegal boolean value {repr(value)}")


# -----------------------------------------------------
# scan functions
# Abandon all hope, ye who enter here
# -----------------------------------------------------

_nscan = 0


def fscan(theLocals, line, *namelist, **kw):
    """fscan function sets parameters from a string or list parameter

    Uses local dictionary (passed as first argument) to set variables
    specified by list of following names.  (This is a bit
    messy, but it is by far the cleanest approach I've thought of.
    I'm literally using call-by-name for these variables.)

    Accepts an additional keyword argument strconv with names of
    conversion functions for each argument in namelist.

    Returns number of arguments set to new values, which may be
    fewer than the number of variables if an unexpected character
    is encountered in 'line'.  If there are too few space-delimited
    arguments on the input line, it does not set all the arguments.
    Returns EOF on end-of-file.
    """
    # get the value of the line (which may be a variable, string literal,
    # expression, or an IRAF list parameter)
    global _nscan
    try:
        from . import iraf
        line = eval(line, {'iraf': iraf}, theLocals)
    except EOFError:
        _weirdEOF(theLocals, namelist)
        _nscan = 0
        return EOF
    f = line.split()
    n = min(len(f), len(namelist))
    # a tricky thing -- null input is OK if the first variable is
    # a struct
    if n == 0 and namelist and _isStruct(theLocals, namelist[0]):
        f = ['']
        n = 1
    if 'strconv' in kw:
        strconv = kw['strconv']
        del kw['strconv']
    else:
        strconv = n * [None]
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    n_actual = 0  # this will be the actual number of values converted
    for i in range(n):
        # even messier: special handling for struct type variables, which
        # consume the entire remaining string
        if _isStruct(theLocals, namelist[i]):
            if i < len(namelist) - 1:
                raise TypeError(f"Struct type param `{namelist[i]}' "
                                "must be the final argument to scan")
            # ultramessy -- struct needs rest of line with embedded whitespace
            if i == 0:
                iend = 0
            else:
                # construct a regular expression that matches the line so far
                pat = [r'\s*'] * (2 * i)
                for j in range(i):
                    pat[2 * j + 1] = f[j]
                # a single following whitespace character also gets removed
                # (don't blame me, this is how IRAF does it!)
                pat.append(r'\s')
                pat = ''.join(pat)
                mm = _re.match(pat, line)
                if mm is None:
                    raise RuntimeError(f"Bug: line '{line}' pattern '{pat}' failed")
                iend = mm.end()
            if line[-1:] == '\n':
                cmd = namelist[i] + ' = ' + repr(line[iend:-1])
            else:
                cmd = namelist[i] + ' = ' + repr(line[iend:])
        elif strconv[i]:
            cmd = namelist[i] + ' = ' + strconv[i] + '(' + repr(f[i]) + ')'
        else:
            cmd = namelist[i] + ' = ' + repr(f[i])
        try:
            exec(cmd, theLocals)
            n_actual += 1
        except ValueError:
            break
    _nscan = n_actual
    return n_actual


def fscanf(theLocals, line, format, *namelist, **kw):
    """fscanf function sets parameters from a string/list parameter with format

    Implementation is similar to fscan but is a bit simpler because
    special struct handling is not needed.  Does not allow strconv keyword.

    Returns number of arguments set to new values, which may be
    fewer than the number of variables if an unexpected character
    is encountered in 'line'.  If there are too few space-delimited
    arguments on the input line, it does not set all the arguments.
    Returns EOF on end-of-file.
    """
    # get the value of the line (which may be a variable, string literal,
    # expression, or an IRAF list parameter)
    global _nscan
    try:
        from . import iraf
        line = eval(line, {'iraf': iraf}, theLocals)
        # format also needs to be evaluated
        format = eval(format, theLocals)
    except EOFError:
        _weirdEOF(theLocals, namelist)
        _nscan = 0
        return EOF
    if sscanf is None:
        raise RuntimeError("fscanf is not supported on this platform")
    f = sscanf.sscanf(line, format)
    n = min(len(f), len(namelist))
    # if list is null, add a null string
    # ugly but should be right most of the time
    if n == 0 and namelist:
        f = ['']
        n = 1
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    n_actual = 0  # this will be the actual number of values converted
    for i in range(n):
        cmd = namelist[i] + ' = ' + repr(f[i])
        try:
            exec(cmd, theLocals)
            n_actual += 1
        except ValueError:
            break
    _nscan = n_actual
    return n_actual


def _weirdEOF(theLocals, namelist):
    # Replicate a weird IRAF behavior -- if the argument list
    # consists of a single struct-type variable, and it does not
    # currently have a defined value, set it to the null string.
    # (I warned you to abandon hope!)
    if namelist and _isStruct(theLocals, namelist[0], checklegal=1):
        if len(namelist) > 1:
            raise TypeError(f"Struct type param `{namelist[0]}' "
                            "must be the final argument to scan")
        # it is an undefined struct, so set it to null string
        cmd = namelist[0] + ' = ""'
        exec(cmd, theLocals)


def _isStruct(theLocals, name, checklegal=0):
    """Returns true if the variable `name' is of type struct

    If checklegal is true, returns true only if variable is struct and
    does not currently have a legal value.
    """
    c = name.split('.')
    if len(c) > 1:
        # must get the parameter object, not the value
        c[-1] = f'getParObject({repr(c[-1])})'
    fname = '.'.join(c)
    try:
        par = eval(fname, theLocals)
    except KeyboardInterrupt:
        raise
    except:
        # assume all failures mean this is not an IrafPar
        return 0
    if isinstance(par, _irafpar.IrafPar) and par.type == 'struct':
        if checklegal:
            return (not par.isLegal())
        else:
            return 1
    else:
        return 0


def scan(theLocals, *namelist, **kw):
    """Scan function sets parameters from line read from stdin

    This can be used either as a function or as a task (it accepts
    redirection and the _save keyword.)
    """
    # handle redirection and save keywords
    # other keywords are passed on to fscan
    redirKW, closeFHList = redirProcess(kw)
    if '_save' in kw:
        del kw['_save']
    resetList = redirApply(redirKW)
    try:
        line = _irafutils.tkreadline()
        # null line means EOF
        if line == "":
            _weirdEOF(theLocals, namelist)
            global _nscan
            _nscan = 0
            return EOF
        else:
            args = (
                theLocals,
                repr(line),
            ) + namelist
            return fscan(*args, **kw)
    except Exception as ex:
        print('iraf.scan exception: ' + str(ex))
    finally:
        redirReset(resetList, closeFHList)


def scanf(theLocals, format, *namelist, **kw):
    """Formatted scan function sets parameters from line read from stdin

    This can be used either as a function or as a task (it accepts
    redirection and the _save keyword.)
    """
    # handle redirection and save keywords
    # other keywords are passed on to fscan
    redirKW, closeFHList = redirProcess(kw)
    if '_save' in kw:
        del kw['_save']
    resetList = redirApply(redirKW)
    try:
        line = _irafutils.tkreadline()
        # null line means EOF
        if line == "":
            _weirdEOF(theLocals, namelist)
            global _nscan
            _nscan = 0
            return EOF
        else:
            args = (
                theLocals,
                repr(line),
                format,
            ) + namelist
            return fscanf(*args, **kw)
    except Exception as ex:
        print('iraf.scanf exception: ' + str(ex))
    finally:
        redirReset(resetList, closeFHList)


def nscan():
    """Return number of items read in last scan function"""
    global _nscan
    return _nscan


# -----------------------------------------------------
# IRAF utility procedures
# -----------------------------------------------------

# these have extra keywords (redirection, _save) because they can
# be called as tasks


@handleRedirAndSaveKwdsPlus
def set(*args, **kw):
    """Set IRAF environment variables"""
    if len(args) == 0:
        if len(kw) != 0:
            # normal case is only keyword,value pairs
            msg = []
            for keyword, value in kw.items():
                keyword = _irafutils.untranslateName(keyword)
                svalue = str(value)
                if keyword == "erract":
                    irafecl.erract.adjust(svalue)
                else:
                    # add keyword:svalue to the dict, but first check for '#'
                    if svalue.find('#') > 0 and svalue.find("'") < 0 and \
                       svalue.find('"') < 0:
                        # this can happen when translating .cl scripts with
                        # vars with sequential commented-out continuation lines
                        svalue = svalue[0:svalue.find('#')]
                    _varDict[keyword] = svalue
                msg.append(f"set {keyword}={svalue}\n")
            _irafexecute.processCache.setenv("".join(msg))
        else:
            # set with no arguments lists all variables (using same format
            # as IRAF)
            listVars("    ", "=")
    else:
        # The only other case allowed is the peculiar syntax
        # 'set @filename', which only gets used in the zzsetenv.def file,
        # where it reads extern.pkg.  That file also gets read (in full cl
        # mode) by clpackage.cl.  I get errors if I read this during
        # zzsetenv.def, so just ignore it here...
        #
        # Flag any other syntax as an error.
        if len(args) != 1 or len(kw) != 0 or \
           (not isinstance(args[0], str)) or args[0][:1] != '@':
            raise SyntaxError("set requires name=value pairs")


# currently do not distinguish set from reset
# this will change when keep/bye/unloading are implemented

reset = set


@handleRedirAndSaveKwds
def show(*args):
    """Print value of IRAF or OS environment variables"""
    if len(args) and args[0].startswith("erract"):
        print(irafecl.erract.states())
    else:
        if args:
            for arg in args:
                print(envget(arg))
        else:
            # print them all
            listVars("    ", "=")


@handleRedirAndSaveKwds
def unset(*args):
    """Unset IRAF environment variables.
    This is not a standard IRAF task, but it is obviously useful.
    It makes the resulting variables undefined.  It silently ignores
    variables that are not defined.  It does not change the os environment
    variables.
    """
    for arg in args:
        if arg in _varDict:
            del _varDict[arg]


@handleRedirAndSaveKwds
def time():
    """Print current time and date"""
    print(_time.strftime('%a %H:%M:%S %d-%b-%Y'))


# Note - we really should not give this a default (should require an int),
# because why run "sleep 0"?, but some legacy .cl scripts call it that way.
@handleRedirAndSaveKwds
def sleep(seconds=0):
    """Sleep for specified time"""
    _time.sleep(float(seconds))


def beep(**kw):
    """Beep to terminal (even if output is redirected)"""
    # just ignore keywords
    _sys.__stdout__.write("")
    _sys.__stdout__.flush()


def clOscmd(s, **kw):
    """Execute a system-dependent command in the shell, returning status"""

    # handle redirection and save keywords
    redirKW, closeFHList = redirProcess(kw)
    if '_save' in kw:
        del kw['_save']
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    resetList = redirApply(redirKW)
    try:
        # if first character of s is '!' then force to Bourne shell
        if s[:1] == '!':
            shell = "/bin/sh"
            s = s[1:]
        else:
            # otherwise use default shell
            shell = None

        # ignore null commands
        if not s:
            return 0

        # use subshell to execute command so wildcards, etc. are handled
        status = _subproc.subshellRedir(s, shell=shell)
        return status

    finally:
        rv = redirReset(resetList, closeFHList)
    return rv


_sttyArgs = _minmatch.MinMatchDict({
    'terminal': None,
    'baud': 9600,
    'ncols': 80,
    'nlines': 24,
    'show': no,
    'all': no,
    'reset': no,
    'resize': no,
    'clear': no,
    'ucasein': no,
    'ucaseout': no,
    'login': None,
    'logio': None,
    'logout': None,
    'playback': None,
    'verify': no,
    'delay': 500,
})


@handleRedirAndSaveKwdsPlus
def stty(terminal=None, **kw):
    """IRAF stty command (mainly not implemented)"""
    expkw = _sttyArgs.copy()
    if terminal is not None:
        expkw['terminal'] = terminal
    for key, item in kw.items():
        if key in _sttyArgs:
            expkw[key] = item
        else:
            raise TypeError('unexpected keyword argument: ' + key)
    if terminal is None and len(kw) == 0:
        # will need default values for the next step; try _wutil for them
        dftNcol = '80'
        dftNlin = '24'
        try:
            if _sys.stdout.isatty():
                nlines, ncols = _wutil.getTermWindowSize()
                dftNcol = str(ncols)
                dftNlin = str(nlines)
        except:
            pass  # No error message here - may not always be available
        # no args: print terminal type and size
        print('{} ncols={} nlines={}'
              .format(envget('terminal', 'undefined'),
                      envget('ttyncols', dftNcol),
                      envget('ttynlines', dftNlin)))
    elif expkw['resize'] or expkw['terminal'] == "resize":
        # resize: sets CL env parameters giving screen size; show errors
        if _sys.stdout.isatty():
            nlines, ncols = _wutil.getTermWindowSize()
            set(ttyncols=str(ncols), ttynlines=str(nlines))
    elif expkw['terminal']:
        set(terminal=expkw['terminal'])
        # They are setting the terminal type.  Let's at least try to
        # get the dimensions if not given. This is more than the CL does.
        if ('nlines' not in kw) and ('ncols' not in kw) and \
           _sys.stdout.isatty():
            try:
                nlines, ncols = _wutil.getTermWindowSize()
                set(ttyncols=str(ncols), ttynlines=str(nlines))
            except:
                pass  # No error msg here - may not always be available
    elif expkw['playback'] is not None:
        _writeError("stty playback not implemented")


@handleRedirAndSaveKwds
def eparam(*args):
    """Edit parameters for tasks.  Starts up epar GUI."""
    for taskname in args:
        try:  # maybe it is an IRAF task
            taskname.eParam()
        except AttributeError:
            try:  # maybe it is an IRAF task name
                getTask(taskname).eParam()
            except (KeyError, TypeError):
                try:  # maybe it is a task which uses .cfg files
                    _wrapTeal(taskname)
                except _teal.cfgpars.NoCfgFileError:
                    _writeError('Warning: Could not find task "' + taskname +
                                '"')


def _wrapTeal(taskname):
    """ Wrap the call to TEAL.  Try to use focus switching here. """
    # place focus on gui
    oldFoc = _wutil.getFocalWindowID()
    _wutil.forceFocusToNewWindow()
    # pop up TEAL
    x = 0
    try:
        # use simple-auto-close mode (like EPAR) by no return dict
        x = _teal.teal(taskname,
                       returnAs="status",
                       errorsToTerm=True,
                       strict=False,
                       autoClose=True)
    # put focus back on terminal, even if there is an exception
    finally:
        # Turns out, for the majority of TEAL-enabled tasks, users don't like
        # having the focus jump back to the terminal for them (especially if
        # it is a long-running task) after executing, so only move focus
        # back if they didn't execute
        if x < 1:
            _wutil.setFocusTo(oldFoc)


@handleRedirAndSaveKwds
def tparam(*args):
    """Edit parameters for tasks.  Starts up epar GUI."""
    for taskname in args:
        try:
            taskname.tParam()
        except AttributeError:
            # try:
            getTask(taskname).tParam()
            # except (KeyError, TypeError):
            #    _writeError(f"Warning: Could not find task {taskname} for tpar\n")


@handleRedirAndSaveKwds
def lparam(*args):
    """List parameters for tasks"""
    for taskname in args:
        try:
            taskname.lParam()
        except AttributeError:
            try:
                getTask(taskname).lParam()
            except (KeyError, TypeError):
                _writeError(f"Warning: Could not find task {taskname} for lpar\n")


@handleRedirAndSaveKwdsPlus
def dparam(*args, **kw):
    """Dump parameters for task in executable form"""
    # only keyword: pyraf-specific 'cl=' used to specify CL or Python syntax
    cl = 1
    if 'cl' in kw:
        cl = kw['cl']
        del kw['cl']
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    for taskname in args:
        try:
            taskname.dParam(cl=cl)
        except AttributeError:
            try:
                getTask(taskname).dParam(cl=cl)
            except (KeyError, TypeError):
                _writeError(f"Warning: Could not find task {taskname} for dpar\n")


@handleRedirAndSaveKwds
def update(*args):
    """Update task parameters on disk"""
    for taskname in args:
        try:
            getTask(taskname).saveParList()
        except KeyError:
            _writeError(f"Warning: Could not find task {taskname} for update")


@handleRedirAndSaveKwdsPlus
def unlearn(*args, **kw):
    """Unlearn task parameters -- restore to defaults"""
    force = False
    if 'force' in kw:
        force = kw['force'] in (True, '+', 'yes')
        del kw['force']
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    for taskname in args:
        try:  # maybe it is an IRAF task name
            getTask(taskname).unlearn()
        except KeyError:
            try:  # maybe it is a task which uses .cfg files
                ans = _teal.unlearn(taskname, deleteAll=force)
                if ans != 0:
                    _writeError(
                        'Error: multiple user-owned files found '
                        f'to unlearn for task "{taskname}.\n"'
                        'None were deleted.  Please review and move/'
                        f'delete these files:\n\n\t'
                        + '\n\t'.join(ans)
                        + f'\n\nor type "unlearn {taskname} force=yes"')
            except _teal.cfgpars.NoCfgFileError:
                _writeError(f"Warning: Could not find task {taskname} to unlearn")


@handleRedirAndSaveKwdsPlus
def teal(taskArg, **kw):
    """ Synonym for epar.  Open the TEAL GUI but keep logic in eparam.
    There is no return dict."""
    eparam(taskArg, **kw)


@handleRedirAndSaveKwds
def edit(*args):
    """Edit text files"""
    editor = envget('editor')
    margs = list(map(Expand, args))
    _os.system(' '.join([
        editor,
    ] + margs))


_clearString = None


@handleRedirAndSaveKwds
def clear(*args):
    """Clear screen if output is terminal"""
    global _clearString
    if not _os.path.exists('/usr/bin/tput'):
        _clearString = ''
    if _clearString is None:
        # get the clear command by running system clear
        fh = _io.StringIO()
        try:
            clOscmd('/usr/bin/tput clear', Stdout=fh)
            _clearString = fh.getvalue()
        except SubprocessError:
            _clearString = ""
        fh.close()
        del fh
    if _sys.stdout == _sys.__stdout__:
        _sys.stdout.write(_clearString)
        _sys.stdout.flush()


@handleRedirAndSaveKwds
def flprcache(*args):
    """Flush process cache.  Takes optional list of tasknames."""
    _irafexecute.processCache.flush(*args)
    if Verbose > 0:
        print("Flushed process cache")


@handleRedirAndSaveKwds
def prcacheOff():
    """Disable process cache.  No process cache will be employed
       for the rest of this session."""
    _irafexecute.processCache.setSize(0)
    if Verbose > 0:
        print("Disabled process cache")


@handleRedirAndSaveKwds
def prcacheOn():
    """Re-enable process cache.  A process cache will again be employed
       for the rest of this session.  This may be useful after prcacheOff()."""
    _irafexecute.processCache.resetSize()
    if Verbose > 0:
        print("Enabled process cache")


@handleRedirAndSaveKwds
def prcache(*args):
    """Print process cache.  If args are given, locks tasks into cache."""
    if args:
        _irafexecute.processCache.lock(*args)
    else:
        _irafexecute.processCache.list()


@handleRedirAndSaveKwds
def gflush():
    """Flush any buffered graphics output."""
    gki.kernel.flush()


@handleRedirAndSaveKwdsPlus
def pyexecute(filename, **kw):
    """Execute python code in filename (which may include IRAF path).
    This is callable from within CL scripts.  There is a corresponding
    pyexecute.cl task that runs outside the PyRAF environment and just
    prints a warning.
    """
    # these keyword parameters are relevant only outside PyRAF
    for keyword in ['_save', 'verbose', 'tasknames']:
        if keyword in kw:
            del kw[keyword]
    # get package info
    if 'PkgName' in kw:
        pkgname = kw['PkgName']
        del kw['PkgName']
    else:
        pkgname = curpack()
    if 'PkgBinary' in kw:
        pkgbinary = kw['PkgBinary']
        del kw['PkgBinary']
    else:
        pkgbinary = curPkgbinary()
    # fix illegal package names
    spkgname = pkgname.replace('.', '_')
    if spkgname != pkgname:
        _writeError("Warning: `.' illegal in task name, changing "
                    f"`{pkgname}' to `{spkgname}'")
        pkgname = spkgname
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    # execute code in a new namespace (including PkgName, PkgBinary)
    efilename = Expand(filename)
    namespace = {
        'PkgName': pkgname,
        'PkgBinary': pkgbinary,
        '__file__': efilename
    }
    exec(compile(open(efilename, "rb").read(), efilename, 'exec'), namespace)


# history routines


@handleRedirAndSaveKwds
def history(n=20):
    """Print history.
    Does not replicate the IRAF behavior of changing default number of
    lines to print.  (That seems fairly useless to me.)
    """
    # Seems like there ought to be a way to do this using readline, but I have
    # not been able to figure out any readline command that lists the history
    import __main__
    try:
        n = abs(int(n))
        __main__._pycmdline.printHistory(n)
    except (NameError, AttributeError):
        pass


@handleRedirAndSaveKwds
def ehistory(*args):
    """Dummy history function"""
    print('ehistory command not required: Use arrow keys to recall commands')
    print('or ctrl-R to search for a string in the command history.')


# dummy routines (must allow *args and **kw)


@handleRedirAndSaveKwdsPlus
def clNoBackground(*args, **kw):
    """Dummy background function"""
    _writeError('Background jobs not implemented')


jobs = service = kill = wait = clNoBackground

# dummy (do-nothing) routines


def clDummy(*args, **kw):
    """Dummy do-nothing function"""
    # just ignore keywords and arguments
    pass


bye = keep = logout = clbye = cache = language = clDummy


# unimplemented but no exception raised (and no message
# printed if not in verbose mode)
def _notImplemented(cmd):
    """Dummy unimplemented function"""
    if Verbose > 0:
        _writeError(f"The {cmd} task has not been implemented")


@handleRedirAndSaveKwdsPlus
def putlog(*args, **kw):
    _notImplemented('putlog')


@handleRedirAndSaveKwdsPlus
def clAllocate(*args, **kw):
    _notImplemented('_allocate')


@handleRedirAndSaveKwdsPlus
def clDeallocate(*args, **kw):
    _notImplemented('_deallocate')


@handleRedirAndSaveKwdsPlus
def clDevstatus(*args, **kw):
    _notImplemented('_devstatus')


# unimplemented -- raise exception


def fprint(*args, **kw):
    """Error unimplemented function"""
    # The fprint task is never used in CL scripts, as far as I can tell
    raise IrafError("The fprint task has not been implemented")


# various helper functions


@handleRedirAndSaveKwds
def pkgHelp(pkgname=None):
    """Give help on package (equivalent to CL '? [taskname]')"""
    if pkgname is None:
        listCurrent()
    else:
        listTasks(pkgname)


@handleRedirAndSaveKwds
def allPkgHelp():
    """Give help on all packages (equivalent to CL '??')"""
    listTasks()


def _clProcedure(*args, **kw):
    """Core function for the CL task

    Gets passed to IrafPythonTask as function argument.
    Note I/O redirection has already been set up before calling this.
    """
    # just ignore the arguments -- they are only used through .par list
    # if input is not redirected, don't do anything
    if _sys.stdin == _sys.__stdin__:
        return
    # initialize environment
    theLocals = {}
    exec('from pyraf import iraf', theLocals)
    exec('from pyraf.irafpar import makeIrafPar', theLocals)
    exec('from stsci.tools.irafglobals import *', theLocals)
    exec('from pyraf.pyrafglobals import *', theLocals)

    # feed the input to clExecute
    # redirect input to sys.__stdin__ after reading the CL script from sys.stdin
    clExecute(_sys.stdin.read(), locals=theLocals, Stdin=_sys.__stdin__)


def clProcedure(input=None, mode="", DOLLARnargs=0, **kw):
    """Run CL commands from a file (cl < input) -- OBSOLETE

    This is obsolete, replaced by the IrafPythonTask version of
    the cl, using above _clProcedure function.  It is being
    retained only for backward compatibility since translated
    versions of CL scripts could use it.  New versions will
    not use it.  Also, this cannot use handleRedirAndSaveKwds.
    """
    # handle redirection and save keywords
    redirKW, closeFHList = redirProcess(kw)
    if '_save' in kw:
        del kw['_save']
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    # get the input
    if 'stdin' in redirKW:
        stdin = redirKW['stdin']
        del redirKW['stdin']
        if hasattr(stdin, 'name'):
            filename = stdin.name.split('.')[0]
        else:
            filename = 'tmp'
    elif input is not None:
        if isinstance(input, str):
            # input is a string -- stick it in a StringIO buffer
            stdin = _io.StringIO(input)
            filename = input
        elif hasattr(input, 'read'):
            # input is a filehandle
            stdin = input
            if hasattr(stdin, 'name'):
                filename = stdin.name.split('.')[0]
            else:
                filename = 'tmp'
        else:
            raise TypeError("Input must be a string or input filehandle")
    else:
        # CL without input does nothing
        return
    # apply the I/O redirections
    resetList = redirApply(redirKW)
    # create and run the task
    try:
        # create task object with no package
        newtask = _iraftask.IrafCLTask('', filename, '', stdin, '', '')
        newtask.run()
    finally:
        # reset the I/O redirections
        rv = redirReset(resetList, closeFHList)
    return rv


@handleRedirAndSaveKwds
def hidetask(*args):
    """Hide the CL task in package listings"""
    for taskname in args:
        try:
            getTask(taskname).setHidden()
        except KeyError:
            _writeError(f"Warning: Could not find task {taskname} to hide")


# pattern matching single task name, possibly with $ prefix and/or
# .pkg or .tb suffix
# also matches optional trailing comma and whitespace

optional_whitespace = r'[ \t]*'
taskname = r'(?:' + r'(?P<taskprefix>\$?)' + \
    r'(?P<taskname>[a-zA-Z_][a-zA-Z0-9_]*)' + \
    r'(?P<tasksuffix>\.(?:pkg|tb))?' + \
    r',?' + optional_whitespace + r')'

_re_taskname = _re.compile(taskname)

del taskname, optional_whitespace


@handleRedirAndSaveKwdsPlus
def task(*args, **kw):
    """Define IRAF tasks"""
    redefine = 0
    iscmdstring = False
    if 'Redefine' in kw:
        redefine = kw['Redefine']
        del kw['Redefine']
    # get package info
    if 'PkgName' in kw:
        pkgname = kw['PkgName']
        del kw['PkgName']
    else:
        pkgname = curpack()
    if 'PkgBinary' in kw:
        pkgbinary = kw['PkgBinary']
        del kw['PkgBinary']
    else:
        pkgbinary = curPkgbinary()
    if 'IsCmdString' in kw:
        iscmdstring = kw['IsCmdString']
        del kw['IsCmdString']
    # fix illegal package names
    spkgname = pkgname.replace('.', '_')
    if spkgname != pkgname:
        _writeError("Warning: `.' illegal in task name, changing "
                    f"`{pkgname}' to `{spkgname}'")
        pkgname = spkgname
    # get the task name
    if len(kw) > 1:
        raise SyntaxError("More than one `=' in task definition")
    elif len(kw) < 1:
        raise SyntaxError("Must be at least one `=' in task definition")
    s = list(kw.keys())[0]
    value = kw[s]
    # To handle when actual CL code is given, not a file name, we will
    # replace the code with the name of the tmp file that we write it to.
    if iscmdstring:
        # write it to a temp file in the home$ dir, then use filename
        (fd, tmpCl) = _tempfile.mkstemp(suffix=".cl",
                                        prefix=str(s) + '_',
                                        dir=userIrafHome,
                                        text=True)
        _os.close(fd)
        # Check basename for invalid chars as far as python func. names go.
        # yes this goes against the use of mkstemp from a purity point
        # of view but it can't much be helped.  verify later is it unique
        orig_tmpCl = tmpCl
        tmpClPath, tmpClFname = _os.path.split(tmpCl)
        tmpClFname = tmpClFname.replace('-', '_')
        tmpClFname = tmpClFname.replace('+', '_')
        tmpCl = _os.path.join(tmpClPath, tmpClFname)
        assert tmpCl == orig_tmpCl or not _os.path.exists(tmpCl), \
            'Abused mkstemp usage in some way; fname: '+tmpCl
        # write inline code to .cl file; len(kw) is checked below
        f = open(tmpCl, 'w')
        f.write(value + '\n')
        # Add text at end to auto-delete this temp file
        f.write('#\n# this last section automatically added\n')
        f.write('delete ' + tmpCl + ' verify-\n')
        f.close()
        # exchange for tmp .cl file name
        value = tmpCl

    # untranslateName
    s = _irafutils.untranslateName(s)
    args = args + (s,)

    # assign value to each task in the list
    global _re_taskname
    for tlist in args:
        mtl = _re_taskname.match(tlist)
        if not mtl:
            raise SyntaxError(f"Illegal task name `{tlist}'")
        name = mtl.group('taskname')
        prefix = mtl.group('taskprefix')
        suffix = mtl.group('tasksuffix')
        IrafTaskFactory(prefix,
                        name,
                        suffix,
                        value,
                        pkgname,
                        pkgbinary,
                        redefine=redefine)


def redefine(*args, **kw):
    """Redefine an existing task"""
    kw['Redefine'] = 1
    task(*args, **kw)


def package(pkgname=None, bin=None, PkgName='', PkgBinary='', **kw):
    """Define IRAF package, returning tuple with new package name and binary

    PkgName, PkgBinary are old default values.  If Stdout=1 is specified,
    returns output as string array (normal task behavior) instead of
    returning PkgName, PkgBinary.  This inconsistency is necessary
    to replicate the inconsistent behavior of the package command
    in IRAF.
    """

    module = irafecl.getTaskModule()

    # handle redirection and save keywords
    redirKW, closeFHList = redirProcess(kw)
    if '_save' in kw:
        del kw['_save']
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    resetList = redirApply(redirKW)
    try:
        if pkgname is None:
            # no argument: list all loaded packages in search order
            printed = {}
            lp = loadedPath[:]
            lp.reverse()
            for pkg in lp:
                pkgname = pkg.getName()
                if pkgname not in printed:
                    printed[pkgname] = 1
                    print(f'    {pkgname}')
            rv1 = (PkgName, PkgBinary)
        else:
            spkgname = pkgname.replace('.', '_')
            # remove trailing comma
            if spkgname[-1:] == ",":
                spkgname = spkgname[:-1]
            if (spkgname != pkgname) and (Verbose > 0):
                _writeError("Warning: illegal characters in task name, "
                            f"changing `{pkgname}' to `{spkgname}'")
            pkgname = spkgname
            # is the package defined?
            # if not, is there a CL task by this name?
            # otherwise there is an error
            pkg = getPkg(pkgname, found=1)
            if pkg is None:
                pkg = getTask(pkgname, found=1)
                if pkg is None or not isinstance(pkg, _iraftask.IrafCLTask) or \
                        pkg.getName() != pkgname:
                    raise KeyError(f"Package `{pkgname}' not defined")
                # Hack city -- there is a CL task with the package name, but it was
                # not defined to be a package.  Convert it to an IrafPkg object.

                module.mutateCLTask2Pkg(pkg)

                # We must be currently loading this package if we encountered
                # its package statement (XXX can I confirm that?).
                # Add it to the lists of loaded packages (this usually
                # is done by the IrafPkg run method, but we are executing
                # as an IrafCLTask instead.)

                _addPkg(pkg)
                loadedPath.append(pkg)
                addLoaded(pkg)
                if Verbose > 0:
                    _writeError(f"Warning: CL task `{pkgname}' apparently is "
                                "a package")

            # Make sure that this is the current package, even
            # if another package was loaded in the package script
            # but before the package statement
            if loadedPath[-1] is not pkg:
                loadedPath.append(pkg)

            rv1 = (pkgname, bin or PkgBinary)
    finally:
        rv = redirReset(resetList, closeFHList)
    # return output as array of strings if not None, else return name,bin
    return rv or rv1


@handleRedirAndSaveKwds
def clPrint(*args):
    """CL print command -- emulates CL spacing and uses redirection keywords"""
    nargs = len(args)
    for n, arg in enumerate(args, start=1):
        print(arg, end='')
        # add separator space, except after string arguments and at the end
        if n < nargs and not isinstance(arg, str):
            print(end=' ')
    print()


# printf format conversion utilities


def _quietConv(w, d, c, args, i):
    """Format codes that are quietly converted to %s"""
    return f"%{w}s"


def _boolConv(w, d, c, args, i):
    """Boolean gets converted to upper case before printing"""
    args[i] = str(args[i]).upper()
    return f"%{w}s"


def _badConv(w, d, c, args, i):
    """Format codes that are converted to %s with warning"""
    _writeError(f"Warning: printf cannot handle format '%{w + d + c}', "
                f"using '%{w}s' instead\n")
    return f"%{w}s"


def _hConv(w, d, c, args, i):
    """Handle %h %m %H %M dd:mm:ss.s formats"""
    if i < len(args):
        try:
            if d[1:]:
                digits = int(d[1:])
            else:
                digits = 1
            if c in "HM":
                # capital letters convert from degrees to hours (undocumented)
                value = args[i] / 15.0
            else:
                value = args[i]
            args[i] = clDms(value, digits=digits, seconds=c not in "mM")
        except ValueError:
            pass
    return f"%{w}s"


def _rConv(w, d, c, args, i):
    """Handle W.DrN general radix format"""
    if i < len(args):
        try:
            base = int(c[-1])
        except ValueError:
            base = 10
        if w[:1] == "0":
            # add leading zeros
            args[i] = radix(args[i], base, length=int(w))
        else:
            args[i] = radix(args[i], base)
    return f"%{w}s"


def _wConv(w, d, c, args, i):
    """Handle %w format, which is supposed to generate spaces"""
    if i < len(args) and not w:
        # number of spaces comes from argument
        if args[i] == INDEF:
            w = 0
        else:
            try:
                w = int(args[i])
            except ValueError:
                w = 0
    args[i] = ""
    return f"%{w}s"


# pattern matching %w.dc where c is single letter format code
_reFormat = _re.compile(r"%(?P<w>-?\d*)(?P<d>(?:\.\d*)?)(?P<c>[a-zHM])")

# dispatch table for format conversions
_fDispatch = {}
for b in _string.ascii_lowercase:
    _fDispatch[b] = None

# formats that get quietly converted to uppercase and translated to %s
badList = ["b"]
for b in badList:
    _fDispatch[b] = _boolConv

# formats that get translated to %s with warning
badList = ["t", "z"]
for b in badList:
    _fDispatch[b] = _badConv

# other cases
_fDispatch["r"] = _rConv
_fDispatch["w"] = _wConv
_fDispatch["h"] = _hConv
_fDispatch["m"] = _hConv
_fDispatch["H"] = _hConv
_fDispatch["M"] = _hConv

del badList, b


@handleRedirAndSaveKwds
def printf(format, *args):
    """Formatted print function"""
    # make argument list mutable
    args = list(args)
    newformat = []
    # find all format strings and translate them (and arg) if needed
    iend = 0
    mm = _reFormat.search(format, iend)
    i = 0
    while mm:
        oend = iend
        istart = mm.start()
        iend = mm.end()
        # append the stuff preceding the format
        newformat.append(format[oend:istart])
        c = mm.group('c')
        # special handling for INDEF arguments
        if args[i] == INDEF and c != 'w':
            # INDEF always gets printed as string except for '%w' format
            f = _quietConv
        else:
            # dispatch function for this format type
            f = _fDispatch[c]
        if f is None:
            # append the format
            newformat.append(mm.group())
        else:
            w = mm.group('w')
            d = mm.group('d')
            # ugly special case for 'r' format
            if c == 'r':
                c = format[iend - 1:iend + 1]
                iend = iend + 1
            # append the modified format
            newformat.append(f(w, d, c, args, i))
        mm = _reFormat.search(format, iend)
        i = i + 1
    newformat.append(format[iend:])
    format = ''.join(newformat)
    # finally ready to print
    try:
        _sys.stdout.write(format % tuple(args))
        _sys.stdout.flush()
    except ValueError as e:
        raise IrafError(str(e))
    except TypeError as e:
        raise IrafError(f'{str(e)}\nFormat/datatype mismatch in printf '
                        f'(format is {repr(format)})')


# _backDir is previous working directory

_backDir = None


@handleRedirAndSaveKwds
def pwd():
    """Print working directory"""
    print(_os.getcwd())


@handleRedirAndSaveKwds
def chdir(directory=None):
    """Change working directory"""
    global _backDir
    try:
        _newBack = _os.getcwd()
    except OSError:
        # OSError for getcwd() means current directory does not exist
        _newBack = _backDir
    if directory is None:
        # use startup directory as home if argument is omitted
        directory = userWorkingHome
    if not isinstance(directory, str):
        raise IrafError("Illegal non-string value for directory:" +
                        +repr(directory))
    if Verbose > 2:
        print('chdir to: ' + str(directory))
    # Check for (1) local directory and (2) iraf variable
    # when given an argument like 'dev'.  In IRAF 'cd dev' is
    # the same as 'cd ./dev' if there is a local directory named
    # dev but is equivalent to 'cd dev$' if there is no local
    # directory.
    try:
        edir = Expand(directory)
        _os.chdir(edir)
        _backDir = _newBack
        _irafexecute.processCache.setenv(f'chdir {edir}\n')
    except (IrafError, OSError):
        try:
            edir = Expand(directory + '$')
            _os.chdir(edir)
            _backDir = _newBack
            _irafexecute.processCache.setenv(f'chdir {edir}\n')
        except (IrafError, OSError):
            raise IrafError(f"Cannot change directory to `{directory}'")


cd = chdir


@handleRedirAndSaveKwds
def back():
    """Go back to previous working directory"""
    global _backDir
    if _backDir is None:
        raise IrafError("no previous directory for back()")
    try:
        _newBack = _os.getcwd()
    except OSError:
        # OSError for getcwd() means current directory does not exist
        _newBack = _backDir
    _os.chdir(_backDir)
    print(_backDir)
    _irafexecute.processCache.setenv(f'chdir {_backDir}\n')
    _backDir = _newBack


def error(errno=0, errmsg='', task="error", _save=False, suppress=True):
    """Print error message"""
    e = IrafError(f"ERROR: {errmsg}\n",
                  errno=errno,
                  errmsg=errmsg,
                  errtask=task)
    e._ecl_suppress_first_trace = suppress
    raise e


def errno(_save=None):
    """Returns status from last call to error()"""
    return irafecl._ecl_parent_task().DOLLARerrno


errcode = errno


def errmsg(_save=None):
    """Returns message from last call to error()"""
    irafecl._ecl_parent_task().DOLLARerrmsg


def errtask(_save=None):
    """Returns task from last call to error()"""
    return irafecl._ecl_parent_task().DOLLARerrtask


# -----------------------------------------------------
# clCompatibilityMode: full CL emulation (with Python
# syntax accessible only through !P escape)
# -----------------------------------------------------

_exitCommands = {
    "logout": 1,
    "exit": 1,
    "quit": 1,
    ".exit": 1,
}


def clCompatibilityMode(verbose=0, _save=0):
    """Start up full CL-compatibility mode"""

    import traceback
    import __main__

    if verbose:
        vmode = ' (verbose)'
    else:
        vmode = ''
    print(f'Entering CL-compatibility{vmode} mode...')

    # logging may be active if Monty is in use
    if hasattr(__main__, '_pycmdline'):
        logfile = __main__._pycmdline.logfile
    else:
        logfile = None

    theLocals = {}
    local_vars_dict = {}
    local_vars_list = []
    # initialize environment
    exec('from pyraf import iraf', theLocals)
    exec('from pyraf.irafpar import makeIrafPar', theLocals)
    exec('from stsci.tools.irafglobals import *', theLocals)
    exec('from pyraf.pyrafglobals import *', theLocals)
    exec('from pyraf.irafecl import EclState', theLocals)
    prompt2 = '>>> '
    while (1):
        try:
            if not _sys.stdin.isatty():
                prompt = ''
            elif loadedPath:
                prompt = loadedPath[-1].getName()[:2] + '> '
            else:
                prompt = 'cl> '
            line = input(prompt)
            # simple continuation escape handling
            while line[-1:] == '\\':
                line = line + '\n' + input(prompt2)
            line = line.strip()
            if line in _exitCommands:
                break
            elif line[:2] == '!P':
                # Python escape -- execute Python code
                exec(line[2:].strip(), theLocals)
            elif line and (line[0] != '#'):
                code = clExecute(line,
                                 locals=theLocals,
                                 mode='single',
                                 local_vars_dict=local_vars_dict,
                                 local_vars_list=local_vars_list)
                if logfile is not None:
                    # log CL code as comment
                    cllines = line.split('\n')
                    for oneline in cllines:
                        logfile.write('# ' + oneline + '\n')
                    logfile.write(code)
                    logfile.flush()
                if verbose:
                    print('----- Python -----')
                    print(code, end=' ')
                    print('------------------')
        except EOFError:
            break
        except KeyboardInterrupt:
            _writeError(
                "Use `logout' or `.exit' to exit CL-compatibility mode")
        except:
            _sys.stdout.flush()
            traceback.print_exc()
    print()
    print('Leaving CL-compatibility mode...')


# -----------------------------------------------------
# clArray: IRAF array class with type checking
# Note that subscripts start zero, in Python style --
# the CL-to-Python translation takes care of the offset
# in CL code, and Python code should use zero-based
# subscripts.
# -----------------------------------------------------


def clArray(array_size,
            datatype,
            name="<anonymous>",
            mode="h",
            min=None,
            max=None,
            enum=None,
            prompt=None,
            init_value=None,
            strict=0):
    """Create an IrafPar object that can be used as a CL array"""
    try:
        return _irafpar.makeIrafPar(init_value,
                                    name=name,
                                    datatype=datatype,
                                    mode=mode,
                                    min=min,
                                    max=max,
                                    enum=enum,
                                    prompt=prompt,
                                    array_size=array_size,
                                    strict=strict)
    except ValueError as e:
        raise ValueError(f"Error creating Cl array `{name}'\n{str(e)}")


# -----------------------------------------------------
# clExecute: execute a single cl statement
# -----------------------------------------------------

# count number of CL tasks currently executing
# used to give unique name to each one
_clExecuteCount = 0


def clExecute(s,
              locals=None,
              mode="proc",
              local_vars_dict=None,
              local_vars_list=None,
              verbose=0,
              **kw):
    """Execute a single cl statement"""
    # handle redirection keywords

    redirKW, closeFHList = redirProcess(kw)
    if len(kw):
        raise TypeError('unexpected keyword argument: ' +
                        repr(list(kw.keys())))
    resetList = redirApply(redirKW)
    try:
        global _clExecuteCount
        _clExecuteCount = _clExecuteCount + 1
        pycode = _cl2py.cl2py(string=s,
                              mode=mode,
                              local_vars_dict=local_vars_dict,
                              local_vars_list=local_vars_list)
        # use special scriptname
        taskname = f"CL{_clExecuteCount}"
        scriptname = f"<CL script {taskname}>"
        code = pycode.code.lstrip()  # XXX needed?
        #       DBG('*'*80)
        #       DBG('pycode for task,script='+str((taskname,scriptname,))+':\n'+code)
        #       DBG('*'*80)
        # force compile to inherit future division so we don't rely on 2.x div.
        codeObject = compile(code, scriptname, 'exec', 0, 0)
        # add this script to linecache
        codeLines = code.split('\n')
        _linecache.cache[scriptname] = (0, 0, codeLines, taskname)
        if locals is None:
            locals = {}
        exec(codeObject, locals)
        if pycode.vars.proc_name:
            exec(pycode.vars.proc_name + "(taskObj=iraf.cl)", locals)
        return code
    finally:
        _clExecuteCount = _clExecuteCount - 1
        # note return value not used
        rv = redirReset(resetList, closeFHList)


def clLineToPython(line):
    """Returns the Python code corresponding to a single cl statement."""
    pycode = _cl2py.cl2py(string=line,
                          mode='single',
                          local_vars_dict={},
                          local_vars_list=[])
    code = pycode.code
    if pycode.vars.proc_name:
        code += pycode.vars.proc_name + "(taskObj=iraf.cl)\n"
    return code.lstrip()


# -----------------------------------------------------
# Expand: Expand a string with embedded IRAF variables
# (IRAF virtual filename)
# -----------------------------------------------------

# Input string is in format 'name$rest' or 'name$str(name2)' where
# name and name2 are defined in the _varDict dictionary.  The
# name2 string may have embedded dollar signs, which are ignored.
# There may be multiple embedded parenthesized variable names.
#
# Returns string with IRAF variable name expanded to full host name.
# Input may also be a comma-separated list of strings to Expand,
# in which case an expanded comma-separated list is returned.

# search for leading string without embedded '$'
__re_var_match = _re.compile(r'(?P<varname>[^$]*)\$')

# search for string embedded in parentheses
__re_var_paren = _re.compile(r'\((?P<varname>[^()]*)\)')


def Expand(instring, noerror=0):
    """Expand a string with embedded IRAF variables (IRAF virtual filename)

    Allows comma-separated lists.  Also uses os.path.expanduser to
    replace '~' symbols.
    Set noerror flag to silently replace undefined variables with just
    the variable name or null (so Expand('abc$def') = 'abcdef' and
    Expand('(abc)def') = 'def').  This is the IRAF behavior, though it
    is confusing and hides errors.
    """
    # call _expand1 for each entry in comma-separated list
    wordlist = instring.split(",")
    outlist = []
    for word in wordlist:
        outlist.append(_os.path.expanduser(_expand1(word, noerror=noerror)))
    return ",".join(outlist)


def _expand1(instring, noerror):
    """Expand a string with embedded IRAF variables (IRAF virtual filename)"""
    # first expand names in parentheses
    # note this works on nested names too, expanding from the
    # inside out (just like IRAF)
    mm = __re_var_paren.search(instring)
    while mm is not None:
        # remove embedded dollar signs from name
        varname = mm.group('varname').replace('$', '')
        if defvar(varname):
            varname = envget(varname)
        elif noerror:
            varname = ""
        else:
            raise IrafError(f"Undefined variable `{varname}' "
                            f"in string `{instring}'")
        instring = instring[:mm.start()] + varname + instring[mm.end():]
        mm = __re_var_paren.search(instring)
    # now expand variable name at start of string
    mm = __re_var_match.match(instring)
    if mm is None:
        return instring
    varname = mm.group('varname')
    if defvar(varname):
        # recursively expand string after substitution
        return _expand1(envget(varname) + instring[mm.end():], noerror)
    elif noerror:
        return _expand1(varname + instring[mm.end():], noerror)
    else:
        raise IrafError(f"Undefined variable `{varname}' "
                        f"in string `{instring}'")


def IrafTaskFactory(prefix='',
                    taskname=None,
                    suffix='',
                    value=None,
                    pkgname=None,
                    pkgbinary=None,
                    redefine=0,
                    function=None):
    """Returns a new or existing IrafTask, IrafPset, or IrafPkg object

    Type of returned object depends on value of suffix and value.

    Returns a new object unless this task or package is already
    defined. In that case if the old task appears consistent with
    the new task, a reference to the old task is returned.
    Otherwise a warning is printed and a reference to a new task is
    returned.

    If redefine keyword is set, the behavior is the same except
    a warning is printed if it does *not* exist.
    """

    module = irafecl.getTaskModule()

    if pkgname is None:
        pkgname = curpack()
        if pkgbinary is None:
            pkgbinary = curPkgbinary()
    elif pkgbinary is None:
        pkgbinary = ''
    # fix illegal names
    spkgname = pkgname.replace('.', '_')
    if spkgname != pkgname:
        _writeError("Warning: `.' illegal in package name, changing "
                    f"`{pkgname}' to `{spkgname}'")
        pkgname = spkgname

    staskname = taskname.replace('.', '_')
    if staskname != taskname:
        _writeError("Warning: `.' illegal in task name, changing "
                    f"`{taskname}' to `{staskname}'")
        taskname = staskname

    if suffix == '.pkg':
        return IrafPkgFactory(prefix,
                              taskname,
                              suffix,
                              value,
                              pkgname,
                              pkgbinary,
                              redefine=redefine)

    root, ext = _os.path.splitext(value)
    if ext == '.par' and function is None:
        return IrafPsetFactory(prefix,
                               taskname,
                               suffix,
                               value,
                               pkgname,
                               pkgbinary,
                               redefine=redefine)

    # normal task definition

    fullname = pkgname + '.' + taskname
    # existing task object (if any)
    task = _tasks.get(fullname)
    if task is None and redefine:
        _writeError(f"Warning: `{taskname}' is not a defined task")

    if function is not None:
        newtask = module.IrafPythonTask(prefix,
                                        taskname,
                                        suffix,
                                        value,
                                        pkgname,
                                        pkgbinary,
                                        function=function)
    elif ext == '.cl':
        newtask = module.IrafCLTask(prefix, taskname, suffix, value, pkgname,
                                    pkgbinary)
    elif value[:1] == '$':
        newtask = module.IrafForeignTask(prefix, taskname, suffix, value,
                                         pkgname, pkgbinary)
    else:
        newtask = module.IrafTask(prefix, taskname, suffix, value, pkgname,
                                  pkgbinary)
    if task is not None:
        # check for consistency of definition by comparing to the
        # new object
        if not task.isConsistent(newtask):
            # looks different -- print warning and continue
            if not redefine:
                _writeError(f"Warning: `{fullname}' is a task redefinition")
        else:
            # new task is consistent with old task, so return old task
            if task.getPkgbinary() != newtask.getPkgbinary():
                # package binary differs -- add it to search path
                if Verbose > 1:
                    print('Adding', pkgbinary, 'to', task, 'path')
                task.addPkgbinary(pkgbinary)
            return task
    # add it to the task list
    _addTask(newtask)
    return newtask


def IrafPsetFactory(prefix,
                    taskname,
                    suffix,
                    value,
                    pkgname,
                    pkgbinary,
                    redefine=0):
    """Returns a new or existing IrafPset object

    Returns a new object unless this task is already
    defined. In that case if the old task appears consistent with
    the new task, a reference to the old task is returned.
    Otherwise a warning is printed and a reference to a new task is
    returned.

    If redefine keyword is set, the behavior is the same except
    a warning is printed if it does *not* exist.
    """

    module = irafecl.getTaskModule()

    fullname = pkgname + '.' + taskname
    task = _tasks.get(fullname)
    if task is None and redefine:
        _writeError(f"Warning: `{taskname}' is not a defined task")

    newtask = module.IrafPset(prefix, taskname, suffix, value, pkgname,
                              pkgbinary)
    if task is not None:
        # check for consistency of definition by comparing to the new
        # object (which will be discarded)
        if task.getFilename() != newtask.getFilename():
            if redefine:
                _writeError(f"Warning: `{fullname}' is a task redefinition")
        else:
            # old version of task is same as new
            return task
    # add it to the task list
    _addTask(newtask)
    return newtask


def IrafPkgFactory(prefix,
                   taskname,
                   suffix,
                   value,
                   pkgname,
                   pkgbinary,
                   redefine=0):
    """Returns a new or existing IrafPkg object

    Returns a new object unless this package is already defined, in which case
    a warning is printed and a reference to the existing task is returned.
    Redefine parameter currently ignored.

    Returns a new object unless this package is already
    defined. In that case if the old package appears consistent with
    the new package, a reference to the old package is returned.
    Else if the old package has already been loaded, a warning
    is printed and the redefinition is ignored.
    Otherwise a warning is printed and a reference to a new package is
    returned.

    If redefine keyword is set, the behavior is the same except
    a warning is printed if it does *not* exist.
    """

    module = irafecl.getTaskModule()

    # does package with exactly this name exist in minimum-match
    # dictionary _pkgs?
    pkg = _pkgs.get_exact_key(taskname)
    if pkg is None and redefine:
        _writeError(f"Warning: `{taskname}' is not a defined task")
    newpkg = module.IrafPkg(prefix, taskname, suffix, value, pkgname,
                            pkgbinary)
    if pkg is not None:
        if pkg.getFilename() != newpkg.getFilename() or \
           pkg.hasParfile()  != newpkg.hasParfile():
            if pkg.isLoaded():
                _writeError("Warning: currently loaded package "
                            f"`{taskname}' was not redefined")
                return pkg
            else:
                if not redefine:
                    _writeError(f"Warning: `{taskname}' is a task redefinition")
                _addPkg(newpkg)
                return newpkg
        if pkg.getPkgbinary() != newpkg.getPkgbinary():
            # only package binary differs -- add it to search path
            if Verbose > 1:
                print('Adding', pkgbinary, 'to', pkg, 'path')
            pkg.addPkgbinary(pkgbinary)
        if pkgname != pkg.getPkgname():
            # add existing task as an item in the new package
            _addTask(pkg, pkgname=pkgname)
        return pkg
    _addPkg(newpkg)
    return newpkg


# -----------------------------------------------------
# Utilities to handle I/O redirection keywords
# -----------------------------------------------------


def redirProcess(kw):
    """Process Stdout, Stdin, Stderr keywords used for redirection

    Removes the redirection keywords from kw
    Returns (redirKW, closeFHList) which are a dictionary of
    the filehandles for stdin, stdout, stderr and a list of
    filehandles to close after execution.

    Image and Stdplot redirection not handled (but it isn't clear that these
    are ever used anyway)
    """

    redirKW = {}
    closeFHList = []
    # Dictionary of redirection keywords
    # Values are (outputFlag, standardName, openArgs)
    # Still need to add graphics redirection keywords
    redirDict = {
        'Stdin': (0, "stdin", "r"),
        'Stdout': (1, "stdout", "w"),
        'StdoutAppend': (1, "stdout", "a"),
        'Stderr': (1, "stderr", "w"),
        'StderrAppend': (1, "stderr", "a"),
        'StdoutG': (1, "stdgraph", "wb"),
        'StdoutAppendG': (1, "stdgraph", "ab")
    }
    # Magic values that trigger special behavior
    magicValues = {"STDIN": 1, "STDOUT": 1, "STDERR": 1}

    PipeOut = None
    for key in redirDict.keys():
        if key in kw:
            outputFlag, standardName, openArgs = redirDict[key]
            # if it is a string, open as a file
            # otherwise assume it is a filehandle
            value = kw[key]
            if isinstance(value, str):
                if value in magicValues:
                    if outputFlag and value == "STDOUT":
                        fh = _sys.__stdout__
                    elif outputFlag and value == "STDERR":
                        fh = _sys.__stderr__
                    elif (not outputFlag) and value == "STDIN":
                        fh = _sys.__stdin__
                    else:
                        # IRAF doesn't raise an exception here (e.g., on
                        # input redirection from "STDOUT"), but it should
                        raise OSError(f"Illegal value `{value}' for "
                                      f"{key} redirection")
                else:
                    # expand IRAF variables
                    value = Expand(value)
                    if outputFlag:
                        # output file
                        # check to see if it is dev$null
                        if isNullFile(value):
                            if _sys.platform.startswith('win'):
                                value = 'NUL'
                            else:
                                value = '/dev/null'
                        elif "w" in openArgs and \
                                envget("clobber", "") != yes and \
                                _os.path.exists(value):
                            # don't overwrite unless clobber is set
                            raise OSError(f"Output file `{value}' already exists")
                    fh = open(value, openArgs)
                    # close this when we're done
                    closeFHList.append(fh)
            elif isinstance(value, int):
                # integer is OK for output keywords -- it indicates
                # that output should be captured and returned as
                # function value
                if not outputFlag:
                    raise IrafError(f"{key} redirection must be from a file "
                                    f"handle or string\nValue is `{value}'")
                if not value:
                    fh = None
                else:
                    if PipeOut is None:
                        # several outputs can be written to same buffer
                        # (e.g. Stdout=1, Stderr=1 is legal)
                        PipeOut = _io.StringIO()
                        # stick this in the close list too so we know that
                        # output should be returned
                        # wrap it in a tuple to make it easy to recognize
                        closeFHList.append((PipeOut,))
                    fh = PipeOut
            elif isinstance(value, (list, tuple)):
                # list/tuple of strings is OK for input
                if outputFlag:
                    raise IrafError(f"{key} redirection must be to a file "
                                    f"handle or string\nValue is type {value}")
                try:
                    if value and value[0][-1:] == '\n':
                        s = ''.join(value)
                    elif value:
                        s = '\n'.join(value) + '\n'
                    else:
                        # empty value means null input
                        s = ''
                    fh = _io.StringIO(s)
                    # close this when we're done
                    closeFHList.append(fh)
                except TypeError:
                    raise IrafError(f"{key} redirection must be from a "
                                    "sequence of strings\n")
            else:
                # must be a file handle
                if outputFlag:
                    if not hasattr(value, 'write'):
                        raise IrafError(f"{key} redirection must be to a file "
                                        f"handle or string\nValue is `{value}'")
                elif not hasattr(value, 'read'):
                    raise IrafError(f"{key} redirection must be from a file "
                                    f"handle or string\nValue is `{value}'")
                fh = value
            if fh is not None:
                redirKW[standardName] = fh
            del kw[key]
    # Now handle IRAF semantics for redirection of stderr to mean stdout
    # also redirects to stderr file handle if Stdout not also specified
    if 'stderr' in redirKW and 'stdout' not in redirKW:
        redirKW['stdout'] = redirKW['stderr']
    return redirKW, closeFHList


def redirApply(redirKW):
    """Modify _sys.stdin, stdout, stderr using the redirKW dictionary

    Returns a list of the original filehandles so they can be
    restored (by redirReset)
    """

    sysDict = {'stdin': 1, 'stdout': 1, 'stderr': 1}
    resetList = []
    for key, value in redirKW.items():
        if key in sysDict:
            resetList.append((key, getattr(_sys, key)))
            setattr(_sys, key, value)
        elif key == 'stdgraph':
            resetList.append((key, gki.kernel))
            gki.kernel = gki.GkiRedirection(value)
    return resetList


def redirReset(resetList, closeFHList):
    """Restore _sys.stdin, stdout, stderr to their original values

    Also closes the filehandles in closeFHList.  If a tuple with a
    StringIO pipe is included in closeFHList, that means the value
    should be returned as the return value of the function.
    Returns an array of lines (without newlines.)
    """
    PipeOut = None
    for fh in closeFHList:
        if isinstance(fh, tuple):
            PipeOut = fh[0]
        else:
            fh.close()
    for key, value in resetList:
        if key == 'stdgraph':
            gki.kernel = value
        else:
            setattr(_sys, key, value)
    if PipeOut is not None:
        # unfortunately io.StringIO has no readlines method:
        # PipeOut.seek(0)
        # rv = PipeOut.readlines()
        rv = PipeOut.getvalue().split('\n')
        PipeOut.close()
        # delete trailing null value
        if rv[-1] == '':
            del rv[-1]
        return rv
