"""irafpar.py -- parse IRAF .par files and create lists of IrafPar objects

$Id$

R. White, 1999 July 16
"""

import os, sys, string, re
import irafgcur, irafimcur, irafukey, irafutils, minmatch
from types import *

# -----------------------------------------------------
# Warning (non-fatal) error.  Raise an exception if in
# strict mode, or print a message if iraf.Verbose is on.
# -----------------------------------------------------

# The iraf.py parameter verbose, set by iraf.setVerbose(), determines
# whether warning messages are printed when errors are found.  The
# strict parameter to various methods and functions can be set to
# raise an exception on errors; otherwise we do our best to work
# around errors, only raising an exception for really serious,
# unrecoverable problems.

import iraf

def warning(msg, strict=0, exception=SyntaxError):
	if strict:
		raise exception(msg)
	elif iraf.Verbose>0:
		print msg

# -----------------------------------------------------
# IRAF parameter factory
# -----------------------------------------------------

_string_types = [ 's', 'f', 'struct' ]
_string_list_types = [ '*struct', '*s', '*i' ]
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
	elif type in _string_list_types:
		return IrafParLS(fields,filename,strict)
	elif type == "*gcur" or type == "gcur":
		return IrafParGCur(fields,filename,strict)
	elif type == "*imcur" or type == "imcur":
		return IrafParImCur(fields,filename,strict)
	elif type == "*ukey" or type == "ukey":
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

flist = ("p_name", "p_xtype", "p_type", "p_mode", "p_prompt",
			"p_value", "p_default", "p_filename", "p_maximum", "p_minimum")
_getFieldDict = minmatch.MinMatchDict()
for field in flist: _getFieldDict.add(field, field)

flist = ("p_prompt", "p_value", "p_filename", "p_maximum", "p_minimum", "p_mode")
_setFieldDict = minmatch.MinMatchDict()
for field in flist: _setFieldDict.add(field, field)

del flist, field

# -----------------------------------------------------
# IRAF parameter base class
# -----------------------------------------------------

