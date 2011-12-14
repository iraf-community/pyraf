"""Give help on variables, functions, modules, classes, IRAF tasks,
IRAF packages, etc.

- help() with no arguments will list all the defined variables.
- help("taskname") or help(IrafTaskObject) display the IRAF help for the task
- help("taskname",html=1) or help(IrafTaskObject,html=1) will direct a browser
  to display the HTML version of IRAF help for the task
- help(object) where object is a module, instance, ? will display
  information on the attributes and methods of the object (or the
  variables, functions, and classes in the module)
- help(function) will give the calling sequence for the function (except
  for built-in functions)

and so on.  There are optional keyword arguments to help that specify
what information is to be printed:

variables=1     Print info on variables/attributes
functions=1     Print info on function/method calls
modules=1       Print info on modules
tasks=0         Print info on IrafTask objects
packages=0      Print info on IrafPkg objects
hidden=0        Print info on hidden variables/attributes (starting with '_')
html=0          Use HTML help instead of standard IRAF help for tasks

regexp=None     Specify a regular expression that matches the names of
                        variables of interest.  E.g. help(sys, regexp='std') will
                        give help on all attributes of sys that start with std.
                        regexp can use all the re patterns.

The padchars keyword determines some details of the format of the output.

The **kw argument allows minimum matching for the keyword arguments
(so help(func=1) will work).

$Id$

R. White, 1999 September 23
"""
from __future__ import division # confidence high

import __main__, re, os, sys, types
from stsci.tools import minmatch, irafutils
from stsci.tools.irafglobals import IrafTask, IrafPkg
import describe, iraf

# print info on numpy arrays if numpy is available

try:
    import numpy
    _numpyArrayType = numpy.ndarray
except ImportError:
    # no numpy available, so we won't encounter arrays
    _numpyArrayType = None

_MODULE = 0
_FUNCTION = 1
_METHOD = 2
_OTHER = 3

_functionTypes = (types.BuiltinFunctionType,
                  types.FunctionType,
                  types.LambdaType)

_methodTypes = (types.BuiltinMethodType,
                types.MethodType,
                types.UnboundMethodType)

_listTypes = (list, tuple, dict)

_numericTypes = (float, int, long, complex)
if globals().has_key('bool'):
    _numericTypes = _numericTypes + (bool,)

_allSingleTypes = _functionTypes + _methodTypes + _listTypes + _numericTypes

# set up minimum-match dictionary with function keywords

kwnames = ( 'variables', 'functions', 'modules',
                'tasks', 'packages', 'hidden', 'padchars', 'regexp', 'html' )
_kwdict = minmatch.MinMatchDict()
for key in kwnames: _kwdict.add(key,key)
del kwnames, key

# additional keywords for IRAF help task

irafkwnames = ( 'file_template', 'all',
                'parameter', 'section', 'option', 'page', 'nlpp', 'lmargin',
                'rmargin', 'curpack', 'device', 'helpdb', 'mode' )
_irafkwdict = {}
for key in irafkwnames:
    _kwdict.add(key,key)
    _irafkwdict[key] = 1
del irafkwnames, key

def help(object=__main__, variables=1, functions=1, modules=1,
         tasks=0, packages=0, hidden=0, padchars=16, regexp=None, html=0,
         **kw):

    """List the type and value of all the variables in the specified object.

- help() with no arguments will list all the defined variables.
- help("taskname") or help(IrafTaskObject) displays IRAF help for the task
- help(object) where object is a module, instance, etc., will display
information on the attributes and methods of the object.
- help(function) will give the calling sequence for the function.

Optional keyword arguments specify what information is to be printed.
The keywords can be abbreviated:

variables=1 Print info on variables/attributes
functions=1 Print info on function/method calls
modules=1   Print info on modules
tasks=0     Print info on IrafTask objects
packages=0  Print info on IrafPkg objects
hidden=0    Print info on hidden variables/attributes (starting with '_')
html=0      Use HTML help instead of standard IRAF help for tasks

regexp=None Specify a regular expression that matches the names of variables of
        interest.  E.g., help(sys, regexp='std') will give help on all attr-
        ibutes of sys that start with std.  All the re patterns can be used.

Other keywords are passed on to the IRAF help task if it is called.
"""

    # handle I/O redirection keywords
    redirKW, closeFHList = iraf.redirProcess(kw)
    if kw.has_key('_save'): del kw['_save']

    # get the keywords using minimum-match
    irafkw = {}
    for key in kw.keys():
        try:
            fullkey = _kwdict[key]
            if _irafkwdict.has_key(fullkey):
                # this is an IRAF help keyword
                irafkw[fullkey] = kw[key]
            else:
                # this is a Python help function keyword
                exec fullkey + ' = ' + `kw[key]`
        except KeyError, e:
            raise e.__class__("Error in keyword "+key+"\n"+str(e))

    resetList = iraf.redirApply(redirKW)

    # try block for I/O redirection

    try:
        _help(object, variables, functions, modules,
                tasks, packages, hidden, padchars, regexp, html, irafkw)
    finally:
        rv = iraf.redirReset(resetList, closeFHList)
    return rv

