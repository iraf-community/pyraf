"""irafpar.py -- parse IRAF .par files and create lists of IrafPar objects

$Id$

R. White, 2000 January 7
"""

import os, sys, string, re, types
import irafgcur, irafimcur, irafukey, irafutils, minmatch, epar
from irafglobals import INDEF, Verbose, yes, no

# container class used for __deepcopy__ method
import copy
class _EmptyClass: pass

# -----------------------------------------------------
# Warning (non-fatal) error.  Raise an exception if in
# strict mode, or print a message if Verbose is on.
# -----------------------------------------------------

# Verbose, set by iraf.setVerbose(), determines
# whether warning messages are printed when errors are found.  The
# strict parameter to various methods and functions can be set to
# raise an exception on errors; otherwise we do our best to work
# around errors, only raising an exception for really serious,
# unrecoverable problems.

import iraf

def warning(msg, strict=0, exception=SyntaxError, level=0):
	if strict:
		raise exception(msg)
	elif Verbose>level:
		sys.stdout.flush()
		sys.stderr.write('Warning: %s' % msg)
		if msg[-1:] != '\n': sys.stderr.write('\n')

# -----------------------------------------------------
# IRAF parameter factory
# -----------------------------------------------------

_string_types = [ 's', 'f', 'struct' ]
_string_list_types = [ '*struct', '*s', '*f', '*i' ]
_real_types = [ 'r', 'd' ]

def IrafParFactory(fields,filename=None,strict=0):

	"""IRAF parameter factory

	fields is a list of the comma-separated fields in the .par file.
	Each entry is a string or None (indicating that field was omitted.)

	Set the strict parameter to non-zero value to do stricter parsing
	(to find errors in .par files.)"""

	if len(fields) < 3 or None in fields[0:3]:
		raise SyntaxError("At least 3 fields must be given")
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
	elif type == "as":
		return IrafParAS(fields,filename,strict)
	elif type[:1] == "a":
		raise SyntaxError("Cannot handle arrays of type %s" % type)
	else:
		raise SyntaxError("Cannot handle parameter type %s" % type)

# -----------------------------------------------------
# make an IrafPar variable (another factory function,
# using more descriptive notation for characteristics)
# -----------------------------------------------------

# dictionary mapping verbose types to short par-file types

_typedict = { 'string': 's',
			'char': 's',
			'file': 'f',
			'struct': 'struct',
			'int': 'i',
			'bool': 'b',
			'real': 'r',
			'double': 'd',
			'gcur': 'gcur',
			'imcur': 'imcur',
			'ukey': 'ukey',
			'pset': 'pset', }

def makeIrafPar(init_value, datatype=None, name="<anonymous>", mode="h",
	array_size=None, list_flag=0, min=None, max=None, enum=None, prompt="",
	strict=0, filename=None):

	"""Create an IrafPar variable"""

	# if init_value is already an IrafPar, just return it
	#XXX Could check parameters to see if they are ok
	if isinstance(init_value, IrafPar): return init_value

	#XXX Enhance this to determine datatype from init_value if it is omitted
	#XXX Could use _typedict.get(datatype,datatype) to allow short types to be used

	if datatype is None: raise ValueError("datatype must be specified")

	shorttype = _typedict[datatype]
	if array_size is not None:
		shorttype = "a" + shorttype
	if list_flag:
		shorttype = "*" + shorttype

	# messy stuff -- construct strings like we would read
	# from .par file for this parameter
	if array_size is None:
		# scalar parameter
		fields = [ name,
					shorttype,
					mode,
					init_value,
					min,
					max,
					prompt ]
		if fields[4] is None: fields[4] = enum
	else:
		# 1-dimensional array parameter
		fields = [ name,
					shorttype,
					mode,
					"1",					# number of dims
					array_size,				# dimension
					"1",					# apparently always 1
					min,
					max,
					prompt ]
		if fields[6] is None: fields[6] = enum
		if init_value is not None:
			for iv in init_value:
				fields.append(iv)
		else:
			fields = fields + array_size*[None]
	for i in range(len(fields)):
		if fields[i] is not None:
			fields[i] = str(fields[i])
	try:
		return IrafParFactory(fields, filename, strict=strict)
	except ValueError, e:
		errmsg = "Bad value for parameter `%s'\n%s" % (name, str(e))
		raise ValueError(errmsg)


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

# utility function to check whether string is a parameter field

def isParField(s):
	"""Returns true if string s appears to be a parameter field"""
	try:
		return (s[:2] == "p_") and _getFieldDict.has_key(s)
	except minmatch.AmbiguousKeyError, e:
		# If ambiguous match, assume it is a parameter field.
		# An exception will doubtless be raised later, but
		# there's really no good choice here.
		return 1

# basic IrafPar attributes
# IrafPar's are protected in setattr against adding arbitrary attributes,
# and this dictionary is used as a helper in instance initialization
_IrafPar_attr_dict = {
	"filename" : None,
	"name" : None,
	"type" : None,
	"mode" : None,
	"value" : None,
	"min" : None,
	"max" : None,
	"choice" : None,
	"choiceDict" : None,
	"prompt" : None,
	"flags" : 0,
	}

# flag bits tell whether value has been changed and
# whether it was set on the command line.
_changedFlag = 1
_cmdlineFlag = 2

# -----------------------------------------------------
# IRAF parameter base class
# -----------------------------------------------------

