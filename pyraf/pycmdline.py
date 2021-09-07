"""pycmdline.py -- Python/CL command line interface for Pyraf

Provides this functionality:

- Command directives:
        .logfile [filename [append]]
        .exit
        .help
        .complete [ 1 | 0 ]
        .fulltraceback
        .clemulate
        .debug
- Shell escapes (!cmd, !!cmd to run in /bin/sh)
- CL command-mode execution, triggered by a line that starts with a
  CL task token and is not followed by other characters indicating
  it is some other kind of Python statement
- Normal Python mode execution (when CL emulation and directives are
  not triggered)

Uses standard code module plus some ideas from cmd.py module
(and of course Perry's Monty design.)

R. White, 2000 February 20
"""


import string
import re
import os
import sys
import code
import keyword
import traceback
import linecache
from stsci.tools import capable, minmatch
from . import iraf
from . import irafinst
from . import wutil
from .pyrafglobals import pyrafDir


class CmdConsole(code.InteractiveConsole):
    """Base class for command console.

    Similar to InteractiveConsole, but provides local prompt control and
    hook for simple non-Python command processing.
    """

    def __init__(self,
                 locals=None,
                 filename="<console>",
                 cmddict=None,
                 prompt1=">>> ",
                 prompt2="... ",
                 cmdchars=("a-zA-Z_.", "0-9")):
        code.InteractiveConsole.__init__(self,
                                         locals=locals,
                                         filename=filename)
        self.ps1 = prompt1
        self.ps2 = prompt2
        if cmddict is None:
            cmddict = {}
        self.cmddict = cmddict
        # cmdchars gives character set for first character, following
        # characters in the command name
        # create pattern that puts command in group 'cmd' and matches
        # optional leading and trailing whitespace
        self.recmd = re.compile("[ \t]*(?P<cmd>" + "[" + cmdchars[0] + "][" +
                                cmdchars[0] + cmdchars[1] + "]*" + ")[ \t]*")
        # history is a list of lines entered by user (allocated in blocks)
        self.history = 100 * [None]
        self.nhistory = 0
        from . import irafcompleter
        self.completer = irafcompleter.IrafCompleter()

    def addHistory(self, line):
        """Append a line to history"""
        if self.nhistory >= len(self.history):
            self.history.extend(100 * [None])
        self.history[self.nhistory] = line
        self.nhistory = self.nhistory + 1

    def printHistory(self, n=20):
        """Print last n lines of history"""
        for i in range(-min(n, self.nhistory), 0):
            print(self.history[self.nhistory + i])

    def interact(self, banner=None):
        """Emulate the interactive Python console, with extra commands.

        Also is modified so it does not catch EOFErrors."""
        if banner is None:
            self.write(f"Python {sys.version} on {sys.platform}\n"
                       f"{sys.copyright}\n({self.__class__.__name__})\n")
        else:
            self.write(f"{str(banner)}\n")
        more = 0
        # number of consecutive EOFs
        neofs = 0
        # flag indicating whether terminal ID needs to be set
        needtermid = 1
        while True:
            try:
                if not sys.stdin.isatty():
                    prompt = ""
                elif more:
                    prompt = self.ps2
                else:
                    prompt = self.ps1
# !!!               prompt = 'curpkg > '
# reset the focus to terminal if necessary
                wutil.focusController.resetFocusHistory()
                line = self.raw_input(prompt)
                if needtermid and prompt:
                    # reset terminal window ID immediately
                    # after first input from terminal
                    wutil.terminal.updateWindowID()
                    needtermid = 0
                neofs = 0
                # add non-null lines to history
                if line.strip():
                    self.addHistory(line)
                # note that this forbids combination of python & CL
                # code -- e.g. a for loop that runs CL tasks.
                if not more:
                    line = self.cmd(line)
                if line or more:
                    more = self.push(line)
            except EOFError:
                # XXX ugly code here -- refers to methods
                # XXX defined in extensions of this class
                neofs = neofs + 1
                if neofs >= 5:
                    self.write("\nToo many EOFs, exiting now\n")
                    self.do_exit()
                self.write("\nUse .exit to exit\n"
                           ".help describes executive commands\n")
                self.resetbuffer()
                more = 0
            except KeyboardInterrupt:
                self.write("^C\n")
                self.resetbuffer()
                more = 0

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

    def default(self, cmd, line, i):
        """Hook to handle other commands (this version does nothing)"""
        return line


# put the executive commands in a minimum match dictionary

