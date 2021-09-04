"""Modified input for PyRAF CL-script execution and pre-processing.

Modifies the IPython intepreter to process PyRAF "magic" prior to
attempting a more conventional IPython interpretation of a command.

Code derived from pyraf.pycmdline.py
"""
# *****************************************************************************
#       Copyright (C) 2001-2004 Fernando Perez <fperez@colorado.edu>
#
#  Distributed under the terms of the BSD License.  The full license is in
#  the file COPYING, distributed as part of this software.
# *****************************************************************************


from IPython.core import release
from IPython.terminal.interactiveshell import TerminalInteractiveShell


__license__ = release.license

# set search path to include directory above this script and current directory
# ... but do not want the pyraf package directory itself in the path, since
# that messes things up by allowing direct imports of pyraf submodules
# (bypassing the __init__ mechanism.)

import sys
from . import iraf, __version__
from .irafpar import makeIrafPar
from stsci.tools.irafglobals import yes, no, INDEF, EOF

_locals = globals()

# del iraf, __version__, makeIrafPar, yes, no, INDEF, EOF, logout, quit, exit

if '-nobanner' not in sys.argv and '--no-banner' not in sys.argv:
    print("\nPyRAF", __version__, "Copyright (c) 2002 AURA")

# Start up command line wrapper keeping definitions in main name space
# Keep the command-line object in namespace too for access to history

# --------------------------------------------------------------------------
from .irafcompleter import IrafCompleter


class IPythonIrafCompleter(IrafCompleter):

    def __init__(self, IP):
        IrafCompleter.__init__(self)
        self.IP = IP
        self._completer = None
        self.install_init_readline_hack()

    # Override activate to prevent PyRAF from stealing readline hooks as
    # well as to hook into IPython
    def activate(self):
        # print >>sys.stderr, "Activating pyraf readline completer"
        def completer(C, text):  # C will be the IPython Completer;  not used
            return self.global_matches(text)

        # set_custom_completer mutates completer
        self.IP.set_custom_completer(completer)
        # ... get the mutant...
        self._completer = self.IP.Completer.matchers[0]

    def deactivate(self):
        # print >>sys.stderr, "Deactivating pyraf readline completer"
        if self._completer in self.IP.Completer.matchers:
            self.IP.Completer.matchers.remove(self._completer)

    def install_init_readline_hack(self):
        """The IPython startup sequence calls IP.init_readline() after
        the IP has been created and after the pyraf profile has been
        read.  This creates a new Completer and obliterates ours.
        We hook IP.init_readline here so that IPython doesn't override (or at
        least re-implements) changes PyRAF has already made.
        """
        if not hasattr(self, "_ipython_init_readline"):
            self._ipython_init_readline = TerminalInteractiveShell.init_readline

        def pyraf_init_readline(
                IP):  # Create function with built-in bindings to self
            assert self.IP is IP  # IPythonShell shouldn't change...
            self._ipython_init_readline(
                IP
            )  # Call IPython's original init_readline... make IP.Completer.
            self.activate()  # activate PyRAF completer

        TerminalInteractiveShell.init_readline = pyraf_init_readline  # Override class method

    def uninstall_init_readline_hack(self):
        TerminalInteractiveShell.init_readline = self._ipython_init_readline  # restore class method
        del self._ipython_init_readline


# ---------------------------------------------------------------------------


