"""module iraffunctions.py -- IRAF emulation tasks and functions

This is not usually used directly -- the relevant public classes and
functions get included in iraf.py.  The implementations are kept here
to avoid possible problems with name conflicts in iraf.py (which is the
home for all the IRAF task and package names.)  Private routines have
names beginning with '_' and do not get imported by the iraf module.

The exception is that iraffunctions can be used directly for modules
that must be compiled and executed early, before the pyraf module
initialization is complete.

$Id$

R. White, 1999 December 20
"""

# define INDEF, yes, no, EOF, Verbose, IrafError, userIrafHome

from irafglobals import *

# -----------------------------------------------------
# setVerbose: set verbosity level
# -----------------------------------------------------

def setVerbose(value=1, **kw):
	"""Set verbosity level when running tasks
	
	Level 0 (default) prints almost nothing.
	Level 1 prints warnings.
	Level 2 prints info on progress.
	"""
	if type(value) is _types.StringType:
		try:
			value = int(value)
		except ValueError:
			pass
	Verbose.set(value)

def _writeError(msg):
	"""Write a message to stderr"""
	_sys.stdout.flush()
	_sys.stderr.write(msg)
	if msg[-1:] != "\n": _sys.stderr.write("\n")


# -----------------------------------------------------
# now it is safe to import other iraf modules
# -----------------------------------------------------

import sys, os, string, re, math, types, time
import minmatch, subproc, wutil
import irafnames, irafutils, iraftask, irafpar, cl2py

try:
	import cStringIO
	StringIO = cStringIO
	del cStringIO
except ImportError:
	import StringIO

# hide these modules so we can use 'from iraffunctions import *'
_sys = sys
_os = os
_string = string
_re = re
_math = math
_types = types
_time = time
_StringIO = StringIO

_minmatch = minmatch
_subproc = subproc
_wutil = wutil

_irafnames = irafnames
_irafutils = irafutils
_iraftask = iraftask
_irafpar = irafpar
_cl2py = cl2py

del sys, os, string, re, math, types, time, StringIO
del minmatch, subproc, wutil
del irafnames, irafutils, iraftask, irafpar, cl2py

class IrafError(Exception):
	pass

yes = 1
no = 0
 
# -----------------------------------------------------
# private dictionaries:
#
# _varDict: dictionary of all IRAF cl variables (defined with set name=value)
# _tasks: all IRAF tasks (defined with task name=value)
# _mmtasks: minimum-match dictionary for tasks
# _pkgs: min-match dictionary for all packages (defined with
#			task name.pkg=value)
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
#			Used as search path to find fully qualified task name
# -----------------------------------------------------

loadedPath = []

# cl is the cl task pointer (frequently used because cl parameters
# are always available)

cl = None


# -----------------------------------------------------
# help: implemented in irafhelp.py
# -----------------------------------------------------

from irafhelp import help

# -----------------------------------------------------
# Init: basic initialization
# -----------------------------------------------------

# This could be executed automatically when the module first
# gets imported, but that would not allow control over output
# (which is available through the doprint and hush parameters.)

def Init(doprint=1,hush=0):
	"""Basic initialization of IRAF environment"""
	global _pkgs, cl
	if len(_pkgs) == 0:
		set(iraf = _os.environ['iraf'])
		set(host = _os.environ['host'])
		set(hlib = _os.environ['hlib'])
		set(arch = '.'+_os.environ['IRAFARCH'])
		if _os.environ.has_key('tmp'):
			set(tmp = _os.environ['tmp'])
		global userIrafHome
		set(home = userIrafHome)

		# define initial symbols
		clProcedure(Stdin='hlib$zzsetenv.def')

		# define clpackage

		clpkg = IrafTaskFactory('', 'clpackage', '.pkg', 'hlib$clpackage.cl',
			'clpackage', 'bin$')

		# add the cl as a task, because its parameters are sometimes needed,
		# but make it a hidden task

		# Make cl a pset since parameters are all we care about
		cl = IrafTaskFactory('','cl','','cl$cl.par','clpackage','bin$')
		cl.setHidden()

		# load clpackage

		clpkg.run(_doprint=0, _hush=hush, _save=1)

		if access('login.cl'):
			fname = 'login.cl'
		elif access('home$login.cl'):
			fname = 'home$login.cl'
		else:
			fname = None

		if fname:
			# define and load user package
			userpkg = IrafTaskFactory('', 'user', '.pkg', fname,
							'clpackage', 'bin$')
			userpkg.run(_doprint=0, _hush=hush, _save=1)
		else:
			_writeError("Warning: no login.cl found")

		# make clpackage the current package
		loadedPath.append(clpkg)
		if doprint: listTasks('clpackage')

# -----------------------------------------------------
# _addPkg: Add an IRAF package to the pkgs list
# -----------------------------------------------------

def _addPkg(pkg):
	"""Add an IRAF package to the packages list"""
	global _pkgs
	name = pkg.getName()
	_pkgs.add(name,pkg)
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
	if not pkgname: pkgname = task.getPkgname()
	fullname = pkgname + '.' + name
	_tasks[fullname] = task
	_mmtasks.add(name,fullname)
	# add task to global namespaces
	_irafnames.strategy.addTask(task)
	# add task to list for its package
	getPkg(pkgname).addTask(task,fullname)

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

def load(pkgname,args=(),kw=None,doprint=1,hush=0,save=1):
	"""Load an IRAF package by name"""
	if isinstance(pkgname,_iraftask.IrafPkg):
		p = pkgname
	else:
		p = getPkg(pkgname)
	if kw is None: kw = {}
	if not kw.has_key('_doprint'): kw['_doprint'] = doprint
	if not kw.has_key('_hush'): kw['_hush'] = hush
	if not kw.has_key('_save'): kw['_save'] = save
	apply(p.run, tuple(args), kw)

# -----------------------------------------------------
# run: Run an IRAF task by name
# -----------------------------------------------------

def run(taskname,args=(),kw=None,save=1):
	"""Run an IRAF task by name"""
	if isinstance(taskname,_iraftask.IrafTask):
		t = taskname
	else:
		t = getTask(taskname)
	if kw is None: kw = {}
	if not kw.has_key('_save'): kw['_save'] = save
	apply(t.run, tuple(args), kw)


