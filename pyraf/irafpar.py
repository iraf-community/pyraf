"""irafpar.py -- parse IRAF .par files and create lists of IrafPar objects

R. White, 2000 January 7
"""


import copy
import glob
import os
import re
import types
from stsci.tools import basicpar, minmatch, irafutils, taskpars
from stsci.tools.irafglobals import INDEF, Verbose, yes, no
from stsci.tools.basicpar import (warning, _StringMixin, IrafPar, IrafParS,
                                  _cmdlineFlag)
# also import basicpar.IrafPar* class names for cached scripts
from stsci.tools.basicpar import (IrafParB, IrafParI, IrafParR, IrafParAB,
                                  IrafParAI, IrafParAR, IrafParAS)
from . import iraf

# -----------------------------------------------------
# IRAF parameter factory
# -----------------------------------------------------

_string_list_types = ('*struct', '*s', '*f', '*i')


def IrafParFactory(fields, strict=0):
    """IRAF parameter factory
    fields is a list of the comma-separated fields (as in the .par file).
    Each entry is a string or None (indicating that field was omitted.)
    Set the strict parameter to a non-zero value to do stricter parsing
    (to find errors in the input.)"""

    # Sanity check
    if len(fields) < 3 or None in fields[0:3]:
        raise SyntaxError("At least 3 fields must be given")
    type = fields[1]

    # Handle special PyRAF/IRAF types, otherwise default to the standard types
    if type in _string_list_types:
        return IrafParLS(fields, strict)
    elif type == "*gcur" or type == "gcur":
        return IrafParGCur(fields, strict)
    elif type == "*imcur" or type == "imcur":
        return IrafParImCur(fields, strict)
    elif type == "*ukey" or type == "ukey":
        return IrafParUKey(fields, strict)
    elif type == "pset":
        return IrafParPset(fields, strict)
    else:
        return basicpar.parFactory(fields, strict)


# -----------------------------------------------------
# make an IrafPar variable (another factory function,
# using more descriptive notation for characteristics)
# -----------------------------------------------------

# dictionary mapping verbose types to short par-file types

_typedict = {
    'string': 's',
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
    'pset': 'pset',
}


def makeIrafPar(init_value,
                datatype=None,
                name="<anonymous>",
                mode="h",
                array_size=None,
                list_flag=0,
                min=None,
                max=None,
                enum=None,
                prompt="",
                strict=0,
                filename=None):
    """Create an IrafPar variable"""

    # Deprecation note - after 1.6 is released, remove the arg and this note
    if (filename is not None and len(filename) > 0 and
            filename != 'string_proc'):
        warning("Use of filename arg in makeIrafPar is rather deprecated\n" +
                ", filename = \'" + filename + "'",
                level=-1)

    # if init_value is already an IrafPar, just return it
    # XXX Could check parameters to see if they are ok
    if isinstance(init_value, IrafPar):
        return init_value

    # XXX Enhance this to determine datatype from init_value if it is omitted
    # XXX Could use _typedict.get(datatype,datatype) to allow short types to be used

    if datatype is None:
        raise ValueError("datatype must be specified")

    shorttype = _typedict[datatype]
    if array_size is None:
        shape = None
    else:
        shorttype = "a" + shorttype
        # array_size can be an integer or a tuple
        # get a tuple shape and make array_size the
        # combined size of all dimensions
        try:
            shape = tuple(array_size)
        except TypeError:
            shape = (array_size,)
        array_size = 1
        for d in shape:
            array_size = array_size * d
    if list_flag:
        shorttype = "*" + shorttype

    # messy stuff -- construct strings like we would read
    # from .par file for this parameter
    if shape is None:
        # scalar parameter
        fields = [name, shorttype, mode, init_value, min, max, prompt]
        if fields[4] is None:
            fields[4] = enum
    else:
        # N-dimensional array parameter
        fields = [
            name,
            shorttype,
            mode,
            str(len(shape)),  # number of dims
        ]
        for d in shape:
            fields.extend([
                d,  # dimension
                "1"
            ])  # apparently always 1
        if min is None:
            fields.extend([enum, max, prompt])
        else:
            fields.extend([min, max, prompt])
        if init_value is not None:
            if len(init_value) != array_size:
                raise ValueError("Initial value list does not match array "
                                 f"size for parameter `{name}'")
            for iv in init_value:
                fields.append(iv)
        else:
            fields = fields + array_size * [None]
    for i in range(len(fields)):
        if fields[i] is not None:
            fields[i] = str(fields[i])
    try:
        return IrafParFactory(fields, strict=strict)
    except ValueError as e:
        errmsg = f"Bad value for parameter `{name}'\n{str(e)}"
        raise ValueError(errmsg)


# -----------------------------------------------------
# IRAF pset parameter class
# -----------------------------------------------------


class IrafParPset(IrafParS):
    """IRAF pset parameter class"""

    def __init__(self, fields, strict=0):
        IrafParS.__init__(self, fields, strict)
        # omitted pset parameters default to null string
        if self.value is None:
            self.value = ""

    def get(self,
            field=None,
            index=None,
            lpar=0,
            prompt=1,
            native=0,
            mode="h"):
        """Return pset value (IrafTask object)"""
        if index:
            raise SyntaxError("Parameter " + self.name +
                              " is pset, cannot use index")
        if field:
            return self._getField(field)
        if lpar:
            return str(self.value)

        # assume there are no query or indirection pset parameters

        # see if parameter value has .par extension, if so, it is a file name
        f = self.value.split('.')
        if len(f) > 1 and f[-1] == 'par':
            # must be a file name
            from .iraffunctions import IrafTaskFactory
            irf_val = iraf.Expand(self.value)
            return IrafTaskFactory(taskname=irf_val.split(".")[0],
                                   value=irf_val)
        else:
            # must be a task name
            if self.value:
                # The normal case here is that the value is a task name string
                # so we get&return that task. There is a quirky case where in
                # some CL scripts (e.g. ccdproc.cl), the CL script writers use
                # this place as a temporarty place to store values; handle that.
                if self.value.startswith('<') and self.value.endswith(
                        '>') and self.name in self.value:
                    # don't lookup task for self.value, it is something like:
                    # "<IrafCLTask ccdproc (mscsrc$ccdproc.cl) Pkg: mscred Bin: mscbin$>"
                    return iraf.getTask(self.name)
                    # this is only a safe assumption to make in a PSET
                else:
                    return iraf.getTask(self.value)
            else:
                return iraf.getTask(self.name)


