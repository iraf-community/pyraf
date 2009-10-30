""" module irafinst.py - Defines bare-bones functionality needed when IRAF
is not present.  This is NOT a replacement for any major parts of IRAF.
For now, in general, we assume that IRAF exists until we are told otherwise.

Obviously, this module should refrain as much as possible from importing any
IRAF related code, since this is heavily relied upon in non-IRAF situations.

$Id$
"""
from __future__ import division # confidence high

import os, sys


# File name prefix signal
NO_IRAF_PFX = '*no~iraf*/'

# Are we running without an IRAF installation?  If no, EXISTS == False
if sys.platform.startswith('win'):
    EXISTS = False
else:
    EXISTS = 'PYRAF_NO_IRAF' not in os.environ

# Keep track of any tmp files created
_files = []

# cleanup (for exit)
def cleanup():
    """ Try to cleanup.  Don't complain if the files isn't there.  """
    global _files
    for f in _files:
        os.remove(f)
    _files = []


# Create files on the fly when needed
def tmpParFile(fname):
    """ Create a tmp file for the given par file, and return the filename. """
    global _files
    assert fname and fname.endswith('.par'), 'Unexpected file: '+fname

    if fname == 'cl.par':
        content = """
# Variables effecting cl operation.
args,s,h,,,,CL command line arguments
gcur,*gcur,a,,,,Graphics cursor
imcur,*imcur,a,,,,Image cursor
ukey,*ukey,a,,,,Global user terminal keyboard keylist
abbreviate,b,h,yes,,,Allow abbreviations in operand names?
echo,b,h,no,,,Echo CL command input on stderr?
ehinit,s,h,"nostandout eol noverify",,,Ehistory options string
epinit,s,h,"standout showall",,,Eparam options string
keeplog,b,h,no,,,Record all interactive commands in logfile?
logfile,f,h,"home$logfile.cl",,,Name of the logfile
logmode,s,h,"commands nobackground noerrors notrace",,,Logging control
lexmodes,b,h,yes,,,Enable conversational mode
menus,b,h,yes,,,Display menu when changing packages?
showtype,b,h,no,,,Add task-type suffix in menus?
notify,b,h,yes,,,Send done message when bkgrnd task finishes?
szprcache,i,h,4,1,10,Size of the process cache
version,s,h,"IRAF V2.14EXPORT Nov 2007",,,IRAF version
logver,s,h,"",,,login.cl version
logregen,b,h,no,,,Updating of login.cl to current version is advised
release,s,h,"2.14",,,IRAF release
mode,s,h,ql,,,CL mode of execution (query or query+learn)
#
auto,s,h,a,,,The next 4 params are read-only.
query,s,h,q
hidden,s,h,h
learn,s,h,l
menu,s,h,m
#
# Handy boolean variables for interactive use.
b1,b,h,,,,b1
b2,b,h,,,,b2
b3,b,h,,,,b3
# Handy integer variables for interactive use.
i,i,h,,,,i
j,i,h,,,,j
k,i,h,,,,k
# Handy real variables for interactive use.
x,r,h,,,,x
y,r,h,,,,y
z,r,h,,,,z
# Handy string variables for interactive use.
s1,s,h,,,,s1
s2,s,h,,,,s2
s3,s,h,,,,s3
# Handy parameter for reading lists (text files).
list,*s,h,,,,list
# Line buffer for list files.
line,struct,h,,,,line
...
"""
    elif fname == 'system.par':
        content = """
version,s,h,"12-Nov-83"
mode,s,h,ql
"""
    
    else:
        # For now that's it - this must be a file we don't handle
        raise RuntimeError('Unexpected .par file: '+fname)

    tmpd = os.environ['HOME']+os.sep+'.pyraf-no-iraf' # !!! use tmp dir
    if not os.path.exists(tmpd): os.mkdir(tmpd)
    tmpf = tmpd+os.sep+fname
    if os.path.exists(tmpf): os.remove(tmpf)
    f = open(tmpf, 'w')
    f.write(content)
    f.close()
    _files.append(tmpf)
    return tmpf


def getNoIrafClFor(fname):
    """ Generate CL file text on the fly when missing IRAF, return the str. """

    assert fname and fname.endswith('.cl'), 'Unexpected file: '+fname

    # bare-bones clpackage.cl
    if fname == 'clpackage.cl':
        return """
# IRAF standard system package script task declarations.
task  language.pkg = "language$language.cl"
task  system.pkg   = "system$system.cl"
# Handy task to call the user's logout.cl file.
task  $_logout     = "home$logout.cl"
# (might use as a hook) Define any external (user-configurable) packages.
# cl < hlib$extern.pkg
#
if (menus) {
    menus = no;  system;  menus = yes
} else
    system
keep
"""

    # bare-bones system.cl
    if fname == 'system.cl':
        return """
# lists (not using these for now in this case)

# { SYSTEM.CL -- Package script task for the SYSTEM package.  This package is
# loaded by the CL upon startup, and is always in the search path.

package system

# These tasks might be useful to convert to Python where no IRAF exists

#task cmdstr,
#    concatenate,
#    copy,
#    count,
#    delete,
#    directory,
#    files,
#    head,
#    lprint,
#    match,
#    mkdir,
#    movefiles,
#    mtclean,
#    $netstatus,
#    page,
#    pathnames,
#    protect,
#    rename,
#    sort,
#    tail,
#    tee,
#    touch,
#    type,
#    rewind,
#    unprotect,
#    help = "system$x_system.e"
#hidetask cmdstr
#hidetask mtclean

task  mkscript    = "system$mkscript.cl"
task  $news       = "system$news.cl"
task  allocate    = "hlib$allocate.cl"
task  gripes      = "hlib$gripes.cl"
task  deallocate  = "hlib$deallocate.cl"
task  devstatus   = "hlib$devstatus.cl"
task  $diskspace  = "hlib$diskspace.cl"
task  $spy        = "hlib$spy.cl"
task  $devices    = "system$devices.cl"
task  references  = "system$references.cl"
task  phelp       = "system$phelp.cl"

keep
"""

    # For now that's it - this must be a file we don't handle
    raise RuntimeError('Unexpected .cl file: '+fname)