# -----------------------------------------------------
# getTask: Find an IRAF task by name
# -----------------------------------------------------

def getTask(taskname, found=0):
	"""Find an IRAF task by name using minimum match

	Returns an IrafTask object.  Name may be either fully qualified
	(package.taskname) or just the taskname.  taskname is also allowed
	to be an IrafTask object, in which case it is simply returned.
	Does minimum match to allow abbreviated names.	If found is set,
	returns None when task is not found; default is to raise exception
	if task is not found.
	"""

	if isinstance(taskname,_iraftask.IrafTask): return taskname

	# undo any modifications to the taskname
	taskname = _irafutils.untranslateName(taskname)

	# Try assuming fully qualified name first

	task = _tasks.get(taskname)
	if task:
		if Verbose>1: print 'found',taskname,'in task list'
		return task

	# Look it up in the minimum-match dictionary
	# Note _mmtasks.getall returns list of full names of all matching tasks

	fullname = _mmtasks.getall(taskname)
	if not fullname:
		if found:
			return None
		else:
			raise KeyError("Task "+taskname+" is not defined")
	if len(fullname) == 1:
		# unambiguous match
		task = _tasks[fullname[0]]
		if Verbose>1: print 'found',task.getName(),'in task list'
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
		sp = _string.split(name,'.')
		if sp[-1] == taskname:
			trylist.append(name)
			pkglist.append(sp[0])
	# return a single exact match
	if len(trylist) == 1: return _tasks[trylist[0]]

	if not trylist:
		# no exact matches, see if all tasks have same name
		sp = _string.split(fullname[0],'.')
		name = sp[-1]
		pkglist = [ sp[0] ]
		for i in xrange(len(fullname)-1):
			sp = _string.split(fullname[i+1],'.')
			if name != sp[-1]:
				if len(fullname)>3:
					fullname[3:] = ['...']
				raise _minmatch.AmbiguousKeyError(
					"Task `%s' is ambiguous, could be %s" %
					(taskname, _string.join(fullname,', ')))
			pkglist.append(sp[0])
		trylist = fullname

	# trylist has a list of several candidate tasks that differ
	# only in package.  Search loaded packages in reverse to find
	# which one was loaded most recently.
	for i in xrange(len(loadedPath)):
		pkg = loadedPath[-1-i].getName()
		if pkg in pkglist:
			# Got it at last
			j = pkglist.index(pkg)
			return _tasks[trylist[j]]
	# None of the packages are loaded?  This presumably cannot happen
	# now, but could happen if package unloading is implemented.
	if found:
		return None
	else:
		raise KeyError("Task "+taskname+" is not in a loaded package")


# -----------------------------------------------------
# getPkg: Find an IRAF package by name
# -----------------------------------------------------

def getPkg(pkgname,found=0):
	"""Find an IRAF package by name using minimum match

	Returns an IrafPkg object.  pkgname is also allowed
	to be an IrafPkg object, in which case it is simply
	returned.  If found is set, returns None when package
	is not found; default is to raise exception if package
	is not found.
	"""
	if not pkgname:
		raise TypeError("Bad package name `%s'" % `pkgname`)
	try:
		if isinstance(pkgname,_iraftask.IrafPkg): return pkgname
		# undo any modifications to the pkgname
		pkgname = _irafutils.untranslateName(pkgname)
		return _pkgs[pkgname]
	except _minmatch.AmbiguousKeyError, e:
		# re-raise the error with a bit more info
		raise e.__class__("Package "+pkgname+": "+str(e))
	except KeyError, e:
		if found: return None
		raise KeyError("Package `%s' not found" % (pkgname,))


# -----------------------------------------------------
# Miscellaneous access routines:
# getTaskList: Get list of names of all defined IRAF tasks
# getPkgList: Get list of names of all defined IRAF packages
# getLoadedList: Get list of names of all loaded IRAF packages
# getVarList: Get list of names of all defined IRAF variables
# -----------------------------------------------------

def getTaskList():
	"""Returns list of names of all defined IRAF tasks"""
	return _tasks.keys()

def getTaskObjects():
	"""Returns list of all defined IrafTask objects"""
	return _tasks.values()

def getPkgList():
	"""Returns list of names of all defined IRAF packages"""
	return _pkgs.keys()

def getLoadedList():
	"""Returns list of names of all loaded IRAF packages"""
	return _loaded.keys()

def getVarDict():
	"""Returns dictionary all IRAF variables"""
	return _varDict

def getVarList():
	"""Returns list of names of all IRAF variables"""
	return _varDict.keys()

# -----------------------------------------------------
# listAll, listPkg, listLoaded, listTasks, listCurrent, listVars:
# list contents of the dictionaries
# -----------------------------------------------------

def listAll(hidden=0, **kw):
	"""List IRAF packages, tasks, and variables"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		print 'Packages:'
		listPkgs()
		print 'Loaded Packages:'
		listLoaded()
		print 'Tasks:'
		listTasks(hidden=hidden)
		print 'Variables:'
		listVars()
	finally:
		redirReset(resetList, closeFHList)

def listPkgs(**kw):
	"""List IRAF packages"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		keylist = getPkgList()
		if len(keylist) == 0:
			print 'No IRAF packages defined'
		else:
			keylist.sort()
			# append '/' to identify packages
			for i in xrange(len(keylist)): keylist[i] = keylist[i] + '/'
			_irafutils.printCols(keylist)
	finally:
		redirReset(resetList, closeFHList)

