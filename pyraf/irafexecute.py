"""irafexecute.py: Functions to execute IRAF connected subprocesses
"""


import os
import re
import signal
import struct
import sys
import numpy
import io
from stsci.tools import irafutils
from stsci.tools.irafglobals import IrafError, IrafTask, Verbose
from . import subproc
from . import filecache
from . import wutil
from . import gki
from . import irafukey
from . import irafgwcs
from . import iraf

# test_probe is a flag that a testing system can use to tell pyraf
# (when used as a library, e.g. in stsci_regtest) to print various
# diagnostic information that we think might be useful in test logs.
# This is different from verbose, because it is more selective.
#
# There is no interface to activate this feature.  Use:
#   from . import irafexecute
#   irafexecute.test_probe = True
test_probe = False

# stdgraph = None

IPC_PREFIX = b'P\x02'

# weirdo protocol to get output from task back to subprocess
# definitions from cl/task.h and lib/clio.h
IPCOUT = "IPC$IPCIO-OUT"
IPCDONEMSG = "# IPC$IPCIO-FINISHED\n"

# set flag indicating big endian or little endian byte order
# sys.byteorder was added in Python 2.0
isBigEndian = sys.byteorder == "big"

# Create an instance of the stdimage kernel
stdimagekernel = gki.GkiController()


class IrafProcessError(Exception):

    def __init__(self, msg, errno=-1, errmsg="", errtask=""):
        Exception.__init__(self, msg)
        self.errno = errno
        self.errmsg = errmsg
        self.errtask = errtask


def _getExecutable(arg):
    """Get executable pathname.

    Arg may be a string with the path, an IrafProcess, an IrafTask,
    or a string with the name of an IrafTask.
    """
    if isinstance(arg, IrafProcess):
        return arg.executable
    elif isinstance(arg, IrafTask):
        return arg.getFullpath()
    elif isinstance(arg, str):
        if os.path.exists(arg):
            return arg
        task = iraf.getTask(arg, found=1)
        if task is not None:
            return task.getFullpath()
    raise IrafProcessError(f"Cannot find task or executable {arg}")


class _ProcessProxy(filecache.FileCache):
    """Proxy for a single process that restarts it if needed

    Restart is triggered by change of executable on disk.
    """

    def __init__(self, process):
        self.process = process
        self.envdict = {}
        # pass executable filename to FileCache
        filecache.FileCache.__init__(self, process.executable)

    def newValue(self):
        # no action required at proxy creation
        pass

    def updateValue(self):
        """Called when executable changes to start a new version"""
        self.process.terminate()
        # seems to be necessary to delete this process before starting
        # next one to avoid some weird problems...
        del self.process
        self.process = IrafProcess(self.filename)
        self.process.initialize(self.envdict)

    def getProcess(self, envdict):
        """Get the process; create & initialize using envdict if needed"""
        self.envdict = envdict
        return self.get()

    def getValue(self):
        return self.process


