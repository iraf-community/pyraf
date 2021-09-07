"""This module adds IRAF ECL style error handling to PyRAF."""



import inspect
import sys
from stsci.tools.irafglobals import Verbose
from . import pyrafglobals
from . import iraftask
from . import irafexecute
from . import iraf

executionMonitor = None


class EclState:
    """An object which records the ECL state for one invocation of a CL proc:

    1. The procedure's linemap converting Python line numberss to CL line numbers.

    2. A mutable counter for tracking iferr blocking.
    """

    def __init__(self, linemap):
        self._value = 0
        self._linemap = linemap

    def __iadd__(self, value):
        self._value += value
        return self

    def __int__(self):
        return self._value


def getTaskModule():
    """Returns the module which supplies Task classes for the current
    language mode,  either ECL or classic CL.
    """
    if pyrafglobals._use_ecl:
        from . import irafecl
        return irafecl
    else:
        return iraftask


class Erract:
    """Erract is a state variable (singleton) which corresponds to the IRAF ECL
    environment variable 'erract'.  erract has the following properties which
    control ECL exception handling:

    abort | noabort  An ECL task should stop and unwind when it encounters an untrapped error.

    trace | notrace  Output to stderr for each task failure.

    flpr  | noflpr   Flush the process cache for failed tasks.

    clear | noclear  Reset the $errno, $errmsg, $errtask variables with each task invocation, or not.

    full  | nofull   Show tracebacks for the entire ECL call stack or just the erring task.

    ecl | noecl      Use ECL style error handling or classic PyRAF exception handling.
    """

    def __init__(self,
                 clear=True,
                 flpr=True,
                 abort=True,
                 trace=True,
                 full=True,
                 ecl=True):
        self.clear = clear
        self.flpr = flpr
        self.abort = abort
        self.trace = trace
        self.full = full
        self.ecl = ecl
        self._fields = ["abort", "trace", "flpr", "clear", "full", "ecl"]

    def states(self):
        ans = ""
        for s in self._fields:
            if not self.__dict__[s]:
                s = "no" + s
            ans += s + " "
        return ans

    def set_one(self, field):
        flag = not field.startswith("no")
        if not flag:
            field = field[2:]
        if field in self._fields:
            self.__dict__[field] = flag
        else:
            raise ValueError("set erract:  unknown behavior '" + field + "'")

    def adjust(self, values):
        for a in values.split():
            self.set_one(a)


erract = Erract()

# IrafExecute --> IrafTask._run --> IrafTask.run
# user_code --> IrafPyTask._run  --> IrafTask.run


def _ecl_runframe(frame):
    """Determines if frame corresponds to an IrafTask._run() method call."""
    # print "runframe:",frame.f_code.co_name
    if frame.f_code.co_name != "_run":  # XXXX necessary but not sufficient
        return False
    return True


def _ecl_parent_task():
    """Returns the local variables of the task which called this one.
    """
    f = inspect.currentframe()
    while f and not _ecl_runframe(f):
        f = f.f_back
    if not f:
        return iraf.cl
    return f.f_locals["self"]


def _ecl_interpreted_frame(frame=None):
    """Returns the stack frame corresponding to the executing Python code of
    the nearest enclosing CL task.
    """
    if frame is None:
        f = inspect.currentframe()
    else:
        f = frame
    priors = []
    while f and not _ecl_runframe(f):
        priors.append(f)
        f = f.f_back
    if len(priors) >= 2:
        return priors[-2]
    else:
        return None


