"""module iraf.py -- parse IRAF package definition files and
create IRAF task and package lists

$Id$

R. White, 1999 Jan 25
"""

import os, string, re, irafpar, irafexecute, types

class IrafError(Exception):
	pass
 
# -----------------------------------------------------
# dictionaries:
# vars: all IRAF cl variables (defined with set name=value)
# tasks: all IRAF tasks (defined with task name=value)
# pkgs: all packages (defined with task name.pkg=value)
# loaded: loaded packages
# -----------------------------------------------------

# Will want to enhance this to allow a "bye" function that unloads packages.
# That might be done using a stack of definitions for each task.

# May want to reorganize this so that the tasks and packages
# are in a single dictionary?

vars = {'iraf': os.environ['iraf'],
	'host': os.environ['host'],
	'hlib': os.environ['hlib'],
	'arch': '.'+os.environ['IRAFARCH'],
	'home': os.path.join(os.environ['HOME'],'iraf') }
tasks = {}
pkgs = {}
loaded = {}

_verbose = 0

# _loadedPath: loaded packages in order of loading
# Used as search path to find fully qualified task name

_loadedPath = []


# -----------------------------------------------------
# HTML help
# -----------------------------------------------------

_HelpURL = "http://ra.stsci.edu/cgi-bin/bps/gethelp.cgi?task="

def help(taskname):
	"""Display HTML help for given IRAF task in Netscape.
	Tries using 'netscape -remote' command to load the page in
	a running Netscape.  If that fails, starts a new netscape."""
	pid = os.fork()
	if pid == 0:
		url = _HelpURL + taskname
		cmd = "netscape -remote 'openURL(" + url + ")' 1> /dev/null 2>&1"
		status = os.system(cmd)
		if status != 0:
			print "Starting Netscape for HTML help..."
			os.execvp("netscape",["netscape",url])
		os._exit(0)

# -----------------------------------------------------
# basic initialization
# -----------------------------------------------------

# Should these just be executed statements rather than a function?
# Then simply importing the package would initialize them -- but
# perhaps that is better done in some other module.

def init():
	"""Basic initialization of IRAF environment"""
	global pkgs
	if len(pkgs) == 0:
		readcl('hlib$zzsetenv.def', 'clpackage', 'bin$')
		# define and load clpackage
		p = IrafPkg('$', 'clpackage', '.pkg', 'hlib$clpackage.cl', 'clpackage', 'bin$')
		pkgs['clpackage'] = p
		p.run()
		if os.path.exists('login.cl'):
			readcl('login.cl','clpackage','bin$')
		else:
			print "Warning: no login.cl found in login directory"
		listtasks('clpackage')

def setVerbose(verbose=1):
	"""Set verbosity level when running tasks"""
	global _verbose
	_verbose = verbose

def getVerbose():
	"""Return verbosity level"""
	global _verbose
	return _verbose

# -----------------------------------------------------
# IRAF task class
# -----------------------------------------------------

