"""module iraffunctions.py -- parse IRAF package definition files and
create IRAF task and package lists

Do not use this directly -- the relevant public classes and functions
get included in iraf.py.  The implementations are kept here to avoid
possible problems with name conflicts in iraf.py (which is the home for
all the IRAF task and package names.)

$Id$

R. White, 1999 August 16
"""

import sys, os, string, re, types, time
import irafnames, irafutils, minmatch, iraftask

# hide these modules so we can use 'from iraffunctions import *'
_sys = sys
_os = os
_string = string
_re = re
_types = types
_time = time

del sys, os, string, re, types, time

_irafnames = irafnames
_irafutils = irafutils
_minmatch = minmatch
_iraftask = iraftask

del irafnames, irafutils, minmatch, iraftask

class IrafError(Exception):
	pass
 
# -----------------------------------------------------
# private dictionaries:
#
# _tasks: all IRAF tasks (defined with task name=value)
# _mmtasks: minimum-match dictionary for tasks
# _pkgs: min-match dictionary for all packages (defined with
#			task name.pkg=value)
# _loaded: loaded packages
# -----------------------------------------------------

# Will want to enhance this to allow a "bye" function that unloads packages.
# That might be done using a stack of definitions for each task.

_tasks = {}
_mmtasks = _minmatch.MinMatchDict()
_pkgs = _minmatch.MinMatchDict()
_loaded = {}
 
# -----------------------------------------------------
# public variables:
#
# varDict: dictionary of all IRAF cl variables (defined with set name=value)
# loadedPath: list of loaded packages in order of loading
#			Used as search path to find fully qualified task name
# -----------------------------------------------------

varDict = {}
loadedPath = []

# cl is the cl task pointer (frequently used because cl parameters
# are always available)

cl = None

# -----------------------------------------------------
# setVerbose: set verbosity level
# -----------------------------------------------------

# make Verbose an instance of a class so it can be imported
# into other modules

class _VerboseClass:
	"""Container class for verbosity (or other) value"""
	def __init__(self, value=0): self.value = value
	def set(self, value): self.value = value
	def get(self): return self.value
	def __cmp__(self, other): return cmp(self.value, other)

Verbose = _VerboseClass()

def setVerbose(value=1):
	"""Set verbosity level when running tasks.
	
	Level 0 (default) prints almost nothing.
	Level 1 prints parsing warnings.
	Level 2 prints info on progress.
	Level 3 prints cl code itself.
	"""
	Verbose.set(value)


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
	global varDict, _pkgs, cl
	if len(_pkgs) == 0:
		varDict['iraf'] = _os.environ['iraf']
		varDict['host'] = _os.environ['host']
		varDict['hlib'] = _os.environ['hlib']
		varDict['arch'] = '.'+_os.environ['IRAFARCH']
		# XXX Note that this setting of home may not be correct -- should
		# XXX do something more sophisticated like making current directory
		# XXX home if it contains a login.cl and uparm?
		varDict['home'] = _os.path.join(_os.environ['HOME'],'iraf','')

		readCl('hlib$zzsetenv.def', 'clpackage', 'bin$', hush=hush)

		# define clpackage

		clpkg = IrafTaskFactory('', 'clpackage', '.pkg', 'hlib$clpackage.cl',
			'clpackage', 'bin$')

		# add the cl as a task, because its parameters are sometimes needed,
		# but make it a hidden task

		cl = IrafTaskFactory('','cl','','cl$cl.e','clpackage','bin$')
		cl.setHidden(1)

		# load clpackage

		clpkg.run(_doprint=0, _hush=hush)

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
			userpkg.run(_doprint=0, _hush=hush)
		else:
			print "Warning: no login.cl found"

		# make clpackage the current package
		loadedPath.append(clpkg)
		if doprint: listTasks('clpackage')

# -----------------------------------------------------
# addPkg: Add an IRAF package to the pkgs list
# -----------------------------------------------------

def addPkg(pkg):
	global _pkgs
	name = pkg.getName()
	_pkgs.add(name,pkg)
	# add package to global namespaces
	_irafnames.strategy.addPkg(pkg)
	# packages are tasks too, so add to task lists
	addTask(pkg)

# -----------------------------------------------------
# addTask: Add an IRAF task to the tasks list
# -----------------------------------------------------

def addTask(task, pkgname=None):
	global _tasks, _mmtasks
	name = task.getName()
	if not pkgname: pkgname = task.getPkgname()
	fullname = pkgname + '.' + name
	_tasks[fullname] = task
	_mmtasks.add(name,fullname)
	# add task to global namespaces
	_irafnames.strategy.addTask(task)
	# add task to list for its package
	_pkgs[pkgname].addTask(task)

# -----------------------------------------------------
# addLoaded: Add an IRAF package to the loaded pkgs list
# -----------------------------------------------------

def addLoaded(pkg):
	"""Add an IRAF package to the loaded pkgs list"""
	global _loaded
	_loaded[pkg.getName()] = len(_loaded)

# -----------------------------------------------------
# load: Load an IRAF package by name
# -----------------------------------------------------

def load(pkgname,args=(),kw=None,doprint=1,hush=0):
	"""Load an IRAF package by name."""
	if isinstance(pkgname,_iraftask.IrafPkg):
		p = pkgname
	else:
		p = getPkg(pkgname)
	if kw == None: kw = {}
	kw['_doprint'] = doprint
	kw['_hush'] = hush
	apply(p.run, tuple(args), kw)

# -----------------------------------------------------
# run: Run an IRAF task by name
# -----------------------------------------------------

def run(taskname,args=(),kw=None):
	"""Run an IRAF task by name."""
	if isinstance(taskname,_iraftask.IrafTask):
		t = taskname
	else:
		t = getTask(taskname)
	if kw == None: kw = {}
	apply(t.run, tuple(args), kw)

# -----------------------------------------------------
# getPkg: Find an IRAF package by name
# -----------------------------------------------------

def getPkg(pkgname,found=0):
	"""Find an IRAF package by name using minimum match.

	Returns an IrafPkg object.  pkgname is also allowed
	to be an IrafPkg object, in which case it is simply
	returned.  If found is set, returns None when package
	is not found; default is to raise exception if package
	is not found."""
	try:
		if isinstance(pkgname,_iraftask.IrafPkg): return pkgname
		return _pkgs[pkgname]
	except KeyError, e:
		if found: return None
		# re-raise the error with a bit more info
		if pkgname:
			raise e.__class__("Package "+pkgname+": "+str(e))
		else:
			raise e