def listLoaded(**kw):
	"""List loaded IRAF packages"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		keylist = getLoadedList()
		if len(keylist) == 0:
			print 'No IRAF packages loaded'
		else:
			keylist.sort()
			# append '/' to identify packages
			for i in xrange(len(keylist)): keylist[i] = keylist[i] + '/'
			_irafutils.printCols(keylist)
	finally:
		redirReset(resetList, closeFHList)

def listTasks(pkglist=None, hidden=0, **kw):
	"""List IRAF tasks, optionally specifying a list of packages to include

	Package(s) may be specified by name or by IrafPkg objects.
	"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		keylist = getTaskList()
		if len(keylist) == 0:
			print 'No IRAF tasks defined'
			return
		# make a dictionary of pkgs to list
		if not pkglist:
			pkgdict = _pkgs
		else:
			pkgdict = {}
			if type(pkglist) == _types.StringType or \
					isinstance(pkglist,_iraftask.IrafPkg):
				pkglist = [ pkglist ]
			for p in pkglist:
				try:
					pthis = getPkg(p)
					if pthis.isLoaded():
						pkgdict[pthis.getName()] = 1
					else:
						_writeError('Package %s has not been loaded' %
							pthis.getName())
				except KeyError, e:
					_writeError(str(e))
		if not len(pkgdict):
			print 'No packages to list'
			return

		# print each package separately
		keylist.sort()
		lastpkg = ''
		tlist = []
		for tname in keylist:
			pkg, task = _string.split(tname,'.')
			tobj = _tasks[tname]
			if hidden or not tobj.isHidden():
				if isinstance(tobj,_iraftask.IrafPkg):
					task = task + '/'
				elif isinstance(tobj,_iraftask.IrafPset):
					task = task + '@'
				if pkg == lastpkg:
					tlist.append(task)
				else:
					if len(tlist) and pkgdict.has_key(lastpkg):
						print lastpkg + '/:'
						_irafutils.printCols(tlist)
					tlist = [task]
					lastpkg = pkg
		if len(tlist) and pkgdict.has_key(lastpkg):
			print lastpkg + '/:'
			_irafutils.printCols(tlist)
	finally:
		redirReset(resetList, closeFHList)

def listCurrent(n=1, hidden=0, **kw):
	"""List IRAF tasks in current package (equivalent to '?' in the cl)

	If parameter n is specified, lists n most recent packages."""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		if len(loadedPath):
			if n > len(loadedPath): n = len(loadedPath)
			plist = n*[None]
			for i in xrange(n):
				plist[i] = loadedPath[-1-i].getName()
			listTasks(plist,hidden=hidden)
		else:
			print 'No IRAF tasks defined'
	finally:
		redirReset(resetList, closeFHList)

def listVars(prefix="", equals="\t= ", **kw):
	"""List IRAF variables"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		keylist = getVarList()
		if len(keylist) == 0:
			print 'No IRAF variables defined'
		else:
			keylist.sort()
			for word in keylist:
				print "%s%s%s%s" % (prefix, word, equals, envget(word))
	finally:
		redirReset(resetList, closeFHList)

# -----------------------------------------------------
# IRAF utility functions
# -----------------------------------------------------

# these do not have extra keywords because they should not
# be called as tasks

def clParGet(paramname,pkg=None,native=1):
	"""Return value of IRAF parameter
	
	Parameter can be a cl task parameter, a package parameter for
	any loaded package, or a fully qualified (task.param) parameter
	from any known task.
	"""
	if pkg is None: pkg = loadedPath[-1]
	return pkg.getParam(paramname,native=native)

def envget(var,default=""):
	"""Get value of IRAF or OS environment variable"""
	if _varDict.has_key(var):
		return _varDict[var]
	elif _os.environ.has_key(var):
		return _os.environ[var]
	else:
		return default

_tmpfileCounter = 0

def mktemp(root):
	"""Make a temporary filename starting with root"""
	global _tmpfileCounter
	basename = root + `_os.getpid()`
	while 1:
		_tmpfileCounter = _tmpfileCounter + 1
		if _tmpfileCounter <= 26:
			# use letters to start
			suffix = chr(ord("a")+_tmpfileCounter-1)
		else:
			# use numbers once we've used up letters
			suffix = "_" + `_tmpfileCounter-26`
		file = basename + suffix
		if not _os.path.exists(Expand(file)):
			return file

_NullFile = "dev$null"
_NullPath = None

def isNullFile(s):
	"""Returns true if this is the CL null file"""
	global _NullFile, _NullPath
	if s == _NullFile: return 1
	sPath = Expand(s)
	if _NullPath is None: _NullPath = Expand(_NullFile)
	if sPath == _NullPath:
		return 1
	else:
		return 0

def substr(s,first,last):
	"""Return sub-string using IRAF 1-based indexing"""
	return s[first-1:last]

def stridx(test, s):
	"""Return location of string s in test using IRAF 1-based indexing"""
	return _string.find(s,test)+1

def strlen(s):
	"""Return length of string"""
	return len(s)

def frac(x):
	"""Return fractional part of x"""
	frac_part, int_part = _math.modf(x)
	return frac_part

_radixDigits = list(_string.digits+_string.uppercase)

def radix(value, base=10):
	"""Convert integer value to string expressed using given base"""
	ivalue = int(value)
	if base == 10:
		return str(ivalue)
	elif base == 16:
		return '%X' % (ivalue,)
	elif base == 8:
		return '%o' % (ivalue,)
	elif ivalue == 0:
		# handle specially so don't have to worry about it below
		return '0'

	# arbitrary base
	if not ( 2 <= base <= 36):
		raise ValueError("base must be between 2 and 36 (inclusive)")
	outdigits = []
	if ivalue < 0:
		sign = "-"
		ivalue = -ivalue
	else:
		sign = ""
	while ivalue > 0:
		ivalue, digit = divmod(ivalue, base)
		outdigits.append(digit)
	outdigits = map(lambda index: _radixDigits[index], outdigits)
	outdigits.reverse()
	return sign+_string.join(outdigits,'')

def osfn(filename):
	"""Convert IRAF virtual path name to OS pathname"""
	return Expand(filename)

def clSexagesimal(d, m, s=0):
	"""Convert d:m:s value to float"""
	return (d+(m+s/60.0)/60.0)

def defpar(paramname):
	"""Returns true if parameter is defined"""
	try:
		value = clParGet(paramname)
		return 1
	except IrafError, e:
		# ambiguous name is an error, not found is OK
		value = str(e)
		if _string.find(value, "ambiguous") >= 0:
			raise e
		return 0

def access(filename):
	"""Returns true if file exists"""
	return _os.path.exists(Expand(filename))

def defvar(varname):
	"""Returns true if CL variable is defined"""
	return _varDict.has_key(varname)

def deftask(taskname):
	"""Returns true if CL task is defined"""
	try:
		import iraf
		t = getattr(iraf, taskname)
		return 1
	except AttributeError, e:
		# ambiguous name is an error, not found is OK
		value = str(e)
		if _string.find(value, "ambiguous") >= 0:
			raise e
		return 0

def defpac(pkgname):
	"""Returns true if CL package is defined"""
	try:
		t = getPkg(pkgname)
		return (t in loadedPath)
	except KeyError, e:
		# ambiguous name is an error, not found is OK
		value = str(e)
		if _string.find(value, "ambiguous") >= 0:
			raise e
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
	
	Accepts integer/float values 0,1 or string 'yes','no'
	Also allows INDEF as value
	"""
	if value in [INDEF,0,1]:
		return value
	elif value in ["", None]:
		return INDEF
	tval = type(value)
	if tval is _types.StringType:
		v2 = _irafutils.stripQuotes(_string.strip(value))
		if v2 == "INDEF":
			return INDEF
		ff = _string.lower(v2)
		if ff == "no":
			return 0
		elif ff == "yes":
			return 1
	elif tval is _types.FloatType:
		# try converting to integer
		try:
			ival = int(value)
			if (ival == value) and (ival == 0 or ival == 1):
				return ival
		except (ValueError, OverflowError):
			pass
	raise ValueError("Illegal boolean value %s" % `value`)


