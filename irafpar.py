"""module 'irafpar.py' -- parse IRAF .par files and create lists of
IrafPar objects

$Id$

R. White, 1999 March 4
"""

import os, sys, string, re, irafgcur, irafukey, minmatch
from types import *

# -----------------------------------------------------
# Warning (non-fatal) error.  Raise an exception if in
# strict mode, or print a message if iraf.verbose is on.
# -----------------------------------------------------

# The iraf.py parameter verbose, set by iraf.setVerbose(), determines
# whether warning messages are printed when errors are found.  The
# strict parameter to various methods and functions can be set to
# raise an exception on errors; otherwise we do our best to work
# around errors, only raising an exception for really serious,
# unrecoverable problems.

import iraf

def warning(msg, strict=0, exception=SyntaxError,
		filename=None, irafpar=None):
	# prepend filename to message if known
	if irafpar:
		prefix = irafpar.filename + ":\n"
	elif filename:
		prefix = filename + ":\n"
	if strict:
		raise exception(prefix + msg)
	elif iraf.verbose:
		print prefix + msg

# -----------------------------------------------------
# IRAF parameter factory
# -----------------------------------------------------

_string_types = [ 's', 'f', 'struct', '*imcur', '*struct', '*s', '*i']
_real_types = [ 'r', 'd' ]

def IrafParFactory(fields,filename=None,strict=0):

	"""IRAF parameter factory

	Set the strict parameter to non-zero value to do stricter parsing
	(to find errors in .par files)"""

	orig_len = len(fields)
	if orig_len < 3:
		raise SyntaxError("Fewer than 3 fields in parameter line")
	type = fields[1]
	if type in _string_types:
		return IrafParS(fields,filename,strict)
	elif type == "*gcur":
		return IrafParGCur(fields,filename,strict)
	elif type == "*ukey":
		return IrafParUKey(fields,filename,strict)
	elif type == "pset":
		return IrafParPset(fields,filename,strict)
	elif type in _real_types:
		return IrafParR(fields,filename,strict)
	elif type == "i":
		return IrafParI(fields,filename,strict)
	elif type == "b":
		return IrafParB(fields,filename,strict)
	elif type == "ar":
		return IrafParAR(fields,filename,strict)
	elif type == "ai":
		return IrafParAI(fields,filename,strict)
	elif type[:1] == "a":
		raise SyntaxError("Cannot handle arrays of type "+type)
	else:
		raise SyntaxError("Cannot handle parameter type "+type)

# -----------------------------------------------------
# Set up minmatch dictionaries for parameter fields
# -----------------------------------------------------

flist = ("p_name", "p_xtype", "p_mode", "p_prompt",
			"p_value", "p_filename", "p_maximum", "p_minimum")
_getFieldDict = minmatch.MinMatchDict()
for field in flist: _getFieldDict.add(field, field)

flist = ("p_prompt", "p_value", "p_filename", "p_maximum", "p_minimum")
_setFieldDict = minmatch.MinMatchDict()
for field in flist: _setFieldDict.add(field, field)

del flist, field

# -----------------------------------------------------
# IRAF parameter base class
# -----------------------------------------------------

