"""cl2py.py: Translate IRAF CL program to Python

$Id$

R. White, 1999 December 20
"""

import string, cStringIO, os, sys, types

from generic import GenericASTTraversal
from clast import AST
from cltoken import Token
import clscan, clparse

import pyraf, irafpar, minmatch, iraftask, irafutils
import iraffunctions

# The parser object can be constructed once and used many times.
# The other classes have instance variables (e.g. lineno in CLScanner),
# so using a single instance could screw up if several threads are trying
# to use the same object.
#
# I handled this in the CLScanner class by creating cached versions
# of the various scanners that are stateless.

_parser = clparse._parser

def cl2py(filename=None, str=None, parlist=None, parfile="", mode="proc",
	local_vars_dict=None, local_vars_list=None):

	"""Read CL program from file and return pycode object with Python equivalent
	
	filename: Name of the CL source file or a filehandle from which the
		source code can be read.
	str: String containing the source code.  Either filename or str must be
		specified; if both are specified, only filename is used
	parlist: IrafParList object with list of parameters (which may have already
		been defined from a .par file)
	parfile: Name of the .par file used to define parlist.  parlist may be
		defined even if parfile is null, but a null parfile is interpreted
		to mean that the parameter definitions in the CL script should
		override the parlist.  If parfile is not null, it is an error if
		the CL script parameters conflict with the parlist.
	mode: Mode of translation.  Default "proc" creates a procedure script
		(which defines a Python function.)  Normally CL scripts will be
		translated using this default.  If mode is "single" then the
		necessary environment is assumed to be set and the Python
		code simply gets executed directly.  This is used in the
		CL compatibility mode and other places where a single line of
		CL must be executed.
		Mode also determines whether parameter sets are saved in calls
		to CL tasks.  In "single" mode parameters do get saved; in
		"proc" mode they do not get saved.  This is intended to be
		consistent with the behavior of the IRAF CL, where parameter
		changes in scripts are not preserved.
	local_vars_dict, local_vars_list: Initial definitions of local variables.
		May be modified by declarations in the CL code.  This is used only for
		"single" mode to allow definitions to persist across statements.
	"""

	global _parser, codeCache

	if mode not in ["proc", "single"]:
		raise ValueError("Mode = `%s', must be `proc' or `single'" % (mode,))

	if filename is not None:

		if type(filename) == types.StringType:
			efilename = os.path.expanduser(filename)
			index, attributes, pycode = codeCache.get(efilename,mode=mode)
			if pycode is not None:
				if iraffunctions.Verbose>1:
					print index,"found in CL script cache"
				return pycode
			fh = open(efilename)
			clInput = fh.read()
			fh.close()
		elif hasattr(filename,'read'):
			clInput = filename.read()
			index, attributes, pycode = codeCache.get(filename,mode=mode)
			if pycode is not None:
				if iraffunctions.Verbose>1:
					print index,"found in CL script cache"
				return pycode
			if hasattr(filename,'name'):
				efilename = filename.name
			else:
				efilename = 'cmdline.cl'
		else:
			raise TypeError('filename must be a string or a filehandle')
	elif str is not None:
		if type(str) != types.StringType:
			raise TypeError('str must be a string')
		clInput = str
		efilename = 'string_proc'
		# don't cache scripts from strings
		index = None
		attributes = None
	else:
		raise ValueError('Either filename or str must be specified')

	# tokenize and parse to create the abstract syntax tree
	scanner = clscan.CLScanner()
	tokens = scanner.tokenize(clInput)
	tree = _parser.parse(tokens)
	# add filename to tree root
	tree.filename = efilename

	# first pass -- get variables

	vars = VarList(tree,mode,local_vars_list,local_vars_dict)

	# check variable list for consistency with the given parlist
	# this may change the vars list

	_checkVars(vars, parlist, parfile)

	# second pass -- check all expression types
	# type info is added to tree

	TypeCheck(tree, vars, efilename)

	# third pass -- generate python code

	tree2python = Tree2Python(tree, vars, efilename)

	# just keep the relevant fields of Tree2Python output
	# attach tokens to the code object too

	pycode = Pycode(tree2python,attributes)

	# add to cache
	if index is not None: codeCache.add(index, pycode)
	return pycode

def checkCache(filename, pycode):

	"""Returns true if pycode attributes are up-to-date"""

	global codeCache
	index, curattr = codeCache.getIndex(filename)
	return (pycode.attributes == curattr)


class Container:

	"""Simple container class (no methods) for holding picklable objects"""

	pass


def Pycode(tree2python, attributes):

	"""Returns simple container instance with relevant fields"""

	rv = Container()
	rv.code = tree2python.code
	rv.attributes = attributes
	rv.vars = Container()
	rv.vars.filename        = tree2python.vars.filename
	rv.vars.local_vars_dict = tree2python.vars.local_vars_dict
	rv.vars.local_vars_list = tree2python.vars.local_vars_list
	rv.vars.parList         = tree2python.vars.parList
	rv.vars.proc_name       = tree2python.vars.proc_name
	rv.vars.has_proc_stmt   = tree2python.vars.has_proc_stmt
	return rv


def _checkVars(vars, parlist, parfile):
	"""Check variable list for consistency with the given parlist"""

	# if there is no parfile specified, the parlist was created by default
	# if parlist is None, the parfile was empty
	# in either case, just use the parameter list specified in the CL code

	if (not parfile) or (parlist is None): return

	# parfile and parlist are specified, so create a new
	# list of procedure variables from parlist

	# check for consistency with the CL code if there was a procedure stmt
	if vars.has_proc_stmt and not parlist.isConsistent(vars.parList):
		# note we continue even if parameter lists are inconsistent.
		# That agrees with IRAF's approach, in which the .par file
		# overrides the CL script in determining parameters...
		#XXX Maybe could improve this by allowing certain types of
		#XXX mismatches (e.g. additional parameters) but not others
		#XXX (name or type disagreements for the same parameters.)
		if iraffunctions.Verbose>0:
			sys.stdout.flush()
			sys.stderr.write("Parameters from CL code inconsistent "
				"with .par file for task %s\n" % vars.getProcName())
			sys.stderr.flush()

	# create copies of the list and dictionary
	plist = parlist.getParList()
	newlist = []
	newdict = {}
	for par in plist:
		newlist.append(par.name)
		newdict[par.name] = Variable(irafParObject=par)
	vars.proc_args_list = newlist
	vars.proc_args_dict = newdict
	# add mode, $nargs, other special parameters to all tasks
	vars.addSpecialArgs()
	# Check for local variables that conflict with parameters
	vars.checkLocalConflict()
	vars.parList = parlist

class CleanupASTTraversal(GenericASTTraversal):

	"""AST traversal class that can be garbage-collected"""
	def __init__(self, ast):
		GenericASTTraversal.__init__(self, ast)
		# print 'Created object of type',self.__class__.__name__

	#def cleanup(self):
	#	"""Delete all tables of circular method references"""
	#	# there don't seem to be any
	#	pass

	#def __del__(self):
	#	print "Deleting object of type", self.__class__.__name__


class ExtractProcInfo(CleanupASTTraversal):

	"""Extract name and args from procedure statement"""

	def __init__(self, ast):
		CleanupASTTraversal.__init__(self, ast)
		self.preorder()

	def n_proc_stmt(self, node):
		# get procedure name and list of argument names
		self.proc_name = node[1].attr
		self.proc_args_list = []
		if len(node[2]):
			self.preorder(node[2])
		self.prune()

	def n_IDENT(self, node):
		self.proc_args_list.append(irafutils.translateName(node.attr))

_longTypeName = {
			"s": "string",
			"f": "file",
			"struct": "struct",
			"i": "int",
			"b": "bool",
			"r": "real",
			"d": "double",
			"gcur": "gcur",
			"imcur": "imcur",
			"ukey": "ukey",
			"pset": "pset",
			}

