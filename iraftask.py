"""module iraftask.py -- defines IrafTask and IrafPkg classes

$Id$

R. White, 1999 March 25
"""

import os, string, types
import iraf, irafpar, irafexecute, minmatch, epar

# -----------------------------------------------------
# IRAF task class
# -----------------------------------------------------

class IrafTask:

	"""IRAF task class"""

	def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
		sname = string.replace(name, '.', '_')
		if sname != name:
			print "Warning: '.' illegal in task name, changing", name, \
				"to", sname
		spkgname = string.replace(pkgname, '.', '_')
		if spkgname != pkgname:
			print "Warning: '.' illegal in pkgname, changing", pkgname, \
				"to", spkgname
		self.__name = sname
		self.__pkgname = spkgname
		self.__pkgbinary = []
		self.addPkgbinary(pkgbinary)
		# tasks with names starting with '_' are implicitly hidden
		if name[0] == '_':
			self.__hidden = 1
		else:
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
		self.__parList = None
		self.__parDictList = None
		if filename[0] == '$':
			# this is a foreign task
			self.__cl = 0
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
			# flag .cl scripts
			root, ext = os.path.splitext(filename)
			if ext == ".cl":
				self.__cl = 1
			else:
				self.__cl = 0

	# parameters are accessible as attributes

	def __getattr__(self,name):
		if name[:1] == '_': raise AttributeError(name)
		self.initTask()
		return self.__parList.get(name,native=1)

	def __setattr__(self,name,value):
		# hidden Python parameters go into the standard dictionary
		# (hope there are none of these in IRAF tasks)
		if name[:1] == '_':
			self.__dict__[name] = value
		else:
			self.initTask()
			self.__parList.set(name,value)

	# public accessor functions for attributes

	def getName(self):      return self.__name
	def getPkgname(self):   return self.__pkgname
	def getPkgbinary(self): return self.__pkgbinary
	def isHidden(self):     return self.__hidden
	def hasParfile(self):   return self.__hasparfile
	def getTbflag(self):    return self.__tbflag
	def getCl(self):        return self.__cl
	def getForeign(self):   return self.__foreign
	def getFilename(self):  return self.__filename

	def getFullpath(self):
		"""Return full path name of executable"""
		self.initTask()
		return self.__fullpath

	def getParpath(self):
		"""Return full path name of parameter file"""
		self.initTask()
		return self.__parpath

	def getParList(self):
		"""Return list of all parameter objects"""
		self.initTask()
		return self.__parList.getParList()

	def getParDict(self):
		"""Return (min-match) dictionary of all parameter objects"""
		self.initTask()
		return self.__parList.getParDict()

	def addPkgbinary(self, pkgbinary):
		"""Add another entry in list of possible package binary locations
		
		Parameter can be a string or a list of strings"""

		if not pkgbinary:
			return
		elif type(pkgbinary) == types.StringType:
			if pkgbinary and (pkgbinary not in self.__pkgbinary):
				self.__pkgbinary.append(pkgbinary)
		else:
			for pbin in pkgbinary:
				if pbin and (pbin not in self.__pkgbinary):
					self.__pkgbinary.append(pbin)

	# public access to set hidden attribute, which can be specified
	# in a separate 'hide' statement

	def setHidden(self,value=1):     self.__hidden = value

	def getParObject(self,param):
		"""Get the IrafPar object for a parameter"""
		self.initTask()
		return self.__parList.getParObject(param)

	def get(self,param,native=0):
		"""Return value for task parameter 'param' (with min-match)
		
		If native is non-zero, returns native format for value.  Default is
		to return a string.
		"""
		return self.getParObject(param).get(native=native)

	def set(self,param,value):
		"""Set task parameter 'param' to value (with minimum-matching)"""
		self.getParObject(param).set(value)

	# allow running task using taskname() or with
	# parameters as arguments, including keyword=value form.

	def __call__(self,*args,**kw):
		apply(self.run,args,kw)

	def run(self,*args,**kw):
		"""Execute this task with the specified arguments"""
		self.initTask()
		if self.__foreign:
			print "No run yet for foreign task '" + self.__name + "'"
		elif self.__cl:
			raise iraf.IrafError("Cannot run cl tasks yet: " +
				self.__name + " ("+self.__fullpath+")")
		else:
			# Special Stdout, Stdin, Stderr keywords are used to redirect IO
			#XXX This list is not complete yet -- need the appending versions
			#XXX (StdoutAppend, StderrAppend) and the graphics stream versions
			#XXX (StdoutIPG etc.) too
			additionalKW = {}
			closeFHList = []
			# output redirection keywords
			# eventually this will get bigger
			outputRedir = {'Stdout': 1 , 'Stderr': 1 }
			for key in ('Stdout', 'Stdin', 'Stderr'):
				if kw.has_key(key):
					# if it is a string, open as a file
					# otherwise assume it is a filehandle
					value = kw[key]
					if type(value) == types.StringType:
						# expand IRAF variables
						value = iraf.Expand(value)
						if outputRedir.has_key(key):
							# output file
							# check to see if it is dev$null
							if iraf.isNullFile(value): value = '/dev/null'
							fh = open(value,'w')
							# close this when we're done
							closeFHList.append(fh)
						else:
							# input file
							fh = open(value,'r')
							closeFHList.append(fh)
					else:
						if outputRedir.has_key(key):
							if not hasattr(value, 'write'):
								raise iraf.IrafError("%s redirection must "
									"be to a file handle or string\n"
									"Value is `%s'" %
									(key, value))
						elif not hasattr(value, 'read'):
							raise iraf.IrafError("%s redirection must "
								"be from a file handle or string\n"
								"Value is `%s'" %
								(key, value))
						fh = value
					additionalKW[string.lower(key)] = fh
					del kw[key]

			# set parameters
			apply(self.setParList,args,kw)
			if iraf.Verbose>1:
				print "Connected subproc run ", self.__name, \
					"("+self.__fullpath+")"
				self.lpar()
			try:
				# create the list of parameter dictionaries to use
				self.setParDictList()
				# run the task
				apply(irafexecute.IrafExecute,
						(self, iraf.varDict), additionalKW)
				if iraf.Verbose>1: print 'Successful task termination'
				for fh in closeFHList: fh.close()
			except irafexecute.IrafProcessError, value:
				for fh in closeFHList: fh.close()
				raise iraf.IrafError("Error running IRAF task " + self.__name +
					"\n" + str(value))

	def setParList(self,*args,**kw):
		"""Set arguments to task"""
		self.initTask()
		apply(self.__parList.setParList, args, kw)

	def setParDictList(self):
		"""Set the list of parameter dictionaries for task execution.

		Parameter dictionaries for execution consist of this
		task's parameters (which includes any psets
		referenced), all the parameters for packages that have
		been loaded, and the cl parameters.  Each dictionary
		has an associated name (because parameters could be
		asked for as task.parname as well as just parname).

		Create this list anew for each execution in case the
		list of loaded packages has changed.  It is stored as
		an attribute of this object so it can be accessed by
		the getParam() and setParam() methods.
		"""

		self.initTask()
		parDictList = [(self.__name,self.__parList.getParDict())]
		# package parameters
		for i in xrange(len(iraf.loadedPath)):
			pkg = iraf.loadedPath[-1-i]
			pd = pkg.getParDict()
			# don't include null dictionaries
			if pd:
				parDictList.append( (pkg.getName(), pd) )
		# cl
		parDictList.append( (iraf.cl.getName(),iraf.cl.getParDict()) )
		self.__parDictList = parDictList

	def setParam(self,qualifiedName,newvalue,check=1):
		"""Set parameter specified by qualifiedName to newvalue.

		qualifiedName can be a simple parameter name or can be
		[[package.]task.]paramname[.field].
		If check is set to zero, does not check value to make sure it
		satisfies min-max range or choice list.
		"""

		if self.__parDictList is None: self.setParDictList()

		package, task, paramname, pindex, field = _splitName(qualifiedName)

		# special syntax for package parameters
		if task == "_": task = self.__pkgname
				
		if task or package:
			if not package:
				# maybe this task is the name of one of the dictionaries?
				for dictname, paramdict in self.__parDictList:
					if dictname == task:
						if paramdict.has_key(paramname):
							paramdict[paramname].set(newvalue,index=pindex,
								field=field,check=check)
							return
						else:
							raise iraf.IrafError("Attempt to set unknown parameter " +
								qualifiedName)
			# Not one of our dictionaries, so must find the relevant task
			if package: task = package + '.' + task
			try:
				tobj = iraf.getTask(task)
				# reattach the index and/or field
				if pindex: paramname = paramname + '[' + `pindex+1` + ']'
				if field: paramname = paramname + '.' + field
				tobj.setParam(paramname,newvalue,check=check)
				return
			except KeyError:
				raise iraf.IrafError("Could not find task " + task +
					" to get parameter " + qualifiedName)
			except iraf.IrafError, e:
				raise iraf.IrafError(e + "\nFailed to set parameter " +
					qualifiedName)

		# no task specified, just search the standard dictionaries
		for dictname, paramdict in self.__parDictList:
			if paramdict.has_key(paramname):
				paramdict[paramname].set(newvalue,index=pindex,
					field=field,check=check)
				return
		else:
			raise iraf.IrafError("Attempt to set unknown parameter " +
				qualifiedName)

	def getParam(self,qualifiedName,native=0):
		"""Return parameter specified by qualifiedName.

		qualifiedName can be a simple parameter name or can be
		[[package.]task.]paramname[.field].
		Paramname can also have an optional subscript, "param[1]".
		If native is non-zero, returns native format (e.g. float for
		floating point parameter.)  Default is return string value.
		"""

		if self.__parDictList is None: self.setParDictList()
		package, task, paramname, pindex, field = _splitName(qualifiedName)

		# special syntax for package parameters
		if task == "_": task = self.__pkgname
				
		if task and (not package):
			# maybe this task is the name of one of the dictionaries?
			for dictname, paramdict in self.__parDictList:
				if dictname == task:
					if paramdict.has_key(paramname):
						v = paramdict[paramname].get(index=pindex,field=field)
						if v[:1] == ")":
							# parameter indirection: call getParam recursively
							# I'm making the assumption that indirection in a
							# field (e.g. in the min or max value) is allowed
							# and that it uses exactly the same syntax as
							# the argument to getParam, i.e. ')task.param'
							# refers to the p_value of the parameter,
							# ')task.param.p_min' refers to the min or
							# choice string, etc.
							return self.getParam(v[1:],native=native)
						elif native:
							# don't prompt again if this is a query parameter
							return paramdict[paramname].get(index=pindex,
								field=field,native=native,prompt=0)
						else:
							return v
					else:
						raise iraf.IrafError("Unknown parameter requested: " +
							qualifiedName)

		if package or task:
			# Not one of our dictionaries, so must find the relevant task
			if package: task = package + '.' + task
			try:
				tobj = iraf.getTask(task)
				if field:
					return tobj.getParam(paramname+'.'+field,native=native)
				else:
					return tobj.getParam(paramname,native=native)
			except KeyError:
				raise iraf.IrafError("Could not find task " + task +
					" to get parameter " + qualifiedName)
			except iraf.IrafError, e:
				raise iraf.IrafError(e + "\nFailed to get parameter " +
					qualifiedName)

		for dictname, paramdict in self.__parDictList:
			if paramdict.has_key(paramname):
				v = paramdict[paramname].get(index=pindex,field=field)
				if v[:1] == ")":
					# parameter indirection: call getParam recursively
					return self.getParam(v[1:],native=native)
				elif native:
					# don't prompt again if this is a query parameter
					return paramdict[paramname].get(index=pindex,
						field=field,native=native,prompt=0)
				else:
					return v
		else:
			raise iraf.IrafError("Unknown parameter requested: " +
				qualifiedName)

	def lpar(self,verbose=0):
		"""List the task parameters"""
		self.initTask()
		if not self.__hasparfile:
			print "Task",self.__name," has no parameter file"
		else:
			self.__parList.lpar()

	def epar(self):
		"""Edit the task parameters"""
		self.initTask()
		if not self.__hasparfile:
			print "Task",self.__name," has no parameter file"
		else:
			epar.epar(self)

	def initTask(self):
		"""Fill in full pathnames of files and read parameter file

		If names are None then need to run this.
		If names are "" then already tried and failed.  Try again
		in case something has changed.
		If names are strings then already did it.
		"""

		basedir = None
		if not self.__fullpath:
			# This follows the search strategy used by findexe in
			# cl/exec.c: first it checks in the BIN directory for the
			# "installed" version of the executable, and if that is not
			# found it tries the pathname given in the TASK declaration.
			#
			# Expand iraf variables.  We will try both paths if the expand fails.
			try:
				exename1 = iraf.Expand(self.__filename)
				# get name of executable file without path
				basedir, basename = os.path.split(exename1)
			except iraf.IrafError, e:
				if iraf.Verbose>0:
					print "Error searching for executable for task " + \
						self.__name
					print str(e)
				exename1 = ""
				# make our best guess that the basename is what follows the
				# last '$' in __filename
				basedir = ""
				s = string.split(self.__filename, "$")
				basename = s[-1]
			if basename == "":
				self.__fullpath = ""
				raise iraf.IrafError("No filename in task " + self.__name + \
					" definition: '" + self.__filename + "'")
			# for foreign tasks, just set path to filename (XXX will
			# want to improve this by checking os path for existence)
			if self.__foreign:
				self.__fullpath = self.__filename
			else:
				# first look in the task binary directories
				exelist = []
				for pbin in self.__pkgbinary:
					try:
						exelist.append(iraf.Expand(pbin + basename))
					except iraf.IrafError, e:
						if iraf.Verbose>0:
							print "Error searching for executable for task " + \
								self.__name
							print str(e)
				for exename2 in exelist:
					if os.path.exists(exename2):
						self.__fullpath = exename2
						break
				else:
					if os.path.exists(exename1):
						self.__fullpath = exename1
					else:
						self.__fullpath = ""
						raise iraf.IrafError("Cannot find executable for task " +
							self.__name + "\nTried "+exename1+" and "+exename2)

		if (not self.__parList):
			if not self.__hasparfile:
				# no parameter file -- create default parameter list anyway
				self.__parList = irafpar.IrafParList(self.__name)
			else:
				if basedir is None:
					try:
						exename1 = iraf.Expand(self.__filename)
						basedir, basename = os.path.split(exename1)
					except iraf.IrafError, e:
						if iraf.Verbose>0:
							print "Error searching for executable for task " + \
								self.__name
							print str(e)
						exename1 = ""
						basedir = ""
				pfile = os.path.join(basedir,self.__name + ".par")
				# check uparm first for scrunched version of par filename
				# with saved parameters
				if iraf.varDict.has_key("uparm"):
					upfile = iraf.Expand("uparm$" + self.scrunchName() + ".par")
				else:
					upfile = None
				if upfile and os.path.exists(upfile):
					# probably should do some sort of comparison with pfile
					# here to make sure this file is an up-to-date version?
					self.__parpath = upfile
				elif os.path.exists(pfile):
					self.__parpath = pfile
				elif isinstance(self,IrafPkg):
					self.__parpath = ""
				elif self.__cl:
					# XXX need to parse header of cl tasks to get parameters
					raise iraf.IrafError("Cannot run cl tasks yet: " +
						self.__name + " ("+self.__fullpath+")")
				else:
					self.__parpath = ""
					raise iraf.IrafError("Cannot find .par file for task " +
						self.__name)
				self.__parList = irafpar.IrafParList(self.__name,self.__parpath)

	def unlearn(self):
		"""Reset task parameters to their default values"""
		self.initTask()
		if self.__hasparfile:
			exename1 = iraf.Expand(self.__filename)
			basedir, basename = os.path.split(exename1)
			pfile = os.path.join(basedir,self.__name + ".par")
			if os.path.exists(pfile):
				self.__parpath = pfile
			else:
				raise iraf.IrafError("Cannot find .par file for task " +
					self.__name)
			self.__parList = irafpar.IrafParList(self.__name, self.__parpath)

	def scrunchName(self):
		"""Return scrunched version of filename (used for uparm files)

		Scrunched version of filename is chars 1,2,last from package
		name and chars 1-5,last from task name.
		"""
		s = self.__pkgname[0:2]
		if len(self.__pkgname) > 2:
			s = s + self.__pkgname[-1:]
		s = s + self.__name[0:5]
		if len(self.__name) > 5:
			s = s + self.__name[-1:]
		return s

	def __str__(self):
		s = '<IrafTask ' + self.__name + ' (' + self.__filename + ')' + \
			' Pkg: ' + self.__pkgname + ' Bin: ' + self.__pkgbinary[0]
		for pbin in self.__pkgbinary[1:]: s = s + ':' + pbin
		if self.__cl: s = s + ' Cl'
		if self.__foreign: s = s + ' Foreign'
		if self.__hidden: s = s + ' Hidden'
		if self.__hasparfile == 0: s = s + ' No parfile'
		if self.__tbflag: s = s + ' .tb'
		return s + '>'