class EclBase:

    def __init__(self, *args, **kw):
        self.__dict__['DOLLARerrno'] = 0
        self.__dict__['DOLLARerrmsg'] = ""
        self.__dict__['DOLLARerrtask'] = ""
        self.__dict__['DOLLARerr_dzvalue'] = 1
        self.__dict__['_ecl_pseudos'] = [
            'DOLLARerrno', 'DOLLARerrmsg', 'DOLLARerrtask', 'DOLLARerr_dzvalue'
        ]

    def is_pseudo(self, name):
        """Returns True iff 'name' is a pseudo variable or begins with _ecl"""
        return (name
                in self.__dict__["_ecl_pseudos"]) or name.startswith("_ecl")

    def run(self, *args, **kw):  # OVERRIDE IrafTask.run
        """Execute this task with the specified arguments"""

        self.initTask(force=1)

        # Special _save keyword turns on parameter-saving.
        # Default is *not* to save parameters (so it is necessary
        # to use _save=1 to get parameter changes to be persistent.)
        if '_save' in kw:
            save = kw['_save']
            del kw['_save']
        else:
            save = 0

        # Handle other special keywords
        specialKW = self._specialKW(kw)

        # Special Stdout, Stdin, Stderr keywords are used to redirect IO
        redirKW, closeFHList = iraf.redirProcess(kw)

        # set parameters
        kw['_setMode'] = 1
        self.setParList(*args, **kw)

        if Verbose > 1:
            print(f"run {self._name} ({self.__class__.__name__}: "
                  f"{self._fullpath})")
            if self._runningParList:
                self._runningParList.lParam()

        # delete list of param dictionaries so it will be
        # recreated in up-to-date version if needed
        self._parDictList = None
        # apply IO redirection
        resetList = self._applyRedir(redirKW)

        self._ecl_clear_error_params()

        def _runcore():
            try:
                # Hook for execution monitor
                if executionMonitor:
                    executionMonitor(self)
                self._run(redirKW, specialKW)
                self._updateParList(save)
                if Verbose > 1:
                    print('Successful task termination', file=sys.stderr)
            finally:
                rv = self._resetRedir(resetList, closeFHList)
                self._deleteRunningParList()
                if self._parDictList:
                    self._parDictList[0] = (self._name, self.getParDict())
                if executionMonitor:
                    executionMonitor()
            return rv

        # if self._ecl_iferr_entered() and
        if erract.ecl:
            try:
                return _runcore()
            except Exception as e:
                self._ecl_handle_error(e)
        else:
            return _runcore()

    def _run(self, redirKW, specialKW):
        # OVERRIDE IrafTask._run for primitive (SPP, C, etc.) tasks to avoid exception trap.
        irafexecute.IrafExecute(self, iraf.getVarDict(), **redirKW)

    def _ecl_push_err(self):
        """Method call emitted in compiled CL code to start an iferr
        block.  Increments local iferr state counter to track iferr
        block nesting.
        """
        s = self._ecl_state()
        s += 1
        self._ecl_set_error_params(0, '', '')

    def _ecl_pop_err(self):
        """Method call emitted in compiled CL code to close an iferr
        block and start the handler.  Returns $errno which is 0 iff no
        error occurred.  Decrements local iferr state counter to track block nesting.
        """
        s = self._ecl_state()
        s += -1
        return self.DOLLARerrno

    def _ecl_handle_error(self, e):
        """IrafTask version of handle error:  register error with calling task but continue."""
        self._ecl_record_error(e)
        if erract.flpr:
            iraf.flpr(self)
        parent = _ecl_parent_task()
        parent._ecl_record_error(e)
        self._ecl_trace(parent._ecl_err_msg(e))

    def _ecl_trace(self, *args):
        """Outputs an ECL error message to stderr iff erract.trace is True."""
        if erract.trace:
            s = ""
            for a in args:
                s += str(a) + " "
            sys.stderr.write(s + "\n")
            sys.stderr.flush()

    def _ecl_exception_properties(self, e):
        """This is a 'safe wrapper' which extracts the ECL pseudo parameter values from an
        exception.  It works for both ECL and non-ECL exceptions.
        """
        return (getattr(e, "errno",
                        -1), getattr(e, "errmsg",
                                     str(e)), getattr(e, "errtask", ""))

    def _ecl_record_error(self, e):
        self._ecl_set_error_params(*self._ecl_exception_properties(e))

    def _ecl_set_error_params(self, errno, msg, taskname):
        """Sets the ECL pseduo parameters for this task."""
        self.DOLLARerrno = errno
        self.DOLLARerrmsg = msg
        self.DOLLARerrtask = taskname

    def _ecl_clear_error_params(self):
        """Clears the ECL pseudo parameters to a non-error condition."""
        if erract.clear:
            self._ecl_set_error_params(0, "", "")

    def _ecl_err_msg(self, e):
        """Formats an ECL error message from an exception and returns it as a string."""
        errno, errmsg, errtask = self._ecl_exception_properties(e)
        if errno and errmsg and errtask:
            text = (f"Error ({errno:d}): on line {self._ecl_get_lineno():d} "
                    f"of '{self._name}' from '{errtask}':\n\t'{errmsg}'")
        else:
            text = str(e)
        return text

    def _ecl_get_lineno(self, frame=None):
        """_ecl_get_lineno fetches the innermost frame of Python code compiled from a CL task.
        and then translates the current line number in that frame into it's CL line number
        and returns it.
        """
        try:
            f = _ecl_interpreted_frame(frame)
            map = f.f_locals["_ecl"]._linemap
            return map[f.f_lineno]
        except:
            return 0

    def _ecl_state(self, frame=None):
        """returns the EclState object corresponding to this task invocation."""
        locals = _ecl_interpreted_frame(frame).f_locals
        return locals["_ecl"]

    def _ecl_iferr_entered(self):
        """returns True iff the current invocation of the task self is in an iferr or ifnoerr guarded block."""
        try:
            return int(self._ecl_state()) > 0
        except KeyError:
            return False

    def _ecl_safe_divide(self, a, b):
        """_ecl_safe_divide is used to wrap the division operator for ECL code and trap divide-by-zero errors."""
        if b == 0:
            if not erract.abort or self._ecl_iferr_entered():
                self._ecl_trace(f"Warning on line {self._ecl_get_lineno():d} "
                                f"of '{self._name}':  "
                                "divide by zero - using $err_dzvalue =",
                                self.DOLLARerr_dzvalue)
                return self.DOLLARerr_dzvalue
            else:
                iraf.error(1, "divide by zero", self._name, suppress=False)
        if isinstance(a, int) and isinstance(b, int):
            return a // b
        else:
            return a / b

    def _ecl_safe_modulo(self, a, b):
        """_ecl_safe_modulus is used to wrap the modulus operator for ECL code and trap mod-by-zero errors."""
        if b == 0:
            if not erract.abort or self._ecl_iferr_entered():
                self._ecl_trace(f"Warning on line {self._ecl_get_lineno():d} "
                                f"of task '{self._name}':  "
                                "modulo by zero - using $err_dzvalue =",
                                self.DOLLARerr_dzvalue)
                return self.DOLLARerr_dzvalue
            else:
                iraf.error(1, "modulo by zero", self._name, suppress=False)
        return a % b


