"""
implement IRAF ukey functionality

$Id$
"""
from __future__ import division # confidence high

import os, string, sys
import wutil
from stsci.tools import capable, for2to3, irafutils

try:
    import termios
except:
   if 0==sys.platform.find('win'): # not on win*, but IS on darwin & cygwin
       termios = None
   else:
       raise

# TERMIOS is deprecated in Python 2.1
if hasattr(termios, 'ICANON') or termios==None:
    TERMIOS = termios
else:
    import TERMIOS

# This class emulates the IRAF ukey parameter mechanism. IRAF calls for
# a ukey parameter and expects that the user will type a character in
# response. The value of this character is then returned to the iraf task

def getSingleTTYChar(): # return type str in all Python versions

    """Returns None if Control-C is typed or any other exception occurs"""

    # Ripped off from python FAQ
    fd = sys.stdin.fileno()
    old = termios.tcgetattr(fd)
    new = termios.tcgetattr(fd)
    new[3] = new[3] & ~(TERMIOS.ICANON | TERMIOS.ECHO | TERMIOS.ISIG)
    new[6][TERMIOS.VMIN] = 1
    new[6][TERMIOS.VTIME] = 0
    termios.tcsetattr(fd, TERMIOS.TCSANOW, new)
    c = None
    try:
        # allow Tk mainloop to run while waiting...
        # vanilla version would be c = os.read(fd, 1)
        if capable.OF_GRAPHICS:
            c = irafutils.tkread(fd, 1)
        else:
            c = os.read(fd, 1)
            if for2to3.PY3K: c = c.decode('ascii', 'replace')
    finally:
        termios.tcsetattr(fd, TERMIOS.TCSAFLUSH, old)
        return c

def ukey():

    """Returns the string expected for the IRAF ukey parameter"""

    # set focus to terminal if it is not already there
    wutil.focusController.setFocusTo('terminal')
    char = getSingleTTYChar()

    if not char:
        # on control-C, raise KeyboardInterrupt
        raise KeyboardInterrupt
    elif char == '\004':
        # on control-D, raise EOF
        raise EOFError
    elif ord(char) <= ord(' '):
        # convert to octal ascii representation
        returnStr = '\\'+"%03o" % ord(char)
    elif char == ':':
        # suck in colon string until newline is encountered
        done = 0
        sys.stdout.write(':')
        sys.stdout.flush()
        colonString = ''
        while not done:
            char = getSingleTTYChar()
            if (not char) or (char == '\n'):
                done = 1
            elif char == '\b':
                # backspace
                colonString = colonString[:-1]
                sys.stdout.write('\b \b')
                sys.stdout.flush()
            elif ord(char) >= ord(' '):
                colonString = colonString+char
                sys.stdout.write(char)
                sys.stdout.flush()
            else:
                # ignore all other characters
                pass
        returnStr = ': '+colonString
    else:
        returnStr = char
    return returnStr