# -----------------------------------------------------
# IRAF list parameter base class
# -----------------------------------------------------


class IrafParL(_StringMixin, IrafPar):
    """IRAF list parameter base class"""

    def __init__(self, fields, strict=0):
        IrafPar.__init__(self, fields, strict)
        # filehandle for input file
        self.__dict__['fh'] = None
        # lines used to store input when not reading from a tty
        self.__dict__['lines'] = None
        # flag inidicating error message has been printed if file does not exist
        # message only gets printed once for each file
        self.__dict__['errMsg'] = 0
        # omitted list parameters default to null string
        if self.value is None:
            self.value = ""

    # --------------------------------------------
    # public methods
    # --------------------------------------------

    def set(self, value, field=None, index=None, check=1):
        """Set value of this parameter from a string or other value.
        Field is optional parameter field (p_prompt, p_minimum, etc.)
        Index is optional array index (zero-based).  Set check=0 to
        assign the value without checking to see if it is within
        the min-max range or in the choice list."""

        if index is not None:
            raise SyntaxError("Parameter " + self.name + " is not an array")

        if field:
            self._setField(value, field, check=check)
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
                except OSError:
                    pass
                self.fh = None
                self.lines = None
            self.errMsg = 0

    def get(self,
            field=None,
            index=None,
            lpar=0,
            prompt=1,
            native=0,
            mode="h"):
        """Return value of this parameter as a string (or in native format
        if native is non-zero.)"""

        if field:
            return self._getField(field, native=native, prompt=prompt)
        if lpar:
            if self.value is None and native == 0:
                return ""
            else:
                return self.value

        # assume there are no query or indirection list parameters

        if index is not None:
            raise SyntaxError("Parameter " + self.name + " is not an array")

        if self.value:
            # non-null value means we're reading from a file
            try:
                if not self.fh:
                    self.fh = open(iraf.Expand(self.value))
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
                    raise EOFError(f"EOF from list parameter `{self.name}'")
                if value[-1:] == "\n":
                    value = value[:-1]
            except OSError as e:
                if not self.errMsg:
                    warning(f"Unable to read values for list parameter "
                            f"`{self.name}' from file `{self.value}'\n{str(e)}",
                            level=-1)
                    # only print message one time
                    self.errMsg = 1
                # fall back on default behavior if file is not readable
                value = self._getNextValue()
        else:
            # if self.value is null, use the special _getNextValue method
            # (which should always return a string)
            if prompt:
                value = self._getNextValue()
            else:
                return self.value
        if native:
            return self._coerceValue(value)
        else:
            return value

    # --------------------------------------------
    # private methods
    # --------------------------------------------

    # Use _getNextValue() method to implement a particular type

    def _getNextValue(self):
        """Return a string with next value"""
        raise RuntimeError("Bug: base class IrafParL cannot be used directly")

    def _getPFilename(self, native, prompt):
        """Get p_filename field for this parameter (returns filename)"""
        # XXX is this OK? should we check for self.value==None?
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

    def _getNextValue(self):
        """Return next string value"""
        # save current values (in case this got called
        # because filename was in error)
        saveVal = self.value
        saveErr = self.errMsg
        try:
            # get rid of default value in prompt
            self.value = None
            self.getWithPrompt()
            retval = self.value
            return retval
        finally:
            # restore original values
            self.value = saveVal
            self.errMsg = saveErr


# -----------------------------------------------------
# IRAF cursor parameter class
# -----------------------------------------------------


class IrafParCursor(IrafParL):
    """Base class for cursor parameters"""

    def _coerceOneValue(self, value, strict=0):
        if isinstance(value, IrafParCursor):
            return value.p_filename
        else:
            return IrafParL._coerceOneValue(self, value, strict)


# -----------------------------------------------------
# IRAF gcur (graphics cursor) parameter class
# -----------------------------------------------------


class IrafParGCur(IrafParCursor):
    """IRAF graphics cursor parameter class"""

    def _getNextValue(self):
        """Return next graphics cursor value"""
        from . import gki  # lazy import - reduce circular imports on startup
        return gki.kernel.gcur()


# -----------------------------------------------------
# IRAF imcur (image display cursor) parameter class
# -----------------------------------------------------


class IrafParImCur(IrafParCursor):
    """IRAF image display cursor parameter class"""

    def _getNextValue(self):
        """Return next image display cursor value"""
        from . import irafimcur  # lazy import - reduce circular imports on startup
        return irafimcur.imcur()


# -----------------------------------------------------
# IRAF ukey (user typed key) parameter class
# -----------------------------------------------------


class IrafParUKey(IrafParL):
    """IRAF user typed key parameter class"""

    def _getNextValue(self):
        """Return next typed character"""
        from . import irafukey  # lazy import - reduce circular imports on startup
        return irafukey.ukey()


# -----------------------------------------------------
# IRAF parameter list synchronized to disk file
# -----------------------------------------------------

from . import filecache