class IrafPar:

	"""Non-array IRAF parameter base class"""

	def __init__(self,fields,filename,strict=0):
		orig_len = len(fields)
		if orig_len < 3:
			raise SyntaxError("Fewer than 3 fields in parameter line")
		#
		# all the attributes that are going to get defined
		#
		self.filename = filename
		self.name   = fields[0]
		self.type   = fields[1]
		self.mode   = fields[2]
		self.value  = None
		self.min    = None
		self.max    = None
		self.choice = None
		self.prompt = None
		#
		# put fields into appropriate attributes
		#
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
							strict)
					# try to recover by assuming max string is prompt
					fields[6] = fields[5]
					fields[5] = ""
				else:
					warning("Max value illegal when choice list given" +
						" for parameter " + self.name, strict)
		else:
			# XXX should catch ValueError exceptions here and set to null
			# XXX could also check for missing comma (null prompt, prompt in max field)
			if fields[4]: self.min = self.coerceValue(fields[4],strict)
			if fields[5]: self.max = self.coerceValue(fields[5],strict)
		if self.min is not None and self.max is not None and self.max < self.min:
			warning("Max " + str(self.max) + " is less than min " + \
				str(self.min) + " for parameter " + self.name,
				strict)
			self.min, self.max = self.max, self.min
		self.prompt = irafutils.removeEscapes(fields[6])
		#
		# check attributes to make sure they are appropriate for
		# this parameter type (e.g. some do not allow choice list
		# or min/max)
		#
		self.checkAttribs(strict)
		#
		# check parameter value to see if it is correct
		#
		try:
			self.checkValue(self.value,strict)
		except ValueError, e:
			warning("Illegal initial value for parameter\n" + str(e),
				strict, exception=ValueError)
			# Set illegal values to null string, just like IRAF
			self.value = ""

	def checkAttribs(self,strict=0):
		# by default no restrictions on attributes
		pass

	def setChoice(self,s,strict=0):
		"""Set choice parameter from string s"""
		clist = _getChoice(self,s,strict)
		newchoice = len(clist)*[0]
		for i in xrange(len(clist)):
			newchoice[i] = self.coerceValue(clist[i])
		self.choice = newchoice

	def getPrompt(self):
		"""Interactively prompt for parameter value"""
		pstring = string.strip( string.split(self.prompt,"\n")[0] )
		if self.choice:
			schoice = [None]*len(self.choice)
			for i in xrange(len(self.choice)):
				schoice[i] = self.toString(self.choice[i])
			pstring = pstring + " (" + string.join(schoice,"|") + ")"
		elif self.min is not None or self.max is not None:
			pstring = pstring + " ("
			if self.min is not None: pstring = pstring + self.toString(self.min)
			pstring = pstring + ":"
			if self.max is not None: pstring = pstring + self.toString(self.max)
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
							(self.choice is None and self.min is None and \
							self.max is None):
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

		if field: return self.getField(field,native=native,prompt=prompt)

		# prompt for query parameters unless prompt is set to zero
		if prompt and self.mode == "q": self.getPrompt()

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if native:
			return self.value
		else:
			return self.toString(self.value)

	def getField(self, field, native=0, prompt=1):
		"""Get a parameter field value"""
		try:
			# expand field name using minimum match
			field = _getFieldDict[field]
		except KeyError, e:
			# re-raise the exception with a bit more info
			raise SyntaxError("Cannot get field " + field +
				" for parameter " + self.name + "\n" + str(e))
		if field == "p_name": return self.name
		elif field == "p_xtype": return self.type
		elif field == "p_type": return self.getPType()
		elif field == "p_mode": return self.mode
		elif field == "p_prompt": return self.prompt
		elif field == "p_value" or field == "p_default" or field == "p_filename":
			# these all appear to be equivalent -- they just return the
			# current PValue of the parameter (which is the same as the value
			# for non-list parameters, and is the filename for list parameters)
			return self.getPValue(native,prompt)
		elif field == "p_maximum":
			if native:
				return self.max
			else:
				return self.toString(self.max)
		elif field == "p_minimum":
			if self.choice is not None:
				if native:
					return self.choice
				else:
					schoice = [None]*len(self.choice)
					for i in xrange(len(self.choice)):
						schoice[i] = self.toString(self.choice[i])
					schoice = "|" + string.join(schoice,"|") + "|"
					return schoice
			else:
				if native:
					return self.min
				else:
					return self.toString(self.min)
		else:
			# XXX unimplemented fields:
			# p_length: maximum string length in bytes -- what to do with it?
			raise RuntimeError("Program bug in IrafPar.getField()\n" +
				"Requested field " + field + " for parameter " + self.name)

	def getPValue(self,native,prompt):
		"""Get p_value field for this parameter (same as get for non-list params)"""
		return self.get(native=native,prompt=prompt)

	def getPType(self):
		"""Get underlying datatype for this parameter (just self.type for normal params)"""
		return self.type

	def set(self, value, field=None, index=None, check=1):
		"""Set value of this parameter from a string or other value.
		Field is optional parameter field (p_prompt, p_minimum, etc.)
		Index is optional array index (zero-based).  Set check=0 to
		assign the value without checking to see if it is within
		the min-max range or in the choice list."""

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if field:
			self.setField(value,field,check=check)
		else:
			if check:
				self.value = self.checkValue(value)
			else:
				self.value = self.coerceValue(value)

	def setField(self, value, field, check=1):
		"""Set a parameter field value"""
		try:
			# expand field name using minimum match
			field = _setFieldDict[field]
		except KeyError, e:
			raise SyntaxError("Cannot set field " + field +
				" for parameter " + self.name + "\n" + str(e))
		if field == "p_prompt":
			self.prompt = irafutils.removeEscapes(irafutils.stripQuotes(value))
		elif field == "p_value":
			self.set(value,check=check)
		elif field == "p_filename":
			# this is only relevant for list parameters (*imcur, *gcur, etc.)
			self.set(value,check=check)
		elif field == "p_maximum":
			self.max = self.coerceOneValue(value)
		elif field == "p_minimum":
			if type(value) == StringType and '|' in value:
				self.setChoice(irafutils.stripQuotes(value))
			else:
				self.min = self.coerceOneValue(value)
		elif field == "p_mode":
			# not doing any type or value checking here -- setting mode is
			# rare, so assume that it is being done correctly
			self.mode = value
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
		return self.checkOneValue(v)

	def checkOneValue(self,v):
		"""Checks a single value to see if it is in range or choice list

		Allows indirection strings starting with ")".  Assumes
		v has already been converted to right value by
		coerceOneValue.  Returns value if OK, or raises
		ValueError if not OK.
		"""
		if v is None or v == "" or \
				((type(v) is StringType) and (v[0] == ")")):
			return v
		elif self.choice is not None and not (v in self.choice):
			raise ValueError("Value '" + str(v) +
				"' is not in choice list for " + self.name)
		elif (self.min is not None and v < self.min) or \
			 (self.max is not None and v > self.max):
			raise ValueError("Value '" + str(v) + "' is out of min-max range for " +
				self.name)
		return v

	def coerceValue(self,value,strict=0):
		"""Coerce parameter to appropriate type
		
		Should accept None or null string.
		"""
		return self.coerceOneValue(value,strict)

	def coerceOneValue(self,value,strict=0):
		"""Coerce a scalar parameter to the appropriate type
		
		Default implementation simply prevents direct use of base class.
		Should accept None or null string.
		"""
		raise RuntimeError("Bug: base class IrafPar cannot be used directly")

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

		if self.choice is not None:
			s = s + "\n" + 32*" " + "|"
			nline = 33
			for i in xrange(len(self.choice)):
				sch = str(self.choice[i]) + "|"
				s = s + sch
				nline = nline + len(sch) + 1
				if nline > 80:
					s = s + "\n" + 32*" " + "|"
					nline = 33
		elif self.min is not None or self.max is not None:
			s = s + "\n" + 32*" "
			if self.min is not None:
				s = s + str(self.min) + " <= "
			s = s + self.name
			if self.max is not None:
				s = s + " <= " + str(self.max)
		return s

	def __str__(self):
		"""Return readable description of parameter"""
		s = "<" + self.__class__.__name__ + " " + self.name + " " + self.type
		s = s + " " + self.mode + " " + `self.value`
		if self.choice is not None:
			s = s + " |"
			for i in xrange(len(self.choice)):
				s = s + str(self.choice[i]) + "|"
		else:
			s = s + " " + `self.min` + " " + `self.max`
		s = s + ' "' + self.prompt + '">'
		return s