class IrafPar:

	"""IRAF parameter base class"""

	def __init__(self,fields,filename,strict=0):
		orig_len = len(fields)
		if orig_len < 3:
			raise SyntaxError("Fewer than 3 fields in parameter line")
		#
		# all the attributes that are going to get defined (put them here
		# to make them easier to find)
		#
		self.filename = filename
		self.name   = fields[0]
		self.type   = fields[1]
		self.mode   = fields[2]
		self.value  = None
		self.dim    = 1
		self.min    = None
		self.max    = None
		self.choice = None
		self.prompt = None

	def setChoice(self,s,strict=0):
		"""Set choice parameter from string s"""
		clist = _getChoice(self,s,strict)
		newchoice = len(clist)*[0]
		for i in xrange(len(clist)):
			newchoice[i] = self.coerceOneValue(clist[i])
		self.choice = newchoice

	def getPrompt(self):
		"""Interactively prompt for parameter value"""
		pstring = string.strip( string.split(self.prompt,"\n")[0] )
		if self.choice:
			schoice = [None]*len(self.choice)
			for i in xrange(len(self.choice)):
				schoice[i] = self.toString(self.choice[i])
			pstring = pstring + " (" + string.join(schoice,"|") + ")"
		elif self.min != None or self.max != None:
			pstring = pstring + " ("
			if self.min != None: pstring = pstring + self.toString(self.min)
			pstring = pstring + ":"
			if self.max != None: pstring = pstring + self.toString(self.max)
			pstring = pstring + ")"
		# add current value as default
		if self.value: pstring = pstring + " (" + self.toString(self.value) + ")"
		pstring = pstring + ": "
		print pstring,
		value = string.strip(sys.stdin.readline())
		# loop until we get an acceptable value
		while (1):
			try:
				if value == "":
					# null input means use current value as default
					# null default is acceptable only if no min, max or choice
					if (self.value or self.value == 0) or \
							(self.choice == None and self.min == None and \
							self.max == None):
						return
				else:
					self.set(value)
					return
			except ValueError, e:
				print e
			print pstring,
			value = string.strip(sys.stdin.readline())

	def get(self, field=None, index=None, lpar=0, prompt=1, native=0):
		"""Return value of this parameter as a string (or in native format
		if native is non-zero.)"""
		# prompt for query parameters unless prompt is set to zero
		if prompt and self.mode == "q": self.getPrompt()
		if index != None:
			if self.dim < 2:
				raise SyntaxError("Parameter "+self.name+" is not an array")
			try:
				if native:
					return self.value[index]
				else:
					return self.toString(self.value[index])
			except IndexError:
				raise SyntaxError("Illegal index [" + `index` +
					"] for array parameter " + self.name)

		if field: return self.getField(field,native=native)

		if self.dim == 1:
			if native:
				return self.value
			else:
				return self.toString(self.value)
		elif native:
			# return list of values for array
			return self.value
		else:
			# return blank-separated string of values for array
			sval = self.dim*[None]
			for i in xrange(self.dim):
				sval[i] = self.toString(self.value[i])
			return string.join(sval,' ')

	def toString(self, value):
		"""Convert a single (non-array) value of the appropriate type for
		this parameter to a string"""
		if value == None:
			return ""
		else:
			return str(value)

	def getField(self, field, native=0):
		"""Get a parameter field value"""
		try:
			field = _getFieldDict[field]
		except KeyError, e:
			# re-raise the exception with a bit more info
			raise SyntaxError("Cannot get field " + field +
				" for parameter " + self.name + "\n" + str(e))
		if field == "p_name": return self.name
		elif field == "p_xtype": return self.type
		elif field == "p_mode": return self.mode
		elif field == "p_prompt": return self.prompt
		elif field == "p_value": return self.get(native=native)
		elif field == "p_filename": return str(self.value)
		elif field == "p_maximum": return self.toString(self.maximum)
		elif field == "p_minimum":
			if self.choice != None:
				schoice = [None]*len(self.choice)
				for i in xrange(len(self.choice)):
					schoice[i] = self.toString(self.choice[i])
				schoice = "|" + string.join(schoice,"|") + "|"
				return schoice
			else:
				return self.toString(self.minimum)
		else:
			# XXX unimplemented fields:
			# p_type: different than p_xtype?
			# p_length: length in bytes? IRAF words? something else?
			# p_default: from task parameter file (as opposed to current
			#    .par file)?
			raise RuntimeError("Program bug in IrafPar.getField()\n" +
				"Requested field " + field + " for parameter " + self.name)

	def set(self, value, field=None, index=None, check=1):
		"""Set value of this parameter from a string or other value.
		Field is optional parameter field (p_prompt, p_minimum, etc.)
		Index is optional array index (zero-based).  Set check=0 to
		assign the value without checking to see if it is within
		the min-max range or in the choice list."""
		if index != None:
			if self.dim < 2:
				raise SyntaxError("Parameter "+self.name+" is not an array")
			try:
				value = self.coerceOneValue(value)
				if check:
					self.value[index] = self.checkOneValue(value)
				else:
					self.value[index] = value
				return
			except IndexError:
				raise SyntaxError("Illegal index [" + `index` +
					"] for array parameter " + self.name)
		if field:
			self.setField(value,field,check=check)
		else:
			if check:
				self.value = self.checkValue(value)
			else:
				self.value = self.coerceValue(value)
			return

	def setField(self, value, field, check=1):
		"""Set a parameter field value"""
		try:
			field = _setFieldDict[field]
		except KeyError, e:
			raise SyntaxError("Cannot set field " + field +
				" for parameter " + self.name + "\n" + str(e))
		if field == "p_prompt":
			self.prompt = _removeEscapes(_stripQuote(value))
		elif field == "p_value":
			self.set(value,check=check)
		elif field == "p_filename":
			# this is only relevant for list parameters (*imcur, *gcur, etc.)
			self.value = _stripQuote(value)
		elif field == "p_maximum":
			self.maximum = self.coerceOneValue(value)
		elif field == "p_minimum":
			if type(value) == StringType and '|' in value:
				self.setChoice(_stripQuote(value))
			else:
				self.minimum = self.coerceOneValue(value)
		else:
			raise RuntimeError("Program bug in IrafPar.setField()" +
				"Requested field " + field + " for parameter " + self.name)

	def checkValue(self,value,strict=0):
		"""Check and convert a parameter value.

		Raises an exception if the value is not permitted for this
		parameter.  Otherwise returns the value (converted to the
		right type.)
		"""
		v = self.coerceValue(value,strict)
		if self.dim == 1:
			return self.checkOneValue(v)
		else:
			for i in xrange(self.dim): self.checkOneValue(v[i])
			return v

	def checkOneValue(self,v):
		"""Checks a single value to see if it is in range or choice list

		Ignores indirection strings starting with ")".  Assumes
		v has already been converted to right value by
		coerceOneValue.  Returns value if OK, or raises
		ValueError if not OK.
		"""
		if v == None or v == "" or \
				((type(v) is StringType) and (v[0] == ")")):
			return v
		elif self.choice != None and not (v in self.choice):
			raise ValueError("Value '" + str(v) +
				"' is not in choice list for " + self.name)
		elif (self.min != None and v < self.min) or \
			 (self.max != None and v > self.max):
			raise ValueError("Value '" + str(v) + "' is out of min-max range for " +
				self.name)
		return v

	def coerceOneValue(self,value,strict=0):
		"""Coerce a scalar parameter to the appropriate type
		
		Should accept None or null string.
		"""
		raise RuntimeError("Bug: base class IrafPar cannot be used directly")

	def coerceValue(self,value,strict=0):
		"""Coerce parameter to appropriate type
		
		Should accept None or null string.  Must be an array for
		an array parameter.
		"""
		if self.dim == 1:
			return self.coerceOneValue(value,strict)
		if (type(value) not in [ListType,TupleType]) or len(value) != self.dim:
			raise ValueError("Value must be a " + `self.dim` + \
				"-element integer array for "+self.name)
		v = self.dim*[0]
		for i in xrange(self.dim):
			v[i] = self.coerceOneValue(value[i],strict)
		return v

	def pretty(self,verbose=0):
		"""Return pretty list description of parameter"""
		# split prompt lines and add blanks in later lines to align them
		plines = string.split(self.prompt,'\n')
		for i in xrange(len(plines)-1): plines[i+1] = 32*' ' + plines[i+1]
		plines = string.join(plines,'\n')
		if self.mode == "h":
			s = "%13s = %-15s %s" % ("("+self.name,
						self.get(prompt=0,lpar=1)+")", plines)
		else:
			s = "%13s = %-15s %s" % (self.name,
						self.get(prompt=0,lpar=1), plines)
		if not verbose: return s

		if self.choice != None:
			s = s + "\n" + 32*" " + "|"
			nline = 33
			for i in xrange(len(self.choice)):
				sch = str(self.choice[i]) + "|"
				s = s + sch
				nline = nline + len(sch) + 1
				if nline > 80:
					s = s + "\n" + 32*" " + "|"
					nline = 33
		elif self.min != None or self.max != None:
			s = s + "\n" + 32*" "
			if self.min != None:
				s = s + str(self.min) + " <= "
			s = s + self.name
			if self.max != None:
				s = s + " <= " + str(self.max)
		return s

	def __str__(self):
		"""Return readable description of parameter"""
		s = "<IrafPar " + self.name + " " + self.type
		if self.dim > 1: s = s + "[" + str(self.dim) + "]"
		s = s + " " + self.mode + " " + `self.value`
		if self.choice != None:
			s = s + " |"
			for i in xrange(len(self.choice)):
				s = s + str(self.choice[i]) + "|"
		else:
			s = s + " " + `self.min` + " " + `self.max`
		s = s + ' "' + self.prompt + '">'
		return s