class ParCache(filecache.FileCache):
    """Parameter cache that updates from .par file when necessary"""

    def __init__(self, filename, parlist, strict=0):
        self.initparlist = parlist
        # special filename used by cl2py
        if filename is None or filename == 'string_proc':
            filename = ''
        try:
            filecache.FileCache.__init__(self, filename)
        except OSError:
            # whoops, couldn't open that file
            # start with a null file instead unless strict is set
            if strict:
                raise
            filename = ''
            filecache.FileCache.__init__(self, filename)

    def getValue(self):
        return self.pars, self.pardict, self.psetlist

    def newValue(self):
        """Called to create initial value"""
        # initparlist dominates .par file during initialization
        if self.initparlist is not None:
            self.pars = self.initparlist
        elif self.filename:
            self.pars = _readpar(self.filename)
        else:
            # create empty list if no filename is specified
            self.pars = []
        # build auxiliary attributes from pars list
        self._buildFromPars()

    def updateValue(self):
        """Initialize parameter list from parameter file"""
        if self.filename:
            # .par file dominates initparlist on update
            self.pars = _readpar(self.filename)
        elif self.initparlist is not None:
            self.pars = self.initparlist
        else:
            # create empty list if no filename is specified
            self.pars = []
        # build auxiliary attributes from pars list
        self._buildFromPars()

    def _buildFromPars(self):
        # build minmatch dictionary of all parameters, including
        # those in psets
        self.pardict = minmatch.MinMatchDict()
        psetlist = []
        for p in self.pars:
            self.pardict.add(p.name, p)
            if isinstance(p, IrafParPset):
                psetlist.append(p)
        # add mode, $nargs to parameter list if not already present
        if not self.pardict.has_exact_key("mode"):
            p = makeIrafPar("al", name="mode", datatype="string", mode="h")
            self.pars.append(p)
            self.pardict.add(p.name, p)
        if not self.pardict.has_exact_key("$nargs"):
            p = makeIrafPar(0, name="$nargs", datatype="int", mode="h")
            self.pars.append(p)
            self.pardict.add(p.name, p)

        # save the list of pset parameters
        # Defer adding the parameters until later because saved parameter
        # sets may not be defined yet when restoring from save file.
        self.psetlist = psetlist


# -----------------------------------------------------
# IRAF parameter list class
# -----------------------------------------------------

# Note that all methods are mixed case and all attributes are private
# (start with __) to avoid conflicts with parameter names


