""" module irafinst.py - Defines bare-bones functionality needed when IRAF
is not present.  This is NOT a replacement for any major parts of IRAF.
For now, in general, we assume that IRAF exists until we are told otherwise.

Obviously, this module should refrain as much as possible from importing any
IRAF related code (at least globally), since this is heavily relied upon in
non-IRAF situations.
"""


import os
import shutil
import sys
import tempfile

# File name prefix signal
NO_IRAF_PFX = '*no~iraf*/'

# Are we running without an IRAF installation?  If no, EXISTS == False
if sys.platform.startswith('win'):
    EXISTS = False
else:
    EXISTS = 'PYRAF_NO_IRAF' not in os.environ

# Keep track of any tmp files created
_tmp_dir = None


# cleanup (for exit)
def cleanup():
    """ Try to cleanup.  Don't complain if the dir isn't there.  """
    global _tmp_dir
    if _tmp_dir:
        shutil.rmtree(_tmp_dir)
        _tmp_dir = None


# Create files on the fly when needed
def tmpParFile(fname):
    """ Create a tmp file for the given par file, and return the filename. """
    assert fname and fname.endswith('.par'), 'Unexpected file: ' + fname

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
        raise RuntimeError('Unexpected .par file: ' + fname)

    return _writeTmpFile(fname, content)


def _writeTmpFile(base_fname, text):
    """ Utility function for writing our tmp files. Return the full fname."""
    global _tmp_dir
    if not _tmp_dir:
        u = os.environ.get('USER', '')
        if not u:
            u = os.environ.get('LOGNAME', '')
        _tmp_dir = tempfile.mkdtemp(prefix='pyraf_' + u + '_tmp_',
                                    suffix='.no-iraf')
    tmpf = _tmp_dir + os.sep + base_fname
    if os.path.exists(tmpf):
        os.remove(tmpf)
    f = open(tmpf, 'w')
    f.write(text)
    f.close()
    return tmpf


def getNoIrafClFor(fname, useTmpFile=False):
    """ Generate CL file text on the fly when missing IRAF, return the
    full text sting.  If useTmpFile, then returns the temp file name. """

    assert fname and fname.endswith('.cl'), 'Unexpected file: ' + fname

    # First call ourselves to get the text if we need to write it to a tmp file
    if useTmpFile:
        return _writeTmpFile(fname, getNoIrafClFor(fname, useTmpFile=False))

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

    # basic login.cl for the case of no IRAF
    if fname == 'login.cl':
        usr = None
        try:
            if hasattr(os, 'getlogin'):
                usr = os.getlogin()
        except OSError:
            pass  # "Inappropriate ioctl for device" - happens in a cron job
        if not usr and 'USER' in os.environ:
            usr = os.environ['USER']
        if not usr and 'USERNAME' in os.environ:
            usr = os.environ['USERNAME']
        if not usr and 'LOGNAME' in os.environ:
            usr = os.environ['LOGNAME']
        ihome = os.getcwd() + '/'
        ihome = ihome.replace('\\', '/')  # for windoze
        content = '# LOGIN.CL -- User login file.\n'+ \
            'set home = "'+ihome+'"\nset userid = "'+usr+'"\n'+ \
            'set uparm = "home$uparm/"\n'+ \
            'stty xterm\n'+ \
            'showtype = yes\n'+ \
            '# Load default CL pkg - allow overrides via loginuser.cl\n'+\
            'clpackage\n'+ \
            '# Default USER package - to be modified by the user\n'+ \
            'package user\n'+ \
            '# Basic foreign tasks from UNIX\n'+ \
            'task  $adb $bc $cal $cat $comm $cp $csh $date $dbx = "$foreign"\n' +\
            'task  $df $diff $du $find $finger $ftp $grep $lpq  = "$foreign"\n' +\
            'task  $lprm $mail $make $man $mon $mv $nm $od      = "$foreign"\n' +\
            'task  $ps $rcp $rlogin $rsh $ruptime $rwho $sh     = "$foreign"\n' +\
            'task  $spell $sps $strings $su $telnet $tip $top   = "$foreign"\n' +\
            'task  $vi $emacs $w $wc $less $more $rusers $sync  = "$foreign"\n' +\
            'task  $pwd $gdb $xc $mkpkg $generic $rtar $wtar    = "$foreign"\n' +\
            'task  $tar $bash $tcsh $buglog $who $ssh $scp      = "$foreign"\n' +\
            'task  $mkdir $rm $chmod $sort                      = "$foreign"\n'
        if sys.platform.startswith('win'):
            content += '# Basic foreign tasks for Win\n'+ \
                'task  $cmd $cls $DIR $erase $start $title $tree = "$foreign"\n'+\
                'task  $ls  = "$DIR" \n'
        else:
            content += '# Conveniences\n'+ \
                'task  $ls    = "$foreign"\n' +\
                'task  $cls = "$clear;ls"\n' +\
                'task  $clw = "$clear;w"\n'
        content += 'if (access ("home$loginuser.cl"))\n' +\
            '   cl < "home$loginuser.cl"\n' +\
            ';\n' +\
            '# more ...\nkeep\n'
        return content

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
    raise RuntimeError('Unexpected .cl file: ' + fname)


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