# -----------------------------------------------------
# IRAF string parameter class
# -----------------------------------------------------

class IrafParS(IrafPar):

	"""IRAF string parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		orig_len = len(fields)
		while len(fields) < 7: fields.append("")
		#
		self.value = fields[3]
		# string (s) can have choice of values; min,max must be null for
		# others if not in strict mode, allow file (f) to act just like
		# string (s)
		if self.type == "s" or ((not strict) and (self.type == "f")):
			# only min can be defined and it must have choices
			if fields[4] != "":
				self.setChoice(string.strip(fields[4]),strict)
			if fields[5] != "":
				if orig_len < 7:
					warning("Illegal max value for string-type parameter " + 
							self.name + " (probably missing comma)",
							strict, irafpar=self)
					# try to recover by assuming this string is prompt
					fields[6] = fields[5]
					fields[5] = ""
				else:
					warning("Illegal max value for string-type parameter " +
						self.name, strict, irafpar=self)
		else:
			# otherwise, min & max must be blank
			if fields[4] != "" or fields[5] != "":
				if orig_len < 7:
					warning("Illegal min/max/choice values for type '" +
							self.type + "' for parameter " + self.name +
							" (probably missing comma)", strict, irafpar=self)
					# try to recover by assuming max string is prompt
					fields[6] = fields[5]
					fields[5] = ""
				else:
					warning("Illegal min/max/choice values for type '" +
						self.type + "' for parameter " + self.name,
						strict, irafpar=self)
		self.prompt = _removeEscapes(fields[6])
		# check parameter to see if it is correct
		try:
			self.checkValue(self.value,strict)
		except ValueError, e:
			warning("Illegal initial value for parameter\n" + str(e),
				strict, irafpar=self, exception=ValueError)
			# Set to null string, just like IRAF
			self.value = ""

	def setChoice(self,s,strict=0):
		"""Set choice parameter and min-match dictionary from string"""
		self.choice = _getChoice(self,s,strict)
		# minimum-match dictionary for choice list
		# value is full name of choice parameter
		self.mmchoice = minmatch.MinMatchDict()
		for c in self.choice: self.mmchoice.add(c, c)

	def coerceOneValue(self,value,strict=0):
		if value == None:
			return ""
		elif type(value) is StringType:
			# strip double quotes
			return _stripQuote(value)
		else:
			return str(value)

	# slightly modified checkOneValue allows minimum match for
	# choice strings
	def checkOneValue(self,v):
		if v == None or v == "" or \
				((type(v) is StringType) and (v[0] == ")")):
			return v
		elif self.choice != None:
			try:
				v = self.mmchoice[v]
			except minmatch.AmbiguousKeyError, e:
				raise ValueError("Ambiguous value '" + str(v) +
					"' from choice list for " + self.name +
					"\n" + str(e))
			except KeyError, e:
				raise ValueError("Value '" + str(v) +
					"' is not in choice list for " + self.name +
					"\nChoices are " + string.join(self.choice,"|"))
		elif (self.min != None and v < self.min) or \
			 (self.max != None and v > self.max):
			raise ValueError("Value '" + str(v) +
				"' is out of min-max range for " + self.name)
		return v


# -----------------------------------------------------
# Utility function to strip single or double quotes off string
# -----------------------------------------------------

def _stripQuote(value):
	if value[:1] == '"':
		value = value[1:]
		if value[-1:] == '"':
			value = value[:-1]
	elif value[:1] == "'":
		value = value[1:]
		if value[-1:] == "'":
			value = value[:-1]
	return value

# -----------------------------------------------------
# Utility function to remove escapes from in front of quotes
# -----------------------------------------------------

def _removeEscapes(value):
	"""Remove escapes from in front of quotes (which IRAF seems to
	just stick in for fun sometimes.)
	Don't worry about multiple-backslash case -- this will replace
	\\" with just ", which is fine by me."""

	i = string.find(value,r'\"')
	while i>=0:
		value = value[:i] + value[i+1:]
		# search from beginning every time to handle multiple \\ case
		i = string.find(value,r'\"')
	i = string.find(value,r"\'")
	while i>=0:
		value = value[:i] + value[i+1:]
		i = string.find(value,r"\'")
	return value

# -----------------------------------------------------
# IRAF pset parameter class
# -----------------------------------------------------

class IrafParPset(IrafParS):
	"""IRAF graphics cursor parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafParS.__init__(self,fields,filename,strict)
	def get(self, field=None, index=None, lpar=0, prompt=1, native=0):
		"""Return pset value (IrafTask object)"""
		if index:
			raise SyntaxError("Parameter " + self.name +
				" is pset, cannot use index")
		if field: return self.getField(field)
		if lpar: return str(self.value)
		return iraf.getTask(self.value or self.name)
	def set(self, value, field=None, index=None, check=1):
		raise ValueError("Pset parameter " + self.name +
			" cannot be assigned a value")

