"""cl2py.py: Translate IRAF CL program to Python

R. White, 1999 December 20
"""


import io
import os
import sys

from .generic import GenericASTTraversal
from .clast import AST
from .cltoken import Token
from . import clscan
from . import clparse
from .clcache import codeCache

from stsci.tools.irafglobals import Verbose
from stsci.tools import basicpar, minmatch, irafutils
from . import irafpar
from . import pyrafglobals

# The parser object can be constructed once and used many times.
# The other classes have instance variables (e.g. lineno in CLScanner),
# so using a single instance could screw up if several threads are trying
# to use the same object.
#
# I handled this in the CLScanner class by creating cached versions
# of the various scanners that are stateless.

_parser = None


def cl2py(filename=None,
          string=None,
          parlist=None,
          parfile="",
          mode="proc",
          local_vars_dict=None,
          local_vars_list=None,
          usecache=True):
    """Read CL program from file and return pycode object with Python equivalent

    filename: Name of the CL source file or a filehandle from which the
            source code can be read.
    string: String containing the source code.  Either filename or string must be
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
    usecache: Set to false value to omit use of code cache for either saving
            or retrieving code.  This is useful mainly for compiler testing.
    """

    global _parser, codeCache

    if _parser is None:
        _parser = clparse.getParser()

    if mode not in ["proc", "single"]:
        raise ValueError(f"Mode = `{mode}', must be `proc' or `single'")

    if filename not in (None, ''):
        if isinstance(filename, str):
            efilename = os.path.expanduser(filename)
            if usecache:
                index, pycode = codeCache.get(efilename, mode=mode)
                if pycode is not None:
                    if Verbose > 1:
                        print(efilename, "filename found in CL script cache")
                    return pycode
            else:
                index = None
            fh = open(efilename)
            clInput = fh.read()
            fh.close()
        elif hasattr(filename, 'read'):
            clInput = filename.read()
            if usecache:
                index, pycode = codeCache.get(filename,
                                              mode=mode,
                                              source=clInput)
                if pycode is not None:
                    if Verbose > 1:
                        print(filename, "filehandle found in CL script cache")
                    return pycode
            else:
                index = None
            if hasattr(filename, 'name'):
                efilename = filename.name
            else:
                efilename = ''
        else:
            raise TypeError('filename must be a string or a filehandle')
    elif string is not None:
        # if not isinstance(string,str):
        # raise TypeError('string must be a string')
        clInput = string
        efilename = 'string_proc'  # revisit this setting (tik #24), maybe '' ?
        if usecache:
            index, pycode = codeCache.get(None, mode=mode, source=clInput)
            if pycode is not None:
                if Verbose > 3:
                    print("Found in CL script cache: ", clInput.strip()[:20])
                return pycode
        else:
            index = None
    else:
        raise ValueError('Either filename or string must be specified')

    if mode == "single":
        taskObj = 'cl'
    else:
        taskObj = None

    # tokenize and parse to create the abstract syntax tree
    scanner = clscan.CLScanner()
    tokens = scanner.tokenize(clInput)
    tree = _parser.parse(tokens, fname=efilename)
    # add filename to tree root
    tree.filename = efilename

    # first pass -- get variables
    vars = VarList(tree, mode, local_vars_list, local_vars_dict, parlist)

    # check variable list for consistency with the given parlist
    # this may change the vars list
    _checkVars(vars, parlist, parfile)

    # second pass -- check all expression types
    # type info is added to tree
    TypeCheck(tree, vars, efilename)

    # third pass -- generate python code
    tree2python = Tree2Python(tree, vars, efilename, taskObj)

    # just keep the relevant fields of Tree2Python output
    # attach tokens to the code object too
    pycode = Pycode(tree2python)

    # add to cache
    if index is not None:
        codeCache.add(index, pycode)
    pycode.index = index
    if Verbose > 1:
        if efilename == 'string_proc':
            print("Code-string compiled by cl2py:", file=sys.stderr)
            print("-" * 80, file=sys.stderr)
            print(clInput, file=sys.stderr)
            print("-" * 80, file=sys.stderr)
        else:
            print("Code-file compiled by cl2py:" + efilename, file=sys.stderr)
    return pycode


def checkCache(filename, pycode):
    """Returns true if pycode is up-to-date"""

    global codeCache
    if pycode is None:
        return 0
    index = codeCache.getIndex(filename)
    return (index is not None) and (pycode.index == index)


class Container:
    """Simple container class (no methods) for holding picklable objects"""

    pass


class Pycode:
    """Container for Python CL translation"""

    def __init__(self, tree2python):

        self.code = tree2python.code
        self.vars = Container()
        self.vars.local_vars_dict = tree2python.vars.local_vars_dict
        self.vars.local_vars_list = tree2python.vars.local_vars_list
        self.vars.parList = tree2python.vars.parList
        self.vars.proc_name = tree2python.vars.proc_name
        self.vars.has_proc_stmt = tree2python.vars.has_proc_stmt

    def setFilename(self, filename):
        """Set the filename used for parameter list

        This is used by codeCache, which needs to be able to read a Pycode
        object created from some other file and attach it to the current file.
        """

        self.vars.parList.setFilename(filename)


def _checkVars(vars, parlist, parfile):
    """Check variable list for consistency with the given parlist"""

    # if there is no parfile specified, the parlist was created by default
    # if parlist is None, the parfile was empty
    # in either case, just use the parameter list specified in the CL code

    if (not parfile) or (parlist is None):
        return

    # parfile and parlist are specified, so create a new
    # list of procedure variables from parlist

    # check for consistency with the CL code if there was a procedure stmt
    if vars.has_proc_stmt and not parlist.isConsistent(vars.parList):
        # note we continue even if parameter lists are inconsistent.
        # That agrees with IRAF's approach, in which the .par file
        # overrides the CL script in determining parameters...
        # XXX Maybe could improve this by allowing certain types of
        # XXX mismatches (e.g. additional parameters) but not others
        # XXX (name or type disagreements for the same parameters.)
        if Verbose > 0:
            sys.stdout.flush()
            sys.stderr.write("Parameters from CL code inconsistent with "
                             f".par file for task {vars.getProcName()}\n")
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


class FindLineNumber(GenericASTTraversal):
    """Helper class to find first line number in an AST"""

    class FoundIt(Exception):
        pass

    def __init__(self, ast):
        GenericASTTraversal.__init__(self, ast)
        self.lineno = 0
        try:
            self.preorder()
        except self.FoundIt:
            pass

    def default(self, node):
        if hasattr(node, 'lineno'):
            self.lineno = node.lineno
            raise self.FoundIt


