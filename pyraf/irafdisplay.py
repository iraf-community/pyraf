"""irafdisplay.py: Interact with IRAF-compatible image display

Modeled after the NOAO Client Display Library (CDL)

Public functions:

readCursor(sample=0)
        Read image cursor position

open(imtdev=None)
        Open a connection to the display server.  This is called
        automatically by readCursor if the display has not already been
        opened, so it is not generally necessary for users to call it.

        See the open doc string for info on the imtdev argument, which
        allows various forms of socket and network connections.

close()
        Close the active display server.  Called automatically on exit.

Various classes are defined for the different connections (ImageDisplay,
ImageDisplayProxy, UnixImageDisplay, InetImageDisplay, FifoImageDisplay).
They should generally be created using the _open factory function.
This could be used to maintain references to multiple display servers.

Ultimately more functionality may be added to make this a complete
replacement for CDL.
"""
import os
import numpy
import socket
import sys
import fcntl
from stsci.tools import irafutils

_default_imtdev = ("unix:/tmp/.IMT%d", "fifo:/dev/imt1i:/dev/imt1o")


def _open(imtdev=None):
    """Open connection to the image display server

    This is a factory function that returns an instance of the ImageDisplay
    class for the specified imtdev.  The default connection if no imtdev is
    specified is given in the environment variable IMTDEV (if defined) or
    is "unix:/tmp/.IMT%d".  Failing that, a connection is attempted on the
    /dev/imt1[io] named fifo pipes.

    The syntax for the imtdev argument is <domain>:<address> where <domain>
    is one of "inet" (internet tcp/ip socket), "unix" (unix domain socket)
    or "fifo" (named pipe).  The form of the address depends upon the
    domain, as illustrated in the examples below.

    inet:5137                   Server connection to port 5137 on the local
                                host.  For a client, a connection to the
                                given port on the local host.

    inet:5137:foo.bar.edu       Client connection to port 5137 on internet
                                host foo.bar.edu.  The dotted form of address
                                may also be used.

    unix:/tmp/.IMT212           Unix domain socket with the given pathname
                                IPC method, local host only.

    fifo:/dev/imt1i:/dev/imt1o  FIFO or named pipe with the given pathname.
                                IPC method, local host only.  Two pathnames
                                are required, one for input and one for
                                output, since FIFOs are not bidirectional.
                                For a client the first fifo listed will be
                                the client's input fifo; for a server the
                                first fifo will be the server's output fifo.
                                This allows the same address to be used for
                                both the client and the server, as for the
                                other domains.

    The address field may contain one or more "%d" fields.  If present, the
    user's UID will be substituted (e.g. "unix:/tmp/.IMT%d").
    """

    if not imtdev:
        # try defaults
        defaults = list(_default_imtdev)
        if 'IMTDEV' in os.environ:
            defaults.insert(0, os.environ['IMTDEV'])
        for imtdev in defaults:
            try:
                return _open(imtdev)
            except OSError:
                pass
        raise OSError("Cannot open image display")
    # substitute user id in name (multiple times) if necessary
    nd = len(imtdev.split("%d"))
    dev = imtdev % ((os.getuid(),) * (nd - 1))
    fields = dev.split(":")
    domain = fields[0]
    if domain == "unix" and len(fields) == 2:
        return UnixImageDisplay(fields[1])
    elif domain == "fifo" and len(fields) == 3:
        return FifoImageDisplay(fields[1], fields[2])
    elif domain == "inet" and (2 <= len(fields) <= 3):
        try:
            port = int(fields[1])
            if len(fields) == 3:
                hostname = fields[2]
            else:
                hostname = None
            return InetImageDisplay(port, hostname)
        except ValueError:
            pass
    raise ValueError(f"Illegal image device specification `{imtdev}'")


