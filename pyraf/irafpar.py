"""irafpar.py -- parse IRAF .par files and create lists of IrafPar objects

$Id$

R. White, 2000 January 7
"""
from __future__ import division # confidence high

import copy, glob, os, re, sys, types
from stsci.tools import basicpar, minmatch, irafutils, taskpars
from stsci.tools.irafglobals import INDEF, Verbose, yes, no
from stsci.tools.basicpar import (warning, _StringMixin, IrafPar, IrafParS,
                                  _cmdlineFlag)
# also import basicpar.IrafPar* class names for cached scripts
from stsci.tools.basicpar import (IrafParB,  IrafParI,  IrafParR,
                                  IrafParAB, IrafParAI, IrafParAR, IrafParAS)

if __name__.find('.') >= 0: # not a unit test
    import irafimcur, irafukey, epar, tpar, gki, iraf


# -----------------------------------------------------
# IRAF parameter factory
# -----------------------------------------------------

_string_list_types = ( '*struct', '*s', '*f', '*i' )

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
        return IrafParLS(fields,strict)
    elif type == "*gcur" or type == "gcur":
        return IrafParGCur(fields,strict)
    elif type == "*imcur" or type == "imcur":
        return IrafParImCur(fields,strict)
    elif type == "*ukey" or type == "ukey":
        return IrafParUKey(fields,strict)
    elif type == "pset":
        return IrafParPset(fields,strict)
    else:
        return basicpar.parFactory(fields, strict)


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

    # Deprecation note - after 1.6 is released, remove the arg and this note
    if filename!=None and len(filename)>0 and filename!='string_proc':
       warning("Use of filename arg in makeIrafPar is rather deprecated\n"+\
               ", filename = \'"+filename+"'", level=-1)

    # if init_value is already an IrafPar, just return it
    #XXX Could check parameters to see if they are ok
    if isinstance(init_value, IrafPar): return init_value

    #XXX Enhance this to determine datatype from init_value if it is omitted
    #XXX Could use _typedict.get(datatype,datatype) to allow short types to be used

    if datatype is None: raise ValueError("datatype must be specified")

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
            array_size = array_size*d
    if list_flag:
        shorttype = "*" + shorttype

    # messy stuff -- construct strings like we would read
    # from .par file for this parameter
    if shape is None:
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
        # N-dimensional array parameter
        fields = [ name,
                   shorttype,
                   mode,
                   str(len(shape)),  # number of dims
                 ]
        for d in shape:
            fields.extend([d,              # dimension
                           "1"])           # apparently always 1
        if min is None:
            fields.extend([ enum,
                            max,
                            prompt ])
        else:
            fields.extend([ min,
                            max,
                            prompt ])
        if init_value is not None:
            if len(init_value) != array_size:
                raise ValueError("Initial value list does not match array size for parameter `%s'" % name)
            for iv in init_value:
                fields.append(iv)
        else:
            fields = fields + array_size*[None]
    for i in range(len(fields)):
        if fields[i] is not None:
            fields[i] = str(fields[i])
    try:
        return IrafParFactory(fields, strict=strict)
    except ValueError, e:
        errmsg = "Bad value for parameter `%s'\n%s" % (name, str(e))
        raise ValueError(errmsg)


# -----------------------------------------------------
# IRAF pset parameter class
# -----------------------------------------------------

class IrafParPset(IrafParS):

    """IRAF pset parameter class"""

    def __init__(self,fields,strict=0):
        IrafParS.__init__(self,fields,strict)
        # omitted pset parameters default to null string
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
        f = self.value.split('.')
        if len(f) <= 1 or f[-1] != 'par':
            # must be a task name
            return iraf.getTask(self.value or self.name)
        else:
            from iraffunctions import IrafTaskFactory
            irf_val = iraf.Expand(self.value)
            return IrafTaskFactory(taskname=irf_val.split(".")[0],
                                   value=irf_val)


# -----------------------------------------------------
# IRAF list parameter base class
# -----------------------------------------------------