# -----------------------------------------------------
# IRAF gcur (graphics cursor) parameter class
# -----------------------------------------------------

# XXX Need to upgrade this to handle file list inputs too.
# That is a bit tricky because we need to initialize the
# input list every time we start a new task.  Will need
# to add an initialization step for all list parameters.
# Probably should handle all list parameters at the same time.

class IrafParGCur(IrafParS):
	"""IRAF graphics cursor parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafParS.__init__(self,fields,filename,strict)
	def get(self, field=None, index=None, lpar=0, prompt=1, native=0):
		"""Return graphics cursor value"""
		if index:
			raise SyntaxError("Parameter " + self.name +
				" is graphics cursor, cannot use index")
		if field: return self.getField(field)
		if lpar: return str(self.value)
		return irafgcur.gcur()

# -----------------------------------------------------
# IRAF ukey (user typed key) parameter class
# -----------------------------------------------------

class IrafParUKey(IrafParS):
	"""IRAF user typed key parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafParS.__init__(self,fields,filename,strict)
	def get(self, field=None, index=None, lpar=0, prompt=1, native=0):
		"""Return typed character"""
		if index:
			raise SyntaxError("Parameter " + self.name +
				" is ukey parameter, cannot use index")
		if field: return self.getField(field)
		if lpar: return str(self.value)
		return irafukey.UserKey()()

