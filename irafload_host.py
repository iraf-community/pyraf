"""
module 'irafload.py' -- parse IRAF package definition files

$Id$
R. White, 1998 Dec 16
"""
import os, string, re, irafpar

# -----------------------------------------------------
# dictionaries:
# vars: all IRAF cl variables (defined with set name=value)
# tasks: all IRAF tasks (defined with task name=value)
# pkgs: all packages (defined with task name.pkg=value)
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

# -----------------------------------------------------
# IRAF task class
# -----------------------------------------------------

# This will eventually get enhanced to have all the parameters, etc.,
# for the task, but currently just has info on where to find the
# executable and some task properties.

# This could do something fancy -- check to see if a task is
# already in the list (with the same package) and if it is,
# just return a reference to the same IrafTask object.  This
# might be a way to allow us to 'bye' out of a multiply-loaded
# package?  Still tricky I think...

class IrafTask:
	def __init__(self, name, filename, pkgname, pkgbinary):
		self.name = name
		self.pkgname = pkgname
		self.pkgbinary = pkgbinary
		self.hidden = 0
		self.hasparfile = 1
		self.tbflag = 0
		# full path names and parameter list get filled in on demand
		self.fullpath = None
		self.parpath = None
		self.pars = None
		if filename[0] == '$':
			# this is a foreign task
			self.cl = 0
			self.pset = 0
			self.foreign = 1
			self.filename = filename[1:]
			# handle weird syntax for names
			if self.filename == 'foreign':
				self.filename = name
			elif filename[0:2] == '$0':
				self.filename = name + self.filename[2:]
		else:
			self.foreign = 0
			self.filename = filename
			# flag .cl scripts and psets
			root, ext = os.path.splitext(filename)
			if ext == ".cl":
				self.cl = 1
				self.pset = 0
			elif ext == ".par":
				self.pset = 1
				self.cl = 0
			else:
				self.cl = 0
				self.pset = 0
	#Sample host-level run syntax:
	#% /usr/stsci/irafx/bin/x_images.e
	#> imcopy
	#input: /data/sundog1/rlw/science/gasp/Compress/Coma/coma.fits
	#output: testout.fits
	#verbose: yes
	#/data/sundog1/rlw/science/gasp/Compress/Coma/coma.fits -> testout.fits
	#> ^D
	def run(self):
		if self.fullpath == None: self.initTask()
		if self.foreign:
			print "Fake run foreign task",self.name
		else:
			if self.cl:
				print "Fake run cl task",self.name, "("+self.fullpath+")"
				if self.hasparfile: self.lpar()
			else:
				print "Crude host-level run task",self.name, "("+self.fullpath+")"
				if self.hasparfile: self.lpar()
				slist = []
				slist.append(self.name + "\n")
				for i in xrange(len(self.pars)):
					p = self.pars[i]
					if p.param != 'mode':
						slist.append(p.get()+"\n")
				pun = os.popen(self.fullpath,"w")
				pun.writelines(slist)
				pun.flush()
				pun.close()

	def lpar(self):
		if self.fullpath == None: self.initTask()
		if not self.hasparfile:
			print "Task",self.name," has no parameter file"
		else:
			for i in xrange(len(self.pars)):
				p = self.pars[i]
				print p.pretty()

	# fill in full pathnames of files and read parameter file (if it exists)
	# if names are None then need to run this
	# if names are "" then already tried and failed
	# if names are strings then already did it
	def initTask(self):
		if self.fullpath == "":
			raise RuntimeError("Cannot find executable for task " + self.name)
		if (self.hasparfile and self.parpath == ""):
			raise RuntimeError("Cannot find .par file for task " + self.name)
		if self.fullpath == None:
			# expand iraf variables
			exename1 = expand(self.filename)
			# get name of executable file without path
			basedir, basename = os.path.split(exename1)
			if basename == "":
				self.fullpath = ""
				raise SyntaxError("No filename in task " + self.name + \
					" definition: '" + self.filename + "'")
			# for foreign tasks, just set path to filename (eventually will
			# want to improve this by checking os path)
			if self.foreign:
				self.fullpath = self.filename
			else:
				# first look in the task binary directory
				exename2 = expand(self.pkgbinary + basename)
				if os.path.exists(exename2):
					self.fullpath = exename2
				elif os.path.exists(exename1):
					self.fullpath = exename1
				else:
					self.fullpath = ""
					raise RuntimeError("Cannot find executable for task " + self.name)
			if self.hasparfile:
				pfile = os.path.join(basedir,self.name + ".par")
				if os.path.exists(pfile):
					self.parpath = pfile
					self.pars = irafpar.readpar(pfile)
					self.pardict = {}
					for i in xrange(len(self.pars)):
						p = self.pars[i]
						self.pardict[p.param] = p
				else:
					self.parpath = ""
					raise RuntimeError("Cannot find .par file for task " + self.name)
	def __str__(self):
		s = '<IrafTask ' + self.name + ' (' + self.filename + ')' + \
			' Pkg: ' + self.pkgname + ' Bin: ' + self.pkgbinary
		if self.cl: s = s + ' Cl'
		if self.pset: s = s + ' Pset'
		if self.foreign: s = s + ' Foreign'
		if self.hidden: s = s + ' Hidden'
		if self.hasparfile == 0: s = s + ' No parfile'
		if self.tbflag: s = s + ' .tb'
		return s + '>'

