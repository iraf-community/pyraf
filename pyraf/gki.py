"""
IRAF GKI interpreter -- abstract implementation

The main classes here are GkiKernel and GkiController.

GkiKernel is the base class for graphics kernel implementations.  Methods:

    control() append()
        Called by irafexecute to plot IRAF GKI metacode.
    pushStdio() popStdio() getStdin/out/err()
        Hooks to allow text I/O to special graphics devices, e.g. the
        status line.
    flush()
        Flush graphics.  May print or write a file for hardcopy devices.
    clearReturnData()
        Empty out return data buffer.
    gcur()
        Activate interactive graphics and return key pressed, position, etc.
    redrawOriginal()
        Redraw graphics without any annotations, overlays, etc.
    undoN()
        Allows annotations etc. to be removed.

Classes that implement a kernel provide methods named gki_* and control_*
which are called by the translate and control methods using dispatch
tables (functionTable and controlFunctionTable).  The complete lists
of methods are in opcode2name and control2name.  Python introspection
is used to determine which methods are implemented; it is OK for
unused methods to be omitted.

GkiProxy is a GkiKernel proxy class that implements the GkiKernel
interface and allows switching between GkiKernel objects (effectively
allowing the kernel type to change.)

GkiController is a GkiProxy that allows switching between different
graphics kernels as directed by commands embedded in the metacode stream.

"""


import numpy
import sys
import re
from stsci.tools.irafglobals import IrafError
from . import wutil
from . import graphcap
from . import irafgwcs
from . import fontdata
from .textattrib import (CHARPATH_RIGHT, JUSTIFIED_NORMAL, FONT_ROMAN,
                        FQUALITY_NORMAL)
from . import iraf

nIrafColors = 16

BOI = -1  # beginning of instruction sentinel
NOP = 0  # no op value
GKI_MAX = 32767
GKI_MAX_FLOAT = float(GKI_MAX)
NDC_MAX = GKI_MAX_FLOAT / (GKI_MAX_FLOAT + 1)
GKI_MAX_OP_CODE = 27
GKI_FLOAT_FACTOR = 100.
MAX_ERROR_COUNT = 7

# gki opcode constants

GKI_EOF = 0
GKI_OPENWS = 1
GKI_CLOSEWS = 2
GKI_REACTIVATEWS = 3
GKI_DEACTIVATEWS = 4
GKI_MFTITLE = 5
GKI_CLEARWS = 6
GKI_CANCEL = 7
GKI_FLUSH = 8
GKI_POLYLINE = 9
GKI_POLYMARKER = 10
GKI_TEXT = 11
GKI_FILLAREA = 12
GKI_PUTCELLARRAY = 13
GKI_SETCURSOR = 14
GKI_PLSET = 15
GKI_PMSET = 16
GKI_TXSET = 17
GKI_FASET = 18
GKI_GETCURSOR = 19
GKI_GETCELLARRAY = 20
GKI_ESCAPE = 25
GKI_SETWCS = 26
GKI_GETWCS = 27

GKI_ILLEGAL_LIST = (21, 22, 23, 24)

CONTROL_OPENWS = 1
CONTROL_CLOSEWS = 2
CONTROL_REACTIVATEWS = 3
CONTROL_DEACTIVATEWS = 4
CONTROL_CLEARWS = 6
CONTROL_SETWCS = 26
CONTROL_GETWCS = 27

# Names of methods in GkiKernel that handle the various opcodes
# This also can be useful for debug prints of opcode values.

# Initial dictionaries with all opcodes unknown

opcode2name = {}
control2name = {}
for i in range(GKI_MAX_OP_CODE + 1):
    opcode2name[i] = 'gki_unknown'
    control2name[i] = 'control_unknown'

opcode2name.update({
    GKI_EOF: 'gki_eof',
    GKI_OPENWS: 'gki_openws',
    GKI_CLOSEWS: 'gki_closews',
    GKI_REACTIVATEWS: 'gki_reactivatews',
    GKI_DEACTIVATEWS: 'gki_deactivatews',
    GKI_MFTITLE: 'gki_mftitle',
    GKI_CLEARWS: 'gki_clearws',
    GKI_CANCEL: 'gki_cancel',
    GKI_FLUSH: 'gki_flush',
    GKI_POLYLINE: 'gki_polyline',
    GKI_POLYMARKER: 'gki_polymarker',
    GKI_TEXT: 'gki_text',
    GKI_FILLAREA: 'gki_fillarea',
    GKI_PUTCELLARRAY: 'gki_putcellarray',
    GKI_SETCURSOR: 'gki_setcursor',
    GKI_PLSET: 'gki_plset',
    GKI_PMSET: 'gki_pmset',
    GKI_TXSET: 'gki_txset',
    GKI_FASET: 'gki_faset',
    GKI_GETCURSOR: 'gki_getcursor',
    GKI_GETCELLARRAY: 'gki_getcellarray',
    GKI_ESCAPE: 'gki_escape',
    GKI_SETWCS: 'gki_setwcs',
    GKI_GETWCS: 'gki_getwcs',
})

# control channel opcodes

control2name.update({
    CONTROL_OPENWS: 'control_openws',
    CONTROL_CLOSEWS: 'control_closews',
    CONTROL_REACTIVATEWS: 'control_reactivatews',
    CONTROL_DEACTIVATEWS: 'control_deactivatews',
    CONTROL_CLEARWS: 'control_clearws',
    CONTROL_SETWCS: 'control_setwcs',
    CONTROL_GETWCS: 'control_getwcs',
})

standardWarning = """
The graphics kernel for IRAF tasks has just received a metacode
instruction (%s) it never expected to see.  Please inform the
STSDAS group of this occurrence."""

standardNotImplemented = \
    """This IRAF task requires a graphics kernel facility not implemented
in the Pyraf graphics kernel (%s)."""