class IrafPar:

	"""Non-array IRAF parameter base class"""

	def __init__(self,fields,filename,strict=0):
		orig_len = len(fields)
		if orig_len < 3 or None in fields[0:3]:
			raise SyntaxError("At least 3 fields must be given")
		#
		# all the attributes that are going to get defined
		#
		self.__dict__.update(_IrafPar_attr_dict)
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
		while len(fields) < 7: fields.append(None)
		#
		self.value = self._coerceValue(fields[3],strict)
		if fields[4] is not None and '|' in fields[4]:
			self._setChoice(string.strip(fields[4]),strict)
			if fields[5] is not None:
				if orig_len < 7:
					warning("Max value illegal when choice list given" +
							" for parameter " + self.name +
							" (probably missing comma)",
							strict)
					# try to recover by assuming max string is prompt
					fields[6] = fields[5]
					fields[5] = None
				else:
					warning("Max value illegal when choice list given" +
						" for parameter " + self.name, strict)
		else:
			#XXX should catch ValueError exceptions here and set to null
			#XXX could also check for missing comma (null prompt, prompt
			#XXX in max field)
			if fields[4] is not None:
				self.min = self._coerceValue(fields[4],strict)
			if fields[5] is not None:
				self.max = self._coerceValue(fields[5],strict)
		if self.min not in [None, INDEF] and \
		   self.max not in [None, INDEF] and self.max < self.min:
			warning("Max " + str(self.max) + " is less than minimum " + \
				str(self.min) + " for parameter " + self.name,
				strict)
			self.min, self.max = self.max, self.min
		if fields[6] is not None:
			self.prompt = irafutils.removeEscapes(
							irafutils.stripQuotes(fields[6]))
		else:
			self.prompt = ''
		#
		# check attributes to make sure they are appropriate for
		# this parameter type (e.g. some do not allow choice list
		# or min/max)
		#
		self._checkAttribs(strict)
		#
		# check parameter value to see if it is correct
		#
		try:
			self.checkValue(self.value,strict)
		except ValueError, e:
			warning("Illegal initial value for parameter\n" + str(e),
				strict, exception=ValueError)
			# Set illegal values to None, just like IRAF
			self.value = None

	#--------------------------------------------
	# public accessor methods
	#--------------------------------------------

	def isLegal(self):
		"""Returns true if current parameter value is legal"""
		try:
			# apply a stricter definition of legal here
			# fixable values have already been fixed
			# don't accept None values
			self.checkValue(self.value)
			return self.value is not None
		except ValueError:
			return 0

	def setCmdline(self,value=1):
		"""Set cmdline flag"""
		# set through dictionary to avoid extra calls to __setattr__
		if value:
			self.__dict__['flags'] = self.flags | _cmdlineFlag
		else:
			self.__dict__['flags'] = self.flags & ~_cmdlineFlag

	def isCmdline(self):
		"""Return cmdline flag"""
		return (self.flags & _cmdlineFlag) == _cmdlineFlag

	def setChanged(self,value=1):
		"""Set changed flag"""
		# set through dictionary to avoid another call to __setattr__
		if value:
			self.__dict__['flags'] = self.flags | _changedFlag
		else:
			self.__dict__['flags'] = self.flags & ~_changedFlag

	def isChanged(self):
		"""Return changed flag"""
		return (self.flags & _changedFlag) == _changedFlag

	def setFlags(self,value):
		"""Set all flags"""
		self.__dict__['flags'] = value

	def isLearned(self, mode=None):
		"""Return true if this parameter is learned
		
		Hidden parameters are not learned; automatic parameters inherit
		behavior from package/cl; other parameters are learned.
		If mode is set, it determines how automatic parameters behave.
		If not set, cl.mode parameter determines behavior.
		"""
		if "l" in self.mode: return 1
		if "h" in self.mode: return 0
		if "a" in self.mode:
			if mode is None: mode = iraf.cl.mode
			if "h" in mode and "l" not in mode:
				return 0
		return 1

	#--------------------------------------------
	# other public methods
	#--------------------------------------------

	def getPrompt(self):
		"""Interactively prompt for parameter value"""
		if self.prompt:
			pstring = string.strip( string.split(self.prompt,"\n")[0] )
		else:
			pstring = self.name
		if self.choice:
			schoice = map(self.toString, self.choice)
			pstring = pstring + " (" + string.join(schoice,"|") + ")"
		elif self.min not in [None, INDEF] or \
			 self.max not in [None, INDEF]:
			pstring = pstring + " ("
			if self.min not in [None, INDEF]:
				pstring = pstring + self.toString(self.min)
			pstring = pstring + ":"
			if self.max not in [None, INDEF]:
				pstring = pstring + self.toString(self.max)
			pstring = pstring + ")"
		# add current value as default
		if self.value is not None:
			pstring = pstring + " (" + self.toString(self.value,quoted=1) + ")"
		pstring = pstring + ": "
		# print prompt, suppressing both newline and following space
		sys.stdout.write(pstring)
		sys.stdout.flush()
		ovalue = sys.stdin.readline()
		value = string.strip(ovalue)
		# loop until we get an acceptable value
		while (1):
			try:
				# null input usually means use current value as default
				# check it anyway since it might not be acceptable
				if value == "": value = self._nullPrompt()
				self.set(value)
				# None (no value) is not acceptable value after prompt
				if self.value is not None: return
				# if not EOF, keep looping
				if ovalue == "":
					sys.stdout.flush()
					raise EOFError("EOF on parameter prompt")
				print "Error: specify a value for the parameter"
			except ValueError, e:
				print str(e)
			print pstring,
			ovalue = sys.stdin.readline()
			value = string.strip(ovalue)

	def get(self, field=None, index=None, lpar=0, prompt=1, native=0, mode="h"):
		"""Return value of this parameter as a string (or in native format
		if native is non-zero.)"""

		if field and field != "p_value":
			# note p_value comes back to this routine, so shortcut that case
			return self._getField(field,native=native,prompt=prompt)

		# may prompt for value if prompt flag is set
		if prompt: self._optionalPrompt(mode)

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if native:
			rv = self.value
		else:
			rv = self.toString(self.value)
		return rv

	def set(self, value, field=None, index=None, check=1):
		"""Set value of this parameter from a string or other value.
		Field is optional parameter field (p_prompt, p_minimum, etc.)
		Index is optional array index (zero-based).  Set check=0 to
		assign the value without checking to see if it is within
		the min-max range or in the choice list."""

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if field:
			self._setField(value,field,check=check)
		else:
			if check:
				self.value = self.checkValue(value)
			else:
				self.value = self._coerceValue(value)
			self.setChanged()

	def checkValue(self,value,strict=0):
		"""Check and convert a parameter value.

		Raises an exception if the value is not permitted for this
		parameter.  Otherwise returns the value (converted to the
		right type.)
		"""
		v = self._coerceValue(value,strict)
		return self.checkOneValue(v,strict)

	def checkOneValue(self,v,strict=0):
		"""Checks a single value to see if it is in range or choice list

		Allows indirection strings starting with ")".  Assumes
		v has already been converted to right value by
		_coerceOneValue.  Returns value if OK, or raises
		ValueError if not OK.
		"""
		if v in [None, INDEF] or (type(v) is types.StringType and v[:1] == ")"):
			return v
		elif v == "":
			# most parameters treat null string as omitted value
			return None
		elif self.choice is not None and not self.choiceDict.has_key(v):
			raise ValueError("Value '" + str(v) +
				"' is not in choice list for " + self.name)
		elif (self.min not in [None, INDEF] and v<self.min):
			raise ValueError("Value `%s' for %s is less than minimum %s" %
				(str(v), self.name, str(self.min)))
		elif (self.max not in [None, INDEF] and v>self.max):
			raise ValueError("Value `%s' for %s is greater than maximum %s" %
				(str(v), self.name, str(self.max)))
		return v

	def dpar(self):
		"""Return dpar-style executable assignment for parameter"""
		sval = self.toString(self.value, quoted=1)
		if sval == "": sval = "None"
		s = "%s = %s" % (self.name, sval)
		return s

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
		elif self.min not in [None, INDEF] or self.max not in [None, INDEF]:
			s = s + "\n" + 32*" "
			if self.min not in [None, INDEF]:
				s = s + str(self.min) + " <= "
			s = s + self.name
			if self.max not in [None, INDEF]:
				s = s + " <= " + str(self.max)
		return s

	def save(self, dolist=0):
		"""Return .par format string for this parameter
		
		If dolist is set, returns fields as a list of strings.  Default
		is to return a single string appropriate for writing to a file.
		"""
		quoted = not dolist
		fields = 7*[""]
		fields[0] = self.name
		fields[1] = self.type
		fields[2] = self.mode
		fields[3] = self.toString(self.value,quoted=quoted)
		if self.choice is not None:
			schoice = map(self.toString, self.choice)
			schoice.insert(0,'')
			schoice.append('')
			fields[4] = repr(string.join(schoice,'|'))
		elif self.min not in [None,INDEF]:
			fields[4] = self.toString(self.min,quoted=quoted)
		if self.max not in [None,INDEF]:
			fields[5] = self.toString(self.max,quoted=quoted)
		if self.prompt:
			if quoted:
				sprompt = repr(self.prompt)
			else:
				sprompt = self.prompt
			# prompt can have embedded newlines (which are printed)
			sprompt = string.replace(sprompt, r'\012', '\n')
			sprompt = string.replace(sprompt, r'\n', '\n')
			fields[6] = sprompt
		# delete trailing null parameters
		for i in [6,5,4]:
			if fields[i] != "": break
			del fields[i]
		if dolist:
			return fields
		else:
			return string.join(fields, ',')

	#--------------------------------------------
	# special methods to give desired object syntax
	#--------------------------------------------

	# allow parameter object to be used in arithmetic expression

	def __coerce__(self, other):
		return coerce(self.get(native=1), other)

	# fields are accessible as attributes

	def __getattr__(self,field):
		if field[:1] == '_':
			raise AttributeError(field)
		try:
			return self._getField(field, native=1)
		except SyntaxError, e:
			raise AttributeError(str(e))

	def __setattr__(self,attr,value):
		# don't allow any new parameters to be added
		if self.__dict__.has_key(attr):
			self.__dict__[attr] = value
		elif isParField(attr):
			#XXX should check=0 be used here?
			self._setField(value, attr)
		else:
			raise AttributeError("No attribute %s for parameter %s" %
				(attr, self.name))

	def __deepcopy__(self, memo=None):
		"""Deep copy of this parameter object"""
		new = _EmptyClass()
		# shallow copy of dictionary suffices for most attributes
		new.__dict__ = self.__dict__.copy()
		# value, choice may be lists of atomic items
		if isinstance(self.value, types.ListType):
			new.value = list(self.value)
		if isinstance(self.choice, types.ListType):
			new.choice = list(self.choice)
		# choiceDict is OK with shallow copy because it will
		# always be reset if choices change
		new.__class__ = self.__class__
		return new

	def __getstate__(self):
		"""Return state info for pickle"""
		# choiceDict gets reconstructed
		if self.choice is None:
			return self.__dict__
		else:
			d = self.__dict__.copy()
			d['choiceDict'] = None
			return d

	def __setstate__(self, state):
		"""Restore state info from pickle"""
		self.__dict__ = state
		if self.choice is not None:
			self._setChoiceDict()

	def __str__(self):
		"""Return readable description of parameter"""
		s = "<" + self.__class__.__name__ + " " + self.name + " " + self.type
		s = s + " " + self.mode + " " + `self.value`
		if self.choice is not None:
			schoice = map(self.toString, self.choice)
			s = s + " |" + string.join(schoice,"|") + "|"
		else:
			s = s + " " + `self.min` + " " + `self.max`
		s = s + ' "' + self.prompt + '">'
		return s

	#--------------------------------------------
	# private methods -- may be used by subclasses, but should
	# not be needed outside this module
	#--------------------------------------------

	def _checkAttribs(self,strict=0):
		# by default no restrictions on attributes
		pass

	def _setChoice(self,s,strict=0):
		"""Set choice parameter from string s"""
		clist = _getChoice(self,s,strict)
		self.choice = map(self._coerceValue, clist)
		self._setChoiceDict()

	def _setChoiceDict(self):
		"""Create dictionary for choice list"""
		# value is name of choice parameter (same as key)
		self.choiceDict = {}
		for c in self.choice: self.choiceDict[c] = c

	def _nullPrompt(self):
		"""Returns value to use when answer to prompt is null string"""
		# most parameters just keep current default (even if None)
		return self.value

	def _optionalPrompt(self, mode):
		"""Interactively prompt for parameter if necessary
		
		Prompt for value if
		(1) mode is hidden but value is undefined or bad, or
		(2) mode is query and value was not set on command line
		Never prompt for "u" mode parameters, which are local variables.
		"""
		if (self.mode == "h") or (self.mode == "a" and mode == "h"):
			# hidden parameter
			if not self.isLegal():
				self.getPrompt()
		elif self.mode == "u":
			# "u" is a special mode used for local variables in CL scripts
			# They should never prompt under any circumstances
			if not self.isLegal():
				raise ValueError(
						"Attempt to access undefined local variable `%s'" %
						self.name)
		else:
			# query parameter
			if self.isCmdline()==0:
				self.getPrompt()

	def _getPFilename(self,native,prompt):
		"""Get p_filename field for this parameter
		
		Same as get for non-list params
		"""
		return self.get(native=native,prompt=prompt)

	def _getPType(self):
		"""Get underlying datatype for this parameter
		
		Just self.type for normal params
		"""
		return self.type

	def _getField(self, field, native=0, prompt=1):
		"""Get a parameter field value"""
		try:
			# expand field name using minimum match
			field = _getFieldDict[field]
		except KeyError, e:
			# re-raise the exception with a bit more info
			raise SyntaxError("Cannot get field " + field +
				" for parameter " + self.name + "\n" + str(e))
		if field == "p_value":
			# return value of parameter
			# Note that IRAF returns the filename for list parameters
			# when p_value is used.  I consider this a bug, and it does
			# not appear to be used by any cl scripts or SPP programs
			# in either IRAF or STSDAS.  It is also in conflict with
			# the IRAF help documentation.  I am making p_value exactly
			# the same as just a simple CL parameter reference.
			return self.get(native=native,prompt=prompt)
		elif field == "p_name": return self.name
		elif field == "p_xtype": return self.type
		elif field == "p_type": return self._getPType()
		elif field == "p_mode": return self.mode
		elif field == "p_prompt": return self.prompt
		elif field == "p_default" or field == "p_filename":
			# these all appear to be equivalent -- they just return the
			# current PFilename of the parameter (which is the same as the value
			# for non-list parameters, and is the filename for list parameters)
			return self._getPFilename(native,prompt)
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
					schoice = map(self.toString, self.choice)
					return "|" + string.join(schoice,"|") + "|"
			else:
				if native:
					return self.min
				else:
					return self.toString(self.min)
		else:
			# XXX unimplemented fields:
			# p_length: maximum string length in bytes -- what to do with it?
			raise RuntimeError("Program bug in IrafPar._getField()\n" +
				"Requested field " + field + " for parameter " + self.name)

	def _setField(self, value, field, check=1):
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
			self.max = self._coerceOneValue(value)
		elif field == "p_minimum":
			if type(value) is types.StringType and '|' in value:
				self._setChoice(irafutils.stripQuotes(value))
			else:
				self.min = self._coerceOneValue(value)
		elif field == "p_mode":
			# not doing any type or value checking here -- setting mode is
			# rare, so assume that it is being done correctly
			self.mode = irafutils.stripQuotes(value)
		else:
			raise RuntimeError("Program bug in IrafPar._setField()" +
				"Requested field " + field + " for parameter " + self.name)

	def _coerceValue(self,value,strict=0):
		"""Coerce parameter to appropriate type
		
		Should accept None or null string.
		"""
		return self._coerceOneValue(value,strict)

	def _coerceOneValue(self,value,strict=0):
		"""Coerce a scalar parameter to the appropriate type
		
		Default implementation simply prevents direct use of base class.
		Should accept None or null string.
		"""
		raise RuntimeError("Bug: base class IrafPar cannot be used directly")

