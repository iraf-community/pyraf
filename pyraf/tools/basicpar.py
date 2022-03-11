"""basicpar.py -- General base class for parameter objects.  Broken out
                  from PyRAF's IrafPar class.

$Id$
"""
import re
import sys
from . import irafutils, minmatch
from .irafglobals import INDEF, Verbose, yes, no

int_types = (int, )


# container class used for __deepcopy__ method
class _EmptyClass:
    pass


# -----------------------------------------------------
# Warning (non-fatal) error.  Raise an exception if in
# strict mode, or print a message if Verbose is on.
# -----------------------------------------------------

# Verbose (set irafglobals.py) determines
# whether warning messages are printed when errors are found.  The
# strict parameter to various methods and functions can be set to
# raise an exception on errors; otherwise we do our best to work
# around errors, only raising an exception for really serious,
# unrecoverable problems.

def warning(msg, strict=0, exception=SyntaxError, level=0):
    if strict:
        raise exception(msg)
    elif Verbose>level:
        sys.stdout.flush()
        sys.stderr.write('Warning: %s' % msg)
        if msg[-1:] != '\n': sys.stderr.write('\n')

# -----------------------------------------------------
# basic parameter factory
# -----------------------------------------------------

_string_types = [ 's', 'f', 'struct', 'z' ]
_real_types = [ 'r', 'd' ]

def parFactory(fields, strict=0):

    """parameter factory function

    fields is a list of the comma-separated fields (as in the .par file).
    Each entry is a string or None (indicating that field was omitted.)

    Set the strict parameter to a non-zero value to do stricter parsing
    (to find errors in the input)"""

    if len(fields) < 3 or None in fields[0:3]:
        raise SyntaxError("At least 3 fields must be given")
    type = fields[1]
    if type in _string_types:
        return IrafParS(fields,strict)
    elif type == 'R':
        return StrictParR(fields,1)
    elif type in _real_types:
        return IrafParR(fields,strict)
    elif type == "I":
        return StrictParI(fields,1)
    elif type == "i":
        return IrafParI(fields,strict)
    elif type == "b":
        return IrafParB(fields,strict)
    elif type == "ar":
        return IrafParAR(fields,strict)
    elif type == "ai":
        return IrafParAI(fields,strict)
    elif type == "as":
        return IrafParAS(fields,strict)
    elif type == "ab":
        return IrafParAB(fields,strict)
    elif type[:1] == "a":
        raise SyntaxError("Cannot handle arrays of type %s" % type)
    else:
        raise SyntaxError("Cannot handle parameter type %s" % type)


# --------------------------------------------------------
# Publish the (simple) algorithm for combining scope+name
# --------------------------------------------------------

def makeFullName(parScope, parName):
    """ Create the fully-qualified name (inclues scope if used) """
    # Skip scope (and leading dot) if no scope, even in cases where scope
    # IS used for other pars in the same task.
    if parScope:
        return parScope+'.'+parName
    else:
        return parName

# -----------------------------------------------------
# Set up minmatch dictionaries for parameter fields
# -----------------------------------------------------

flist = ("p_name", "p_xtype", "p_type", "p_mode", "p_prompt", "p_scope",
         "p_value", "p_default", "p_filename", "p_maximum", "p_minimum")
_getFieldDict = minmatch.MinMatchDict()
for field in flist: _getFieldDict.add(field, field)

flist = ("p_prompt", "p_value", "p_filename", "p_maximum", "p_minimum", "p_mode", "p_scope")
_setFieldDict = minmatch.MinMatchDict()
for field in flist: _setFieldDict.add(field, field)
del flist, field

# utility function to check whether string is a parameter field

def isParField(s):
    """Returns true if string s appears to be a parameter field"""
    try:
        return (s[:2] == "p_") and s in _getFieldDict
    except minmatch.AmbiguousKeyError:
        # If ambiguous match, assume it is a parameter field.
        # An exception will doubtless be raised later, but
        # there's really no good choice here.
        return 1