class IrafTask:
	"""IRAF task class"""
	def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
		self.__name = name
		self.__pkgname = pkgname
		self.__pkgbinary = pkgbinary
		self.__hidden = 0
		if prefix == '$':
			self.__hasparfile = 0
		else:
			self.__hasparfile = 1
		if suffix == '.tb':
			self.__tbflag = 1
		else:
			self.__tbflag = 0
		# full path names and parameter list get filled in on demand
		self.__fullpath = None
		self.__parpath = None
		self.__pars = None
		self.__pardict = None
		if filename[0] == '$':
			# this is a foreign task
			self.__cl = 0
			self.__pset = 0
			self.__foreign = 1
			self.__filename = filename[1:]
			# handle weird syntax for names
			if self.__filename == 'foreign':
				self.__filename = name
			elif filename[0:2] == '$0':
				self.__filename = name + self.__filename[2:]
		else:
			self.__foreign = 0
			self.__filename = filename
			# flag .cl scripts and psets
			root, ext = os.path.splitext(filename)
			if ext == ".cl":
				self.__cl = 1
				self.__pset = 0
			elif ext == ".par":
				self.__pset = 1
				self.__cl = 0
			else:
				self.__cl = 0
				self.__pset = 0

	# public accessor functions for attributes

	def getName(self):       return self.__name
	def getPkgname(self):    return self.__pkgname
	def getPkgbinary(self):  return self.__pkgbinary
	def getHidden(self):     return self.__hidden
	def getHasparfile(self): return self.__hasparfile
	def getTbflag(self):     return self.__tbflag
	def getCl(self):         return self.__cl
	def getPset(self):       return self.__pset
	def getForeign(self):    return self.__foreign
	def getFilename(self):   return self.__filename

	def getFullpath(self):
		if self.__fullpath == None: self.initTask()
		return self.__fullpath
	def getParpath(self):
		if self.__fullpath == None: self.initTask()
		return self.__parpath
	def getPars(self):
		if self.__fullpath == None: self.initTask()
		return self.__pars
	def getParDict(self):
		if self.__fullpath == None: self.initTask()
		return self.__pardict

	# public access to set hidden attribute, which is specified
	# in a separate 'hide' statement

	def setHidden(self,value):     self.__hidden = value

	# get value for parameter 'param'
	def get(self,param):
		if self.__fullpath == None: self.initTask()
		if not self.__hasparfile:
			raise SyntaxError("Task "+self.__name+" has no parameter file")
		else:
			if self.__pardict.has_key(param):
				return self.__pardict[param].get()
			else:
				raise SyntaxError("No such parameter '" +
					param + "' for task " + self.__name)

	# set task parameter 'param' to value
	def set(self,param,value):
		if self.__fullpath == None: self.initTask()
		if not self.__hasparfile:
			raise SyntaxError("Task "+self.__name+" has no parameter file")
		else:
			if self.__pardict.has_key(param):
				self.__pardict[param].set(value)
			else:
				raise SyntaxError("No such parameter '" +
					param + "' for task " + self.__name)

	# allow running task using taskname() or with
	# parameters as arguments, including keyword=value form.

	def __call__(self,*args,**kw):
		apply(self.run,args,kw)
	def run(self,*args,**kw):
		if self.__fullpath == None: self.initTask()
		if self.__foreign:
			print "No run yet for foreign task",self.__name
		elif self.__cl:
			print "No run yet for cl task", self.__name, \
				"("+self.__fullpath+")"
		else:
			# set parameters
			apply(self.setParList,args,kw)
			if _verbose:
				print "Connected subproc run ", self.__name, \
					"("+self.__fullpath+")"
				self.lpar()
			try:
				# Parameter dictionaries for execution consist of this
				# task's parameters, any psets referenced, and all the parameters
				# for packages that have been loaded.  Each dictionary has
				# an associated name (because parameters could be asked for
				# as task.parname as well as just parname).

				# XXX This is getting fairly complicated -- probably want to
				# move this out of irafexecute.py and just provide an
				# accessor function here that gets called from irafexecute.py

				parDictList = [(self.__name,self.__pardict)]
				# look for any psets
				for param in self.__pars:
					if param.type == "pset":
						# pset name is from either parameter value (if not null)
						# or from parameter name (XXX I'm just guessing at this)
						try:
							psetname = param.get() or param.name
							pset = getTask(psetname)
							parDictList.append( (param.name,pset.getParDict()) )
						except KeyError:
							raise IrafError("Cannot get pset " +
								param.name + " for task " + self.__name)
				# package parameters
				for i in xrange(len(_loadedPath)):
					pkg = _loadedPath[-1-i]
					parDictList.append( (pkg.getName(),pkg.getParDict()) )
				irafexecute.IrafExecute(self.__name, self.__fullpath,
					vars, parDictList)
				if _verbose: print 'Successful task termination'
			except irafexecute.IrafProcessError, value:
				raise IrafError("Error running IRAF task " + self.__name +
					"\n" + str(value))

	def setParList(self,*args,**kw):
		# add positional parameters to the keyword list, checking
		# for duplicates
		ipar = 0
		for value in args:
			while ipar < len(self.__pars):
				if self.__pars[ipar].mode != "h": break
				ipar = ipar+1
			else:
				# executed if we run out of non-hidden parameters
				raise SyntaxError("Too many positional parameters for task " +
					self.__name)
			param = self.__pars[ipar].name
			if kw.has_key(param):
				raise SyntaxError("Multiple values given for parameter " + 
					param + " in task " + self.__name)
			kw[param] = value
			ipar = ipar+1
		# now set all keyword parameters
		keys = kw.keys()
		for param in keys: self.set(param,kw[param])
		# Number of arguments on command line is used by some IRAF tasks
		# (e.g. imheader).  Emulate same behavior by setting $nargs.
		# XXX Are there any other weird parameter conventions?
		self.set('$nargs',len(args))
	def lpar(self):
		if self.__fullpath == None: self.initTask()
		if not self.__hasparfile:
			print "Task",self.__name," has no parameter file"
		else:
			for i in xrange(len(self.__pars)):
				p = self.__pars[i]
				if _verbose or p.name != '$nargs': print p.pretty()

	# fill in full pathnames of files and read parameter file (if it exists)
	# if names are None then need to run this
	# if names are "" then already tried and failed
	# if names are strings then already did it
	def initTask(self):
		if self.__fullpath == "":
			raise IrafError("Cannot find executable for task " + self.__name)
		if (self.__hasparfile and self.__parpath == ""):
			raise IrafError("Cannot find .par file for task " + self.__name)
		if self.__fullpath == None:
			# This follows the search strategy used by findexe in
			# cl/exec.c: first it checks in the BIN directory for the
			# "installed" version of the executable, and if that is not
			# found it tries the pathname given in the TASK declaration.
			#
			# expand iraf variables
			exename1 = expand(self.__filename)
			# get name of executable file without path
			basedir, basename = os.path.split(exename1)
			if basename == "":
				self.__fullpath = ""
				raise IrafError("No filename in task " + self.__name + \
					" definition: '" + self.__filename + "'")
			# for foreign tasks, just set path to filename (XXX will
			# want to improve this by checking os path for existence)
			if self.__foreign:
				self.__fullpath = self.__filename
			else:
				# first look in the task binary directory
				exename2 = expand(self.__pkgbinary + basename)
				if os.path.exists(exename2):
					self.__fullpath = exename2
				elif os.path.exists(exename1):
					self.__fullpath = exename1
				else:
					self.__fullpath = ""
					raise IrafError("Cannot find executable for task " + self.__name)
			if self.__hasparfile:
				pfile = os.path.join(basedir,self.__name + ".par")
				# check uparm first for scrunched version of par filename
				# with saved parameters
				if vars.has_key("uparm"):
					upfile = expand("uparm$" + self.scrunchName() + ".par")
				else:
					upfile = None
				if upfile and os.path.exists(upfile):
					# probably should do some sort of comparison with pfile
					# here to make sure this file is an up-to-date version?
					self.__parpath = upfile
				elif os.path.exists(pfile):
					self.__parpath = pfile
				else:
					# XXX need to parse header of cl tasks to get parameters
					# XXX if package has no par file, create a par list with just
					# mode parameter
					if isinstance(self,IrafPkg):
						self.__parpath = None
						self.__pars = [ irafpar.IrafParFactory(['mode','s','h','al']) ]
					else:
						self.__parpath = ""
						raise IrafError("Cannot find .par file for task " + self.__name)
				if self.__parpath: self.__pars = irafpar.readpar(self.__parpath)
				self.__pardict = {}
				for i in xrange(len(self.__pars)):
					p = self.__pars[i]
					self.__pardict[p.name] = p
	def unlearn(self):
		if self.__fullpath == None: self.initTask()
		if self.__hasparfile:
			exename1 = expand(self.__filename)
			basedir, basename = os.path.split(exename1)
			pfile = os.path.join(basedir,self.__name + ".par")
			if os.path.exists(pfile):
				self.__parpath = pfile
			else:
				raise IrafError("Cannot find .par file for task " + self.__name)
			self.__pars = irafpar.readpar(self.__parpath)
			self.__pardict = {}
			for i in xrange(len(self.__pars)):
				p = self.__pars[i]
				self.__pardict[p.name] = p
	def scrunchName(self):
		# scrunched version of filename is chars 1,2,last from package
		# name and chars 1-5,last from task name
		s = self.__pkgname[0:2]
		if len(self.__pkgname) > 2:
			s = s + self.__pkgname[-1:]
		s = s + self.__name[0:5]
		if len(self.__name) > 6:
			s = s + self.__name[-1:]
		return s
	def __str__(self):
		s = '<IrafTask ' + self.__name + ' (' + self.__filename + ')' + \
			' Pkg: ' + self.__pkgname + ' Bin: ' + self.__pkgbinary
		if self.__cl: s = s + ' Cl'
		if self.__pset: s = s + ' Pset'
		if self.__foreign: s = s + ' Foreign'
		if self.__hidden: s = s + ' Hidden'
		if self.__hasparfile == 0: s = s + ' No parfile'
		if self.__tbflag: s = s + ' .tb'
		return s + '>'