class IrafParList(taskpars.TaskPars):
    """List of Iraf parameters"""

    def __init__(self, taskname, filename="", parlist=None):
        """Create a parameter list for task taskname

        If parlist is specified, uses it as a list of IrafPar objects.
        Else if filename is specified, reads a .par file.
        If neither is specified, generates a default list.
        """
        self.__pars = []
        self.__hasPsets = False
        self.__psets2merge = None  # is a list when populated
        self.__psetLock = False
        self.__filename = filename
        self.__name = taskname
        self.__filecache = ParCache(filename, parlist)
        # initialize parameter list
        self.Update()

    def Update(self):
        """Check to make sure this list is in sync with parameter file"""
        self.__pars, self.__pardict, self.__psets2merge = \
            self.__filecache.get()
        if self.__psets2merge:
            self.__addPsetParams()

    def setFilename(self, filename):
        """Change filename and create ParCache object

        Retains current parameter values until an unlearn is done
        """
        if hasattr(filename, 'name') and hasattr(filename, 'read'):
            filename = filename.name
        if isinstance(filename, str):
            root, ext = os.path.splitext(filename)
            if ext != ".par":
                # Only .par files are used as basis for parameter cache -- see if there
                # is one
                # Note that parameters specified in CL scripts are automatically updated
                # when the script changes
                filename = root + ".par"
                if not os.path.exists(filename):
                    filename = ""
        else:
            filename = ""
        if self.__filename != filename:
            if filename:
                # it is an error if this file does not exist
                self.__filecache = ParCache(filename, None, strict=1)
            else:
                # for null filename, default parameter list is fixed
                self.__filecache = ParCache(filename, self.__pars)
            self.__filename = filename

    def __addPsetParams(self):
        """
        Merge pset parameters into the parameter lists.
        Developer note - the original intention of this may have been to ensure
        that the pset par which appears in this list is NOT a copy of the
        original par (from the pset) but a reference to the same object, and if
        so, that would make things work smoothly, but it was found in Feb of
        2013 that this is not happening correctly, and may be an unsafe plan.
        Therefore the code was changed to allow clients to access both copies;
        see getParObjects() and any related code. """
        # return immediately if they have already been added or
        # if we are in the midst of a recursive call tree
        if self.__psetLock or self.__psets2merge is None:
            return
        # otherwise, merge in any PSETs
        if len(self.__psets2merge) > 0:
            self.__hasPsets = True  # never reset
        self.__psetLock = True  # prevent us from coming in recursively

        # Work from the pset's pardict because then we get
        # parameters from nested psets too
        for p in self.__psets2merge:
            # silently ignore parameters from psets that already are defined
            psetdict = p.get().getParDict()
            for pname in psetdict.keys():
                if not self.__pardict.has_exact_key(pname):
                    self.__pardict.add(pname, psetdict[pname])

        # back to normal state
        self.__psets2merge = None
        self.__psetLock = False

    def addParam(self, p):
        """Add a parameter to the list"""
        if not isinstance(p, IrafPar):
            t = type(p)
            if issubclass(t, types.InstanceType):
                tname = p.__class__.__name__
            else:
                tname = t.__name__
            raise TypeError("Parameter must be of type IrafPar (value: " +
                            tname + ", type: " + str(t) + ", object: " +
                            repr(p) + ")")
        elif self.__pardict.has_exact_key(p.name):
            if p.name in ["$nargs", "mode"]:
                # allow substitution of these default parameters
                self.__pardict[p.name] = p
                for i in range(len(self.__pars)):
                    j = -i - 1
                    if self.__pars[j].name == p.name:
                        self.__pars[j] = p
                        return
                else:
                    raise RuntimeError(f"Bug: parameter `{name}' is in "
                                       "dictionary __pardict but not in "
                                       "list __pars??")
            raise ValueError(f"Parameter named `{p.name}' is already defined")
        # add it just before the mode and $nargs parameters (if present)
        j = -1
        for i in range(len(self.__pars)):
            j = -i - 1
            if self.__pars[j].name not in ["$nargs", "mode"]:
                break
        else:
            j = -len(self.__pars) - 1
        self.__pars.insert(len(self.__pars) + j + 1, p)
        self.__pardict.add(p.name, p)
        if isinstance(p, IrafParPset):
            # parameters from this pset will be added too
            if self.__psets2merge is None:
                # add immediately
                self.__psets2merge = [p]
                self.__addPsetParams()
            else:
                # just add to the pset list
                self.__psets2merge.append(p)
                # can't call __addPsetParams here as we may now be inside a call

    def isConsistent(self, other):
        """Compare two IrafParLists for consistency

        Returns true if lists are consistent, false if inconsistent.
        Only checks immutable param characteristics (name & type).
        Allows hidden parameters to be in any order, but requires
        non-hidden parameters to be in identical order.
        """
        if not isinstance(other, self.__class__):
            if Verbose > 0:
                print(f'Comparison list is not a {self.__class__.__name__}')
            return 0
        # compare minimal set of parameter attributes
        thislist = self._getConsistentList()
        otherlist = other._getConsistentList()
        if thislist == otherlist:
            return 1
        else:
            if Verbose > 0:
                _printVerboseDiff(thislist, otherlist)
            return 0

    def _getConsistentList(self):
        """Return simplified parameter dictionary used for consistency check

        Dictionary is keyed by param name, with value of type and
        (for non-hidden parameters) sequence number.
        """
        dpar = {}
        j = 0
        hflag = -1
        for par in self.__pars:
            if par.mode == "h":
                dpar[par.name] = (par.type, hflag)
            else:
                dpar[par.name] = (par.type, j)
                j = j + 1
        return dpar

    def _dlen(self):
        """ For diagnostic use only: return length of class attr name dict. """
        return len(self.__dict__)

    def clearFlags(self):
        """Clear all status flags for all parameters"""
        for p in self.__pars:
            p.setFlags(0)

    def setAllFlags(self):
        """Set all status flags to indicate parameters were set on cmdline"""
        for p in self.__pars:
            p.setCmdline()

    # parameters are accessible as attributes

    def __getattr__(self, name):
        #       DBG: id(self), len(self.__dict__), "__getattr__ for: "+str(name)
        if name and name[0] == '_':
            raise AttributeError(name)
        try:
            return self.getValue(name, native=1)
        except SyntaxError as e:
            raise AttributeError(str(e))

    def __setattr__(self, name, value):
        #       DBG: id(self), len(self.__dict__), "__setattr__ for: "+str(name)+", value: "+str(value)[0:20]
        # hidden Python parameters go into the standard dictionary
        # (hope there are none of these in IRAF tasks)
        if name and name[0] == '_':
            object.__setattr__(self, name, value)
        else:
            self.setParam(name, value)

    def __len__(self):
        return len(self.__pars)

    # public accessor functions for attributes

    def hasPar(self, param):
        """Test existence of parameter named param"""
        if self.__psets2merge:
            self.__addPsetParams()
        param = irafutils.untranslateName(param)
        return param in self.__pardict

    def getFilename(self):
        return self.__filename

    def getParList(self, docopy=0):
        if docopy:
            # return copy of the list if docopy flag set
            pars = copy.deepcopy(self.__pars)
            for p in pars:
                p.setFlags(0)
            return pars
        else:
            # by default return the list itself
            return self.__pars

    def getParDict(self):
        if self.__psets2merge:
            self.__addPsetParams()
        return self.__pardict

    def getParObject(self, param):
        """ Returns an IrafPar object matching the name given (param).
        This looks only at the "top level" (which includes
        any duplicated PSET pars via __addPsetParams), but does not look
        down into PSETs. Note the difference between this and getParObjects
        in their different return types. """
        if self.__psets2merge:
            self.__addPsetParams()
        try:
            param = irafutils.untranslateName(param)
            return self.__pardict[param]
        except KeyError as e:
            raise e.__class__("Error in parameter '" + param + "' for task " +
                              self.__name + "\n" + str(e))

    def getParObjects(self, param, typecheck=True):
        """
        Returns all IrafPar objects matching the string name given (param),
        in the form of a dict like:
            { scopename : <IrafPar instance>, ... }
        where scopename is '' if par was found as a regular par in this list,
        or, where scopename is psetname if the par was found inside a PSET.
        It is possible that some dict values will actually be the same object
        in memory (see docs for __addPsetParams).

        This _will_ raise a KeyError if the given param name was not
        found at the "top level" (a regular par inside this par list)
        even if it is also in a PSET.

        typecheck: If multiple par objects are found, and typecheck is set to
        True, only the first (e.g. top level) will be returned if those
        par objects have a different value for their .type attribute.
        Otherwise all par objects found are returned in the dict.

        Note the difference between this and getParObject in their
        different return types.
        """
        # Notes:
        # To accomplish the parameter setting (e.g. setParam) this calls up
        # all possible exact-name-matching pars in this par list, whether
        # they be on the "top" level with that name (param), or down in some
        # PSET with that name (param).  If we are simply an IRAFish task, then
        # this is fine as we can assume the task likely does not have a par of
        # its own and a PSET par, both of which have the same name. Thus any
        # such case will acquire a copy of the PSET par at the top level. See
        # discussion of this in __addPsetParams().
        # BUT, if we are a CL script (e.g. mscombine.cl), we could have local
        # vars which happen to have the same names as PSET pars.  This is an
        # issue that we need to handle and be aware of (see typecheck arg).

        if self.__psets2merge:
            self.__addPsetParams()
        param = irafutils.untranslateName(param)
        retval = {}

        # First find the single "top-level" matching par
        try:
            pobj = self.__pardict[param]
            retval[''] = pobj
        except KeyError as e:
            raise e.__class__("Error in parameter '" + param + "' for task " +
                              self.__name + "\n" + str(e))

        # Next, see if there are any pars by this name inside any PSETs
        if not self.__hasPsets:
            return retval

        # There is a PSET in here somewhere...
        allpsets = [p for p in self.__pars if isinstance(p, IrafParPset)]
        for pset in allpsets:
            # Search the pset's pars.  We definitely do NOT want a copy,
            # we need the originals to edit.
            its_task = pset.get()
            its_plist = its_task.getParList(docopy=0)
            # assume full paramname given (no min-matching inside of PSETs)
            matching_pars = [pp for pp in its_plist if pp.name == param]
            if len(matching_pars) > 1:
                raise RuntimeError('Unexpected multiple matches for par: ' +
                                   param + ', are: ' +
                                   str([p.name for p in matching_pars]))
            # found one with that name; add it to outgoing dict
            if len(matching_pars) > 0:
                addit = True
                if typecheck and '' in retval:
                    # in this case we already found a top-level and we've been
                    # asked to make sure to return only same-type matches
                    addit = matching_pars[0].type == retval[
                        ''].type  # attr is a char
                if addit:
                    retval[pset.name] = matching_pars[0]
        return retval

    def getAllMatches(self, param):
        """Return list of all parameter names that may match param"""
        if param == "":
            return list(self.__pardict.keys())
        else:
            return self.__pardict.getallkeys(param, [])

    def getValue(self, param, native=0, prompt=1, mode="h"):
        """Return value for task parameter 'param' (with min-match)

        If native is non-zero, returns native format for value.  Default is
        to return a string.
        If prompt is zero, does not prompt for parameter.  Default is to
        prompt for query parameters.
        """
        par = self.getParObject(param)
        value = par.get(native=native, mode=mode, prompt=prompt)
        if isinstance(value, str) and value and value[0] == ")":
            # parameter indirection: ')task.param'
            try:
                task = iraf.getTask(self.__name)
                value = task.getParam(value[1:], native=native, mode="h")
            except KeyError:
                # if task is not known, use generic function to get param
                value = iraf.clParGet(value[1:],
                                      native=native,
                                      mode="h",
                                      prompt=prompt)
        return value

    def setParam(self, param, value, scope='', check=0, idxHint=None):
        """Set task parameter 'param' to value (with minimum-matching).
           scope, idxHint, and check are included for use as a task object
           but they are currently ignored."""
        matches_dict = self.getParObjects(param)
        for par_obj in matches_dict.values():
            par_obj.set(value)

    def setParList(self, *args, **kw):
        """Set value of multiple parameters from list"""
        # first undo translations that were applied to keyword names
        for key in kw.keys():
            okey = key
            key = irafutils.untranslateName(key)
            if okey != key:
                value = kw[okey]
                del kw[okey]
                kw[key] = value

        # then expand all keywords to their full names and add to fullkw
        fullkw = {}
        dupl_pset_pars = []
        for key in kw.keys():
            # recall, kw is just simple { namestr: valstr, ... }
            try:
                # find par obj for this key
                # (read docs for getParObjects - note the 's')
                results_dict = self.getParObjects(key)

                # results_dict is of form:  { psetname : <IrafPar instance> }
                # where results_dict may be (and most often is) empty string ''.
                # if no KeyError, then there exists a top-level entry ('')
                if '' not in results_dict:
                    raise RuntimeError('No top-level match; expected KeyError')
                # assume results_dict[''].name.startswith(key) or .name==key
                # recall that key might be shortened version of par's .name
                param = (results_dict[''].name, ''
                        )  # this means (paramname, [unused])
                results_dict.pop('')

                # if there are others, then they are pars with the same name
                # but located down inside a PSET.  So we save them for further
                # handling down below.
                for psetname in results_dict:
                    if not results_dict[psetname].name.startswith(key):
                        raise RuntimeError('PSET name non-match; par name: ' +
                                           key + '; got: ' +
                                           results_dict[psetname].name)
                    dupl_pset_pars.append(
                        (psetname, results_dict[psetname].name, key))
            except KeyError as e:
                # Perhaps it is pset.param ? This would occur if the caller
                # used kwargs like gemcube(..., geofunc.axis1 = 1, ...)
                # (see help call #3454 for Mark Sim.)
                i = key.find('.')
                if i <= 0:
                    raise e
                # recall that key[:i] might be shortened version of par's .name
                param = (self.getParObject(key[:i]).name, key[i + 1:])
                # here param is  (pset name, par name)
            if param in fullkw:
                msg_full_pname = param[0]
                if param[1]:
                    msg_full_pname = '.'.join(param)
                # at this point, msg_full_pname is fully qualified
                raise SyntaxError("Multiple values given for parameter " +
                                  msg_full_pname + " in task " + self.__name)
            # Add it
            fullkw[param] = kw[key]

        # At this point, an example of fullkw might be:
        # {('extname', ''): 'mef', ('long', ''): no, ('ccdtype', ''): ''}
        # NOTE that the keys to this dict are EITHER in the form
        # (top level par name, '') -OR- (pset name, par name)
        # CDS June2014 - this is ugly - love to change this soon...

        # Now add any duplicated pars that were found, both up at top level and
        # down inside a PSET (saved as dupl_pset_pars list).  The top level
        # version has already been added to fullkw, so we add the PSET version.
        for par_tup in dupl_pset_pars:
            # par_tup is of form:
            #    (pset name (full), par name (full), par name (short/given), )
            if par_tup[0:2] not in fullkw:
                # use par_tup[2]; its the given kw arg w/out the
                # identifying pset name
                fullkw[par_tup[0:2]] = kw[par_tup[2]]

        # Now add positional parameters to the keyword list, checking
        # for duplicates
        ipar = 0
        for value in args:
            while ipar < len(self.__pars):
                if self.__pars[ipar].mode != "h":
                    break
                ipar = ipar + 1
            else:
                # executed if we run out of non-hidden parameters
                raise SyntaxError("Too many positional parameters for task " +
                                  self.__name)
            # at this point, ipar is set to index of next found non-hidden
            # par in self.__pars
            param = (self.__pars[ipar].name, '')
            if param in fullkw:
                # uh-oh, it was already in our fullkw list, but now we got a
                # positional value for it (occurs in _ccdtool; help call #5901)
                msg_full_pname = param[0]
                if param[1]:
                    msg_full_pname = '.'.join(param)
                msg_val_from_kw = fullkw[param]
                msg_val_from_pos = value
                # let's say we only care if the 2 values are, in fact, different
                if msg_val_from_kw != msg_val_from_pos:
                    raise SyntaxError('Both a positional value ("' +
                                      str(msg_val_from_pos) +
                                      '") and a keyword value ("' +
                                      str(msg_val_from_kw) +
                                      '") were given for parameter "' +
                                      msg_full_pname + '" in task "' +
                                      self.__name + '"')
                # else:, we'll now just overwite the old value with the same new value
            fullkw[param] = value
            ipar = ipar + 1

        # Now set all keyword parameters ...
        # clear changed flags and set cmdline flags for arguments
        self.clearFlags()

        # Count number of positional parameters set on cmdline
        # Note that this counts positional parameters set through
        # keywords in $nargs -- that is different from IRAF, which
        # counts only non-keyword parameters.  That is a bug in IRAF.
        nargs = 0
        for key, value in fullkw.items():
            param, tail = key
            p = self.getParObject(param)
            if tail:
                # is pset parameter - get parameter object from its task
                p = p.get().getParObject(tail)
                # what if *this* p is a IrafParPset ? skip for now,
                # since we think no one is doubly nesting PSETs
            p.set(value)
            p.setFlags(_cmdlineFlag)
            if p.mode != "h":
                nargs = nargs + 1

        # Number of arguments on command line, $nargs, is used by some IRAF
        # tasks (e.g. imheader).
        self.setParam('$nargs', nargs)

    def eParam(self):
        from . import epar
        epar.epar(self)

    def tParam(self):
        from . import tpar
        tpar.tpar(self)

    def lParam(self, verbose=0):
        print(self.lParamStr(verbose=verbose))

    def lParamStr(self, verbose=0):
        """List the task parameters"""
        retval = []
        # Do the non-hidden parameters first
        for i in range(len(self.__pars)):
            p = self.__pars[i]
            if p.mode != 'h':
                if Verbose > 0 or p.name != '$nargs':
                    retval.append(p.pretty(verbose=verbose or Verbose > 0))
        # Now the hidden parameters
        for i in range(len(self.__pars)):
            p = self.__pars[i]
            if p.mode == 'h':
                if Verbose > 0 or p.name != '$nargs':
                    retval.append(p.pretty(verbose=verbose or Verbose > 0))
        return '\n'.join(retval)

    def dParam(self, taskname="", cl=1):
        """Dump the task parameters in executable form

        Default is to write CL version of code; if cl parameter is
        false, writes Python executable code instead.
        """
        if taskname and taskname[-1:] != ".":
            taskname = taskname + "."
        for i in range(len(self.__pars)):
            p = self.__pars[i]
            if p.name != '$nargs':
                print(f"{taskname}{p.dpar(cl=cl)}")
        if cl:
            print("# EOF")

    def saveParList(self, filename=None, comment=None):
        """Write .par file data to filename (string or filehandle)"""
        if filename is None:
            filename = self.__filename
        if not filename:
            raise ValueError("No filename specified to save parameters")
        # but not if user turned off parameter writes
        writepars = int(iraf.envget("writepars", 1))
        if writepars < 1:
            msg = "No parameters written to disk."
            print(msg)
            return msg
        # ok, go ahead and write 'em - set up file
        if hasattr(filename, 'write'):
            fh = filename
        else:
            absFileName = iraf.Expand(filename)
            absDir = os.path.dirname(absFileName)
            if len(absDir) and not os.path.isdir(absDir):
                os.makedirs(absDir)
            fh = open(absFileName, 'w')
        nsave = len(self.__pars)
        if comment:
            fh.write('# ' + comment + '\n')
        for par in self.__pars:
            if par.name == '$nargs':
                nsave = nsave - 1
            else:
                fh.write(par.save() + '\n')
        if fh != filename:
            fh.close()
            return f"{nsave:d} parameters written to {filename}"
        elif hasattr(fh, 'name'):
            return f"{nsave:d} parameters written to {fh.name}"
        else:
            return f"{nsave:d} parameters written"

    def __getinitargs__(self):
        """Return parameters for __init__ call in pickle"""
        return (self.__name, self.__filename, self.__pars)