class Variable:

	"""Container for properties of a variable"""

	def __init__(self, name=None, type=None, mode="h", array_size=None,
			init_value=None, list_flag=0, min=None, max=None,
			prompt=None, enum=None, irafParObject=None):
		if irafParObject is not None:
			# define the variable info from an IrafPar object
			ipo = irafParObject
			self.name = ipo.name
			if ipo.type[:1] == "*":
				self.type = _longTypeName[ipo.type[1:]]
				self.list_flag = 1
			else:
				self.type = _longTypeName[ipo.type]
				self.list_flag = 0
			if isinstance(ipo, irafpar.IrafArrayPar):
				self.array_size = ipo.dim
			else:
				self.array_size = None
			self.init_value = ipo.value
			self.options = minmatch.MinMatchDict({
							"mode":   ipo.mode,
							"min":    ipo.min,
							"max":    ipo.max,
							"prompt": ipo.prompt,
							"enum":   ipo.choice,
							"length": None, })
		else:
			# define from the parameters
			self.name = name
			self.type = type
			self.array_size = array_size
			self.list_flag = list_flag
			self.options = minmatch.MinMatchDict({
							"mode":   mode,
							"min":    min,
							"max":    max,
							"prompt": prompt,
							"enum":   enum,
							"length": None, })
			self.init_value = init_value

	def getName(self):
		"""Get name without translations"""
		return irafutils.untranslateName(self.name)

	def toPar(self, strict=0, filename=''):
		"""Convert this variable to an IrafPar object"""
		return irafpar.makeIrafPar(self.init_value,
				datatype=self.type,
				name=self.getName(),
				array_size=self.array_size,
				list_flag=self.list_flag,
				mode=self.options["mode"],
				min=self.options["min"],
				max=self.options["max"],
				enum=self.options["enum"],
				prompt=self.options["prompt"],
				strict=strict,
				filename=filename)

	def procLine(self):
		"""Return a string usable as parameter declaration with
		default value in the function definition statement"""

		name = irafutils.translateName(self.name)
		if self.array_size is None:
			if self.init_value is None:
				return name + "=None"
			else:
				return name + "=" + `self.init_value`
		else:
			# array
			arg = name + "=["
			arglist = []
			for iv in self.init_value:
				arglist.append(`iv`)
			return arg + string.join(arglist,",") + "]"

	def parDefLine(self, filename=None, strict=0):
		"""Return a list of string arguments for makeIrafPar"""

		name = irafutils.translateName(self.name)
		arglist = [name,
			"datatype=" + `self.type`,
			"name=" + `self.getName()` ]
		if self.array_size is not None:
			arglist.append("array_size=" + `self.array_size`)
		if self.list_flag:
			arglist.append("list_flag=" + `self.list_flag`)
		keylist = self.options.keys()
		keylist.sort()
		for key in keylist:
			option = self.options[key]
			if option is not None:
				arglist.append(key + "=" + `self.options[key]`)
		if filename: arglist.append("filename=" + `filename`)
		if strict: arglist.append("strict=" + `strict`)
		return arglist

	def __repr__(self):
		s = self.type + " "
		if self.list_flag: s = s + "*"
		s = s + self.name
		if self.init_value is not None:
			s = s + " = " + `self.init_value`
		optstring = "{"
		for key, value in self.options.items():
			if (value is not None) and (key != "mode" or value != "h"):
				# optstring = optstring + " " + key + "=" + str(value)
				optstring = optstring + " " + key + "=" + str(value)
		if len(optstring) > 1:
			s = s + " " + optstring + " }"
		return s


class ExtractDeclInfo(CleanupASTTraversal):

	"""Extract list of variable definitions from parameter block"""

	def __init__(self, ast, var_list, var_dict, filename):
		CleanupASTTraversal.__init__(self, ast)
		self.var_list = var_list
		n = len(var_list)
		self.var_dict = var_dict
		self.filename = filename
		self.preorder()

	def n_nonnull_stmt(self, node):
		# skip executable statements
		self.prune()

	def n_declaration_stmt(self, node):
		self.current_type = node[0].attr

	def n_decl_spec(self, node):
		var_name = node[1]
		name = irafutils.translateName(var_name[0].attr)
		if len(var_name) > 1:
			# array declaration
			array_size = int(var_name[2])
		else:
			# apparently not an array (but this may change later
			# if multiple initial values are found)
			array_size = None
		if self.var_dict.has_key(name):
			if self.var_dict[name]:
				errmsg = "Variable `%s' is multiply declared" % (name,)
				raise SyntaxError(errmsg)
			else:
				# existing but undefined entry comes from procedure line
				# set mode = "a" by default
				self.var_dict[name] = Variable(name, self.current_type,
								array_size = array_size, mode="a")
		else:
			self.var_list.append(name)
			self.var_dict[name] = Variable(name, self.current_type,
							array_size = array_size)
		self.current_var = self.var_dict[name]
		self.preorder(node[0])	# list flag
		self.preorder(node[2])	# initialization
		self.preorder(node[3])	# declaration options
		self.prune()

	def n_list_flag(self, node):
		if len(node) > 0:
			self.current_var.list_flag = 1
		self.prune()

	def n_decl_init_list(self, node):
		# begin list of initial values
		if self.current_var.init_value is not None:
			# oops, looks like this was already initialized
			errmsg = \
				"%s: Variable `%s' has more than one set of initial values" % \
				(self.filename, self.current_var.name,)
			raise SyntaxError(errmsg)
		self.current_var.init_value = []

	def n_decl_init_list_exit(self, node):
		# convert from list to scalar if not an array
		# also convert all the initial values from tokens to native form
		v = self.current_var
		ilist = v.init_value
		if len(ilist) == 1 and v.array_size is None:
			v.init_value = _convFunc(v, ilist[0])
		else:
			# it is an array, set size or pad initial values
			if v.array_size is None:
				v.array_size = len(ilist)
			elif v.array_size > len(ilist):
				for i in range(v.array_size-len(ilist)):
					v.init_value.append(None)
			elif v.array_size < len(ilist):
				errmsg = "Variable `%s' has too many initial values" % (v.name,)
				raise SyntaxError(errmsg)
			for i in range(len(v.init_value)):
				v.init_value[i] = _convFunc(v, v.init_value[i])

	def n_decl_init_value(self, node):
		# initial value is token with value
		vnode = node[0]
		if isinstance(vnode, Token):
			self.current_var.init_value.append(vnode)
		else:
			# have to create a new token for sign, number
			self.current_var.init_value.append(
				Token(type=vnode[1].type, attr=vnode[0].type+vnode[1].attr,
					lineno=vnode[0].lineno))
		self.prune()

	def n_decl_option(self, node):
		optname = node[0].attr
		vnode = node[2]
		if isinstance(vnode, Token):
			optvalue = vnode.get()
		else:
			# have to combine sign, number
			if vnode[0] == "-":
				optvalue = - vnode[1].get()
			else:
				optvalue = vnode[1].get()
		optdict = self.current_var.options
		if not optdict.has_key(optname):
			errmsg = "Unknown option `%s' for variable `%s'" % (optname, self.current_var.name)
			raise SyntaxError(errmsg)
		else:
			optdict[optname] = optvalue
		self.prune()


# special keyword arguments added to parameter list

_SpecialArgs = {
	'taskObj': None,
	}

