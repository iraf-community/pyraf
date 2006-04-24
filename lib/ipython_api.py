# -*- coding: utf-8 -*-
"""Modified input for PyRAF CL-script execution and pre-processing.

Modifies the IPython intepreter to process PyRAF "magic" prior to
attempting a more conventional IPython interpretation of a command.

Code derived from pyraf.pycmdline.py
"""
#*****************************************************************************
#       Copyright (C) 2001-2004 Fernando Perez <fperez@colorado.edu>
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
#*****************************************************************************

from IPython import Release
__author__  = '%s <%s>' % Release.authors['Fernando']
__license__ = Release.license

# set search path to include directory above this script and current directory
# ... but do not want the pyraf package directory itself in the path, since
# that messes things up by allowing direct imports of pyraf submodules
# (bypassing the __init__ mechanism.)

from pyraf import iraf, __version__
from pyraf.irafpar import makeIrafPar
from pyraf.irafglobals import yes, no, INDEF, EOF

_locals = globals()

# del iraf, __version__, makeIrafPar, yes, no, INDEF, EOF, logout, quit, exit

print "PyRAF", __version__, "Copyright (c) 2002 AURA"

# Start up command line wrapper keeping definitions in main name space
# Keep the command-line object in namespace too for access to history

from IPython.iplib import InteractiveShell

import IPython.ipapi

# ---------------------------------------------------------------------------

_ipython_shell = IPython.ipapi.get() 
    
class PyRAF_CL_line_translator(object):
    """This class is a PyRAF CL line translator.  It is derived from
    from the standalone pyraf shell in pycmdline.py.
    """
    import string
    
    def __init__(self, clemulate=1, cmddict={},
                 cmdchars=("a-zA-Z_.","0-9")):
        import re, sys, os
        self.reword = re.compile('[a-z]*')       
        self.clemulate = clemulate
        self.cmddict = cmddict
        self.recmd = re.compile(
            "[ \t]*(?P<cmd>" +
            "[" + cmdchars[0] + "][" + cmdchars[0] + cmdchars[1] + "]*" +
            ")[ \t]*")
        self.locals = _locals
        self.ipython_magic = _ipython_shell.IP.lsmagic() # skip %

        import pyraf
        self.pyrafDir = os.path.dirname(pyraf.__file__)

        import IPython
        self.ipythonDir = os.path.dirname(IPython.__file__)

        self.traceback_mode = "Context"

    def isLocal(self, value):
        """Returns true if value is local variable"""
        ff = value.split('.')
        return self.locals.has_key(ff[0])

    def cmd(self, line):
        """Check for and execute commands from dictionary."""
        mo = self.recmd.match(line)
        if mo is None:
            i = 0
            cmd = ''
            method_name = None
        else:
            cmd = mo.group('cmd')
            i = mo.end()
            # look up command in dictionary
            method_name = self.cmddict.get(cmd)
        if method_name is None:
            # no method, but have a look at it anyway
            return self.default(cmd,line,i)
        else:
            # if in cmddict, there must be a method by this name
            f = getattr(self, method_name)
            return apply(f, (line, i))

    def _default(self, cmd, line, i):
        """Check for IRAF task calls and use CL emulation mode if needed

        cmd = alpha-numeric string from beginning of line
        line = full line (including cmd, preceding blanks, etc.)
        i = index in line of first non-blank character following cmd
        """
        import os, keyword
        if len(cmd)==0:
            if line[i:i+1] == '!':
                # '!' is shell escape
                # handle it here only if cl emulation is turned off
                if not self.clemulate:
                    iraf.clOscmd(line[i+1:])
                    return ''
            elif line[i:i+1] != '?':
                # leading '?' will be handled by CL code -- else this is Python
                return line
        elif self.clemulate == 0:
            # if CL emulation is turned off then just return
            return line
        elif keyword.iskeyword(cmd) or \
          (os.__builtins__.has_key(cmd) and cmd not in ['type', 'dir', 'help', 'set']):
            # don't mess with Python keywords or built-in functions
            # except allow 'type', 'dir, 'help' to be used in simple syntax
            return line
        elif line[i:i+1] != "" and line[i] in '=,[':
            # don't even try if it doesn't look like a procedure call
            return line
        elif cmd in self.ipython_magic:
            return line
        elif not hasattr(iraf,cmd):
            # not an IRAF command
            #XXX Eventually want to improve error message for
            #XXX case where user intended to use IRAF syntax but
            #XXX forgot to load package
            return line
        elif self.isLocal(cmd):
            # cmd is both a local variable and an IRAF task or procedure name
            # figure out whether IRAF or CL syntax is intended from syntax
            if line[i:i+1] == "" or line[i] == "(":
                return line
            if line[i] not in self.string.digits and \
               line[i] not in self.string.letters and \
               line[i] not in "<>|":
                # this does not look like an IRAF command
                return line
            # check for some Python operator keywords
            mm = self.reword.match(line[i:])
            if mm.group() in ["is","in","and","or","not"]:
                return line
        elif line[i:i+1] == '(':
            if cmd in ['type', 'dir', 'set']:
                # assume a standalone call of Python type, dir functions
                # rather than IRAF task
                #XXX Use IRAF help function in every case (may want to
                # change this eventually, when Python built-in help
                # gets a bit better.)
                return line
            else:
                # Not a local function, so user presumably intends to
                # call IRAF task.  Force Python mode but add the 'iraf.'
                # string to the task name for convenience.
                #XXX this find() may be improved with latest Python readline features
                j = line.find(cmd)
                return line[:j] + 'iraf.' + line[j:]
        elif not callable(getattr(iraf,cmd)):
            # variable from iraf module is not callable task (e.g.,
            # yes, no, INDEF, etc.) -- add 'iraf.' so it can be used
            # as a variable and execute as Python
            j = line.find(cmd)
            return line[:j] + 'iraf.' + line[j:]
        return iraf.clLineToPython(line)

    def default(self, cmd, line, i):
        # print "input line:",repr(cmd),"line:",line,"i:",i
        code = self._default(cmd, line, i)
        if code is None:
            code = ""
        else:
            code = code.strip()
        # print "pyraf code:", repr(code)
        return code
    
    def showtraceback(self, shell, type, value, tb):
        """Display the exception that just occurred.

        We remove the first stack item because it is our own code.
        Strip out references to modules within pyraf unless reprint
        or debug is set.
        """
        import linecache, traceback, sys, os
        import IPython.ultraTB
        linecache.checkcache()
        tblist = traceback.extract_tb(tb)
        tbskip = 0
        for tb1 in tblist:
            path, filename = os.path.split(tb1[0])
            path = os.path.normpath(os.path.join(os.getcwd(), path))
            if path[:len(self.pyrafDir)] == self.pyrafDir or \
               path[:len(self.ipythonDir)] == self.ipythonDir or \
               filename == "<ipython console>":
                tbskip += 1
        color_tb = IPython.ultraTB.AutoFormattedTB(
            mode=self.traceback_mode, tb_offset=tbskip)
        color_tb(type, value, tb)