# -----------------------------------------------------
# IRAF package class
# -----------------------------------------------------

class IrafPkg(IrafTask):
	def __init__(self, name, filename, pkgname, pkgbinary):
		IrafTask.__init__(self,name,filename,pkgname,pkgbinary)
		# a package cannot be a foreign task (or have tbflag
		# set, or be a pset)
		if self.foreign: raise SyntaxError("Bad filename for package " + \
			pkgname + ": " + filename)
	def run(self):
		if self.fullpath == None: self.initTask()
		print "Loading pkg ",self.name, "("+self.fullpath+")",
		if self.hasparfile:
			print "par", self.parpath, "["+`len(self.pars)`+"] parameters"
		print
		readcl(self.fullpath, self.pkgname, self.pkgbinary)
	def __str__(self):
		s = '<IrafPkg ' + self.name + ' (' + self.filename + ')' + \
			' Pkg: ' + self.pkgname
		if self.hidden: s = s + ' Hidden'
		if self.hasparfile == 0: s = s + ' No parfile'
		return s + '>'

# -----------------------------------------------------
# basic initialization
# -----------------------------------------------------

# should these just be executed statements rather than a function?

def init():
	readcl('hlib$zzsetenv.def', '', 'bin$')
	readcl('hlib$clpackage.cl', '', 'bin$')

# -----------------------------------------------------
# Load an IRAF package by name
# -----------------------------------------------------

def load(pkgname):
	if not pkgs.has_key(pkgname):
		raise KeyError("Package "+pkgname+" is not defined")
	p = pkgs[pkgname]
	readcl(p.filename, pkgname, p.pkgbinary)

# -----------------------------------------------------
# Run an IRAF package by name
# -----------------------------------------------------

def run(taskname):
	if not tasks.has_key(taskname):
		raise KeyError("Task "+taskname+" is not defined")
	p = tasks[taskname]
	p.run()

# -----------------------------------------------------
# Locate the executable for an IRAF task
# -----------------------------------------------------

# This follows the search strategy used by findexe in cl/exec.c: first
# it checks in the BIN directory for the "installed" version of the
# executable, and if that is not found it tries the pathname given in the
# TASK declaration.
# Returns the full pathname to the executable.  Raises an exception if
# the executable cannot be found or if the task is not defined.

def findexe(taskname):
	if not tasks.has_key(taskname):
		raise KeyError("Task "+taskname+" is not defined")
	p = tasks[taskname]
	# for foreign tasks, just return immediately (eventually will
	# want to improve this by checking os path)
	if p.foreign: return p.filename

	# expand iraf variables
	exename1 = expand(p.filename)
	# get name of executable file without path
	basename = os.path.basename(exename1)
	if basename == '':
		raise SyntaxError("No filename in task " + taskname + \
			" definition: '" + p.filename + "'")
	# first look in the task binary directory
	exename2 = expand(p.pkgbinary + basename)
	if os.path.exists(exename2):
		return exename2
	elif os.path.exists(exename1):
		return exename1
	else:
		raise RuntimeError("Cannot find executable for task " + taskname)


# -----------------------------------------------------
# Read IRAF .cl file and add symbols to dictionaries
# -----------------------------------------------------