class _ProcessCache:
    """Cache of active processes indexed by executable path"""

    DFT_LIMIT = 8

    def __init__(self, limit=DFT_LIMIT):
        self._data = {}  # dictionary with active process proxies
        self._pcount = 0  # total number of processes started
        self._plimit = limit  # number of active processes allowed
        self._locked = {}  # processes locked into cache

    def error(self, msg, level=0):
        """Write an error message if Verbose is set"""
        if Verbose > level:
            sys.stderr.write(msg)
            sys.stderr.flush()

    def get(self, task, envdict):
        """Get process for given task.  Create a new one if needed."""
        executable = _getExecutable(task)
        if executable in self._data:
            # use existing process
            rank, proxy = self._data[executable]
            process = proxy.getProcess(envdict)
            if not process.running:
                if process.isAlive():
                    return process
                # Hmm, looks like there is something wrong with this process
                # Kill it and start a new one
                # XXX Eventually can make this a level 0 message
                # XXX Leave as level -1 for now so we see if bug is gone
                self.error(f"Warning: process {executable} is bad, "
                           "restarting it\n", level=-1)
                self.kill(executable, verbose=0)
            # Whoops, process is already active...
            # This could happen if one task in an executable tries to
            # execute another task in the same executable.  Don't know
            # if IRAF allows this, but we can handle it by just creating
            # a new process running the same executable.
        # create and initialize a new process
        # this will be added to cache after successful task completion
        process = IrafProcess(executable)
        process.initialize(envdict)
        return process

    def add(self, process):
        """Add process to cache or update its rank if already there"""
        self._pcount = self._pcount + 1
        executable = process.executable
        if executable in self._data:
            # don't replace current cached process
            rank, proxy = self._data[executable]
            oldprocess = proxy.process
            if oldprocess != process:
                # argument is a duplicate process, terminate this copy
                process.terminate()
        elif self._plimit <= len(self._locked):
            # cache is null or all processes are locked
            process.terminate()
            return
        else:
            # new process -- make a proxy
            proxy = _ProcessProxy(process)
            if len(self._data) >= self._plimit:
                # delete the oldest entry to make room
                self._deleteOldest()
        self._data[executable] = (self._pcount, proxy)

    def _deleteOldest(self):
        """Delete oldest unlocked process from the cache

        If all processes are locked, delete oldest locked process.
        """
        # each entry contains rank (to sort and find oldest) and process
        values = sorted(self._data.values())
        if len(self._locked) < len(self._data):
            # find and delete oldest unlocked process
            for rank, proxy in values:
                process = proxy.process
                executable = process.executable
                if not (executable in self._locked or process.running):
                    # terminate it
                    self.terminate(executable)
                    return
        # no unlocked processes or all unlocked are running
        # delete oldest locked process
        rank, proxy = values[0]
        executable = proxy.process.executable
        self.terminate(executable)

    def setenv(self, msg):
        """Update process value of environment variable by sending msg"""
        for rank, proxy in self._data.values():
            # just save messages in a list, they all get sent at
            # once when a task is run
            proxy.process.appendEnv(msg)

    def setSize(self, limit):
        """Set number of processes allowed in cache"""
        self._plimit = limit
        if self._plimit <= 0:
            self._locked = {}
            self.flush()
        else:
            while len(self._data) > self._plimit:
                self._deleteOldest()

    def resetSize(self):
        """Set the number of processes allowed in cache back to the default"""
        self.setSize(_ProcessCache.DFT_LIMIT)

    def lock(self, *args):
        """Lock the specified tasks into the cache

        Takes task names (strings) as arguments.
        """
        # don't bother if cache is disabled or full
        if self._plimit <= len(self._locked):
            return
        for taskname in args:
            task = iraf.getTask(taskname, found=1)
            if task is None:
                print(f"No such task `{taskname}'")
            elif task.__class__.__name__ == "IrafTask":
                # cache only executable tasks (not CL tasks, etc.)
                executable = task.getFullpath()
                process = self.get(task, iraf.getVarDict())
                self.add(process)
                if executable in self._data:
                    self._locked[executable] = 1
                else:
                    self.error(f"Cannot cache {taskname}\n")

    def delget(self, process):
        """Get process object and delete it from cache

        process can be an IrafProcess, task name, IrafTask, or
        executable filename.
        """
        executable = _getExecutable(process)
        if executable in self._data:
            rank, proxy = self._data[executable]
            if not isinstance(process, IrafProcess):
                process = proxy.process
            # don't delete from cache if this is a duplicate process
            if process == proxy.process:
                del self._data[executable]
                if executable in self._locked:
                    del self._locked[executable]
                    # could restart the process if locked?
        return process

    def kill(self, process, verbose=1):
        """Kill process and delete it from cache

        process can be an IrafProcess, task name, IrafTask, or
        executable filename.
        """
        process = self.delget(process)
        if isinstance(process, IrafProcess):
            process.kill(verbose)

    def terminate(self, process):
        """Terminate process and delete it from cache"""
        # This is gentler than kill(), which should be used only
        # when there are process errors.
        process = self.delget(process)
        if isinstance(process, IrafProcess):
            process.terminate()

    def flush(self, *args):
        """Flush given processes (all non-locked if no args given)

        Takes task names (strings) as arguments.
        """
        if args:
            for taskname in args:
                task = iraf.getTask(taskname, found=1)
                if task is not None:
                    self.terminate(task)
        else:
            for rank, proxy in list(self._data.values()):
                executable = proxy.process.executable
                if executable not in self._locked:
                    self.terminate(executable)

    def list(self):
        """List processes sorted from newest to oldest with locked flag"""
        values = sorted(self._data.values())
        values.reverse()
        n = 0
        for rank, proxy in values:
            n = n + 1
            executable = proxy.process.executable
            if executable in self._locked:
                print(f"{n:2d}: L {executable}")
            else:
                print(f"{n:2d}:   {executable}")

    def __del__(self):
        self._locked = {}
        self.flush()