# -----------------------------------------------------
# IRAF package class
# -----------------------------------------------------

class IrafPkg(IrafTask):
	"""IRAF package class (special case of IRAF task)"""
	def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
		IrafTask.__init__(self,prefix,name,suffix,filename,pkgname,pkgbinary)
		# a package cannot be a foreign task or be a pset (both of which get
		# specified through the filename)
		if self.getForeign() or self.getPset():
			raise IrafError("Bad filename for package " +
				pkgname + ": " + filename)
		self.__loaded = 0
	def getLoaded(self): return self.__loaded
	def run(self):
		if self.getFullpath() == None: self.initTask()
		# if already loaded, just add to _loadedPath
		global _loadedPath
		_loadedPath.append(self)
		if not self.__loaded:
			self.__loaded = 1
			loaded[self.getName()] = len(loaded)
			if _verbose:
				print "Loading pkg ",self.getName(), "("+self.getFullpath()+")",
				if self.getHasparfile():
					print "par", self.getParpath(), \
						"["+`len(self.getPars())`+"] parameters"
				print
			readcl(self.getFullpath(), self.getPkgname(), self.getPkgbinary())
	def __str__(self):
		s = '<IrafPkg ' + self.getName() + ' (' + self.getFilename() + ')' + \
			' Pkg: ' + self.getPkgname()
		if self.getHidden(): s = s + ' Hidden'
		if self.getHasparfile() == 0: s = s + ' No parfile'
		return s + '>'