# -----------------------------------------------------
# IRAF Pset class
# -----------------------------------------------------

class IrafPset(IrafTask):

	"""IRAF pset class (special case of IRAF task)"""

	def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
		IrafTask.__init__(self,prefix,name,suffix,filename,pkgname,pkgbinary)
		# check that parameters are consistent with for pset:
		# - not a foreign task
		# - has a parameter file
		if self.getForeign():
			raise iraf.IrafError("Bad filename for pset " +
				self.getName() + ": " + filename)
		if not self.hasParfile():
			raise KeyError("Pset "+self.getName()+" has no parameter file")

	def run(self,*args,**kw):
		# XXX should executing a pset run epar?
		raise iraf.IrafError("Cannot execute Pset " + self.getName())

	def __str__(self):
		s = '<IrafPset ' + self.getName() + ' (' + self.getFilename() + ')' + \
			' Pkg: ' + self.getPkgname()
		if self.isHidden(): s = s + ' Hidden'
		return s + '>'


# -----------------------------------------------------
# IRAF package class
# -----------------------------------------------------

class IrafPkg(IrafTask):

	"""IRAF package class (special case of IRAF task)"""

	def __init__(self, prefix, name, suffix, filename, pkgname, pkgbinary):
		IrafTask.__init__(self,prefix,name,suffix,filename,pkgname,pkgbinary)
		# a package cannot be a foreign task
		if self.getForeign():
			raise iraf.IrafError("Bad filename for package " +
				self.__name + ": " + filename)
		self.__loaded = 0
		self.__tasks = minmatch.MinMatchDict()
		self.__pkgs = minmatch.MinMatchDict()

	def getLoaded(self):
		"""Returns true if this package has already been loaded"""
		return self.__loaded

	def __getattr__(self, name, triedpkgs=None):
		"""Return the task 'name' from this package (if it exists).
		
		Also searches subpackages for the task.  triedpkgs is
		a dictionary with all the packages that have already been
		tried.  It is used to avoid infinite recursion when
		packages contain themselves.
		"""
		if name[:1] == '_':
			raise AttributeError(name)
		if not self.__loaded:
			raise AttributeError("Package " + self.getName() +
				" has not been loaded; no tasks are defined")
		t = self.__tasks.get(name)
		if t: return t
		# try subpackages
		if not triedpkgs: triedpkgs = {}
		triedpkgs[self] = 1
		for p in self.__pkgs.values():
			if p.__loaded and (not triedpkgs.get(p)):
				try:
					return p.__getattr__(name,triedpkgs=triedpkgs)
				except AttributeError, e:
					pass
		raise AttributeError(name)

	def addTask(self, task):
		"""Add a task to the task list for this package"""
		self.__tasks.add(task.getName(), task)
		# sub-packages get added to a separate list
		if isinstance(task, IrafPkg): self.__pkgs.add(task.getName(), task)

	def run(self,*args,**kw):
		"""Load this package with the specified parameters"""
		if self.getFullpath() is None: self.initTask()

		# Special _doprint keyword is used to control whether tasks are listed
		# after package has been loaded.  Default is to list them.
		if kw.has_key('_doprint'):
			if kw['_doprint']:
				doprint = 1
			else:
				doprint = 0
			del kw['_doprint']
		else:
			doprint = 1

		# Special _hush keyword is used to suppress most output when loading
		# packages.  Default is to print output.
		if kw.has_key('_hush'):
			if kw['_hush']:
				hush = 1
			else:
				hush = 0
			del kw['_hush']
		else:
			hush = 0

		# set parameters
		apply(self.setParList,args,kw)
		# if already loaded, just add to iraf.loadedPath
		iraf.loadedPath.append(self)
		if not self.__loaded:
			self.__loaded = 1
			iraf.addLoaded(self)
			if iraf.Verbose>1:
				print "Loading pkg ",self.getName(), "("+self.getFullpath()+")",
				if self.hasParfile():
					print "par", self.getParpath(), \
						"["+`len(self.getParList())`+"] parameters",
				print
			iraf.readCl(self.getFullpath(), self.getPkgname(), self.getPkgbinary(), hush=hush)
			if iraf.Verbose>1:
				print "Done loading",self.getName()
			# if other packages were loaded, put this on the
			# loadedPath list one more time
			if iraf.loadedPath[-1] != self:
				iraf.loadedPath.append(self)
		if doprint: iraf.listTasks(self)

	def __str__(self):
		s = '<IrafPkg ' + self.getName() + ' (' + self.getFilename() + ')' + \
			' Pkg: ' + self.getPkgname()
		if self.isHidden(): s = s + ' Hidden'
		if self.hasParfile() == 0: s = s + ' No parfile'
		return s + '>'