#
#    These two methods were set to do nothing (they were previously
#    needed for pickle) but having them this way makes PY3K deepcopy
#    fail in an extremely difficult to diagnose way.
#
#    def __getstate__(self):
#        """Return additional state for pickle"""
#        # nothing beyond init
#        return None
#
#    def __setstate__(self, state):
#        """Restore additional state from pickle"""
#        pass

    def __str__(self):
        s = '<IrafParList ' + self.__name + ' (' + self.__filename + ') ' + \
            str(len(self.__pars)) + ' parameters>'
        return s

    # these methods are provided so an IrafParList can be treated like
    # an IrafTask object by epar (and other modules)

    def getDefaultParList(self):
        return self.getParList()

    def getName(self):
        return self.__name

    def getPkgname(self):
        return ''

    def run(self, *args, **kw):
        pass


def _printVerboseDiff(list1, list2):
    """Print description of differences between parameter lists"""
    pd1, hd1 = _extractDiffInfo(list1)
    pd2, hd2 = _extractDiffInfo(list2)
    _printHiddenDiff(pd1, hd1, pd2, hd2)  # look for hidden/positional changes
    _printDiff(pd1, pd2, 'positional')  # compare positional parameters
    _printDiff(hd1, hd2, 'hidden')  # compare hidden parameters