# -----------------------------------------------------
# getPkgList: Get list of names of all defined IRAF packages
# -----------------------------------------------------

def getPkgList():
	"""Returns list of names of all defined IRAF packages"""
	return _pkgs.keys()

# -----------------------------------------------------
# getLoadedList: Get list of names of all loaded IRAF packages
# -----------------------------------------------------

def getLoadedList():
	"""Returns list of names of all loaded IRAF packages"""
	return _loaded.keys()

# -----------------------------------------------------
# getVarList: Get list of names of all defined IRAF variables
# -----------------------------------------------------

def getVarList():
	"""Returns list of names of all defined IRAF variables"""
	return varDict.keys()

# -----------------------------------------------------
# getTask: Find an IRAF task by name
# -----------------------------------------------------

def getTask(taskname):
	"""Find an IRAF task by name.  Name may be either fully qualified
	(package.taskname) or just the taskname.  Does minimum match to
	allow abbreviated names.  Returns an IrafTask object."""

	# Try assuming fully qualified name first

	task = _tasks.get(taskname)
	if task:
		if Verbose>1: print 'found',taskname,'in task list'
		return task

	# Look it up in the minimum-match dictionary
	# Note _mmtasks.getall returns list of full names of all matching tasks

	fullname = _mmtasks.getall(taskname)
	if not fullname:
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
				raise KeyError("Task '" + taskname + "' is ambiguous, " +
					"could be " + `fullname`)
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
	raise KeyError("Task "+taskname+" is not in a loaded package")

# -----------------------------------------------------
# getTaskList: Get list of names of all defined IRAF tasks
# -----------------------------------------------------

def getTaskList():
	"""Returns list of names of all defined IRAF tasks"""
	return _tasks.keys()

# -----------------------------------------------------
# listAll, listPkg, listLoaded, listTasks, listCurrent, listVars:
# list contents of the dictionaries
# -----------------------------------------------------

def listAll(hidden=0):
	"""List IRAF packages, tasks, and variables"""
	print 'Packages:'
	listPkgs()
	print 'Loaded Packages:'
	listLoaded()
	print 'Tasks:'
	listTasks(hidden=hidden)
	print 'Variables:'
	listVars()

def listPkgs():
	"""List IRAF packages"""
	keylist = getPkgList()
	if len(keylist) == 0:
		print 'No IRAF packages defined'
	else:
		keylist.sort()
		# append '/' to identify packages
		for i in xrange(len(keylist)): keylist[i] = keylist[i] + '/'
		_irafutils.printCols(keylist)

def listLoaded():
	"""List loaded IRAF packages"""
	keylist = getLoadedList()
	if len(keylist) == 0:
		print 'No IRAF packages loaded'
	else:
		keylist.sort()
		# append '/' to identify packages
		for i in xrange(len(keylist)): keylist[i] = keylist[i] + '/'
		_irafutils.printCols(keylist)

def listTasks(pkglist=None,hidden=0):
	"""List IRAF tasks, optionally specifying a list of packages to include.
	Package(s) may be specified by name or by IrafPkg objects."""
	keylist = getTaskList()
	if len(keylist) == 0:
		print 'No IRAF tasks defined'
	else:
		# make a dictionary of pkgs to list
		if pkglist:
			pkgdict = {}
			if type(pkglist) is _types.StringType or \
					isinstance(pkglist,_iraftask.IrafPkg):
				pkglist = [ pkglist ]
			for p in pkglist:
				try:
					pthis = getPkg(p)
					if pthis.getLoaded():
						pkgdict[pthis.getName()] = 1
					else:
						print 'Package',pthis.getName(),'has not been loaded'
				except KeyError, e:
					print e
			if not len(pkgdict):
				print 'No packages to list'
				return
		else:
			pkgdict = _pkgs

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

def listCurrent(n=1,hidden=0):
	"""List IRAF tasks in current package (equivalent to '?' in the cl.)
	If parameter n is specified, lists n most recent packages."""

	if len(loadedPath):
		if n > len(loadedPath): n = len(loadedPath)
		plist = n*[None]
		for i in xrange(n):
			plist[i] = loadedPath[-1-i].getName()
		listTasks(plist,hidden=hidden)
	else:
		print 'No IRAF tasks defined'

def listVars():
	"""List IRAF variables"""
	keylist = getVarList()
	if len(keylist) == 0:
		print 'No IRAF variables defined'
	else:
		keylist.sort()
		for word in keylist:
			print word + '	= ' + varDict[word]

# -----------------------------------------------------
# _regexp_init: Initialize regular expressions for
#				cl file parsing
# -----------------------------------------------------

_quoteMarker = '\377'
_blockMarker = '\376'

_re_double = None
_re_quote = None
_re_block = None
_re_ComSngDbl = None
_re_word = None
_re_rest = None
_re_bstrail = None
_re_taskname = None
_re_continuation = None
_re_combined_stmt = None