class IrafParL(_StringMixin, IrafPar):

    """IRAF list parameter base class"""

    def __init__(self,fields,strict=0):
        IrafPar.__init__(self,fields,strict)
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
            if prompt:
                value = self._getNextValue()
            else:
                return self.value
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

    def _coerceOneValue(self,value,strict=0):
        if isinstance(value,IrafParCursor):
            return value.p_filename
        else:
            return IrafParL._coerceOneValue(self,value,strict)

# -----------------------------------------------------
# IRAF gcur (graphics cursor) parameter class
# -----------------------------------------------------

class IrafParGCur(IrafParCursor):

    """IRAF graphics cursor parameter class"""

    def _getNextValue(self):
        """Return next graphics cursor value"""
        return gki.kernel.gcur()

# -----------------------------------------------------
# IRAF imcur (image display cursor) parameter class
# -----------------------------------------------------

class IrafParImCur(IrafParCursor):

    """IRAF image display cursor parameter class"""

    def _getNextValue(self):
        """Return next image display cursor value"""
        return irafimcur.imcur()

# -----------------------------------------------------
# IRAF ukey (user typed key) parameter class
# -----------------------------------------------------

class IrafParUKey(IrafParL):

    """IRAF user typed key parameter class"""

    def _getNextValue(self):
        """Return next typed character"""
        return irafukey.ukey()


# -----------------------------------------------------
# IRAF parameter list synchronized to disk file
# -----------------------------------------------------

if __name__.find('.') < 0: # for unit test
    import filecache # revert to simple import after 2to3
else:
    import filecache

