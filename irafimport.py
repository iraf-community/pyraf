# modify import mechanism so that
# (1) 'from iraf import pkg' automatically loads the IRAF package 'pkg'
# (2) 'import iraf' returns a wrapped module instance that allows minimum-match
#		access to task names (e.g. iraf.imhead, not just iraf.imheader)
#
# Assumes that all IRAF tasks and packages are accessible as iraf module attributes

import iraf
import __builtin__
from ldir import ldir

def _irafImport(name, globals={}, locals={}, fromlist=[]):
	if name == "iraf":
		if fromlist:
			for task in fromlist:
				pkg = iraf.getPkg(task,found=1)
				if pkg and not pkg.getLoaded():
					pkg.run(_doprint=0, _hush=1)
			# must return a module for 'from' import
			return _irafModuleProxy.module
		else:
			return _irafModuleProxy
	else:
		return _originalImport(name, globals, locals, fromlist)

def _irafReload(module):
	if isinstance(module, _irafModuleClass):
		#XXX Not sure this is correct
		module.module = _originalReload(module.module)
		return module
	else:
		return _originalReload(module)

class _irafModuleClass:
	"""Proxy for iraf module that makes tasks appear as attributes"""
	def __init__(self, module):
		self.module = module
		self.__name__ = module.__name__
	def __getattr__(self, attr):
		# first try getting this attribute directly from the usual module 
		try:
			return getattr(self.module, attr)
		except AttributeError:
			pass
		# if that fails, try getting a task with this name
		try:
			return self.module.getTask(attr)
		except KeyError:
			raise AttributeError(attr)

_irafModuleProxy = _irafModuleClass(iraf)

# Save the original hooks
_originalImport = __builtin__.__import__
_originalReload = __builtin__.reload

# Install our hooks
__builtin__.__import__ = _irafImport
__builtin__.reload = _irafReload