processCache = _ProcessCache()


def IrafExecute(task,
                envdict,
                stdin=None,
                stdout=None,
                stderr=None,
                stdgraph=None):
    """Execute IRAF task (defined by the IrafTask object task)
    using the provided envionmental variables."""

    global processCache
    try:
        # Start 'er up
        irafprocess = processCache.get(task, envdict)
    except (IrafError, subproc.SubprocessError, IrafProcessError) as value:
        raise

    # Run it
    try:
        taskname = task.getName()
        if stdgraph:
            # Redirect graphics
            prevkernel = gki.kernel
            gki.kernel = gki.GkiRedirection(stdgraph)
            gki.kernel.wcs = prevkernel.wcs
        else:
            # do graphics task initialization
            gki.kernel.taskStart(taskname)
            focusMark = wutil.focusController.getCurrentMark()
            gki.kernel.pushStdio(None, None, None)
        try:
            irafprocess.run(task, pstdin=stdin, pstdout=stdout, pstderr=stderr)
        finally:
            if stdgraph:
                # undo graphics redirection
                gki.kernel = prevkernel
            else:
                # for interactive graphics restore previous stdio
                wutil.focusController.restoreToMark(focusMark)
                gki.kernel.popStdio()
        # do any cleanup needed on task completion
        if not stdgraph:
            gki.kernel.taskDone(taskname)
    except KeyboardInterrupt:
        # On keyboard interrupt (^C), kill the subprocess
        processCache.kill(irafprocess)
        raise
    except (IrafError, IrafProcessError) as exc:
        # on error, kill the subprocess, then re-raise the original exception
        try:
            processCache.kill(irafprocess)
        except Exception as exc2:
            # append new exception text to previous one (right thing to do?)
            exc.args = exc.args + exc2.args
        raise exc
    else:
        # add to the process cache on successful exit
        processCache.add(irafprocess)
    return


# patterns for matching messages from process

# '=param' and '_curpack' have to be treated specially because
# they write to the task rather than to stdout
# 'param=value' is special because it allows errors

_p_par_get = r'\s*=\s*(?P<gname>[a-zA-Z_$][\w.]*(?:\[\d+\])?)\s*\n'
_p_par_set = r'(?P<sname>[a-zA-Z_][\w.]*(?:\[\d+\])?)\s*=\s*(?P<svalue>.*)\n'
_re_msg = re.compile(r'(?P<par_get>' + _p_par_get + ')|' + r'(?P<par_set>' +
                     _p_par_set + ')')

_p_curpack = r'_curpack(?:\s.*|)\n'
_p_stty = r'stty.*\n'
_p_sysescape = r'!(?P<sys_cmd>.*)\n'

_re_clcmd = re.compile(r'(?P<curpack>' + _p_curpack + ')|' + r'(?P<stty>' +
                       _p_stty + ')|' + r'(?P<sysescape>' + _p_sysescape + ')')