class ParCache(filecache.FileCache):

    """Parameter cache that updates from .par file when necessary"""

    def __init__(self, filename, parlist, strict=0):
        self.initparlist = parlist
        # special filename used by cl2py
        if filename is None or filename == 'string_proc':
            filename = ''
        try:
            filecache.FileCache.__init__(self, filename)
        except (OSError, IOError):
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
            if isinstance(p, IrafParPset): psetlist.append(p)
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
        self.__filename = filename
        self.__name = taskname
        self.__filecache = ParCache(filename, parlist)
        # initialize parameter list
        self.Update()

    def Update(self):
        """Check to make sure this list is in sync with parameter file"""
        self.__pars, self.__pardict, self.__psetlist = \
                self.__filecache.get()

    def setFilename(self, filename):
        """Change filename and create ParCache object

        Retains current parameter values until an unlearn is done
        """
        if hasattr(filename, 'name') and hasattr(filename, 'read'):
            filename = filename.name
        if isinstance(filename,str):
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
            if issubclass(t, types.InstanceType):
                tname = p.__class__.__name__
            else:
                tname = t.__name__
            raise TypeError("Parameter must be of type IrafPar (value: "+ \
                            tname+", type: "+str(t)+", object: "+repr(p)+")")
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
        # compare minimal set of parameter attributes
        thislist = self._getConsistentList()
        otherlist = other._getConsistentList()
        if thislist == otherlist:
            return 1
        else:
            if Verbose>0:
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
                j = j+1
        return dpar

    def clearFlags(self):
        """Clear all status flags for all parameters"""
        for p in self.__pars: p.setFlags(0)

    def setAllFlags(self):
        """Set all status flags to indicate parameters were set on cmdline"""
        for p in self.__pars: p.setCmdline()

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
            self.setParam(name,value)

    def __len__(self): return len(self.__pars)

    # public accessor functions for attributes

    def hasPar(self,param):
        """Test existence of parameter named param"""
        if self.__psetlist: self.__addPsetParams()
        param = irafutils.untranslateName(param)
        return self.__pardict.has_key(param)

    def getFilename(self):
        return self.__filename

    def getParList(self, docopy=0):
        if docopy:
            # return copy of the list if docopy flag set
            pars = copy.deepcopy(self.__pars)
            for p in pars: p.setFlags(0)
            return pars
        else:
            # by default return the list itself
            return self.__pars

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
        if isinstance(value,str) and value[:1] == ")":
            # parameter indirection: ')task.param'
            try:
                task = iraf.getTask(self.__name)
                value = task.getParam(value[1:],native=native,mode="h")
            except KeyError:
                # if task is not known, use generic function to get param
                value = iraf.clParGet(value[1:],native=native,mode="h",
                        prompt=prompt)
        return value

    def setParam(self, param, value, scope='', check=0, idxHint=None):
        """Set task parameter 'param' to value (with minimum-matching).
           scope, idxHint, and check are included for use as a task object
           but they are currently ignored."""
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
            try:
                param = (self.getParObject(key).name, '')
            except KeyError, e:
                # maybe it is pset.param
                i = key.find('.')
                if i<=0:
                    raise e
                param = (self.getParObject(key[:i]).name, key[i+1:])
            if fullkw.has_key(param):
                if param[1]:
                    pname = '.'.join(param)
                else:
                    pname = param[0]
                raise SyntaxError("Multiple values given for parameter " +
                        pname + " in task " + self.__name)
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
            param = (self.__pars[ipar].name, '')
            if fullkw.has_key(param):
                raise SyntaxError("Multiple values given for parameter " +
                        param[0] + " in task " + self.__name)
            fullkw[param] = value
            ipar = ipar+1

        # now set all keyword parameters
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
                # pset parameter - get parameter object from task
                p = p.get().getParObject(tail)
            p.set(value)
            p.setFlags(_cmdlineFlag)
            if p.mode != "h": nargs = nargs+1

        # Number of arguments on command line, $nargs, is used by some IRAF
        # tasks (e.g. imheader).
        self.setParam('$nargs',nargs)

    def eParam(self):
        epar.epar(self)

    def tParam(self):
        tpar.tpar(self)

    def lParam(self,verbose=0):
        print self.lParamStr(verbose=verbose)

    def lParamStr(self,verbose=0):
        """List the task parameters"""
        retval = []
        # Do the non-hidden parameters first
        for i in xrange(len(self.__pars)):
            p = self.__pars[i]
            if p.mode != 'h':
                if Verbose>0 or p.name != '$nargs':
                    retval.append(p.pretty(verbose=verbose or Verbose>0))
        # Now the hidden parameters
        for i in xrange(len(self.__pars)):
            p = self.__pars[i]
            if p.mode == 'h':
                if Verbose>0 or p.name != '$nargs':
                    retval.append(p.pretty(verbose=verbose or Verbose>0))
        return '\n'.join(retval)

    def dParam(self, taskname="", cl=1):
        """Dump the task parameters in executable form

        Default is to write CL version of code; if cl parameter is
        false, writes Python executable code instead.
        """
        if taskname and taskname[-1:] != ".": taskname = taskname + "."
        for i in xrange(len(self.__pars)):
            p = self.__pars[i]
            if p.name != '$nargs':
                print "%s%s" % (taskname,p.dpar(cl=cl))
        if cl: print "# EOF"

    def saveParList(self, filename=None, comment=None):
        """Write .par file data to filename (string or filehandle)"""
        if filename is None:
            filename = self.__filename
        if not filename:
            raise ValueError("No filename specified to save parameters")
        if hasattr(filename,'write'):
            fh = filename
        else:
            absFileName = iraf.Expand(filename)
            absDir = os.path.dirname(absFileName)
            if len(absDir) and not os.path.isdir(absDir): os.makedirs(absDir)
            fh = open(absFileName,'w')
        nsave = len(self.__pars)
        if comment:
            fh.write('# '+comment+'\n')
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

    # these methods are provided so an IrafParList can be treated like
    # an IrafTask object by epar (and other modules)

    def getDefaultParList(self):
        return self.getParList()

    def getName(self):
        return self.__filename

    def getPkgname(self):
        return ''

    def run(self, *args, **kw):
        pass

def _printVerboseDiff(list1, list2):
    """Print description of differences between parameter lists"""
    pd1, hd1 = _extractDiffInfo(list1)
    pd2, hd2 = _extractDiffInfo(list2)
    _printHiddenDiff(pd1,hd1,pd2,hd2)       # look for hidden/positional changes
    _printDiff(pd1, pd2, 'positional')      # compare positional parameters
    _printDiff(hd1, hd2, 'hidden')          # compare hidden parameters