# -----------------------------------------------------
# IRAF array parameter base class
# -----------------------------------------------------

class IrafArrayPar(IrafPar):

	"""IRAF array parameter class"""

	def __init__(self,fields,filename,strict=0):
		orig_len = len(fields)
		if orig_len < 3:
			raise SyntaxError("At least 3 fields must be given")
		#
		# all the attributes that are going to get defined
		#
		self.__dict__.update(_IrafPar_attr_dict)
		self.filename = filename
		self.name   = fields[0]
		self.type   = fields[1]
		self.mode   = fields[2]
		self.value  = None
		self.min    = None
		self.max    = None
		self.choice = None
		self.prompt = None
		self.__dict__['dim'] = None
		#
		while len(fields) < 7: fields.append("")
		# for array parameter, get dimensions from normal values field
		# and get values from fields after prompt
		if fields[3] is None or fields[4] is None or fields[5] is None:
			raise ValueError("Fields 4-6 must be specified for array parameter")
		ndim = int(fields[3])
		if ndim != 1:
			raise SyntaxError("Cannot handle multi-dimensional array" +
				" for parameter " + self.name)
		self.dim = int(fields[4])
		while len(fields) < 9+self.dim: fields.append(None)
		if len(fields) > 9+self.dim:
			raise SyntaxError("Too many values for array" +
				" for parameter " + self.name)
		#
		self.value = self._coerceValue(fields[9:9+self.dim],strict)
		if fields[6] is not None and '|' in fields[6]:
			self._setChoice(string.strip(fields[6]),strict)
			if fields[7] is not None:
				if orig_len < 9:
					warning("Max value illegal when choice list given" +
							" for parameter " + self.name +
							" (probably missing comma)",
							strict)
					# try to recover by assuming max string is prompt
					#XXX risky -- all init values might be off by one
					fields[8] = fields[7]
					fields[7] = None
				else:
					warning("Max value illegal when choice list given" +
						" for parameter " + self.name, strict)
		else:
			self.min = self._coerceOneValue(fields[6],strict)
			self.max = self._coerceOneValue(fields[7],strict)
		if fields[8] is not None:
			self.prompt = irafutils.removeEscapes(
							irafutils.stripQuotes(fields[8]))
		else:
			self.prompt = ''
		if self.min not in [None, INDEF] and \
		   self.max not in [None, INDEF] and self.max < self.min:
			warning("Maximum " + str(self.max) + " is less than minimum " + \
				str(self.min) + " for parameter " + self.name,
				strict)
			self.min, self.max = self.max, self.min
		#
		# check attributes to make sure they are appropriate for
		# this parameter type (e.g. some do not allow choice list
		# or min/max)
		#
		self._checkAttribs(strict)
		#
		# check parameter value to see if it is correct
		#
		try:
			self.checkValue(self.value,strict)
		except ValueError, e:
			warning("Illegal initial value for parameter\n" + str(e),
				strict, exception=ValueError)
			# Set illegal values to None, just like IRAF
			self.value = None

	#--------------------------------------------
	# public methods
	#--------------------------------------------

	def save(self, dolist=0):
		"""Return .par format string for this parameter
		
		If dolist is set, returns fields as a list of strings.  Default
		is to return a single string appropriate for writing to a file.
		"""
		quoted = not dolist
		fields = (9+self.dim)*[""]
		fields[0] = self.name
		fields[1] = self.type
		fields[2] = self.mode
		fields[3] = '1'
		fields[4] = str(self.dim)
		fields[5] = '1'
		if self.choice is not None:
			schoice = map(self.toString, self.choice)
			schoice.insert(0,'')
			schoice.append('')
			fields[6] = repr(string.join(schoice,'|'))
		elif self.min not in [None,INDEF]:
			fields[6] = self.toString(self.min,quoted=quoted)
		# insert an escaped line break before min field
		if quoted: fields[6] = '\\\n' + fields[6]
		if self.max not in [None,INDEF]:
			fields[7] = self.toString(self.max,quoted=quoted)
		if self.prompt:
			if quoted:
				sprompt = repr(self.prompt)
			else:
				sprompt = self.prompt
			# prompt can have embedded newlines (which are printed)
			sprompt = string.replace(sprompt, r'\012', '\n')
			sprompt = string.replace(sprompt, r'\n', '\n')
			fields[8] = sprompt
		for i in range(self.dim):
			fields[9+i] = self.toString(self.value[i],quoted=quoted)
		# insert an escaped line break before value fields
		if dolist:
			return fields
		else:
			fields[9] = '\\\n' + fields[9]
			return string.join(fields, ',')

	def dpar(self):
		"""Return dpar-style executable assignment for parameter"""
		sval = map(self.toString, self.value, self.dim*[1])
		for i in self.dim:
			if sval[i] == "": sval[i] = "None"
		s = "%s = [%s]" % (self.name, string.join(sval, ', '))
		return s

	def get(self, field=None, index=None, lpar=0, prompt=1, native=0, mode="h"):
		"""Return value of this parameter as a string (or in native format
		if native is non-zero.)"""

		if field: return self._getField(field,native=native,prompt=prompt)

		# may prompt for value if prompt flag is set
		#XXX should change _optionalPrompt so we prompt for each element of
		#XXX the array separately?  I think array parameters are
		#XXX not useful as non-hidden params.

		if prompt: self._optionalPrompt(mode)

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

	def set(self, value, field=None, index=None, check=1):
		"""Set value of this parameter from a string or other value.
		Field is optional parameter field (p_prompt, p_minimum, etc.)
		Index is optional array index (zero-based).  Set check=0 to
		assign the value without checking to see if it is within
		the min-max range or in the choice list."""
		if index is not None:
			try:
				value = self._coerceOneValue(value)
				if check:
					self.value[index] = self.checkOneValue(value)
				else:
					self.value[index] = value
				return
			except IndexError:
				raise SyntaxError("Illegal index [" + `index` +
					"] for array parameter " + self.name)
		if field:
			self._setField(value,field,check=check)
		else:
			if check:
				self.value = self.checkValue(value)
			else:
				self.value = self._coerceValue(value)
			self.setChanged()

	def checkValue(self,value,strict=0):
		"""Check and convert a parameter value.

		Raises an exception if the value is not permitted for this
		parameter.  Otherwise returns the value (converted to the
		right type.)
		"""
		v = self._coerceValue(value,strict)
		for i in xrange(self.dim): self.checkOneValue(v[i],strict=strict)
		return v

	#--------------------------------------------
	# special methods
	#--------------------------------------------

	# array parameters can be subscripted
	# note subscripts start at zero, unlike CL subscripts
	# that start at one

	def __getitem__(self, index):
		return self.get(index=index,native=1)

	def __setitem__(self, index, value):
		self.set(value, index=index)

	def __str__(self):
		"""Return readable description of parameter"""
		s = "<" + self.__class__.__name__ + " " + self.name + " " + \
			self.type + "[" + str(self.dim) + "]"
		s = s + " " + self.mode + " " + `self.value`
		if self.choice is not None:
			schoice = map(str, self.choice)
			s = s + " |" + string.join(schoice,"|") + "|"
		else:
			s = s + " " + `self.min` + " " + `self.max`
		s = s + ' "' + self.prompt + '">'
		return s

	#--------------------------------------------
	# private methods
	#--------------------------------------------

	def _getPType(self):
		"""Get underlying datatype for this parameter (strip off 'a' array params)"""
		return self.type[1:]

	def _coerceValue(self,value,strict=0):
		"""Coerce parameter to appropriate type
		
		Should accept None or null string.  Must be an array.
		"""
		if (type(value) not in [types.ListType,types.TupleType]) or \
				len(value) != self.dim:
			raise ValueError("Value must be a " + `self.dim` +
				"-element array for " + self.name)
		v = self.dim*[0]
		for i in xrange(self.dim):
			v[i] = self._coerceOneValue(value[i],strict)
		return v