def _regexp_init():

	global _re_double, _re_quote, _re_block, \
		_re_ComSngDbl, _re_word, _re_rest, _re_bstrail, _re_taskname, \
		_re_continuation, _re_combined_stmt

	# Pattern that matches a quoted string with embedded \"
	# From Freidl, Mastering Regular Expressions, p. 176.
	#
	# Modifications:
	# - I'm using the "non-capturing" parentheses (?:...) where
	#   possible; I only capture the part of the string between
	#   the quotes.

	required_whitespace = r'[ \t]+'
	optional_whitespace = r'[ \t]*'
	double = r'"(?P<value>[^"\\]*(?:\\.[^"\\]*)*)"' + optional_whitespace
	_re_double = _re.compile(double)

	# a version without the optional whitespace
	sdouble = r'"(?P<double>[^"\\]*(?:\\.[^"\\]*)*)"'

	# single quotes without the optional whitespace
	ssingle = r"'(?P<single>[^'\\]*(?:\\.[^'\\]*)*)'"

	# match first example of either single or double quotes
	_re_quote = _re.compile( r'(?:' + sdouble + r')|' +
							r'(?:' + ssingle + r')',
							_re.DOTALL)

	# comment (without worrying about quotes)
	comment = r'(?P<comment>#[^\n]*$)'

	# a pattern that matches first example of comment, sdouble, or ssingle
	_re_ComSngDbl = _re.compile( r'(?:' + comment + r')|' +
								r'(?:' + sdouble + r')|' +
								r'(?:' + ssingle + r')',
								_re.MULTILINE | _re.DOTALL)

	# bracket-enclosed block
	# matches over lines, with no embedded blocks
	block = r'{(?P<block>[^{}]*)}'
	_re_block = _re.compile(block)

	# pattern that matches whitespace- or comma-terminated word
	_re_word = _re.compile(r'(?P<word>[^ \t,]+),?' + optional_whitespace)

	# Pattern that matches to end-of-line or semicolon;
	# also picks off first (whitespace-delimited) word.
	# Note I'm using the ungreedy match '*?' and the lookahead
	# match '(?=..)' functions for the tail so that any
	# trailing whitespace is not included in the 'value'
	# string.
	#
	# _re_rest pattern cannot fail to match.

	rest_stmt = r'(?P<value>' + \
		r'(?P<firstword>[^ \t;]*)' + r'(?P<tail>[^;]*?))' + \
		optional_whitespace + r'(?=$|[;])'
	_re_rest = _re.compile(optional_whitespace + rest_stmt)

	# Pattern that matches trailing backslashes at end of line
	_re_bstrail = _re.compile(r'\\*$')

	# Pattern that matches either backslash-newline, comma-newline,
	# or //-newline as continuation
	# We also match (for deletion) any leading whitespace on the next line
	_re_continuation = _re.compile(r'(?:' +
			r'(?P<backslash>\\\n)|' +
			r'(?P<comma>,' + optional_whitespace + r'\n)|' +
			r'(?P<concat>//' + optional_whitespace + r'\n)' +
			r')' + optional_whitespace)

	# alphanumeric variable name
	variable_name = r'[a-zA-Z_][a-zA-Z0-9_]*'
	# alphanumeric variable name with embedded dots
	variable_name_dot = r'[a-zA-Z_][a-zA-Z0-9_\.]*'

	# pattern matching single task name, possibly with $ prefix and/or
	# .pkg or .tb suffix
	# also matches optional trailing comma and whitespace
	taskname = r'(?:' + r'(?P<taskprefix>\$?)' + \
		r'(?P<taskname>[a-zA-Z_][a-zA-Z0-9_]*)' + \
		r'(?P<tasksuffix>\.(?:pkg|tb))?' + \
		r',?' + optional_whitespace + r')'
	_re_taskname = _re.compile(taskname)

	# Pattern matching space or comma separated list of one or more task names.
	# Note this will also match a list with a comma after the last item.  Tough.
	tasklist = taskname + '+'

	# empty statement (must be terminated by semi-colon, empty line is
	# not the same as an empty statement)
	empty_stmt = r'(?P<empty>;)'

	# set var = expression
	# also reset var = expression
	set_stmt = '(?:set|reset)' + required_whitespace + \
		r'(?P<varname>' + variable_name + r')' + \
		optional_whitespace + '=' + optional_whitespace

	# set @filename
	set_file_stmt = 'set' + required_whitespace + \
		r'@(?P<setfilename>[^ \t;]+)' + optional_whitespace

	# cl < filename
	cl_redir_stmt = '(?P<clredir>cl)' + optional_whitespace + '<' + \
		optional_whitespace

	# package name[, bin=bindir]
	package_stmt = 'package' + required_whitespace + \
		r'(?P<packagename>' + variable_name_dot + ')' + \
		r'(?:' + \
			optional_whitespace + ',' + \
			optional_whitespace + 'bin' + \
			optional_whitespace + '=' + \
			optional_whitespace + r'(?P<packagebin>[^ \t]+)' + \
		r')?' + optional_whitespace

	# task tasklist = expression
	# also redefine tasklist = expression
	task_stmt = '(?:task|redefine)' + required_whitespace + \
		r'(?P<tasklist>' + tasklist + r')' + \
		'=' + optional_whitespace

	# hide statement (takes a list of task/package names)
	hide_stmt = '(?P<hidestmt>hide|hidetask)' + required_whitespace

	# matches balanced parenthesized expressions up to 7 deep (ugly
	# but the only way to get reg-exps to match them)
	notpar = r'[^()]*'
	balpar = notpar
	for i in xrange(6):
		balpar = notpar + r'(?:\(' + balpar + r'\)' + notpar + r')*'
	balpar = r'\(' + balpar + r'\)'

	# print statement takes a simple string or a parenthesized
	# list of strings & variables (don't handle more complex versions)
	print_stmt = r'print' + required_whitespace + \
		r'"(?P<printval>[^"\\]*(?:\\.[^"\\]*)*)"' + optional_whitespace

	printexp_stmt = r'print' + optional_whitespace + \
		r'(?P<printexpr>' + balpar + ')' + optional_whitespace

	# equals print statement '= "string"'
	eqprint_stmt = r'=' + optional_whitespace + \
		r'"(?P<eqprintval>[^"\\]*(?:\\.[^"\\]*)*)"' + optional_whitespace

	# type statement takes a filename
	type_stmt = r'type' + required_whitespace + \
		r'(?P<typefilename>[^ \t;(]+)' + optional_whitespace
	typeexp_stmt = r'type' + optional_whitespace + \
		r'(?P<typeexpr>' + balpar + ')' + optional_whitespace

	# error(value, msg)
	#XXX not general in expressions allowed
	error_stmt = r'error' + optional_whitespace + r'\(' + \
		optional_whitespace + r'(?P<errornum>[0-9]+)' + \
		optional_whitespace + ',' + optional_whitespace + \
		r'(?P<errormsg>[^)]*)\)' + optional_whitespace

	# beep statement
	beep_stmt = r'(?P<beepstmt>beep)' + optional_whitespace

	# sleep statement
	sleep_stmt = r'sleep' + optional_whitespace + \
		r'\(' + optional_whitespace + '(?P<sleeptime>[0-9.]+)' + \
		optional_whitespace + '\)' + optional_whitespace

	# declaration statement
	# XXX should add optional attributes to pattern
	declaration_stmt = r'(?P<vartype>' + \
		r'int|bool|char|real|string|struct|file|gcur|imcur' + \
		r')' + required_whitespace

	# block statement (after initial parsing and substitution
	block_stmt = _blockMarker + r'(?P<block>[^' + _blockMarker + r']*)' +  \
		_blockMarker + optional_whitespace

	# if statement
	if_stmt = 'if' + optional_whitespace + \
		r'(?P<ifcondition>' + balpar + ')' + optional_whitespace

	# else statement
	else_stmt = r'(?P<else>else)' + optional_whitespace

	# assignment statement
	assign_stmt = r'(?P<assign_var>' + variable_name_dot + r')' + \
		optional_whitespace + '=' + optional_whitespace

	# miscellaneous statements to parse and ignore quietly
	# some of these we may eventually want to interpret
	misc_stmt = r'(?P<miscstmt>(?:' + \
			r'keep' + \
		')|(?:' + r'clear' + \
		')|(?:' + r'begin' + \
		')|(?:' + r'string' + required_whitespace + 'mode' + optional_whitespace + \
					'=' + optional_whitespace + '[\'"](al|a|h)[\'"]' + \
		')|(?:' + r'procedure' + required_whitespace + variable_name + \
					optional_whitespace + r'\(' + optional_whitespace + r'\)' + \
		')|(?:' + r'end' + \
		')|(?:' + r'cache' + required_whitespace + tasklist + \
		')|(?:' + r'prcache' + required_whitespace + tasklist + \
		')|(?:' + r'stty' + required_whitespace + variable_name + \
		')|(?:' + r'clbye(?:' + \
					optional_whitespace + r'\(' + optional_whitespace + r'\))?' + \
		')|(?:' + r'cl' + \
					optional_whitespace + r'\(' + optional_whitespace + r'\)' + \
		'))' + optional_whitespace

	# combined statement
	# Note rest_stmt, which cannot fail to match, is last so
	# that all the other options are tried first
	combined_stmt = r'(?:' + set_stmt         + r')|' + \
					r'(?:' + empty_stmt       + r')|' + \
					r'(?:' + set_file_stmt    + r')|' + \
					r'(?:' + cl_redir_stmt    + r')|' + \
					r'(?:' + package_stmt     + r')|' + \
					r'(?:' + task_stmt        + r')|' + \
					r'(?:' + hide_stmt        + r')|' + \
					r'(?:' + print_stmt       + r')|' + \
					r'(?:' + printexp_stmt    + r')|' + \
					r'(?:' + eqprint_stmt     + r')|' + \
					r'(?:' + type_stmt        + r')|' + \
					r'(?:' + typeexp_stmt     + r')|' + \
					r'(?:' + error_stmt       + r')|' + \
					r'(?:' + beep_stmt        + r')|' + \
					r'(?:' + sleep_stmt       + r')|' + \
					r'(?:' + block_stmt       + r')|' + \
					r'(?:' + if_stmt          + r')|' + \
					r'(?:' + else_stmt        + r')|' + \
					r'(?:' + assign_stmt      + r')|' + \
					r'(?:' + misc_stmt        + r')|' + \
					r'(?:' + declaration_stmt + r')|' + \
					r'(?:' + rest_stmt        + r')'

	_re_combined_stmt = _re.compile(combined_stmt)