# -----------------------------------------------------
# IRAF array parameter base class
# -----------------------------------------------------

class IrafArrayPar(IrafPar):

	"""IRAF array parameter class"""

	def __init__(self,fields,filename,strict=0):
		orig_len = len(fields)
		if orig_len < 3:
			raise SyntaxError("Fewer than 3 fields in parameter line")
		#
		# all the attributes that are going to get defined
		#
		self.filename = filename
		self.name   = fields[0]
		self.type   = fields[1]
		self.mode   = fields[2]
		self.value  = None
		self.min    = None
		self.max    = None
		self.choice = None
		self.prompt = None
		self.dim    = None
		#
		while len(fields) < 7: fields.append("")
		# for array parameter, get dimensions from normal values field
		# and get values from fields after prompt
		ndim = int(fields[3])
		if ndim != 1:
			raise SyntaxError("Cannot handle multi-dimensional array" +
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
							strict)
					# try to recover by assuming max string is prompt
					fields[8] = fields[7]
					fields[7] = ""
				else:
					warning("Max value illegal when choice list given" +
						" for parameter " + self.name, strict)
		else:
			self.min = self.coerceOneValue(fields[6],strict)
			self.max = self.coerceOneValue(fields[7],strict)
		self.prompt = irafutils.removeEscapes(fields[8])
		if self.min is not None and self.max is not None and self.max < self.min:
			warning("Max " + str(self.max) + " is less than min " + \
				str(self.min) + " for parameter " + self.name,
				strict)
			self.min, self.max = self.max, self.min
		#
		# check attributes to make sure they are appropriate for
		# this parameter type (e.g. some do not allow choice list
		# or min/max)
		#
		self.checkAttribs(strict)
		#
		# check parameter value to see if it is correct
		#
		try:
			self.checkValue(self.value,strict)
		except ValueError, e:
			warning("Illegal initial value for parameter\n" + str(e),
				strict, exception=ValueError)
			# Set illegal values to null string, just like IRAF
			self.value = ""

	def get(self, field=None, index=None, lpar=0, prompt=1, native=0):
		"""Return value of this parameter as a string (or in native format
		if native is non-zero.)"""

		if field: return self.getField(field,native=native,prompt=prompt)

		# prompt for query parameters unless prompt is set to zero
		if prompt and self.mode == "q": self.getPrompt()

		if index is not None:
			try:
				if native:
					return self.value[index]
				else:
					return self.toString(self.value[index])
			except IndexError:
				raise SyntaxError("Illegal index [" + `index` +
					"] for array parameter " + self.name)
		if native:
			# return list of values for array
			return self.value
		else:
			# return blank-separated string of values for array
			sval = self.dim*[None]
			for i in xrange(self.dim):
				sval[i] = self.toString(self.value[i])
			return string.join(sval,' ')

	def getPType(self):
		"""Get underlying datatype for this parameter (strip off 'a' array params)"""
		return self.type[1:]

	def set(self, value, field=None, index=None, check=1):
		"""Set value of this parameter from a string or other value.
		Field is optional parameter field (p_prompt, p_minimum, etc.)
		Index is optional array index (zero-based).  Set check=0 to
		assign the value without checking to see if it is within
		the min-max range or in the choice list."""
		if index is not None:
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

	def checkValue(self,value,strict=0):
		"""Check and convert a parameter value.

		Raises an exception if the value is not permitted for this
		parameter.  Otherwise returns the value (converted to the
		right type.)
		"""
		v = self.coerceValue(value,strict)
		for i in xrange(self.dim): self.checkOneValue(v[i])
		return v

	def coerceValue(self,value,strict=0):
		"""Coerce parameter to appropriate type
		
		Should accept None or null string.  Must be an array.
		"""
		if (type(value) not in [ListType,TupleType]) or len(value) != self.dim:
			raise ValueError("Value must be a " + `self.dim` + \
				"-element array for "+self.name)
		v = self.dim*[0]
		for i in xrange(self.dim):
			v[i] = self.coerceOneValue(value[i],strict)
		return v

	def __str__(self):
		"""Return readable description of parameter"""
		s = "<" + self.__class__.__name__ + " " + self.name + " " + \
			self.type + "[" + str(self.dim) + "]"
		s = s + " " + self.mode + " " + `self.value`
		if self.choice is not None:
			s = s + " |"
			for i in xrange(len(self.choice)):
				s = s + str(self.choice[i]) + "|"
		else:
			s = s + " " + `self.min` + " " + `self.max`
		s = s + ' "' + self.prompt + '">'
		return s