# -----------------------------------------------------
# IRAF string parameter mixin class
# -----------------------------------------------------

class _StringMixin:

	"""IRAF string parameter mixin class"""

	#--------------------------------------------
	# public methods
	#--------------------------------------------

	def toString(self, value, quoted=0):
		"""Convert a single (non-array) value of the appropriate type for
		this parameter to a string"""
		if value is None:
			return ""
		elif quoted:
			return `value`
		else:
			return value

	# slightly modified checkOneValue allows minimum match for
	# choice strings and permits null string as value
	def checkOneValue(self,v,strict=0):
		if v is None or v[:1] == ")":
			return v
		elif self.choice is not None:
			try:
				v = self.choiceDict[v]
			except minmatch.AmbiguousKeyError, e:
				raise ValueError("Ambiguous value '" + str(v) +
					"' from choice list for " + self.name +
					"\n" + str(e))
			except KeyError, e:
				raise ValueError("Value '" + str(v) +
					"' is not in choice list for " + self.name +
					"\nChoices are " + string.join(self.choice,"|"))
		elif (self.min is not None and v<self.min):
			raise ValueError("Value `%s' for %s is less than minimum %s" %
				(str(v), self.name, str(self.min)))
		elif (self.max is not None and v>self.max):
			raise ValueError("Value `%s' for %s is greater than maximum %s" %
				(str(v), self.name, str(self.max)))
		return v

	#--------------------------------------------
	# private methods
	#--------------------------------------------

	def _checkAttribs(self, strict):
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

	def _setChoiceDict(self):
		"""Create min-match dictionary for choice list"""
		# value is full name of choice parameter
		self.choiceDict = minmatch.MinMatchDict()
		for c in self.choice: self.choiceDict.add(c, c)

	def _nullPrompt(self):
		"""Returns value to use when answer to prompt is null string"""
		# for string, null string is a legal value
		# keep current default unless it is None
		if self.value is None:
			return ""
		else:
			return self.value

	def _coerceOneValue(self,value,strict=0):
		if value is None:
			return value 
		elif type(value) is types.StringType:
			# strip double quotes and remove escapes before quotes
			return irafutils.removeEscapes(irafutils.stripQuotes(value))
		else:
			return str(value)