class IPython_PyRAF_Integrator:
    """This class supports the integration of these features with IPython:

    1. PyRAF readline completion
    2. PyRAF CL translation
    3. PyRAF exception traceback simplification

    """
    def __init__(self, clemulate=1, cmddict={}, cmdchars=("a-zA-Z_.", "0-9")):
        import re
        import os
        self.reword = re.compile('[a-z]*')
        self._cl_emulation = clemulate
        self.cmddict = cmddict
        self.recmd = re.compile("[ \t]*(?P<cmd>" + "[" + cmdchars[0] + "][" +
                                cmdchars[0] + cmdchars[1] + "]*" + ")[ \t]*")
        self.locals = _locals

        import pyraf
        self.pyrafDir = os.path.dirname(pyraf.__file__)

        import IPython
        self.ipythonDir = os.path.dirname(IPython.__file__)

        self.traceback_mode = "Context"

        self._ipython_api = pyraf._ipyshell

        # this is pretty far into IPython, i.e. very breakable
        # lsmagic() returns a dict of 2 dicts: 'cell', and 'line'
        if hasattr(self._ipython_api, 'magics_manager'):
            self._ipython_magic = list(
                self._ipython_api.magics_manager.lsmagic()['line'].keys())
        else:
            print('Please upgrade your version of IPython.')
        pfmgr = self._ipython_api.prefilter_manager
        self.priority = 0  # transformer needs this, low val = done first
        self.enabled = True  # a transformer needs this
        pfmgr.register_transformer(self)

    def isLocal(self, value):
        """Returns true if value is local variable"""
        ff = value.split('.')
        return ff[0] in self.locals

    def transform(self, line, continue_prompt):
        """ This pre-processes input to do PyRAF substitutions before
        passing it on to IPython.  Has this signature to match the
        needed API for the new (0.12) IPython's PrefilterTransformer
        instances.  This class is to look like such an instance.
        """
        # Check continue_prompt - we are not handling it currently
        if continue_prompt:
            return line
        # PyRAF assumes ASCII but IPython deals in unicode.  We could handle
        # that also by simply rewriting some of this class to use unicode
        # string literals.  For now, convert and check - if not OK (not
        # convertible to ASCII), simply move on (remove this assumption
        # after we no longer support Python2)
        asciiline = str(line)

        # Handle any weird special cases here.  Most all transformations
        # should occur through the normal route (e.g. sent here, then
        # translated below), but some items never get the chance in ipython
        # to be prefiltered...
        if asciiline == 'get_ipython().show_usage()':
            # Hey! IPython translated '?' before we got a crack at it...
            asciiline = '?'  # put it back! (only for single '?' by itself)

        # Now run it through our normal prefilter function
        return self.cmd(asciiline)

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
            return self.default(cmd, line, i)
        else:
            # if in cmddict, there must be a method by this name
            f = getattr(self, method_name)
            return f(line, i)

    def _default(self, cmd, line, i):
        """Check for IRAF task calls and use CL emulation mode if needed

        cmd = alpha-numeric string from beginning of line
        line = full line (including cmd, preceding blanks, etc.)
        i = index in line of first non-blank character following cmd
        """
        import os
        import keyword
        if len(cmd) == 0:
            if line[i:i + 1] == '!':
                # '!' is shell escape
                # handle it here only if cl emulation is turned off
                if not self._cl_emulation:
                    iraf.clOscmd(line[i + 1:])
                    return ''
            elif line[i:i + 1] != '?':
                # leading '?' will be handled by CL code -- else this is Python
                return line
        elif self._cl_emulation == 0:
            # if CL emulation is turned off then just return
            return line
        elif keyword.iskeyword(cmd) or \
                (cmd in os.__builtins__ and cmd not in ['type', 'dir', 'help', 'set']):
            # don't mess with Python keywords or built-in functions
            # except allow 'type', 'dir, 'help' to be used in simple syntax
            return line
        elif line[i:i + 1] != "" and line[i] in '=,[':
            # don't even try if it doesn't look like a procedure call
            return line
        elif cmd in self._ipython_magic and cmd not in ['cd']:
            return line
        elif not hasattr(iraf, cmd):
            # not an IRAF command
            # XXX Eventually want to improve error message for
            # XXX case where user intended to use IRAF syntax but
            # XXX forgot to load package
            return line
        elif self.isLocal(cmd):
            # cmd is both a local variable and an IRAF task or procedure name
            # figure out whether IRAF or CL syntax is intended from syntax
            if line[i:i + 1] == "" or line[i] == "(":
                return line
            if not (line[i].isalnum() and line[i].isletter()) and \
               line[i] not in "<>|":
                # this does not look like an IRAF command
                return line
            # check for some Python operator keywords
            mm = self.reword.match(line[i:])
            if mm.group() in ["is", "in", "and", "or", "not"]:
                return line
        elif line[i:i + 1] == '(':
            if cmd in ['type', 'dir', 'set']:
                # assume a standalone call of Python type, dir functions
                # rather than IRAF task
                # XXX Use IRAF help function in every case (may want to
                # change this eventually, when Python built-in help
                # gets a bit better.)
                return line
            else:
                # Not a local function, so user presumably intends to
                # call IRAF task.  Force Python mode but add the 'iraf.'
                # string to the task name for convenience.
                # XXX this find() may be improved with latest Python readline features
                j = line.find(cmd)
                return line[:j] + 'iraf.' + line[j:]
        elif not callable(getattr(iraf, cmd)):
            # variable from iraf module is not callable task (e.g.,
            # yes, no, INDEF, etc.) -- add 'iraf.' so it can be used
            # as a variable and execute as Python
            j = line.find(cmd)
            return line[:j] + 'iraf.' + line[j:]
        code = iraf.clLineToPython(line)
        statements = code.split("\n")
        return "; ".join([x for x in statements if x]) + "\n"

    def default(self, cmd, line, i):
        # print "input line:",repr(cmd),"line:",line,"i:",i
        code = self._default(cmd, line, i)
        if code is None:
            code = ""
        else:
            code = code.rstrip()
        # print "pyraf code:", repr(code)
        return code

    def showtraceback(self, IP, type, value, tb):
        """Display the exception that just occurred.

        We remove the first stack item because it is our own code.
        Strip out references to modules within pyraf unless reprint
        or debug is set.
        """
        import linecache
        import traceback
        import os
        import IPython.ultraTB

        # get the color scheme from the user configuration file and pass
        # it to the trace formatter
        csm = 'Linux'  # default

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
        color_tb = IPython.ultraTB.AutoFormattedTB(mode=self.traceback_mode,
                                                   tb_offset=tbskip,
                                                   color_scheme=csm)
        color_tb(type, value, tb)

    def prefilter(self, IP, line, continuation):
        """prefilter pre-processes input to do PyRAF substitutions before
           passing it on to IPython.
           NOTE: this is ONLY used for VERY_OLD_IPY, since we use the transform
           hooks for the later versions.
        """
        line = self.cmd(str(line))  # use type str here, not unicode
        return TerminalInteractiveShell._prefilter(IP, line, continuation)

    # The following are IPython "magic" functions when used as bound methods.

    def _evaluate_flag(self, flag, usage):
        try:
            if flag in [None, "", "on", "ON", "On", "True", "TRUE", "true"]:
                return True
            elif flag in ["off", "OFF", "Off", "False", "FALSE", "false"]:
                return False
            else:
                return int(flag)
        except ValueError:
            import sys
            print("usage:", usage, "[on | off]", file=sys.stderr)
            raise

    def _get_IP(self, IP):
        if IP is None:
            return self._ipython_api.IP
        else:
            return IP

    def _debug(self, *args):
        import sys
        for a in args:
            print(a, end=' ', file=sys.stderr)
        print(file=sys.stderr)

    def set_pyraf_magic(self, IP, line):
        """Setting flag="1" Enables PyRAF to intepret a magic
        identifier before IPython.
        """
        magic, flag = line.split()
        if self._evaluate_flag(flag, "set_pyraf_magic <magic_function>"):
            self._debug("PyRAF magic for", magic, "on")
            while magic in self._ipython_magic:  # should only be one
                self._ipython_magic.remove(magic)
        else:
            self._debug("PyRAF magic for", magic, "off")
            if magic not in self._ipython_magic:
                self._ipython_magic.append(magic)

    def use_pyraf_traceback(self, IP=None, flag=None, feedback=True):
        IP = self._get_IP(IP)
        if self._evaluate_flag(flag, "use_pyraf_traceback"):
            if feedback:
                self._debug("PyRAF traceback display: on")
            IP.set_custom_exc((Exception,), self.showtraceback)
        else:
            if feedback:
                self._debug("PyRAF traceback display: off")
            IP.custom_exceptions = ((), None)

    def use_pyraf_cl_emulation(self, IP=None, flag=None, feedback=True):
        """Turns PyRAF CL emulation on (1) or off (0)"""
        self._cl_emulation = self._evaluate_flag(flag,
                                                 "use_pyraf_cl_emulation")
        if self._cl_emulation:
            if feedback:
                self._debug("PyRAF CL emulation on")
        else:
            if feedback:
                self._debug("PyRAF CL emulation off")

    def use_pyraf_completer(self, IP=None, flag=None, feedback=True):
        if self._evaluate_flag(flag, "use_pyraf_readline_completer"):
            if feedback:
                self._debug("PyRAF readline completion on")
            self._pyraf_completer.activate()
        else:
            if feedback:
                self._debug("PyRAF readline completion off")
            self._pyraf_completer.deactivate()


fb = "-nobanner" not in sys.argv
__PyRAF = IPython_PyRAF_Integrator()
# __PyRAF.use_pyraf_completer(feedback=fb) Can't do this yet...but it's hooked.
# __PyRAF.use_pyraf_cl_emulation(feedback=fb)

if '-nobanner' not in sys.argv and '--no-banner' not in sys.argv:
    print("PyRAF traceback not enabled")
del fb

del IPythonIrafCompleter, IPython_PyRAF_Integrator, IrafCompleter