def _extractDiffInfo(alist):
    hflag = -1
    pd = {}
    hd = {}
    for key, value in alist.items():
        if value[1] == hflag:
            hd[key] = value
        else:
            pd[key] = value
    return (pd, hd)


def _printHiddenDiff(pd1, hd1, pd2, hd2):
    for key in list(pd1.keys()):
        if key in hd2:
            print(f"Parameter `{key}' is hidden in list 2 but not list 1")
            del pd1[key]
            del hd2[key]
    for key in list(pd2.keys()):
        if key in hd1:
            print(f"Parameter `{key}' is hidden in list 1 but not list 2")
            del pd2[key]
            del hd1[key]


def _printDiff(pd1, pd2, label):
    if pd1 == pd2:
        return
    noextra = 1
    k1 = sorted(pd1.keys())
    k2 = sorted(pd2.keys())
    if k1 != k2:
        # parameter name lists differ
        i1 = 0
        i2 = 0
        noextra = 0
        while i1 < len(k1) and i2 < len(k2):
            key1 = k1[i1]
            key2 = k2[i2]
            if key1 == key2:
                i1 = i1 + 1
                i2 = i2 + 1
            else:
                # one or both parameters missing
                if key1 not in pd2:
                    print(f"Extra {label} parameter `{key1}' "
                          f"(type `{pd1[key1][0]}') in list 1")
                    # delete the extra parameter
                    del pd1[key1]
                    i1 = i1 + 1
                if key2 not in pd1:
                    print(f"Extra {label} parameter `{key2}' "
                          f"(type `{pd2[key2][0]}') in list 2")
                    del pd2[key2]
                    i2 = i2 + 1
        # other parameters must be missing
        while i1 < len(k1):
            key1 = k1[i1]
            print("Extra {label} parameter `{key1}' "
                  f"(type `{pd1[key1][0]}') in list 1")
            del pd1[key1]
            i1 = i1 + 1
        while i2 < len(k2):
            key2 = k2[i2]
            print(f"Extra {label} parameter `{key2}' "
                  f"(type `{pd2[key2][0]}') in list 2")
            del pd2[key2]
            i2 = i2 + 1
    # remaining parameters are in both lists
    # check for differing order or type, but ignore order if there
    # were extra parameters
    for key in pd1.keys():
        if pd1[key] != pd2[key]:
            mm = []
            type1, order1 = pd1[key]
            type2, order2 = pd2[key]
            if noextra and order1 != order2:
                mm.append("order disagreement")
            if type1 != type2:
                mm.append(f"type disagreement (`{type1}' vs. `{type2}')")
            print(f"Parameter `{key}': {', '.join(mm)}")


