"""Give help on variables, functions, modules, classes, IRAF tasks,
IRAF packages, etc.

- help() with no arguments will list all the defined variables.
- help("taskname") or help(IrafTaskObject) will direct Netscape to display
  the HTML version of IRAF help for the task
- help(object) where object is a module, instance, ? will display
  information on the attributes and methods of the object (or the
  variables, functions, and classes in the module)
- help(function) will give the calling sequence for the function (except
  for built-in functions)

and so on.  There are optional keyword arguments to help that specify
what information is to be printed:

variables=1	Print info on variables/attributes
functions=1	Print info on function/method calls
modules=1	Print info on modules
tasks=0		Print info on IrafTask objects
packages=0	Print info on IrafPkg objects
hidden=0	Print info on hidden variables/attributes (starting with '_')

regexp=None	Specify a regular expression that matches the names of
			variables of interest.  E.g. help(sys, regexp='std') will
			give help on all attributes of sys that start with std.
			regexp can use all the re patterns.

The padchars keyword determines some details of the format of the output.

The **kw argument allows minimum matching for the keyword arguments
(so help(func=1) will work).

$Id$

R. White, 1999 May 28
"""

import __main__, re, os, types
import minmatch, describe, iraf, iraftask

# print info on Numeric arrays if Numeric is available

try:
	import Numeric
	_NumericArrayType = Numeric.ArrayType
except:
	# no Numeric available, so we won't encounter arrays
	import traceback
	traceback.print_exc()
	_NumericArrayType = None

try:
	if _NumericArrayType:
		_NumericTypeName = {}
		_NumericTypeName[Numeric.PyObject]     = 'PyObject'
		_NumericTypeName[Numeric.UnsignedInt8] = 'UnsignedInt8'
		_NumericTypeName[Numeric.Int8]         = 'Int8'
		_NumericTypeName[Numeric.Int16]        = 'Int16'
		_NumericTypeName[Numeric.Int32]        = 'Int32'
		_NumericTypeName[Numeric.Float32]      = 'Float32'
		_NumericTypeName[Numeric.Float64]      = 'Float64'
		# Int sometimes has different character type than Int32,
		# but may really be the same type
		if not _NumericTypeName.has_key(Numeric.Int):
			a = Numeric.array([0],Numeric.Int)
			_NumericTypeName[Numeric.Int] = 'Int'+`a.itemsize()*8`
		_NumericTypeName[Numeric.Complex32]    = 'Complex32'
		_NumericTypeName[Numeric.Complex64]    = 'Complex64'
		_NumericTypeName[Numeric.Complex128]   = 'Complex128'
except:
	pass

_MODULE = 0
_FUNCTION = 1
_OTHER = 2

# set up minimum-match dictionary with function keywords

kwnames = ( 'variables', 'functions', 'modules',
		'tasks', 'packages', 'hidden', 'padchars', 'regexp' )
_kwdict = minmatch.MinMatchDict()
for key in kwnames: _kwdict.add(key,key)
del kwnames, key