# -----------------------------------------------------
# IRAF boolean parameter class
# -----------------------------------------------------

class IrafParB(IrafPar):
	"""IRAF boolean parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		orig_len = len(fields)
		while len(fields) < 7: fields.append("")
		#
		self.value = self.coerceValue(fields[3],strict)
		# other, min & max must be blank
		if fields[4] != "" or fields[5] != "":
			if orig_len < 7:
				warning("Illegal min/max/choice values for type '" +
						self.type + "' for parameter " + self.name +
						" (probably missing comma)",
						strict, irafpar=self)
				# try to recover by assuming max string is prompt
				fields[6] = fields[5]
				fields[5] = ""
			else:
				warning("Illegal min/max/choice values for type '" + \
					self.type + "' for parameter " + self.name,
					strict, irafpar=self)
		self.prompt = _removeEscapes(fields[6])
		# check parameter to see if it is correct
		self.checkValue(self.value,strict)

	def toString(self, value):
		if value == None:
			return ""
		elif type(value) == StringType:
			# presumably an indirection value ')task.name'
			return value
		else:
			strval = ["no", "yes"]
			return strval[value]

	# accepts integer values 0,1 or string 'yes','no' and variants
	def coerceOneValue(self,value,strict=0):
		if value == None or value == 0 or value == 1: return value
		tval = type(value)
		if tval is StringType:
			v2 = string.strip(value)
			if v2 == "":
				return None
			elif v2[0] == ")":
				# assume this is indirection -- for now just save it as a string
				return v2
			# even more strict would just accept lower-case "yes", "no"
			ff = string.lower(v2)
			if ff == "no" or ff == "n":
				return 0
			elif ff == "yes" or ff == "y":
				return 1
		elif tval is FloatType:
			# try converting to integer
			try:
				ival = int(value)
				if (ival == value) and (ival == 0 or ival == 1):
					return ival
			except Exception:
				pass
		raise ValueError("Illegal boolean value "+`value` +
			" for parameter " + self.name)

# -----------------------------------------------------
# IRAF integer parameter class
# -----------------------------------------------------

class IrafParI(IrafPar):
	"""IRAF integer parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		orig_len = len(fields)
		while len(fields) < 7: fields.append("")
		#
		self.value = self.coerceValue(fields[3],strict)
		s = string.strip(fields[4])
		if '|' in s:
			self.setChoice(s,strict)
			if fields[5] != "":
				if orig_len < 7:
					warning("Max value illegal when choice list given" +
							" for parameter " + self.name +
							" (probably missing comma)",
							strict, irafpar=self)
					# try to recover by assuming max string is prompt
					fields[6] = fields[5]
					fields[5] = ""
				else:
					warning("Max value illegal when choice list given" +
						" for parameter " + self.name, strict, irafpar=self)
		else:
			self.min = self.coerceOneValue(fields[4],strict)
			self.max = self.coerceOneValue(fields[5],strict)
		self.prompt = _removeEscapes(fields[6])
		if self.min != None and self.max != None and self.max < self.min:
			warning("Max " + str(self.max) + " is less than min " + \
				str(self.min) + " for parameter " + self.name,
				strict, irafpar=self)
			self.min, self.max = self.max, self.min
		# check parameter to see if it is correct
		self.checkValue(self.value,strict)

	def toString(self, value):
		if value == None:
			return "INDEF"
		else:
			return str(value)

	# coerce value to integer
	def coerceOneValue(self,value,strict=0):
		if value == None: return None
		tval = type(value)
		if tval is IntType:
			return value
		elif tval is FloatType:
			# try converting to integer
			try:
				ival = int(value)
				if (ival == value): return ival
			except Exception:
				pass
			raise ValueError("Illegal integer value " + `value` +
				" for parameter " + self.name)
		elif tval is StringType:
			s2 = string.strip(value)
			if s2 == "" or ((not strict) and (string.upper(s2) == "INDEF")) or \
					(strict and (s2 == "INDEF")):
				return None
			elif s2[0] == ")":
				# assume this is indirection -- for now just save it as a string
				return s2
			elif s2[-1:] == "x":
				# hexadecimal
				return string.atoi(s2[:-1],16)
			else:
				return int(s2)