# -----------------------------------------------------
# scan functions
# -----------------------------------------------------

_nscan = 0

def fscan(locals, line, *namelist, **kw):
	"""fscan function sets parameters from a string or list parameter
	
	Uses local dictionary (passed as first argument) to set variables
	specified by list of following names.  (This is a bit
	messy, but it is by far the cleanest approach I've thought of.
	I'm literally using call-by-name for these variables.)

	Accepts an additional keyword argument strconv with names of
	conversion functions for each argument in namelist.

	Returns number of arguments set to new values.  If there are
	too few space-delimited arguments on the input line, it does
	not set all the arguments.  Returns EOF on end-of-file.
	"""
	# get the value of the line (which may be a variable, string literal,
	# expression, or an IRAF list parameter)
	try:
		line = eval(line, locals)
	except EOFError:
		return EOF
	f = _string.split(line)
	n = min(len(f),len(namelist))
	if kw.has_key('strconv'):
		strconv = kw['strconv']
		del kw['strconv']
	else:
		strconv = n*[None]
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	for i in range(n):
		if strconv[i]:
			cmd = namelist[i] + ' = ' + strconv[i] + '(' + `f[i]` + ')'
		else:
			cmd = namelist[i] + ' = ' + `f[i]`
		exec cmd in locals
	global _nscan
	_nscan = n
	return n

def scan(locals, *namelist, **kw):
	"""Scan function sets parameters from line read from stdin

	This can be used either as a function or as a task (it accepts
	redirection and the _save keyword.)
	"""
	# handle redirection and save keywords
	# other keywords are passed on to fscan
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	resetList = redirApply(redirKW)
	try:
		line = _sys.stdin.readline()
		if line == "": return EOF
		return apply(fscan, (locals, `line`) + namelist, kw)
	finally:
		redirReset(resetList, closeFHList)

def nscan():
	"""Return number of items read in last scan function"""
	global _nscan
	return _nscan

# -----------------------------------------------------
# unimplemented IRAF functions (raise exception)
# -----------------------------------------------------

def imaccess(*args, **kw):
	"""Error unimplemented function"""
	raise IrafError("The imaccess function has not been implemented")

# -----------------------------------------------------
# IRAF utility procedures
# -----------------------------------------------------

# these have extra keywords (redirection, _save) because they can
# be called as tasks

def set(*args, **kw):
	"""Set IRAF environment variables"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	resetList = redirApply(redirKW)
	try:
		if len(args) == 0:
			if len(kw) != 0:
				# normal case is only keyword,value pairs
				for keyword, value in kw.items():
					keyword = _irafutils.untranslateName(keyword)
					_varDict[keyword] = str(value)
			else:
				# set with no arguments lists all variables (using same format
				# as IRAF)
				listVars(prefix="    ", equals="=")
		else:
			# The only other case allowed is the peculiar syntax
			# 'set @filename', which only gets used in the zzsetenv.def file,
			# where it reads extern.pkg.  That file also gets read (in full cl
			# mode) by clpackage.cl.  I get errors if I read this during
			# zzsetenv.def, so just ignore it here...
			#
			# Flag any other syntax as an error.
			if len(args) != 1 or len(kw) != 0 or \
					type(args[0]) != _types.StringType or args[0][:1] != '@':
				raise SyntaxError("set requires name=value pairs")
	finally:
		redirReset(resetList, closeFHList)

# currently do not distinguish set from reset
# this will change when keep/bye/unloading are implemented

reset = set

def show(*args, **kw):
	"""Print value of IRAF or OS environment variables"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for arg in args:
			print envget(arg)
	finally:
		redirReset(resetList, closeFHList)

def time(**kw):
	"""Print current time and date"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		print _time.ctime(_time.time())
	finally:
		redirReset(resetList, closeFHList)

def sleep(seconds, **kw):
	"""Sleep for specified time"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		_time.sleep(float(seconds))
	finally:
		redirReset(resetList, closeFHList)

def beep(**kw):
	"""Beep to terminal (even if output is redirected)"""
	# just ignore keywords
	_sys.__stdout__.write("")
	_sys.__stdout__.flush()

def clOscmd(s, **kw):
	"""Execute a system-dependent command in the shell, returning status"""

	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		# if first character of s is '!' then force to Bourne shell
		if s[:1] == '!':
			shell = "/bin/sh"
			s = s[1:]
		else:
			# otherwise use default shell
			shell=None

		# ignore null commands
		if not s: return 0

		# use subshell to execute command so wildcards, etc. are handled
		status = _subproc.subshellRedir(s, shell=shell)
		return status

	finally:
		redirReset(resetList, closeFHList)

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