def _extractDiffInfo(list):
    hflag = -1
    pd = {}
    hd = {}
    for key, value in list.items():
        if value[1] == hflag:
            hd[key] = value
        else:
            pd[key] = value
    return (pd,hd)

def _printHiddenDiff(pd1,hd1,pd2,hd2):
    for key in pd1.keys():
        if hd2.has_key(key):
            print "Parameter `%s' is hidden in list 2 but not list 1" % (key,)
            del pd1[key]
            del hd2[key]
    for key in pd2.keys():
        if hd1.has_key(key):
            print "Parameter `%s' is hidden in list 1 but not list 2" % (key,)
            del pd2[key]
            del hd1[key]

def _printDiff(pd1, pd2, label):
    if pd1 == pd2:
        return
    noextra = 1
    k1 = pd1.keys()
    k1.sort()
    k2 = pd2.keys()
    k2.sort()
    if k1 != k2:
        # parameter name lists differ
        i1 = 0
        i2 = 0
        noextra = 0
        while i1<len(k1) and i2<len(k2):
            key1 = k1[i1]
            key2 = k2[i2]
            if key1 == key2:
                i1 = i1+1
                i2 = i2+1
            else:
                # one or both parameters missing
                if not pd2.has_key(key1):
                    print "Extra %s parameter `%s' (type `%s') in list 1" % \
                            (label, key1, pd1[key1][0])
                    # delete the extra parameter
                    del pd1[key1]
                    i1 = i1+1
                if not pd1.has_key(key2):
                    print "Extra %s parameter `%s' (type `%s') in list 2" % \
                            (label, key2, pd2[key2][0])
                    del pd2[key2]
                    i2 = i2+1
        # other parameters must be missing
        while i1<len(k1):
            key1 = k1[i1]
            print "Extra %s parameter `%s' (type `%s') in list 1" % \
                    (label, key1, pd1[key1][0])
            del pd1[key1]
            i1 = i1+1
        while i2<len(k2):
            key2 = k2[i2]
            print "Extra %s parameter `%s' (type `%s') in list 2" % \
                    (label, key2, pd2[key2][0])
            del pd2[key2]
            i2 = i2+1
    # remaining parameters are in both lists
    # check for differing order or type, but ignore order if there
    # were extra parameters
    for key in pd1.keys():
        val1 = pd1[key]
        val2 = pd2[key]
        if pd1[key] != pd2[key]:
            mm = []
            type1, order1 = pd1[key]
            type2, order2 = pd2[key]
            if noextra and order1 != order2:
                mm.append("order disagreement")
            if type1 != type2:
                mm.append("type disagreement (`%s' vs. `%s')" % (type1, type2))
            print "Parameter `%s': %s" % (key, ", ".join(mm))


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
    if _specialUseParFileDict == None:
        _specialUseParFileDict = {}

    # If the caller gave us a dirToCheck, use only it, otherwise check the
    # usual places (which calls us recursively).
    if dirToCheck == None:
        # Check the auxilliary par dir
        uparmAux = iraf.envget("uparm_aux","")
        if 'UPARM_AUX' in os.environ: uparmAux = os.environ['UPARM_AUX']
        if len(uparmAux) > 0:
            _updateSpecialParFileDict(dirToCheck=uparmAux, strict=True)
            # If the _updateSpecialParFileDict processing is found to be
            # be taking too long, we could easily add a global flag here like
            # _alreadyCheckedUparmAux = True

        # Also check the current directory
        _updateSpecialParFileDict(dirToCheck=os.getcwd())
        # For performance, note that there is nothing yet in place to stop us
        # from rereading a large dir of par files every time this is called

        return # we've done enough

    # Do a glob in the given dir
    flist = glob.glob(dirToCheck+"/*.par")
    if len(flist) <= 0: return

    # At this point, we have files.  Foreach, figure out the task and
    # package it is for, and add it's pathname to the dict.
    for supfname in flist:
        buf = []
        try:
            supfile = open(supfname, 'r')
            buf = supfile.readlines()
            supfile.close()
        except:
            pass
        if len(buf) < 1:
            warning("Unable to read special use parameter file: "+supfname,
                    level = -1)
            continue

        # get task and pkg names, and verify this is a correct file
        tupKey = None
        for line in buf:
            mo = _re_taskmeta.match(line)
            if mo:
                # the syntax is right,  get the task and pkg names
                tupKey = ( mo.group(1), mo.group(2) )
                break # only one TASKMETA line per file

        if tupKey:
            if tupKey in _specialUseParFileDict:
                supflist = _specialUseParFileDict[tupKey]
                if supfname not in supflist:
                    _specialUseParFileDict[tupKey].append(supfname)
            else:
                _specialUseParFileDict[tupKey] = [supfname,]
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
    if _specialUseParFileDict == None:
        _updateSpecialParFileDict()

    tupKey = (taskName, pkgName)
    if tupKey in _specialUseParFileDict:
        if not pathName in _specialUseParFileDict[tupKey]:
            _specialUseParFileDict[tupKey].append(pathName)
    else:
        _specialUseParFileDict[tupKey] = [pathName,]


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
        line = lines.pop().strip()
        # skip comments and blank lines
        # "..." is weird line that occurs in cl.par
        if len(line)>0 and line[0] != '#' and line != "...":
            # Append next line if this line ends with continuation character.
            while line[-1:] == "\\":
                # odd number of trailing backslashes means this is continuation
                if (len(_re_bstrail.search(line).group()) % 2 == 1):
                    try:
                        line = line[:-1] + lines.pop().rstrip()
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
                            sline = line.split('\n')
                            raise SyntaxError(filename + ": Unmatched quote\n" +
                                    sline[0])
                        line = line + '\n' + nline.rstrip()
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
                par = IrafParFactory(flist, strict=strict)
            except KeyboardInterrupt:
                raise
            except Exception, exc:
                #XXX Shouldn't catch all exceptions here -- this could
                #XXX screw things up
                if Verbose:
                    import traceback
                    traceback.print_exc()
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