class VarList(CleanupASTTraversal):

	"""Scan tree and get info on procedure, parameters, and local variables"""

	def __init__(self, ast, mode="proc", local_vars_list=None, local_vars_dict=None):
		CleanupASTTraversal.__init__(self, ast)
		self.mode = mode
		self.proc_name = ""
		self.proc_args_list = []
		self.proc_args_dict = {}
		self.has_proc_stmt = 0
		if local_vars_list is None:
			self.local_vars_list = []
			self.local_vars_count = 0
		else:
			self.local_vars_list = local_vars_list
			self.local_vars_count = len(local_vars_list)
		if local_vars_dict is None:
			self.local_vars_dict = {}
		else:
			self.local_vars_dict = local_vars_dict
		if hasattr(ast, 'filename'):
			self.filename = ast.filename
		else:
			self.filename = ''
		self.preorder()

		# If in "proc" mode, add default procedure name for
		# non-procedure scripts
		# (Need to do something like this so non-procedure scripts can
		# be compiled, but this may not be ideal solution.)
		if self.mode != "single" and not self.proc_name:
			if not self.filename:
				self.proc_name = 'proc'
			else:
				path, fname = os.path.split(self.filename)
				root, ext = os.path.splitext(fname)
				self.setProcName(root)

		# add mode, $nargs, other special parameters to all tasks
		self.addSpecialArgs()

		# Check for local variables that conflict with parameters
		self.checkLocalConflict()

		# convert procedure arguments to IrafParList
		p = []
		for var in self.proc_args_list:
			if not _SpecialArgs.has_key(var):
				p.append(self.proc_args_dict[var].toPar(filename=self.filename))
		self.parList = irafpar.IrafParList(self.getProcName(),
					filename=self.filename, parlist=p)

	def setProcName(self, proc_name):
		"""Set procedure name"""
		# Procedure name is stored in translated form ('PY' added
		# to Python keywords, etc.)
		self.proc_name = irafutils.translateName(proc_name)

	def getProcName(self):
		"""Get procedure name, undoing translations"""
		return irafutils.untranslateName(self.proc_name)

	def addSpecialArgs(self):
		"""Add mode, $nargs, other special parameters to all tasks"""

		if not self.proc_args_dict.has_key('mode'):
			self.proc_args_list.append('mode')
			self.proc_args_dict['mode'] = Variable('mode','string',
				init_value='al')

		# just delete $nargs and add it back if it is already present
		if self.proc_args_dict.has_key('$nargs'):
			self.proc_args_list.remove('$nargs')
			del self.proc_args_dict['$nargs']

		targ = irafutils.translateName('$nargs')
		if not self.proc_args_dict.has_key(targ):
			self.proc_args_list.append(targ)
			self.proc_args_dict[targ] = Variable(targ, 'int', init_value=0)

		for parg, ivalue in _SpecialArgs.items():
			if not self.proc_args_dict.has_key(parg):
				self.proc_args_list.append(parg)
				self.proc_args_dict[parg] = ivalue

	def checkLocalConflict(self):
		"""Check for local variables that conflict with parameters"""

		errlist = ["Error in procedure `%s'" % self.getProcName()]
		for v in self.local_vars_list:
			if self.proc_args_dict.has_key(v):
				errlist.append(
					"Local variable `%s' overrides parameter of same name" %
					(v,))
		if len(errlist) > 1:
			errmsg = string.join(errlist, "\n")
			raise SyntaxError(errmsg)

	def n_proc_stmt(self, node):
		self.has_proc_stmt = 1
		# get procedure name and list of argument names
		p = ExtractProcInfo(node)
		self.setProcName(p.proc_name)
		self.proc_args_list = p.proc_args_list
		for arg in self.proc_args_list:
			if self.proc_args_dict.has_key(arg):
				errmsg = "Argument `%s' repeated in procedure statement %s" % \
					(arg,self.getProcName())
				raise SyntaxError(errmsg)
			else:
				self.proc_args_dict[arg] = None
		self.prune()

	def n_param_declaration_block(self, node):
		# get list of parameter variables
		p = ExtractDeclInfo(node, self.proc_args_list, self.proc_args_dict,
			self.ast.filename)
		# check for undefined parameters declared in procedure stmt
		d = self.proc_args_dict
		for arg in d.keys():
			if not d[arg]:
				errmsg = "Procedure argument `%s' is not declared" % (arg,)
				raise SyntaxError(errmsg)
		self.prune()

	def n_statement_block(self, node):
		# declarations in executable section are local variables
		p = ExtractDeclInfo(node, self.local_vars_list, self.local_vars_dict,
			self.ast.filename)
		self.prune()

	def list(self):
		"""List variables"""
		print "Procedure arguments:"
		for var in self.proc_args_list:
			v =  self.proc_args_dict[var]
			if _SpecialArgs.has_key(var):
				print 'Special',var,'=',v
			else:
				print v
		print "Local variables:"
		for var in self.local_vars_list:
			print self.local_vars_dict[var]

	def getParList(self):
		"""Return procedure arguments as IrafParList"""
		return self.parList


# conversion between parameter types and data types

_typeDict = {
			'int':    'int',
			'real':   'float',
			'double': 'float',
			'bool':   'bool',
			'string': 'string',
			'char':   'string',
			'struct': 'string',
			'file':   'string',
			'gcur':   'string',
			'imcur':  'string',
			'ukey':   'string',
			'pset':   'indef',
			}

# nested dictionary mapping required data type (primary key) and
# expression type (secondary key) to the name of the function used to
# convert to the required type

_rfuncDict = {
  'int':   {'int':    None,
  			'float':  'int',
			'string': 'int',
			'bool':   None,
			'indef':  'int'},
  'float': {'int':    'float',
  			'float':  None,
			'string': 'float',
			'bool':   'float',
			'indef':  'float'},
  'string':{'int':    'str',
  			'float':  'str',
			'string': None,
			'bool':   'iraf.bool2str',
			'indef':  'str'},
  'bool':  {'int':    'iraf.boolean',
  			'float':  'iraf.boolean',
			'string': 'iraf.boolean',
			'bool':   None,
			'indef':  'iraf.boolean'},
  'indef': {'int':    None,
  			'float':  None,
			'string': None,
			'bool':   None,
			'indef':  None},
  }

def _funcName(requireType, exprType):
	return _rfuncDict[requireType][exprType]

# given two nodes with defined types in an arithmetic expression,
# set their required times and return the result type
# (using standard promotion rules)

_numberTypes = ['float', 'int']

def _arithType(node1, node2):
	if node1.exprType in _numberTypes:
		if node2.exprType not in _numberTypes:
			rv = node1.exprType
			node2.requireType = rv
		else:
			# both numbers -- don't change required types, but
			# determine result type
			if 'float' in [node1.exprType, node1.exprType]:
				rv = 'float'
			else:
				rv = node1.exprType
	else:
		if node2.exprType in _numberTypes:
			rv = node2.exprType
			node1.requireType = rv
		else:
			rv = 'float'
			node1.requireType = rv
			node2.requireType = rv
	return rv

# force node to be a number type and return the type

def _numberType(node):
	if node.exprType in _numberTypes:
		return node.exprType
	else:
		node.requireType = 'float'
		return node.requireType