class EditHistory:
    """Keeps track of where undoable appends are made so they can be
    removed from the buffer on request. All it needs to know is
    how much as been added to the metacode stream for each edit.
    Since the process may add more gki, we distinguish specific edits
    with a marker, and those are used when undoing."""

    def __init__(self):
        self.editinfo = []

    def add(self, size, undomarker=0):
        self.editinfo.append((undomarker, size))

    def NEdits(self):
        count = 0
        for undomarker, size in self.editinfo:
            if undomarker:
                count = count + 1
        return count

    def popLastSize(self):
        tsize = 0
        while len(self.editinfo) > 0:
            marker, size = self.editinfo.pop()
            tsize = tsize + size
            if marker:
                break
        return tsize

    def split(self, n):
        """Split edit buffer at metacode length n.  Modifies this buffer
        to stop at n and returns a new EditHistory object with any
        edits beyond n."""
        newEditHistory = EditHistory()
        tsize = 0
        for i in range(len(self.editinfo)):
            marker, size = self.editinfo[i]
            tsize = tsize + size
            if tsize >= n:
                break
        else:
            # looks like all edits stay here
            return newEditHistory
        newEditHistory.editinfo = self.editinfo[i + 1:]
        self.editinfo = self.editinfo[:i + 1]
        if tsize != n:
            # split last edit
            newEditHistory.editinfo.insert(0, (marker, tsize - n))
            self.editinfo[i] = (marker, n - (tsize - size))
        return newEditHistory


def acopy(a):
    """Return copy of numpy array a"""
    return numpy.array(a, copy=1)


# GKI opcodes that clear the buffer
_clearCodes = [
    GKI_EOF,
    GKI_OPENWS,
    GKI_REACTIVATEWS,
    GKI_CLEARWS,
    GKI_CANCEL,
]

# **********************************************************************


class GkiBuffer:
    """A buffer for gki which allocates memory in blocks so that
    a new memory allocation is not needed everytime metacode is appended.
    Internally, buffer is numpy array: (numpy.zeros(N, numpy.int16)."""

    INCREMENT = 50000

    def __init__(self, metacode=None):

        self.init(metacode)
        self.redoBuffer = []

    def init(self, metacode=None):
        """Initialize to empty buffer or to metacode"""

        if metacode is not None:
            self.buffer = metacode
            self.bufferSize = len(metacode)
            self.bufferEnd = len(metacode)
        else:
            self.buffer = numpy.zeros(0, numpy.int16)
            self.bufferSize = 0
            self.bufferEnd = 0
        self.editHistory = EditHistory()
        self.prepareToRedraw()

    def prepareToRedraw(self):
        """Reset pointers in preparation for redraw"""

        # nextTranslate is pointer to next element in buffer to be
        # translated.  It is needed because we may get truncated
        # messages, leaving some metacode to be prepended to next
        # message.
        self.nextTranslate = 0
        # lastTranslate points to beginning of last metacode translated,
        # which may need to be removed if buffer is split
        self.lastTranslate = 0
        self.lastOpcode = None

    def reset(self, last=0):
        """Discard everything up to end pointer

        End is lastTranslate if last is true, else nextTranslate
        """

        if last:
            end = self.lastTranslate
        else:
            end = self.nextTranslate
        newEnd = self.bufferEnd - end
        if newEnd > 0:
            self.buffer[0:newEnd] = self.buffer[end:self.bufferEnd]
            self.bufferEnd = newEnd
            self.nextTranslate = self.nextTranslate - end
            self.lastTranslate = 0
            if not last:
                self.lastOpcode = None
        else:
            # complete reset so buffer can shrink sometimes
            self.init()

    def split(self):
        """Split this buffer at nextTranslate and return a new buffer
        object with the rest of the metacode.  lastOpcode may be
        removed if it triggered the buffer split (so we can append
        more metacode later if desired.)
        """

        tail = acopy(self.buffer[self.nextTranslate:self.bufferEnd])
        if self.lastTranslate < self.nextTranslate and \
           self.lastOpcode in _clearCodes:
            # discard last opcode, it cleared the page
            self.bufferEnd = self.lastTranslate
            self.nextTranslate = self.lastTranslate
        else:
            # retain last opcode
            self.bufferEnd = self.nextTranslate
        # return object of same class as this
        newbuffer = self.__class__(tail)
        newbuffer.editHistory = self.editHistory.split(self.bufferEnd)
        return newbuffer

    def append(self, metacode, isUndoable=0):
        """Append metacode to buffer"""

        if self.bufferSize < (self.bufferEnd + len(metacode)):
            # increment buffer size and copy into new array
            diff = self.bufferEnd + len(metacode) - self.bufferSize
            nblocks = diff // self.INCREMENT + 1
            self.bufferSize = self.bufferSize + nblocks * self.INCREMENT
            newbuffer = numpy.zeros(self.bufferSize, numpy.int16)
            if self.bufferEnd > 0:
                newbuffer[0:self.bufferEnd] = self.buffer[0:self.bufferEnd]
            self.buffer = newbuffer
        self.buffer[self.bufferEnd:self.bufferEnd + len(metacode)] = metacode
        self.bufferEnd = self.bufferEnd + len(metacode)
        self.editHistory.add(len(metacode), isUndoable)

    def isUndoable(self):
        """Returns true if there is anything to undo on this plot"""

        return (self.editHistory.NEdits() > 0)

    def undoN(self, nUndo=1):
        """Undo last nUndo edits and replot.  Returns true if plot changed."""

        changed = 0
        while nUndo > 0:
            size = self.editHistory.popLastSize()
            if size == 0:
                break
            self.bufferEnd = self.bufferEnd - size
            # add this chunk to end of buffer (use copy, not view)
            self.redoBuffer.append(
                acopy(self.buffer[self.bufferEnd:self.bufferEnd + size]))
            nUndo = nUndo - 1
            changed = 1
        if changed:
            if self.bufferEnd <= 0:
                self.init()
            # reset translation pointer to beginning so plot gets redone
            # entirely
            self.nextTranslate = 0
            self.lastTranslate = 0
        return changed

    def isRedoable(self):
        """Returns true if there is anything to redo on this plot"""

        return len(self.redoBuffer) > 0

    def redoN(self, nRedo=1):
        """Redo last nRedo edits and replot.  Returns true if plot changed."""

        changed = 0
        while self.redoBuffer and nRedo > 0:
            code = self.redoBuffer.pop()
            self.append(code, isUndoable=1)
            nRedo = nRedo - 1
            changed = 1
        return changed

    def get(self):
        """Return buffer contents (as numpy array, even if empty)"""

        return self.buffer[0:self.bufferEnd]

    def delget(self, last=0):
        """Return buffer up to end pointer, deleting those elements

        End is lastTranslate if last is true, else nextTranslate
        """

        if last:
            end = self.lastTranslate
        else:
            end = self.nextTranslate
        b = acopy(self.buffer[:end])
        self.reset(last)
        return b

    def getNextCode(self):
        """Read next opcode and argument from buffer, returning a tuple
        with (opcode, arg).  Skips no-op codes and illegal codes.
        Returns (None,None) on end of buffer or when opcode is truncated."""

        ip = self.nextTranslate
        lenMC = self.bufferEnd
        buffer = self.buffer
        while ip < lenMC:
            if buffer[ip] == NOP:
                ip = ip + 1
            elif buffer[ip] != BOI:
                print("WARNING: missynched graphics data stream")
                # find next possible beginning of instruction
                ip = ip + 1
                while ip < lenMC:
                    if buffer[ip] == BOI:
                        break
                    ip = ip + 1
                else:
                    # Unable to resync
                    print(
                        "WARNING: unable to resynchronize in graphics data stream"
                    )
                    break
            else:
                if ip + 2 >= lenMC:
                    break
                opcode = int(buffer[ip + 1])
                arglen = buffer[ip + 2]
                if (ip + arglen) > lenMC:
                    break
                self.lastTranslate = ip
                self.lastOpcode = opcode
                arg = buffer[ip + 3:ip + arglen].astype(int)
                ip = ip + arglen
                if ((opcode < 0) or (opcode > GKI_MAX_OP_CODE) or
                    (opcode in GKI_ILLEGAL_LIST)):
                    print("WARNING: Illegal graphics opcode = ", opcode)
                else:
                    # normal return
                    self.nextTranslate = ip
                    return (opcode, arg)
        # end-of-buffer return
        self.nextTranslate = ip
        return (None, None)

    def __len__(self):
        return self.bufferEnd

    def __getitem__(self, i):
        if i >= self.bufferEnd:
            raise IndexError("buffer index out of range")
        return self.buffer[i]

    def __getslice__(self, i, j):
        if j > self.bufferEnd:
            j = self.bufferEnd
        return self.buffer[i:j]