# The dictionary of all special-use par files found on disk.
# Each key is a tuple of (taskName, pkgName).
# Each value is a list of path names.
_specialUseParFileDict = None

# For TASKMETA lines in par files, e.g.: '# TASKMETA: task=display package=tv'
_re_taskmeta = \
    re.compile(r'^# *TASKMETA *: *task *= *([^ ]*) *package *= *([^ \n]*)')


def _updateSpecialParFileDict(dirToCheck=None, strict=False):
    """ Search the disk in the given path (or .) for special-purpose parameter
    files.  These can have any name, end in .par, and have metadata comments
    which identify their associated task.  This function simply fills or
    adds to our _specialUseParFileDict dictionary. If strict is True then
    any .par file found is expected to have our TASKMETA tag. """

    global _specialUseParFileDict

    # Default state is that dictionary is created but empty
    if _specialUseParFileDict is None:
        _specialUseParFileDict = {}

    # If the caller gave us a dirToCheck, use only it, otherwise check the
    # usual places (which calls us recursively).
    if dirToCheck is None:
        # Check the auxilliary par dir
        uparmAux = iraf.envget("uparm_aux", "")
        if 'UPARM_AUX' in os.environ:
            uparmAux = os.environ['UPARM_AUX']
        if len(uparmAux) > 0:
            _updateSpecialParFileDict(dirToCheck=uparmAux, strict=True)
            # If the _updateSpecialParFileDict processing is found to be
            # be taking too long, we could easily add a global flag here like
            # _alreadyCheckedUparmAux = True

        # Also check the current directory
        _updateSpecialParFileDict(dirToCheck=os.getcwd())
        # For performance, note that there is nothing yet in place to stop us
        # from rereading a large dir of par files every time this is called

        return  # we've done enough

    # Do a glob in the given dir
    flist = glob.glob(dirToCheck + "/*.par")
    if len(flist) <= 0:
        return

    # At this point, we have files.  Foreach, figure out the task and
    # package it is for, and add it's pathname to the dict.
    for supfname in flist:
        buf = []
        try:
            supfile = open(supfname)
            buf = supfile.readlines()
            supfile.close()
        except OSError:
            pass
        if len(buf) < 1:
            warning("Unable to read special use parameter file: " + supfname,
                    level=-1)
            continue

        # get task and pkg names, and verify this is a correct file
        tupKey = None
        for line in buf:
            mo = _re_taskmeta.match(line)
            if mo:
                # the syntax is right,  get the task and pkg names
                tupKey = (mo.group(1), mo.group(2))
                break  # only one TASKMETA line per file

        if tupKey:
            if tupKey in _specialUseParFileDict:
                supflist = _specialUseParFileDict[tupKey]
                if supfname not in supflist:
                    _specialUseParFileDict[tupKey].append(supfname)
            else:
                _specialUseParFileDict[tupKey] = [
                    supfname,
                ]
        # If it does not have the TASKMETA line, then it is likely a regular
        # IRAF .par file.  How it got here we don't know, but it got dropped
        # here somehow and warning the user continuously about this would be
        # very annoying, so be quiet about it.