# -----------------------------------------------------
# Load an IRAF package by name
# -----------------------------------------------------

def load(pkgname,doprint=1):
	"""Load an IRAF package by name.
	Set reload=0 to skip loading if package is already loaded (default
	is to reload anyway.)"""
	if not pkgs.has_key(pkgname):
		raise KeyError("Package "+pkgname+" is not defined")
	pkgs[pkgname].run()
	if doprint: listtasks(pkgname)

# -----------------------------------------------------
# Find an IRAF task by name
# -----------------------------------------------------

def getTask(taskname):
	"""Find an IRAF task by name.  Name may be either fully qualified
	(package.taskname) or just the taskname."""

	# Try assuming fully qualified name first
	task = tasks.get(taskname)
	if task:
		if _verbose: print 'found',taskname,'in tasks'
		return task
	# Maybe it is a package?  We assume packages have unique names.
	task = pkgs.get(taskname)
	if task:
		if _verbose: print 'found',taskname,'in pkgs'
		return task

	# Search loaded packages in reverse order
	for i in xrange(len(_loadedPath)):
		pkg = _loadedPath[-1-i].getName()
		task = tasks.get(pkg + '.' + taskname)
		if task:
			if _verbose: print 'found',pkg+'.'+taskname,'in tasks'
			return task
	raise KeyError("Task "+taskname+" is not defined")