def help(object=__main__, variables=1, functions=1, modules=1,
		tasks=0, packages=0, hidden=0, padchars=16, regexp=None,
		**kw):

	"""List the type and value of all the variables in the
	specified object.  Default is to list variables in main.
	The keywords can be abbreviated.  See module documentation
	for more info."""

	# get the keywords
	for key in kw.keys():
		try:
			fullkey = _kwdict[key]
			exec fullkey + ' = ' + `kw[key]`
		except KeyError, e:
			raise e.__class__("Error in keyword "+key+"\n"+str(e))

	# for IrafTask object, display HTML help and also print info on the object
	# for string parameter, if it looks like a task name try getting HTML help
	# on it too (XXX this is a bit risky, but I suppose people will not often
	# be asking for help with simple strings as an argument...)

	if isinstance(object,iraftask.IrafTask):
		print object
		_htmlHelp(object)
	if type(object) == types.StringType and re.match(r'_?[a-z]+$',object):
		_htmlHelp(object)

	try:
		vlist = vars(object)
	except Exception:
		# just print info on the object itself
		vstr = _valueString(object,verbose=1)
		try:
			name = object.__name__
		except AttributeError:
			name = ''
		if len(name) < padchars:
			name = name + (padchars-len(name))*" "
		print name, ":", vstr
		return

	# make one pass through names getting the type and sort order
	# also split IrafTask and IrafPkg objects into separate lists
	names = vlist.keys()
	tasklist = []
	pkglist = []
	namelist = []
	for vname in names:
		value = vlist[vname]
		if isinstance(value,iraftask.IrafPkg):
			pkglist.append(vname)
		elif isinstance(value,iraftask.IrafTask):
			tasklist.append(vname)
		else:
			vtype = type(value)
			vorder = _sortOrder(vtype)
			namelist.append((vorder, vname, value))

	# now sort to group types of objects, and within types to put in
	# alphabetical order
	namelist.sort()
	if regexp: re_check = re.compile(regexp)
	for vorder, vname, value in namelist:
		if (hidden or vname[0:1] != '_') and \
				((not regexp) or re_check.match(vname)):
			if (functions and vorder == _FUNCTION) or \
					(modules and vorder == _MODULE) or \
					(variables and vorder == _OTHER):
				vstr = _valueString(value)
				# pad name to padchars chars if shorter
				if len(vname) < padchars:
					vname = vname + (padchars-len(vname))*" "
				print vname, ":", vstr

	# IRAF packages and tasks get listed in simple column format
	if packages:
		if pkglist:
			pkglist.sort()
			for i in xrange(len(pkglist)):
				pkglist[i] = pkglist[i] + '/'
			print "IRAF Packages:"
			iraf._printcols(pkglist)

	if tasks:
		if tasklist:
			tasklist.sort()
			print "IRAF Tasks:"
			iraf._printcols(tasklist)

	# XXX Need to modify this to look at all parents of this class
	# XXX too.  That's tricky because want to sort all methods/attributes
	# XXX together and, to be completely correct, need to resolve
	# XXX name clashes using the same scheme as Python does for multiple
	# XXX inheritance and multiply-overridden attributes.
	if (type(object) == types.InstanceType) and functions:
		# for instances, call recursively to list class methods
		help(object.__class__, functions=functions, tasks=tasks,
			packages=packages, variables=variables, hidden=hidden,
			padchars=padchars, regexp=regexp)

_functionTypes = (types.BuiltinFunctionType, types.BuiltinMethodType,
				types.FunctionType, types.LambdaType, types.MethodType,
				types.UnboundMethodType)
_numericTypes = (types.FloatType, types.IntType, types.LongType,
				types.ComplexType)

def _sortOrder(type):
	if type == types.ModuleType:
		v = _MODULE
	elif type in _functionTypes:
		v = _FUNCTION
	else:
		v = _OTHER
	return v

def _valueString(value,verbose=0):
	"""Returns name and, for some types, value of the variable as a string."""

	t = type(value)
	vstr = t.__name__
	if t == types.StringType:
		if len(value)>42:
			vstr = vstr + ", value = "+ `value[:39]` + '...'
		else:
			vstr = vstr + ", value = "+ `value`
	elif t == types.FileType:
		vstr = vstr + ", "+ `value`
	elif t in _numericTypes:
		vstr = vstr + ", value = "+ `value`
	elif t == types.InstanceType:
		cls = value.__class__
		if cls.__module__ == '__main__':
			vstr = 'instance of class ' + cls.__name__
		else:
			vstr = 'instance of class ' + cls.__module__ + '.' + cls.__name__
	elif t in _functionTypes:
		# try using Fredrik Lundh's describe on functions
		try:
			vstr = vstr + ' ' + describe.describe(value)
			try:
				if verbose and value.__doc__:
					vstr = vstr + "\n" + value.__doc__
			except:
				pass
		except:
			# oh well, just have to live with type string alone
			pass
	elif t == _NumericArrayType:
		vstr = vstr + " " + _NumericTypeName[value.typecode()] + "["
		for k in xrange(len(value.shape)):
			if k:
				vstr = vstr + "," + `value.shape[k]`
			else:
				vstr = vstr + `value.shape[k]`
		vstr = vstr + "]"
	else:
		# default -- just return the type
		pass
	return vstr

_HelpURL = "http://ra.stsci.edu/cgi-bin/gethelp.cgi?task="
_Netscape = "netscape"

def _htmlHelp(taskname):
	"""Display HTML help for given IRAF task in Netscape.
	Task can be either a name or an IrafTask object.
	Tries using 'netscape -remote' command to load the page in
	a running Netscape.  If that fails, starts a new netscape."""

	if isinstance(taskname,iraftask.IrafTask): taskname = taskname.getName()
	pid = os.fork()
	if pid == 0:
		url = _HelpURL + taskname
		cmd = _Netscape + " -remote 'openURL(" + url + ")' 1> /dev/null 2>&1"
		status = os.system(cmd)
		if status != 0:
			print "Starting Netscape for HTML help..."
			os.execvp("netscape",["netscape",url])
		os._exit(0)
	print "HTML help on", taskname,"is being displayed in Netscape"