# -----------------------------------------------------
# IRAF string parameter mixin class
# -----------------------------------------------------

class _StringMixin:

	"""IRAF string parameter mixin class"""

	def checkAttribs(self, strict):
		"""Check initial attributes to make sure they are legal"""
		if self.min:
			warning("Minimum value not allowed for string-type parameter " +
				self.name, strict)
			self.min = None
		if self.max:
			if not self.prompt:
				warning("Maximum value not allowed for string-type parameter " +
						self.name + " (probably missing comma)",
						strict)
				# try to recover by assuming max string is prompt
				self.prompt = self.max
			else:
				warning("Maximum value not allowed for string-type parameter " +
					self.name, strict)
			self.max = None
		# If not in strict mode, allow file (f) to act just like string (s).
		# Otherwise choice is also forbidden for file type
		if strict and self.type == "f" and self.choice:
			warning("Illegal choice value for type '" +
				self.type + "' for parameter " + self.name,
				strict)
			self.choice = None

	def setChoice(self,s,strict=0):
		"""Set choice parameter and min-match dictionary from string"""
		self.choice = _getChoice(self,s,strict)
		# minimum-match dictionary for choice list
		# value is full name of choice parameter
		self.mmchoice = minmatch.MinMatchDict()
		for c in self.choice: self.mmchoice.add(c, c)

	def toString(self, value):
		"""Convert a single (non-array) value of the appropriate type for
		this parameter to a string"""
		if value is None:
			return ""
		else:
			return value

	def coerceOneValue(self,value,strict=0):
		if value is None:
			return ""
		elif type(value) is StringType:
			# strip double quotes
			return irafutils.stripQuotes(value)
		else:
			return str(value)

	# slightly modified checkOneValue allows minimum match for
	# choice strings
	def checkOneValue(self,v):
		if v is None or v == "" or \
				((type(v) is StringType) and (v[0] == ")")):
			return v
		elif self.choice is not None:
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
		elif (self.min is not None and v < self.min) or \
			 (self.max is not None and v > self.max):
			raise ValueError("Value '" + str(v) +
				"' is out of min-max range for " + self.name)
		return v