class ImageDisplay:
    """Interface to IRAF-compatible image display"""

    # constants for cursor read
    _IIS_READ = 0o100000
    _IMC_SAMPLE = 0o040000
    _IMCURSOR = 0o20
    _SZ_IMCURVAL = 160

    def __init__(self):
        # Flag indicating that readCursor request is active.
        # This is used to handle interruption of readCursor before
        # read is complete.  Without this kluge, ^C interrupts
        # leave image display in a bad state.
        self._inCursorMode = 0

    def readCursor(self, sample=0):
        """Read image cursor value for this image display

        Return immediately if sample is true, or wait for keystroke
        if sample is false (default).  Returns a string with
        x, y, frame, and key.
        """

        if not self._inCursorMode:
            opcode = self._IIS_READ
            if sample:
                opcode |= self._IMC_SAMPLE
            self._writeHeader(opcode, self._IMCURSOR, 0, 0, 0, 0, 0)
            self._inCursorMode = 1
        s = self._read(self._SZ_IMCURVAL)
        self._inCursorMode = 0
        # only part up to newline is real data
        return s.split("\n")[0]

    def _writeHeader(self, tid, subunit, thingct, x, y, z, t):
        """Write request to image display"""

        a = numpy.array([tid, thingct, subunit, 0, x, y, z, t], numpy.int16)
        # Compute the checksum
        sum = numpy.add.reduce(a)
        sum = 0xffff - (sum & 0xffff)
        a[3] = sum
        self._write(a.tobytes())

    def close(self, os_close=os.close):
        """Close image display connection"""

        try:
            os_close(self._fdin)
        except (OSError, AttributeError):
            pass
        try:
            os_close(self._fdout)
        except (OSError, AttributeError):
            pass

    def _read(self, n):
        """Read n bytes from image display and return as string

        Raises IOError on failure.  If a tkinter widget exists, runs
        a Tk mainloop while waiting for data so that the Tk widgets
        remain responsive.
        """
        try:
            return irafutils.tkread(self._fdin, n)
        except EOFError:
            raise OSError("Error reading from image display")

    def _write(self, s):
        """Write string s to image display

        Raises IOError on failure
        """
        n = len(s)
        while n > 0:
            nwritten = os.write(self._fdout, s[-n:])
            n -= nwritten
            if nwritten <= 0:
                raise OSError("Error writing to image display")


class FifoImageDisplay(ImageDisplay):
    """FIFO version of image display"""

    def __init__(self, infile, outfile):
        ImageDisplay.__init__(self)
        self._fdin = os.open(infile, os.O_RDONLY | os.O_NDELAY)
        fcntl.fcntl(self._fdin, fcntl.F_SETFL, os.O_RDONLY)
        self._fdout = os.open(outfile, os.O_WRONLY | os.O_NDELAY)
        fcntl.fcntl(self._fdout, fcntl.F_SETFL, os.O_WRONLY)

    def __del__(self):
        self.close()


class UnixImageDisplay(ImageDisplay):
    """Unix socket version of image display"""

    def __init__(self, filename, family=None, type=socket.SOCK_STREAM):
        ImageDisplay.__init__(self)
        try:
            if family is None:  # set in func, not in decl so it works on win
                family = socket.AF_UNIX
            self._socket = socket.socket(family, type)
            self._socket.connect(filename)
            self._fdin = self._fdout = self._socket.fileno()
        except OSError:
            raise OSError("Cannot open image display")

    def close(self):
        """Close image display connection"""

        self._socket.close()


class InetImageDisplay(UnixImageDisplay):
    """INET socket version of image display"""

    def __init__(self, port, hostname=None):
        hostname = hostname or "localhost"
        UnixImageDisplay.__init__(self, (hostname, port),
                                  family=socket.AF_INET)


class ImageDisplayProxy(ImageDisplay):
    """Interface to IRAF-compatible image display

    This is a proxy to the actual display that allows retries
    on failures and can switch between display connections.
    """

    def __init__(self, imtdev=None):
        # if imtdev is specified, it becomes the default for the
        # life of this instance
        self._display = None
        self.imtdev = imtdev
        if imtdev:
            self.open()

    def open(self, imtdev=None):
        """Open image display connection, closing any active connection"""

        self.close()
        self._display = _open(imtdev or self.imtdev)

    def close(self):
        """Close active image display connection"""

        if self._display:
            self._display.close()
            self._display = None

    def readCursor(self, sample=0):
        """Read image cursor value for the active image display

        Return immediately if sample is true, or wait for keystroke
        if sample is false (default).  Returns a string with
        x, y, frame, and key.  Opens image display if necessary.
        """

        if not self._display:
            self.open()
        try:
            value = self._display.readCursor(sample)
            # Null value indicates display was probably closed
            if value:
                return value
        except OSError:
            pass
        # This error can occur if image display was closed.
        # If a new display has been started then closing and
        # reopening the connection will fix it.  If that
        # fails then give up.
        self.open()
        return self._display.readCursor(sample)


_display = ImageDisplayProxy()

# create aliases for _display methods

readCursor = _display.readCursor
open = _display.open
close = _display.close