# **********************************************************************


class GkiReturnBuffer:
    """A fifo buffer used to queue up metacode to be returned to
    the IRAF subprocess"""

    # Only needed for getcursor and getcellarray, neither of which are
    # currently implemented.
    def __init__(self):

        self.fifo = []

    def reset(self):

        self.fifo = []

    def put(self, metacode):

        self.fifo[:0] = metacode

    def get(self):

        if len(self.fifo):
            return self.fifo.pop()
        else:
            raise Exception("Attempted read on empty gki input buffer")


# stack of active IRAF tasks, used to identify source of plot
tasknameStack = []

# **********************************************************************


class GkiKernel:
    """Abstract class intended to be subclassed by implementations of GKI
    kernels. This is to provide a standard interface to irafexecute"""

    def __init__(self):

        # Basics needed for all instances
        self.createFunctionTables()
        self.returnData = None
        self.errorMessageCount = 0
        self.stdin = None
        self.stdout = None
        self.stderr = None
        self._stdioStack = []
        self.gkiPreferTtyIpc = None  # see notes in the getter
        # no harm in allocating gkibuffer, doesn't actually allocate
        # space unless appended to.
        self.gkibuffer = GkiBuffer()

    def preferTtyIpc(self):
        """Getter. Return the attribute, set 1st if need be (lazy init)."""
        # Allow users to set the behavior of redirection choices
        # for special uses of PyRAF (e.g. embedded in other GUI's).  Do not
        # set this without knowing what you are doing - it breaks some commonly
        # used command-line redirection within PyRAF. (thus default = False)
        if self.gkiPreferTtyIpc is None:
            self.gkiPreferTtyIpc = iraf.envget('gkiprefertty','') == 'yes'
        return self.gkiPreferTtyIpc

    def createFunctionTables(self):
        """Use Python introspection to create function tables"""

        self.functionTable = [None] * (GKI_MAX_OP_CODE + 1)
        self.controlFunctionTable = [None] * (GKI_MAX_OP_CODE + 1)

        # to protect against typos, make list of all gki_ & control_ methods
        gkidict, classlist = {}, [self.__class__]
        for c in classlist:
            for b in c.__bases__:
                classlist.append(b)
            for name in c.__dict__.keys():
                if name[:4] == "gki_" or name[:8] == "control_":
                    gkidict[name] = 0
        # now loop over all methods that might be present
        for opcode, name in opcode2name.items():
            if name in gkidict:
                self.functionTable[opcode] = getattr(self, name)
                gkidict[name] = 1
        # do same for control methods
        for opcode, name in control2name.items():
            if name in gkidict:
                self.controlFunctionTable[opcode] = getattr(self, name)
                gkidict[name] = 1
        # did we use all the gkidict methods?
        badlist = []
        for name, value in gkidict.items():
            if not value:
                badlist.append(name)
        if badlist:
            raise SyntaxError("Bug: error in definition of class "
                              f"{self.__class__.__name__}\n"
                              "Special method name is incorrect: "
                              + " ".join(badlist))

    def control(self, gkiMetacode):
        gkiTranslate(gkiMetacode, self.controlFunctionTable)
        return self.returnData

    def append(self, gkiMetacode, isUndoable=0):

        # append metacode to the buffer
        buffer = self.getBuffer()
        buffer.append(gkiMetacode, isUndoable)
        # translate and display the metacode
        self.translate(buffer, 0)

    def translate(self, gkiMetacode, redraw=0):
        # Note, during the perf. testing of #122 it was noticed that this
        # doesn't seem to get called; should be by self.append/undoN/redoN
        # (looks to be hidden in subclasses, by GkiInteractiveTkBase.translate)
        gkiTranslate(gkiMetacode, self.functionTable)

    def errorMessage(self, text):

        if self.errorMessageCount < MAX_ERROR_COUNT:
            print(text)
            self.errorMessageCount = self.errorMessageCount + 1

    def getBuffer(self):

        # Normally, the buffer will be an attribute of the kernel, but
        # in some cases some kernels need more than one instance (interactive
        # graphics for example). In those cases, this method may be
        # overridden and the buffer will actually reside elsewhere

        return self.gkibuffer

    def flush(self):
        pass

    def clear(self):
        self.gkibuffer.reset()

    def taskStart(self, name):
        """Hook for stuff that needs to be done at start of task"""
        pass

    def taskDone(self, name):
        """Hook for stuff that needs to be done at completion of task"""
        pass

    def pre_imcur(self):
        """Hook for stuff that needs to be done right before imcur() call"""
        pass

    def undoN(self, nUndo=1):

        # Remove the last nUndo interactive appends to the metacode buffer
        buffer = self.getBuffer()
        if buffer.undoN(nUndo):
            self.prepareToRedraw()
            self.translate(buffer, 1)

    def redoN(self, nRedo=1):

        # Redo the last nRedo edits to the metacode buffer
        buffer = self.getBuffer()
        if buffer.redoN(nRedo):
            self.translate(buffer, 1)

    def prepareToRedraw(self):
        """Hook for things that need to be done before redraw from metacode"""
        pass

    def redrawOriginal(self):

        buffer = self.getBuffer()
        nUndo = buffer.editHistory.NEdits()
        if nUndo:
            self.undoN(nUndo)
        else:
            # just redraw it
            buffer.prepareToRedraw()
            self.prepareToRedraw()
            self.translate(buffer, 1)

    def clearReturnData(self):

        # intended to be called after return data is used by the client
        self.returnData = None

    def gcur(self):
        # a default gcur routine to handle all the kernels that aren't
        # interactive
        raise EOFError("The specified graphics device is not interactive")

    # some special routines for getting and setting stdin/out/err attributes

    def pushStdio(self, stdin=None, stdout=None, stderr=None):
        """Push current stdio settings onto stack at set new values"""
        self._stdioStack.append((self.stdin, self.stdout, self.stderr))
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

    def popStdio(self):
        """Restore stdio settings from stack"""
        if self._stdioStack:
            self.stdin, self.stdout, self.stderr = self._stdioStack.pop()
        else:
            self.stdin, self.stdout, self.stderr = None, None, None

    def getStdin(self, default=None):
        # return our own or the default, depending on what is defined
        # and what is a tty
        try:
            if self.preferTtyIpc() and self.stdin and self.stdin.isatty():
                return self.stdin
            elif (not self.stdin) or \
                    (default and not default.isatty()):
                return default
        except AttributeError:
            pass  # OK if isatty is missing
        return self.stdin

    def getStdout(self, default=None):
        # return our own or the default, depending on what is defined
        # and what is a tty
        try:
            if self.preferTtyIpc() and self.stdout and self.stdout.isatty():
                return self.stdout
            elif (not self.stdout) or \
                    (default and not default.isatty()):
                return default
        except AttributeError:
            pass  # OK if isatty is missing
        return self.stdout

    def getStderr(self, default=None):
        # return our own or the default, depending on what is defined
        # and what is a tty
        try:
            if self.preferTtyIpc() and self.stderr and self.stderr.isatty():
                return self.stderr
            elif (not self.stderr) or \
                    (default and not default.isatty()):
                return default
        except AttributeError:
            pass  # OK if isatty is missing
        return self.stderr