# -----------------------------------------------------------------------------

def test_IrafParList(fout = sys.stdout):
    """ Test the IrafParList class """
    # check our input (may be stdout)
    assert hasattr(fout, 'write'), "Input not a file object: "+str(fout)

    # create default, empty parlist for task 'bobs_task'
    pl = IrafParList('bobs_pizza', 'bobs_pizza.par')
    x = pl.getName()
    assert x == 'bobs_pizza.par', "Unexpected name: "+str(x)
    x = pl.getFilename()
    assert x == 'bobs_pizza.par', "Unexpected fname: "+str(x)
    x = pl.getPkgname()
    assert x == '', "Unexpected pkg name: "+str(x)
    assert not pl.hasPar('jojo'), "How did we get jojo?"
    assert pl.hasPar('mode'), "We should have only: mode"
    # length of 'empty' list is 2 - it has 'mode' and '$nargs'
    assert len(pl) == 2, "Unexpected length: "+str(len(pl))
    fout.write("lParam should show 1 par (mode)\n"+pl.lParamStr()+'\n')

    # let's add some pars
    par1 = basicpar.parFactory( \
           ('caller','s','a','Ima Hungry','',None,'person calling Bobs'), True)
    x = par1.dpar().strip()
    assert x == "caller = 'Ima Hungry'", "par1 is off: "+str(x)
    par2 = basicpar.parFactory( \
           ('diameter','i','a','12','',None,'pizza size'), True)
    x = par2.dpar().strip()
    assert x == "diameter = 12", "par2 is off: "+str(x)
    par3 = basicpar.parFactory( \
           ('pi','r','a','3.14159','',None,'Bob makes circles!'), True)
    x = par3.dpar().strip()
    assert x == "pi = 3.14159", "par3 is off: "+str(x)
    par4 = basicpar.parFactory( \
           ('delivery','b','a','yes','',None,'delivery? (or pickup)'), True)
    x = par4.dpar().strip()
    assert x == "delivery = yes", "par4 is off: "+str(x)
    par5 = basicpar.parFactory( \
           ('topping','s','a','peps','|toms|peps|olives',None,'the choices'), True)
    x = par5.dpar().strip()
    assert x == "topping = 'peps'", "par5 is off: "+str(x)

    pl.addParam(par1)
    assert len(pl) == 3, "Unexpected length: "+str(len(pl))
    pl.addParam(par2)
    pl.addParam(par3)
    pl.addParam(par4)
    pl.addParam(par5)
    assert len(pl) == 7, "Unexpected length: "+str(len(pl))

    # now we have a decent IrafParList to play with - test some
    fout.write("lParam should show 6 actual pars (our 5 + mode)\n"+\
               pl.lParamStr()+'\n')
    assert pl.__doc__ == 'List of Iraf parameters',"__doc__ = "+str(pl.__doc__)
    x = sorted(pl.getAllMatches(''))
    assert x==['$nargs','caller','delivery','diameter','mode','pi','topping'],\
           "Unexpected all: "+str(x)
    x = sorted(pl.getAllMatches('d'))
    assert x == ['delivery','diameter'], "Unexpected d's: "+str(x)
    x = sorted(pl.getAllMatches('jojo'))
    assert x == [], "Unexpected empty list: "+str(x)
    x = pl.getParDict()
    assert 'caller' in x, "Bad dict? "+str(x)
    x = pl.getParList()
    assert par1 in x, "Bad list? "+str(x)
    assert pl.hasPar('topping'), "hasPar call failed"
    # change a par val
    pl.setParam('topping','olives') # should be no prob
    assert 'olives' == pl.getParDict()['topping'].value, \
           "Topping error: "+str(pl.getParDict()['topping'].value)
    try:
       # the following setParam should fail - not in choice list
       pl.setParam('topping','peanutbutter') # oh the horror
       raise RuntimeError("The bad setParam didn't fail?")
    except ValueError:
       pass

    # Now try some direct access (also tests IrafPar basics)
    assert pl.caller == "Ima Hungry", 'Ima? '+pl.getParDict()['caller'].value
    pl.pi = 42
    assert pl.pi == 42.0, "pl.pi not 42, ==> "+str(pl.pi)
    try:
       pl.pi = 'strings are not allowed' # should throw
       raise RuntimeError("The bad pi assign didn't fail?")
    except ValueError:
       pass
    pl.diameter = '9.7' # ok, string to float to int
    assert pl.diameter == 9, "pl.diameter?, ==> "+str(pl.diameter)
    try:
       pl.diameter = 'twelve' # fails, not parseable to an int
       raise RuntimeError("The bad diameter assign didn't fail?")
    except ValueError:
       pass
    assert pl.diameter == 9, "pl.diameter after?, ==> "+str(pl.diameter)
    pl.delivery = False # converts
    assert pl.delivery == no, "pl.delivery not no? "+str(pl.delivery)
    pl.delivery = 1 # converts
    assert pl.delivery == yes, "pl.delivery not yes? "+str(pl.delivery)
    pl.delivery = 'NO' # converts
    assert pl.delivery == no, "pl.delivery not NO? "+str(pl.delivery)
    try:
       pl.delivery = "maybe, if he's not being recalcitrant"
       raise RuntimeError("The bad delivery assign didn't fail?")
    except ValueError:
       pass
    try:
       pl.topping = 'peanutbutter' # try again
       raise RuntimeError("The bad topping assign didn't fail?")
    except ValueError:
       pass
    try:
       x = pl.pumpkin_pie
       raise RuntimeError("The pumpkin_pie access didn't fail?")
    except KeyError:
       pass

    # If we get here, then all is well
    # sys.exit(0)
    fout.write("Test successful\n")
    return pl


if __name__ == '__main__':
    pl = test_IrafParList()