class TypeCheck(CleanupASTTraversal):

	"""Determine types of all expressions"""

	def __init__(self, ast, vars, filename):
		CleanupASTTraversal.__init__(self, ast)
		self.vars = vars
		self.filename = filename
		self.postorder()

	# atoms

	def n_FLOAT(self, node):
		node.exprType = 'float'
		node.requireType = node.exprType
	def n_INTEGER(self, node):
		node.exprType = 'int'
		node.requireType = node.exprType
	def n_SEXAGESIMAL(self, node):
		node.exprType = 'float'
		node.requireType = node.exprType
	def n_INDEF(self, node):
		node.exprType = 'indef'
		node.requireType = node.exprType
	def n_STRING(self, node):
		node.exprType = 'string'
		node.requireType = node.exprType
	def n_QSTRING(self, node):
		node.exprType = 'string'
		node.requireType = node.exprType
	def n_EOF(self, node):
		node.exprType = 'string'
		node.requireType = node.exprType
	def n_BOOL(self, node):
		node.exprType = 'bool'
		node.requireType = node.exprType

	def n_IDENT(self, node):
		s = irafutils.translateName(node.attr)
		if self.vars.proc_args_dict.has_key(s):
			a = self.vars.proc_args_dict[s]
			node.exprType = _typeDict[a.type]
			node.requireType = node.exprType
		elif self.vars.local_vars_dict.has_key(s):
			a = self.vars.local_vars_dict[s]
			node.exprType = _typeDict[a.type]
			node.requireType = node.exprType
		else:
			# not a local variable
			node.exprType = 'indef'
			node.requireType = node.exprType

	def n_array_ref(self, node):
		node.exprType = node[0].exprType
		node.requireType = node.exprType

	def n_function_call(self, node):
		functionname = node[0].attr
		ftype = _functionType.get(functionname)
		if ftype is None: ftype = 'indef'
		node.exprType = ftype
		node.requireType = node.exprType

	def n_atom(self, node):
		assert len(node)==3
		node.exprType = node[1].exprType
		node.requireType = node.exprType

	def n_power(self, node):
		assert len(node)==3
		node.exprType = _arithType(node[0], node[2])
		node.requireType = node.exprType

	def n_factor(self, node):
		assert len(node)==2
		node.exprType = _numberType(node[1])
		node.requireType = node.exprType

	def n_term(self, node):
		assert len(node)==3
		node.exprType = _arithType(node[0], node[2])
		node.requireType = node.exprType

	def n_concat_expr(self, node):
		assert len(node)==3
		node.exprType = 'string'
		node.requireType = node.exprType
		node[0].requireType = 'string'
		node[2].requireType = 'string'

	def n_arith_expr(self, node):
		assert len(node)==3
		if node[1].type == '-':
			node.exprType = _arithType(node[0], node[2])
			node.requireType = node.exprType
		else:
			# plus -- could mean add or concatenate
			if node[0].exprType == 'string' or node[2].exprType == 'string':
				node.exprType = 'string'
				node.requireType = node.exprType
				node[0].requireType = 'string'
				node[2].requireType = 'string'
			else:
				node.exprType = _arithType(node[0], node[2])
				node.requireType = node.exprType

	def n_comp_expr(self, node):
		assert len(node) == 3
		node.exprType = 'bool'
		node.requireType = node.exprType

	def n_not_expr(self, node):
		assert len(node) == 2
		node.exprType = 'bool'
		node.requireType = node.exprType
		node[1].requireType = 'bool'

	def n_expr(self, node):
		assert len(node) == 3
		node.exprType = 'bool'
		node.requireType = node.exprType
		node[0].requireType = 'bool'
		node[2].requireType = 'bool'
	
	def n_assignment_stmt(self, node):
		assert len(node) == 3
		node[2].requireType = node[0].exprType


# tokens that are translated or skipped outright
_translateList = {
			"{": "",
			"}": "",
			";": "",
			"!": "not ",
			"//": " + ",
			}

# builtin task names that are translated

_taskList = {
			"cl"			: "clProcedure",
			"print"			: "clPrint",
			"_curpack"		: "curpack",
			"_allocate"		: "clAllocate",
			"_deallocate"	: "clDeallocate",
			"_devstatus"	: "clDevstatus",
			}

# builtin functions that are translated
# other functions just have 'iraf.' prepended

_functionList = {
			"int":		"int",
			"real":		"float",
			"str":		"str",
			"sin":		"math.sin",
			"cos":		"math.cos",
			"tan":		"math.tan",
			"atan2":	"math.atan2",
			"exp":		"math.exp",
			"log":		"math.log",
			"log10":	"math.log10",
			"sqrt":		"math.sqrt",
			"frac":		"math.frac",
			"abs":		"math.abs",
			"min":		"math.min",
			"max":		"math.max",
			}

# return types of IRAF built-in functions

_functionType = {
			"int":		"int",
			"real":		"float",
			"sin":		"float",
			"cos":		"float",
			"tan":		"float",
			"atan2":	"float",
			"exp":		"float",
			"log":		"float",
			"log10":	"float",
			"sqrt":		"float",
			"frac":		"float",
			"abs":		"float",
			"min":		"indef",
			"max":		"indef",
			"fscan":	"int",
			"scan":		"int",
			"nscan":	"int",
			"stridx":	"int",
			"strlen":	"int",
			"str":		"string",
			"substr":	"string",
			"envget":	"string",
			"mktemp":	"string",
			"radix":	"string",
			"osfn":		"string",
			"_curpack":	"string",
			"defpar":	"bool",
			"access":	"bool",
			"defvar":	"bool",
			"deftask":	"bool",
			"defpac":	"bool",
			"imaccess":	"bool",
			}

# logical operator conversion
_LogOpDict = {
			"&&": " and ",
			"||": " or ",
			}

# redirection conversion
_RedirDict = {
			">":	"Stdout",
			">>":	"StdoutAppend",
			">&":	"Stderr",
			">>&":	"StderrAppend",
			"<":	"Stdin",
			}

# tokens printed with both leading and trailing space
_bothSpaceList = {
			"=": 1,
			"ASSIGNOP": 1,
			"COMPOP": 1,
			"+": 1,
			"-": 1,
			"/": 1,
			"*": 1,
			"//": 1,
			}

# tokens printed with only trailing space
_trailSpaceList = {
			",": 1,
			"REDIR": 1,
			"IF": 1,
			"WHILE": 1,
			}

# Convert token value to IRAF type specified by Variable object
# always returns a string, suitable for use in assignment like:
# 'var = ' + _convFunc(var, value)
# The only permitted conversion is int->float.

_stringTypes = { "string": 1,
				"char": 1,
				"file": 1,
				"struct": 1,
				"gcur": 1,
				"imcur": 1,
				"ukey": 1,
				"pset": 1,
				}

def _convFunc(var, value):
	if var.list_flag or _stringTypes.has_key(var.type):
		if value is None:
			return ""
		else:
			return str(value)
	elif var.type == "int":
		if value is None:
			return "INDEF"
		elif type(value) == types.StringType and value[:1] == ")":
			# parameter indirection
			return value
		else:
			return int(value)
	elif var.type == "real":
		if value is None:
			return "INDEF"
		elif type(value) == types.StringType and value[:1] == ")":
			# parameter indirection
			return value
		else:
			return float(value)
	elif var.type == "bool":
		if value is None:
			return "INDEF"
		elif type(value) in [types.IntType,types.FloatType]:
			if value == 0:
				return 'no'
			else:
				return 'yes'
		elif type(value) == types.StringType:
			s = string.lower(value)
			if s == "yes" or s == "y":
				s = "yes"
			elif s == "no" or s == "n":
				s = "'no'"
			elif s[:1] == ")":
				# parameter indirection
				return value
			else:
				raise ValueError(
					"Illegal value `%s' for boolean variable %s" %
					(s, var.name))
			return s
		else:
			try:
				return value.bool()
			except AttributeError, e:
				raise AttributeError(var.name + ':' + str(e))
	raise ValueError("unimplemented type `%s'" % (var.type,))