# **********************************************************************
def gkiTranslate(metacode, functionTable):
    """General Function that can be used for decoding and interpreting
    the GKI metacode stream. FunctionTable is a 28 element list containing
    the functions to invoke for each opcode encountered. This table should
    be different for each kernel that uses this function and the control
    method.
    This may be called with either a gkiBuffer or a simple numerical
    array.  If a gkiBuffer, it translates only the previously untranslated
    part of the gkiBuffer and updates the nextTranslate pointer."""

    if isinstance(metacode, GkiBuffer):
        gkiBuffer = metacode
    else:
        gkiBuffer = GkiBuffer(metacode)

    opcode, arg = gkiBuffer.getNextCode()
    while opcode is not None:
        f = functionTable[opcode]
        if f is not None:
            f(arg)
# ! DEBUG ! timer("in gkiTranslate, for: "+opcode2name[opcode]) # good dbg spot
        opcode, arg = gkiBuffer.getNextCode()


# **********************************************************************


class DrawBuffer:
    """implement a buffer for draw commands which allocates memory in blocks
    so that a new memory allocation is not needed everytime functions are
    appended"""

    INCREMENT = 500

    def __init__(self):

        self.buffer = None
        self.bufferSize = 0
        self.bufferEnd = 0
        self.nextTranslate = 0

    def __len__(self):

        return self.bufferEnd

    def reset(self):
        """Discard everything up to nextTranslate pointer"""

        newEnd = self.bufferEnd - self.nextTranslate
        if newEnd > 0:
            self.buffer[0:newEnd] = self.buffer[self.nextTranslate:self.
                                                bufferEnd]
            self.bufferEnd = newEnd
        else:
            self.buffer = None
            self.bufferSize = 0
            self.bufferEnd = 0
        self.nextTranslate = 0

    def append(self, funcargs):
        """Append a single (function,args) tuple to the list"""

        if self.bufferSize < self.bufferEnd + 1:
            # increment buffer size and copy into new array
            self.bufferSize = self.bufferSize + self.INCREMENT
            newbuffer = self.bufferSize * [None]
            if self.bufferEnd > 0:
                newbuffer[0:self.bufferEnd] = self.buffer[0:self.bufferEnd]
            self.buffer = newbuffer
        self.buffer[self.bufferEnd] = funcargs
        self.bufferEnd = self.bufferEnd + 1

    def get(self):
        """Get current contents of buffer

        Note that this returns a view into the numpy array,
        so if the return value is modified the buffer will change too.
        """

        if self.buffer:
            return self.buffer[0:self.bufferEnd]
        else:
            return []

    def getNewCalls(self):
        """Return tuples (function, args) with all new calls in buffer"""

        ip = self.nextTranslate
        if ip < self.bufferEnd:
            self.nextTranslate = self.bufferEnd
            return self.buffer[ip:self.bufferEnd]
        else:
            return []