# -----------------------------------------------------
# IRAF string parameter class
# -----------------------------------------------------

class IrafParS(_StringMixin, IrafPar):

	"""IRAF string parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF string array parameter class
# -----------------------------------------------------

class IrafParAS(_StringMixin,IrafArrayPar):

	"""IRAF string array parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafArrayPar.__init__(self,fields,filename,strict)

# -----------------------------------------------------
# IRAF pset parameter class
# -----------------------------------------------------

class IrafParPset(IrafParS):

	"""IRAF pset parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParS.__init__(self,fields,filename,strict)
		# omitted list parameters default to null string
		if self.value is None: self.value = ""

	def get(self, field=None, index=None, lpar=0, prompt=1, native=0, mode="h"):
		"""Return pset value (IrafTask object)"""
		if index:
			raise SyntaxError("Parameter " + self.name +
				" is pset, cannot use index")
		if field: return self._getField(field)
		if lpar: return str(self.value)

		# assume there are no query or indirection pset parameters

		# if parameter value has .par extension, it is a file name
		f = string.split(self.value,'\.')
		if len(f) <= 1 or f[-1] != 'par':
			# must be a task name
			return iraf.getTask(self.value or self.name)
		else:
			raise ValueError("Pset parameter `%s' is a .par file -- "
				" Pyraf cannot handle this yet" % self.name)

# -----------------------------------------------------
# IRAF list parameter base class
# -----------------------------------------------------

class IrafParL(_StringMixin, IrafPar):

	"""IRAF list parameter base class"""

	def __init__(self,fields,filename,strict=0):
		IrafPar.__init__(self,fields,filename,strict)
		# filehandle for input file
		self.__dict__['fh'] = None
		# lines used to store input when not reading from a tty
		self.__dict__['lines'] = None
		# flag inidicating error message has been printed if file does not exist
		# message only gets printed once for each file
		self.__dict__['errMsg'] = 0
		# omitted list parameters default to null string
		if self.value is None: self.value = ""

	#--------------------------------------------
	# public methods
	#--------------------------------------------

	def set(self, value, field=None, index=None, check=1):
		"""Set value of this parameter from a string or other value.
		Field is optional parameter field (p_prompt, p_minimum, etc.)
		Index is optional array index (zero-based).  Set check=0 to
		assign the value without checking to see if it is within
		the min-max range or in the choice list."""

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if field:
			self._setField(value,field,check=check)
		else:
			if check:
				self.value = self.checkValue(value)
			else:
				self.value = self._coerceValue(value)
			self.setChanged()
			# close file if it is open
			if self.fh:
				try:
					self.fh.close()
				except IOError:
					pass
				self.fh = None
				self.lines = None
			self.errMsg = 0

	def get(self, field=None, index=None, lpar=0, prompt=1, native=0, mode="h"):
		"""Return value of this parameter as a string (or in native format
		if native is non-zero.)"""

		if field: return self._getField(field,native=native,prompt=prompt)
		if lpar:
			if self.value is None and native == 0:
				return ""
			else:
				return self.value

		# assume there are no query or indirection list parameters

		if index is not None:
			raise SyntaxError("Parameter "+self.name+" is not an array")

		if self.value:
			# non-null value means we're reading from a file
			try:
				if not self.fh:
					self.fh = open(iraf.Expand(self.value), "r")
					if self.fh.isatty():
						self.lines = None
					else:
						# read lines in a block
						# reverse to make pop more convenient & faster
						self.lines = self.fh.readlines()
						self.lines.reverse()
				if self.lines is None:
					value = self.fh.readline()
				elif self.lines:
					value = self.lines.pop()
				else:
					value = ''
				if not value:
					# EOF -- raise exception
					raise EOFError("EOF from list parameter `%s'" % self.name)
				if value[-1:] == "\n": value = value[:-1]
			except IOError, e:
				if not self.errMsg:
					warning("Unable to read values for list parameter `%s' "
						"from file `%s'\n%s" %
						(self.name, self.value,str(e)), level=-1)
					# only print message one time
					self.errMsg = 1
				# fall back on default behavior if file is not readable
				value = self._getNextValue()
		else:
			# if self.value is null, use the special _getNextValue method
			# (which should always return a string)
			value = self._getNextValue()
		if native:
			return self._coerceValue(value)
		else:
			return value

	#--------------------------------------------
	# private methods
	#--------------------------------------------

	# Use _getNextValue() method to implement a particular type

	def _getNextValue(self):
		"""Return a string with next value"""
		raise RuntimeError("Bug: base class IrafParL cannot be used directly")

	def _getPFilename(self,native,prompt):
		"""Get p_filename field for this parameter (returns filename)"""
		#XXX is this OK? should we check for self.value==None?
		return self.value

	def _getPType(self):
		"""Get underlying datatype for this parameter
		
		Strip off '*' from list params
		"""
		return self.type[1:]

# -----------------------------------------------------
# IRAF string list parameter class
# -----------------------------------------------------

class IrafParLS(IrafParL):

	"""IRAF string list parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def _getNextValue(self):
		"""Return next string value"""
		# save current values (in case this got called
		# because filename was in error)
		saveVal = self.value
		saveErr = self.errMsg
		try:
			# get rid of default value in prompt
			self.value = None
			self.getPrompt()
			retval = self.value
			return retval
		finally:
			# restore original values
			self.value = saveVal
			self.errMsg = saveErr