def stty(terminal=None, **kw):
	"""IRAF stty command (mainly not implemented)"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	resetList = redirApply(redirKW)
	try:
		import copy
		expkw = _sttyArgs.copy()
		if terminal is not None: expkw['terminal'] = terminal
		for key, item in kw.items():
			if _sttyArgs.has_key(key):
				expkw[key] = item
			else:
				raise TypeError('unexpected keyword argument: '+key)
		if expkw['playback'] is not None:
			_writeError("stty playback not implemented")
			return
		if expkw['resize'] or expkw['terminal'] == "resize":
			# returns a string with size of display
			# also sets CL environmental CL parameters
			if _sys.stdout != _sys.__stdout__:
				# a kluge -- if _sys.stdout is not the terminal,
				# assume it is a file and give a large number for
				# the number of lines
				# don't set the environment variables in this case
				nlines = 1000000
				ncols = 80
			else:
				nlines,ncols = _wutil.getTermWindowSize()
				set(ttyncols=str(ncols))
				set(ttynlines=str(nlines))
			return ("set ttyncols="  + str(ncols)  + "\n" +
					"set ttynlines=" + str(nlines) + "\n")
	finally:
		redirReset(resetList, closeFHList)

def eparam(*args, **kw):
	"""Edit parameters for tasks.  Starts up epar GUI."""
	# keywords are simply ignored here
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for taskname in args:
			try:
				getTask(taskname).epar()
			except KeyError, e:
				_writeError("Warning: Could not find task %s for epar\n" %
					taskname)
	finally:
		redirReset(resetList, closeFHList)

def lparam(*args, **kw):
	"""List parameters for tasks"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for taskname in args:
			try:
				getTask(taskname).lpar()
			except KeyError, e:
				_writeError("Warning: Could not find task %s for lpar\n" %
					taskname)
	finally:
		redirReset(resetList, closeFHList)

def dparam(*args, **kw):
	"""Dump parameters for task in executable form"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for taskname in args:
			try:
				getTask(taskname).dpar()
			except KeyError, e:
				_writeError("Warning: Could not find task %s for dpar\n" %
					taskname)
	finally:
		redirReset(resetList, closeFHList)

def update(*args, **kw):
	"""Update task parameters on disk"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for taskname in args:
			try:
				getTask(taskname).save()
			except KeyError, e:
				_writeError("Warning: Could not find task %s for update" %
					taskname)
	finally:
		redirReset(resetList, closeFHList)

def unlearn(*args, **kw):
	"""Unlearn task parameters -- restore to defaults"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for taskname in args:
			try:
				getTask(taskname).unlearn()
			except KeyError, e:
				_writeError("Warning: Could not find task %s to unlearn" %
					taskname)
	finally:
		redirReset(resetList, closeFHList)

def edit(*args, **kw):
	"""Edit text files"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		editor = envget('editor')
		margs = map(Expand, args)
		_os.system(_string.join([editor,]+margs,' '))
	finally:
		redirReset(resetList, closeFHList)

_clearString = None

def clear(*args, **kw):
	"""Clear screen if output is terminal"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		global _clearString
		if _clearString is None:
			# get the clear command by running system clear
			fh = _StringIO.StringIO()
			clOscmd('clear', Stdout=fh)
			_clearString = fh.getvalue()
			fh.close()
			del fh
		if _sys.stdout == _sys.__stdout__:
			_sys.stdout.write(_clearString)
			_sys.stdout.flush()
	finally:
		redirReset(resetList, closeFHList)

# dummy routines

def clNoHistory(*args, **kw):
	"""Dummy history function"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		print 'History commands not required: Use arrow keys to recall commands'
		print 'or ctrl-R to search for a string in the command history.'
	finally:
		redirReset(resetList, closeFHList)

history = ehistory = clNoHistory

def clNoBackground(*args, **kw):
	"""Dummy background function"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		_writeError('Background jobs not implemented')
	finally:
		redirReset(resetList, closeFHList)

jobs = service = kill = wait = clNoBackground

# dummy (do-nothing) routines

def clDummy(*args, **kw):
	"""Dummy do-nothing function"""
	# just ignore keywords and arguments
	pass

bye = keep = logout = clbye = gflush = clDummy

# unimplemented but no exception raised (and no message
# printed if not in verbose mode)

def flprcache(*args, **kw):
	"""Dummy process cache function"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	resetList = redirApply(redirKW)
	try:
		if Verbose>0: print "No process cache in Pyraf"
	finally:
		redirReset(resetList, closeFHList)

cache = prcache = clDummy

def _notImplemented(cmd, args, kw):
	"""Dummy unimplemented function"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	resetList = redirApply(redirKW)
	try:
		if Verbose>0:
			_writeError("The %s task has not been implemented" % cmd)
	finally:
		redirReset(resetList, closeFHList)

def putlog(*args, **kw):
	_notImplemented('putlog',args,kw)

def clAllocate(*args, **kw):
	_notImplemented('_allocate',args,kw)

def clDeallocate(*args, **kw):
	_notImplemented('_deallocate',args,kw)

def clDevstatus(*args, **kw):
	_notImplemented('_devstatus',args,kw)

# unimplemented -- raise exception

def fprint(*args, **kw):
	"""Error unimplemented function"""
	# The fprint task is never used in CL scripts, as far as I can tell
	raise IrafError("The fprint task has not been implemented")

# various helper functions

def pkgHelp(pkgname=None, **kw):
	"""Give help on package (equivalent to CL '? [taskname]')"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		if pkgname is None:
			listCurrent()
		else:
			listTasks(pkgname)
	finally:
		redirReset(resetList, closeFHList)

def allPkgHelp(**kw):
	"""Give help on all packages (equivalent to CL '??')"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		listTasks()
	finally:
		redirReset(resetList, closeFHList)

def clProcedure(input=None, mode="", DOLLARnargs=0, **kw):
	"""Run CL commands from a file (cl < input)"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	# get the input
	if redirKW.has_key('stdin'):
		stdin = redirKW['stdin']
		del redirKW['stdin']
	elif input is not None:
		if type(input) == _types.StringType:
			# input is a string -- stick it in a StringIO buffer
			stdin = _StringIO.StringIO(input)
		elif hasattr(input,'read'):
			# input is a filehandle
			stdin = input
		else:
			raise TypeError("Input must be a string or input filehandle")
	else:
		# CL without input does nothing
		return
	# apply the I/O redirections
	resetList = redirApply(redirKW)
	# create and run the task
	try:
		newtask = _iraftask.IrafCLTask('', 'tmp', '', stdin,
			curpack(), curPkgbinary())
		newtask.run()
	finally:
		# reset the I/O redirections
		redirReset(resetList, closeFHList)