# -----------------------------------------------------
# Run an IRAF task by name
# -----------------------------------------------------

def run(taskname):
	"""Run an IRAF task by name"""
	getTask(taskname).run()

# -----------------------------------------------------
# Read an IRAF .cl file and add symbols to dictionaries
# -----------------------------------------------------

def readcl(filename,pkgname,pkgbinary):
	"""Read an IRAF .cl file and add symbols to dictionaries"""

	# expand any IRAF variables in filename
	expfile = expand(filename)

	# if it exists, open it; otherwise return with warning
	if os.path.exists(expfile):
		fh = open(os.path.expanduser(expfile),'r')
	else:
		print 'WARNING: no such file', filename,'('+expfile+')'
		return

	# Pattern that matches a quoted string with embedded \"
	# From Freidl, Mastering Regular Expressions, p. 176.
	#
	# Modifications:
	# - I'm using the "non-capturing" parentheses (?:...) where
	#   possible; I only capture the part of the string between
	#   the quotes.

	required_whitespace = r'[ \t]+'
	optional_whitespace = r'[ \t]*'
	double = r'"(?P<double>[^"\\]*(?:\\.[^"\\]*)*)"' + optional_whitespace
	re_double = re.compile(double)

	# pattern that matches whitespace- or comma-terminated word
	re_word = re.compile(r'(?P<word>[^ \t,]+),?' + optional_whitespace)

	# Pattern that matches to end-of-line or semicolon;
	# also picks off first (whitespace-delimited) word.
	# Note I'm using the ungreedy match '*?' and the lookahead
	# match '(?=..)' functions for the tail so that any
	# trailing whitespace is not included in the 'value'
	# string.
	#
	# This pattern cannot fail to match.

	re_rest = re.compile(optional_whitespace + r'(?P<value>' + \
		r'(?P<firstword>[^ \t;]*)' + r'(?P<tail>[^;]*?))' + \
		optional_whitespace + r'(?=$|[;])')

	# Pattern that matches trailing backslashes at end of line
	re_bstrail = re.compile(r'\\*$')

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
	re_taskname = re.compile(taskname)

	# pattern matching space or comma separated list of one or more task names
	# note this will also match a list with a comma after the last item.  tough.
	tasklist = taskname + '+'

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

	# print statement takes a simple string (don't handle more complex versions)
	print_stmt = r'print' + optional_whitespace + r'\(' + \
		r'"(?P<printval>[^"\\]*(?:\\.[^"\\]*)*)"' + \
		optional_whitespace + r'\)' + optional_whitespace

	# equals print statement '= "string"'
	eqprint_stmt = r'=' + optional_whitespace + \
		r'"(?P<eqprintval>[^"\\]*(?:\\.[^"\\]*)*)"' + optional_whitespace

	# type statement takes a filename
	type_stmt = r'type' + required_whitespace + \
		r'(?P<typefilename>[^ \t;]+)' + optional_whitespace

	# miscellaneous statements to parse and ignore quietly
	# keep, clbye, clbye()
	misc_stmt = r'(?P<miscstmt>' + \
		r'keep|' + \
		r'clbye(?:' + optional_whitespace + \
			r'\(' + optional_whitespace + r'\))?' + \
		')' + optional_whitespace

	# combined statement
	combined_stmt = r'(?:' + set_stmt      + r')|' + \
					r'(?:' + set_file_stmt + r')|' + \
					r'(?:' + cl_redir_stmt + r')|' + \
					r'(?:' + package_stmt  + r')|' + \
					r'(?:' + task_stmt     + r')|' + \
					r'(?:' + hide_stmt     + r')|' + \
					r'(?:' + print_stmt    + r')|' + \
					r'(?:' + eqprint_stmt  + r')|' + \
					r'(?:' + type_stmt     + r')|' + \
					r'(?:' + misc_stmt     + r')'

	re_combined_stmt = re.compile(combined_stmt,re.DOTALL)

	line = fh.readline()
	nread = 1
	while line != '':
		# strip whitespace (including newline) off both ends and remove
		# any trailing comment
		line = _stripcomment(line)

		# skip blank lines (full-line comments look like blank lines after
		# _stripcomment)
		if len(line) == 0:
			i2 = len(line)
		elif line[0] == ';':
			i2 = 1
		else:
			# Append next line if this line ends with continuation character
			# or if it has a trailing comma.
			# Odd number of trailing backslashes means this is continuation.
			# (This is ugly -- can it be cleaned up?)
			while (line[-1:] == ",") or (line[-1:] == "\\"):
				if (line[-1:] == ","):
					pass
				elif (len(re_bstrail.search(line).group()) % 2 == 1):
					line = line[:-1]
				else:
					break
				line = line + _stripcomment(fh.readline())
				nread = nread+1

			# this regular expression match does most of the work

			mm = re_combined_stmt.match(line)

			if mm == None:
				mrest = re_rest.match(line,0)
				i2 = mrest.end()
				# If this is package name, load it.  Otherwise print warning.
				# Ignore trailing parameters on packages
				value = mrest.group('firstword')
				if pkgs.has_key(value):
					if value == pkgname:
						if _verbose:
							print "Skipping recursive load of package",value
					else:
						if _verbose:
							print "Loading package",value
						tail = string.strip(mrest.group('tail'))
						if _verbose and tail != '':
							print "(Ignoring package parameters '" + tail + "')"
						load(value,doprint=0)
				else:
					if _verbose:
						print filename + ":	Ignoring '" + line[:i2] + \
							"' (line " + `nread` + ")"
			elif mm.group('setfilename') != None:
				# This peculiar syntax 'set @filename' only gets used in the
				# zzsetenv.def file, where it reads extern.pkg.  That file
				# also gets read (in full cl mode) by clpackage.cl.  I get
				# errors if I read this during zzsetenv.def, so just ignore
				# it here...
				i2 = mm.end()
			elif mm.group('printval') != None:
				# print statement
				print mm.group('printval')
				i2 = mm.end()
			elif mm.group('eqprintval') != None:
				# equals print statement
				print mm.group('eqprintval')
				i2 = mm.end()
			elif mm.group('typefilename') != None:
				# copy file to stdout if it exists
				# Is there a standard library procedure to do this?
				typefile = mm.group('typefilename')
				# strip quotes
				mdq = re_double.match(typefile)
				if mdq != None: typefile = mdq.group('double')
				try:
					typefile = expand(typefile)
					if os.path.exists(typefile):
						fh_type = open(os.path.expanduser(typefile),'r')
						tline = fh_type.readline()
						while tline != '':
							print tline,
							tline = fh_type.readline()
						fh_type.close()
				except SyntaxError:
					print filename + ":	WARNING: Could not expand", \
						typefile, "(line " + `nread` + ")"
				i2 = mm.end()
			elif mm.group('packagename') != None:
				pkgname = mm.group('packagename')
				if mm.group('packagebin') != None:
					pkgbinary = mm.group('packagebin')
				i2 = mm.end()
			elif mm.group('miscstmt') != None:
				# Miscellaneous: parsed but quietly ignored
				i2 = mm.end()
			else:
				# other statements take a value
				i1 = mm.end()
				if line[i1] == '"':
					# strip off double quotes
					mdq = re_double.match(line,i1)
					if mdq == None:
						raise IrafError(filename + ": Unmatched quotes\n" + \
							"'" + line + "'")
					value = mdq.group('double')
					i2 = mdq.end()
				else:
					# no quotes, take everything to eol or semicolon
					mrest = re_rest.match(line,i1)
					value = mrest.group('value')
					i2 = mrest.end()

				if mm.group('clredir') != None:
					# open and read this file too
					readcl(value,pkgname,pkgbinary)
				elif mm.group('varname') != None:
					name = mm.group('varname')
					vars[name] = value
				elif mm.group('hidestmt') != None:
					# hide can take multiple task names
					mw = re_word.match(value,0)
					while mw != None:
						word = mw.group('word')
						try:
							getTask(word).setHidden(1)
						except KeyError, e:
							print filename + ":	WARNING: Could not find task", \
								word, "to hide (line " + `nread` + ")"
							print e
						mw = re_word.match(value,mw.end())
				elif mm.group('tasklist') != None:
					# assign value to each task in the list
					tlist = mm.group('tasklist')
					mtl = re_taskname.match(tlist)
					while mtl != None:
						name = mtl.group('taskname')
						prefix = mtl.group('taskprefix')
						suffix = mtl.group('tasksuffix')
						if suffix == '.pkg':
							newtask = IrafPkg(prefix,name,suffix,value,pkgname,pkgbinary)
							pkgs[name] = newtask
							tasks[pkgname+'.'+name] = newtask
						else:
							newtask = IrafTask(prefix,name,suffix,value,pkgname,pkgbinary)
							tasks[pkgname+'.'+name] = newtask
						mtl = re_taskname.match(tlist,mtl.end())
				else:
					if _verbose:
						print "Parsed but ignored line " + `nread` + \
							" '" + line + "'"

		if i2 < len(line):
			if line[i2] == ';':
				i2 = i2+1
			else:
				raise IrafError(filename + \
					": Non-blank characters after end of command\n" + \
					"'" + line + "'")
		line = line[i2:]
		if line == '':
			line = fh.readline()
			nread = nread+1
	fh.close()

