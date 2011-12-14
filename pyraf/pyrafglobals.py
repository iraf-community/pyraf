"""module pyrafglobals.py -- widely used PyRAF constants and objects

pyrafDir        Directory with these Pyraf programs
_use_ecl        Flag to turn on ECL mode in PyRAF

This is defined so it is safe to say 'from pyrafglobals import *'

$Id$

Broken out from irafglobals.py which was signed "R. White, 2000 January 5"
"""

from __future__ import division  # confidence high

import os as _os
import sys as _sys

from stsci.tools.irafglobals import userWorkingHome

_use_ecl = _os.environ.get("PYRAF_USE_ECL", False)

# -----------------------------------------------------
# pyrafDir is directory containing this script
# -----------------------------------------------------
if __name__ == "__main__":
    thisfile = _sys.argv[0]
else:
    thisfile = __file__
# follow links to get to the real filename
while _os.path.islink(thisfile):
    thisfile = _os.readlink(thisfile)
pyrafDir = _os.path.dirname(thisfile)
del thisfile

if not pyrafDir:
    pyrafDir = userWorkingHome
# change relative directory paths to absolute and normalize path
pyrafDir = _os.path.normpath(_os.path.join(userWorkingHome, pyrafDir))
del userWorkingHome


def get_resource_filename(resource):
    """
    Returns the absolute path of a pyraf resource file.

    Raises an IOError if the resource is not found, or if pyraf isn't being
    imported from the filesystem, and there is not meaningful __file__
    attribute to rely on.
    """

    try:
        here = _os.path.abspath(_os.path.dirname(__file__))
    except NameError:
        here = None
    else:
        if not _os.path.isdir(here):
            here = None

    if here is None:
        raise IOError('Could not retrieve pyraf resource %r: the filesystem '
                      'location could not be determined.' % resource)

    # Try looking for the file in pyrafDir just in case...
    if pyrafDir and pyrafDir != here:
        filename = _os.path.join(pyrafDir, resource)
        if _os.path.isfile(filename):
            return filename

    filename = _os.path.join(here, 'resources', resource)
    if not _os.path.isfile(filename):
        raise IOError('pyraf resource %r does not exist.' % resource)

    return filename