def hidetask(*args, **kw):
	"""Hide the CL task in package listings"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for taskname in args:
			try:
				getTask(taskname).setHidden()
			except KeyError, e:
				_writeError("Warning: Could not find task %s to hide" %
					taskname)
	finally:
		redirReset(resetList, closeFHList)

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

def task(*args, **kw):
	"""Define IRAF tasks"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']

	if kw.has_key('Redefine'):
		redefine = kw['Redefine']
		del kw['Redefine']
	else:
		redefine = 0

	resetList = redirApply(redirKW)
	try:

		# get package info
		if loadedPath:
			pkg = loadedPath[-1]
			defaultPkgname = pkg.getName()
			defaultPkgbinary = pkg.getPkgbinary()
		else:
			defaultPkgname = ''
			defaultPkgbinary = ''
		# override package using special keywords
		pkgname = kw.get('PkgName')
		if pkgname is None:
			pkgname = defaultPkgname
		else:
			del kw['PkgName']
		pkgbinary = kw.get('PkgBinary')
		if pkgbinary is None:
			pkgbinary = defaultPkgbinary
		else:
			del kw['PkgBinary']
		# fix illegal package names
		spkgname = _string.replace(pkgname, '.', '_')
		if spkgname != pkgname:
			_writeError("Warning: `.' illegal in task name, changing "
				"`%s' to `%s'" % (pkgname, spkgname))
			pkgname = spkgname

		if len(kw) > 1:
			raise SyntaxError("More than one `=' in task definition")
		elif len(kw) < 1:
			raise SyntaxError("Must be at least one `=' in task definition")
		s = kw.keys()[0]
		value = kw[s]
		s = _irafutils.untranslateName(s)
		args = args + (s,)

		# assign value to each task in the list
		global _re_taskname
		for tlist in args:
			mtl = _re_taskname.match(tlist)
			if not mtl:
				raise SyntaxError("Illegal task name `%s'" % (tlist,)) 
			name = mtl.group('taskname')
			prefix = mtl.group('taskprefix')
			suffix = mtl.group('tasksuffix')
			newtask = IrafTaskFactory(prefix,name,suffix,value,
					pkgname,pkgbinary,redefine=redefine)
	finally:
		redirReset(resetList, closeFHList)

def redefine(*args, **kw):
	"""Redefine an existing task"""
	kw['Redefine'] = 1
	apply(task, args, kw)

def package(pkgname, bin=None, PkgName='', PkgBinary='', **kw):
	"""Define IRAF package, returning tuple with new package name and binary
	
	PkgName, PkgBinary are old default values"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		spkgname = _string.replace(pkgname, '.', '_')
		# remove trailing comma
		if spkgname[-1:] == ",": spkgname = spkgname[:-1]
		if (spkgname != pkgname) and (Verbose > 0):
			_writeError("Warning: illegal characters in task name, changing "
				"`%s' to `%s'" % (pkgname, spkgname))
		pkgname = spkgname
		# is the package defined?
		# if not, is there a CL task by this name?
		# otherwise there is an error
		pkg = getPkg(pkgname, found=1)
		if pkg is None:
			pkg = getTask(pkgname, found=1)
			if pkg is None or not isinstance(pkg,_iraftask.IrafCLTask) or \
					pkg.getName() != pkgname:
				raise KeyError("Package `%s' not defined" % pkgname)
			# Hack city -- there is a CL task with the package name, but it was
			# not defined to be a package.  Convert it to an IrafPkg object.

			_iraftask.mutateCLTask2Pkg(pkg)

			# We must be currently loading this package if we encountered
			# its package statement (XXX can I confirm that?).
			# Add it to the lists of loaded packages (this usually
			# is done by the IrafPkg run method, but we are executing
			# as an IrafCLTask instead.)

			_addPkg(pkg)
			loadedPath.append(pkg)
			addLoaded(pkg)
			if Verbose>0: _writeError("Warning: CL task `%s' apparently is "
				"a package" % pkgname)

		return (pkgname, bin or PkgBinary)
	finally:
		redirReset(resetList, closeFHList)

def clPrint(*args, **kw):
	"""CL print command -- emulates CL spacing and uses redirection keywords"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for arg in args:
			print arg,
			# don't put spaces after string arguments
			if type(arg) is _types.StringType: _sys.stdout.softspace=0
		print
	finally:
		redirReset(resetList, closeFHList)

_badFormats = ["%h", "%m", "%b", "%r", "%t", "%u", "%w", "%z"]
		
def printf(format, *args, **kw):
	"""Formatted print function"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		for bad in _badFormats:
			i = _string.find(format, bad)
			while i >= 0:
				_writeError("Warning: printf cannot handle %s format, "
						"using %%s instead\n" % bad)
				format = format[:i] + "%s" + format[i+2:]
				i = _string.find(format, bad, i)
		try:
			print format % args,
			_sys.stdout.softspace = 0
		except ValueError, e:
			raise IrafError(str(e))
	finally:
		redirReset(resetList, closeFHList)

# _backDir is previous working directory

_backDir = None

def pwd(**kw):
	"""Print working directory"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		print _os.getcwd()
	finally:
		redirReset(resetList, closeFHList)