# -----------------------------------------------


class GkiProxy(GkiKernel):
    """Base class for kernel proxy

    stdgraph is an instance of a GkiKernel to which calls are deferred.
    openKernel() method must be supplied to create a kernel and assign
    it to stdgraph.
    """

    def __init__(self):

        GkiKernel.__init__(self)
        self.stdgraph = None

    def __del__(self):
        self.flush()

    def openKernel(self):
        raise Exception("bug: do not use GkiProxy class directly")

    # methods simply defer to stdgraph
    # some create kernel and some simply return if no kernel is defined

    def errorMessage(self, text):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.errorMessage(text)

    def getBuffer(self):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.getBuffer()

    def undoN(self, nUndo=1):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.undoN(nUndo)

    def prepareToRedraw(self):
        if self.stdgraph:
            return self.stdgraph.prepareToRedraw()

    def redrawOriginal(self):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.redrawOriginal()

    def translate(self, gkiMetacode, redraw=0):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.translate(gkiMetacode, redraw)

    def clearReturnData(self):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.clearReturnData()

    def gcur(self):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.gcur()

    # keep both local and stdgraph stdin/out/err up-to-date

    def pushStdio(self, stdin=None, stdout=None, stderr=None):
        """Push current stdio settings onto stack at set new values"""
        if self.stdgraph:
            self.stdgraph.pushStdio(stdin, stdout, stderr)
        # XXX still need some work here?
        self._stdioStack.append((self.stdin, self.stdout, self.stderr))
        self.stdin = stdin
        self.stdout = stdout
        self.stderr = stderr

    def popStdio(self):
        """Restore stdio settings from stack"""
        # XXX still need some work here?
        if self.stdgraph:
            self.stdgraph.popStdio()
        if self._stdioStack:
            self.stdin, self.stdout, self.stderr = self._stdioStack.pop()
        else:
            self.stdin, self.stdout, self.stderr = None, None, None

    def getStdin(self, default=None):
        if self.stdgraph:
            return self.stdgraph.getStdin(default)
        else:
            return GkiKernel.getStdin(self, default)

    def getStdout(self, default=None):
        if self.stdgraph:
            return self.stdgraph.getStdout(default)
        else:
            return GkiKernel.getStdout(self, default)

    def getStderr(self, default=None):
        if self.stdgraph:
            return self.stdgraph.getStderr(default)
        else:
            return GkiKernel.getStderr(self, default)

    def append(self, arg, isUndoable=0):
        if self.stdgraph:
            self.stdgraph.append(arg, isUndoable)

    def control(self, gkiMetacode):
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.control(gkiMetacode)

    def flush(self):
        if self.stdgraph:
            self.stdgraph.flush()

    def clear(self):
        if self.stdgraph:
            self.stdgraph.clear()

    def taskStart(self, name):
        if self.stdgraph:
            self.stdgraph.taskStart(name)

    def taskDone(self, name):
        if self.stdgraph:
            self.stdgraph.taskDone(name)


# **********************************************************************


class GkiController(GkiProxy):
    """Proxy that switches between interactive and other kernels

    This can gracefully handle changes in kernels which can appear
    in any open workstation instruction.  It also uses lazy
    instantiation of the real kernel (which can be expensive).  In
    one sense it is a factory class that will instantiate the
    necessary kernels as they are requested.

    Most external modules should access the gki functions through
    an instance of this class, gki.kernel.
    """

    def __init__(self):

        GkiProxy.__init__(self)
        self.interactiveKernel = None
        self.lastDevice = None
        self.wcs = None

    def taskStart(self, name):

        # GkiController manages the tasknameStack
        tasknameStack.append(name)
        if self.stdgraph:
            self.stdgraph.taskStart(name)

    def taskDone(self, name):

        # delete name from stack; pop until we find it if necessary
        while tasknameStack:
            lastname = tasknameStack.pop()
            if lastname == name:
                break
        if self.stdgraph:
            self.stdgraph.taskDone(name)

    def control(self, gkiMetacode):

        # some control functions get executed here because they can
        # change the kernel
        gkiTranslate(gkiMetacode, self.controlFunctionTable)
        # rest of control is handled by the kernel
        if not self.stdgraph:
            self.openKernel()
        return self.stdgraph.control(gkiMetacode)

    def control_openws(self, arg):
        device = arg[2:].astype(numpy.int8).tobytes().decode().strip()
        self.openKernel(device)

    def openKernel(self, device=None):
        """Open kernel specified by device or by current value of stdgraph"""
        device = self.getDevice(device)
        graphcap = getGraphcap()

        # In either of these 3 cases we want to create a new kernel.  The last
        # is the most complex, and it needs to be revisited (when the Device
        # class is refactored) but suffice it to say we only want to compare
        # the dict for the device, not the "master dict".
        if self.lastDevice is None or \
           device != self.lastDevice or \
           graphcap[device].dict[device] != graphcap.get(self.lastDevice)[self.lastDevice]:
            self.flush()
            executable = graphcap[device]['kf']
            if executable == 'cl':
                # open (persistent) interactive kernel
                if not self.interactiveKernel:
                    if wutil.hasGraphics:
                        from . import gwm
                        self.interactiveKernel = gwm.getGraphicsWindowManager()
                    else:
                        self.interactiveKernel = GkiNull()
                self.stdgraph = self.interactiveKernel
            else:
                from . import gkiiraf
                self.stdgraph = gkiiraf.GkiIrafKernel(device)
            self.stdin = self.stdgraph.stdin
            self.stdout = self.stdgraph.stdout
            self.stderr = self.stdgraph.stderr
            self.lastDevice = device

    def getDevice(self, device=None):
        """Starting with stdgraph, drill until a device is found in
        the graphcap or isn't"""
        if not device:
            device = iraf.envget("stdgraph", "")
        graphcap = getGraphcap()
        # protect against circular definitions
        devstr = device
        tried = {devstr: None}
        while devstr not in graphcap:
            pdevstr = devstr
            devstr = iraf.envget(pdevstr, "")
            if not devstr:
                raise IrafError("No entry found "
                                f"for specified stdgraph device `{device}'")
            elif devstr in tried:
                # track back through circular definition
                s = [devstr]
                next = pdevstr
                while next and (next != devstr):
                    s.append(next)
                    next = tried[next]
                if next:
                    s.append(next)
                s.reverse()
                raise IrafError("Circular definition in graphcap for device\n"
                                +' -> '.join(s))
            else:
                tried[devstr] = pdevstr
        return devstr


