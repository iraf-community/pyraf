""" module irafinst.py - Defines bare-bones functionality needed when IRAF
is not present.  This is NOT a replacement for any major parts of IRAF.
For now, in general, we assume that IRAF exists until we are told otherwise.

Obviously, this module should refrain as much as possible from importing any
IRAF related code (at least globally), since this is heavily relied upon in
non-IRAF situations.
"""
import os
import sys

# File name prefix signal
NO_IRAF_PFX = f'{os.path.dirname(__file__)}/noiraf'

# Are we running without an IRAF installation?  If no, EXISTS == False
if sys.platform.startswith('win'):
    EXISTS = False
else:
    EXISTS = 'PYRAF_NO_IRAF' not in os.environ


def getIrafVer():
    """ Return current IRAF version as a string """
    from . import iraffunctions
    cltask = iraffunctions.getTask('cl')
    # must use default par list, in case they have a local override
    plist = cltask.getDefaultParList()
    # get the 'release' par and then get it's value
    release = [p.value for p in plist if p.name == 'release']
    return release[0]  # only 1 item in list


def getIrafVerTup():
    """ Return current IRAF version as a tuple (ints until last item) """
    verlist = getIrafVer().split('.')
    outlist = []
    for v in verlist:
        if v.isdigit():
            outlist.append(int(v))
        else:
            outlist.append(v)
    return tuple(outlist)