# -----------------------------------------------------
# Expand a string with embedded IRAF variables (IRAF virtual filename)
# -----------------------------------------------------

# Input string is in format 'name$rest' or 'name$str(name2)' where
# name and name2 are defined in the vars dictionary.
# Returns string with IRAF variable name expanded to full host name.
# Input may also be a comma-separated list of strings to expand,
# in which case an expanded comma-separated list is returned.

# search for leading string without embedded '$'
__re_var_match = re.compile(r'(?P<varname>[^$]*)\$')

# search for string embedded in parentheses
# assumes no double embedding
__re_var_paren = re.compile(r'\((?P<varname>[^$]*)\)')

def expand(instring):
	"""Expand a string with embedded IRAF variables (IRAF virtual filename),
	allowing comma-separated lists
	"""
	# call _expand1 for each entry in comma-separated list
	wordlist = string.split(instring,",")
	outlist = []
	for word in wordlist:
		outlist.append(_expand1(word))
	return string.join(outlist,",")

def _expand1(instring):
	"""Expand a string with embedded IRAF variables (IRAF virtual filename)"""
	mm = __re_var_match.match(instring)
	if mm == None:
		mm = __re_var_paren.search(instring)
		if mm == None: return instring
		if vars.has_key(mm.group('varname')):
			return instring[:mm.start()] + \
				_expand1(mm.group('varname')+'$') + \
				instring[mm.end():]
	varname = mm.group('varname')
	if vars.has_key(varname):
		# recursively expand string after substitution
		return _expand1(vars[varname] + instring[mm.end():])
	else:
		raise IrafError("Undefined variable " + varname + \
			" in string " + instring)