# -----------------------------------------------------
# IRAF gcur (graphics cursor) parameter class
# -----------------------------------------------------

class IrafParGCur(IrafParL):

	"""IRAF graphics cursor parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def _getNextValue(self):
		"""Return next graphics cursor value"""
		return irafgcur.gcur()

# -----------------------------------------------------
# IRAF imcur (image display cursor) parameter class
# -----------------------------------------------------

class IrafParImCur(IrafParL):

	"""IRAF image display cursor parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def _getNextValue(self):
		"""Return next image display cursor value"""
		return irafimcur.imcur()

# -----------------------------------------------------
# IRAF ukey (user typed key) parameter class
# -----------------------------------------------------

class IrafParUKey(IrafParL):

	"""IRAF user typed key parameter class"""

	def __init__(self,fields,filename,strict=0):
		IrafParL.__init__(self,fields,filename,strict)

	def _getNextValue(self):
		"""Return next typed character"""
		return irafukey.ukey()

# -----------------------------------------------------
# IRAF boolean parameter mixin class
# -----------------------------------------------------

class _BooleanMixin:

	"""IRAF boolean parameter mixin class"""

	#--------------------------------------------
	# public methods
	#--------------------------------------------

	def toString(self, value, quoted=0):
		if value in [None, INDEF]:
			return ""
		elif type(value) is types.StringType:
			# presumably an indirection value ')task.name'
			if quoted:
				return `value`
			else:
				return value
		else:
			# must be internal yes, no value
			return str(value)

	#--------------------------------------------
	# private methods
	#--------------------------------------------

	def _checkAttribs(self, strict):
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

	# accepts special yes, no objects, integer values 0,1 or
	# string 'yes','no' and variants
	# internal value is yes, no, None/INDEF, or indirection string
	def _coerceOneValue(self,value,strict=0):
		if value in [None,INDEF]:
			return value
		elif value == "":
			return None
		elif value==yes:
			# this handles 1, 1.0, yes, "yes", "YES", "y", "Y"
			return yes
		elif value==no:
			# this handles 0, 0.0, no, "no", "NO", "n", "N"
			return no
		if type(value) is types.StringType:
			v2 = irafutils.stripQuotes(string.strip(value))
			if v2 == "" or v2 == "INDEF":
				return INDEF
			elif v2[0:1] == ")":
				# assume this is indirection -- just save it as a string
				return v2
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

	#--------------------------------------------
	# public methods
	#--------------------------------------------

	def toString(self, value, quoted=0):
		if value is None:
			return ""
		else:
			return str(value)

	#--------------------------------------------
	# private methods
	#--------------------------------------------

	# coerce value to integer
	def _coerceOneValue(self,value,strict=0):
		tval = type(value)
		if value in [None, INDEF] or tval is types.IntType:
			return value
		elif value == "":
			return None
		elif tval is types.FloatType:
			# try converting to integer
			try:
				ival = int(value)
				if (ival == value): return ival
			except (ValueError, OverflowError):
				pass
		elif tval is types.StringType:
			s2 = irafutils.stripQuotes(string.strip(value))
			if s2 == "INDEF" or \
			  ((not strict) and (string.upper(s2) == "INDEF")):
				return INDEF
			elif s2[0:1] == ")":
				# assume this is indirection -- just save it as a string
				return s2
			elif s2[-1:] == "x":
				# hexadecimal
				return string.atoi(s2[:-1],16)
			elif (not strict) and ("." in s2):
				# try interpreting as a float and converting to integer
				try:
					fval = float(s2)
					ival = int(fval)
					if ival == fval: return ival
				except (ValueError, OverflowError):
					pass
			else:
				try:
					return int(s2)
				except ValueError:
					pass
		else:
			# maybe it has an int method
			try:
				return int(value)
			except ValueError:
				pass
		raise ValueError("Illegal integer value %s for parameter %s" % 
			(`value`, self.name))


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

	#--------------------------------------------
	# public methods
	#--------------------------------------------

	def toString(self, value, quoted=0):
		if value is None:
			return ""
		else:
			return str(value)

	#--------------------------------------------
	# private methods
	#--------------------------------------------

	def _checkAttribs(self, strict):
		"""Check initial attributes to make sure they are legal"""
		if self.choice:
			warning("Choice values not allowed for real-type parameter " +
				self.name, strict)
			self.choice = None

	# coerce value to real
	def _coerceOneValue(self,value,strict=0):
		tval = type(value)
		if value in [None, INDEF] or tval is types.FloatType:
			return value
		elif value == "":
			return None
		elif tval in [types.LongType,types.IntType]:
			return float(value)
		elif tval is types.StringType:
			s2 = irafutils.stripQuotes(string.strip(value))
			if s2 == "INDEF" or \
			  ((not strict) and (string.upper(s2) == "INDEF")):
				return INDEF
			elif s2[0:1] == ")":
				# assume this is indirection -- just save it as a string
				return s2
			# allow +dd:mm:ss.s sexagesimal format for floats
			fvalue = 0.0
			vscale = 1.0
			vsign = 1
			i1 = 0
			mm = _re_colon.search(s2)
			if mm is not None:
				if s2[0:1] == "-":
					i1 = 1
					vsign = -1
				elif s2[0:1] == "+":
					i1 = 1
				while mm is not None:
					i2 = mm.start()
					fvalue = fvalue + int(s2[i1:i2])/vscale
					i1 = i2+1
					vscale = vscale*60.0
					mm = _re_colon.search(s2,i1)
			# special handling for d exponential notation
			mm = _re_d.search(s2,i1)
			try:
				if mm is None:
					return vsign*(fvalue + float(s2[i1:])/vscale)
				else:
					return vsign*(fvalue + \
						float(s2[i1:mm.start()]+"E"+s2[mm.end():])/vscale)
			except ValueError:
				pass
		else:
			# maybe it has a float method
			try:
				return float(value)
			except ValueError:
				pass
		raise ValueError("Illegal float value %s for parameter %s" % 
			(`value`, self.name))

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

