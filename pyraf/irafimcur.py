"""irafimcur.py: image cursor interaction

Read the cursor position from stdimage image display device (DS9,
SAOIMAGE or XIMTOOL) and return a string compatible with IRAF's
imcur parameter.
"""


import sys
from stsci.tools import irafutils
from stsci.tools.irafglobals import Verbose, IrafError
from . import irafdisplay
from . import gwm
from . import iraf

# dictionary of devices to support multiple active displays
_devices = {}


def _getDevice(displayname=None):
    """Get device object for this display"""
    if displayname is None:
        displayname = iraf.envget("stdimage")
    try:
        return _devices[displayname]
    except KeyError:
        pass

    # look up display info in graphcap
    try:
        device = gwm.gki.getGraphcap()[displayname]
        dd = device['DD'].split(',')
        if len(dd) > 1 and dd[1] != '':
            imtdev = f'fifo:{dd[1]}i:{dd[1]}o'
        else:
            imtdev = None
        # multiple stdimage/graphcap entries can share the same device
        if imtdev not in _devices:
            _devices[imtdev] = irafdisplay.ImageDisplayProxy(imtdev)
        device = _devices[displayname] = _devices[imtdev]
        return device
    except (KeyError, OSError):
        pass

    # last gasp is to assume display is an imtdev string
    try:
        device = _devices[displayname] = irafdisplay.ImageDisplayProxy(
            displayname)
        return device
    except (ValueError, OSError):
        pass
    raise IrafError(f"Unable to open image display `{displayname}'\n")


def imcur(displayname=None):
    """Read image cursor and return string expected for IRAF's imcur parameter

    If key pressed is colon, also prompts for additional string input.
    Raises EOFError if ^D or ^Z is typed and IrafError on other errors.
    The optional display argument specifies the name of the display to
    use (default is the display specified in stdimage).
    """

    try:
        # give kernel a chance to do anything it needs right before imcur
        gkrnl = gwm.getActiveGraphicsWindow()
        if gkrnl:
            gkrnl.pre_imcur()
        # get device
        device = _getDevice(displayname)
        # Read cursor position at keystroke
        result = device.readCursor()
        if Verbose > 1:
            sys.__stdout__.write(f"{result}\n")
            sys.__stdout__.flush()
        if result == 'EOF':
            raise EOFError()
        x, y, wcs, key = result.split()

        if key in [r'\004', r'\032']:
            # ctrl-D and ctrl-Z are treated as EOF
            # Should ctrl-C raise a KeyboardInterrupt?
            raise EOFError()
        elif key == ':':
            sys.stdout.write(": ")
            sys.stdout.flush()
            result = result + ' ' + irafutils.tkreadline()[:-1]
        return result
    except OSError as error:
        raise IrafError(str(error))
