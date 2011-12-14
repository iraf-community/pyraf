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

from __future__ import division  # confidence high

import imp
import sys

from stsci.tools import minmatch


def _find_module_in_package(fullname, path=None):
    parts = fullname.split('.')
    modname = fullmodname = parts.pop(0)
    while parts:
        if fullmodname in sys.modules:
            mod = sys.modules[fullmodname]
        else:
            fileobj, path, description = imp.find_module(modname, path)
            mod = imp.load_module(modname, fileobj, path, description)
        # If there are still parts remaining, mod should be a package:
        path = mod.__path__
        modname = parts.pop(0)
        fullmodname += '.' + modname
    return imp.find_module(modname, path)


class IrafImporter(object):
    def find_module(self, fullname, path=None):
        modname = None
        if fullname == 'pyraf.iraf':
            modname = 'pyraf.iraf'
        elif fullname == 'iraf':
            modname = 'pyraf.iraf'
        elif fullname == 'pytools':
            modname = 'stsci.tools'
        elif fullname.startswith('pytools.'):
            _, rest = fullname.split('.', 1)
            modname = 'stsci.tools.' + rest

        if modname is not None:
            return IrafLoader(modname, *_find_module_in_package(modname, path))


class IrafLoader(object):
    def __init__(self, fullname, fileobj, pathname, description):
        self.fullname = fullname
        self.fileobj = fileobj
        self.pathname = pathname
        self.description = description

    def load_module(self, modname):
        # The passed in module name is ignored--we use the module name we were
        # told to use...
        if self.fullname in sys.modules:
            return sys.modules[self.fullname]

        mod = imp.load_module(self.fullname, self.fileobj, self.pathname,
                              self.description)

        mod.__loader__ = self
        if self.fullname == 'pyraf.iraf':
            mod = _IrafModuleProxy(mod)
            sys.modules['pyraf.iraf'] = mod
        elif self.fullname == 'stsci.tools':
            sys.modules['pytools'] = mod
        elif self.fullname.startswith('stsci.tools.'):
            _, _, rest = self.fullname.split('.', 2)
            sys.modules['pytools.' + rest] = mod

        return mod


class _IrafModuleProxy(object):
    """Proxy for iraf module that makes tasks appear as attributes"""

    __instance = None

    def __new__(cls, *args, **kwargs):
        if cls.__instance is not None:
            return cls.__instance

        return super(_IrafModuleProxy, cls).__new__(cls, *args, **kwargs)

    def __init__(self, module):
        self.mmdict = minmatch.MinMatchDict(vars(module))
        self.__name__ = module.__name__
        self.module = module

    def __repr__(self):
        return repr(self.module)

    def __getattr__(self, attr):
        from .iraftask import IrafPkg

        # first try getting this attribute directly from the usual module
        try:
            val = getattr(self.module, attr)
        except AttributeError:
            # if that fails, try getting a task with this name
            try:
                val = self.module.getTask(attr)
            except minmatch.AmbiguousKeyError, e:
                raise AttributeError(str(e))
            except KeyError, e:
                # last try is minimum match dictionary of rest of module
                # contents
                try:
                    val = self.mmdict[attr]
                except KeyError:
                    raise AttributeError("Undefined IRAF task `%s'" % (attr,))

        if isinstance(val, IrafPkg):
            val.run(_doprint=0, _hush=1)

        return val

    def __setattr__(self, attr, value):
        # add an attribute to the module itself
        if hasattr(self, 'module'):
            setattr(self.module, attr, value)
            self.mmdict.add(attr, value)
        else:
            super(_IrafModuleProxy, self).__setattr__(attr, value)

    def get_all_matches(self, taskname):
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


sys.meta_path.insert(0, IrafImporter())
