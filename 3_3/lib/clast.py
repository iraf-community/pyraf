"""clast.py: abstract syntax tree node type for CL parsing

$Id$
"""
from __future__ import division # confidence high

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

class AST:
    def __init__(self, type):
        self.type = type
        self._kids = []

    #
    #  Not all these may be needed, depending on which classes you use:
    #
    #  __getitem__          GenericASTTraversal, GenericASTMatcher
    #  __len__              GenericASTBuilder
    #  __setslice__         GenericASTBuilder
    #  __cmp__              GenericASTMatcher
    #
    def __getitem__(self, i):
        return self._kids[i]
    def __len__(self):
        return len(self._kids)
    def __setslice__(self, low, high, seq):
        self._kids[low:high] = seq
    def __cmp__(self, o):
        return cmp(self.type, o)
    def __repr__(self):
        return self.type