# -----------------------------------------------------
# IRAF string parameter class
# -----------------------------------------------------

class IrafParS(_StringMixin, IrafPar):

	"""IRAF string parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF pset parameter class
# -----------------------------------------------------

class IrafParPset(IrafParS):

	"""IRAF pset parameter class"""

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
# IRAF list parameter base class
# -----------------------------------------------------

class IrafParL(_StringMixin, IrafPar):

	"""IRAF list parameter base class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		# filehandle for input file
		self.fh = None

	# Use getNextValue() method to implement a particular type

	def getNextValue(self):
		"""Return a string with next value"""
		raise RuntimeError("Bug: base class IrafParL cannot be used directly")

	def set(self, value, field=None, index=None, check=1):
		"""Set value of this parameter from a string or other value.
		Field is optional parameter field (p_prompt, p_minimum, etc.)
		Index is optional array index (zero-based).  Set check=0 to
		assign the value without checking to see if it is within
		the min-max range or in the choice list."""

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if field:
			self.setField(value,field,check=check)
		else:
			if check:
				self.value = self.checkValue(value)
			else:
				self.value = self.coerceValue(value)
			# close file if it is open
			if self.fh:
				self.fh.close()
				self.fh = None

	def get(self, field=None, index=None, lpar=0, prompt=1, native=0):
		"""Return value of this parameter as a string (or in native format
		if native is non-zero.)"""

		if field: return self.getField(field,native=native,prompt=prompt)
		if lpar: return self.value

		# prompt for query parameters unless prompt is set to zero
		# (I hope there are no query list parameters!)
		if prompt and self.mode == "q": self.getPrompt()

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if self.value:
			# non-null value means we're reading from a file
			if not self.fh:
				self.fh = open(iraf.Expand(self.value), "r")
			value = self.fh.readline()
			if not value:
				# EOF -- return string 'EOF'
				# XXX if native format, raise an exception?
				return "EOF"
			if value[-1:] == "\n": value = value[:-1]
		else:
			# if self.value is null, use the special getNextValue method (which should
			# always return a string)
			value = self.getNextValue()
		if native:
			return self.coerceValue(value)
		else:
			return value

	def getPValue(self,native,prompt):
		"""Get p_value field for this parameter (returns filename)"""
		return self.value

	def getPType(self):
		"""Get underlying datatype for this parameter (strip off '*' from list params)"""
		return self.type[1:]

# -----------------------------------------------------
# IRAF string list parameter class
# -----------------------------------------------------

class IrafParLS(IrafParL):

	"""IRAF string list parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def getNextValue(self):
		"""Return next string value"""
		self.getPrompt()
		retval = self.value
		self.value = ""
		return retval

# -----------------------------------------------------
# IRAF gcur (graphics cursor) parameter class
# -----------------------------------------------------

class IrafParGCur(IrafParL):

	"""IRAF graphics cursor parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def getNextValue(self):
		"""Return next graphics cursor value"""
		return irafgcur.gcur()

# -----------------------------------------------------
# IRAF imcur (image display cursor) parameter class
# -----------------------------------------------------

class IrafParImCur(IrafParL):

	"""IRAF image display cursor parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def getNextValue(self):
		"""Return next image display cursor value"""
		return irafimcur.imcur()

# -----------------------------------------------------
# IRAF ukey (user typed key) parameter class
# -----------------------------------------------------

class IrafParUKey(IrafParL):

	"""IRAF user typed key parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def getNextValue(self):
		"""Return next typed character"""
		return irafukey.ukey()

# -----------------------------------------------------
# IRAF boolean parameter mixin class
# -----------------------------------------------------

class _BooleanMixin:

	"""IRAF boolean parameter mixin class"""

	def checkAttribs(self, strict):
		"""Check initial attributes to make sure they are legal"""
		if self.min:
			warning("Minimum value not allowed for boolean-type parameter " +
				self.name, strict)
			self.min = None
		if self.max:
			if not self.prompt:
				warning("Maximum value not allowed for boolean-type parameter " +
						self.name + " (probably missing comma)",
						strict)
				# try to recover by assuming max string is prompt
				self.prompt = self.max
			else:
				warning("Maximum value not allowed for boolean-type parameter " +
					self.name, strict)
			self.max = None
		if self.choice:
			warning("Choice values not allowed for boolean-type parameter " +
				self.name, strict)
			self.choice = None

	def toString(self, value):
		if value is None:
			return ""
		elif type(value) == StringType:
			# presumably an indirection value ')task.name'
			return value
		else:
			strval = ["no", "yes"]
			return strval[value]

	# accepts integer values 0,1 or string 'yes','no' and variants
	def coerceOneValue(self,value,strict=0):
		if value is None or value == 0 or value == 1: return value
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
# IRAF boolean parameter class
# -----------------------------------------------------