class Tree2Python(CleanupASTTraversal):
	def __init__(self, ast, vars, filename=''):
		CleanupASTTraversal.__init__(self, ast)
		self.filename = filename
		self.column = 0
		self.vars = vars
		self.inSwitch = 0
		self.caseCount = []
		# printPass is an array of flags indicating whether the
		# corresponding indentation level is empty.  If empty when
		# the block is terminated, a 'pass' statement is generated.
		# Start with a reasonable size for printPass array.
		# (It gets extended if necessary.)
		self.printPass = [1]*10
		self.code_buffer = cStringIO.StringIO()
		self.errlist = []
		self.warnlist = []
		self.importDict = {}
		self.specialDict = {}
		self.pipeOut = []
		self.pipeIn = []
		self.pipeCount = 0

		if self.vars.proc_name:
			self.indent = 1
		else:
			self.indent = 0

		self.preorder()
		self.write("\n")

		self.code = self.code_buffer.getvalue()
		self.code_buffer.close()

		# write the header second so it can be minimal
		self.code_buffer = cStringIO.StringIO()
		self.writeProcHeader()
		self.code = self.code_buffer.getvalue() + self.code
		self.code_buffer.close()
		del self.code_buffer

		if self.warnlist:
			self.warnlist = map(lambda x: 'Warning: '+x, self.warnlist)
			warnmsg = string.join(self.warnlist,"\n")
			sys.stdout.flush()
			sys.stderr.write(warnmsg)
			if warnmsg[-1:] != '\n': sys.stderr.write('\n')

		if self.errlist:
			errmsg = string.join(self.errlist,"\n")
			raise SyntaxError(errmsg)

	def incrIndent(self):
		"""Increment indentation count"""
		# printPass is used to recognize empty indentation blocks
		# and add 'pass' statement when indentation level is decremented
		self.indent = self.indent+1
		if len(self.printPass) <= self.indent:
			# extend array to length self.indent+1
			self.printPass = self.printPass + \
					(self.indent+1-len(self.printPass)) * [1]
		self.printPass[self.indent] = 1

	def decrIndent(self):
		"""Decrement indentation count and write 'pass' if required"""
		if self.printPass[self.indent]:
			self.writeIndent('pass')
		self.indent = self.indent-1

	def write(self, s, requireType=None, exprType=None):

		"""Write string to output code buffer"""

		if requireType != exprType:
			# need to wrap this subexpression in a conversion function
			cf = _funcName(requireType, exprType)
			if cf is not None:
				s = cf + '(' + s + ')'
		self.code_buffer.write(s)
		# maintain column count to help with breaking across lines
		self.column = self.column + len(s)
		# handle simple cases of a single initial tab or trailing newline
		if s[:1] == "\t":
			self.column = self.column + 3
		elif s[-1:] == "\n":
			self.column = 0

	def writeIndent(self, value=None):

		"""Write newline and indent"""

		self.write("\n")
		for i in range(self.indent):
			self.write("\t")
		if value: self.write(value)
		self.printPass[self.indent] = 0

	def error(self, msg, node):
		s = msg
		if hasattr(node,'lineno'):
			msg = "%s (line %d)" % (msg, node.lineno)
		self.errlist.append(msg)

	def warning(self, msg, node):
		s = msg
		if hasattr(node,'lineno'):
			msg = "%s (line %d)" % (msg, node.lineno)
		self.warnlist.append(msg)

	def writeProcHeader(self):

		"""Write function definition and other header info"""

		# save printPass flag -- if it is set, the body of
		# the procedure is currently empty and so 'pass' may be added
		printPass = self.printPass[1]

		# reset indentation level; never need 'pass' stmt in header
		self.indent = 0
		self.printPass[0] = 0

		# most header info is omitted in 'single' translation mode
		noHdr = self.vars.mode == "single" and self.vars.proc_name == ""

		# do basic imports and definitions outside procedure definition,
		# mainly so INDEF can be used as a default value for keyword
		# parameters in the def statement

		if not noHdr:
			self.write("import pyraf, iraf, math")
			self.writeIndent("from irafpar import makeIrafPar")
			self.writeIndent("yes = 1; no = 0; INDEF = iraf.INDEF; EOF = 'EOF'")
			self.write("\n")

		if self.vars.proc_name:
			# create list of procedure arguments
			# make list of IrafPar definitions at the same time
			n = len(self.vars.proc_args_list)
			namelist = n*[None]
			proclist = n*[None]
			deflist = n*[None]
			for i in range(n):
				p = self.vars.proc_args_list[i]
				v = self.vars.proc_args_dict[p]
				namelist[i] = irafutils.translateName(p)
				if _SpecialArgs.has_key(p):
					# special arguments are Python types
					proclist[i] = p + '=' + str(v)
					deflist[i] = ''
				else:
					try:
						proclist[i] = v.procLine()
						deflist[i] = v.parDefLine()
					except AttributeError, e:
						raise AttributeError(self.filename + ':' + str(e))
			# allow long argument lists to be broken across lines
			self.writeIndent("def " + self.vars.proc_name + "(")
			self.writeChunks(proclist)
			self.write("):\n")
			self.incrIndent()
			# reset printPass in case procedure is empty
			self.printPass[self.indent] = printPass
		else:
			namelist = []
			deflist = []

		# write additional required imports
		wnewline = 0
		if not noHdr:
			keylist = self.importDict.keys()
			if keylist:
				keylist.sort()
				self.writeIndent("import ")
				self.write(string.join(keylist, ", "))
				wnewline = 1

		if self.specialDict.has_key("PkgName"):
			self.writeIndent("PkgName = iraf.curpack(); "
				"PkgBinary = iraf.curPkgbinary()")
			wnewline = 1
		if wnewline: self.write("\n")

		if deflist:
			# write procedure parameter definitions
			for i in range(n):
				if deflist[i]:
					self.writeIndent(namelist[i] + " = makeIrafPar(")
					self.writeChunks(deflist[i])
					self.write(")")
			self.write("\n")

		# initialize new local variables
		for v in self.vars.local_vars_list[self.vars.local_vars_count:]:
			lvar = self.vars.local_vars_dict[v]
			if lvar.array_size is not None:
				self.writeIndent(lvar.name + " = " +
					"iraf.clArray(" +
					str(lvar.array_size) + "," +
					`lvar.type` + "," +
					"name=" + `lvar.name`)
				if lvar.init_value is not None:
					self.write(", init_value=[")
					arglist = []
					for iv in lvar.init_value:
						arglist.append(`iv`)
					self.writeChunks(arglist)
					self.write("]")
				self.write(")")
			elif lvar.init_value is not None:
				self.writeIndent(lvar.name + " = " + `lvar.init_value`)

		# decrement indentation (which writes the pass if necessary)
		self.decrIndent()

	#------------------------------
	# elements that can be ignored
	#------------------------------

	def n_proc_stmt(self, node): self.prune()
	def n_declaration_block(self, node): self.prune()
	def n_declaration_stmt(self, node): self.prune()

	def n_BEGIN(self, node): pass
	def n_END(self, node): pass
	def n_NEWLINE(self, node): pass

	#------------------------------
	#XXX unimplemented features
	#------------------------------

	def n_BKGD(self, node):
		# background execution ignored for now
		self.warning("Background execution ignored", node)

	#------------------------------
	# low-level conversions
	#------------------------------

	def n_FLOAT(self, node):
		# convert d exponents to e for Python 
		s = node.attr
		i = string.find(s, 'd')  
		if i>=0: 
			s = s[:i] + 'e' + s[i+1:] 
		else: 
			i = string.find(s, 'D')
			if i>=0:
				s = s[:i] + 'E' + s[i+1:]
		self.write(s, node.requireType, node.exprType)

	def n_INTEGER(self, node):
		# convert octal and hex constants
		value = node.attr
		last = string.lower(value[-1])
		if last == 'b':
			# octal
			self.write('0'+value[:-1], node.requireType, node.exprType)
		elif last == 'x':
			# hexadecimal
			self.write('0x'+value[:-1], node.requireType, node.exprType)
		else:
			# remove leading zeros on decimal values
			i=0
			for digit in value:
				if digit != '0': break
				i = i+1
			else:
				# all zeros
				i = i-1
			self.write(value[i:], node.requireType, node.exprType)

	def n_SEXAGESIMAL(self, node):
		# convert d:m:s values to float
		v = string.split(node.attr, ':')
		# at least 2 values in expression
		s = 'iraf.clSexagesimal(' + v[0] + ',' + v[1]
		if len(v)>2: s = s + ',' + v[2]
		s = s + ')'
		self.write(s, node.requireType, node.exprType)

	def n_IDENT(self, node, array_ref=0):
		s = irafutils.translateName(node.attr)
		if self.vars.proc_args_dict.has_key(s):
			if not _SpecialArgs.has_key(s) and not array_ref:
				# If this is a procedure parameter, append '.p_value' so sets
				# and gets work correctly.  (Not needed for array references)
				#XXX Note we are not doing minimum match on parameter names
				s = s+'.p_value'
			self.write(s, node.requireType, node.exprType)
		elif self.vars.local_vars_dict.has_key(s):
			self.write(s, node.requireType, node.exprType)
		elif '.' in s:
			# looks like a task.parameter or field reference
			# look for special p_ extensions -- need to use task objects
			# instead of task values if they are specified
			attribs = string.split(s,'.')
			if len(attribs)==2 and \
			  self.vars.proc_args_dict.has_key(attribs[0]) and \
			  attribs[1][:2] == "p_":
				# this is a reference to a field of a procedure parameter
				# just write it directly
				self.write(s, node.requireType, node.exprType)
			else:
				prefix = 'iraf.'
				if attribs[-1][:2] == 'p_':
					attribs[-2] = 'getParObject(' + `attribs[-2]` +  ')'
					s = string.join(attribs,'.')
				self.write(prefix+s, node.requireType, node.exprType)
		else:
			# not a local variable; use task object to search other
			# dictionaries
			if self.vars.mode == "single":
				self.write('iraf.cl.'+s, node.requireType, node.exprType)
			else:
				self.write('taskObj.'+s, node.requireType, node.exprType)

	def n_array_ref(self, node):
		# in array reference, do not add .p_value to parameter identifier
		# because we can index the parameter directly
		# wrap in a conversion function if necessary
		cf = _funcName(node.requireType, node.exprType)
		if cf: self.write(cf + "(")
		self.n_IDENT(node[0], array_ref=1)
		self.write("[")
		# subtract one from IRAF subscripts to get Python subscripts
		if node[2].type == "INTEGER":
			self.write(str(int(node[2])-1) + "]")
		else:
			self.preorder(node[2])
			self.write("-1]")
		if cf: self.write(")")
		self.prune()

	def n_param_name(self, node):
		s = irafutils.translateName(node[0].attr,dot=1)
		self.write(s)
		self.prune()

	def n_LOGOP(self, node):
		self.write(_LogOpDict[node.attr])

	def n_function_call(self, node):
		# all functions are built-in (since CL does not allow new definitions)
		# wrap in a conversion function if necessary
		cf = _funcName(node.requireType, node.exprType)
		if cf: self.write(cf + "(")
		functionname = node[0].attr
		newname = _functionList.get(functionname)
		if newname is None:
			# just add "iraf." prefix
			newname = "iraf." + functionname
		self.write(newname + "(")
		# argument list for scan statement
		sargs = self.captureArgs(node[2])
		if functionname in ["scan", "fscan"]:
			# scan is weird -- effectively uses call-by-name
			# call special routine to change the args
			sargs = self.modify_scan_args(functionname, sargs)
		self.writeChunks(sargs)
		self.write(")")
		if cf: self.write(")")
		self.prune()

	def modify_scan_args(self, functionname, sargs):
		# modify argument list for scan statement
		# pass in locals dictionary and names of variables to set
		sargs.insert(0, "locals()")
		# if fscan, first argument is the string to read from
		if functionname == 'fscan':
			i = 2
		else:
			i = 1
		# if there are non-string local variables in the list, we have to
		# coerce the types in the scan function
		# non-local (parameter) type coercion happens automatically
		nlocal = 0
		localType = []
		for varname in sargs[i:]:
			ventry = self.vars.local_vars_dict.get(varname)
			if ventry is None:
				localType.append(None)
			else:
				vtype = _typeDict[ventry.type]
				# this will be used as the name of the conversion function
				# in the scan procedure
				localType.append(_funcName(vtype,"string"))
				if localType[-1] is not None:
					nlocal = nlocal + 1
		# add quotes to names (we're literally passing the names, not
		# the values)
		sargs[i:] = map(lambda x: `x`, sargs[i:])
		# append the types list if it is not all zeros
		if nlocal>0:
			localType = map(repr, localType)
			sargs.append("strconv=(" + string.join(localType,",") + ",)")
		return sargs

	def default(self, node):

		"""Handle other tokens"""

		if hasattr(node, 'exprType'):
			requireType = node.requireType
			exprType = node.exprType
		else:
			requireType = None
			exprType = None

		if isinstance(node, Token):
			s = _translateList.get(node.type)
			if s is not None:
				self.write(s, requireType, exprType)
			elif _trailSpaceList.has_key(node.type):
				self.write(`node`, requireType, exprType)
				self.write(" ")
			elif _bothSpaceList.has_key(node.type):
				self.write(" ")
				self.write(`node`, requireType, exprType)
				self.write(" ")
			else:
				self.write(`node`, requireType, exprType)
		elif requireType != exprType:
			cf = _funcName(requireType, exprType)
			if cf is not None:
				self.write(cf + '(')
				for nn in node:
					self.preorder(nn)
				self.write(')')
				self.prune()

	#------------------------------
	# block indentation control
	#------------------------------

	def n_compound_stmt(self, node):
		self.write(":")
		self.incrIndent()

	def n_compound_stmt_exit(self, node):
		self.decrIndent()

	def n_nonnull_stmt(self, node):
		if node[0].type == "{":
			# indentation already done for compound statements
			self.preorder(node[1])
			self.prune()
		else:
			self.writeIndent()

	#------------------------------
	# statements
	#------------------------------

	def n_osescape_stmt(self, node):
		self.write("iraf.clOscmd(" + `node[0].attr` + ")")
		self.prune()

	def n_assignment_stmt(self, node):
		if node[1].type == "ASSIGNOP":
			# convert +=, -=, etc.
			self.preorder(node[0])
			self.write(" = ")
			self.preorder(node[0])
			self.write(" " + node[1].attr[0] + " ")
			self.preorder(node[2])
			self.prune()

	def n_else_clause(self, node):
		# recognize special 'else if' case

		# pattern is:
		#       else_clause ::= opt_newline ELSE compound_stmt
		#     compound_stmt ::= opt_newline one_compound_stmt
		# one_compound_stmt ::= nonnull_stmt
		#      nonnull_stmt ::= if_stmt

		if len(node) == 3:
			stmt = node[2][1]
			if stmt.type == "nonnull_stmt" and stmt[0].type == "if_stmt":
				self.writeIndent("el")
				self.preorder(stmt[0])
				self.prune()

	def n_ELSE(self, node):
		# else clause is not a 'nonnull_stmt', so must explicitly
		# print the indentation
		self.writeIndent("else")

	def n_for_stmt(self, node):
		# convert for loop into while loop
		#
		#  0  1      2         3    4      5     6     7    8
		# for ( initialization ; condition ; increment ) compound_stmt
		#
		# any of the components inside the parentheses may be empty
		#
		# -------- initialization --------
		init = node[2]
		if init.type == "opt_assign_stmt" and len(init)==0:
			# empty initialization
			self.write("while (")
		else:
			self.preorder(init)
			self.writeIndent("while (")
		# -------- condition --------
		condition = node[4]
		if condition.type == "opt_bool" and len(condition)==0:
			# empty condition
			self.write("1")
		else:
			self.preorder(condition)
		self.write(")")
		# -------- execution block --------
		# go down inside the compound_stmt item so the increment can
		# be included inside the same block
		self.write(":")
		self.incrIndent()
		for subnode in node[8]: self.preorder(subnode)
		# -------- increment --------
		incr = node[6]
		if incr.type == "opt_assign_stmt" and len(incr)==0:
			# empty increment
			pass
		else:
			self.writeIndent()
			self.preorder(incr)
		self.decrIndent()
		self.prune()

	def n_next_stmt(self, node):
		self.write("continue")
		self.prune()

	def n_label_stmt(self, node):
		# write labels as comments for now
		self.write("# LABEL: ")

	def n_goto_stmt(self, node):
		self.error("GOTOs in CL scripts are not implemented", node[0])

	def n_inspect_stmt(self, node):
		self.write("print ")
		self.preorder(node[1])
		self.prune()

	def n_switch_stmt(self, node):
		self.inSwitch = self.inSwitch + 1
		self.caseCount.append(0)
		self.write("SwitchVal%d = " % (self.inSwitch,))
		self.preorder(node[2])
		self.preorder(node[4])
		self.inSwitch = self.inSwitch - 1
		del self.caseCount[-1]
		self.prune()

	def n_case_block(self, node):
		self.preorder(node[2])
		self.preorder(node[3])
		self.prune()

	def n_case_stmt_block(self, node):
		if self.caseCount[-1] == 0:
			self.caseCount[-1] = 1
			self.writeIndent("if ")
		else:
			self.writeIndent("elif ")
		self.write("SwitchVal%d in [" % (self.inSwitch,))
		self.preorder(node[2])
		self.write("]")
		self.preorder(node[4])
		self.prune()

	def n_default_stmt_block(self, node):
		if len(node)>0:
			if self.caseCount[-1] == 0:
				# only a default in this switch
				self.writeIndent("if 1")
			else:
				self.writeIndent("else")
			self.preorder(node[3])
			self.prune()

	#------------------------------
	# pipes implemented using redirection
	#------------------------------

	def n_task_pipe_stmt(self, node):
		self.pipeCount = self.pipeCount+1
		pipename = 'Pipe' + str(self.pipeCount)
		self.pipeOut.append(pipename)
		self.preorder(node[0])
		self.pipeOut = self.pipeOut[:-1]
		self.pipeIn.append(pipename)
		self.writeIndent()
		self.preorder(node[2])
		self.pipeIn = self.pipeIn[:-1]
		self.pipeCount = self.pipeCount-1
		self.prune()

	#------------------------------
	# task execution
	#------------------------------

	def n_task_call_stmt(self, node):
		taskname = node[0].attr
		self.currentTaskname = taskname
		# '$' prefix means print time required for task (just ignore it for now)
		if taskname[:1] == '$': taskname = taskname[1:]
		# translate some special task names and add "iraf." to all names
		# additionalArguments will get appended at the end of the
		# argument list
		self.additionalArguments = []
		addsep = ""
		# add plumbing for pipes if necessary
		if self.pipeOut:
			# create new output pipe
			self.write(self.pipeOut[-1] + " = cStringIO.StringIO()")
			self.writeIndent()
			self.importDict["cStringIO"] = 1
			self.additionalArguments.append("Stdout=" + self.pipeOut[-1])
		if self.pipeIn:
			# read from existing input pipe
			self.additionalArguments.append("Stdin=" + self.pipeIn[-1])
		# add extra arguments for task, package commands
		newname = _taskList.get(taskname, taskname)
		newname = "iraf." + irafutils.translateName(newname)
		if taskname == 'task':
			# task needs additional package, bin arguments
			self.specialDict['PkgName'] = 1
			self.additionalArguments.append("PkgName=PkgName")
			self.additionalArguments.append("PkgBinary=PkgBinary")
		elif taskname == 'package':
			# package needs additional package, bin arguments and returns args
			self.specialDict['PkgName'] = 1
			self.additionalArguments.append("PkgName=PkgName")
			self.additionalArguments.append("PkgBinary=PkgBinary")
			# package is a function returning new values for PkgName etc.
			self.write("PkgName, PkgBinary = ")
		# add extra argument to save parameters if in "single" mode
		if self.vars.mode == "single":
			self.additionalArguments.append("_save=1")
		self.write(newname)
		self.preorder(node[1])

		if self.pipeIn:
			# done with this input pipe
			self.writeIndent(self.pipeIn[-1] + ".close()")
		if self.pipeOut:
			# rewind the output pipe
			self.writeIndent(self.pipeOut[-1] + ".seek(0)")

		if taskname == "clbye":
			# must do a return after clbye() if not in 'single' mode
			if self.vars.mode != "single": self.writeIndent("return")
		self.prune()

	def n_task_arglist(self, node):
		# print task_arglist, adding parentheses if necessary
		if len(node) == 3:
			# parenthesized arglist
			# i is index for args in node
			i = 1
		elif len(node) == 1:
			# unparenthesized arglist
			i = 0
		else:
			# len(node)==2
			# fix some common CL script errors
			# (these are parsed in sloppy mode)
			if node[0].type == "(":
				# missing close parenthesis
				self.warning("Missing closing parenthesis", node[0])
				i = 1
			elif node[1].type == ")":
				# missing open parenthesis
				self.warning("Missing opening parenthesis", node[1])
				i = 0

		# get the list of arguments

		sargs = self.captureArgs(node[i])

		# Delete the extra parentheses on a single argument that already
		# has parentheses.  This is fixing a parsing ambiguity created by
		# the ability to interpret a single parenthesized argument either
		# as a parenthesized list or as an unparenthesized list consisting
		# of an expression.
		if len(sargs) == 1:
			s = sargs[0]
			if s[:1] == "(" and s[-1:] == ")": sargs[0] = s[1:-1]

		if self.currentTaskname in ["scan", "fscan"]:
			# scan is weird -- effectively uses call-by-name
			# call special routine to change the args
			sargs = self.modify_scan_args(self.currentTaskname, sargs)

		# combine CL arguments with additional (redirection) arguments
		sargs = sargs + self.additionalArguments
		self.additionalArguments = []

		# break up arg list into line-sized chunks
		self.write("(")
		self.writeChunks(sargs)
		self.write(")")
		self.prune()

	def captureArgs(self, node):
		"""Process the arguments list and return a list of the args"""

		# arguments get written to a separate string so we can
		# decide whether extra parens are really needed or not
		# Also add special character after arguments to make it
		# easier to break up long lines

		arg_buffer = cStringIO.StringIO()
		saveColumn = self.column
		saveBuffer = self.code_buffer
		self.code_buffer = arg_buffer

		# add a special character after commas to make it easy
		# to break up argument list for long lines
		global _translateList
		# save current translation for comma to handle nested lists
		curComma = _translateList.get(',')
		_translateList[','] = ',\255'

		self.preorder(node)

		# restore original comma translation and buffer pointers
		if curComma is None:
			del _translateList[',']
		else:
			_translateList[','] = curComma
		self.code_buffer = saveBuffer
		self.column = saveColumn

		args = arg_buffer.getvalue()
		arg_buffer.close()

		# split arguments into list
		sargs = string.split(args, ',\255')
		if sargs[0] == '': del sargs[0]
		return sargs

	def writeChunks(self, arglist, linelength=78):
		# break up arg list into line-sized chunks
		if not arglist: return
		maxline = linelength - self.column
		newargs = arglist[0]
		for arg in arglist[1:]:
			if len(newargs)+len(arg)+2>maxline:
				self.write(newargs + ',')
				self.writeIndent('\t')
				newargs = arg
				maxline = linelength - self.column
			else:
				newargs = newargs + ', ' + arg
		self.write(newargs)

	def n_empty_arg(self, node):
		#XXX This is an omitted argument
		#XXX Not really correct yet -- need to work on this
		self.write('None')
		self.prune()

	def n_bool_arg(self, node):
		self.preorder(node[0])
		if node[1].type == "+":
			self.write("=yes")
		else:
			self.write("=no")
		self.prune()

	def n_redir_arg(self, node):
		# redirection is handled by special keyword parameters
		# Stdout=<filename>, Stdin=<filename>, Stderr=<filename>, etc.
		s = node[0].attr
		redir = _RedirDict.get(s)
		if redir is None:
			# must be GIP redirection, construct a standard name
			# using GIP in sorted order
			tail = []
			while s[-1] in 'PIG':
				tail.append(s[-1])
				s = s[:-1]
			tail.sort()
			redir = _RedirDict[s] + string.join(tail,'')
		self.write(redir + '=')
		self.preorder(node[1])
		self.prune()