# **********************************************************************


class GkiNull(GkiKernel):
    """A version of the graphics kernel that does nothing except warn the
    user that it does nothing. Used when graphics display isn't possible"""

    def __init__(self):

        print("No graphics display available for this session.")
        print("Graphics tasks that attempt to plot to an interactive "
              "screen will fail.")
        GkiKernel.__init__(self)
        self.name = 'Null'

    def control_openws(self, arg):
        raise IrafError("Unable to plot graphics to screen")

    def control_reactivatews(self, arg):
        raise IrafError("Attempt to access graphics when "
                        "it isn't available")

    def control_getwcs(self, arg):
        raise IrafError("Attempt to access graphics when "
                        "it isn't available")

    def translate(self, gkiMetacode, redraw=0):
        pass


# **********************************************************************


class GkiRedirection(GkiKernel):
    """A graphics kernel whose only responsibility is to redirect
    metacode to a file-like object. Currently doesn't handle WCS
    get or set commands.

    (This is needed for situations when you append to a graphics
    file - RIJ)"""

    def __init__(self, filehandle):
        # Differs from all other constructors in that it takes a
        # file-like object as an argument.
        GkiKernel.__init__(self)
        self.filehandle = filehandle
        self.wcs = None

    def append(self, metacode):
        # Overloads the baseclass implementation.
        # metacode is array of 16-bit ints
        self.filehandle.write(metacode.tobytes())

    # control needs to get and set WCS data
    def control_setwcs(self, arg):
        self.wcs = irafgwcs.IrafGWcs(arg)
        # Need to store this in the (persistent) kernel
        kernel.wcs = self.wcs

    def control_getwcs(self, arg):
        if not self.wcs:
            self.wcs = irafgwcs.IrafGWcs()
        if self.returnData:
            self.returnData = self.returnData + self.wcs.pack()
        else:
            self.returnData = self.wcs.pack()

    def getStdin(self, default=None):
        return default

    def getStdout(self, default=None):
        return default

    def getStderr(self, default=None):
        return default


# **********************************************************************


class GkiNoisy(GkiKernel):
    """Print metacode stream information"""

    def __init__(self):

        GkiKernel.__init__(self)
        self.name = 'Noisy'

    def control_openws(self, arg):
        print('control_openws')

    def control_closews(self, arg):
        print('control_closews')

    def control_reactivatews(self, arg):
        print('control_reactivatews')

    def control_deactivatews(self, arg):
        print('control_deactivatews')

    def control_clearws(self, arg):
        print('control_clearws')

    def control_setwcs(self, arg):
        print('control_setwcs')

    def control_getwcs(self, arg):
        print('control_getwcs')

    def gki_eof(self, arg):
        print('gki_eof')

    def gki_openws(self, arg):
        print('gki_openws')

    def gki_closews(self, arg):
        print('gki_closews')

    def gki_reactivatews(self, arg):
        print('gki_reactivatews')

    def gki_deactivatews(self, arg):
        print('gki_deactivatews')

    def gki_mftitle(self, arg):
        print('gki_mftitle')

    def gki_clearws(self, arg):
        print('gki_clearws')

    def gki_cancel(self, arg):
        print('gki_cancel')

    def gki_flush(self, arg):
        print('gki_flush')

    def gki_polyline(self, arg):
        print('gki_polyline')

    def gki_polymarker(self, arg):
        print('gki_polymarker')

    def gki_text(self, arg):
        print('gki_text')

    def gki_fillarea(self, arg):
        print('gki_fillarea')

    def gki_putcellarray(self, arg):
        print('gki_putcellarray')

    def gki_setcursor(self, arg):
        print('gki_setcursor')

    def gki_plset(self, arg):
        print('gki_plset')

    def gki_pmset(self, arg):
        print('gki_pmset')

    def gki_txset(self, arg):
        print('gki_txset')

    def gki_faset(self, arg):
        print('gki_faset')

    def gki_getcursor(self, arg):
        print('gki_getcursor')

    def gki_getcellarray(self, arg):
        print('gki_getcellarray')

    def gki_unknown(self, arg):
        print('gki_unknown')

    def gki_escape(self, arg):
        print('gki_escape')

    def gki_setwcs(self, arg):
        print('gki_setwcs')

    def gki_getwcs(self, arg):
        print('gki_getwcs')


# Dictionary of all graphcap files known so far

graphcapDict = {}


def getGraphcap(filename=None):
    """Get graphcap file from filename (or cached version if possible)"""
    if filename is None:
        filename = iraf.osfn(iraf.envget('graphcap', 'dev$graphcap'))
    if filename not in graphcapDict:
        graphcapDict[filename] = graphcap.GraphCap(filename)
    return graphcapDict[filename]