def _help(object, variables, functions, modules,
                tasks, packages, hidden, padchars, regexp, html, irafkw):

    # for IrafTask object, display help and also print info on the object
    # for string parameter, if it looks like a task name try getting help
    # on it too (XXX this is a bit risky, but I suppose people will not
    # often be asking for help with simple strings as an argument...)

    if isinstance(object,IrafTask):
        if _printIrafHelp(object, html, irafkw): return

    if isinstance(object,str):
        if re.match(r'[A-Za-z_][A-Za-z0-9_.]*$',object) or \
          (re.match(r'[^\0]*$',object) and \
                    os.path.exists(iraf.Expand(object, noerror=1))):
            if _printIrafHelp(object, html, irafkw): return

    vlist = None
    if not isinstance(object, _allSingleTypes):
        try:
            vlist = vars(object)
        except TypeError:
            pass
    if vlist is None:
        # simple object with no vars()
        _valueHelp(object, padchars)
        return

    # look inside the object

    tasklist, pkglist, functionlist, methodlist, modulelist, otherlist = \
            _getContents(vlist, regexp, object)

    if isinstance(object, types.InstanceType):
        # for instances, print a help line for the object itself first
        _valueHelp(object, padchars=0)

    if modules and modulelist:
        # modules get listed in simple column format
        print "Modules:"
        irafutils.printCols(map(lambda x: x[0], modulelist))
        print

    if functions and functionlist:
        _printValueList(functionlist, hidden, padchars)

    if functions and methodlist:
        _printValueList(methodlist, hidden, padchars)

    if variables and otherlist:
        _printValueList(otherlist, hidden, padchars)

    # IRAF packages and tasks get listed in simple column format
    if packages and pkglist:
        print "IRAF Packages:"
        irafutils.printCols(pkglist)
        print

    if tasks and tasklist:
        print "IRAF Tasks:"
        irafutils.printCols(tasklist)
        print

    if isinstance(object, types.InstanceType) and functions:
        # for instances, call recursively to list class methods
        help(object.__class__, functions=functions, tasks=tasks,
                packages=packages, variables=variables, hidden=hidden,
                padchars=padchars, regexp=regexp)

#------------------------------------
# helper functions
#------------------------------------

# return 1 if they handle the object, 0 if they don't

def _printIrafHelp(object, html, irafkw):
    if html:
        _htmlHelp(object)
        return 0
    else:
        return _irafHelp(object, irafkw)

def _valueHelp(object, padchars):
    # just print info on the object itself
    vstr = _valueString(object,verbose=1)
    try:
        name = object.__name__
    except AttributeError:
        name = ''
    name = name + (padchars-len(name))*" "
    if name and len(name.strip()) > 0:
        print name, ":", vstr
    else:
        # omit the colon if name is null
        print vstr