# -----------------------------------------------------
# Utility function: print elements of list in ncols columns
# -----------------------------------------------------

# This probably exists somewhere in the Python standard libraries?
# If not and it is really useful, probably should move it
# somewhere else (and rewrite it too, this is crude...)

def _printcols(strlist,cols=5,width=80):
	ncol = 0
	nwid = 0
	for word in strlist:
		print word,
		ncol = ncol+1
		nwid = nwid + len(word) + 1
		if ncol >= cols:
			print "\n",
			ncol = 0
			nwid = 0
		elif nwid < width/cols*ncol:
			print (width/cols*ncol - nwid) * ' ',
			nwid = width/cols*ncol
	if ncol > 0: print "\n",

# -----------------------------------------------------
# Utility function: strip both blanks and trailing comments from string
# -----------------------------------------------------

# A bit tricky -- don't strip comment symbols inside quotes, and don't
# strip off unmatched quotes either.
# The stripcom pattern matches everything up to the first comment symbol (#),
# ignoring symbols inside matched quotes.

__double = r'"(?:[^"\\]*(?:\\.[^"\\]*)*)"'
__unpaired_double = r'"(?:[^"\\]*(?:\\.[^"\\]*)*(?:$|\\$))'
__re_stripcom = re.compile(r'(?:(?:[^#"]+)|' + __double + '|' + \
	__unpaired_double + ')*')

