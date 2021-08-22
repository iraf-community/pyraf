"""cltoken.py: Token definition for CL parser
"""


#  Copyright (c) 1998-1999 John Aycock
#
#  Permission is hereby granted, free of charge, to any person obtaining
#  a copy of this software and associated documentation files (the
#  "Software"), to deal in the Software without restriction, including
#  without limitation the rights to use, copy, modify, merge, publish,
#  distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to
#  the following conditions:
#
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#  CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#  TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

#
#       Token class for IRAF CL parsing
#

from stsci.tools.irafglobals import INDEF
from stsci.tools import compmixin

verbose = 0


class Token(compmixin.ComparableMixin):

    def __init__(self, type=None, attr=None, lineno=None):
        self.type = type
        self.attr = attr
        self.lineno = lineno

    #
    #  Not all these may be needed:
    #
    #  _compare     required for GenericParser, required for
    #                       GenericASTMatcher only if your ASTs are
    #                       heterogeneous (i.e., AST nodes and tokens)
    #  __repr__     recommended for nice error messages in GenericParser
    #  __getitem__  only if you have heterogeneous ASTs
    #
    def _compare(self, other, method):
        if isinstance(other, Token):
            return method(self.type, other.type)
        else:
            return method(self.type, other)

    def __hash__(self):
        return hash(self.type)

    def verboseRepr(self):
        if self.attr:
            return self.type + '(' + self.attr + ')'
        else:
            return self.type

    def __repr__(self):
        global verbose
        if verbose:
            return self.verboseRepr()
        else:
            if self.type in ["STRING", "QSTRING"]:
                # add quotes to strings
                # but replace double escapes with single escapes
                return repr(self.attr).replace('\\\\', '\\')
            else:
                rv = self.attr
                if rv is None:
                    rv = self.type
                return rv

    def __getitem__(self, i):
        raise IndexError()

    def __len__(self):
        return 0

    def get(self):
        """Return native representation of this token"""
        if self.type == "INTEGER":
            return self.__int__()
        elif self.type == "FLOAT":
            return self.__float__()
        elif self.type in ["STRING", "QSTRING"]:
            return self.attr
        elif self.type == "BOOL":
            return self.bool()

    # special conversions

    def __str__(self):
        rv = self.attr
        if rv is None:
            rv = self.type
        return rv

    def __int__(self):
        if self.type == "INTEGER":
            return _str2int(self.attr)
        elif self.type == "INDEF":
            return int(INDEF)
        elif self.type == "FLOAT":
            # allow floats as values if they are exact integers
            f = self.__float__()
            i = int(f)
            if float(i) == f:
                return i
        elif self.type in ["STRING", "QSTRING"]:
            try:
                if self.attr == "":
                    return int(INDEF)
                elif self.attr[:1] == ')':
                    # indirection to another parameter
                    return self.attr
                else:
                    return _str2int(self.attr)
            except Exception as e:
                print('Exception', str(e))
                pass
        raise ValueError("Cannot convert " + self.verboseRepr() + " to int")

    def __float__(self):
        if self.type == "FLOAT":
            # convert d exponents to e for Python
            value = self.attr
            i = value.find('d')
            if i >= 0:
                value = value[:i] + 'e' + value[i + 1:]
            else:
                i = value.find('D')
                if i >= 0:
                    value = value[:i] + 'E' + value[i + 1:]
            return float(value)
        elif self.type == "INTEGER":
            # convert to int first because of octal, hex formats
            return float(_str2int(self.attr))
        elif self.type == "SEXAGESIMAL":
            # convert d:m:s values directly to float
            flist = self.attr.split(':')
            flist.reverse()
            value = float(flist[0])
            for v in flist[1:]:
                value = float(v) + value / 60.0
            return value
        elif self.type == "INDEF":
            return float(INDEF)
        elif self.type in ["STRING", "QSTRING"]:
            try:
                if self.attr == "":
                    return float(INDEF)
                elif self.attr[:1] == ')':
                    # indirection to another parameter
                    return self.attr
                else:
                    return float(self.attr)
            except (ValueError, TypeError):
                pass
        raise ValueError("Cannot convert " + self.verboseRepr() + " to float")

    def bool(self):
        # XXX convert INTEGER to bool too?
        if self.type == "BOOL":
            return self.attr
        elif self.type == "INDEF":
            return INDEF
        elif self.type in ["STRING", "QSTRING"]:
            keyword = self.attr.lower()
            if keyword in ["yes", "y"]:
                return "yes"
            elif keyword in ["no", "n"]:
                return "no"
            elif self.attr[:1] == ')':
                # indirection to another parameter
                return self.attr
            elif keyword == "":
                return INDEF
        raise ValueError("Cannot convert " + self.verboseRepr() + " to bool")


def _str2int(value):
    # convert integer string to python int
    # handles IRAF octal, hex values
    last = value[-1].lower()
    if last == 'b':
        # octal
        return eval('0' + value[:-1])
    elif last == 'x':
        # hexadecimal
        return eval('0x' + value[:-1])
    # remove leading zeros on decimal values
    i = 0
    for digit in value:
        if digit != '0':
            break
        i = i + 1
    else:
        # all zeros
        return 0
    return int(value[i:])