# Note that all methods are mixed case and all attributes are private
# (start with __) to avoid conflicts with parameter names


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
			p = makeIrafPar("al", name="mode", datatype="string", mode="h")
			self.__pars.append(p)
			self.__pardict.add(p.name, p)
		if not self.__pardict.has_exact_key("$nargs"):
			p = makeIrafPar(0, name="$nargs", datatype="int", mode="h")
			self.__pars.append(p)
			self.__pardict.add(p.name, p)

		# save the list of pset parameters
		# Defer adding the parameters until later because saved parameter
		# sets may not be defined yet when restoring from save file.
		self.__psetlist = psetlist

	def __addPsetParams(self):
		"""Merge pset parameters into the parameter lists"""
		# return immediately if they have already been added
		if self.__psetlist is None: return
		# Work from the pset's pardict because then we get
		# parameters from nested psets too
		for p in self.__psetlist:
			# silently ignore parameters from psets that already are defined
			psetdict = p.get().getParDict()
			for pname in psetdict.keys():
				if not self.__pardict.has_exact_key(pname):
					self.__pardict.add(pname, psetdict[pname])
		self.__psetlist = None

	def addParam(self, p):
		"""Add a parameter to the list"""
		if not isinstance(p, IrafPar):
			t = type(p)
			if t is types.InstanceType:
				tname = p.__class__.__name__
			else:
				tname = t.__name__
			raise TypeError("Parameter must be of type IrafPar (value is %s)" %
				tname)
		elif self.__pardict.has_exact_key(p.name):
			if p.name in ["$nargs", "mode"]:
				# allow substitution of these default parameters
				self.__pardict[p.name] = p
				for i in range(len(self.__pars)):
					j = -i-1
					if self.__pars[j].name == p.name:
						self.__pars[j] = p
						return
				else:
					raise RuntimeError("Bug: parameter `%s' is in dictionary "
						"__pardict but not in list __pars??" % p.name)
			raise ValueError("Parameter named `%s' is already defined" % p.name)
		# add it just before the mode and $nargs parameters (if present)
		j = -1
		for i in range(len(self.__pars)):
			j = -i-1
			if self.__pars[j].name not in ["$nargs", "mode"]: break
		else:
			j = -len(self.__pars)-1
		self.__pars.insert(len(self.__pars)+j+1, p)
		self.__pardict.add(p.name, p)
		if isinstance(p, IrafParPset):
			# parameters from this pset will be added too
			if self.__psetlist is None:
				# add immediately
				self.__psetlist = [p]
				self.__addPsetParams()
			else:
				# just add to the pset list
				self.__psetlist.append(p)

	def isConsistent(self, other):
		"""Compare two IrafParLists for consistency
		
		Returns true if lists are consistent, false if inconsistent.
		Only checks immutable param characteristics (name & type).
		Allows hidden parameters to be in any order, but requires
		non-hidden parameters to be in identical order.
		"""
		if not isinstance(other, self.__class__):
			if Verbose>0:
				print 'Comparison list is not a %s' % self.__class__.__name__
			return 0
		if len(self) != len(other): return 0
		# compare dictionaries of parameters
		return self._getConsistentList() == other._getConsistentList()

	def _getConsistentList(self):
		"""Return simplified parameter dictionary used for consistency check
		
		Dictionary is keyed by param name, with value of type and
		(for non-hidden parameters) sequence number.
		"""
		dpar = {}
		j = 0
		for par in self.__pars:
			if par.mode == "h":
				dpar[par.name] = par.type
			else:
				dpar[par.name] = (par.type, j)
				j = j+1
		return dpar

	def clearFlags(self):
		"""Clear all status flags for all parameters"""
		for p in self.__pars: p.setFlags(0)

	# parameters are accessible as attributes

	def __getattr__(self,name):
		if name[:1] == '_':
			raise AttributeError(name)
		try:
			return self.getValue(name,native=1)
		except SyntaxError, e:
			raise AttributeError(str(e))

	def __setattr__(self,name,value):
		# hidden Python parameters go into the standard dictionary
		# (hope there are none of these in IRAF tasks)
		if name[:1] == '_':
			self.__dict__[name] = value
		else:
			self.setValue(name,value)

	def __len__(self): return len(self.__pars)

	# public accessor functions for attributes

	def hasPar(self,param):
		"""Test existence of parameter named param"""
		if self.__psetlist: self.__addPsetParams()
		param = irafutils.untranslateName(param)
		return self.__pardict.has_key(param)

	def getFilename(self): return self.__filename
	def getParList(self): return self.__pars
	def getParDict(self):
		if self.__psetlist: self.__addPsetParams()
		return self.__pardict

	def getParObject(self,param):
		if self.__psetlist: self.__addPsetParams()
		try:
			param = irafutils.untranslateName(param)
			return self.__pardict[param]
		except KeyError, e:
			raise e.__class__("Error in parameter '" +
				param + "' for task " + self.__name + "\n" + str(e))

	def getAllMatches(self,param):
		"""Return list of all parameter names that may match param"""
		if param == "":
			return self.__pardict.keys()
		else:
			return self.__pardict.getallkeys(param, [])

	def getValue(self,param,native=0,prompt=1,mode="h"):
		"""Return value for task parameter 'param' (with min-match)
		
		If native is non-zero, returns native format for value.  Default is
		to return a string.
		If prompt is zero, does not prompt for parameter.  Default is to
		prompt for query parameters.
		"""
		par = self.getParObject(param)
		value = par.get(native=native, mode=mode, prompt=prompt)
		if type(value) is types.StringType and value[:1] == ")":
			# parameter indirection: ')task.param'
			try:
				task = iraf.getTask(self.__name)
				value = task.getParam(value[1:],native=native,mode="h")
			except KeyError:
				# if task is not known, use generic function to get param
				value = iraf.clParGet(value[1:],native=native,mode="h")
		return value

	def setValue(self,param,value):
		"""Set task parameter 'param' to value (with minimum-matching)"""
		self.getParObject(param).set(value)

	def setParList(self,*args,**kw):
		"""Set value of multiple parameters from list"""
		# first undo translations that were applied to keyword names
		for key in kw.keys():
			okey = key
			key = irafutils.untranslateName(key)
			if okey != key:
				value = kw[okey]
				del kw[okey]
				kw[key] = value
		# then expand all keywords to their full names
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
		# clear changed flags and set cmdline flags for arguments
		self.clearFlags()
		for param in fullkw.keys():
			p = self.getParObject(param)
			p.set(fullkw[param])
			p.setFlags(_cmdlineFlag)

		# Number of arguments on command line, $nargs, is used by some IRAF
		# tasks (e.g. imheader).
		self.setValue('$nargs',len(args))

	def eParam(self):
		epar.epar(self.__name)

	def lParam(self,verbose=0):
		"""List the task parameters"""
		for i in xrange(len(self.__pars)):
			p = self.__pars[i]
			if Verbose>0 or p.name != '$nargs':
				print p.pretty(verbose=verbose or Verbose>0)

	def dParam(self, taskname=""):
		"""Dump the task parameters in executable form"""
		if taskname and taskname[-1:] != ".": taskname = taskname + "."
		for i in xrange(len(self.__pars)):
			p = self.__pars[i]
			if p.name != '$nargs':
				print "%s%s" % (taskname,p.dpar())

	def saveList(self, filename):
		"""Write .par file data to filename (string or filehandle)"""
		if hasattr(filename,'write'):
			fh = filename
		else:
			fh = open(filename,'w')
		nsave = len(self.__pars)
		for par in self.__pars:
			if par.name == '$nargs':
				nsave = nsave-1
			else:
				fh.write(par.save()+'\n')
		if fh != filename:
			fh.close()
			return "%d parameters written to %s" % (nsave, filename)
		elif hasattr(fh, 'name'):
			return "%d parameters written to %s" % (nsave, fh.name)
		else:
			return "%d parameters written" % (nsave,)

	def __getinitargs__(self):
		"""Return parameters for __init__ call in pickle"""
		return (self.__name, self.__filename, self.__pars)

	def __getstate__(self):
		"""Return additional state for pickle"""
		# nothing beyond init
		return None

	def __setstate__(self, state):
		"""Restore additional state from pickle"""
		pass

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