class SimpleTraceback(EclBase):

    def _ecl_handle_error(self, e):
        self._ecl_record_error(e)
        raise e


class EclTraceback(EclBase):

    def _ecl_handle_error(self, e):
        """Python task version of handle_error:  do traceback and possibly abort."""
        self._ecl_record_error(e)
        parent = _ecl_parent_task()
        if parent:
            parent._ecl_record_error(e)
        if hasattr(e, "_ecl_traced"):
            if erract.full:
                self._ecl_traceback(e)
            raise e
        else:
            try:
                self._ecl_trace(f"ERROR ({e.errno:d}): {e.errmsg}")
            except:
                self._ecl_trace("ERROR:", str(e))
            self._ecl_traceback(e)
            if erract.abort:  # and not self._ecl_iferr_entered():
                e._ecl_traced = True
                raise e

    def _ecl_get_code(self, task, frame=None):
        pass

    def _ecl_traceback(self, e):
        raising_frame = inspect.trace()[-1][0]
        lineno = self._ecl_get_lineno(frame=raising_frame)
        cl_file = self.getFilename()
        try:
            cl_code = open(cl_file).readlines()[lineno - 1].strip()
        except OSError:
            cl_code = "<source code not available>"
        if hasattr(e, "_ecl_suppress_first_trace") and \
                e._ecl_suppress_first_trace:
            del e._ecl_suppress_first_trace
        else:
            self._ecl_trace("  ", repr(cl_code))
        self._ecl_trace(f"      line {lineno:d}: {cl_file}")
        parent = _ecl_parent_task()
        if parent:
            parent_lineno = self._ecl_get_lineno()
            parent_file = parent.getFilename()
            try:
                parent_code = open(parent_file).readlines()[parent_lineno -
                                                            1].strip()
                self._ecl_trace("      called as:", repr(parent_code))
            except:
                pass