# -----------------------------------------------------
# Utility function to split qualified names into components
# -----------------------------------------------------

def _splitName(qualifiedName):
	"""Split qualifiedName into components.
	
	qualifiedName looks like [[package.]task.]paramname[subscript][.field],
	where subscript is an index in brackets.  Returns a tuple with
	(package, task, paramname, subscript, field). IRAF one-based subscript
	is changed to Python zero-based subscript.
	"""
	slist = string.split(qualifiedName,'.')
	package = None
	task = None
	pindex = None
	field = None
	ip = len(slist)-1
	if ip>0 and slist[ip][:2] == "p_":
		field = slist[ip]
		ip = ip-1
	paramname = slist[ip]
	if ip > 0:
		ip = ip-1
		task = slist[ip]
		if ip > 0:
			ip = ip-1
			package = slist[ip]
			if ip > 0:
				raise iraf.IrafError("Illegal syntax for parameter: " +
					qualifiedName)

	# parse possible subscript

	pstart = string.find(paramname,'[')
	if pstart >= 0:
		try:
			pend = string.rindex(paramname,']')
			pindex = int(paramname[pstart+1:pend])-1
			paramname = paramname[:pstart]
		except:
			raise iraf.IrafError("Illegal syntax for array parameter: " +
				qualifiedName)
	return (package, task, paramname, pindex, field)

