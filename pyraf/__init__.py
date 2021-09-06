"""
PyRAF is a command language for running IRAF tasks in a Python like
environment. It works very similar to IRAF, but has been updated to
allow such things as importing Python modules, starting in any
directory, GUI parameter editing and help. Most importantly, it can be
imported into Python allowing you to run IRAF commands from within a
larger script.
"""
import os
import sys

from stsci.tools import irafglobals  # noqa: F401

from .version import version as __version__  # noqa: F401

# Grab the terminal window's id at the earliest possible moment
from . import wutil  # noqa: F401

# Modify the standard import mechanism to make it more
# convenient for the iraf module
from . import irafimport  # noqa: F401

# this gives more useful tracebacks for CL scripts
from . import cllinecache  # noqa: F401

from . import irafnames  # noqa: F401
from . import irafexecute  # noqa: F401
from . import clcache


# set up exit handler to close caches
def _cleanup():
    if iraf:
        iraf.gflush()
    if hasattr(irafexecute, 'processCache'):
        del irafexecute.processCache
    if hasattr(clcache, 'codeCache'):
        del clcache.codeCache


import atexit  # noqa: E402
atexit.register(_cleanup)
del atexit

# Detect if the module was called via `python3 -m pyraf`:
executable = sys.argv[0]
while os.path.islink(executable):
    executable = os.readlink(executable)
_pyrafMain = os.path.split(executable)[1] in ('pyraf', '-m', 'epyraf')
del executable

# now get ready to do the serious IRAF initialization

# If iraf.Init() throws an exception, we cannot be confident
# that it has initialized properly.  This can later lead to
# exceptions from an atexit function.  This results in a lot
# of help tickets about "gki", which are really caused by
# something wrong in login.cl
#
# By setting iraf=None in the case of an exception, the cleanup
# function skips the parts that don't work.  By re-raising the
# exception, we ensure that the user sees what really happened.
#
# This is the case for "import pyraf"
try:
    from . import iraf
    if not _pyrafMain:
        iraf.Init(doprint=0, hush=1)
except Exception:
    iraf = None
    raise

help = iraf.help

if '-m' not in sys.argv:
    from .__main__ import main  # noqa: F401
