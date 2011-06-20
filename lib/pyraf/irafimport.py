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
from __future__ import division # confidence high

import __builtin__
import sys
from stsci.tools import minmatch

_importHasLvlArg = sys.version_info[0] > 2 or sys.version_info[1] >= 5 # no 1.*
_reloadIsBuiltin = sys.version_info[0] < 3

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

#   print("% % % > "+name+", "+str(fromlist)+", "+str(level))

    # e.g. "from iraf import stsdas, noao" or "from .iraf import noao"
    if fromlist and (name in ["iraf", "pyraf.iraf", ".iraf"]):
        for task in fromlist:
            pkg = iraf.getPkg(task,found=1)
            if pkg is not None and not pkg.isLoaded():
                pkg.run(_doprint=0, _hush=1)
        # must return a module for 'from' import
        return _irafModuleProxy.module
    # e.g. "import iraf" or "from . import iraf"
    elif (name == "iraf") or (name=='' and level==1 and \
         fromlist and 'iraf' in fromlist and len(fromlist)==1):
        return _irafModuleProxy
    # e.g. "import sys" or "import stsci.tools.alert"
    # e.g. Note! "import os, sys, re, glob" calls this 4 separate times, but
    #            "from . import gki, gwm, iraf" is only a single call here!
    else:
        # !!! TEMPORARY KLUDGE !!! working on why seeing pyraf.minmatch in cache
        if   name == 'pyraf.minmatch':  name = 'stsci.tools.minmatch'
        elif name == 'pyraf.irafutils': name = 'stsci.tools.irafutils'
        elif name == 'pyraf.dialog':    name = 'stsci.tools.dialog'
        elif name == 'pyraf.listdlg':   name = 'stsci.tools.listdlg'
        elif name == 'pyraf.filedlg':   name = 'stsci.tools.filedlg'
        elif name == 'pyraf.alert':     name = 'stsci.tools.alert'
        elif name == 'pyraf.irafglobals': name='stsci.tools.irafglobals' # is diffnt
        # Not planning to fix this until after 'pytools' is renamed.
        # TODO: Well, pytools has been renamed :)  Not exactly clear what the
        # problem is here though...
        # !!! END TEMPORARY KLUDGE !!!

        hadIrafInList = False
        if fromlist and 'iraf' in fromlist and name == '' and level > 0:
            fromlist = tuple([j for j in fromlist if j != 'iraf'])
            hadIrafInList = True

        if _importHasLvlArg:
            retval = _originalImport(name, globals, locals, fromlist, level)
        else:
            # we could assert here that level == -1, but it's safe to assume
            retval = _originalImport(name, globals, locals, fromlist)

        if hadIrafInList:
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
        global iraf
        self.__dict__['module'] = iraf
        self.__dict__['__name__'] = iraf.__name__
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
iraf = _originalImport('iraf', globals(), locals(), [])
