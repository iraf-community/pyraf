# http://www.dejanews.com/getdoc.xp?AN=382948703
#
# Instant Python
#
# utilities to describe functions, methods, and classes
#
# history:
# 96-10-27 fl     created
# 98-02-24 fl     added code to handle unpacked arguments
# 01-11-13 rlw    added UNPACK_SEQUENCE to UNPACK_TUPLE for tuple args
#                 (Changed for Python2.0)
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



from dis import opname, HAVE_ARGUMENT

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


def describeParams(func, name=None):
    # get argument list

    code = func.__code__

    n = code.co_argcount
    a = list(code.co_varnames[:n])
    p = 0
    for i in range(n):
        # anonymous arguments
        c = code.co_code
        if not a[i] or a[i][0] == ".":
            vars = []
            while p < len(c):
                v = ord(c[p])
                if v >= HAVE_ARGUMENT:
                    s, v = opname[v], ord(c[p + 1]) + ord(c[p + 2]) * 256
                    p = p + 3
                    if s in ("UNPACK_SEQUENCE", "UNPACK_TUPLE"):
                        count = v
                    elif s == "STORE_FAST":
                        vars.append(code.co_varnames[v])
                        if len(vars) >= count:
                            break
                else:
                    p = p + 1
            if vars:
                a[i] = "(" + ", ".join(vars) + ")"
    if func.__defaults__:
        # defaults
        i = n - len(func.__defaults__)
        for d in func.__defaults__:
            a[i] = (a[i], d)
            i = i + 1
    if code.co_flags & CO_VARARGS:
        # extra arguments
        a.append("*" + code.co_varnames[n])
        n = n + 1
    if code.co_flags & CO_VARKEYWORDS:
        # extra keyword arguments
        a.append("**" + code.co_varnames[n])
        n = n + 1
    return a


def describe(func, name=None):
    "Return the function or method declaration as a string"

    # argument list
    a = describeParams(func)
    args = []
    for arg in a:
        if isinstance(arg, str):
            args.append(arg)
        else:
            args.append(f"{arg[0]}={repr(arg[1])}")
    args = ", ".join(args)

    # function name
    if not name:
        # func_name is considered obsolete, use __name__ instead
        # name = func.func_name
        name = func.__name__
        if name == "<lambda>":
            return f"lambda {args}"
    return f"{name}({args})"


def __getmethods(c, m):
    for k, v in c.__dict__.items():
        if isinstance(v, type(__getmethods)):  # and k[0] != "_":
            if k not in m:
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