# -----------------------------------------------------
# readCl: Read and execute an IRAF .cl file
# -----------------------------------------------------

def readCl(filename,pkgname,pkgbinary,hush=0):
	"""Read and execute an IRAF .cl file"""

	spkgname = _string.replace(pkgname, '.', '_')
	if spkgname != pkgname:
		print "Warning: '.' illegal in task name, changing", pkgname, \
			"to", spkgname
	pkgname = spkgname

	# expand any IRAF variables in filename
	expfile = Expand(filename)

	# if file exists, read it; otherwise return with warning
	if _os.path.exists(expfile):
		fh = open(_os.path.expanduser(expfile),"r")
	else:
		if filename == expfile:
			print "WARNING: no such file", filename
		else:
			print "WARNING: no such file", filename,"("+expfile+")"
		return
	all = fh.read()
	fh.close()
	execCl(all,pkgname,pkgbinary,filename,hush=hush)


# -----------------------------------------------------
# execCl: Execute IRAF .cl command(s)
# -----------------------------------------------------

def execCl(clstring,pkgname=None,pkgbinary=None,filename="<no file>",hush=0):
	"""Execute IRAF .cl command(s), possibly with embedded newlines"""

	global _re_ComSngDbl, _re_block

	# initialize regular expressions
	if not _re_ComSngDbl: _regexp_init()

	if pkgname is None: pkgname = curpack()

	# delete comments and replace quoted strings with marker+pointer
	# into list of extracted strings
	if Verbose>2: print '%%%%%% before ComSngDbl substitution:\n', clstring
	qlist = []
	mm = _re_ComSngDbl.search(clstring)
	while mm:
		if mm.group("comment"):
			# just delete comments
			clstring = clstring[0:mm.start()] + clstring[mm.end():]
		else:
			# extract quoted strings (including quotes)
			s = mm.group()
			this = _quoteMarker + `len(qlist)` + _quoteMarker
			qlist.append(_joinContinuation(s))
			clstring = clstring[0:mm.start()] + this + clstring[mm.end():]
		mm = _re_ComSngDbl.search(clstring,mm.start())

	if Verbose>2: print '%%%%%% after ComSngDbl substitution:\n', clstring
	# join continuation lines
	clstring = _joinContinuation(clstring)
	if Verbose>2: print '%%%%%% after joinContinuation:\n', clstring

	# Break code up into blocks delimited by {} and
	# replace blocks with marker+pointer.
	# The block pattern matches only interior blocks (with no
	# embedded blocks), so this replaces from the inside out.
	blist = []
	mm = _re_block.search(clstring)
	while mm:
		this = _blockMarker + `len(blist)` + _blockMarker
		# note blocks get split into lines here
		blist.append(_string.split(mm.group("block"),'\n'))
		clstring = clstring[0:mm.start()] + this + clstring[mm.end():]
		mm = _re_block.search(clstring)

	if Verbose>2: print '%%%%%% after block substitution:\n', clstring

	# Split the remaining lines
	lines = _string.split(clstring,'\n')

	# Execute the cleaned-up lines
	_execCl(filename,lines,qlist,blist,pkgname,pkgbinary,hush)

# -----------------------------------------------------
# _joinContinuation: Join up all the continuation lines
# in the string
# -----------------------------------------------------

def _joinContinuation(s):
	"""Delete line continuation sequences from _string.  A trailing
	backslash, trailing comma, or trailing // indicates continuation."""
	global _re_continuation
	mm = _re_continuation.search(s)
	while mm:
		if mm.group('comma'):
			# delete whitespace-newline from comma-whitespace-newline
			s = s[:mm.start()+1] + s[mm.end():]
			iend = mm.start()
		elif mm.group('concat'):
			# delete whitespace-newline from //-whitespace-newline
			s = s[:mm.start()+2] + s[mm.end():]
			iend = mm.start()
		else:
			# delete backslash-newline unless the backslash itself
			# is escaped
			i = mm.start()-1
			while i>=0:
				if s[i] != "\\": break
				i = i-1
			if ((mm.start()-i) % 2) == 1:
				s = s[:mm.start()] + s[mm.end():]
				iend = mm.start()
			else:
				iend = mm.end()
		mm = _re_continuation.search(s,iend)
	return s

