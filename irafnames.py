"""module irafnames.py -- define how names of IRAF packages and tasks get
included in the user's namespace.  Uses a plug-in strategy so behavior can
be changed.

$Id$

R. White, 1999 March 26
"""

import __main__
import iraf

# base class for namespace strategy

class IrafNameStrategy:
	def addTask(self,task):
		pass
	def addPkg(self,pkg):
		pass

# NameClean implementation does nothing with either tasks or packages

class IrafNameClean(IrafNameStrategy):
	pass

# IrafNamePkg adds packages to name space

class IrafNamePkg(IrafNameStrategy):
	def addTask(self,task):
		pass
	def addPkg(self,pkg):
		d = __main__.__dict__
		pkgname = pkg.getName()
		p = d.get(pkgname)
		if (not p) or isinstance(p,iraf.IrafPkg):
			d[pkgname] = pkg
		else:
			if iraf.verbose:
				print "Warning: variable " +  pkgname + \
					" was not redefined as IrafPkg"

# IrafNameTask puts everything (tasks and packages) in name space

class IrafNameTask(IrafNamePkg):
	def addTask(self,task):
		d = __main__.__dict__
		taskname = task.getName()
		p = d.get(taskname)
		if (not p) or isinstance(p,iraf.IrafTask):
			d[taskname] = task
		else:
			if iraf.verbose:
				print "Warning: variable " +  taskname + \
					" was not redefined as IrafTask"

# define adding package names as the default behavior

strategy = IrafNamePkg()

def setPkgStrategy():
	global strategy
	strategy = IrafNamePkg()

def setTaskStrategy():
	global strategy
	strategy = IrafNameTask()

def setCleanStrategy():
	global strategy
	strategy = IrafNameClean()