# -----------------------------------------------------
# IRAF integer array parameter class
# -----------------------------------------------------

class IrafParAI(IrafParI):
	"""IRAF integer array parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		orig_len = len(fields)
		while len(fields) < 7: fields.append("")
		# for array parameter, get dimensions from normal values field
		# and get values from fields after prompt
		ndim = int(fields[3])
		if ndim != 1:
			raise SyntaxError("Cannot handle multi-dimensional arrays" +
				" for parameter " + self.name)
		self.dim = int(fields[4])
		while len(fields) < 9+self.dim: fields.append("")
		if len(fields) > 9+self.dim:
			raise SyntaxError("Too many values for array" +
				" for parameter " + self.name)
		#
		self.value = self.coerceValue(fields[9:9+self.dim],strict)
		s = string.strip(fields[6])
		if '|' in s:
			self.setChoice(s,strict)
			if fields[7] != "":
				if orig_len < 9:
					warning("Max value illegal when choice list given" +
							" for parameter " + self.name +
							" (probably missing comma)",
							strict, irafpar=self)
					# try to recover by assuming max string is prompt
					fields[8] = fields[7]
					fields[7] = ""
				else:
					warning("Max value illegal when choice list given" +
						" for parameter " + self.name, strict, irafpar=self)
		else:
			self.min = self.coerceOneValue(fields[6],strict)
			self.max = self.coerceOneValue(fields[7],strict)
		self.prompt = _removeEscapes(fields[8])
		if self.min != None and self.max != None and self.max < self.min:
			warning("Max " + str(self.max) + " is less than min " + \
				str(self.min) + " for parameter " + self.name,
				strict, irafpar=self)
			self.min, self.max = self.max, self.min
		# check parameter to see if it is correct
		self.checkValue(self.value,strict)

# -----------------------------------------------------
# IRAF real parameter class
# -----------------------------------------------------

_re_d = re.compile(r'[Dd]')
_re_colon = re.compile(r':')

class IrafParR(IrafPar):
	"""IRAF real parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		orig_len = len(fields)
		while len(fields) < 7: fields.append("")
		#
		self.value = self.coerceValue(fields[3],strict)
		s = string.strip(fields[4])
		if '|' in s:
			warning("Choice list not allowed for float parameter " +
					self.name, strict, irafpar=self)
		else:
			self.min = self.coerceOneValue(fields[4],strict)
			self.max = self.coerceOneValue(fields[5],strict)
		self.prompt = _removeEscapes(fields[6])
		if self.min != None and self.max != None and self.max < self.min:
			warning("Max " + str(self.max) + " is less than min " +
				" for parameter " + self.name + str(self.min),
				strict, irafpar=self)
			self.min, self.max = self.max, self.min
		# check parameter to see if it is correct
		self.checkValue(self.value,strict)

	def toString(self, value):
		if value == None:
			return "INDEF"
		else:
			return str(value)

	# coerce value to real
	def coerceOneValue(self,value,strict=0):
		if value == None: return None
		tval = type(value)
		if tval is FloatType:
			return value
		elif tval in [LongType,IntType]:
			return float(value)
		elif tval is StringType:
			s2 = string.strip(value)
			if s2 == "" or ((not strict) and (string.upper(s2) == "INDEF")) or \
					(strict and (s2 == "INDEF")):
				return None
			elif s2[0] == ")":
				# assume this is indirection -- for now just save it as a string
				return s2
			else:
				# allow +dd:mm:ss.s sexagesimal format for floats
				value = 0.0
				vscale = 1.0
				vsign = 1
				i1 = 0
				mm = _re_colon.search(s2)
				if mm != None:
					if s2[0] == "-":
						i1 = 1
						vsign = -1
					elif s2[0] == "+":
						i1 = 1
					while mm != None:
						i2 = mm.start()
						value = value + int(s2[i1:i2])/vscale
						i1 = i2+1
						vscale = vscale*60.0
						mm = _re_colon.search(s2,i1)
				# special handling for d exponential notation
				mm = _re_d.search(s2,i1)
				if mm == None:
					return vsign*(value + float(s2[i1:])/vscale)
				else:
					return vsign*(value + \
						float(s2[i1:mm.start()]+"E"+s2[mm.end():])/vscale)