# -----------------------------------------------------
# _markQuotes: substitute markers in place of quoted
# strings.  Returns the new string and  a list of the
# extracted quotes.
# -----------------------------------------------------

def _markQuotes(s):
	"""Extract any quoted strings (that match the _re_quote regular
	expression) and replace with markers.  Returns a tuple with the
	modified string and a list of the extracted strings (which can
	be used with _subMarkedQuotes to restore the strings.)"""
	global _re_quote
	mm = _re_quote.search(s)
	qlist = []
	while mm:
		this = _quoteMarker + `len(qlist)` + _quoteMarker
		qlist.append(mm.group())
		s = s[0:mm.start()] + this + s[mm.end():]
		mm = _re_quote.search(s,mm.start()+len(this))
	return s, qlist

# -----------------------------------------------------
# _subMarkedQuotes: substitute quoted strings back in
# place of markers
# -----------------------------------------------------

def _subMarkedQuotes(s, qlist):
	"""Search string s for marked quotes and plug them back in."""
	global _re_quote
	re_mq = _re.compile(_quoteMarker + r'(?P<value>[^' + _quoteMarker + ']*)' +
		_quoteMarker)
	mm = re_mq.search(s)
	while mm:
		i = int(mm.group('value'))
		s = s[:mm.start()] + qlist[i] + s[mm.end():]
		mm = re_mq.search(s,mm.start()+len(qlist[i]))
	return s

# -----------------------------------------------------
# _execCl: Execute a list of IRAF cl commands
# Define tasks and packages, load packages, add symbols
# to dictionaries, etc.
# -----------------------------------------------------