# XXX printPlot belongs in gwm, not gki?
# XXX or maybe should be a method of gwm window manager


def printPlot(window=None):
    """Print contents of window (default active window) to stdplot
    window must be a GkiKernel object (with a gkibuffer attribute.)
    """
    from . import gwm
    from . import gkiiraf
    if window is None:
        window = gwm.getActiveGraphicsWindow()
        if window is None:
            return
    gkibuff = window.gkibuffer.get()
    if len(gkibuff):
        graphcap = getGraphcap()
        stdplot = iraf.envget('stdplot', '')
        if not stdplot:
            msg = "No hardcopy device defined in stdplot"
        elif stdplot not in graphcap:
            msg = f"Unknown hardcopy device stdplot=`{stdplot}'"
        else:
            printer = gkiiraf.GkiIrafKernel(stdplot)
            printer.append(gkibuff)
            printer.flush()
            msg = "snap completed"
    stdout = kernel.getStdout(default=sys.stdout)
    stdout.write(f"{msg}\n")


# **********************************************************************


class IrafGkiConfig:
    """Holds configurable aspects of IRAF plotting behavior

    This gets instantiated as a singleton instance so all windows
    can share the same configuration.
    """

    def __init__(self):

        # All set to constants for now, eventually allow setting other
        # values

        # h = horizontal font dimension, v = vertical font dimension

        # ratio of font height to width
        self.fontAspect = 42. / 27.
        self.fontMax2MinSizeRatio = 4.

        # Empirical constants for font sizes
        self.UnitFontHWindowFraction = 1. / 80
        self.UnitFontVWindowFraction = 1. / 45

        # minimum unit font size in pixels (set to None if not relevant)
        self.minUnitHFontSize = 5.
        self.minUnitVFontSize = self.minUnitHFontSize * self.fontAspect

        # maximum unit font size in pixels (set to None if not relevant)
        self.maxUnitHFontSize = \
            self.minUnitHFontSize * self.fontMax2MinSizeRatio
        self.maxUnitVFontSize = self.maxUnitHFontSize * self.fontAspect

        # offset constants to match iraf's notion of where 0,0 is relative
        # to the coordinates of a character
        self.vFontOffset = 0.0
        self.hFontOffset = 0.0

        # font sizing switch
        self.isFixedAspectFont = 1

        # List of rgb tuples (0.0-1.0 range) for the default IRAF set of colors
        self.defaultColors = [
            (0., 0., 0.),  # black
            (1., 1., 1.),  # white
            (1., 0., 0.),  # red
            (0., 1., 0.),  # green
            (0., 0., 1.),  # blue
            (0., 1., 1.),  # cyan
            (1., 1., 0.),  # yellow
            (1., 0., 1.),  # magenta
            (1., 1., 1.),  # white
            # (0.32,0.32,0.32),  # gray32
            (0.18, 0.31, 0.31),  # IRAF blue-green
            (1., 1., 1.),  # white
            (1., 1., 1.),  # white
            (1., 1., 1.),  # white
            (1., 1., 1.),  # white
            (1., 1., 1.),  # white
            (1., 1., 1.),  # white
        ]
        self.cursorColor = 2  # red
        if len(self.defaultColors) != nIrafColors:
            raise ValueError(f"defaultColors should have {nIrafColors:d} "
                             f"elements (has {len(self.defaultColors):d})")

        # old colors
        #       (1.,0.5,0.),      # coral
        #       (0.7,0.19,0.38),  # maroon
        #       (1.,0.65,0.),     # orange
        #       (0.94,0.9,0.55),  # khaki
        #       (0.85,0.45,0.83), # orchid
        #       (0.25,0.88,0.82), # turquoise
        #       (0.91,0.53,0.92), # violet
        #       (0.96,0.87,0.72)  # wheat

    def setCursorColor(self, color):
        if not 0 <= color < len(self.defaultColors):
            raise ValueError(f"Bad cursor color ({color:d}) should be >=0 "
                             f"and <{len(self.defaultColors)-1:d}")
        self.cursorColor = color

    def fontSize(self, gwidget):
        """Determine the unit font size for the given setup in pixels.
        The unit size refers to the horizonal size of fixed width characters
        (allow for proportionally sized fonts later?).

        Basically, if font aspect is not fixed, the unit font size is
        proportional to the window dimension (for v and h independently),
        with the exception that if min or max pixel sizes are enabled,
        they are 'clipped' at the specified value. If font aspect is fixed,
        then the horizontal size is the driver if the window is higher than
        wide and vertical size for the converse.
        """

        hwinsize = gwidget.winfo_width()
        vwinsize = gwidget.winfo_height()
        hsize = hwinsize * self.UnitFontHWindowFraction
        vsize = vwinsize * self.UnitFontVWindowFraction
        if self.minUnitHFontSize is not None:
            hsize = max(hsize, self.minUnitHFontSize)
        if self.minUnitVFontSize is not None:
            vsize = max(vsize, self.minUnitVFontSize)
        if self.maxUnitHFontSize is not None:
            hsize = min(hsize, self.maxUnitHFontSize)
        if self.maxUnitVFontSize is not None:
            vsize = min(vsize, self.maxUnitVFontSize)
        if not self.isFixedAspectFont:
            fontAspect = vsize / hsize
        else:
            hsize = min(hsize, vsize / self.fontAspect)
            vsize = hsize * self.fontAspect
            fontAspect = self.fontAspect
        return (hsize, fontAspect)

    def getIrafColors(self):

        return self.defaultColors


# create the singleton instance

_irafGkiConfig = IrafGkiConfig()

# -----------------------------------------------


class IrafLineStyles:

    def __init__(self):

        self.patterns = [0x0000, 0xFFFF, 0x00FF, 0x5555, 0x33FF]