# ------------- Python code cache -------------
# Uses filename as key and size, creation/modification
# dates, and Pycode as value
# Uses shelve module to create persistent dictionaries
# Allows a list of cache files

import shelve, stat

class _CodeCache:

	"""Python code cache class"""

	def __init__(self, filelist):
		cachelist = []
		flist = []
		nwrite = 0
		for file in filelist:
			# first try opening the cache read-write
			# first argument of tuple is writeflag
			try:
				cachelist.append( (1, shelve.open(file)) )
				nwrite = nwrite+1
				flist.append(file)
			except:
				# that failed -- try opening the cache read-only
				# Note I'm catching all errors here because shelve.open
				# raises an unpredictable type of exception depending
				# on the underlying database.  Ideally I should modify
				# shelve.open so it raises a standard error.
				try:
					cachelist.append( (0, shelve.open(file,"r")) )
					flist.append(file)
				except:
					self.warning("Unable to open CL script cache file %s" %
						(file,))
		self.cachelist = cachelist
		self.filelist = flist
		self.nwrite = nwrite
		# flag indicating preference for system cache
		self.useSystem = 0
		if not cachelist:
			self.warning("Unable to open any CL script cache, "
				"performance will be slow")
		elif nwrite == 0:
			self.warning("Unable to open any CL script cache for writing")

	def warning(self, msg, level=0):

		"""Print warning message to stderr, using verbose flag"""

		if iraffunctions.Verbose >= level:
			sys.stdout.flush()
			sys.stderr.write(msg + "\n")
			sys.stderr.flush()

	def writeSystem(self, value=1):

		"""Add scripts to system cache instead of user cache"""

		if value==0:
			self.useSystem = 0
		elif self.cachelist:
			writeflag, cache = self.cachelist[-1]
			if writeflag:
				self.useSystem = 1
			else:
				self.warning("System CL script cache is not writable")
		else:
			self.warning("No CL script cache is active")

	def close(self):

		"""Close all cache files"""

		for writeflag, cache in self.cachelist:
			cache.close()
		self.cachelist = []
		self.nwrite = 0

	def __del__(self):
		self.close()

	def getIndex(self, filename):

		"""Get cache key & file attributes for a file or filehandle"""

		if type(filename) is types.StringType:
			st = os.stat(filename)
		elif hasattr(filename, 'fileno') and hasattr(filename, 'name'):
			fh = filename
			st = os.fstat(fh.fileno())
			filename = fh.name
		else:
			return None, None
		# use filename as key
		# file attributes are size, creation, and modification times
		key = filename
		attributes = ( st[stat.ST_SIZE], st[stat.ST_CTIME], st[stat.ST_MTIME] )
		return key, attributes

	def add(self, index, pycode):

		"""Add pycode to cache with key = index.  Ignores if index=None."""

		if index is None or self.nwrite==0: return
		if self.useSystem:
			# system cache is last in list
			cachelist = self.cachelist[:]
			cachelist.reverse()
		else:
			cachelist = self.cachelist
		for writeflag, cache in cachelist:
			if writeflag:
				cache[index] = pycode
				return

	def get(self, filename, mode="proc"):

		"""Get pycode from cache for this file.
		
		Returns tuple (index, attributes, pycode).  Pycode=None if not found
		in cache.  If mode != "proc", assumes that the code should not be
		cached.
		"""

		if mode != "proc": return None, None, None

		index, attributes = self.getIndex(filename)
		if index is None: return None, None, None

		for i in range(len(self.cachelist)):
			writeflag, cache = self.cachelist[i]
			if cache.has_key(index):
				pycode = cache[index]
				oldattr = pycode.attributes
				if oldattr == attributes:
					return index, attributes, pycode
				elif writeflag:
					del cache[index]
					if oldattr[1]>attributes[1] or oldattr[2]>attributes[2]:
						self.warning("Warning: cached CL script (%s)"
							" in %s was newer than current script"
							 % (filename,self.filelist[i]))
				else:
					self.warning("Warning: cached CL script (%s)"
						"is out of date, but cache %s is read-only"
						 % (filename,self.filelist[i]))
		return index, attributes, None

	def remove(self, filename):

		"""Remove pycode from cache for this file or IrafTask object."""

		if isinstance(filename, iraftask.IrafCLTask):
			task = filename
			filename = task.getFullpath()
		elif type(filename) is not types.StringType:
			raise TypeError("Filename parameter must be a string or IrafCLTask")
		index, attributes = self.getIndex(filename)
		# system cache is last in list
		irange = range(len(self.cachelist))
		if self.useSystem: irange.reverse()
		nremoved = 0
		for i in irange:
			writeflag, cache = self.cachelist[i]
			if cache.has_key(index):
				if writeflag:
					del cache[index]
					self.warning("Removed %s from CL script cache %s" % \
						(filename,self.filelist[i]), 2)
					nremoved = nremoved+1
				else:
					self.warning("Cannot remove %s from read-only "
						"CL script cache %s" % \
						(filename,self.filelist[i]))
		if nremoved==0:
			self.warning("Did not find %s in CL script cache" % filename, 2)