class IrafProcess:
    """IRAF process class"""

    def __init__(self, executable):
        """Start IRAF task executable."""

        if test_probe:
            sys.stdout.write(f"Starting IRAF process for {executable}\n")

        self.executable = executable
        self.process = subproc.Subprocess(executable + ' -c')
        self.running = 0  # flag indicating whether process is active
        self.task = None
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self.default_stdin = None
        self.default_stdout = None
        self.default_stderr = None
        self.stdinIsatty = 0
        self.stdoutIsatty = 0
        self.envVarList = []
        self.par_set_msg_buf = ''

    def initialize(self, envdict):
        """Initialization: Copy environment variables to process"""

        outenvstr = []
        for key, value in envdict.items():
            outenvstr.append(f"set {key}={str(value)}\n")
        outenvstr.append(f"chdir {os.getcwd()}\n")
        if outenvstr:
            self.writeString("".join(outenvstr))
        self.envVarList = []

        # end set up mode
        self.writeString('_go_\n')

    def appendEnv(self, msg):
        """Append environment variable set command to list"""

        # Changes are saved and sent to task before starting
        # it next time.  Note that environment variable changes
        # are not immediately sent to a running task (because it is
        # not expecting them.)

        self.envVarList.append(msg)

    def run(self, task, pstdin=None, pstdout=None, pstderr=None):
        """Run the IRAF logical task (which must be in this executable)

        The IrafTask object must have these methods:

        getName(): return the name of the task
        getParam(param): get parameter value
        setParam(param,value): set parameter value
        getParObject(param): get parameter object
        """

        if test_probe:
            sys.stdout.write(f"Running IRAF task {task} "
                             f"from {self.executable}\n")
        self.task = task
        # set IO streams
        stdin = pstdin or sys.stdin
        stdout = pstdout or sys.stdout
        stderr = pstderr or sys.stderr
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr
        self.default_stdin = stdin
        self.default_stdout = stdout
        self.default_stderr = stderr

        # stdinIsatty flag is used in xfer to decide whether to
        # read inputs in blocks or not.  As long as input comes
        # from __stdin__, consider it equivalent to a tty.
        self.stdinIsatty = (hasattr(stdin, 'isatty') and stdin.isatty()) or \
            self.stdin == sys.__stdin__
        self.stdoutIsatty = hasattr(stdout, 'isatty') and stdout.isatty()

        # stdinIsraw flag is used in xfer to decide whether to
        # read inputs as RAW input or not.
        self.stdinIsraw = False

        # redir_info tells task that IO has been redirected

        redir_info = ''
        if pstdin and pstdin != sys.__stdin__:
            redir_info = '<'
        if (pstdout and pstdout != sys.__stdout__) or \
           (pstderr and pstderr != sys.__stderr__):
            redir_info = redir_info + '>'

        # update IRAF environment variables if necessary
        if self.envVarList:
            self.writeString(''.join(self.envVarList))
            self.envVarList = []

        # if stdout is a terminal, set the lines & columns sizes
        # this ensures that they are up-to-date at the start of the task
        # (which is better than the CL does)
        if self.stdoutIsatty:
            nlines, ncols = wutil.getTermWindowSize()
            self.writeString(f'set ttynlines={nlines:d}\n'
                             f'set ttyncols={ncols:d}\n')

        taskname = self.task.getName()
        # remove leading underscore, which is just a convention for CL
        if taskname[:1] == '_':
            taskname = taskname[1:]
        self.writeString(taskname + redir_info + '\n')
        self.running = 1
        try:
            # begin slave mode
            self.slave()
        finally:
            self.running = 0

    def isAlive(self):
        """Returns true if process appears to be OK"""

        return self.process.active()

    def terminate(self):
        """Terminate the IRAF process (when process in normal end state)"""

        # Standard IRAF task termination (assuming we already have the
        # task's attention for input):
        #   Send bye message to task
        #   Wait briefly for EOF, which signals task is done
        #   Kill it anyway if it is still hanging around

        if not self.process.pid:
            return  # no need, process gone
        try:
            self.writeString("bye\n")
            if self.process.wait(0.5):
                return
        except (IrafProcessError, subproc.SubprocessError):
            pass
        # No more Mr. Nice Guy
        try:
            self.process.die()
        except subproc.SubprocessError as e:
            if Verbose > 0:
                # too bad, if we can't kill it assume it is already dead
                self.stderr.write(f"Warning: cannot terminate process {e}\n")
                self.stderr.flush()

    def kill(self, verbose=1):
        """Kill the IRAF process (more drastic than terminate)"""

        # Try stopping process in IRAF-approved way first; if that fails
        # blow it away. Copied with minor mods from subproc.py.

        if not self.process.pid:
            return  # no need, process gone

        self.stdout.flush()
        self.stderr.flush()
        from . import pyrafglobals
        if verbose and not pyrafglobals._use_ecl:
            sys.stderr.write(f"Killing IRAF task `{self.task.getName()}'\n")
            sys.stderr.flush()
        if self.process.cont():
            # get the task's attention for input
            try:
                os.kill(self.process.pid, signal.SIGTERM)
            except os.error:
                pass
        self.terminate()

    def writeString(self, s):
        """Convert ascii string to IRAF form and write to IRAF process"""

        self.write(Asc2IrafString(s))

    def readString(self):
        """Read IRAF string from process and convert to ascii string"""

        return Iraf2AscString(self.read())

    def write(self, data):
        """write binary data to IRAF process in blocks of <= 4096 bytes"""

        i = 0
        block = 4096
        try:
            while i < len(data):
                # Write:
                #  IRAF magic number
                #  number of following bytes
                #  data
                dsection = data[i:i + block]
                # the arg parts to the following are all type bytes in PY3K
                self.process.write(IPC_PREFIX +
                                   struct.pack('=h', len(dsection)) +
                                   dsection)
                i = i + block
        except subproc.SubprocessError as e:
            raise IrafProcessError(f"Error in write: {str(e)}")

    def read(self):
        """Read binary data from IRAF pipe"""
        try:
            # read pipe header first (self.process is subproc.Subprocess)
            header = self.process.read(4)  # read returns bytes
            if header[0:2] != IPC_PREFIX:
                raise IrafProcessError("Not a legal IRAF pipe record: " +
                                       str(header[0:2]))
            ntemp = struct.unpack('=h', header[2:])
            nbytes = ntemp[0]
            # read the rest
            data = self.process.read(nbytes)  # read returns bytes
            return data
        except subproc.SubprocessError as e:
            raise IrafProcessError(f"Error in read: {str(e)}")

    def slave(self):
        """Talk to the IRAF process in slave mode.
        Raises an IrafProcessError if an error occurs."""

        self.msg = ''
        self.xferline = ''
        # try to speed up loop a bit
        re_match = _re_msg.match
        xfer = self.xfer
        xmit = self.xmit
        par_get = self.par_get
        par_set = self.par_set
        executeClCommand = self.executeClCommand

        while True:

            # each read may return multiple lines; only
            # read new data when old has been used up

            if not self.msg:
                self.msg = self.readString()

            msg = self.msg
            msg5 = msg[:5]

            if msg5 == 'xfer(':
                xfer()
            elif msg5 == 'xmit(':
                xmit()
            elif msg[:4] == 'bye\n':
                return
            elif msg5 in ['error', 'ERROR']:
                errno, text = self._scanErrno(msg)
                raise IrafProcessError("IRAF task terminated abnormally\n" +
                                       msg,
                                       errno=errno,
                                       errmsg=text,
                                       errtask=self.task.getName())
            else:
                # pattern match to see what this message is
                mcmd = re_match(msg)

                # assume each par_set msg ends with either a 'bye' line or with a par_get line
                if (mcmd and mcmd.group('par_set')) or len(
                        self.par_set_msg_buf) > 0:
                    # enter this section if we got a par_set, OR if we are in the
                    # middle of a par_set coming in multiple msgs...
                    msg_last_line = msg.strip().split('\n')[-1]
                    # either way, first line of msg is a par_set, since our re matched,
                    # but check the LAST line to see if this is the end
                    if msg_last_line == 'bye' or msg_last_line.startswith('='):
                        # we have the whole msg now (or maybe did in 1st shot)
                        #                       L.log('FULL matched (ps):\n'+('='*60+'\n')+msg+'\n'+('='*60))
                        if len(self.par_set_msg_buf) > 0:
                            # is final part of a msg that came in parts
                            self.par_set_msg_buf += msg
                            mcmd = re_match(self.par_set_msg_buf)
                            par_set(mcmd)
                            self.par_set_msg_buf = ''  # flag to not wait for more
                            self.msg = 'bye\n'
                        else:
                            # is a normal par_set that came all in one shot
                            par_set(mcmd)
                    else:
                        # We only have a partial message here, so don't
                        # do any par_set-ing until we have the whole msg
                        #                       L.log('PARTIAL matched (ps):\n'+('='*60+'\n')+msg+'\n'+('='*60))
                        self.par_set_msg_buf += msg
                        # empty self.msg to trigger us to read more
                        self.msg = ''
                elif mcmd and mcmd.group('par_get'):
                    #                   L.log('matched (pg):\n'+('='*60+'\n')+msg+'\n'+('='*60))
                    par_get(mcmd)
                elif mcmd is None:
                    #                   L.log('NO match!:\n'+('='*60+'\n')+msg+'\n'+('='*60))
                    # Could be any legal CL command.
                    executeClCommand()
                else:
                    # should never get here
                    #                   L.log("Program bug: uninterpreted message: " + msg)
                    raise RuntimeError(
                        f"Program bug: uninterpreted message `{msg}'")

    def _scanErrno(self, msg):
        sp = "\\s*"
        quote = "\""
        m = re.search(
            "(ERROR|error)" + sp + "\\(" + sp + "(\\d+)" + sp + "," + sp +
            quote + "([^\\\"]*)" + quote + sp + "\\)" + sp, msg)
        if m:
            try:
                errno = int(m.group(2))
            except:
                errno = -9999999
            text = m.group(3)
        else:
            errno, text = -9999998, msg
        return errno, text

    def setStdio(self):
        """Set self.stdin/stdout based on current state

        If in graphics mode, I/O is done through status line.
        Else I/O is done through normal streams.
        """

        self.stdout = gki.kernel.getStdout(default=self.default_stdout)
        self.stderr = gki.kernel.getStderr(default=self.default_stderr)
        self.stdin = gki.kernel.getStdin(default=self.default_stdin)

    def par_get(self, mcmd):
        # parameter get request
        # list parameters can generate EOF exception
        paramname = mcmd.group('gname')
        # interactive parameter prompts may be redirected to the graphics
        # status line, but do not get redirected to a file
        c_stdin = sys.stdin
        c_stdout = sys.stdout
        c_stderr = sys.stderr
        #
        # These lines reset stdin/stdout/stderr to the graphics
        # window.
        sys.stdin = gki.kernel.getStdin(default=sys.__stdin__)
        sys.stdout = gki.kernel.getStdout(default=sys.__stdout__)
        sys.stderr = gki.kernel.getStderr(default=sys.__stderr__)
        try:
            try:
                pmsg = self.task.getParam(paramname, native=0)
                if not isinstance(pmsg, str):
                    # Only psets should return a non-string type (they
                    # return the task object).
                    # Work a little to get the underlying string value.
                    # (Yes, this is klugy, but there are so many places
                    # where it is necessary to return the task object
                    # for a pset that this seems like a small price to
                    # pay.)
                    pobj = self.task.getParObject(paramname)
                    pmsg = pobj.get(lpar=1)
                else:
                    # replace all newlines in strings with "\n"
                    pmsg = pmsg.replace('\n', '\\n')
                pmsg = pmsg + '\n'
            except EOFError:
                pmsg = 'EOF\n'
        finally:
            # Make sure that STDIN/STDOUT/STDERR are reset to
            # tty mode instead of being stuck in graphics window.
            sys.stdin = c_stdin
            sys.stdout = c_stdout
            sys.stderr = c_stderr
        self.writeString(pmsg)
        self.msg = self.msg[mcmd.end():]

    def par_set(self, mcmd):
        # set value of parameter
        group = mcmd.group
        paramname = group('sname')
        newvalue = group('svalue')
        self.msg = self.msg[mcmd.end():]
        try:
            self.task.setParam(paramname, newvalue)
        except ValueError as e:
            # on ValueError, just print warning and then force set
            if Verbose > 0:
                self.stderr.write(f'Warning: {e}\n')
                self.stderr.flush()
            self.task.setParam(paramname, newvalue, check=0)

    def xmit(self):
        """Handle xmit data transmissions"""

        chan, nbytes = self.chanbytes()

        checkForEscapeSeq = (chan == 4 and (nbytes == 6 or nbytes == 5))
        xdata = self.read()

        if len(xdata) != 2 * nbytes:
            raise IrafProcessError("Error, wrong number of bytes read\n"
                                   f"(got {len(xdata):d}, "
                                   f"expected {2 * nbytes:d}, chan {chan:d})")
        if chan == 4:
            if self.task.getTbflag():
                # for tasks with .tb flag, stdout is binary data
                txdata = xdata
            else:
                # normally stdout is translated text data
                txdata = Iraf2AscString(xdata)

            if checkForEscapeSeq:
                if (txdata[0:5] == "\033+rAw"):
                    # Turn on RAW mode for STDIN
                    self.stdinIsraw = True
                    return

                if (txdata[0:5] == "\033-rAw"):
                    # Turn off RAW mode for STDIN
                    self.stdinIsraw = False
                    return

                if (txdata[0:5] == "\033=rDw"):
                    # ignore IRAF io escape sequences for now
                    # This mode enables screen redraw code
                    return

            self.stdout.write(txdata)
            self.stdout.flush()
        elif chan == 5:
            sys.stdout.flush()
            self.stderr.write(Iraf2AscString(xdata))
            self.stderr.flush()
        elif chan == 6:
            gki.kernel.append(numpy.frombuffer(xdata, dtype=numpy.int16))
        elif chan == 7:
            stdimagekernel.append(numpy.frombuffer(xdata, dtype=numpy.int16))
        elif chan == 8:
            self.stdout.write("data for STDPLOT\n")
            self.stdout.flush()
        elif chan == 9:
            sdata = numpy.frombuffer(xdata, dtype=numpy.int16)
            if isBigEndian:
                # Actually, the channel destination is sent
                # by the iraf process as a 4 byte int, the following
                # code basically chooses the right two bytes to
                # find it in.
                forChan = sdata[1]
            else:
                forChan = sdata[0]
            if forChan == 6:
                # STDPLOT control
                # Pass it to the kernel to deal with
                # Only returns a value for getwcs
                wcs = gki.kernel.control(sdata[2:])
                if wcs:
                    # Write directly to stdin of subprocess;
                    # strangely enough, it doesn't use the
                    # STDGRAPH I/O channel.
                    self.write(wcs)
                    gki.kernel.clearReturnData()
                self.setStdio()
            elif forChan == 7:
                # STDIMAGE control, see previous block for comments on details
                wcs = stdimagekernel.control(sdata[2:])
                if wcs:
                    self.write(wcs)
                    stdimagekernel.clearReturnData()
            else:
                self.stdout.write("GRAPHICS control data "
                                  f"for channel {forChan:d}\n")
                self.stdout.flush()
        else:
            self.stdout.write(f"data for channel {chan:d}\n")
            self.stdout.flush()

    def xfer(self):
        """Handle xfer data requests"""

        chan, nbytes = self.chanbytes()
        nchars = nbytes // 2
        if chan == 3:

            # Read data from stdin unless xferline already has
            # some untransmitted data from a previous read

            line = self.xferline
            if not line:
                if self.stdinIsatty:
                    if not self.stdinIsraw:
                        self.setStdio()
                        # tty input, read a single line
                        line = irafutils.tkreadline(self.stdin)
                    else:
                        # Raw input requested
                        # Input character needs to be converted
                        # to its ASCII integer code.
                        # line = raw_input()
                        line = irafukey.getSingleTTYChar()
                else:
                    # file input, read a big chunk of data

                    # NOTE: Here we are reading ahead in the stdin stream,
                    # which works fine with a single IRAF task.  This approach
                    # could conceivably cause problems if some program expects
                    # to continue reading from this stream starting at the
                    # first line not read by the IRAF task.  That sounds
                    # very unlikely to be a good design and will not work
                    # as a result of this approach.  Sending the data in
                    # large chunks is *much* faster than sending many
                    # small messages (due to the overhead of handshaking
                    # between the CL task and this main process.)  That's
                    # why it is done this way.

                    line = self.stdin.read(nchars)
                self.xferline = line
            # Send two messages, the first with the number of characters
            # in the line and the second with the line itself.
            # For very long lines, may need multiple messages.  Task
            # will keep sending xfer requests until it gets the
            # newline.

            if not self.stdinIsraw:
                if len(line) <= nchars:
                    # short line
                    self.writeString(str(len(line)))
                    self.writeString(line)
                    self.xferline = ''
                else:
                    # long line
                    self.writeString(str(nchars))
                    self.writeString(line[:nchars])
                    self.xferline = line[nchars:]
            else:
                self.writeString(str(len(line)))
                self.writeString(line)
                self.xferline = ''
        else:
            raise IrafProcessError(f"xfer request for unknown channel {chan:d}")

    def chanbytes(self):
        """Parse xmit(chan,nbytes) and return integer tuple

        Assumes first 5 characters have already been checked
        """
        msg = self.msg
        try:
            i = msg.find(",", 5)
            if i < 0 or msg[-2:] != ")\n":
                raise ValueError()
            chan = int(msg[5:i])
            nbytes = int(msg[i + 1:-2])
            self.msg = ''
        except ValueError:
            raise IrafProcessError(f"Illegal message format `{self.msg}'")
        return chan, nbytes

    def executeClCommand(self):
        """Execute an arbitrary CL command"""

        # pattern match to handle special commands that write to task
        mcmd = _re_clcmd.match(self.msg)
        if mcmd is None:
            # general command
            i = self.msg.find("\n")
            if i >= 0:
                cmd = self.msg[:i + 1]
                self.msg = self.msg[i + 1:]
            else:
                cmd = self.msg
                self.msg = ""
            if not (cmd.find(IPCOUT) >= 0):
                # normal case -- execute the CL script code
                # redirect I/O (but don't use graphics status line)
                iraf.clExecute(cmd,
                               Stdout=self.default_stdout,
                               Stdin=self.default_stdin,
                               Stderr=self.default_stderr)
            else:
                #
                # Bizzaro protocol -- redirection to file with special
                # name given by IPCOUT causes output to be written back
                # to subprocess instead of to stdout.
                #
                # I think this only occurs one place in the entire system
                # (in clio/clepset.x) so I'm not trying to handle it robustly.
                # Just raise an exception if it does not fit my preconceptions.
                #
                ll = -(len(IPCOUT) + 3)
                if cmd[ll:] != f"> {IPCOUT}\n":
                    raise IrafProcessError(
                        f"Error: cannot understand IPCOUT syntax in `{cmd}'")
                sys.stdout.flush()
                # strip the redirection off and capture output of command
                buffer = io.StringIO()
                # redirect other I/O (but don't use graphics status line)
                iraf.clExecute(cmd[:ll] + "\n",
                               Stdout=buffer,
                               Stdin=self.default_stdin,
                               Stderr=self.default_stderr)
                # send it off to the task with special flag line at end
                buffer.write(IPCDONEMSG)
                self.writeString(buffer.getvalue())
                buffer.close()
        elif mcmd.group('stty'):
            # terminal window size
            if self.stdoutIsatty:
                nlines, ncols = wutil.getTermWindowSize()
            else:
                # a kluge -- if self.stdout is not a tty, assume it is a
                # file and give a large number for the number of lines
                nlines, ncols = 100000, 80
            self.writeString(f'set ttynlines={nlines:d}\n'
                             f'set ttyncols={ncols:d}\n')
            self.msg = self.msg[mcmd.end():]
        elif mcmd.group('curpack'):
            # current package request
            self.writeString(iraf.curpack() + '\n')
            self.msg = self.msg[mcmd.end():]
        elif mcmd.group('sysescape'):
            # OS escape
            tmsg = mcmd.group('sys_cmd')
            # use my version of system command so redirection works
            sysstatus = iraf.clOscmd(tmsg,
                                     Stdin=self.stdin,
                                     Stdout=self.stdout,
                                     Stderr=self.stderr)
            self.writeString(str(sysstatus) + "\n")
            self.msg = self.msg[mcmd.end():]
            # self.stdout.write(self.msg + "\n")
        else:
            # should never get here
            raise RuntimeError("Program bug: uninterpreted message "
                               f"`{self.msg}'")