def _execCl(filename,lines,qlist,blist,pkgname,pkgbinary,hush,offset=0):
	"""Execute lines from an IRAF .cl file.  Assumes block statements,
	strings, comments, and continuation lines have already been
	handled.
	qlist and blist are list of quoted strings replaced by
	marker/pointer combination.  Offset is value to add to line
	number to get original line number in file."""

	global _re_double, _re_quote, _re_block, \
		_re_ComSngDbl, _re_word, _re_rest, _re_bstrail, _re_taskname, \
		_re_continuation, _re_combined_stmt

	# initialize regular expressions
	if not _re_ComSngDbl: _regexp_init()

	# state is a stack used to determine how to handle if/else statements.
	# All states are active for only a single statement (because blocks
	# have been turned into one statement.)  But that "single" statement
	# can be another if-else (which itself may contain if-elses), which is
	# why we need the stack.

	state = []
	S_EXECUTE = 0
	S_SKIP = 1
	S_SKIP_ELSE = 2
	S_DO_ELSE = 3

	nlines = len(lines)
	line = _string.strip(lines[0])
	next = 1
	while line or (next < nlines):
		# remove leading whitespace
		line = _string.lstrip(line)
		if line == '':
			line = _string.strip(lines[next])
			next = next+1

		# skip blank lines
		if line == '': continue

		# put back the quotes
		# XXX should change this later, it will simplify other
		# XXX parsing to have quotes as markers

		line = _subMarkedQuotes(line,qlist)

		# parse the line

		try:
			mmlist = _parseLine(line)
		except IrafError, e:
			raise IrafError(str(e) + "\n'" + line + "'\n" +
						"(line " + `next+offset` + ", " + filename + ")")

		i2 = mmlist[-1].end()
		mm = mmlist[0]
		if len(mmlist)>1:
			mmvalue = mmlist[1]
		else:
			mmvalue = None

		# state determines what to do with this statement
		# always go to next state on list after executing this one
		if state:
			thisState = state[-1]
			state = state[:-1]
		else:
			thisState = S_EXECUTE

		if thisState == S_SKIP:
			if mm.group('ifcondition'):
				# if we're skipping, must skip both parts of this if
				state.append(S_SKIP_ELSE)
				state.append(S_SKIP)
		elif thisState == S_DO_ELSE:
			if mm.group('else'):
				# do this else clause
				state.append(S_EXECUTE)
			else:
				# no else, so just continue with execution
				thisState = S_EXECUTE
		elif thisState == S_SKIP_ELSE:
			if mm.group('else'):
				# skip this else clause
				state.append(S_SKIP)
			else:
				# no else, so just continue with execution
				thisState = S_EXECUTE

		if thisState == S_EXECUTE:
			if mm.group('block') != None:
				# call _execCl recursively to execute this block
				b = int(mm.group('block'))
				offset = _execCl(filename, blist[b], qlist, blist, pkgname,
							pkgbinary, hush, offset=offset+next-1) - next
			elif mm.group('ifcondition') != None:
				if _evalCondition(mm.group('ifcondition'),pkgname):
					state.append(S_SKIP_ELSE)
					state.append(S_EXECUTE)
				else:
					state.append(S_DO_ELSE)
					state.append(S_SKIP)
			elif mm.group('else') != None:
				# error to encounter else in S_EXECUTE state
				if Verbose>0:
					print "Unexpected 'else' statement\n" + \
						"'" + line + "'\n" + \
						"(line " + `next+offset` + ", " + filename + ")"
			elif mm.group('empty') != None:
				# ignore empty statements (but note they do get used
				# for state changes)
				pass
			elif mm.group('value') != None:
				# Load packages and execute tasks
				value = mm.group('firstword')
				try:
					p = getTask(value)
					value = p.getName()
					if value == pkgname:
						if Verbose>1:
							print "Skipping recursive load of package",value
					else:
						if Verbose>1:
							print "Loading package",value
						# Parse parameters to package
						tail = _string.strip(mm.group('tail'))
						args, kw = parseArgs(tail)
						if isinstance(p,_iraftask.IrafPkg):
							# load IRAF package
							load(p,args,kw,doprint=0,hush=hush)
						else:
							# run IRAF task
							run(p,args,kw)
				except KeyError:
					if Verbose>0:
						print "Ignoring '" + line[:i2] + \
							"' (line " + `next+offset` + ", " + filename + ")"
				except IrafError, e:
					raise e.__class__("Error at '" + line[:i2] + \
						"' (line " + `next+offset` + ", " + filename + ")\n" + \
						str(e))
			elif mm.group('setfilename') != None:
				# This peculiar syntax 'set @filename' only gets used in the
				# zzsetenv.def file, where it reads extern.pkg.  That file
				# also gets read (in full cl mode) by clpackage.cl.  I get
				# errors if I read this during zzsetenv.def, so just ignore
				# it here...
				pass
			elif mm.group('printval') != None:
				# print statement
				if not hush: print mm.group('printval')
			elif mm.group('printexpr') != None:
				# print statement
				if not hush: _evalPrint(mm.group('printexpr'),pkgname)
			elif mm.group('eqprintval') != None:
				# equals print statement
				if not hush: print mm.group('eqprintval')
			elif mm.group('errornum') != None:
				# error(errornum, errormsg)
				try:
					errormsg = mm.group('errormsg')
					msg = clEval(errormsg)
				except Exception:
					msg = errormsg
				# try to print something sensible if msg=None
				if not msg: msg = errormsg
				raise IrafError('ERROR: ' + msg)
			elif mm.group('beepstmt') != None:
				# beep statement
				_sys.stdout.write("")
				_sys.stdout.flush()
			elif mm.group('sleeptime') != None:
				# sleep statement
				try:
					_time.sleep(float(mm.group('sleeptime')))
				except:
					if Verbose>0:
						print "Error in sleep(" + \
							mm.group("sleeptime") + ")" + \
							" (line " + `next+offset` + ", " + filename + ")"
					pass
			elif mm.group('typefilename') or mm.group('typeexpr'):
				# copy file to stdout if it exists
				# Is there a standard library procedure to do this?
				typefile = mm.group('typefilename')
				if not typefile:
					typefile = clEval(mm.group('typeexpr'))
				# strip quotes
				mdq = _re_double.match(typefile)
				if mdq != None: typefile = mdq.group('value')
				try:
					typefile = Expand(typefile)
					if (not hush) and _os.path.exists(typefile):
						fh_type = open(_os.path.expanduser(typefile),'r')
						tline = fh_type.readline()
						while tline != '':
							print tline,
							tline = fh_type.readline()
						fh_type.close()
				except SyntaxError:
					print "WARNING: Could not expand", typefile, \
						"(line " + `next+offset` + ", " + filename + ")"
			elif mm.group('packagename') != None:
				pkgname = mm.group('packagename')
				spkgname = _string.replace(pkgname, '.', '_')
				if spkgname != pkgname:
					print "Warning: '.' illegal in task name, changing", pkgname, \
						"to", spkgname
				pkgname = spkgname
				if mm.group('packagebin') != None:
					pkgbinary = mm.group('packagebin')
			elif mm.group('vartype') != None:
				# Declaration: currently ignored
				if Verbose>0:
					print "Ignoring '" + line[:i2] + \
						"' (line " + `next+offset` + ", " + filename + ")"
			elif mm.group('miscstmt') != None:
				# Miscellaneous: parsed but quietly ignored
				pass
			else:

				# other statements take a value
				if not mmvalue:
					raise IrafError("Expected a value???\n" +
						"'" + line + "'\n" +
						"(line " + `next+offset` + ", " + filename + ")")

				value = mmvalue.group('value')

				if mm.group('clredir') != None:
					# open and read this file too
					if Verbose>1: print "Reading",value
					readCl(value,pkgname,pkgbinary,hush=hush)
					if Verbose>1: print "Done reading",value
				elif mm.group('varname') != None:
					name = mm.group('varname')
					varDict[name] = value
				elif mm.group('assign_var') != None:
					name = mm.group('assign_var')
					try:
						clSet(name,value,pkg=getPkg(pkgname))
					except IrafError:
						if Verbose>0:
							print "Ignoring '" + line[:i2] + \
								"' (line " + `next+offset` + ", " + \
								filename + ")"
				elif mm.group('hidestmt') != None:
					# hide can take multiple task names
					# XXX messy stuff here to allow parenthesized
					# XXX list of quoted names.  remove this when
					# XXX parser gets better.
					if value[:1] == '(': value = value[1:]
					if value[-1:] == ')': value = value[:-1]
					mw = _re_word.match(value,0)
					while mw != None:
						word = mw.group('word')
						try:
							word = _irafutils.stripQuotes(word)
							getTask(word).setHidden(1)
						except KeyError, e:
							print "WARNING: Could not find task", \
								word, "to hide (line " + `next+offset` + \
								", " + filename + ")"
							print e
						mw = _re_word.match(value,mw.end())
				elif mm.group('tasklist') != None:
					# assign value to each task in the list
					tlist = mm.group('tasklist')
					mtl = _re_taskname.match(tlist)
					while mtl != None:
						name = mtl.group('taskname')
						prefix = mtl.group('taskprefix')
						suffix = mtl.group('tasksuffix')
						newtask = IrafTaskFactory(prefix,name,suffix,value,
							pkgname,pkgbinary)
						mtl = _re_taskname.match(tlist,mtl.end())
				else:
					if Verbose>0:
						print "Parsed but ignored line " + `next+offset` + \
							" '" + line + "'"

		# error if characters follow command except for if, else, block, empty
		if i2 < len(line):
			if line[i2] == ';':
				i2 = i2+1
			elif not (mm.group('ifcondition') or
						mm.group('else') or
						mm.group('block') or
						mm.group('empty')):
				# probably a parsing error
				if Verbose>0:
					print "Non-blank characters after end of command\n" + \
						"'" + line + \
						"' (line " + `next+offset` + ", " + filename + ")"
		line = line[i2:]
	return offset+nlines

# -----------------------------------------------------
# _parseLine: Parse a single cl line
# Returns a list of match objects for line.  Most lines
# return only a single object; lines with a separate
# argument return 2 objects.
# -----------------------------------------------------

def _parseLine(line):
	"""Parse a single line from an IRAF .cl file.  Returns a
	list of match objects."""

	global _re_double, _re_quote, _re_block, \
		_re_ComSngDbl, _re_word, _re_rest, _re_bstrail, _re_taskname, \
		_re_continuation, _re_combined_stmt

	# this regular expression match does most of the work

	mm = _re_combined_stmt.match(line)
	mmlist = [mm]

	# see if an argument is required

	if (mm.group('clredir') or
		mm.group('varname') or
		mm.group('assign_var') or
		mm.group('vartype') or
		mm.group('hidestmt') or
		mm.group('tasklist') ) :

		i1 = mm.end()

		if line[i1] == '"':
			# strip off double quotes
			mdq = _re_double.match(line,i1)
			if mdq == None:
				raise IrafError("Unmatched quotes")
			mmlist.append(mdq)
		else:
			# no quotes, take everything to eol or semicolon
			mmlist.append(_re_rest.match(line,i1))

	return mmlist

