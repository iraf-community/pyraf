"""module irafimport.py -- modify import mechanism

Modify module import mechanism so that
(1) 'from iraf import pkg' automatically loads the IRAF package 'pkg'
(2) 'import iraf' returns a wrapped module instance that allows minimum-match
        access to task names (e.g. iraf.imhead, not just iraf.imheader)

Assumes that all IRAF tasks and packages are accessible as iraf
module attributes.  Only affects imports of iraf module.

$Id$

R. White, 1999 August 17
"""
from __future__ import absolute_import, division # confidence high

import __builtin__
import sys
from stsci.tools import minmatch

PY3K = sys.version_info[0] > 2
_importHasLvlArg = PY3K or sys.version_info[1] >= 5 # is 2.*, handle no 1.*
_reloadIsBuiltin = sys.version_info[0] < 3

IMPORT_DEBUG = False

# Save the original hooks;  replaced at bottom of module...
_originalImport = __builtin__.__import__
if _reloadIsBuiltin:
    _originalReload = __builtin__.reload
else:
    import imp
    _originalReload = imp.reload


def restoreBuiltins():
    """ Called before exiting pyraf - this puts import and reload back. """
    __builtin__.__import__ = _originalImport
    if _reloadIsBuiltin:
        __builtin__.reload = _originalReload
    else:
        imp.reload = _originalReload


def _irafImport(name, globals={}, locals={}, fromlist=[], level=-1):

    if IMPORT_DEBUG:
        print("irafimport called: "+name+", "+str(fromlist)+", "+str(level))

    # do first: the default value for level changed to 0 as of Python 3.3
    if PY3K and sys.version_info[1] >= 3 and level < 0:
        level = 0

    # e.g. "from iraf import stsdas, noao" or "from .iraf import noao"
    if fromlist and (name in ["iraf", "pyraf.iraf", ".iraf"]):
        for task in fromlist:
            pkg = the_iraf_module.getPkg(task,found=1)
            if pkg is not None and not pkg.isLoaded():
                pkg.run(_doprint=0, _hush=1)
        # must return a module for 'from' import
        if IMPORT_DEBUG:
            print("irafimport: case: from "+name+" import "+str(fromlist))
        return _irafModuleProxy.module

    # e.g. "import iraf" or "from . import iraf" (fromlist is a list OR tuple)
    # (extra Python2 cases are not used in PY3K - double check this)
    if (PY3K and not fromlist and name == 'iraf') or \
       ((not PY3K) and (name == "iraf")) or \
       ((not PY3K) and name=='' and level==1 and len(fromlist)==1 and 'iraf' in fromlist):
        if IMPORT_DEBUG:
            print("irafimport: iraf case: n="+name+", fl="+str(fromlist)+ \
                  ", l="+str(level))
        return _irafModuleProxy

    # e.g. "import pyraf.iraf" (return module is for pyraf, not iraf)
    if not fromlist and name == 'pyraf.iraf' and level == 0:
        assert 'pyraf' in sys.modules, 'Unexpected import error - contact STScI'
        if IMPORT_DEBUG:
            print("irafimport: pyraf.iraf case: n="+name+", fl="+str(fromlist)+
                  ", l="+str(level)+", will modify pyraf module")
        # builtin import below will return pyraf module, after having set up an
        # attr of it called 'iraf' which is the iraf module.  Instead we want
        # to set the attr to be our proxy (this case maybe unused in Python 2).
        retval = sys.modules['pyraf']
        retval.iraf = _irafModuleProxy
        return retval

    # ALL OTHER CASES (PASS-THROUGH)
    # e.g. "import sys" or "import stsci.tools.alert"
    # e.g. "import pyraf" or "from pyraf import wutil, gki"
    # e.g. Note! "import os, sys, re, glob" calls this 4 separate times, but
    #            "from . import gki, gwm, iraf" is only a single call here!

    # !!! TEMPORARY KLUDGE !!! keep this code until cache files are updated
    if name:
        for module in ['minmatch', 'irafutils', 'dialog', 'listdlg',
                       'filedlg', 'alert', 'irafglobals']:
            if name == ('pyraf.%s' % module):
                name = 'stsci.tools.%s' % module
        # Replace any instances of 'pytools' with 'stsci.tools' -- the
        # new name of the former pytools package
        name = name.replace('pytools.', 'stsci.tools.')

    # Same for everything in fromlist (which is a tuple in PY3K)
    if fromlist:
        fromlist = tuple([item.replace('pytools', 'stsci.tools')
                         for item in fromlist])
    # !!! END TEMPORARY KLUDGE !!!

    hadIrafInList = fromlist and 'iraf' in fromlist and name=='' and level>0

    if IMPORT_DEBUG:
        print("irafimport - PASSTHRU: n="+name+", fl="+str(fromlist)+", l="+
              str(level))
    if _importHasLvlArg:
        retval = _originalImport(name, globals, locals, fromlist, level)
    else:
        # we could assert here that level is default, but it's safe to assume
        retval = _originalImport(name, globals, locals, fromlist)

    if hadIrafInList:
        # Use case is: "from . import gki, gwm, iraf"
        # Overwrite with our proxy (see pyraf.iraf case)
        retval.__setattr__('iraf', _irafModuleProxy)

    return retval


def _irafReload(module):
    if isinstance(module, _irafModuleClass):
        #XXX Not sure this is correct
        module.module = _originalReload(module.module)
        return module
    else:
        return _originalReload(module)


class _irafModuleClass:
    """Proxy for iraf module that makes tasks appear as attributes"""
    def __init__(self):
        self.__dict__['module'] = None

    def _moduleInit(self):
        global the_iraf_module
        self.__dict__['module'] = the_iraf_module
        self.__dict__['__name__'] = the_iraf_module.__name__
        # create minmatch dictionary of current module contents
        self.__dict__['mmdict'] = minmatch.MinMatchDict(vars(self.module))

    def __getattr__(self, attr):
        if self.module is None: self._moduleInit()
        # first try getting this attribute directly from the usual module
        try:
            return getattr(self.module, attr)
        except AttributeError:
            pass
        # if that fails, try getting a task with this name
        try:
            return self.module.getTask(attr)
        except minmatch.AmbiguousKeyError, e:
            raise AttributeError(str(e))
        except KeyError, e:
            pass
        # last try is minimum match dictionary of rest of module contents
        try:
            return self.mmdict[attr]
        except KeyError:
            raise AttributeError("Undefined IRAF task `%s'" % (attr,))

    def __setattr__(self, attr, value):
        # add an attribute to the module itself
        setattr(self.module, attr, value)
        self.mmdict.add(attr, value)

    def getAllMatches(self, taskname):
        """Get list of names of all tasks that may match taskname

        Useful for command completion.
        """
        if self.module is None: self._moduleInit()
        if taskname == "":
            matches = self.mmdict.keys()
        else:
            matches = self.mmdict.getallkeys(taskname, [])
        matches.extend(self.module.getAllTasks(taskname))
        return matches


# Install our hooks
__builtin__.__import__ = _irafImport
if _reloadIsBuiltin:
    __builtin__.reload = _irafReload
else:
    imp.reload = _irafReload

# create the module proxy
_irafModuleProxy = _irafModuleClass()

# import iraf module using original mechanism
if PY3K:
    # necessary as of Python 3.3+ :  try "import pyraf.iraf"
    pyrafmod = _originalImport('pyraf.iraf', globals(), locals(), [])
    the_iraf_module = pyrafmod.iraf
else:
    the_iraf_module = _originalImport('iraf', globals(), locals(), [])
 
# leaving
if IMPORT_DEBUG:
    print("irafimport: passed final import")