# IRAF string conversions using numpy module


def Asc2IrafString(ascii_string):
    """translate ascii to IRAF 16-bit string format"""
    inarr = numpy.frombuffer(ascii_string.encode('ascii'), numpy.int8)
    retval = inarr.astype(numpy.int16).tobytes()
    #   log_task_comm('Asc2IrafString (write to task)', retval, False)
    return retval


def Iraf2AscString(iraf_string):
    """translate 16-bit IRAF characters to ascii"""
    inarr = numpy.frombuffer(iraf_string, numpy.int16)
    retval = inarr.astype(numpy.int8).tobytes().decode('ascii')
    #   log_task_comm('Iraf2AscString', retval, True)
    return retval


def log_task_comm(pfx, strbuf, expectAsStr, shorten=True):
    import some_pkg_w_a_log_func as L
    assert isinstance(strbuf,
                      (str, str, bytes)), "?!: " + str(type(strbuf))
    if expectAsStr:
        assert isinstance(strbuf, str), "Unexpected type: " + str(type(strbuf))
    if isinstance(strbuf, (str, str)):
        out = strbuf.strip()
        if shorten:
            out = out[0:30]
        L.log(pfx + ' (str): ' + out)
    else:  # strbuf is bytes
        out = strbuf.decode().strip()
        if shorten:
            out = out[0:30]
        L.log(pfx + ' (byt): ' + out)