_cmdDict = minmatch.QuietMinMatchDict({
    '.help': 'do_help',
    '.clemulate': 'do_clemulate',
    '.logfile': 'do_logfile',
    '.exit': 'do_exit',
    #                               'lo': 'do_exit',
    '.fulltraceback': 'do_fulltraceback',
    '.complete': 'do_complete',
    '.debug': 'do_debug',
})


class PyCmdLine(CmdConsole):
    """Simple Python interpreter with executive commands"""

    def __init__(self,
                 locals=None,
                 logfile=None,
                 complete=1,
                 debug=0,
                 clemulate=1):
        CmdConsole.__init__(self,
                            locals=locals,
                            cmddict=_cmdDict,
                            prompt1="--> ",
                            prompt2="... ")
        self.reword = re.compile('[a-z]*')
        self.complete = complete
        self.debug = debug
        self.clemulate = clemulate
        self.logfile = None
        self.lasttrace = None
        if logfile is not None:
            if hasattr(logfile, 'write'):
                self.logfile = logfile
            elif isinstance(logfile, str):
                self.do_logfile(logfile)
            else:
                self.write('logfile ignored -- not string or filehandle\n')
        # turn command completion on or off as requested
        self.do_complete(default=self.complete)
        # install special error handler for Tk tracebacks
        if capable.OF_GRAPHICS:
            from pyraf import pyrafTk
            pyrafTk.setTkErrorHandler(self.showtraceback)

    def runsource(self, source, filename="<input>", symbol="single"):
        """Compile and run some source in the interpreter.

        Modified from code.py to include logging."""
        try:
            pcode = code.compile_command(source, filename, symbol)
        except (OverflowError, SyntaxError):
            # Case 1
            self.showsyntaxerror(filename)
            return 0

        if pcode is None:
            # Case 2
            return 1

        # Case 3
        self.runcode(pcode)
        if self.logfile:
            self.logfile.write(source)
            if source[-1:] != '\n':
                self.logfile.write('\n')
            self.logfile.flush()
        return 0

    def do_help(self, line='', i=0):
        """Print help on executive commands"""
        if self.debug > 1:
            self.write(f'do_help: {line[i:]}\n')
        self.write("""Executive commands (commands can be abbreviated):
.exit
Exit from Pyraf.
.help
Print this help message.
.logfile [filename [append|overwrite]]
If filename is specified, start logging commands to the file.  If filename
is omitted, turns off logging.  The optional append/overwrite argument
determines action for existing file (default is to append.)
.fulltraceback
Print full version of last error traceback.
.complete [0|1]
Turn command-completion on (default) or off.  When on, the tab character
acts as the completion character, attempting to complete a partially
specified task name, variable name, filename, etc.  If the result is
ambiguous, a list of the possibilities is printed.  Use ^V+tab to insert
a tab other than at the line beginning.
.clemulate [0|1]
Turn CL emulation on (default) or off, which determines whether lines
starting with a CL task name are interpreted in CL mode rather than Python
mode.
.debug [1|0]
Set debugging flag.  If argument is omitted, default is 1 (debugging on.)
""")

    def do_exit(self, line='', i=0):
        """Exit from PyRAF and then Python"""
        if self.debug > 1:
            self.write(f'do_exit: {line[i:]}\n')

        # write out history - ignore write errors
        hfile = os.getenv('HOME', '.') + os.sep + '.pyraf_history'
        hlen = 1000  # High default.  Note this setting itself may cause
        # confusion between this history and the IRAF history cmd.
        try:
            hlen = int(iraf.envget('histfilesize'))
        except (KeyError, ValueError):
            pass
        try:
            import readline
            readline.set_history_length(hlen)  # hlen<0 means unlimited
            readline.write_history_file(hfile)  # clobber any old version
        except (ImportError, OSError):
            pass

        # any irafinst tmp files?
        irafinst.cleanup()  # any irafinst tmp files?

        # graphics
        wutil.closeGraphics()

        # leave
        raise SystemExit()

    def do_logfile(self, line='', i=0):
        """Start or stop logging commands"""
        if self.debug > 1:
            self.write(f'do_logfile: {line[i:]}\n')
        args = line[i:].split()
        if len(args) == 0:  # turn off logging (if on)
            if self.logfile:
                self.logfile.close()
                self.logfile = None
            else:
                self.write("No log file currently open\n")
        else:
            filename = args[0]
            del args[0]
            oflag = 'a'
            if len(args) > 0:
                if args[0] == 'overwrite':
                    oflag = 'w'
                    del args[0]
                elif args[0] == 'append':
                    del args[0]
            if args:
                self.write(f'Ignoring unknown options: {" ".join(args)}\n')
            try:
                oldlogfile = self.logfile
                self.logfile = open(filename, oflag)
                if oldlogfile:
                    oldlogfile.close()
            except OSError as e:
                self.write(f"error opening logfile {filename}\n{str(e)}\n")
        return ""

    def do_clemulate(self, line='', i=0):
        """Turn CL emulation on or off"""
        if self.debug > 1:
            self.write(f'do_clemulate: {line[i:]}\n')
        self.clemulate = 1
        if line[i:] != "":
            try:
                self.clemulate = int(line[i:])
            except ValueError as e:
                if self.debug:
                    self.write(str(e) + '\n')
                pass
        return ""

    def do_complete(self, line='', i=0, default=1):
        """Turn command completion on or off"""
        if self.debug > 1:
            self.write(f'do_complete: {line[i:]}\n')
        self.complete = default
        if line[i:] != "":
            try:
                self.complete = int(line[i:])
            except ValueError as e:
                if self.debug:
                    self.write(str(e) + '\n')
                pass
        if self.complete:
            # set list of executive commands
            self.completer.executive(_cmdDict.keys())
            self.completer.activate()
        else:
            self.completer.deactivate()
        return ""

    def do_debug(self, line='', i=0):
        """Turn debug output on or off"""
        if self.debug > 1:
            self.write(f'do_debug: {line[i:]}\n')
        self.debug = 1
        if line[i:] != "":
            try:
                self.debug = int(line[i:])
            except ValueError as e:
                if self.debug:
                    self.write(str(e) + '\n')
                pass
        return ""

    def do_fulltraceback(self, line='', i=0):
        """Print full version of last traceback"""
        if self.debug > 1:
            self.write(f'do_fulltraceback: {line[i:]}\n')
        self.showtraceback(reprint=1)
        return ""

    def default(self, cmd, line, i):
        """Check for IRAF task calls and use CL emulation mode if needed

        cmd = alpha-numeric string from beginning of line
        line = full line (including cmd, preceding blanks, etc.)
        i = index in line of first non-blank character following cmd
        """
        if self.debug > 1:
            self.write(f'default: {cmd} - {line[i:]}\n')
        if len(cmd) == 0:
            if line[i:i + 1] == '!':
                # '!' is shell escape
                # handle it here only if cl emulation is turned off
                if not self.clemulate:
                    iraf.clOscmd(line[i + 1:])
                    return ''
            elif line[i:i + 1] != '?':
                # leading '?' will be handled by CL code -- else this is Python
                return line
        elif self.clemulate == 0:
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
            if line[i] not in string.digits and \
               line[i] not in string.ascii_letters and \
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

        # if we get to here then it looks like CL code
        if self.debug > 1:
            self.write(f'CL: {line}\n')
        try:
            code = iraf.clExecute(line, locals=self.locals, mode='single')
            if self.logfile is not None:
                # log CL code as comment
                cllines = line.split('\n')
                for oneline in cllines:
                    self.logfile.write(f'# {oneline}\n')
                self.logfile.write(code)
                self.logfile.flush()
        except:
            self.showtraceback()
        return ''

    def isLocal(self, value):
        """Returns true if value is local variable"""
        ff = value.split('.')
        return ff[0] in self.locals

    def start(self,
              banner="Python/CL command line wrapper\n"
              "  .help describes executive commands"):
        """Start interpreter"""
        self.interact(banner=banner)

    def showtraceback(self, reprint=0):
        """Display the exception that just occurred.

        We remove the first stack item because it is our own code.
        Strip out references to modules within pyraf unless reprint
        or debug is set.
        """
        try:
            if reprint:
                if self.lasttrace is None:
                    return
                type, value, tbmod = self.lasttrace
            else:
                type, value, tb = sys.exc_info()
                linecache.checkcache()
                sys.last_type = type
                sys.last_value = value
                sys.last_traceback = tb
                tblist = traceback.extract_tb(tb)
                del tblist[:1]
                self.lasttrace = type, value, tblist
                if self.debug:
                    tbmod = tblist
                else:
                    tbmod = []
                    for tb1 in tblist:
                        path, filename = os.path.split(tb1[0])
                        path = os.path.normpath(os.path.join(
                            os.getcwd(), path))
                        if path[:len(pyrafDir)] != pyrafDir:
                            tbmod.append(tb1)
            list = traceback.format_list(tbmod)
            if list:
                list.insert(0, "Traceback (innermost last):\n")
            list[len(list):] = traceback.format_exception_only(type, value)
        finally:
            tbmod = tblist = tb = None
        for item in list:
            self.write(item)
