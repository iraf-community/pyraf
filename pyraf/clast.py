"""clast.py: abstract syntax tree node type for CL parsing
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
#  Minimal AST class -- N-ary trees.
#

from stsci.tools import compmixin


class AST(compmixin.ComparableMixin):

    def __init__(self, type=None):
        self.type = type
        self._kids = []

    #
    #  Not all these may be needed, depending on which classes you use:
    #
    #  __getitem__          GenericASTTraversal, GenericASTMatcher
    #  __len__              GenericASTBuilder
    #  __setslice__         GenericASTBuilder
    #  _compare             GenericASTMatcher
    #
    def __getitem__(self, i):
        return self._kids[i]

    def __len__(self):
        return len(self._kids)

    # __setslice__ is deprec.d, out in PY3K; use __setitem__ instead
    def __setslice__(self, low, high, seq):
        self._kids[low:high] = seq

    def __setitem__(self, idx, val):
        self._kids[idx] = val

    def __repr__(self):
        return self.type

    def _compare(self, other, method):
        if isinstance(other, AST):
            return method(self.type, other.type)
        else:
            return method(self.type, other)
