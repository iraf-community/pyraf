"""module irafnames.py -- define how names of IRAF packages and tasks get
included in the user's namespace.  Uses a plug-in strategy so behavior can
be changed.

$Id$

R. White, 1999 March 26
"""

import __main__
import iraf, iraftask

def _addName(task, module):
	"""Add a task object to the module namespace

	Skip if there is a collision with another name
	"""
	name = task.getName()
	d = module.__dict__
	p = d.get(name)
	if (not p) or isinstance(p, iraftask.IrafTask):
		d[name] = task
	else:
		if iraf.Verbose>0:
			print "Warning: " + module.__name__ + "." + \
				name + " was not redefined as Iraf Task"

# Basic namespace strategy class (does nothing)

class IrafNameStrategy:
	def addTask(self,task):
		pass
	def addPkg(self,pkg):
		pass

# NameClean implementation puts tasks and packages in iraf module name space
# Note that since packages are also tasks, we only need to do this for tasks

class IrafNameClean(IrafNameStrategy):
	def addTask(self,task):
		_addName(task, iraf)

# IrafNamePkg also adds packages to __main__ name space

class IrafNamePkg(IrafNameClean):
	def addPkg(self,pkg):
		_addName(pkg, __main__)

# IrafNameTask puts everything (tasks and packages) in __main__ name space

class IrafNameTask(IrafNameClean):
	def addTaskHook(self,task):
		_addName(task, iraf)
		_addName(task, __main__)

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