def _getContents(vlist, regexp, object):
    # Make one pass through names getting the type and sort order
    # Also split IrafTask and IrafPkg objects into separate lists and
    #  look into base classes if object is a class.
    # Returns lists of various types of included objects
    if regexp: re_check = re.compile(regexp)
    tasklist = []
    pkglist = []
    # lists for functions, modules, other types
    functionlist = []
    methodlist = []
    modulelist = []
    otherlist = []
    sortlist = 4*[None]
    sortlist[_FUNCTION] = functionlist
    sortlist[_METHOD] = methodlist
    sortlist[_MODULE] = modulelist
    sortlist[_OTHER] = otherlist
    namedict = {}
    names = vlist.keys()
    for vname in names:
        if (regexp is None) or re_check.match(vname):
            value = vlist[vname]
            if isinstance(value,IrafPkg):
                pkglist.append(vname + '/')
            elif isinstance(value,IrafTask):
                tasklist.append(vname)
            else:
                vorder = _sortOrder(type(value))
                sortlist[vorder].append((vname,value))
                namedict[vname] = 1
    # add methods from base classes if this is a class
    if isinstance(object, types.ClassType):
        classlist = list(object.__bases__)
        for c in classlist:
            classlist.extend(list(c.__bases__))
            for vname, value in vars(c).items():
                if not namedict.has_key(vname) and \
                  ((regexp is None) or re_check.match(vname)):
                    vorder = _sortOrder(type(value))
                    sortlist[vorder].append((vname,value))
                    namedict[vname] = 1
    # sort into alphabetical order by name
    tasklist.sort()
    pkglist.sort()
    functionlist.sort()
    methodlist.sort()
    modulelist.sort()
    otherlist.sort()
    return tasklist, pkglist, functionlist, methodlist, modulelist, otherlist

def _printValueList(varlist, hidden, padchars):
    # special hidden methods to keep (because they are widely useful)
    _specialHidden = ['__init__', '__call__']
    for vname, value in varlist:
        if (hidden or vname[0:1] != '_' or vname in _specialHidden):
            vstr = _valueString(value)
            # pad name to padchars chars if shorter
            if len(vname) < padchars:
                vname = vname + (padchars-len(vname))*" "
            print vname, ":", vstr



def _sortOrder(type):
    if issubclass(type, types.ModuleType):
        v = _MODULE
    elif issubclass(type, _functionTypes):
        v = _FUNCTION
    elif issubclass(type, _methodTypes):
        v = _METHOD
    else:
        v = _OTHER
    return v

def _valueString(value,verbose=0):
    """Returns name and, for some types, value of the variable as a string."""

    t = type(value)
    vstr = t.__name__
    if issubclass(t, str):
        if len(value)>42:
            vstr = vstr + ", value = "+ `value[:39]` + '...'
        else:
            vstr = vstr + ", value = "+ `value`
    elif issubclass(t, _listTypes):
        return "%s [%d entries]" % (vstr, len(value))
    elif issubclass(t, file):
        vstr = vstr + ", "+ `value`
    elif issubclass(t, _numericTypes):
        vstr = vstr + ", value = "+ `value`
    elif issubclass(t, types.InstanceType):
        cls = value.__class__
        if cls.__module__ == '__main__':
            vstr = 'instance of class ' + cls.__name__
        else:
            vstr = 'instance of class ' + cls.__module__ + '.' + cls.__name__
    elif issubclass(t, _functionTypes+_methodTypes):
        # try using Fredrik Lundh's describe on functions
        try:
            vstr = vstr + ' ' + describe.describe(value)
            try:
                if verbose and value.__doc__:
                    vstr = vstr + "\n" + value.__doc__
            except AttributeError:
                pass
        except (AttributeError, TypeError):
            # oh well, just have to live with type string alone
            pass
    elif issubclass(t, _numpyArrayType):
        vstr = vstr + " " + str(value.dtype) + "["
        for k in range(len(value.shape)):
            if k:
                vstr = vstr + "," + `value.shape[k]`
            else:
                vstr = vstr + `value.shape[k]`
        vstr = vstr + "]"
    else:
        # default -- just return the type
        pass
    return vstr


def _irafHelp(taskname, irafkw):
    """Display IRAF help for given task.
    Task can be either a name or an IrafTask object.
    Returns 1 on success or 0 on failure."""

    if isinstance(taskname,IrafTask):
        taskname = taskname.getName()
    else:
        # expand IRAF variables in case this is name of a help file
        taskname = iraf.Expand(taskname,noerror=1)
    try:
        if not irafkw.has_key('page'): irafkw['page'] = 1
        apply(iraf.system.help, (taskname,), irafkw)
        return 1
    except iraf.IrafError, e:
        print str(e)
        return 0

_HelpURL = "http://stsdas.stsci.edu/cgi-bin/gethelp.cgi?task="
_Browser = "netscape"

def _htmlHelp(taskname):
    """Display HTML help for given IRAF task in a browser.
    Task can be either a name or an IrafTask object. """

    if isinstance(taskname,IrafTask):
        taskname = taskname.getName()
    url = _HelpURL + taskname

    irafutils.launchBrowser(url, brow_bin=_Browser, subj=taskname)