## The following classes exist as "ECL enabled" drop in replacements for the original
## PyRAF task classes.  I factored things this way in an attempt to minimize the impact
## of ECL changes on ordinary PyRAF CL.


class EclTask(EclBase, iraftask.IrafTask):

    def __init__(self, *args, **kw):
        EclBase.__init__(self, *args, **kw)
        iraftask.IrafTask.__init__(self, *args, **kw)


IrafTask = EclTask


class EclGKITask(SimpleTraceback, iraftask.IrafGKITask):

    def __init__(self, *args, **kw):
        SimpleTraceback.__init__(self, *args, **kw)
        iraftask.IrafGKITask.__init__(self, *args, **kw)


IrafGKITask = EclGKITask


class EclPset(SimpleTraceback, iraftask.IrafPset):

    def __init__(self, *args, **kw):
        SimpleTraceback.__init__(self, *args, **kw)
        iraftask.IrafPset.__init__(self, *args, **kw)

    def _run(self, *args, **kw):
        return iraftask.IrafPset._run(self, *args, **kw)


IrafPset = EclPset


class EclPythonTask(EclTraceback, iraftask.IrafPythonTask):

    def __init__(self, *args, **kw):
        EclTraceback.__init__(self, *args, **kw)
        iraftask.IrafPythonTask.__init__(self, *args, **kw)

    def _run(self, *args, **kw):
        return iraftask.IrafPythonTask._run(self, *args, **kw)


IrafPythonTask = EclPythonTask


class EclCLTask(EclTraceback, iraftask.IrafCLTask):

    def __init__(self, *args, **kw):
        EclTraceback.__init__(self, *args, **kw)
        iraftask.IrafCLTask.__init__(self, *args, **kw)

    def _run(self, *args, **kw):
        return iraftask.IrafCLTask._run(self, *args, **kw)


IrafCLTask = EclCLTask


class EclForeignTask(SimpleTraceback, iraftask.IrafForeignTask):

    def __init__(self, *args, **kw):
        SimpleTraceback.__init__(self, *args, **kw)
        iraftask.IrafForeignTask.__init__(self, *args, **kw)

    def _run(self, *args, **kw):
        return iraftask.IrafForeignTask._run(self, *args, **kw)


IrafForeignTask = EclForeignTask


class EclPkg(EclTraceback, iraftask.IrafPkg):

    def __init__(self, *args, **kw):
        EclTraceback.__init__(self, *args, **kw)
        iraftask.IrafPkg.__init__(self, *args, **kw)

    def _run(self, *args, **kw):
        return iraftask.IrafPkg._run(self, *args, **kw)


IrafPkg = EclPkg


def mutateCLTask2Pkg(o, loaded=1, klass=EclPkg):
    return iraftask.mutateCLTask2Pkg(o, loaded=loaded, klass=klass)