class ErrorTracker:
    """Mixin class that does error tracking during AST traversal"""

    def _error_init(self):
        self.errlist = []  # list of 2-tuples
        self.warnlist = []  # list of 2-tuples
        self.comments = []  # list of strings

    def error(self, msg, node=None):
        """Add error to the list with line number"""

        if not hasattr(self, 'errlist'):
            self._error_init()
        self.errlist.append((self.getlineno(node), msg))

    def warning(self, msg, node=None):
        """Add warning to the list with line number"""

        if not hasattr(self, 'errlist'):
            self._error_init()
        self.warnlist.append((self.getlineno(node), f"Warning: {msg}"))

    def comment(self, msg):
        """Add comments to the list - to be helpful to the debugging soul"""

        if not hasattr(self, 'errlist'):
            self._error_init()
        self.comments.append(msg)

    def getlineno(self, node):
        # find terminal token that contains the line number
        if node:
            return FindLineNumber(node).lineno
        else:
            return 0

    def errorappend(self, other):
        """Add errors from another ErrorTracker"""

        if not hasattr(other, 'errlist'):
            return
        if not hasattr(self, 'errlist'):
            self._error_init()
        self.errlist.extend(other.errlist)
        self.warnlist.extend(other.warnlist)
        self.comments.extend(other.comments)

    def printerrors(self):
        """Print all warnings and errors and raise SyntaxError if errors were found"""

        if not hasattr(self, 'errlist'):
            return
        if self.errlist:
            self.errlist.extend(self.warnlist)
            self.errlist.sort()
            try:
                errmsg = [f"Error in CL script {self.filename}"]
            except AttributeError:
                errmsg = ["Error in CL script"]
            for lineno, msg in self.errlist:
                if lineno:
                    errmsg.append(f"{msg} (line {lineno:d})")
                else:
                    errmsg.append(msg)
            for comment in self.comments:
                errmsg.append(comment)
            raise SyntaxError("\n".join(errmsg))
        elif self.warnlist:
            self.warnlist.sort()
            try:
                warnmsg = [f"Warning in CL script {self.filename}"]
            except AttributeError:
                warnmsg = ["Warning in CL script"]
            for lineno, msg in self.warnlist:
                if lineno:
                    warnmsg.append(f"{msg} (line {lineno:d})")
                else:
                    warnmsg.append(msg)
            for comment in self.comments:
                warnmsg.append(comment)
            warnmsg = "\n".join(warnmsg)
            sys.stdout.flush()
            sys.stderr.write(warnmsg)
            if warnmsg[-1:] != '\n':
                sys.stderr.write('\n')


class ExtractProcInfo(GenericASTTraversal):
    """Extract name and args from procedure statement"""

    def __init__(self, ast):
        GenericASTTraversal.__init__(self, ast)
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

    def __init__(self,
                 name=None,
                 type=None,
                 mode="h",
                 array_size=None,
                 init_value=None,
                 list_flag=0,
                 min=None,
                 max=None,
                 prompt=None,
                 enum=None,
                 irafParObject=None):
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
            if isinstance(ipo, basicpar.IrafArrayPar):
                self.shape = ipo.shape
            else:
                self.shape = None
            self.init_value = ipo.value
            self.options = minmatch.MinMatchDict({
                "mode": ipo.mode,
                "min": ipo.min,
                "max": ipo.max,
                "prompt": ipo.prompt,
                "enum": ipo.choice,
                "length": None,
            })
        else:
            # define from the parameters
            self.name = name
            self.type = type
            self.shape = array_size
            self.list_flag = list_flag
            self.options = minmatch.MinMatchDict({
                "mode": mode,
                "min": min,
                "max": max,
                "prompt": prompt,
                "enum": enum,
                "length": None,
            })
            self.init_value = init_value

    def getName(self):
        """Get name without translations"""
        return irafutils.untranslateName(self.name)

    def toPar(self, strict=0):
        """Convert this variable to an IrafPar object"""
        return irafpar.makeIrafPar(self.init_value,
                                   datatype=self.type,
                                   name=self.getName(),
                                   array_size=self.shape,
                                   list_flag=self.list_flag,
                                   mode=self.options["mode"],
                                   min=self.options["min"],
                                   max=self.options["max"],
                                   enum=self.options["enum"],
                                   prompt=self.options["prompt"],
                                   strict=strict)

    def procLine(self):
        """Return a string usable as parameter declaration with
        default value in the function definition statement"""

        name = irafutils.translateName(self.name)
        if self.shape is None:
            if self.init_value is None:
                return name + "=None"
            else:
                return name + "=" + repr(self.init_value)
        else:
            # array
            arg = name + "=["
            if self.init_value is None:
                arglist = ["INDEF"] * len(self)
            else:
                arglist = []
                for iv in self.init_value:
                    arglist.append(repr(iv))
            return arg + ", ".join(arglist) + "]"

    def parDefLine(self, filename=None, strict=0, local=0):
        """Return a list of string arguments for makeIrafPar"""

        name = irafutils.translateName(self.name)
        arglist = [
            name, "datatype=" + repr(self.type), "name=" + repr(self.getName())
        ]
        # if local is set, use the default initial value instead of name
        # also set mode="u" for locals so they never prompt
        if local:
            arglist[0] = repr(self.init_value)
            self.options["mode"] = "u"
        if self.shape is not None:
            arglist.append("array_size=" + repr(self.shape))
        if self.list_flag:
            arglist.append("list_flag=" + repr(self.list_flag))
        keylist = sorted(self.options.keys())
        for key in keylist:
            option = self.options[key]
            if option is not None:
                arglist.append(key + "=" + repr(self.options[key]))
        if filename:
            arglist.append("filename=" + repr(filename))
        if strict:
            arglist.append("strict=" + repr(strict))
        return arglist

    def __repr__(self):
        s = self.type + " "
        if self.list_flag:
            s = s + "*"
        s = s + self.name
        if self.init_value is not None:
            s = s + " = " + repr(self.init_value)
        optstring = "{"
        for key, value in self.options.items():
            if (value is not None) and (key != "mode" or value != "h"):
                # optstring = optstring + " " + key + "=" + str(value)
                optstring = optstring + " " + key + "=" + str(value)
        if len(optstring) > 1:
            s = s + " " + optstring + " }"
        return s

    def __len__(self):
        array_size = 1
        if self.shape:
            for d in self.shape:
                array_size = array_size * d
        return array_size