def readcl(filename,pkgname,pkgbinary):

	# print "xxx filename",filename,"pkgname",pkgname,"pkgbinary",pkgbinary
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
		line = stripcomment(line)
		if pkgname == 'quad': print line

		# skip blank lines (full-line comments look like blank lines after stripcom)
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
				line = line + stripcomment(fh.readline())
				if pkgname == 'quad': print line
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
						print "Skipping recursive load of package",value
					else:
						print "Loading package",value
						tail = string.strip(mrest.group('tail'))
						if tail != '':
							print "(Ignoring package parameters '" + tail + "')"
						load(value)
				else:
					print filename + ":	Ignoring '" + line[:i2] + \
						"' (line " + `nread` + ")"
			elif mm.group('setfilename') != None:
				# open and read this file too
				readcl(mm.group('setfilename'),pkgname,pkgbinary)
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
				# print "xxx '"+line+"'"
				if line[i1] == '"':
					# strip off double quotes
					mdq = re_double.match(line,i1)
					if mdq == None:
						raise SyntaxError(filename + ": Unmatched quotes\n" + \
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
						if tasks.has_key(word):
							tasks[word].hidden = 1
						elif pkgs.has_key(word):
							pkgs[word].hidden = 1
						else:
							print filename + ":	WARNING: Could not find task", \
								word, "to hide (line " + `nread` + ")"
						mw = re_word.match(value,mw.end())
				elif mm.group('tasklist') != None:
					# assign value to each task in the list
					tlist = mm.group('tasklist')
					mtl = re_taskname.match(tlist)
					while mtl != None:
						name = mtl.group('taskname')
						if mtl.group('tasksuffix') == '.pkg':
							newtask = IrafPkg(name,value,pkgname,pkgbinary)
							pkgs[name] = newtask
						else:
							newtask = IrafTask(name,value,pkgname,pkgbinary)
							tasks[name] = newtask
						if mtl.group('taskprefix') == '$': newtask.hasparfile = 0
						if mtl.group('tasksuffix') == '.tb': newtask.tbflag = 1
						mtl = re_taskname.match(tlist,mtl.end())
				else:
					print "Parsed but ignored line " + `nread` + \
						" '" + line + "'"

		if i2 < len(line):
			if line[i2] == ';':
				i2 = i2+1
			else:
				raise SyntaxError(filename + \
					": Non-blank characters after end of command\n" + \
					"'" + line + "'")
		line = line[i2:]
		if line == '':
			line = fh.readline()
			nread = nread+1
	fh.close()

# -----------------------------------------------------
# Expand a string with embedded IRAF variable
# -----------------------------------------------------

# Input string is in format 'name$rest' or 'name$str(name2)' where
# name and name2 are defined in the vars dictionary.
# Returns string with IRAF variable name expanded to full host name.

# search for leading string without embedded '$'
__re_var_match = re.compile(r'(?P<varname>[^$]*)\$')

# search for string embedded in parentheses
# assumes no double embedding
__re_var_paren = re.compile(r'\((?P<varname>[^$]*)\)')

def expand(instring):
	mm = __re_var_match.match(instring)
	if mm == None:
		mm = __re_var_paren.search(instring)
		if mm == None: return instring
		if vars.has_key(mm.group('varname')):
			return instring[:mm.start()] + \
				expand(mm.group('varname')+'$') + \
				instring[mm.end():]
	varname = mm.group('varname')
	if vars.has_key(varname):
		# recursively expand string after substitution
		return expand(vars[varname] + instring[mm.end():])
	else:
		raise SyntaxError("Undefined variable " + varname + \
			" in string " + instring)

# -----------------------------------------------------
# Utility function: print elements of list in ncols columns
# -----------------------------------------------------

# This probably exists somewhere in the Python standard libraries?
# If not and it is really useful, probably should move it
# somewhere else (and rewrite it too, this is crude...)

def printcols(strlist,cols=5,width=80):
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

def stripcomment(str):
	mm = __re_stripcom.match(str)
	return string.strip(mm.group())

# -----------------------------------------------------
# list contents of the dictionaries
# -----------------------------------------------------

# need ability to print/not print hidden tasks and packages

def listall():
	print 'Packages:'
	listpkgs()
	print 'Tasks:'
	listtasks()
	print 'Variables:'
	listvars()

def listpkgs():
	keylist = pkgs.keys()
	if len(keylist) == 0:
		print 'No IRAF packages defined'
	else:
		keylist.sort()
		# append '/' to identify packages
		for i in xrange(len(keylist)): keylist[i] = keylist[i] + '/'
		printcols(keylist)

def listtasks():
	keylist = tasks.keys()
	if len(keylist) == 0:
		print 'No IRAF tasks defined'
	else:
		keylist.sort()
		printcols(keylist)

def listvars():
	keylist = vars.keys()
	if len(keylist) == 0:
		print 'No IRAF variables defined'
	else:
		keylist.sort()
		for word in keylist:
			print word + '	= ' + vars[word]