def newSpecialParFile(taskName, pkgName, pathName):
    """ Someone has just created a new one and we are being notified of that
    fact so that we can update the dict. """

    # We could at this point simply re-scan the disk for files, but for
    # now let's assume the user doesnt want that.  Just add this entry to
    # the dict.  Someday, after we gauge usage, we could change this to
    # re-scan and add this entry to the dict if not there yet.

    global _specialUseParFileDict

    # lazy init - only search disk here when abs. necessary
    if _specialUseParFileDict is None:
        _updateSpecialParFileDict()

    tupKey = (taskName, pkgName)
    if tupKey in _specialUseParFileDict:
        if pathName not in _specialUseParFileDict[tupKey]:
            _specialUseParFileDict[tupKey].append(pathName)
    else:
        _specialUseParFileDict[tupKey] = [
            pathName,
        ]


def haveSpecialVersions(taskName, pkgName):
    """ This is a simple check to see if special-purpose parameter files
    have been found for the given task/package.  This returns True or False.
    If the dictionary has not been created yet, this initializes it.  Note
    that this may take some time reading the disk. """

    global _specialUseParFileDict

    # Always update the _specialUseParFileDict, since we may have changed
    # directories into a new work area with as-yet-unseen .par files
    _updateSpecialParFileDict()

    # Check and return answer
    tupKey = (taskName, pkgName)
    return tupKey in _specialUseParFileDict


def getSpecialVersionFiles(taskName, pkgName):
    """ Returns a (possibly empty) list of path names for special versions of
    parameter files. This also causes lazy initialization."""

    global _specialUseParFileDict

    tupKey = (taskName, pkgName)
    if haveSpecialVersions(taskName, pkgName):
        return _specialUseParFileDict[tupKey]
    else:
        return []


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
_re_field = re.compile(field, re.DOTALL)

# Pattern that matches trailing backslashes at end of line
_re_bstrail = re.compile(r'\\*$')

# clean up unnecessary global variables
del whitespace, field, comma, optcomma, noncommajunk, double, single


def _readpar(filename, strict=0):
    """Read IRAF .par file and return list of parameters"""

    global _re_field, _re_bstrail

    param_dict = {}
    param_list = []
    fh = open(os.path.expanduser(filename))
    lines = fh.readlines()
    fh.close()
    # reverse order of lines so we can use pop method
    lines.reverse()
    while lines:
        # strip whitespace (including newline) off both ends
        line = lines.pop().strip()
        # skip comments and blank lines
        # "..." is weird line that occurs in cl.par
        if len(line) > 0 and line[0] != '#' and line != "...":
            # Append next line if this line ends with continuation character.
            while line[-1:] == "\\":
                # odd number of trailing backslashes means this is continuation
                if (len(_re_bstrail.search(line).group()) % 2 == 1):
                    try:
                        line = line[:-1] + lines.pop().rstrip()
                    except IndexError:
                        raise SyntaxError(filename +
                                          ": Continuation on last line\n" +
                                          line)
                else:
                    break
            flist = []
            i1 = 0
            while len(line) > i1:
                mm = _re_field.match(line, i1)
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
                            sline = line.split('\n')
                            raise SyntaxError(filename +
                                              ": Unmatched quote\n" + sline[0])
                        line = line + '\n' + nline.rstrip()
                        mm = _re_field.match(line, i1)
                if mm.group('comma') is not None:
                    g = mm.group('comma')
                    # completely omitted field (,,)
                    if g == "":
                        g = None
                    # check for trailing quote in unquoted string
                    elif g[-1:] == '"' or g[-1:] == "'":
                        warning(
                            filename + "\n" + line + "\n" +
                            "Unquoted string has trailing quote", strict)
                elif mm.group('double') is not None:
                    if mm.group('djunk'):
                        warning(
                            filename + "\n" + line + "\n" +
                            "Non-blank follows quoted string", strict)
                    g = mm.group('double')
                elif mm.group('single') is not None:
                    if mm.group('sjunk'):
                        warning(
                            filename + "\n" + line + "\n" +
                            "Non-blank follows quoted string", strict)
                    g = mm.group('single')
                else:
                    raise SyntaxError(
                        filename + "\n" + line + "\n" + "Huh? mm.groups()=" +
                        repr(mm.groups()) + "\n" +
                        "Bug: doesn't match single, double or comma??")
                flist.append(g)
                # move match pointer
                i1 = mm.end()
            try:
                par = IrafParFactory(flist, strict=strict)
            except KeyboardInterrupt:
                raise
            except Exception as exc:
                # XXX Shouldn't catch all exceptions here -- this could
                # XXX screw things up
                if Verbose:
                    import traceback
                    traceback.print_exc()
                raise SyntaxError(filename + "\n" + line + "\n" + str(flist) +
                                  "\n" + str(exc))
            if par.name in param_dict:
                warning(
                    filename + "\n" + line + "\n" + "Duplicate parameter " +
                    par.name, strict)
            else:
                param_dict[par.name] = par
                param_list.append(par)
    return param_list