class IrafParB(_BooleanMixin,IrafPar):

	"""IRAF boolean parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF integer parameter mixin class
# -----------------------------------------------------

class _IntMixin:

	"""IRAF integer parameter mixin class"""

	def toString(self, value):
		if value is None:
			return "INDEF"
		else:
			return str(value)

	# coerce value to integer
	def coerceOneValue(self,value,strict=0):
		if value is None: return None
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
# IRAF integer parameter class
# -----------------------------------------------------

class IrafParI(_IntMixin,IrafPar):

	"""IRAF integer parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF integer array parameter class
# -----------------------------------------------------

class IrafParAI(_IntMixin,IrafArrayPar):

	"""IRAF integer array parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafArrayPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF real parameter mixin class
# -----------------------------------------------------

_re_d = re.compile(r'[Dd]')
_re_colon = re.compile(r':')

class _RealMixin:

	"""IRAF real parameter mixin class"""

	def checkAttribs(self, strict):
		"""Check initial attributes to make sure they are legal"""
		if self.choice:
			warning("Choice values not allowed for real-type parameter " +
				self.name, strict)
			self.choice = None

	def toString(self, value):
		if value is None:
			return "INDEF"
		else:
			return str(value)

	# coerce value to real
	def coerceOneValue(self,value,strict=0):
		if value is None: return None
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
				# assume this is indirection -- just save it as a string
				return s2
			else:
				# allow +dd:mm:ss.s sexagesimal format for floats
				value = 0.0
				vscale = 1.0
				vsign = 1
				i1 = 0
				mm = _re_colon.search(s2)
				if mm is not None:
					if s2[0] == "-":
						i1 = 1
						vsign = -1
					elif s2[0] == "+":
						i1 = 1
					while mm is not None:
						i2 = mm.start()
						value = value + int(s2[i1:i2])/vscale
						i1 = i2+1
						vscale = vscale*60.0
						mm = _re_colon.search(s2,i1)
				# special handling for d exponential notation
				mm = _re_d.search(s2,i1)
				if mm is None:
					return vsign*(value + float(s2[i1:])/vscale)
				else:
					return vsign*(value + \
						float(s2[i1:mm.start()]+"E"+s2[mm.end():])/vscale)

# -----------------------------------------------------
# IRAF real parameter class
# -----------------------------------------------------

class IrafParR(_RealMixin,IrafPar):

	"""IRAF real parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF real array parameter class
# -----------------------------------------------------