def _stripcomment(str):
	mm = __re_stripcom.match(str)
	return string.strip(mm.group())

# -----------------------------------------------------
# list contents of the dictionaries
# -----------------------------------------------------

# need ability to print/not print hidden tasks and packages

def listall():
	"""List IRAF packages, tasks, and variables"""
	print 'Packages:'
	listpkgs()
	print 'Loaded Packages:'
	listloaded()
	print 'Tasks:'
	listtasks()
	print 'Variables:'
	listvars()

def listpkgs():
	"""List IRAF packages"""
	keylist = pkgs.keys()
	if len(keylist) == 0:
		print 'No IRAF packages defined'
	else:
		keylist.sort()
		# append '/' to identify packages
		for i in xrange(len(keylist)): keylist[i] = keylist[i] + '/'
		_printcols(keylist)

def listloaded():
	"""List loaded IRAF packages"""
	keylist = loaded.keys()
	if len(keylist) == 0:
		print 'No IRAF packages loaded'
	else:
		keylist.sort()
		# append '/' to identify packages
		for i in xrange(len(keylist)): keylist[i] = keylist[i] + '/'
		_printcols(keylist)

def listtasks(pkglist=None):
	"""List IRAF tasks, optionally specifying a list of packages to include."""
	keylist = tasks.keys()
	if len(keylist) == 0:
		print 'No IRAF tasks defined'
	else:
		# make a dictionary of pkgs to list
		if pkglist:
			pkgdict = {}
			if type(pkglist) is types.StringType: pkglist = [ pkglist ]
			for p in pkglist:
				pthis = pkgs.get(p)
				if pthis:
					if pthis.getLoaded():
						pkgdict[p] = 1
					else:
						print 'Package',p,'has not been loaded'
				else:
					print 'Package',p,'is not defined'
			if not len(pkgdict):
				print 'No packages to list'
				return
		else:
			pkgdict = pkgs

		# print each package separately
		keylist.sort()
		lastpkg = ''
		tlist = []
		for tname in keylist:
			pkg, task = string.split(tname,'.')
			tobj = tasks[tname]
			if isinstance(tobj,IrafPkg):
				task = task + '/'
			elif tobj.getPset():
				task = task + '@'
			if pkg == lastpkg:
				tlist.append(task)
			else:
				if len(tlist) and pkgdict.has_key(lastpkg):
					print lastpkg + '/:'
					_printcols(tlist)
				tlist = [task]
				lastpkg = pkg
		if len(tlist) and pkgdict.has_key(lastpkg):
			print lastpkg + '/:'
			_printcols(tlist)

def listcurrent(n=1):
	"""List IRAF tasks in current package (equivalent to '?' in the cl.)
	(Actually this will list a secondary package instead of the last
	primary package. Fix that eventually.)
	
	If parameter n is specified, lists n most recent packages."""

	if len(_loadedPath):
		if n > len(_loadedPath): n = len(_loadedPath)
		plist = n*[None]
		for i in xrange(n):
			plist[i] = _loadedPath[-1-i].getName()
		listtasks(plist)
	else:
		print 'No IRAF tasks defined'

def listvars():
	"""List IRAF variables"""
	keylist = vars.keys()
	if len(keylist) == 0:
		print 'No IRAF variables defined'
	else:
		keylist.sort()
		for word in keylist:
			print word + '	= ' + vars[word]
