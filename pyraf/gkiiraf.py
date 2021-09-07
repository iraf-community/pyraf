"""
OpenGL implementation of the gki kernel class
"""


import sys
import os
from . import gki
from . import irafgwcs
from . import iraftask
from . import iraf

# kernels to flush frequently
# imdkern does not erase, so always flush it
_alwaysFlush = {"imdkern": 1}

# dictionary of IrafTask objects for known kernels
_kernelDict = {}


class GkiIrafKernel(gki.GkiKernel):
    """This is designed to route metacode to an IRAF kernel executable.
    It needs very minimal functionality. The basic function is to collect
    metacode in the buffer and ship it off on flushes and when the kernel
    is shut down."""

    def __init__(self, device):

        from . import irafecl
        module = irafecl.getTaskModule()

        gki.GkiKernel.__init__(self)
        graphcap = gki.getGraphcap()
        if device not in graphcap:
            raise iraf.IrafError(
                f"No entry found for specified stdgraph device `{device}'")
        gentry = graphcap[device]
        self.device = device
        self.executable = executable = gentry['kf']
        self.taskname = taskname = gentry['tn']
        self.wcs = None
        if taskname not in _kernelDict:
            # create special IRAF task object for this kernel
            _kernelDict[taskname] = module.IrafGKITask(taskname, executable)
        self.task = _kernelDict[taskname]

    def control_openws(self, arg):
        # control_openws precedes gki_openws, so trigger on it to
        # send everything before the open to the device
        mode = arg[0]
        if mode == 5 or self.taskname in _alwaysFlush:
            self.flush()

    def control_setwcs(self, arg):
        self.wcs = irafgwcs.IrafGWcs(arg)

    def control_getwcs(self, arg):
        if not self.wcs:
            self.wcs = irafgwcs.IrafGWcs()
        if self.returnData:
            self.returnData = self.returnData + self.wcs.pack()
        else:
            self.returnData = self.wcs.pack()

    def gki_closews(self, arg):
        # gki_closews follows control_closews, so trigger on it to
        # send everything up through the close to the device
        if self.taskname in _alwaysFlush:
            self.flush()

    def gki_flush(self, arg):
        if self.taskname in _alwaysFlush:
            self.flush()

    def flush(self):
        # grab last part of buffer and delete it
        metacode = self.gkibuffer.delget().tobytes()
        # only plot if buffer contains something
        if metacode:
            # write to a temporary file
            tmpfn = iraf.mktemp("iraf") + ".gki"
            fout = open(tmpfn, 'wb')
            fout.write(metacode)
            fout.close()
            try:
                if self.taskname == "stdgraph":
                    # this is to allow users to specify via the
                    # stdgraph device parameter the device they really
                    # want to display to
                    device = iraf.stdgraph.device
                else:
                    device = self.device

                # XXX In principle we could read from Stdin by
                # XXX wrapping the string in a StringIO buffer instead of
                # XXX writing it to a temporary file.  But that will not
                # XXX work until binary redirection is implemented in
                # XXX irafexecute
                # XXX task(Stdin=tmpfn,device=device,generic="yes")

                # Explicitly set input to sys.__stdin__ to avoid possible
                # problems with redirection. Sometimes graphics kernel tries
                # to read from stdin if it is not the default stdin.

                self.task(tmpfn,
                          device=device,
                          generic="yes",
                          Stdin=sys.__stdin__)
            finally:
                os.remove(tmpfn)
