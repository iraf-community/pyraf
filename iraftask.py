"""module iraftask.py -- defines IrafTask and IrafPkg classes

$Id$

R. White, 1999 March 2
"""

import sys, os, string, re, types, time
import iraf, irafpar, irafexecute, minmatch

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
		self.__pkgbinary = pkgbinary
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
		self.__pars = None
		self.__pardict = None
		self.__parDictList = None
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

	# parameters are accessible as attributes

	def __getattr__(self,name):
		if name[:1] == '_': raise AttributeError(name)
		return self.get(name)

	def __setattr__(self,name,value):
		# hidden Python parameters go into the standard dictionary
		# (hope there are none of these in IRAF tasks)
		if name[:1] == '_':
			self.__dict__[name] = value
		else:
			self.set(name,value)

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

	# Get the IrafPar object for a parameter
	def getPar(self,param):
		if self.__fullpath == None: self.initTask()
		if not self.__hasparfile:
			raise KeyError("Task "+self.__name+" has no parameter file")
		try:
			return self.__pardict[param]
		except KeyError, e:
			raise KeyError("Error in parameter '" +
				param + "' for task " + self.__name +
				"\n" + str(e))

	# get value for parameter 'param' with minimum-matching
	# returns a string
	def get(self,param):
		return self.getPar(param).get()

	# set task parameter 'param' to value with minimum-matching
	def set(self,param,value):
		self.getPar(param).set(value)

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
			if iraf.verbose>1:
				print "Connected subproc run ", self.__name, \
					"("+self.__fullpath+")"
				self.lpar()
			try:
				# create the list of parameter dictionaries to use
				self.setParDictList()
				# run the task
				irafexecute.IrafExecute(self, iraf._vars)
				if iraf.verbose>1: print 'Successful task termination'
			except irafexecute.IrafProcessError, value:
				raise iraf.IrafError("Error running IRAF task " + self.__name +
					"\n" + str(value))

	def setParList(self,*args,**kw):
		# first expand all keywords to their full names
		fullkw = {}
		for key in kw.keys():
			param = self.getPar(key).name
			if fullkw.has_key(param):
				raise SyntaxError("Multiple values given for parameter " + 
					param + " in task " + self.__name)
			fullkw[param] = kw[key]

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
			if fullkw.has_key(param):
				raise SyntaxError("Multiple values given for parameter " + 
					param + " in task " + self.__name)
			fullkw[param] = value
			ipar = ipar+1

		# now set all keyword parameters
		# XXX Need to add ability to set pset parameters using keywords too
		for param in fullkw.keys(): self.set(param,fullkw[param])

		# Number of arguments on command line, $nargs, is used by some IRAF
		# tasks (e.g. imheader).
		if self.__hasparfile: self.set('$nargs',len(args))

	def setParDictList(self):
		"""Parameter dictionaries for execution consist of this
		task's parameters, any psets referenced, all the
		parameters for packages that have been loaded, and the
		cl parameters.  Each dictionary has an associated name
		(because parameters could be asked for as task.parname
		as well as just parname).

		Create this list anew for each execution in case the
		list of loaded packages has changed.  It is stored as
		an attribute of this object so it can be accessed by
		the getParam() and setParam() methods."""

		if self.__fullpath == None: self.initTask()
		parDictList = [(self.__name,self.__pardict)]
		# look for any psets
		for param in self.__pars:
			if param.type == "pset":
				# pset name is from either parameter value (if not null)
				# or from parameter name (XXX I'm just guessing at this)
				try:
					psetname = param.get() or param.name
					pset = iraf.getTask(psetname)
					parDictList.append( (param.name,pset.getParDict()) )
				except KeyError:
					raise iraf.IrafError("Cannot get pset " +
						param.name + " for task " + self.__name)
		# package parameters
		for i in xrange(len(iraf._loadedPath)):
			pkg = iraf._loadedPath[-1-i]
			pd = pkg.getParDict()
			# don't include null dictionaries
			if pd:
				parDictList.append( (pkg.getName(), pd) )
		# cl
		parDictList.append( (iraf._cl.getName(),iraf._cl.getParDict()) )
		self.__parDictList = parDictList

	def setParam(self,qualifiedName,newvalue,check=1):
		"""Set parameter specified by qualifiedName to newvalue.
		If check is set to zero, does not check value to make sure it
		satisfies min-max range or choice list."""

		if self.__parDictList == None: self.setParDictList()

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
		"""Return parameter specified by qualifiedName, which can be a simple
		parameter name or can be [[package.]task.]paramname[.field].
		Paramname can also have an optional subscript, "param[1]".
		If native is non-zero, returns native format (e.g. float for
		floating point parameter.)  Default is return string value.
		"""

		if self.__parDictList == None: self.setParDictList()
		package, task, paramname, pindex, field = _splitName(qualifiedName)

		# XXX Need to add minimum match here for the various fields

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
							return self.getParam(v[1:],native=native)
						elif native:
							return paramdict[paramname].get(index=pindex,
								field=field,native=native)
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
					return paramdict[paramname].get(index=pindex,
						field=field,native=native)
				else:
					return v
		else:
			raise iraf.IrafError("Unknown parameter requested: " +
				qualifiedName)

	def lpar(self,verbose=0):
		if self.__fullpath == None: self.initTask()
		if not self.__hasparfile:
			print "Task",self.__name," has no parameter file"
		else:
			for i in xrange(len(self.__pars)):
				p = self.__pars[i]
				if iraf.verbose or p.name != '$nargs':
					print p.pretty(verbose=verbose or iraf.verbose)

	# fill in full pathnames of files and read parameter file (if it exists)
	# if names are None then need to run this
	# if names are "" then already tried and failed
	# if names are strings then already did it
	def initTask(self):
		if self.__fullpath == "":
			raise iraf.IrafError("Cannot find executable for task " + self.__name)
		if (self.__hasparfile and self.__parpath == ""):
			raise iraf.IrafError("Cannot find .par file for task " + self.__name)
		if self.__fullpath == None:
			# This follows the search strategy used by findexe in
			# cl/exec.c: first it checks in the BIN directory for the
			# "installed" version of the executable, and if that is not
			# found it tries the pathname given in the TASK declaration.
			#
			# Expand iraf variables.  We will try both paths if the expand fails.
			try:
				exename1 = iraf.expand(self.__filename)
				# get name of executable file without path
				basedir, basename = os.path.split(exename1)
			except iraf.IrafError, e:
				if iraf.verbose:
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
				# first look in the task binary directory
				try:
					exename2 = iraf.expand(self.__pkgbinary + basename)
				except iraf.IrafError, e:
					if iraf.verbose:
						print "Error searching for executable for task " + \
							self.__name
						print str(e)
					exename2 = ""
				if os.path.exists(exename2):
					self.__fullpath = exename2
				elif os.path.exists(exename1):
					self.__fullpath = exename1
				else:
					self.__fullpath = ""
					raise iraf.IrafError("Cannot find executable for task " +
						self.__name + "\nTried "+exename1+" and "+exename2)
			if self.__hasparfile:
				pfile = os.path.join(basedir,self.__name + ".par")
				# check uparm first for scrunched version of par filename
				# with saved parameters
				if iraf._vars.has_key("uparm"):
					upfile = iraf.expand("uparm$" + self.scrunchName() + ".par")
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
					# XXX if package has no par file, create a par list with
					# just mode and $nargs parameters
					if isinstance(self,IrafPkg):
						self.__parpath = None
						self.__pars = [
							irafpar.IrafParFactory(["mode","s","h","al"]),
							irafpar.IrafParFactory(["$nargs","i","h","0"]) ]
					else:
						self.__parpath = ""
						raise iraf.IrafError("Cannot find .par file for task " +
							self.__name)
				if self.__parpath: self.__pars = irafpar.readpar(self.__parpath)
				self.__pardict = minmatch.MinMatchDict()
				for i in xrange(len(self.__pars)):
					p = self.__pars[i]
					self.__pardict.add(p.name, p)
	def unlearn(self):
		if self.__fullpath == None: self.initTask()
		if self.__hasparfile:
			exename1 = iraf.expand(self.__filename)
			basedir, basename = os.path.split(exename1)
			pfile = os.path.join(basedir,self.__name + ".par")
			if os.path.exists(pfile):
				self.__parpath = pfile
			else:
				raise iraf.IrafError("Cannot find .par file for task " + self.__name)
			self.__pars = irafpar.readpar(self.__parpath)
			self.__pardict = minmatch.MinMatchDict()
			for i in xrange(len(self.__pars)):
				p = self.__pars[i]
				self.__pardict.add(p.name, p)
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
			raise iraf.IrafError("Bad filename for package " +
				pkgname + ": " + filename)
		self.__loaded = 0
	def getLoaded(self): return self.__loaded
	def run(self,*args,**kw):
		if self.getFullpath() == None: self.initTask()
		# set parameters
		apply(self.setParList,args,kw)
		# if already loaded, just add to iraf._loadedPath
		iraf._loadedPath.append(self)
		if not self.__loaded:
			self.__loaded = 1
			iraf._loaded[self.getName()] = len(iraf._loaded)
			if iraf.verbose>1:
				print "Loading pkg ",self.getName(), "("+self.getFullpath()+")",
				if self.getHasparfile():
					print "par", self.getParpath(), \
						"["+`len(self.getPars())`+"] parameters",
				print
			iraf.readcl(self.getFullpath(), self.getPkgname(), self.getPkgbinary())
			if iraf.verbose>1:
				print "Done loading",self.getName()
			# if other packages were loaded, put this on the
			# _loadedPath list one more time
			if iraf._loadedPath[-1] != self:
				iraf._loadedPath.append(self)
	def __str__(self):
		s = '<IrafPkg ' + self.getName() + ' (' + self.getFilename() + ')' + \
			' Pkg: ' + self.getPkgname()
		if self.getHidden(): s = s + ' Hidden'
		if self.getHasparfile() == 0: s = s + ' No parfile'
		return s + '>'

# -----------------------------------------------------
# Utility function to split qualified names into components
# -----------------------------------------------------

def _splitName(qualifiedName):
	"""qualifiedName looks like [[package.]task.]paramname[subscript][.field],
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