# -----------------------------------------------------
# IRAF real array parameter class
# -----------------------------------------------------

class IrafParAR(IrafParR):
	"""IRAF real array parameter class"""
	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		orig_len = len(fields)
		while len(fields) < 7: fields.append("")
		# for array parameter, get dimensions from normal values field
		# and get values from fields after prompt
		ndim = int(fields[3])
		if ndim != 1:
			raise SyntaxError("Cannot handle multi-dimensional arrays" +
				" for parameter " + self.name)
		self.dim = int(fields[4])
		while len(fields) < 9+self.dim: fields.append("")
		if len(fields) > 9+self.dim:
			raise SyntaxError("Too many values for array" +
				" for parameter " + self.name)
		#
		self.value = self.coerceValue(fields[9:9+self.dim],strict)
		s = string.strip(fields[6])
		if '|' in s:
			warning("Choice list not allowed for float parameter " +
					self.name, strict, irafpar=self)
		else:
			self.min = self.coerceOneValue(fields[6],strict)
			self.max = self.coerceOneValue(fields[7],strict)
		self.prompt = _removeEscapes(fields[8])
		if self.min != None and self.max != None and self.max < self.min:
			warning("Max " + str(self.max) + " is less than min " + \
				str(self.min) + " for parameter " + self.name,
				strict, irafpar=self)
			self.min, self.max = self.max, self.min
		# check parameter to see if it is correct
		self.checkValue(self.value,strict)

# -----------------------------------------------------
# utility routine for parsing choice string
# -----------------------------------------------------

_re_choice = re.compile(r'\|')

def _getChoice(self, s, strict):
	if (s[0] != "|") or (s[-1] != "|"):
		warning("Choice string does not start and end with '|'" +
			" for parameter " + self.name, strict, irafpar=self)
	if s[0] == "|":
		i1 = 1
	else:
		i1 = 0
	clist = []
	mm = _re_choice.search(s,i1)
	while mm != None:
		i2 = mm.start()
		clist.append(s[i1:i2])
		i1 = mm.end()
		mm = _re_choice.search(s,i1)
	if i1 < len(s):
		clist.append(s[i1:])
	return clist

# -----------------------------------------------------
# Read IRAF .par file and return list of parameters
# -----------------------------------------------------

# Parameter file is basically comma-separated fields, but
# with some messy variations involving embedded quotes
# and the ability to break the final field across lines.

