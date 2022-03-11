""" Learn basic capabilities here (e.g. can we display graphics?).
This is meant to be fast and light, having no complicated dependencies, so
that any module can fearlessly import this without adverse affects or
performance concerns.

$Id$
"""
import os
import sys

descrip = "basic capabilities file, last edited: 28 Dec 2017"


def is_darwin_and_x():
    """ Convenience function.  Returns True if is an X11-linked Python/tkinter
    build on OSX.  This is intended to be quick and easy without further
    imports.  As a result, this relies on the assumption that on OSX, PyObjC
    is installed (only) in the Framework builds of Python. """
    if not sys.platform == 'darwin':
        return False

    return which_darwin_linkage() == "x11"


def which_darwin_linkage(force_otool_check=False):
    """ Convenience function.  Returns one of ('x11', 'aqua') in answer to the
    question of whether this is an X11-linked Python/tkinter, or a natively
    built (framework, Aqua) one.  This is only for OSX.
    This relies on the assumption that on OSX, PyObjC is installed
    in the Framework builds of Python.  If it doesn't find PyObjC,
    this inspects the actual tkinter library binary via otool.

    One driving requirement here is to try to make the determination quickly
    and quietly without actually importing/loading any GUI libraries.  We
    even want to avoid importing tkinter if we can.
    """

    # sanity check
    if sys.platform != 'darwin':
        raise OSError('Incorrect usage, not on OSX')

    # If not forced to run otool, then make some quick and dirty
    # simple checks/assumptions, which do not add to startup time and do not
    # attempt to initialize any graphics.
    if not force_otool_check:

        # There will (for now) only ever be an aqua-linked Python/tkinter
        # when using Ureka on darwin, so this is an easy short-circuit check.
        if 'UR_DIR' in os.environ:
            return "aqua"

        # There will *usually* be PyObjC modules on sys.path on the natively-
        # linked Python. This is assumed to be always correct on Python 2.x, as
        # of 2012.  This is kludgy but quick and effective.
        sp = ",".join(sys.path)
        sp = sp.lower().strip(',')
        if '/pyobjc' in sp or 'pyobjc,' in sp or 'pyobjc/' in sp or sp.endswith('pyobjc'):
            return "aqua"

        # Try one more thing - look for the physical PyObjC install dir under site-packages
        # The assumption above using sys.path does not seem to be correct as of the
        # combination of Python2.7.9/PyObjC3.0.4/2015.
        sitepacksloc = os.path.split(os.__file__)[0]+'/site-packages/objc'
        if os.path.exists(sitepacksloc):
            return "aqua"

        # OK, no trace of PyObjC found - need to fall through to the forced otool check.

    # Use otool shell command
    import tkinter as TKNTR
    import subprocess  # nosec
    try:
        tk_dyn_lib = TKNTR._tkinter.__file__
    except AttributeError: # happens on Ureka
        if 'UR_DIR' in os.environ:
            return 'aqua'
        else:
            return 'unknown'
    libs = subprocess.check_output(('/usr/bin/otool', '-L', tk_dyn_lib)).decode('ascii')  # nosec
    if libs.find('/libX11.') >= 0:
        return "x11"
    else:
        return "aqua"


def get_dc_owner(raises, mask_if_self):
    """ Convenience function to return owner of /dev/console.
    If raises is True, this raises an exception on any error.
    If not, it returns any error string as the owner name.
    If owner is self, and if mask_if_self, returns "<self>"."""
    try:
        from pwd import getpwuid
        owner_uid = os.stat('/dev/console').st_uid
        self_uid  = os.getuid()
        if mask_if_self and owner_uid == self_uid:
            return "<self>"
        owner_name = getpwuid(owner_uid).pw_name
        return owner_name
    except Exception as e:
        if raises:
            raise e
        else:
            return str(e)


OF_GRAPHICS = True

if 'PYRAF_NO_DISPLAY' in os.environ or 'PYTOOLS_NO_DISPLAY' in os.environ:
    OF_GRAPHICS = False

if OF_GRAPHICS and sys.platform == 'darwin':
    #
    # On OSX, there is an AppKit error where Python itself will abort if
    # tkinter operations (e.g. tkinter._test() ...) are attempted when running
    # from a remote terminal.  In these situations, it is not even safe to put
    # the code in a try/except block, since the AppKit error seems to happen
    # *asynchronously* within ObjectiveC code.  See PyRAF ticket #149.
    #
    # SO, let's try a quick simple test here (only on OSX) to find out if we
    # are the "console user".  If we are not, then we don't even want to attempt
    # any windows/graphics calls.  See "console user" here:
    #     http://developer.apple.com/library/mac/#technotes/tn2083/_index.html
    # If we are the console user, we own /dev/console and can read from it.
    # When no one is logged in, /dev/console is owned by "root". When user "bob"
    # is logged in locally/physically, /dev/console is owned by "bob".
    # However, if "bob" restarts the X server while logged in, /dev/console
    # may be owned by "sysadmin" - so we check for that.
    #
    if 'PYRAF_YES_DISPLAY' not in os.environ:
        # the use of PYRAF_YES_DISPLAY is a temporary override while we
        # debug why a user might have no read-acces to /dev/console
        dc_owner = get_dc_owner(False, False)
        OF_GRAPHICS = dc_owner == 'sysadmin' or os.access("/dev/console", os.R_OK)

    # Add a double-check for remote X11 users.  We *think* this is a smaller
    # set of cases, so we do it last minute here:
    if not OF_GRAPHICS:
        # On OSX, but logged in remotely. Normally (with native build) this
        # means there are no graphics.  But, what if they're calling an
        # X11-linked Python?  Then we should allow graphics to be attempted.
        OF_GRAPHICS = is_darwin_and_x()

        # OF_GRAPHICS will be True here in only two cases (2nd should be rare):
        #    An OSX Python build linked with X11, or
        #    An OSX Python build linked natively where PyObjC was left out

# After all that, we may have decided that we want graphics.  Now
# that we know it is ok to try to import tkinter, we can test if it
# is there.  If it is not, we are not capable of graphics.
if OF_GRAPHICS :
    try :
        import tkinter as TKNTR
    except ImportError :
        TKINTER_IMPORT_FAILED = 1
        OF_GRAPHICS = False

# Using tkFileDialog from PyRAF (and maybe in straight TEAL) is crashing python
# itself on OSX only.  Allow on Linux.  Mac: use this until PyRAF #171 fixed.
OF_TKFD_IN_EPAR = True
if sys.platform == 'darwin' and OF_GRAPHICS and \
   not is_darwin_and_x(): # if framework ver
    OF_TKFD_IN_EPAR = 'TEAL_TRY_TKFD' in list(os.environ.keys())
