# http://www.dejanews.com/getdoc.xp?AN=382948703
#
# Instant Python
# $Id$
#
# utilities to describe functions, methods, and classes
#
# history:
# 96-10-27 fl     created
# 98-02-24 fl     added code to handle unpacked arguments
#
# notes:
# This has been tested with Python 1.4 and 1.5.  The code and
# function object attributes might change in future versions of
# Python.
#
# written by fredrik lundh.  last updated february 1998.
#
# fredrik@pythonware.com
# http://www.pythonware.com
#

import string

# --------------------------------------------------------------------
# code object attributes
# --------------------------------------------------------------------
# co_argcount   INT
# co_nlocals    INT
# co_flags      INT
#       CO_OPTIMIZED
#       CO_NEWLOCALS
#       CO_VARARGS
#       CO_VARKEYWORDS
# co_code       OBJECT
# co_consts     OBJECT
# co_names      OBJECT
# co_varnames   OBJECT
# co_filename   OBJECT
# co_name       OBJECT

# --------------------------------------------------------------------
# function object attributes
# --------------------------------------------------------------------
# func_code     OBJECT
# func_globals  OBJECT
# func_name     OBJECT (__name__)
# func_defaults OBJECT
# func_doc      OBJECT (__doc__)

# copied from Python header file
CO_OPTIMIZED = 0x0001
CO_NEWLOCALS = 0x0002
CO_VARARGS = 0x0004
CO_VARKEYWORDS = 0x0008

def _describe(func, name = None):
	# get argument list

	code = func.func_code

	n = code.co_argcount
	a = list(code.co_varnames[:n])
	p = 0
	for i in range(n):
		# anonymous arguments
		from dis import opname, HAVE_ARGUMENT
		c = code.co_code
		if not a[i] or a[i][0] == ".":
			vars = []
			while p < len(c):
				v = ord(c[p])
				if v >= HAVE_ARGUMENT:
					s, v = opname[v], ord(c[p+1]) + ord(c[p+2])*256
					p = p + 3
					if s == "UNPACK_TUPLE":
						count = v
					elif s == "STORE_FAST":
						vars.append(code.co_varnames[v])
						if len(vars) >= count:
							break
				else:
					p = p + 1
			if vars:
				a[i] = "(" + string.join(vars, ", ") + ")"
	if func.func_defaults:
		# defaults
		i = n - len(func.func_defaults)
		for d in func.func_defaults:
			a[i] = (a[i], d)
			i = i + 1
	if code.co_flags & CO_VARARGS:
		# extra arguments
		a.append("*"+code.co_varnames[n])
		n = n + 1
	if code.co_flags & CO_VARKEYWORDS:
		# extra keyword arguments
		a.append("**"+code.co_varnames[n])
		n = n + 1
	return a

def describe(func, name = None):
	"Return the function or method declaration as a string"

	# argument list
	a = _describe(func)
	args = []
	for arg in a:
		if type(arg) == type(""):
			args.append(arg)
		else:
			args.append("%s=%s" % (arg[0], repr(arg[1])))
	args = string.join(args, ", ")

	# function name
	if not name:
		name = func.func_name
		if name == "<lambda>":
			return "lambda %s" % args
	return "%s(%s)" % (name, args)

def __getmethods(c, m):
	for k, v in c.__dict__.items():
		if type(v) == type(__getmethods): # and k[0] != "_":
			if not m.has_key(k):
				m[k] = describe(v, k), c.__name__
	for c in c.__bases__:
		__getmethods(c, m)

def describe_class(cls):
	"Return a dictionary describing all methods available in a class"

	m = {}
	__getmethods(cls, m)
	return m

def describe_instance(self):
	"Return a dictionary describing all methods available in an instance"

	return describe_class(self.__class__)

#
# --------------------------------------------------------------------

if __name__ == "__main__":

	def foo(a, b=1, *c, **d):
		e = a + b + c
		f = None

	bar = lambda a: 0

	# from Duncan Booth
	# def baz(a, (b, c) = ('foo','bar'), (d, e, f), g):
	#	pass

	print describe(foo)
	print describe(bar)
	# print describe(baz)