# -----------------------------------------------------
# IRAF utility procedures (used to evaluate if statements)
# -----------------------------------------------------

def clGet(paramname,pkg=None,native=1):
	"""Return value of parameter, which can be a cl task parameter,
	a package parameter for any loaded package, or a fully qualified
	(task.param) parameter from any known task."""
	if pkg==None: pkg = loadedPath[-1]
	return pkg.getParam(paramname,native=native)

def clSet(paramname,value,pkg=None):
	"""Set value of parameter, which can be a cl task parameter,
	a package parameter for any loaded package, or a fully qualified
	(task.param) parameter from any known task."""
	if pkg==None: pkg = loadedPath[-1]

	# XXX improve this by evaluating possible parameter expression
	# XXX (but that requires leaving quotes on string arguments)

	if value[:1] == "(" and value[-1:] == ")":
		# try evaluating expressions in parantheses
		result = clEval(value[1:-1],pkg=pkg,native=0)
		if result == None: result = value
	else:
		result = value
	if Verbose>1:
		print "clSet name", paramname, "value", `value`, "eval", result
	pkg.setParam(paramname,result)

def envget(var):
	if varDict.has_key(var):
		return varDict[var]
	elif _os.environ.has_key(var):
		return _os.environ[var]
	else:
		return ""
		# raise KeyError("No IRAF or environment variable '" + var + "'")

def defpar(paramname):
	try:
		value = clGet(paramname)
		return 1
	except IrafError, e:
		# ambiguous name is an error, not found is OK
		value = str(e)
		if _string.find(value, "ambiguous") >= 0:
			raise e
		return 0

def access(filename):
	return _os.path.exists(Expand(filename))

def defvar(varname):
	return varDict.has_key(varname)

def deftask(taskname):
	try:
		t = getTask(taskname)
		return 1
	except KeyError, e:
		# ambiguous name is an error, not found is OK
		value = str(e)
		if _string.find(value, "ambiguous") >= 0:
			raise e
		return 0

def defpac(pkgname):
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
	if loadedPath:
		return loadedPath[-1].getName()
	else:
		return ""

# -----------------------------------------------------
# _evalCondition: evaluate the condition from a cl if
# statement
# -----------------------------------------------------

_re_varname = _re.compile(r'(?P<var>[$a-zA-Z_][$a-zA-Z_0-9.]*)' +
	r'[ \t]*(?![a-zA-Z_0-9. \t(])')

def _evalCondition(s,pkgname):
	# evaluate the condition s from a cl if statement
	# return 1 or 0 for true or false
	# raise an Exception on error

	s_in = s

	# extract any quoted strings and replace with marker
	s, qlist = _markQuotes(s)

	# replace variable names with calls to clGet()
	s = _re_varname.sub(_convertVar,s)

	# replace '!' by not, except for '!='
	s = _re.sub(r'![ \t]*(?![= \t])', ' not ', s)

	# put quoted strings back into expression
	s = _subMarkedQuotes(s,qlist)

	# pkg gets used in the clGet call
	pkg = getPkg(pkgname)
	# use native values, not strings
	native = 1
	try:
		result = eval(s)
	except Exception, e:
		if Verbose>0: print 'error in condition ' + s_in + ': '+str(e)
		result = 0

	if Verbose>1:
		print "condition:", s_in, "=",
		if s != s_in: print s, "=",
		print result
	return result

# -----------------------------------------------------
# _evalPrint: evaluate and print a list of expressions
# from a cl print statement
# -----------------------------------------------------

def _evalPrint(s,pkgname):
	# evaluate parenthesized list of expressions and print them

	# trim off the parentheses
	if s[0] == '(':
		i1 = 1
	else:
		i1 = 0
	if s[-1] == ')':
		i2 = -1
	else:
		i2 = len(s)
	s = s[i1:i2]

	# extract any quoted strings and replace with markers
	s, qlist = _markQuotes(s)

	# split on commas
	v = _string.split(s,',')

	# evaluate and print each field
	pkg = getPkg(pkgname)
	for field in v:
		if field:
			# convert from cl to Python form
			# returns null on error
			result = clEval(field,qlist,pkg,native=0)
			if result: print result,
	print
	return

# -----------------------------------------------------
# clEval: evaluate a cl expression
# Currently pretty limited in its capabilities
# -----------------------------------------------------

def clEval(s,qlist=None,pkg=None,native=1):
	"""Evaluate expression and return value"""

	# extract any quoted strings and replace with markers
	if qlist == None: s, qlist = _markQuotes(s)

	# replace variable names with calls to clGet()
	s = _re_varname.sub(_convertVar,s)

	# replace '!' by not, except for '!='
	s = _re.sub(r'![ \t]*(?![= \t])', ' not ', s)

	# replace '//' by '+'
	s = _re.sub(r'//', '+', s)

	# put the quotes back
	s = _subMarkedQuotes(s,qlist)

	try:
		return eval(s)
	except Exception, e:
		if Verbose>0:
			print 'error evaluating: '+s
			print str(e)
		return None

def _convertVar(mm):
	# convert the matched variable name to a call to clGet
	return 'clGet("' + mm.group('var') + '",pkg=pkg,native=native)'

# -----------------------------------------------------
# parseArgs: Parse IRAF command-mode arguments
# Returns a list of positional parameters and a dictionary
# of keyword parameters
# -----------------------------------------------------