class IrafHatchFills:

    def __init__(self):

        # Each fill pattern is a 32x4 ubyte array (represented as 1-d).
        # These are computed on initialization rather than using a
        # 'data' type initialization since they are such simple patterns.
        # these arrays are stored in a pattern list. Pattern entries
        # 0-2 should never be used since they are not hatch patterns.

        # so much for these, currently PyOpenGL does not support
        # glPolygonStipple()! But adding it probably is not too hard.

        self.patterns = [None] * 7
        # pattern 3, vertical stripes
        p = numpy.zeros(128, numpy.int8)
        p[0:4] = [0x92, 0x49, 0x24, 0x92]
        for i in range(31):
            p[(i + 1) * 4:(i + 2) * 4] = p[0:4]
        self.patterns[3] = p
        # pattern 4, horizontal stripes
        p = numpy.zeros(128, numpy.int8)
        p[0:4] = [0xFF, 0xFF, 0xFF, 0xFF]
        for i in range(10):
            p[(i + 1) * 12:(i + 1) * 12 + 4] = p[0:4]
        self.patterns[4] = p
        # pattern 5, close diagonal striping
        p = numpy.zeros(128, numpy.int8)
        p[0:12] = [
            0x92, 0x49, 0x24, 0x92, 0x24, 0x92, 0x49, 0x24, 0x49, 0x24, 0x92,
            0x49
        ]
        for i in range(9):
            p[(i + 1) * 12:(i + 2) * 12] = p[0:12]
        p[120:128] = p[0:8]
        self.patterns[5] = p
        # pattern 6, diagonal stripes the other way
        p = numpy.zeros(128, numpy.int8)
        p[0:12] = [
            0x92, 0x49, 0x24, 0x92, 0x49, 0x24, 0x92, 0x49, 0x24, 0x92, 0x49,
            0x24
        ]
        for i in range(9):
            p[(i + 1) * 12:(i + 2) * 12] = p[0:12]
        p[120:128] = p[0:8]
        self.patterns[6] = p


class LineAttributes:

    def __init__(self):

        self.linestyle = 1
        self.linewidth = 1.0
        self.color = 1

    def set(self, linestyle, linewidth, color):

        self.linestyle = linestyle
        self.linewidth = linewidth
        self.color = color


class FillAttributes:

    def __init__(self):

        self.fillstyle = 1
        self.color = 1

    def set(self, fillstyle, color):

        self.fillstyle = fillstyle
        self.color = color


class MarkerAttributes:

    def __init__(self):

        # the first two attributes are not currently used in IRAF, so ditch'em
        self.color = 1

    def set(self, markertype, size, color):

        self.color = color


class TextAttributes:

    # Used as a structure definition basically, perhaps it should be made
    # more sophisticated.
    def __init__(self):

        self.charUp = 90.
        self.charSize = 1.
        self.charSpace = 0.
        self.textPath = CHARPATH_RIGHT
        self.textHorizontalJust = JUSTIFIED_NORMAL
        self.textVerticalJust = JUSTIFIED_NORMAL
        self.textFont = FONT_ROMAN
        self.textQuality = FQUALITY_NORMAL
        self.textColor = 1
        self.font = fontdata.font1
        # Place to keep font size and aspect for current window dimensions
        self.hFontSize = None
        self.fontAspect = None

    def set(self,
            charUp=90.,
            charSize=1.,
            charSpace=0.,
            textPath=CHARPATH_RIGHT,
            textHorizontalJust=JUSTIFIED_NORMAL,
            textVerticalJust=JUSTIFIED_NORMAL,
            textFont=FONT_ROMAN,
            textQuality=FQUALITY_NORMAL,
            textColor=1):

        self.charUp = charUp
        self.charSize = charSize
        self.charSpace = charSpace
        self.textPath = textPath
        self.textHorizontalJust = textHorizontalJust
        self.textVerticalJust = textVerticalJust
        self.textFont = textFont
        self.textQuality = textQuality
        self.textColor = textColor
        # Place to keep font size and aspect for current window dimensions

    def setFontSize(self, win):
        """Set the unit font size for a given window using the iraf
        configuration parameters contained in an attribute class"""

        conf = win.irafGkiConfig
        self.hFontSize, self.fontAspect = conf.fontSize(win.gwidget)

    def getFontSize(self):

        return self.hFontSize, self.fontAspect


# -----------------------------------------------


class FilterStderr:
    """Filter GUI messages out of stderr during plotting"""

    pat = re.compile('\031[^\035]*\035\037')

    def __init__(self):
        self.fh = sys.stderr

    def write(self, text):
        # remove GUI junk
        edit = self.pat.sub('', text)
        if edit:
            self.fh.write(edit)

    def flush(self):
        self.fh.flush()

    def close(self):
        pass


# -----------------------------------------------


class StatusLine:

    def __init__(self, status, name):
        self.status = status
        self.windowName = name

    def readline(self):
        """Shift focus to graphics, read line from status, restore focus"""
        wutil.focusController.setFocusTo(self.windowName)
        rv = self.status.readline()
        return rv

    def read(self, n=0):
        """Return up to n bytes from status line

        Reads only a single line.  If n<=0, just returns the line.
        """
        s = self.readline()
        if n > 0:
            return s[:n]
        else:
            return s

    def write(self, text):
        self.status.updateIO(text=text.strip())

    def flush(self):
        self.status.update_idletasks()

    def close(self):
        # clear status line
        self.status.updateIO(text="")

    def isatty(self):
        return 1


# -----------------------------------------------

# ********************************


def ndc(intarr):
    return intarr / (GKI_MAX_FLOAT + 1)


def ndcpairs(intarr):
    f = ndc(intarr)
    return f[0::2], f[1::2]


# This is the proxy for the current graphics kernel

kernel = GkiController()


# Beware! This is highly experimental and was made only for a test case.
def _resetGraphicsKernel():
    global kernel
    from . import gwm
    if kernel:
        kernel.clearReturnData()
        kernel.flush()
        gwm.delete()
        kernel = None
    gwm._resetGraphicsWindowManager()
    kernel = GkiController()