# basic IrafPar attributes
# IrafPar's are protected in setattr against adding arbitrary attributes,
# and this dictionary is used as a helper in instance initialization
_IrafPar_attr_dict = {
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
        "scope" : None,
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

    def __init__(self,fields,strict=0):
        orig_len = len(fields)
        if orig_len < 3 or None in fields[0:3]:
            raise SyntaxError("At least 3 fields must be given")
        #
        # all the attributes that are going to get defined
        #
        self.__dict__.update(_IrafPar_attr_dict)
        self.name   = fields[0]
        self.type   = fields[1]
        self.mode   = fields[2]
        self.scope  = None # simple default; may be unused
        #
        # put fields into appropriate attributes
        #
        while len(fields) < 7: fields.append(None)
        #
        self.value = self._coerceValue(fields[3],strict)
        if fields[4] is not None and '|' in fields[4]:
            self._setChoice(fields[4].strip(),strict)
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
        except ValueError as e:
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

    def setScope(self,value=''):
        """Set scope value.  Written this way to not change the
           standard set of fields in the comma-separated list. """
        # set through dictionary to avoid extra calls to __setattr__
        self.__dict__['scope'] = value

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
            if mode is None: mode = 'ql' # that is, iraf.cl.mode
            if "h" in mode and "l" not in mode:
                return 0
        return 1

    #--------------------------------------------
    # other public methods
    #--------------------------------------------

    def getPrompt(self):
        """Alias for getWithPrompt() for backward compatibility"""
        return self.getWithPrompt()

    def getWithPrompt(self):
        """Interactively prompt for parameter value"""
        if self.prompt:
            pstring = self.prompt.split("\n")[0].strip()
        else:
            pstring = self.name
        if self.choice:
            schoice = list(map(self.toString, self.choice))
            pstring = pstring + " (" + "|".join(schoice) + ")"
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
        # don't redirect stdin/out unless redirected filehandles are also ttys
        # or unless originals are NOT ttys
        stdout = sys.__stdout__
        try:
            if sys.stdout.isatty() or not stdout.isatty():
                stdout = sys.stdout
        except AttributeError:
            pass
        stdin = sys.__stdin__
        try:
            if sys.stdin.isatty() or not stdin.isatty():
                stdin = sys.stdin
        except AttributeError:
            pass
        # print prompt, suppressing both newline and following space
        stdout.write(pstring)
        stdout.flush()
        ovalue = irafutils.tkreadline(stdin)
        value = ovalue.strip()
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
                    stdout.flush()
                    raise EOFError("EOF on parameter prompt")
                print("Error: specify a value for the parameter")
            except ValueError as e:
                print(str(e))
            stdout.write(pstring)
            stdout.flush()
            ovalue = irafutils.tkreadline(stdin)
            value = ovalue.strip()

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
        if v in [None, INDEF] or (isinstance(v,str) and v[:1] == ")"):
            return v
        elif v == "":
            # most parameters treat null string as omitted value
            return None
        elif self.choice is not None and v not in self.choiceDict:
            schoice = list(map(self.toString, self.choice))
            schoice = "|".join(schoice)
            raise ValueError("Parameter %s: "
                    "value %s is not in choice list (%s)" %
                    (self.name, str(v), schoice))
        elif (self.min not in [None, INDEF] and v<self.min):
            raise ValueError("Parameter %s: "
                    "value `%s' is less than minimum `%s'" %
                    (self.name, str(v), str(self.min)))
        elif (self.max not in [None, INDEF] and v>self.max):
            raise ValueError("Parameter %s: "
                    "value `%s' is greater than maximum `%s'" %
                    (self.name, str(v), str(self.max)))
        return v

    def dpar(self, cl=1):
        """Return dpar-style executable assignment for parameter

        Default is to write CL version of code; if cl parameter is
        false, writes Python executable code instead.
        """
        sval = self.toString(self.value, quoted=1)
        if not cl:
            if sval == "": sval = "None"
        s = "%s = %s" % (self.name, sval)
        return s

    def fullName(self):
        """ Return the fully-qualified name (inclues scope if used) """
        return makeFullName(self.scope, self.name) # scope can be None or ''

    def pretty(self,verbose=0):
        """Return pretty list description of parameter"""
        # split prompt lines and add blanks in later lines to align them
        plines = self.prompt.split('\n')
        for i in range(len(plines)-1): plines[i+1] = 32*' ' + plines[i+1]
        plines = '\n'.join(plines)
        namelen = min(len(self.name), 12)
        pvalue = self.get(prompt=0,lpar=1)
        alwaysquoted = ['s', 'f', '*gcur', '*imcur', '*ukey', 'pset']
        if self.type in alwaysquoted and self.value is not None: pvalue = '"' + pvalue + '"'
        if self.mode == "h":
            s = "%13s = %-15s %s" % ("("+self.name[:namelen],
                                    pvalue+")", plines)
        else:
            s = "%13s = %-15s %s" % (self.name[:namelen],
                                    pvalue, plines)
        if not verbose: return s

        if self.choice is not None:
            s = s + "\n" + 32*" " + "|"
            nline = 33
            for i in range(len(self.choice)):
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
            schoice = list(map(self.toString, self.choice))
            schoice.insert(0,'')
            schoice.append('')
            fields[4] = repr('|'.join(schoice))
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
            sprompt = sprompt.replace(r'\012', '\n')
            sprompt = sprompt.replace(r'\n', '\n')
            fields[6] = sprompt
        # delete trailing null parameters
        for i in [6,5,4]:
            if fields[i] != "": break
            del fields[i]
        if dolist:
            return fields
        else:
            return ','.join(fields)

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
        except SyntaxError as e:
            if field in _IrafPar_attr_dict:
                # handle odd-ball case of new code accessing par's new
                # attr (e.g. scope), with old-code-cached version of par
                return _IrafPar_attr_dict[field] # return unused default
            else:
                raise AttributeError(str(e))

    def __setattr__(self,attr,value):
        # don't allow any new parameters to be added
        if attr in self.__dict__:
            self.__dict__[attr] = value
        elif isParField(attr):
            #XXX should check=0 be used here?
            self._setField(value, attr)
        else:
            raise AttributeError("No attribute %s for parameter %s" %
                    (attr, self.name))

    def __deepcopy__(self, memo):
        """Deep copy of this parameter object"""
        new = _EmptyClass()
        # shallow copy of dictionary suffices for most attributes
        new.__dict__ = self.__dict__.copy()
        # value, choice may be lists of atomic items
        if isinstance(self.value, list):
            new.value = list(self.value)
        if isinstance(self.choice, list):
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
        self.__dict__.clear()
        self.__dict__.update(state)
        if self.choice is not None:
            self._setChoiceDict()

    def __str__(self):
        """Return readable description of parameter"""
        s = "<" + self.__class__.__name__ + " " + self.name + " " + self.type
        s = s + " " + self.mode + " " + repr(self.value)
        if self.choice is not None:
            schoice = list(map(self.toString, self.choice))
            s = s + " |" + "|".join(schoice) + "|"
        else:
            s = s + " " + repr(self.min) + " " + repr(self.max)
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
        clist = _getChoice(s,strict)
        self.choice = list(map(self._coerceValue, clist))
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
                self.getWithPrompt()
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
                self.getWithPrompt()

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
        except KeyError as e:
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
        elif field == "p_scope": return self.scope
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
                    schoice = list(map(self.toString, self.choice))
                    return "|" + "|".join(schoice) + "|"
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
        except KeyError as e:
            raise SyntaxError("Cannot set field " + field +
                    " for parameter " + self.name + "\n" + str(e))
        if field == "p_prompt":
            self.prompt = irafutils.removeEscapes(irafutils.stripQuotes(value))
        elif field == "p_value":
            self.set(value,check=check)
        elif field == "p_filename":
            # this is only relevant for list parameters (*imcur, *gcur, etc.)
            self.set(value,check=check)
        elif field == "p_scope":
            self.scope = value
        elif field == "p_maximum":
            self.max = self._coerceOneValue(value)
        elif field == "p_minimum":
            if isinstance(value,str) and '|' in value:
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
        raise NotImplementedError("class IrafPar cannot be used directly")


# -----------------------------------------------------
# IRAF array parameter base class
# -----------------------------------------------------

class IrafArrayPar(IrafPar):

    """IRAF array parameter class"""

    def __init__(self,fields,strict=0):
        orig_len = len(fields)
        if orig_len < 3:
            raise SyntaxError("At least 3 fields must be given")
        #
        # all the attributes that are going to get defined
        #
        self.__dict__.update(_IrafPar_attr_dict)
        self.name   = fields[0]
        self.type   = fields[1]
        self.mode   = fields[2]
        self.__dict__['shape'] = None
        #
        # for array parameters, dimensions follow mode field
        # and values come from fields after prompt
        #
        if len(fields)<4 or fields[3] is None:
            raise ValueError("Missing dimension field for array parameter")
        ndim = int(fields[3])
        if len(fields) < 4+2*ndim:
            raise ValueError("Missing array shape fields for array parameter")
        shape = []
        array_size = 1
        for i in range(ndim):
            shape.append(int(fields[4+2*i]))
            array_size = array_size*shape[-1]
        self.shape = tuple(shape)
        nvstart = 7+2*ndim
        fields.extend([""]*(nvstart-len(fields)))
        fields.extend([None]*(nvstart+array_size-len(fields)))
        if len(fields) > nvstart+array_size:
            raise SyntaxError("Too many values for array" +
                    " for parameter " + self.name)
        #
        self.value = [None]*array_size
        self.value = self._coerceValue(fields[nvstart:],strict)
        if fields[nvstart-3] is not None and '|' in fields[nvstart-3]:
            self._setChoice(fields[nvstart-3].strip(),strict)
            if fields[nvstart-2] is not None:
                if orig_len < nvstart:
                    warning("Max value illegal when choice list given" +
                                    " for parameter " + self.name +
                                    " (probably missing comma)",
                                    strict)
                    # try to recover by assuming max string is prompt
                    #XXX risky -- all init values might be off by one
                    fields[nvstart-1] = fields[nvstart-2]
                    fields[nvstart-2] = None
                else:
                    warning("Max value illegal when choice list given" +
                            " for parameter " + self.name, strict)
        else:
            self.min = self._coerceOneValue(fields[nvstart-3],strict)
            self.max = self._coerceOneValue(fields[nvstart-2],strict)
        if fields[nvstart-1] is not None:
            self.prompt = irafutils.removeEscapes(
                                            irafutils.stripQuotes(fields[nvstart-1]))
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
        except ValueError as e:
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
        array_size = 1
        for d in self.shape:
            array_size = d*array_size
        ndim = len(self.shape)
        fields = (7+2*ndim+len(self.value))*[""]
        fields[0] = self.name
        fields[1] = self.type
        fields[2] = self.mode
        fields[3] = str(ndim)
        next = 4
        for d in self.shape:
            fields[next] = str(d); next += 1
            fields[next] = '1';    next += 1
        nvstart = 7+2*ndim
        if self.choice is not None:
            schoice = list(map(self.toString, self.choice))
            schoice.insert(0,'')
            schoice.append('')
            fields[nvstart-3] = repr('|'.join(schoice))
        elif self.min not in [None,INDEF]:
            fields[nvstart-3] = self.toString(self.min,quoted=quoted)
        # insert an escaped line break before min field
        if quoted:
            fields[nvstart-3] = '\\\n' + fields[nvstart-3]
        if self.max not in [None,INDEF]:
            fields[nvstart-2] = self.toString(self.max,quoted=quoted)
        if self.prompt:
            if quoted:
                sprompt = repr(self.prompt)
            else:
                sprompt = self.prompt
            # prompt can have embedded newlines (which are printed)
            sprompt = sprompt.replace(r'\012', '\n')
            sprompt = sprompt.replace(r'\n', '\n')
            fields[nvstart-1] = sprompt
        for i in range(len(self.value)):
            fields[nvstart+i] = self.toString(self.value[i],quoted=quoted)
        # insert an escaped line break before value fields
        if dolist:
            return fields
        else:
            fields[nvstart] = '\\\n' + fields[nvstart]
            return ','.join(fields)

    def dpar(self, cl=1):
        """Return dpar-style executable assignment for parameter

        Default is to write CL version of code; if cl parameter is
        false, writes Python executable code instead.  Note that
        dpar doesn't even work for arrays in the CL, so we just use
        Python syntax here.
        """
        sval = list(map(self.toString, self.value, len(self.value)*[1]))
        for i in range(len(sval)):
            if sval[i] == "":
                sval[i] = "None"
        s = "%s = [%s]" % (self.name, ', '.join(sval))
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
            sumindex = self._sumindex(index)
            try:
                if native:
                    return self.value[sumindex]
                else:
                    return self.toString(self.value[sumindex])
            except IndexError:
                # should never happen
                raise SyntaxError("Illegal index [" + repr(sumindex) +
                        "] for array parameter " + self.name)
        elif native:
            # return object itself for an array because it is
            # indexable, can have values assigned, etc.
            return self
        else:
            # return blank-separated string of values for array
            return str(self)

    def set(self, value, field=None, index=None, check=1):
        """Set value of this parameter from a string or other value.
        Field is optional parameter field (p_prompt, p_minimum, etc.)
        Index is optional array index (zero-based).  Set check=0 to
        assign the value without checking to see if it is within
        the min-max range or in the choice list."""
        if index is not None:
            sumindex = self._sumindex(index)
            try:
                value = self._coerceOneValue(value)
                if check:
                    self.value[sumindex] = self.checkOneValue(value)
                else:
                    self.value[sumindex] = value
                return
            except IndexError:
                # should never happen
                raise SyntaxError("Illegal index [" + repr(sumindex) +
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
        for i in range(len(v)):
            self.checkOneValue(v[i],strict=strict)
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
        # This differs from non-arrays in that it returns a
        # print string with just the values.  That's because
        # the object itself is returned as the native value.
        sv = list(map(str, self.value))
        for i in range(len(sv)):
            if self.value[i] is None:
                sv[i] = "INDEF"
        return ' '.join(sv)

    def __len__(self):
        return len(self.value)

    #--------------------------------------------
    # private methods
    #--------------------------------------------

    def _sumindex(self, index=None):
        """Convert tuple index to 1-D index into value"""
        try:
            ndim = len(index)
        except TypeError:
            # turn index into a 1-tuple
            index = (index,)
            ndim = 1
        if len(self.shape) != ndim:
            raise ValueError("Index to %d-dimensional array %s has too %s dimensions" %
                (len(self.shape), self.name, ["many","few"][len(self.shape) > ndim]))
        sumindex = 0
        for i in range(ndim-1,-1,-1):
            index1 = index[i]
            if index1 < 0 or index1 >= self.shape[i]:
                raise ValueError("Dimension %d index for array %s is out of bounds (value=%d)" %
                    (i+1, self.name, index1))
            sumindex = index1 + sumindex*self.shape[i]
        return sumindex

    def _getPType(self):
        """Get underlying datatype for this parameter (strip off 'a' array params)"""
        return self.type[1:]

    def _coerceValue(self,value,strict=0):
        """Coerce parameter to appropriate type

        Should accept None or null string.  Must be an array.
        """
        try:
            if isinstance(value,str):
                # allow single blank-separated string as input
                value = value.split()
            if len(value) != len(self.value):
                raise IndexError
            v = len(self.value)*[0]
            for i in range(len(v)):
                v[i] = self._coerceOneValue(value[i],strict)
            return v
        except (IndexError, TypeError):
            raise ValueError("Value must be a " + repr(len(self.value)) +
                    "-element array for " + self.name)

    def isLegal(self):
        """Dont call checkValue for arrays"""
        try:
            return self.value is not None
        except ValueError:
            return 0


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
            return repr(value)
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
            except minmatch.AmbiguousKeyError:
                clist = self.choiceDict.getall(v)
                raise ValueError("Parameter %s: "
                        "ambiguous value `%s', could be %s" %
                        (self.name, str(v), "|".join(clist)))
            except KeyError:
                raise ValueError("Parameter %s: "
                        "value `%s' is not in choice list (%s)" %
                        (self.name, str(v), "|".join(self.choice)))
        elif (self.min is not None and v<self.min):
            raise ValueError("Parameter %s: "
                    "value `%s' is less than minimum `%s'" %
                    (self.name, str(v), str(self.min)))
        elif (self.max is not None and v>self.max):
            raise ValueError("Parameter %s: "
                    "value `%s' is greater than maximum `%s'" %
                    (self.name, str(v), str(self.max)))
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
        elif isinstance(value,str):
            # strip double quotes and remove escapes before quotes
            return irafutils.removeEscapes(irafutils.stripQuotes(value))
        else:
            return str(value)

# -----------------------------------------------------
# IRAF string parameter class
# -----------------------------------------------------

class IrafParS(_StringMixin, IrafPar):

    """IRAF string parameter class"""
    pass

# -----------------------------------------------------
# IRAF string array parameter class
# -----------------------------------------------------

class IrafParAS(_StringMixin,IrafArrayPar):

    """IRAF string array parameter class"""
    pass

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
        elif isinstance(value,str):
            # presumably an indirection value ')task.name'
            if quoted:
                return repr(value)
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
        if value == INDEF:
            return INDEF
        elif value is None or value == "":
            return None
        elif value in (1, 1.0, yes, "yes", "YES", "y", "Y", True):
            return yes
        elif value in (0, 0.0, no,  "no",  "NO",  "n", "N", False):
            return no
        elif isinstance(value,str):
            v2 = irafutils.stripQuotes(value.strip())
            if v2 == "" or v2 == "INDEF" or \
                    ((not strict) and (v2.upper() == "INDEF")):
                return INDEF
            elif v2[0:1] == ")":
                # assume this is indirection -- just save it as a string
                return v2
        raise ValueError("Parameter %s: illegal boolean value %s or type %s" %
                (self.name, repr(value), str(type(value))))

# -----------------------------------------------------
# IRAF boolean parameter class
# -----------------------------------------------------

class IrafParB(_BooleanMixin,IrafPar):

    """IRAF boolean parameter class"""
    pass

# -----------------------------------------------------
# IRAF boolean array parameter class
# -----------------------------------------------------

class IrafParAB(_BooleanMixin,IrafArrayPar):

    """IRAF boolean array parameter class"""
    pass

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
        if value == INDEF:
            return INDEF
        elif value is None or isinstance(value,int):
            return value
        elif value in ("", "None", "NONE"):
            return None
        elif isinstance(value,float):
            # try converting to integer
            try:
                return int(value)
            except (ValueError, OverflowError):
                pass
        elif isinstance(value,str):
            s2 = irafutils.stripQuotes(value.strip())
            if s2 == "INDEF" or \
              ((not strict) and (s2.upper() == "INDEF")):
                return INDEF
            elif s2[0:1] == ")":
                # assume this is indirection -- just save it as a string
                return s2
            elif s2[-1:] == "x":
                # hexadecimal
                return int(s2[:-1],16)
            elif "." in s2:
                # try interpreting as a float and converting to integer
                try:
                    return int(float(s2))
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
        raise ValueError("Parameter %s: illegal integer value %s" %
                (self.name, repr(value)))

# -----------------------------------------------------
# IRAF integer parameter class
# -----------------------------------------------------

class IrafParI(_IntMixin,IrafPar):

    """IRAF integer parameter class"""
    pass

# -----------------------------------------------------
# IRAF integer array parameter class
# -----------------------------------------------------

class IrafParAI(_IntMixin,IrafArrayPar):

    """IRAF integer array parameter class"""
    pass

# -----------------------------------------------------
# Strict integer parameter mixin class
# -----------------------------------------------------

class _StrictIntMixin(_IntMixin):

    """Strict integer parameter mixin class"""

    #--------------------------------------------
    # public methods
    #--------------------------------------------

    def toString(self, value, quoted=0):
        return str(value)

    #--------------------------------------------
    # private methods
    #--------------------------------------------

    # coerce value to integer
    def _coerceOneValue(self,value,strict=0):
        if value is None or isinstance(value,int):
            return value
        elif isinstance(value,str):
            s2 = irafutils.stripQuotes(value.strip())
            if s2[-1:] == "x":
                # hexadecimal
                return int(s2[:-1],16)
            elif s2 == '':
                raise ValueError('Parameter '+self.name+ \
                      ': illegal empty integer value')
            else:
                # see if it is a stringified int
                try:
                    return int(s2)
                except ValueError:
                    pass
        # otherwise it is not a strict integer
        raise ValueError("Parameter %s: illegal integer value %s" %
                (self.name, repr(value)))

# -----------------------------------------------------
# Strict integer parameter class
# -----------------------------------------------------

class StrictParI(_StrictIntMixin,IrafPar):

    """Strict integer parameter class"""
    pass


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
        if value == INDEF:
            return INDEF
        elif value is None or isinstance(value,float):
            return value
        elif value in ("", "None", "NONE"):
            return None
        elif isinstance(value, int_types):
            return float(value)
        elif isinstance(value,str):
            s2 = irafutils.stripQuotes(value.strip())
            if s2 == "INDEF" or \
              ((not strict) and (s2.upper() == "INDEF")):
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
        raise ValueError("Parameter %s: illegal float value %s" %
                (self.name, repr(value)))


# -----------------------------------------------------
# IRAF real parameter class
# -----------------------------------------------------

class IrafParR(_RealMixin,IrafPar):

    """IRAF real parameter class"""
    pass

# -----------------------------------------------------
# IRAF real array parameter class
# -----------------------------------------------------

class IrafParAR(_RealMixin,IrafArrayPar):

    """IRAF real array parameter class"""
    pass

# -----------------------------------------------------
# Strict real parameter mixin class
# -----------------------------------------------------

class _StrictRealMixin(_RealMixin):

    """Strict real parameter mixin class"""

    #--------------------------------------------
    # public methods
    #--------------------------------------------

    def toString(self, value, quoted=0):
        return str(value)

    #--------------------------------------------
    # private methods
    #--------------------------------------------

    # coerce value to real
    def _coerceOneValue(self,value,strict=0):
        if value is None or isinstance(value,float):
            return value
        elif isinstance(value, int_types):
            return float(value)
        elif isinstance(value,str):
            s2 = irafutils.stripQuotes(value.strip())
            if s2 == '':
                raise ValueError('Parameter '+self.name+ \
                      ': illegal empty float value')
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
            # see if it's a stringified float
            try:
                return float(s2)
            except ValueError:
                raise ValueError("Parameter %s: illegal float value %s" %
                                 (self.name, repr(value)))
        # Otherwise it is not a strict float
        raise ValueError("Parameter %s: illegal float value %s" %
                         (self.name, repr(value)))


# -----------------------------------------------------
# Strict real parameter class
# -----------------------------------------------------

class StrictParR(_StrictRealMixin,IrafPar):

    """Strict real parameter class"""
    pass


# -----------------------------------------------------
# Utility routine for parsing choice string
# -----------------------------------------------------

_re_choice = re.compile(r'\|')

def _getChoice(s, strict):
    clist = s.split("|")
    # string is allowed to start and end with "|", so ignore initial
    # and final empty strings
    if not clist[0]: del clist[0]
    if len(clist)>1 and not clist[-1]: del clist[-1]
    return clist