# set up pickle so it can pickle code objects

import copy_reg, marshal, types
try:
	import cPickle
	pickle = cPickle
except ImportError:
	import pickle

def code_unpickler(data):
	return marshal.loads(data)

def code_pickler(code):
	return code_unpickler, (marshal.dumps(code),)

copy_reg.pickle(types.CodeType, code_pickler, code_unpickler)

#XXX Just ignoring instance method objects
#XXX I think these pickling functions are currently not used, but
#XXX leave this (with debug writes) in case they are needed again.

def dummy_unpickler(data):
	return None

def dummy_pickler(dummy):
	#XXX
	print 'dummy_pickler called'
	return dummy_unpickler, ('',)

copy_reg.pickle(types.MethodType, dummy_pickler, dummy_unpickler)

# create code cache

userDir = os.path.join(iraffunctions._userIrafHome,'pyraf')
if not os.path.exists(userDir):
	try:
		os.mkdir(userDir)
		print 'Created directory %s for cache' % userDir
	except OSError:
		print 'Could not create directory %s' % userDir

dbfile = 'pyraf.Database'
codeCache = _CodeCache([
	os.path.join(userDir,dbfile),
	os.path.join(pyraf.homeDir,dbfile),
	])
del userDir, dbfile

if __name__ == "__main__":

	import time

	t0 = time.time()

	# scan file "simple.cl"

	filename = "simple.cl"
	lines = open(filename).read()
	scanner = clscan.CLScanner()
	tokens = scanner.tokenize(lines)
	t1 = time.time()

	# parse
	tree = _parser.parse(tokens)
	tree.filename = filename
	t2 = time.time()

	# first pass -- get variables

	vars = VarList(tree)
	t3 = time.time()

	# second pass -- generate python code

	pycode = Tree2Python(tree, vars)
	t4 = time.time()

	print "Scan:", t1-t0, "sec,   Parse:", t2-t1, "sec"
	print "Vars:", t3-t2, "sec, CodeGen:", t4-t3, "sec"