def readpar(filename,strict=0):
	"""Read IRAF .par file and return list of parameters"""

	# Patterns that match a quoted string with embedded \" or \'
	# From Freidl, Mastering Regular Expressions, p. 176.
	#
	# Modifications:
	# - I'm using the "non-capturing" parentheses (?:...) where
	#   possible; I only capture the part of the string between
	#   the quotes.
	# - Match leading white space and optional trailing comma.
	# - Pick up any non-whitespace between the closing quote and
	#   the comma or end-of-line (which is a syntax error.)
	#   Any matched string gets captured into djunk or sjunk
	#   variable, depending on which quotes were matched.

	whitespace = r'[ \t]*'
	optcomma = r',?'
	noncommajunk = r'[^,]*'
	double = whitespace + r'"(?P<double>[^"\\]*(?:\\.[^"\\]*)*)"' + whitespace + \
		r'(?P<djunk>[^,]*)' + optcomma
	single = whitespace + r"'(?P<single>[^'\\]*(?:\\.[^'\\]*)*)'" + whitespace + \
		r'(?P<sjunk>[^,]*)' + optcomma

	# Comma-terminated string that doesn't start with quote
	# Match explanation:
	# - match leading white space 
	# - if end-of-string then done with capture
	# - elif lookahead == comma then done with capture
	# - else match not-[comma | blank | quote] followed
	#     by string of non-commas; then done with capture
	# - match trailing comma if present
	#
	# Trailing blanks do get captured (which I think is
	# the right thing to do)

	comma = whitespace + r"(?P<comma>$|(?=,)|(?:[^, \t'" + r'"][^,]*))' + optcomma

	# Combined pattern

	field = '(?:' + comma + ')|(?:' + double + ')|(?:' + single + ')'
	re_field = re.compile(field,re.DOTALL)

	# Pattern that matches trailing backslashes at end of line
	re_bstrail = re.compile(r'\\*$')

	# Pattern that matches unclosed quote at end of line, indicating need
	# to read another line.  This can only be used after all other strings
	# have been removed.  (This could be made more clever.)  Apparently
	# only double-quoted strings are allow to extend across lines
	re_unclosed = re.compile('"')

	param_dict = {}
	param_list = []
	fh = open(os.path.expanduser(filename),'r')
	line = fh.readline()
	while line != "":
		# strip whitespace (including newline) off both ends
		line = string.strip(line)
		# skip comments and blank lines
		# "..." is weird line that occurs in cl.par
		if len(line)>0 and line[0] != '#' and line != "...":
			# Append next line if this line ends with continuation character.
			while line[-1:] == "\\":
				# odd number of trailing backslashes means this is continuation
				if (len(re_bstrail.search(line).group()) % 2 == 1):
					line = line[:-1] + string.rstrip(fh.readline())
				else:
					break
			flist = []
			i1 = 0
			while len(line) > i1:
				mm = re_field.match(line,i1)
				if mm == None:
					# Failure occurs only for unmatched leading quote.
					# Append more lines to get quotes to match.  (Probably
					# want to restrict this behavior to only the description
					# field.)
					while mm == None:
						nline = fh.readline()
						if nline == "":
							# serious error, run-on quote consumed entire file 
							raise SyntaxError(filename + ": Unmatched quote\n" +
								line)
						line = line + '\n' + string.rstrip(nline)
						mm = re_field.match(line,i1)
				if mm.group('comma') != None:
					g = mm.group('comma')
					# check for trailing quote in unquoted string
					if g[-1:] == '"' or g[-1:] == "'":
						warning("Unquoted string has trailing quote\n" +
								line, strict, filename=filename)
				elif mm.group('double') != None:
					if mm.group('djunk'):
						warning("Non-blank follows quoted string\n" + \
								line, strict, filename=filename)
					g = mm.group('double')
				elif mm.group('single') != None:
					if mm.group('sjunk'):
						warning("Non-blank follows quoted string\n" + \
								line, strict, filename=filename)
					g = mm.group('single')
				else:
					raise SyntaxError(filename + "\n" + line + "\n" + \
						"Huh? mm.groups()="+`mm.groups()`+"\n" + \
						"Bug: doesn't match single, double or comma??")
				flist.append(g)
				# move match pointer
				i1 = mm.end()
			try:
				par = IrafParFactory(flist,filename,strict=strict)
			except StandardError, exc:
				raise SyntaxError(filename + "\n" + line + "\n" + \
					str(flist) + "\n" + str(exc))
			if param_dict.has_key(par.name):
				warning("Duplicate parameter " + \
						par.name + "\n" + line, strict, filename=filename)
			else:
				param_dict[par.name] = par
				param_list.append(par)
		line = fh.readline()
	# add special $nargs parameter
	if not param_dict.has_key("$nargs"):
		try:
			flist = ["$nargs","i","h","0"]
			par = IrafParFactory(flist,strict=strict)
		except StandardError, exc:
			raise SyntaxError(filename + "\n" + 
				"Error creating $nargs parameter\n" + str(exc))
		param_dict[par.name] = par
		param_list.append(par)
	return param_list