_pyraf = PyRAF_CL_line_translator()

def prefilter_PyRAF(self, line, continuation):
    """Alternate prefilter for input of PhysicalQuantityInteractive objects.
    This assumes that the function PhysicalQuantityInteractive() has been
    imported.
    """
    line = _pyraf.cmd(line)
    return self._prefilter(line,continuation)

# Rebind this to be the new IPython prefilter:
InteractiveShell.prefilter = prefilter_PyRAF

# --------------------------------------------------------------------------

def use_pyraf_completer(shell, value="1"):

    import sys

    from pyraf.irafcompleter import IrafCompleter
    from IPython.completer import IPCompleter

    def activate_hybrid_completer(IP):
        
        def completer(C, text):
            return C._pyraf_completer.global_matches(text)
            
        IP.init_readline()
        # print >>sys.stderr, "activating pyraf readline completer", IP.Completer
        deactivate_hybrid_completer(IP)
        IP.Completer._pyraf_completer = IrafCompleter()
        IP.set_custom_completer(completer)

    def deactivate_hybrid_completer(IP):
        if hasattr(IP, "Completer") and \
           hasattr(IP.Completer, "_pyraf_completer"):
            # print >>sys.stderr, "deactivating pyraf readline completer"
            if IP.Completer._pyraf_completer in IP.Completer.matchers:
                IP.Completer.matchers.remove(IP.Completer._pyraf_completer)
            del IP.Completer._pyraf_completer
            
    if value.strip() == "":
        value = "1"
    if int(value):
        activate_hybrid_completer(shell)
    else:
        deactivate_hybrid_completer(shell)
        

# --------------------------------------------------------------------------

def use_ipython_magic(shell, magic):
    """Enables IPython to interpret a magic identifier before PyRAF."""
    if magic not in _pyraf.ipython_magic:
        _pyraf.ipython_magic.append(magic)

def use_pyraf_magic(shell, magic):
    """Enables PyRAF to intepret a magic identifier before IPython."""
    while magic in _pyraf.ipython_magic:  # should only be one
        _pyraf.ipython_magic.remove(magic)

def use_pyraf_traceback(shell, *args):
    shell.set_custom_exc((Exception,), _pyraf.showtraceback)

def use_ipython_traceback(shell, *args):
    shell.custom_exceptions = ((), None)

def use_clemulate(shell, value="1"):
    """Turns PyRAF CL emulation on (1) or off (0)"""
    import sys
    try:
        _pyraf.clemulate = int(value)
    except:
        import sys
        print >>sys.stderr, "clemulate [0 or 1]"
        _pyraf.clemulate = 1

use_pyraf_traceback(_ipython_shell.IP)
use_pyraf_completer(_ipython_shell.IP)

_ipython_shell.expose_magic("use_ipython_magic", use_ipython_magic)
_ipython_shell.expose_magic("use_pyraf_magic", use_pyraf_magic)
_ipython_shell.expose_magic("use_ipython_traceback", use_ipython_traceback)
_ipython_shell.expose_magic("use_pyraf_traceback", use_pyraf_traceback)
_ipython_shell.expose_magic("use_clemulate", use_clemulate)
_ipython_shell.expose_magic("use_pyraf_completer", use_pyraf_completer)

del InteractiveShell, prefilter_PyRAF, PyRAF_CL_line_translator
del use_ipython_magic, use_pyraf_magic
del use_pyraf_traceback, use_ipython_traceback
del use_clemulate, use_pyraf_completer

