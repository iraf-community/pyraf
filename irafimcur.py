"""irafimcur.py: image cursor interaction

Read the cursor position from SAOIMAGE or XIMTOOL and return
a string compatible with IRAF's imcur parameter.

$Id$
"""

import sys,string
from irafglobals import Verbose, IrafError
import irafdisplay, irafutils

def imcur():

    """Read image cursor and return string expected for IRAF's imcur parameter

    If key pressed is colon, also prompts for additional string input.
    Raises EOFError if ^D or ^Z is typed and IrafError on other errors.
    """

    try:
        # Read cursor position at keystroke
        result = irafdisplay.readCursor()
        if Verbose>1:
            sys.__stdout__.write("%s\n" % (result,))
            sys.__stdout__.flush()
        if result == 'EOF':
            raise EOFError
        x, y, wcs, key = result.split()
        if key in [r'\004', r'\032']:
            # ctrl-D and ctrl-Z are treated as EOF
            # Should ctrl-C raise a KeyboardInterrupt?
            raise EOFError
        elif key == 'q':
            # Reproduce IRAF behavior by confirming whether
            # the user really intended on quitting. This prevents
            # accidentally hitting 'q' in the middle of a big
            # process and having to restart.
            _quit = raw_input("Do you really want to quit? (yes or no) ")
            if string.find(string.lower(_quit),'y') > -1:
                raise EOFError
        elif key == ':':
            sys.stdout.write(": ")
            sys.stdout.flush()
            result = result + ' ' + irafutils.tkreadline()[:-1]
        return result
    except IOError, error:
        raise IrafError(str(error))