def parseArgs(s):
	args = []
	kw = {}
	smod = _string.strip(s)
	if not smod: return (tuple(args), kw)

	if Verbose>1:
		print "(Parsing package parameters '" + smod + "')"

	# extract any double-quoted strings and replace with marker
	smod, qlist = _markQuotes(smod)
	words = _string.split(smod)

	# build list of positional arguments
	for i in xrange(len(words)):
		word = words[i]
		if (word[-1] == '-') or (word[-1] == '+') or ('=' in word):
			break
		word = _subMarkedQuotes(word,qlist)
		args.append(word)
	else:
		if Verbose>1:
			print "(args", args, "kw", kw, ")"
		return (tuple(args), kw)

	# now build list of keyword arguments
	while i < len(words):
		word = words[i]
		if word[-1] == '-':
			word = word[:-1]
			word = _subMarkedQuotes(word,qlist)
			if kw.has_key(word):
				raise SyntaxError("Multiple values given for parameter " + 
					word + "\nFull parameter list: '" + s + "'")
			kw[word] = "no"
		elif word[-1] == '+':
			word = word[:-1]
			word = _subMarkedQuotes(word,qlist)
			if kw.has_key(word):
				raise SyntaxError("Multiple values given for parameter " + 
					word + "\nFull parameter list: '" + s + "'")
			kw[word] = "yes"
		else:
			f = _string.split(word,'=')
			if len(f) < 2:
				raise SyntaxError(
					"Positional parameter cannot follow keyword: '" +
					s + "'")
			elif len(f) > 2:
				raise SyntaxError("Illegal keyword syntax: '" + 
					s + "'")
			key = f[0]
			value = f[1]
			key = _subMarkedQuotes(key,qlist)
			value = _subMarkedQuotes(value,qlist)
			if kw.has_key(key):
				raise SyntaxError("Multiple values given for parameter " + 
					key + "\nFull parameter list: '" + s + "'")
			kw[key] = value
		i = i+1
	if Verbose>1:
		print "(args", args, "kw", kw, ")"
	return (tuple(args), kw)

# -----------------------------------------------------
# Expand: Expand a string with embedded IRAF variables
# (IRAF virtual filename)
# -----------------------------------------------------

# Input string is in format 'name$rest' or 'name$str(name2)' where
# name and name2 are defined in the varDict dictionary.
# Returns string with IRAF variable name expanded to full host name.
# Input may also be a comma-separated list of strings to Expand,
# in which case an expanded comma-separated list is returned.

# search for leading string without embedded '$'
__re_var_match = _re.compile(r'(?P<varname>[^$]*)\$')

# search for string embedded in parentheses
# assumes no double embedding
__re_var_paren = _re.compile(r'\((?P<varname>[^$]*)\)')

def Expand(instring):
	"""Expand a string with embedded IRAF variables (IRAF virtual filename),
	allowing comma-separated lists
	"""
	# call _expand1 for each entry in comma-separated list
	wordlist = _string.split(instring,",")
	outlist = []
	for word in wordlist:
		outlist.append(_expand1(word))
	return _string.join(outlist,",")

def _expand1(instring):
	"""Expand a string with embedded IRAF variables (IRAF virtual filename)"""
	mm = __re_var_match.match(instring)
	if mm == None:
		mm = __re_var_paren.search(instring)
		if mm == None: return instring
		if varDict.has_key(mm.group('varname')):
			return instring[:mm.start()] + \
				_expand1(mm.group('varname')+'$') + \
				instring[mm.end():]
	varname = mm.group('varname')
	if varDict.has_key(varname):
		# recursively expand string after substitution
		return _expand1(varDict[varname] + instring[mm.end():])
	else:
		raise IrafError("Undefined variable " + varname + \
			" in string " + instring)

def IrafTaskFactory(prefix,taskname,suffix,value,pkgname,pkgbinary):

	"""Returns a new or existing IrafTask, IrafPset, or IrafPkg object
	
	Type of returned object depends on value of suffix and value.  Returns a new
	object unless this task or package is already defined, in which case
	a warning is printed and a reference to the existing task is returned.
	"""

	if suffix == '.pkg':
		return IrafPkgFactory(prefix,taskname,suffix,value,pkgname,pkgbinary)
	root, ext = _os.path.splitext(value)
	if ext == '.par':
		return IrafPsetFactory(prefix,taskname,suffix,value,pkgname,pkgbinary)

	fullname = pkgname + '.' + taskname
	task = _tasks.get(fullname)
	newtask = _iraftask.IrafTask(prefix,taskname,suffix,value,pkgname,pkgbinary)
	if task:
		# check for consistency of definition by comparing to the new
		# object (which will be discarded)
		if task.getFilename() != newtask.getFilename() or \
		   task.hasParfile()  != newtask.hasParfile() or \
		   task.getForeign()  != newtask.getForeign() or \
		   task.getTbflag()   != newtask.getTbflag():
			print 'Warning: ignoring attempt to redefine task',fullname
		if task.getPkgbinary() != newtask.getPkgbinary():
			# only package binary differs -- add it to search path
			if Verbose>1: print 'Adding',pkgbinary,'to',task,'path'
			task.addPkgbinary(pkgbinary)
		return task
	# add it to the task list
	addTask(newtask)
	return newtask

def IrafPsetFactory(prefix,taskname,suffix,value,pkgname,pkgbinary):

	"""Returns a new or existing IrafPset object
	
	Returns a new object unless this package is already defined, in which case
	a warning is printed and a reference to the existing task is returned.
	"""

	fullname = pkgname + '.' + taskname
	task = _tasks.get(fullname)
	newtask = _iraftask.IrafPset(prefix,taskname,suffix,value,pkgname,pkgbinary)
	if task:
		# check for consistency of definition by comparing to the new
		# object (which will be discarded)
		if task.getFilename() != newtask.getFilename():
			print 'Warning: ignoring attempt to redefine task',fullname
		return task
	# add it to the task list
	addTask(newtask)
	return newtask

def IrafPkgFactory(prefix,taskname,suffix,value,pkgname,pkgbinary):

	"""Returns a new or existing IrafPkg object
	
	Returns a new object unless this package is already defined, in which case
	a warning is printed and a reference to the existing task is returned.
	"""

	# does package with exactly this name exist in minimum-match
	# dictionary _pkgs?
	pkg = _pkgs.data.get(taskname)
	newpkg = _iraftask.IrafPkg(prefix,taskname,suffix,value,pkgname,pkgbinary)
	if pkg:
		if pkg.getFilename() != newpkg.getFilename() or \
		   pkg.hasParfile()  != newpkg.hasParfile():
			print 'Warning: ignoring attempt to redefine package',taskname
		if pkg.getPkgbinary() != newpkg.getPkgbinary():
			# only package binary differs -- add it to search path
			if Verbose>1: print 'Adding',pkgbinary,'to',pkg,'path'
			pkg.addPkgbinary(pkgbinary)
		if pkgname != pkg.getPkgname():
			# add existing task as an item in the new package
			addTask(pkg,pkgname=pkgname)
		return pkg
	addPkg(newpkg)
	return newpkg