class IrafParAR(_RealMixin,IrafArrayPar):

	"""IRAF real array parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafArrayPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF parameter list class
# -----------------------------------------------------

class IrafParList:

	"""List of Iraf parameters"""

	def __init__(self, taskname, filename="", parlist=None):
		"""Create a parameter list for task taskname
		
		If parlist is specified, uses it as a list of IrafPar objects.
		Else if filename is specified, reads a .par file.
		If neither is specified, generates a default list.
		"""
		self.__filename = filename
		self.__name = taskname

		if parlist is not None:
			self.__pars = parlist
		elif filename:
			self.__pars = _readpar(filename)
		else:
			# create empty list if no filename is specified
			self.__pars = []

		# build minmatch dictionary of all parameters, including
		# those in psets
		self.__pardict = minmatch.MinMatchDict()
		psetlist = []
		for p in self.__pars:
			self.__pardict.add(p.name, p)
			if isinstance(p, IrafParPset): psetlist.append(p)

		# add mode, $nargs to parameter list if not already present
		if not self.__pardict.has_exact_key("mode"):
			p = IrafParFactory(["mode","s","h","al"])
			self.__pars.append(p)
			self.__pardict.add(p.name, p)
		if not self.__pardict.has_exact_key("$nargs"):
			p = IrafParFactory(["$nargs","i","h","0"])
			self.__pars.append(p)
			self.__pardict.add(p.name, p)

		# Now add the pset parameters
		# Work from the pset's pardict because then we get
		# parameters from nested psets too
		for p in psetlist:
			# silently ignore parameters from this pset
			# that already are defined
			psetdict = p.get().getParDict()
			for pname in psetdict.keys():
				if not self.__pardict.has_exact_key(pname):
					self.__pardict.add(pname, psetdict[pname])

	# parameters are accessible as attributes

	def __getattr__(self,name):
		if name[:1] == '_': raise AttributeError(name)
		return self.get(name,native=1)

	def __setattr__(self,name,value):
		# hidden Python parameters go into the standard dictionary
		# (hope there are none of these in IRAF tasks)
		if name[:1] == '_':
			self.__dict__[name] = value
		else:
			self.set(name,value)

	def __len__(self): return len(self.__pars)

	# public accessor functions for attributes

	def getFilename(self): return self.__filename
	def getParList(self): return self.__pars
	def getParDict(self): return self.__pardict
	def getParObject(self,param):
		try:
			return self.__pardict[param]
		except KeyError, e:
			raise e.__class__("Error in parameter '" +
				param + "' for task " + self.__name + "\n" + str(e))

	def get(self,param,native=0):
		"""Return value for task parameter 'param' (with min-match)
		
		If native is non-zero, returns native format for value.  Default is
		to return a string.
		"""
		return self.getParObject(param).get(native=native)

	def set(self,param,value):
		"""Set task parameter 'param' to value (with minimum-matching)"""
		self.getParObject(param).set(value)

	def setParList(self,*args,**kw):
		"""Set value of multiple parameters from list"""
		# first expand all keywords to their full names
		fullkw = {}
		for key in kw.keys():
			param = self.getParObject(key).name
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
		for param in fullkw.keys(): self.set(param,fullkw[param])

		# Number of arguments on command line, $nargs, is used by some IRAF
		# tasks (e.g. imheader).
		self.set('$nargs',len(args))

	def lpar(self,verbose=0):
		"""List the task parameters"""
		for i in xrange(len(self.__pars)):
			p = self.__pars[i]
			if iraf.Verbose>0 or p.name != '$nargs':
				print p.pretty(verbose=verbose or iraf.Verbose>0)

	def __str__(self):
		s = '<IrafParList ' + self.__name + ' (' + self.__filename + ') ' + \
			str(len(self.__pars)) + ' parameters>'
		return s

# -----------------------------------------------------
# Read IRAF .par file and return list of parameters
# -----------------------------------------------------

# Parameter file is basically comma-separated fields, but
# with some messy variations involving embedded quotes
# and the ability to break the final field across lines.

def _readpar(filename,strict=0):
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
				if mm is None:
					# Failure occurs only for unmatched leading quote.
					# Append more lines to get quotes to match.  (Probably
					# want to restrict this behavior to only the description
					# field.)
					while mm is None:
						nline = fh.readline()
						if nline == "":
							# serious error, run-on quote consumed entire file 
							raise SyntaxError(filename + ": Unmatched quote\n" +
								line)
						line = line + '\n' + string.rstrip(nline)
						mm = re_field.match(line,i1)
				if mm.group('comma') is not None:
					g = mm.group('comma')
					# check for trailing quote in unquoted string
					if g[-1:] == '"' or g[-1:] == "'":
						warning(filename + "\n" + line + "\n" +
								"Unquoted string has trailing quote",
								strict)
				elif mm.group('double') is not None:
					if mm.group('djunk'):
						warning(filename + "\n" + line + "\n" +
								"Non-blank follows quoted string",
								strict)
					g = mm.group('double')
				elif mm.group('single') is not None:
					if mm.group('sjunk'):
						warning(filename + "\n" + line + "\n" +
							"Non-blank follows quoted string",
							strict)
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
				warning(filename + "\n" + line + "\n" +
						"Duplicate parameter " + par.name,
						strict)
			else:
				param_dict[par.name] = par
				param_list.append(par)
		line = fh.readline()
	return param_list

# -----------------------------------------------------
# Utility routine for parsing choice string
# -----------------------------------------------------

_re_choice = re.compile(r'\|')

def _getChoice(self, s, strict):
	clist = string.split(s, "|")
	# string is allowed to start and end with "|", so ignore initial
	# and final empty strings
	if not clist[0]: del clist[0]
	if len(clist)>1 and not clist[-1]: del clist[-1]
	return clist