# First define regular expressions used in parsing

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
double = whitespace + r'"(?P<double>[^"\\]*(?:\\.[^"\\]*)*)"' + \
	whitespace + r'(?P<djunk>[^,]*)' + optcomma
single = whitespace + r"'(?P<single>[^'\\]*(?:\\.[^'\\]*)*)'" + \
	whitespace + r'(?P<sjunk>[^,]*)' + optcomma

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
_re_field = re.compile(field,re.DOTALL)

# Pattern that matches trailing backslashes at end of line
_re_bstrail = re.compile(r'\\*$')

# clean up unnecessary global variables
del whitespace, field, comma, optcomma, noncommajunk, double, single

def _readpar(filename,strict=0):
	"""Read IRAF .par file and return list of parameters"""

	global _re_field, _re_bstrail

	param_dict = {}
	param_list = []
	fh = open(os.path.expanduser(filename),'r')
	lines = fh.readlines()
	fh.close()
	# reverse order of lines so we can use pop method
	lines.reverse()
	while lines:
		# strip whitespace (including newline) off both ends
		line = string.strip(lines.pop())
		# skip comments and blank lines
		# "..." is weird line that occurs in cl.par
		if len(line)>0 and line[0] != '#' and line != "...":
			# Append next line if this line ends with continuation character.
			while line[-1:] == "\\":
				# odd number of trailing backslashes means this is continuation
				if (len(_re_bstrail.search(line).group()) % 2 == 1):
					try:
						line = line[:-1] + string.rstrip(lines.pop())
					except IndexError:
						raise SyntaxError(filename + ": Continuation on last line\n" +
								line)
				else:
					break
			flist = []
			i1 = 0
			while len(line) > i1:
				mm = _re_field.match(line,i1)
				if mm is None:
					# Failure occurs only for unmatched leading quote.
					# Append more lines to get quotes to match.  (Probably
					# want to restrict this behavior to only the prompt
					# field.)
					while mm is None:
						try:
							nline = lines.pop()
						except IndexError:
							# serious error, run-on quote consumed entire file
							sline = string.split(line,'\n')
							raise SyntaxError(filename + ": Unmatched quote\n" +
								sline[0])
						line = line + '\n' + string.rstrip(nline)
						mm = _re_field.match(line,i1)
				if mm.group('comma') is not None:
					g = mm.group('comma')
					# completely omitted field (,,)
					if g == "":
						g = None
					# check for trailing quote in unquoted string
					elif g[-1:] == '"' or g[-1:] == "'":
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
			except KeyboardInterrupt, e:
				raise e
			except Exception, exc:
				#XXX Shouldn't catch all exceptions here -- this could
				#XXX screw things up
				raise SyntaxError(filename + "\n" + line + "\n" + \
					str(flist) + "\n" + str(exc))
			if param_dict.has_key(par.name):
				warning(filename + "\n" + line + "\n" +
						"Duplicate parameter " + par.name,
						strict)
			else:
				param_dict[par.name] = par
				param_list.append(par)
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