class ExtractDeclInfo(GenericASTTraversal, ErrorTracker):
    """Extract list of variable definitions from parameter block"""

    def __init__(self, ast, var_list, var_dict, filename):
        GenericASTTraversal.__init__(self, ast)
        self.var_list = var_list
        self.var_dict = var_dict
        self.filename = filename
        self.preorder()
        self.printerrors()

    def n_declaration_stmt(self, node):
        self.current_type = node[0].attr

    def _get_dims(self, node, rv=None):
        # expand array shape declaration
        if len(node) > 1:
            return self._get_dims(node[0]) + (int(node[2]),)
        else:
            return (int(node[0]),)

    def n_decl_spec(self, node):
        var_name = node[1]
        name = irafutils.translateName(var_name[0].attr)
        if len(var_name) > 1:
            # array declaration
            shape = tuple(self._get_dims(var_name[2]))
        else:
            # apparently not an array (but this may change later
            # if multiple initial values are found)
            shape = None
        if name in self.var_dict:
            if self.var_dict[name]:
                self.error(f"Variable `{name}' is multiply declared",
                           node)
                self.prune()
            else:
                # existing but undefined entry comes from procedure line
                # set mode = "a" by default
                self.var_dict[name] = Variable(name,
                                               self.current_type,
                                               array_size=shape,
                                               mode="a")
        else:
            self.var_list.append(name)
            self.var_dict[name] = Variable(name,
                                           self.current_type,
                                           array_size=shape)
        self.current_var = self.var_dict[name]
        self.preorder(node[0])  # list flag
        self.preorder(node[2])  # initialization
        self.preorder(node[3])  # declaration options
        self.prune()

    def n_list_flag(self, node):
        if len(node) > 0:
            self.current_var.list_flag = 1
        self.prune()

    def n_decl_init_list(self, node):
        # begin list of initial values
        if self.current_var.init_value is not None:
            # oops, looks like this was already initialized
            errmsg = (f"{self.filename}: Variable `{self.current_var.name}' "
                      "has more than one set of initial values")
            self.error(errmsg, node)
        else:
            self.current_var.init_value = []

    def n_decl_init_list_exit(self, node):
        # convert from list to scalar if not an array
        # also convert all the initial values from tokens to native form
        v = self.current_var
        ilist = v.init_value
        if len(ilist) == 1 and v.shape is None:
            try:
                v.init_value = _convFunc(v, ilist[0])
            except ValueError as e:
                self.error(
                    f"Bad initial value for variable `{v.name}': {e}",
                    node)
        else:
            # it is an array, set size or pad initial values
            if v.shape is None:
                v.shape = (len(ilist),)
            elif len(v) > len(ilist):
                for i in range(len(v) - len(ilist)):
                    v.init_value.append(None)
            elif len(v) < len(ilist):
                self.error(
                    f"Variable `{v.name}' has too many initial values",
                    node)
            else:
                try:
                    for i in range(len(v.init_value)):
                        v.init_value[i] = _convFunc(v, v.init_value[i])
                except ValueError as e:
                    self.error(
                        f"Bad initial value for array variable `{v.name}': {e}",
                        node)

    def n_decl_init_value(self, node):
        # initial value is token with value
        vnode = node[0]
        if isinstance(vnode, Token):
            self.current_var.init_value.append(vnode)
        else:
            # have to create a new token for sign, number
            self.current_var.init_value.append(
                Token(type=vnode[1].type,
                      attr=vnode[0].type + vnode[1].attr,
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
                optvalue = -vnode[1].get()
            else:
                optvalue = vnode[1].get()
        optdict = self.current_var.options
        if optname not in optdict:
            errmsg = (f"Unknown option `{optname}' "
                      f"for variable `{self.current_var.name}'")
            self.error(errmsg, node)
        else:
            optdict[optname] = optvalue
        self.prune()


# special keyword arguments added to parameter list

_SpecialArgs = {
    'taskObj': None,
}


class VarList(GenericASTTraversal, ErrorTracker):
    """Scan tree and get info on procedure, parameters, and local variables"""

    def __init__(self,
                 ast,
                 mode="proc",
                 local_vars_list=None,
                 local_vars_dict=None,
                 parlist=None):
        GenericASTTraversal.__init__(self, ast)
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
        self.input_parlist = parlist
        self.preorder()
        del self.input_parlist

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

        self.printerrors()

        # convert procedure arguments to IrafParList
        p = []
        for var in self.proc_args_list:
            if var not in _SpecialArgs:
                arg = self.proc_args_dict[var].toPar()
                p.append(arg)
        self.parList = irafpar.IrafParList(self.getProcName(),
                                           filename=self.filename,
                                           parlist=p)

    def has_key(self, key):
        return self._has(key)

    def __contains__(self, key):
        return self._has(key)

    def _has(self, name):
        """Check both local and procedure dictionaries for this name"""
        return name in self.proc_args_dict or name in self.local_vars_dict

    def get(self, name):
        """Return entry from local or procedure dictionary (None if none)"""
        return self.proc_args_dict.get(name) or self.local_vars_dict.get(name)

    def setProcName(self, proc_name, node=None):
        """Set procedure name"""
        # names with embedded dots are allow by the CL but should be illegal
        pdot = proc_name.find('.')
        if pdot == 0:
            self.error(f"Illegal procedure name `{proc_name}' starts with `.'",
                       node)
        if pdot >= 0:
            self.warning(f"Bad procedure name `{proc_name}' "
                         f"truncated after dot to `{proc_name[:pdot]}'",
                         node)
            proc_name = proc_name[:pdot]
        # Procedure name is stored in translated form ('PY' added
        # to Python keywords, etc.)
        self.proc_name = irafutils.translateName(proc_name)

    def getProcName(self):
        """Get procedure name, undoing translations"""
        return irafutils.untranslateName(self.proc_name)

    def addSpecial(self, name, type, value):
        # just delete $nargs and add it back if it is already present
        if name in self.proc_args_dict:
            self.proc_args_list.remove(name)
            del self.proc_args_dict[name]

        targ = irafutils.translateName(name)
        if targ not in self.proc_args_dict:
            self.proc_args_list.append(targ)
            self.proc_args_dict[targ] = Variable(targ, type, init_value=value)

    def addSpecialArgs(self):
        """Add mode, $nargs, other special parameters to all tasks"""

        if 'mode' not in self.proc_args_dict:
            self.proc_args_list.append('mode')
            self.proc_args_dict['mode'] = Variable('mode',
                                                   'string',
                                                   init_value='al')

        self.addSpecial("$nargs", 'int', 0)

        ##         self.addSpecial("$errno", 'int', 0)
        ##         self.addSpecial("$errmsg", 'string', "")
        ##         self.addSpecial("$errtask", 'string',"")
        ##         self.addSpecial("$err_dzvalue", 'int', 1)

        for parg, ivalue in _SpecialArgs.items():
            if parg not in self.proc_args_dict:
                self.proc_args_list.append(parg)
                self.proc_args_dict[parg] = ivalue

    def checkLocalConflict(self):
        """Check for local variables that conflict with parameters"""

        errlist = [f"Error in procedure `{self.getProcName()}'"]
        for v in self.local_vars_list:
            if v in self.proc_args_dict:
                errlist.append(f"Local variable `{v}' "
                               "overrides parameter of same name")
        if len(errlist) > 1:
            self.error("\n".join(errlist))

    def list(self):
        """List variables"""
        print("Procedure arguments:")
        for var in self.proc_args_list:
            v = self.proc_args_dict[var]
            if var in _SpecialArgs:
                print('Special', var, '=', v)
            else:
                print(v)
        print("Local variables:")
        for var in self.local_vars_list:
            print(self.local_vars_dict[var])

    def getParList(self):
        """Return procedure arguments as IrafParList"""
        return self.parList

    def n_proc_stmt(self, node):
        self.has_proc_stmt = 1
        # get procedure name and list of argument names
        p = ExtractProcInfo(node)
        self.setProcName(p.proc_name, node)
        self.proc_args_list = p.proc_args_list
        for arg in self.proc_args_list:
            if arg in self.proc_args_dict:
                errmsg = (f"Argument `{arg}' repeated "
                          f"in procedure statement {self.getProcName()}")
                self.error(errmsg, node)
            else:
                self.proc_args_dict[arg] = None
        self.prune()

    def n_param_declaration_block(self, node):
        # get list of parameter variables
        ExtractDeclInfo(node, self.proc_args_list, self.proc_args_dict,
                        self.ast.filename)
        # check for undefined parameters declared in procedure stmt
        d = self.proc_args_dict
        for arg in d.keys():
            if not d[arg]:
                # try substituting from parlist parameter list
                d[arg] = self.getFromInputList(arg)
                if not d[arg]:
                    errmsg = f"Procedure argument `{arg}' is not declared"
                    self.error(errmsg, node)
        self.prune()

    def getFromInputList(self, param):
        # look up missing parameter in input_parlist
        if self.input_parlist and self.input_parlist.hasPar(param):
            return Variable(
                irafParObject=self.input_parlist.getParObject(param))

    def n_statement_block(self, node):
        # declarations in executable section are local variables
        ExtractDeclInfo(node, self.local_vars_list, self.local_vars_dict,
                        self.ast.filename)
        self.prune()


# conversion between parameter types and data types

_typeDict = {
    'int': 'int',
    'real': 'float',
    'double': 'float',
    'bool': 'bool',
    'string': 'string',
    'char': 'string',
    'struct': 'string',
    'file': 'string',
    'gcur': 'string',
    'imcur': 'string',
    'ukey': 'string',
    'pset': 'unknown',
}

# nested dictionary mapping required data type (primary key) and
# expression type (secondary key) to the name of the function used to
# convert to the required type

_rfuncDict = {
    'int': {
        'int': None,
        'float': None,
        'string': 'int',
        'bool': None,
        'unknown': 'int',
        'indef': None
    },
    'float': {
        'int': None,
        'float': None,
        'string': 'float',
        'bool': 'float',
        'unknown': 'float',
        'indef': None
    },
    'string': {
        'int': 'str',
        'float': 'str',
        'string': None,
        'bool': 'iraf.bool2str',
        'unknown': 'str',
        'indef': None
    },
    'bool': {
        'int': 'iraf.boolean',
        'float': 'iraf.boolean',
        'string': 'iraf.boolean',
        'bool': None,
        'unknown': 'iraf.boolean',
        'indef': None
    },
    'indef': {
        'int': None,
        'float': None,
        'string': None,
        'bool': None,
        'unknown': None,
        'indef': None
    },
    'unknown': {
        'int': None,
        'float': None,
        'string': None,
        'bool': None,
        'unknown': None,
        'indef': None
    },
}


def _funcName(requireType, exprType):
    return _rfuncDict[requireType][exprType]


# given two nodes with defined types in an arithmetic expression,
# set their required times and return the result type
# (using standard promotion rules)

_numberTypes = ['float', 'int', 'unknown']


def _arithType(node1, node2):
    if node1.exprType in _numberTypes:
        if node2.exprType not in _numberTypes:
            rv = node1.exprType
            node2.requireType = rv
        else:
            # both numbers -- don't change required types, but
            # determine result type
            if 'float' in [node1.exprType, node2.exprType]:
                rv = 'float'
            elif 'unknown' in [node1.exprType, node2.exprType]:
                rv = 'unknown'
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


_CLVarDict = {}


def _getCLVarType(name):
    """Returns CL parameter data type if this is a CL variable, "unknown" if not

    Note that this can be incorrect about the data type for CL variables
    that are masked by package level variables.  Too bad, that is just
    too ugly to be believed anyway.  Don't do that.
    """
    global _CLVarDict
    try:
        if not _CLVarDict:
            from . import iraf
            d = iraf.cl.getParDict()
            # construct type dictionary for all variables
            # don't use minimum matching -- require exact match
            for pname, pobj in d.items():
                iraftype = pobj.type
                if iraftype[:1] == "*":
                    iraftype = iraftype[1:]
                _CLVarDict[pname] = _typeDict[_longTypeName[iraftype]]
    except AttributeError:
        pass
    return _CLVarDict.get(name, "unknown")


class TypeCheck(GenericASTTraversal):
    """Determine types of all expressions"""

    def __init__(self, ast, vars, filename):
        GenericASTTraversal.__init__(self, ast)
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
        v = self.vars.get(s)
        if v is not None:
            node.exprType = _typeDict[v.type]
            node.requireType = node.exprType
        else:
            # not a local variable
            # try CL as a common case
            node.exprType = _getCLVarType(node.attr)
            node.requireType = node.exprType

    def n_array_ref(self, node):
        node.exprType = node[0].exprType
        node.requireType = node.exprType

    def n_function_call(self, node):
        functionname = node[0].attr
        ftype = _functionType.get(functionname)
        if ftype is None:
            ftype = 'unknown'
        node.exprType = ftype
        node.requireType = node.exprType

    def n_atom(self, node):
        assert len(node) == 3
        node.exprType = node[1].exprType
        node.requireType = node.exprType

    def n_power(self, node):
        assert len(node) == 3
        node.exprType = _arithType(node[0], node[2])
        node.requireType = node.exprType

    def n_factor(self, node):
        assert len(node) == 2
        node.exprType = _numberType(node[1])
        node.requireType = node.exprType

    def n_term(self, node):
        assert len(node) == 3
        node.exprType = _arithType(node[0], node[2])
        node.requireType = node.exprType
        if node[0].exprType=='int' and node[2].exprType=='int' and \
           node[1].type=='/':
            # mark this node, we want it to use integer division (truncating)
            node[1].trunc_int_div = True  # only place we add this attr

    def n_concat_expr(self, node):
        assert len(node) == 3
        node.exprType = 'string'
        node.requireType = node.exprType
        node[0].requireType = 'string'
        node[2].requireType = 'string'

    def n_arith_expr(self, node):
        assert len(node) == 3
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


class BlockInfo:
    """Helper class to store block structure info for GOTO analysis"""

    def __init__(self, node, blockid, parent):
        self.node = node
        self.blockid = blockid
        self.parent = parent


class GoToAnalyze(GenericASTTraversal, ErrorTracker):
    """AST traversal for CL GOTO analysis

    Analyze GOTO structure looking for branches into blocks (which are forbidden),
    backward branches (which are not supported), and other errors.  Adds information
    to the AST that is used to generate Python equivalent code.
    """

    def __init__(self, ast):
        GenericASTTraversal.__init__(self, ast)
        self.blocks = []
        self.label_blockid = {}
        self.goto_blockidlist = {}
        self.goto_nodelist = {}
        self.current_blockid = -1

        # walk the tree
        self.preorder()

        # check for missing labels
        for label in self.goto_blockidlist.keys():
            if label not in self.label_blockid:
                node = self.goto_nodelist[label][0]
                self.error(f"GOTO refers to unknown label `{label}'",
                           node)

        # note that we count on the Tree2Python class to print errors

        # add label count info to blocks if all is OK
        label_count = [0] * len(self.blocks)
        for label, ib in self.label_blockid.items():
            # only count labels that are actually used
            if label in self.goto_blockidlist:
                label_count[ib] += 1
        for ib in range(len(self.blocks)):
            self.blocks[ib].node.label_count = label_count[ib]

    # -------------------------
    # public interface methods
    # -------------------------

    def labels(self):
        """Get a list of known labels used in GOTOs"""
        labels = sorted(self.goto_blockidlist.keys())
        return labels

    def __contains__(self, key):
        return self._has(key)

    def has_key(self, key):
        return self._has(key)

    def _has(self, label):
        """Check if label is used in a GOTO"""
        return label in self.goto_blockidlist

    # ------------------------------------
    # methods called during AST traversal
    # ------------------------------------

    def n_compound_stmt(self, node):
        newid = len(self.blocks)
        self.blocks.append(BlockInfo(node, newid, self.current_blockid))
        self.current_blockid = newid

    def n_statement_block(self, node):
        newid = len(self.blocks)
        self.blocks.append(BlockInfo(node, newid, self.current_blockid))
        self.current_blockid = newid

    def n_compound_stmt_exit(self, node):
        self.current_blockid = self.blocks[self.current_blockid].parent

    def n_statement_block_exit(self, node):
        self.current_blockid = self.blocks[self.current_blockid].parent

    def n_label_stmt(self, node):
        label = node[0].attr
        if label in self.label_blockid:
            self.error(f"Duplicate statement label `{label}'", node)
        else:
            cblockid = self.current_blockid
            self.label_blockid[label] = cblockid
            # make sure all gotos for this label are in this or deeper blocks
            for i in self.goto_blockidlist.get(label, []):
                if self.blocks[i].blockid < cblockid:
                    self.error(
                        f"GOTO branches to label `{label}' in inner block",
                        node)

    def n_goto_stmt(self, node):
        label = str(node[1])
        if label in self.label_blockid:
            self.error(f"Backwards GOTO to label `{label}' is not allowed",
                       node)
        elif label in self.goto_blockidlist:
            self.goto_blockidlist[label].append(self.current_blockid)
            self.goto_nodelist[label].append(node)
        else:
            self.goto_blockidlist[label] = [self.current_blockid]
            self.goto_nodelist[label] = [node]


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
    "print": "clPrint",
    "_curpack": "curpack",
    "_allocate": "clAllocate",
    "_deallocate": "clDeallocate",
    "_devstatus": "clDevstatus",
}

# builtin functions that are translated
# other functions just have 'iraf.' prepended

_functionList = {
    "int": "iraf.integer",
    "str": "str",
    "abs": "iraf.absvalue",
    "min": "iraf.minimum",
    "max": "iraf.maximum",
}

# return types of IRAF built-in functions

_functionType = {
    "int": "int",
    "real": "float",
    "sin": "float",
    "cos": "float",
    "tan": "float",
    "atan2": "float",
    "exp": "float",
    "log": "float",
    "log10": "float",
    "sqrt": "float",
    "frac": "float",
    "abs": "float",
    "min": "unknown",
    "max": "unknown",
    "fscan": "int",
    "scan": "int",
    "fscanf": "int",
    "scanf": "int",
    "nscan": "int",
    "stridx": "int",
    "strlen": "int",
    "str": "string",
    "substr": "string",
    "envget": "string",
    "mktemp": "string",
    "radix": "string",
    "osfn": "string",
    "_curpack": "string",
    "defpar": "bool",
    "access": "bool",
    "defvar": "bool",
    "deftask": "bool",
    "defpac": "bool",
    "imaccess": "bool",
}

# logical operator conversion
_LogOpDict = {
    "&&": " and ",
    "||": " or ",
}

# redirection conversion
_RedirDict = {
    ">": "Stdout",
    ">>": "StdoutAppend",
    ">&": "Stderr",
    ">>&": "StderrAppend",
    "<": "Stdin",
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

_stringTypes = {
    "string": 1,
    "char": 1,
    "file": 1,
    "struct": 1,
    "gcur": 1,
    "imcur": 1,
    "ukey": 1,
    "pset": 1,
}


def _convFunc(var, value):
    if var.list_flag or var.type in _stringTypes:
        if value is None:
            return ""
        else:
            return str(value)
    elif var.type == "int":
        if value is None or value == "INDEF":  # (matches _INDEFClass object)
            return "INDEF"
        elif isinstance(value, str) and value[:1] == ")":
            # parameter indirection
            return value
        else:
            return int(value)
    elif var.type == "real":
        if value is None or value == "INDEF":  # (matches _INDEFClass object)
            return "INDEF"
        elif isinstance(value, str) and value[:1] == ")":
            # parameter indirection
            return value
        else:
            return float(value)
    elif var.type == "bool":
        if value is None:
            return "INDEF"
        elif isinstance(value, (int, float)):
            if value == 0:
                return 'no'
            else:
                return 'yes'
        elif isinstance(value, str):
            s = value.lower()
            if s == "yes" or s == "y":
                s = "yes"
            elif s == "no" or s == "n":
                s = "'no'"
            elif s[:1] == ")":
                # parameter indirection
                return value
            else:
                raise ValueError(f"Illegal value `{s}' "
                                 f"for boolean variable {var.name}")
            return s
        else:
            try:
                return value.bool()
            except AttributeError as e:
                raise AttributeError(var.name + ':' + str(e))
    raise ValueError(f"unimplemented type `{var.type}'")


class CheckArgList(GenericASTTraversal, ErrorTracker):
    """Check task argument list for errors"""

    def __init__(self, ast):
        GenericASTTraversal.__init__(self, ast)
        # keywords is a list of keyword dictionaries (to handle
        # nested task calls)
        self.keywords = []
        self.taskname = []
        self.tasknode = []
        self.preorder()
        # note that we count on the Tree2Python class to print any errors

    def n_task_call_stmt(self, node):
        self.taskname.append(node[0].attr)
        self.tasknode.append(node)
        self.keywords.append({})

    def n_task_call_stmt_exit(self, node):
        self.taskname.pop()
        self.tasknode.pop()
        self.keywords.pop()

    def n_function_call(self, node):
        self.taskname.append(node[0].attr)
        self.tasknode.append(node)
        self.keywords.append({})

    def n_function_call_exit(self, node):
        self.taskname.pop()
        self.tasknode.pop()
        self.keywords.pop()

    def n_param_name(self, node):
        keyword = node[0].attr
        if keyword in self.keywords[-1]:
            self.error(f"Duplicate keyword `{keyword}' "
                       f"in call to {self.taskname[-1]}", node)
        else:
            self.keywords[-1][keyword] = 1

    def n_non_empty_arg(self, node):
        if node[0].type not in [
                'keyword_arg', 'bool_arg', 'redir_arg', 'non_expr_arg'
        ] and self.keywords[-1]:
            self.error("Non-keyword arg after keyword arg "
                       f"in call to {self.taskname[-1]}", node)

    def n_empty_arg(self, node):
        if self.keywords[-1]:
            # empty args don't have line number, so use task line
            self.error("Non-keyword (empty) arg after keyword arg "
                       f"in call to {self.taskname[-1]}", self.tasknode[-1])


class Tree2Python(GenericASTTraversal, ErrorTracker):

    def __init__(self, ast, vars, filename='', taskObj=None):
        self._ecl_iferr_entered = 0
        GenericASTTraversal.__init__(self, ast)
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
        self.printPass = [1] * 10
        self.code_buffer = io.StringIO()
        self.importDict = {}
        self.specialDict = {}
        self.pipeOut = []
        self.pipeIn = []
        self.pipeCount = 0
        # These three are used only by n_while_stmt, n_for_stmt, n_next_stmt,
        # and decrIndent; they are for incrementing the loop variable before
        # writing "continue" in a "for" loop (but not in a "while" loop).
        self.save_incr = []  # info to increment the loop variable
        self.save_indent = []  # indentation level in a while loop
        self.IN_A_WHILE_LOOP = "while"  # this is a constant value

        self._ecl_pyline = 1
        self._ecl_clline = None
        self._ecl_linemap = {}

        if self.vars.proc_name:
            self.indent = 1
        else:
            self.indent = 0

        if taskObj and self._ecl_iferr_entered:
            self.write(f"taskObj = iraf.getTask('{taskObj}')\n")

        # analyze goto structure
        # this assigns the label_count field for statement blocks
        self.gotos = GoToAnalyze(ast)

        # propagate any errors from goto analysis, but continue to see
        # if we can identify more problems
        self.errorappend(self.gotos)

        # This performs the actual translation.  It traverses the
        # abstract syntax tree.  self has methods called n_WHATEVER
        # for each WHATEVER node type in the tree.  Each method
        # writes python source code to self.code_buffer.
        self.preorder()
        self.write("\n")

        # Get the python source that is the translation of the cl.
        self.code = self.code_buffer.getvalue()
        self.code_buffer.close()

        # The translated python requires a header with initialization
        # code.  Now that we have performed the entire translation,
        # we know which of the initialization steps we need.  Stick
        # them on the front of the translated python.
        self.code_buffer = io.StringIO()
        self.writeProcHeader()
        header = self.code_buffer.getvalue()
        if pyrafglobals._use_ecl:
            self.code = self._ecl_linemapping(header) + \
                header + \
                self.code
        else:
            self.code = header + self.code
        self.code_buffer.close()
        del self.code_buffer

        #

        if self.filename == 'string_proc':
            self.comment('The code for "string_proc":')
            self.comment('-' * 80)
            self.comment(self.code)
            self.comment('-' * 80)

        self.printerrors()

    def _ecl_linemapping(self, header):
        lines = header.count("\n") + 2
        # count + 2 because we will add two more lines to the header

        # adjust all the line numbers up by the size of the header
        newmap = {}
        for key, value in self._ecl_linemap.items():
            newmap[key + lines] = value

        # return a python assignment statement that initializes the dictionary
        return "_ecl_linemap_" + self.vars.proc_name + " = " + repr(
            newmap) + "\n\n"

    def incrIndent(self):
        """Increment indentation count"""
        # printPass is used to recognize empty indentation blocks
        # and add 'pass' statement when indentation level is decremented
        self.indent = self.indent + 1
        if len(self.printPass) <= self.indent:
            # extend array to length self.indent+1
            self.printPass = self.printPass + \
                (self.indent+1-len(self.printPass)) * [1]
        self.printPass[self.indent] = 1

    def decrIndent(self):
        """Decrement indentation count and write 'pass' if required"""
        if self.printPass[self.indent]:
            self.writeIndent('pass')
        self.indent = self.indent - 1
        if len(self.save_indent) > 0 and self.save_indent[-1] == self.indent:
            del self.save_incr[-1]
            del self.save_indent[-1]

    def write(self, s, requireType=None, exprType=None):
        """Write string to output code buffer"""

        self._ecl_pyline += s.count("\n")
        self._ecl_linemap[self._ecl_pyline] = self._ecl_clline

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
        if s[-1:] == "\n":
            self.column = 0

    def writeIndent(self, value=None):
        """Write newline and indent"""
        self.write("\n")
        for i in range(self.indent):
            self.write("\t")
        if value:
            self.write(value)
        self.printPass[self.indent] = 0

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
            self.write("from pyraf import iraf")
            self.writeIndent(
                "from pyraf.irafpar import makeIrafPar, IrafParList")
            self.writeIndent("from stsci.tools.irafglobals import *")
            self.writeIndent("from pyraf.pyrafglobals import *")
            self.write("\n")

        if self.vars.proc_name:
            # create list of procedure arguments
            # make list of IrafPar definitions at the same time
            n = len(self.vars.proc_args_list)
            namelist = n * [None]
            proclist = n * [None]
            deflist = n * [None]
            for i in range(n):
                p = self.vars.proc_args_list[i]
                v = self.vars.proc_args_dict[p]
                namelist[i] = irafutils.translateName(p)
                if p in _SpecialArgs:
                    # special arguments are Python types
                    proclist[i] = p + '=' + str(v)
                    deflist[i] = ''
                else:
                    try:
                        proclist[i] = v.procLine()
                        deflist[i] = v.parDefLine()
                    except AttributeError as e:
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
            keylist = sorted(self.importDict.keys())
            if keylist:
                self.writeIndent("import ")
                self.write(", ".join(keylist))
                wnewline = 1

        if "PkgName" in self.specialDict:
            self.writeIndent("PkgName = iraf.curpack(); "
                             "PkgBinary = iraf.curPkgbinary()")
            wnewline = 1
        if wnewline:
            self.write("\n")

        # add local variables to deflist
        for p in self.vars.local_vars_list[self.vars.local_vars_count:]:
            v = self.vars.local_vars_dict[p]
            try:
                deflist.append(v.parDefLine(local=1))
            except AttributeError as e:
                raise AttributeError(self.filename + ':' + str(e))

        if deflist:
            # add local and procedure parameters to Vars list
            if not noHdr:
                self.writeIndent("Vars = IrafParList(" +
                                 repr(self.vars.proc_name) + ")")
            for defargs in deflist:
                if defargs:
                    self.writeIndent("Vars.addParam(makeIrafPar(")
                    self.writeChunks(defargs)
                    self.write("))")
            self.write("\n")

        if pyrafglobals._use_ecl:
            self.writeIndent("from pyraf.irafecl import EclState")
            self.writeIndent(
                f"_ecl = EclState(_ecl_linemap_{self.vars.proc_name})\n")

        # write goto label definitions if needed
        for label in self.gotos.labels():
            self.writeIndent(f"class GoTo_{label}(Exception): pass")

        # decrement indentation (which writes the pass if necessary)
        self.decrIndent()

    # ------------------------------
    # elements that can be ignored
    # ------------------------------

    def n_proc_stmt(self, node):
        self.prune()

    def n_declaration_block(self, node):
        self.prune()

    def n_declaration_stmt(self, node):
        self.prune()

    def n_BEGIN(self, node):
        pass

    def n_END(self, node):
        pass

    def n_NEWLINE(self, node):
        pass

    # ------------------------------
    # XXX unimplemented features
    # ------------------------------

    def n_BKGD(self, node):
        # background execution ignored for now
        self.warning("Background execution ignored", node)

    # ------------------------------
    # low-level conversions
    # ------------------------------

    def n_FLOAT(self, node):
        # convert d exponents to e for Python
        s = node.attr
        i = s.find('d')
        if i >= 0:
            s = s[:i] + 'e' + s[i + 1:]
        else:
            i = s.find('D')
            if i >= 0:
                s = s[:i] + 'E' + s[i + 1:]
        self.write(s, node.requireType, node.exprType)

    def n_INTEGER(self, node):
        # convert octal and hex constants
        value = node.attr
        last = value[-1].lower()
        if last == 'b':
            # octal
            self.write('0' + value[:-1], node.requireType, node.exprType)
        elif last == 'x':
            # hexadecimal
            self.write('0x' + value[:-1], node.requireType, node.exprType)
        else:
            # remove leading zeros on decimal values
            i = 0
            for digit in value:
                if digit != '0':
                    break
                i = i + 1
            else:
                # all zeros
                i = i - 1
            self.write(value[i:], node.requireType, node.exprType)

    def n_SEXAGESIMAL(self, node):
        # convert d:m:s values to float
        v = node.attr.split(':')
        # at least 2 values in expression
        s = 'iraf.clSexagesimal(' + v[0] + ',' + v[1]
        if len(v) > 2:
            s = s + ',' + v[2]
        s = s + ')'
        self.write(s, node.requireType, node.exprType)

    def n_IDENT(self, node, array_ref=0):
        s = irafutils.translateName(node.attr)
        if s in self.vars and s not in _SpecialArgs:

            # Prepend 'Vars.' to all procedure and local variable references
            # except for special args, which are normal Python variables.
            # The main reason I do it this way is so the IRAF scan/fscan
            # functions can work correctly, but it simplifies
            # other code generation as well.  Vars does all the type
            # conversions and applies constraints.
            # XXX Note we are not doing minimum match on parameter names

            self.write('Vars.' + s, node.requireType, node.exprType)
        elif '.' in s:

            # Looks like a task.parameter or field reference
            # Add 'Vars.' or 'iraf.' or 'taskObj.' prefix to name.
            # Also look for special p_ extensions -- need to use parameter
            # objects instead of parameter values if they are specified.

            attribs = s.split('.')
            ipf = basicpar.isParField(attribs[-1])
            if attribs[0] in self.vars:
                attribs.insert(0, 'Vars')
            elif ipf and (len(attribs) == 2):
                attribs.insert(0, 'taskObj')
            else:
                attribs.insert(0, 'iraf')
            if ipf:
                attribs[-2] = 'getParObject(' + repr(attribs[-2]) + ')'
            self.write(".".join(attribs), node.requireType, node.exprType)

        else:

            # not a local variable; use task object to search other
            # dictionaries

            if self.vars.mode == "single":
                self.write('iraf.cl.' + s, node.requireType, node.exprType)
            else:
                self.write('taskObj.' + s, node.requireType, node.exprType)

    def _print_subscript(self, node):
        # subtract one from IRAF subscripts to get Python subscripts
        # returns number of subscripts
        if len(node) > 1:
            n = self._print_subscript(node[0])
            self.write(", ")
        else:
            n = 0
        if node[-1].type == "INTEGER":
            self.write(str(int(node[-1]) - 1))
        else:
            self.preorder(node[-1])
            self.write("-1")
        return n + 1

    def n_array_ref(self, node):
        # in array reference, do not add .p_value to parameter identifier
        # because we can index the parameter directly
        # wrap in a conversion function if necessary
        cf = _funcName(node.requireType, node.exprType)
        if cf:
            self.write(cf + "(")
        self.n_IDENT(node[0], array_ref=1)
        self.write("[")
        nsub = self._print_subscript(node[2])
        self.write("]")
        if cf:
            self.write(")")
        # check for correct number of subscripts for local arrays
        s = irafutils.translateName(node[0].attr)
        if s in self.vars:
            v = self.vars.get(s)
            if nsub < len(v.shape):
                self.error(f"Too few subscripts for array {s}", node)
            elif nsub > len(v.shape):
                self.error(f"Too many subscripts for array {s}", node)
        self.prune()

    def n_param_name(self, node):
        s = irafutils.translateName(node[0].attr, dot=1)
        self.write(s)
        self.prune()

    def n_LOGOP(self, node):
        self.write(_LogOpDict[node.attr])

    def n_function_call(self, node):
        # all functions are built-in (since CL does not allow new definitions)
        # wrap in a conversion function if necessary
        cf = _funcName(node.requireType, node.exprType)
        if cf:
            self.write(cf + "(")
        functionname = node[0].attr
        newname = _functionList.get(functionname)
        if newname is None:
            # just add "iraf." prefix
            newname = "iraf." + functionname
        self.write(newname + "(")
        # argument list for scan statement
        sargs = self.captureArgs(node[2])
        if functionname in ["scan", "fscan", "scanf", "fscanf"]:
            # scan is weird -- effectively uses call-by-name
            # call special routine to change the args
            sargs = self.modify_scan_args(functionname, sargs)
        self.writeChunks(sargs)
        self.write(")")
        if cf:
            self.write(")")
        self.prune()

    def modify_scan_args(self, functionname, sargs):
        # modify argument list for scan statement

        # If fscan, first argument is the string to read from.
        # But we still want to pass it by name because if the
        # first argument is a list parameter, we want to postpone
        # its evaluation until we get into the fscan function so
        # we can catch EOF exceptions.

        # Add quotes to names (we're literally passing the names, not
        # the values)
        sargs = list(map(repr, sargs))

        # pass in locals dictionary so we can get names of variables to set
        sargs.insert(0, "locals()")
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
            elif node.type in _trailSpaceList:
                self.write(repr(node), requireType, exprType)
                self.write(" ")
            elif node.type in _bothSpaceList:
                self.write(" ")
                if hasattr(node, 'trunc_int_div'):
                    self.write('//', requireType, exprType)
                else:
                    self.write(repr(node), requireType, exprType)
                self.write(" ")
            else:
                self.write(repr(node), requireType, exprType)
        elif requireType != exprType:
            cf = _funcName(requireType, exprType)
            if cf is not None:
                self.write(cf + '(')
                for nn in node:
                    self.preorder(nn)
                self.write(')')
                self.prune()

    def n_term(self, node):
        if pyrafglobals._use_ecl and node[1] in ['/', '%']:
            kind = {"/": "divide", "%": "modulo"}[node[1]]
            self.write(f"taskObj._ecl_safe_{kind}(")
            self.preorder(node[0])
            self.write(",")
            self.preorder(node[2])
            self.write(")")
            self.prune()
        else:
            self.default(node)

    # ------------------------------
    # block indentation control
    # ------------------------------

    def n_statement_block(self, node):
        for i in range(node.label_count):
            self.writeIndent("try:")
            self.incrIndent()

    def n_compound_stmt(self, node):
        self.write(":")
        self.incrIndent()
        for i in range(node.label_count):
            self.writeIndent("try:")
            self.incrIndent()

    def n_compound_stmt_exit(self, node):
        self.decrIndent()

    def n_nonnull_stmt(self, node):
        if node[0].type == "{":
            # indentation already done for compound statements
            self.preorder(node[1])
            self.prune()
        else:
            ##             if self._ecl_iferr_entered:
            ##                 self.writeIndent("try:")
            ##                 self.incrIndent()
            ##                 self.writeIndent()
            ##                 for kid in node:
            ##                     self.preorder(kid)
            ##                 self.decrIndent()
            ##                 self.writeIndent("except Exception, e:")
            ##                 self.incrIndent()
            ##                 self.writeIndent("taskObj._ecl_record_error(e)")
            ##                 self.decrIndent()
            ##                 self.prune()
            ##             else:
            self._ecl_clline = FindLineNumber(node).lineno
            self.writeIndent()

    # ------------------------------
    # statements
    # ------------------------------

    def n_osescape_stmt(self, node):
        self.write("iraf.clOscmd(" + repr(node[0].attr) + ")")
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

    def n_iferr_stmt(self, node):
        # iferr_stmt    ::= if_kind guarded_stmt except_action
        # iferr_stmt    ::= if_kind guarded_stmt opt_newline THEN except_action
        # iferr_stmt    ::= if_kind guarded_stmt opt_newline THEN except_action opt_newline ELSE else_action
        # if_kind ::= IFERR
        # if_kind ::= IFNOERR
        # guarded_stmt  ::=  { opt_newline statement_list }
        # except_action ::= compound_stmt
        # else_action   ::= compound_stmt
        if len(node) == 3:
            ifkind, guarded_stmt, except_action, else_action = node[0], node[
                1], node[2], None
        elif len(node) == 5:
            ifkind, guarded_stmt, except_action, else_action = node[0], node[
                1], node[4], None
        else:
            ifkind, guarded_stmt, except_action, else_action = node[0], node[
                1], node[4], node[7]
        if ifkind.type == "IFNOERR":
            except_action, else_action = else_action, except_action

        self.writeIndent("taskObj._ecl_push_err()\n")

        self._ecl_iferr_entered += 1
        self.preorder(guarded_stmt)
        self._ecl_iferr_entered -= 1

        self.write("\n")
        self.writeIndent("if taskObj._ecl_pop_err()")

        self.preorder(except_action)
        if else_action:
            self.writeIndent("else")
            self.preorder(else_action)
        self.prune()


##         self.writeIndent("try:")
##         self.incrIndent()
##         self._ecl_iferr_entered += 1
##         self.preorder(guarded_stmt)
##         self._ecl_iferr_entered -= 1
##         self.decrIndent()
##         self.writeIndent("except")
##         self.preorder(except_action)
##         if else_action:
##             self.writeIndent("else")
##             self.preorder(else_action)
##         self.prune()

    def n_while_stmt(self, node):
        """we've got a 'while' statement"""
        # Append this value as a flag to tell n_next_stmt that it should
        # not increment the loop variable before writing "continue".
        self.save_incr.append(self.IN_A_WHILE_LOOP)
        # Save the indentation level, so we can tell when we're leaving
        # the 'while' loop.
        self.save_indent.append(self.indent)

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
        if init.type == "opt_assign_stmt" and len(init) == 0:
            # empty initialization
            self.write("while (")
        else:
            self.preorder(init)
            self.writeIndent("while (")
        # -------- condition --------
        condition = node[4]
        if condition.type == "opt_bool" and len(condition) == 0:
            # empty condition
            self.write("1")
        else:
            self.preorder(condition)
        self.write(")")
        # -------- execution block --------
        # go down inside the compound_stmt item so the increment can
        # be included inside the same block
        self.save_incr.append(node[6])  # needed if there's a 'next' statement
        self.write(":")
        self.incrIndent()
        for i in range(node[8].label_count):
            self.writeIndent("try:")
            self.incrIndent()
        for subnode in node[8]:
            self.preorder(subnode)
        # -------- increment --------
        incr = node[6]
        if incr.type == "opt_assign_stmt" and len(incr) == 0:
            # empty increment
            pass
        else:
            self.writeIndent()
            self.preorder(incr)
        self.decrIndent()
        if len(self.save_incr) > 0:
            del (self.save_incr[-1])
        self.prune()

    def n_next_stmt(self, node):
        if len(self.save_incr) > 0 and \
           self.save_incr[-1] != self.IN_A_WHILE_LOOP:
            # increment the loop variable -- copied from n_for_stmt()
            incr = self.save_incr[-1]
            if incr.type == "opt_assign_stmt" and len(incr) == 0:
                pass
            else:
                self.preorder(incr)
                self.writeIndent()
        self.write("continue")
        self.prune()

    def n_label_stmt(self, node):
        # labels translate to except statements
        # skip unsued labels
        label = node[0].attr
        if label in self.gotos:
            self.decrIndent()
            self.writeIndent(f"except GoTo_{irafutils.translateName(label)}:")
            self.incrIndent()
            self.writeIndent("pass")
            self.decrIndent()
        self.prune()

    def n_goto_stmt(self, node):
        self.write(f"raise GoTo_{irafutils.translateName(node[1].attr)}")
        self.prune()

    def n_inspect_stmt(self, node):
        self.write("print(")
        if node[0].type == "=":
            # '= expr' version of inspect
            self.preorder(node[1])
        else:
            # 'IDENT =' version of inspect
            self.preorder(node[0])
        self.write(")")
        self.prune()

    def n_switch_stmt(self, node):
        self.inSwitch = self.inSwitch + 1
        self.caseCount.append(0)
        self.write(f"SwitchVal{self.inSwitch:d} = ")
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
        self.write(f"SwitchVal{self.inSwitch:d} in [")
        self.preorder(node[2])
        self.write("]")
        self.preorder(node[4])
        self.prune()

    def n_default_stmt_block(self, node):
        if len(node) > 0:
            if self.caseCount[-1] == 0:
                # only a default in this switch
                self.writeIndent("if 1")
            else:
                self.writeIndent("else")
            self.preorder(node[3])
            self.prune()

    # ------------------------------
    # pipes implemented using redirection + task return values
    # ------------------------------

    def n_task_pipe_stmt(self, node):
        self.pipeCount = self.pipeCount + 1
        pipename = 'Pipe' + str(self.pipeCount)
        self.pipeOut.append(pipename)
        self.preorder(node[0])
        self.pipeOut.pop()
        self.pipeIn.append(pipename)
        self.writeIndent()
        self.preorder(node[2])
        self.pipeIn.pop()
        self.pipeCount = self.pipeCount - 1
        self.prune()

    # ------------------------------
    # task execution
    # ------------------------------

    def n_task_call_stmt(self, node):
        self.errorappend(CheckArgList(node))
        taskname = node[0].attr
        self.currentTaskname = taskname
        # '$' prefix means print time required for task (just ignore it for now)
        if taskname[:1] == '$':
            taskname = taskname[1:]
        # translate some special task names and add "iraf." to all names
        # additionalArguments will get appended at the end of the
        # argument list
        self.additionalArguments = []
        # add plumbing for pipes if necessary
        if self.pipeIn:
            # read from existing input line list
            self.additionalArguments.append("Stdin=" + self.pipeIn[-1])
        if self.pipeOut:
            self.write(self.pipeOut[-1] + " = ")
            self.additionalArguments.append("Stdout=1")
        # add extra arguments for task, package commands
        newname = _taskList.get(taskname, taskname)
        newname = "iraf." + irafutils.translateName(newname)
        if taskname in ('task', 'pyexecute'):
            # task, pyexecute need additional package, bin arguments
            self.specialDict['PkgName'] = 1
            self.additionalArguments.append("PkgName=PkgName")
            self.additionalArguments.append("PkgBinary=PkgBinary")
        elif taskname == 'package':
            # package needs additional package, bin arguments and returns args
            self.specialDict['PkgName'] = 1
            self.additionalArguments.append("PkgName=PkgName")
            self.additionalArguments.append("PkgBinary=PkgBinary")
            # package is a function returning new values for PkgName etc.
            # except when pipe is specified
            if not self.pipeOut:
                self.write("PkgName, PkgBinary = ")
        # add extra argument to save parameters if in "single" mode
        if self.vars.mode == "single":
            self.additionalArguments.append("_save=1")
        self.write(newname)
        self.preorder(node[1])

        if self.pipeIn:
            # done with this input pipe
            self.writeIndent("del " + self.pipeIn[-1])

        if taskname == "clbye" or taskname == "bye":
            # must do a return after clbye() or bye() if not in 'single' mode
            if self.vars.mode != "single":
                self.writeIndent("return")
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
                self.warning("Missing closing parenthesis", node)
                i = 1
            elif node[1].type == ")":
                # missing open parenthesis
                self.warning("Missing opening parenthesis", node)
                i = 0

        # tag argument list with parent for context analysis in case of
        # keyword args later
        node[i].parent = node
        # get the list of arguments

        sargs = self.captureArgs(node[i])

        # Delete the extra parentheses on a single argument that already
        # has parentheses.  This is fixing a parsing ambiguity created by
        # the ability to interpret a single parenthesized argument either
        # as a parenthesized list or as an unparenthesized list consisting
        # of an expression.
        if len(sargs) == 1:
            s = sargs[0]
            if s[:1] == "(" and s[-1:] == ")":
                sargs[0] = s[1:-1]

        if self.currentTaskname in ["scan", "fscan", "scanf", "fscanf"]:
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

        arg_buffer = io.StringIO()
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
        sargs = args.split(',\255')
        if sargs[0] == '':
            del sargs[0]
        return sargs

    def writeChunks(self, arglist, linelength=78):
        # break up arg list into line-sized chunks
        if not arglist:
            return
        maxline = linelength - self.column
        newargs = arglist[0]
        for arg in arglist[1:]:
            if len(newargs) + len(arg) + 2 > maxline:
                self.write(newargs + ',')
                # self.writeIndent('\t')
                newargs = arg
                maxline = linelength - self.column
            else:
                newargs = newargs + ', ' + arg
        self.write(newargs)

    def n_empty_arg(self, node):
        # XXX This is an omitted argument
        # XXX Not really correct yet -- need to work on this
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
            redir = _RedirDict[s] + ''.join(tail)
        self.write(redir + '=')
        self.preorder(node[1])
        self.prune()

    def n_keyword_arg(self, node):
        # This is needed to handle cursor parameters, which should
        # be passed as objects rather than by value.
        assert len(node) == 3
        self.preorder(node[0])
        self.preorder(node[1])
        # only the value needs special handling
        if node[2].type == 'IDENT':
            s = irafutils.translateName(node[2].attr)
            v = self.vars.get(s)
            if v and v.type in ['gcur', 'imcur']:
                # pass cursors by value
                self.write('Vars.getParObject("' + s + '")')
                self.prune()
                return
        self.preorder(node[2])
        self.prune()