def chdir(directory=None, **kw):
	"""Change working directory"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		global _backDir
		_newBack = _os.getcwd()
		if directory is None:
			# use startup directory as home if argument is omitted
			directory = userWorkingHome
		# Check for (1) local directory and (2) iraf variable
		# when given an argument like 'dev'.  In IRAF 'cd dev' is
		# the same as 'cd ./dev' if there is a local directory named
		# dev but is equivalent to 'cd dev$' if there is no local
		# directory.
		try:
			_os.chdir(Expand(directory))
			_backDir = _newBack
			return
		except (IrafError, OSError):
			pass
		try:
			_os.chdir(Expand(directory + '$'))
			_backDir = _newBack
			return
		except (IrafError, OSError):
			raise IrafError("Cannot change directory to `%s'" % (directory,))
	finally:
		redirReset(resetList, closeFHList)

cd = chdir

def back(**kw):
	"""Go back to previous working directory"""
	# handle redirection and save keywords
	redirKW, closeFHList = redirProcess(kw)
	if kw.has_key('_save'): del kw['_save']
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		global _backDir
		if _backDir is None:
			raise IrafError("ERROR: no previous directory for back()")
		_newBack = _os.getcwd()
		_os.chdir(_backDir)
		print _backDir
		_backDir = _newBack
	finally:
		redirReset(resetList, closeFHList)

def error(errnum=0, errmsg=''):
	"""Print error message"""
	raise IrafError("ERROR: %s\n" % (errmsg,))

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

	import traceback, __main__
	if verbose:
		vmode = ' (verbose)'
	else:
		vmode = ''
	print 'Entering CL-compatibility%s mode...' % vmode

	# logging may be active if Monty is in use
	if hasattr(__main__,'_pycmdline'):
		logfile = __main__._pycmdline.logfile
	else:
		logfile = None

	locals = {}
	local_vars_dict = {}
	local_vars_list = []
	# initialize environment
	exec 'import pyraf, iraf, math, cStringIO' in locals
	exec 'from irafpar import makeIrafPar' in locals
	exec 'from irafglobals import *' in locals
	prompt2 = '>>>'
	while (1):
		try:
			if loadedPath:
				prompt = loadedPath[-1].getName()[:2] + '>'
			else:
				prompt = 'cl>'
			line = raw_input(prompt)
			# simple continuation escape handling
			while line[-1:] == '\\':
				line = line + '\n' + raw_input(prompt2)
			line = _string.strip(line)
			if _exitCommands.has_key(line):
				break
			elif line[:2] == '!P':
				# Python escape -- execute Python code
				exec _string.strip(line[2:]) in locals
			elif line and (line[0] != '#'):
				code = clExecute(line, locals=locals, mode='single',
					local_vars_dict=local_vars_dict,
					local_vars_list=local_vars_list)
				if logfile is not None:
					# log CL code as comment
					cllines = _string.split(line,'\n')
					for oneline in cllines:
						logfile.write('# '+oneline+'\n')
					logfile.write(code)
					logfile.flush()
				if verbose:
					print '----- Python -----'
					print code,
					print '------------------'
		except EOFError:
			break
		except KeyboardInterrupt:
			_writeError("Use `logout' or `.exit' to exit CL-compatibility mode")
		except:
			_sys.stdout.flush()
			traceback.print_exc()
	print
	print 'Leaving CL-compatibility mode...'

# -----------------------------------------------------
# clArray: IRAF array class with type checking
# Note that subscripts start zero, in Python style --
# the CL-to-Python translation takes care of the offset
# in CL code, and Python code should use zero-based
# subscripts.
# -----------------------------------------------------

def clArray(array_size, datatype, name="<anonymous>", mode="h",
		min=None, max=None, enum=None, prompt=None,
		init_value=None, strict=0):
	"""Create an IrafPar object that can be used as a CL array"""
	try:
		return _irafpar.makeIrafPar(init_value, name=name, datatype=datatype,
			mode=mode, min=min, max=max, enum=enum, prompt=prompt,
			array_size=array_size, strict=strict)
	except ValueError, e:
		raise ValueError("Error creating Cl array `%s'\n%s" %
			(name, str(e)))

# -----------------------------------------------------
# clExecute: execute a single cl statement
# -----------------------------------------------------

def clExecute(s, locals=None, mode="proc",
		local_vars_dict={}, local_vars_list=[], verbose=0, **kw):
	"""Execute a single cl statement"""
	# handle redirection keywords
	redirKW, closeFHList = redirProcess(kw)
	if len(kw):
		raise TypeError('unexpected keyword argument: ' + `kw.keys()`)
	resetList = redirApply(redirKW)
	try:
		pycode = _cl2py.cl2py(str=s, mode=mode, local_vars_dict=local_vars_dict,
			local_vars_list=local_vars_list)
		# put code in the filename so it appears in messages
		code = _string.lstrip(pycode.code)
		codeObject = compile(code,_string.rstrip(code),'exec')
		if locals is None: locals = {}
		exec codeObject in locals
		if pycode.vars.proc_name:
			exec pycode.vars.proc_name+"()" in locals
		return code
	finally:
		redirReset(resetList, closeFHList)


# -----------------------------------------------------
# Expand: Expand a string with embedded IRAF variables
# (IRAF virtual filename)
# -----------------------------------------------------

# Input string is in format 'name$rest' or 'name$str(name2)' where
# name and name2 are defined in the _varDict dictionary.
# Returns string with IRAF variable name expanded to full host name.
# Input may also be a comma-separated list of strings to Expand,
# in which case an expanded comma-separated list is returned.

# search for leading string without embedded '$'
__re_var_match = _re.compile(r'(?P<varname>[^$]*)\$')

# search for string embedded in parentheses
# assumes no double embedding
__re_var_paren = _re.compile(r'\((?P<varname>[^$]*)\)')

def Expand(instring):
	"""Expand a string with embedded IRAF variables (IRAF virtual filename)

	Allows comma-separated lists.  Also uses os.path.expanduser to
	replace '~' symbols.
	"""
	# call _expand1 for each entry in comma-separated list
	wordlist = _string.split(instring,",")
	outlist = []
	for word in wordlist:
		outlist.append(_os.path.expanduser(_expand1(word)))
	return _string.join(outlist,",")

def _expand1(instring):
	"""Expand a string with embedded IRAF variables (IRAF virtual filename)"""
	mm = __re_var_match.match(instring)
	if mm is None:
		mm = __re_var_paren.search(instring)
		if mm is None: return instring
		if defvar(mm.group('varname')):
			return instring[:mm.start()] + \
				_expand1(mm.group('varname')+'$') + \
				instring[mm.end():]
	varname = mm.group('varname')
	if defvar(varname):
		# recursively expand string after substitution
		return _expand1(envget(varname) + instring[mm.end():])
	else:
		raise IrafError("Undefined variable " + varname + \
			" in string " + instring)

def IrafTaskFactory(prefix,taskname,suffix,value,pkgname,pkgbinary,
		redefine=0):

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

	# fix illegal names
	spkgname = _string.replace(pkgname, '.', '_')
	if spkgname != pkgname:
		_writeError("Warning: `.' illegal in package name, changing "
			"`%s' to `%s'" % (pkgname, spkgname))
		pkgname = spkgname

	staskname = _string.replace(taskname, '.', '_')
	if staskname != taskname:
		_writeError("Warning: `.' illegal in task name, changing "
			"`%s' to `%s'" % (taskname, staskname))
		taskname = staskname

	if suffix == '.pkg':
		return IrafPkgFactory(prefix,taskname,suffix,value,pkgname,pkgbinary,
			redefine=redefine)

	root, ext = _os.path.splitext(value)
	if ext == '.par':
		return IrafPsetFactory(prefix,taskname,suffix,value,pkgname,pkgbinary,
			redefine=redefine)

	# normal task definition

	fullname = pkgname + '.' + taskname
	# existing task object (if any)
	task = _tasks.get(fullname)
	if task is None and redefine:
		_writeError("Warning: `%s' is not a defined task" % taskname)

	if ext == '.cl':
		newtask = _iraftask.IrafCLTask(prefix,taskname,suffix,value,
						pkgname,pkgbinary)
	elif value[:1] == '$':
		newtask = _iraftask.IrafForeignTask(prefix,taskname,suffix,value,
						pkgname,pkgbinary)
	else:
		newtask = _iraftask.IrafTask(prefix,taskname,suffix,value,
						pkgname,pkgbinary)
	if task:
		# check for consistency of definition by comparing to the
		# new object
		if task.getFilename() != newtask.getFilename() or \
		   task.hasParfile()  != newtask.hasParfile() or \
		   task.getForeign()  != newtask.getForeign() or \
		   task.getTbflag()   != newtask.getTbflag():
			# looks different -- print warning and continue
			if not redefine:
				_writeError("Warning: `%s' is a task redefinition" %
					fullname)
		else:
			# new task is consistent with old task, so return old task
			if task.getPkgbinary() != newtask.getPkgbinary():
				# package binary differs -- add it to search path
				if Verbose>1: print 'Adding',pkgbinary,'to',task,'path'
				task.addPkgbinary(pkgbinary)
			return task
	# add it to the task list
	_addTask(newtask)
	return newtask

def IrafPsetFactory(prefix,taskname,suffix,value,pkgname,pkgbinary,
	redefine=redefine):

	"""Returns a new or existing IrafPset object
	
	Returns a new object unless this task is already
	defined. In that case if the old task appears consistent with
	the new task, a reference to the old task is returned.
	Otherwise a warning is printed and a reference to a new task is
	returned.

	If redefine keyword is set, the behavior is the same except
	a warning is printed if it does *not* exist.
	"""

	fullname = pkgname + '.' + taskname
	task = _tasks.get(fullname)
	if task is None and redefine:
		_writeError("Warning: `%s' is not a defined task" % taskname)

	newtask = _iraftask.IrafPset(prefix,taskname,suffix,value,pkgname,pkgbinary)
	if task:
		# check for consistency of definition by comparing to the new
		# object (which will be discarded)
		if task.getFilename() != newtask.getFilename():
			if redefine:
				_writeError("Warning: `%s' is a task redefinition" %
					fullname)
		else:
			# old version of task is same as new
			return task
	# add it to the task list
	_addTask(newtask)
	return newtask

def IrafPkgFactory(prefix,taskname,suffix,value,pkgname,pkgbinary,
	redefine=redefine):

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

	# does package with exactly this name exist in minimum-match
	# dictionary _pkgs?
	pkg = _pkgs.get_exact_key(taskname)
	if pkg is None and redefine:
		_writeError("Warning: `%s' is not a defined task" % taskname)
	newpkg = _iraftask.IrafPkg(prefix,taskname,suffix,value,pkgname,pkgbinary)
	if pkg:
		if pkg.getFilename() != newpkg.getFilename() or \
		   pkg.hasParfile()  != newpkg.hasParfile():
			if pkg.isLoaded():
				_writeError("Warning: currently loaded package `%s' was not "
					"redefined" % taskname)
				return pkg
			else:
				if not redefine:
					_writeError("Warning: `%s' is a task redefinition" %
						taskname)
				_addPkg(newpkg)
				return newpkg
		if pkg.getPkgbinary() != newpkg.getPkgbinary():
			# only package binary differs -- add it to search path
			if Verbose>1: print 'Adding',pkgbinary,'to',pkg,'path'
			pkg.addPkgbinary(pkgbinary)
		if pkgname != pkg.getPkgname():
			# add existing task as an item in the new package
			_addTask(pkg,pkgname=pkgname)
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

	XXX Still need to do graphics redirection keywords
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
				}
	for key in redirDict.keys():
		if kw.has_key(key):
			outputFlag, standardName, openArgs = redirDict[key]
			# if it is a string, open as a file
			# otherwise assume it is a filehandle
			value = kw[key]
			if type(value) == _types.StringType:
				# expand IRAF variables
				value = Expand(value)
				if outputFlag:
					# output file
					# check to see if it is dev$null
					if isNullFile(value): value = '/dev/null'
				fh = open(value,openArgs)
				# close this when we're done
				closeFHList.append(fh)
			else:
				if outputFlag:
					if not hasattr(value, 'write'):
						raise IrafError("%s redirection must "
							"be to a file handle or string\n"
							"Value is `%s'" %
							(key, value))
				elif not hasattr(value, 'read'):
					raise IrafError("%s redirection must "
						"be from a file handle or string\n"
						"Value is `%s'" %
						(key, value))
				fh = value
			redirKW[standardName] = fh
			del kw[key]
	return redirKW, closeFHList

def redirApply(redirKW):

	"""Modify _sys.stdin, stdout, stderr using the redirKW dictionary

	Returns a list of the original filehandles so they can be
	restored (by redirReset)
	"""

	sysDict = { 'stdin': 1, 'stdout': 1, 'stderr': 1 }
	resetList = []
	for key, value in redirKW.items():
		if sysDict.has_key(key):
			resetList.append((key, getattr(_sys,key)))
			setattr(_sys,key,value)
	return resetList


def redirReset(resetList, closeFHList):

	"""Restore _sys.stdin, stdout, stderr to their original values

	Also closes the filehandles in closeFHList
	"""

	for fh in closeFHList:
		fh.close()
	for key, value in resetList:
		setattr(_sys,key,value)
