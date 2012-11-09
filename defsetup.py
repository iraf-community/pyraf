#!/usr/bin/env python
from __future__ import division # confidence high

import os, os.path, shutil, sys, commands
import distutils.core
import distutils.sysconfig
import string


## conditional flags, defaults

# conditional for if we are running on Windows
ms_windows = sys.platform.startswith('win')

# conditional for if we should build the C code
build_c = not ms_windows

C_EXT_MODNAME_ENDING = 'module'
if sys.version_info[0] > 2: # actually changes in Python 3.3, but why wait
    C_EXT_MODNAME_ENDING = '' # needs not "sscanfmodule.so", but "sscanf.so"

# default to no C extensions; add to this list when necessary
PYRAF_EXTENSIONS = []

# get the python libraries for use by C extensions
# (why? doesn't distutils already reference those?)
add_lib_dirs = [ distutils.sysconfig.get_python_lib(plat_specific=1, standard_lib = 1) ]
add_inc_dirs = [ distutils.sysconfig.get_python_inc(plat_specific=1) ]

## x windows specific features

x_libraries = 'X11'


def find_x(xdir=""):
    if xdir != "":
        add_lib_dirs.append(os.path.join(xdir,'lib64'))
        add_lib_dirs.append(os.path.join(xdir,'lib'))
        add_inc_dirs.append(os.path.join(xdir,'include'))
    elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
        add_lib_dirs.append('/usr/X11R6/lib64')
        add_lib_dirs.append('/usr/X11R6/lib')
        add_inc_dirs.append('/usr/X11R6/include')
    elif sys.platform == 'sunos5' :
        add_lib_dirs.append('/usr/openwin/lib')
        add_inc_dirs.append('/usr/openwin/include')
    else:
        try:
            import Tkinter
        except:
            raise ImportError("Tkinter is not installed")
        tk=Tkinter.Tk()
        tk.withdraw()
        tcl_lib = os.path.join((tk.getvar('tcl_library')), '../')
        tcl_inc = os.path.join((tk.getvar('tcl_library')), '../../include')
        tk_lib = os.path.join((tk.getvar('tk_library')), '../')
        tkv = str(Tkinter.TkVersion)[:3]
        # yes, the version number of Tkinter really is a float...
        if Tkinter.TkVersion < 8.3:
            print "Tcl/Tk v8.3 or later required\n"
            sys.exit(1)
        else:
            suffix = '.so'
            tklib='libtk'+tkv+suffix
            command = "ldd %s" % (os.path.join(tk_lib, tklib))
            lib_list = string.split(commands.getoutput(command))
            for lib in lib_list:
                if string.find(lib, 'libX11') == 0:
                    ind = lib_list.index(lib)
                    add_lib_dirs.append(os.path.dirname(lib_list[ind + 2]))
                    #break
                    add_inc_dirs.append(os.path.join(os.path.dirname(lib_list[ind + 2]), '../include'))

if not ms_windows :
    # Should we do something about X if we're using aqua on a mac?
    # Apparently it doesn't cause any problems.
    find_x()

#

def dir_clean(list) :
    # We have a list of directories.  Remove any that don't exist.
    r = [ ]
    for x in list :
        if os.path.isdir(x) :
            r.append(x)
    return r

add_lib_dirs = dir_clean(add_lib_dirs)
add_inc_dirs = dir_clean(add_inc_dirs)

## C extensions

# by default, we don't build any C extensions on MS Windows.  The
# user probably does not have a compiler, and these extensions just
# aren't that important.

if not ms_windows or build_c :
    # windows users have to do without the CL sscanf() function,
    # unless you explicitly set build_c true.
    PYRAF_EXTENSIONS.append(
        distutils.core.Extension(
            'pyraf.sscanf'+C_EXT_MODNAME_ENDING,
            ['src/sscanfmodule.c'],
            include_dirs=add_inc_dirs
        )
    )

if not ms_windows :
    # windows users do not have X windows, so we never need the X
    # support
    PYRAF_EXTENSIONS.append(
        distutils.core.Extension(
            'pyraf.xutil'+C_EXT_MODNAME_ENDING,
            ['src/xutil.c'],
            include_dirs=add_inc_dirs,
            library_dirs=add_lib_dirs,
            libraries = [x_libraries]
        )
    )


## what scripts do we install

if ms_windows :
    # On windows, you use "runpyraf.py" -  it can't be pyraf.py
    # because then you can't "import pyraf" in the script.
    # Instead, you ( double-click the icon for runpyraf.py ) or
    # ( type "runpyraf.py" ) or ( type "pyraf" to get pyraf.bat ).

    # adapt to installing in the pyraf package or installing stsci_python
    if os.path.exists('pyraf'):
        scriptdir = [ 'pyraf', 'scripts' ]
    else :
        scriptdir = [ 'scripts' ]

    # copy the pyraf main program to the name we want it installed as
    shutil.copy(
        os.path.join( * ( scriptdir + [ 'pyraf' ] ) ) ,
        os.path.join( * ( scriptdir + [ 'runpyraf.py' ] ) )
        )

    # list of scripts for windows
    scriptlist = ['scripts/runpyraf.py', 'scripts/pyraf.bat']

else :
    # on linux/mac, you have just the one main program
    scriptlist = ['scripts/pyraf' ]

## icon on the desktop

if ms_windows :
    # Install optional launcher onto desktop
    if 'USERPROFILE' in os.environ:
       dtop = os.environ['USERPROFILE']+os.sep+'Desktop'
       if os.path.exists(dtop):
           shortcut = dtop+os.sep+"PyRAF.bat"
           if os.path.exists(shortcut):
               os.remove(shortcut)
           target = sys.exec_prefix+os.sep+"Scripts"+os.sep+"runpyraf.py"
           f = open(shortcut, 'w')
           f.write('@echo off\necho.\ncd %APPDATA%\n')
           f.write('echo Launching PyRAF ...\necho.\n')
           f.write(target)
           f.write('\necho.\npause\n')
           f.close()
           print('Installing PyRAF.bat to -> '+dtop)
       else:
           print('Error: User desktop not found at: '+dtop)
    else:
       print('Error: User desktop location unknown')

    # NOTE: a much better solution would be to use something (bdist) to
    # create installer binaries for Windows, since they are: 1) easier on
    # the win user, and 2) can be used to create actual desktop shortcuts,
    # not this kludgy .bat file.  If we take out the two libraries built
    # from the bdist run (which aren't used on Win anyway) then we can
    # automate this build from Linux (yes, for Windows), via:
    #    python setup.py bdist_wininst --no-target-compile --plat-name=win32
    # and
    #    python setup.py bdist_wininst --no-target-compile --plat-name=win-amd64
    # We would need to provide both 32- and 64-bit versions since the
    # installer will fail gracelessly if you try to install one and the Win
    # node only has the other (listed in its registry).  The above 64-bit bdist
    # fails currently on thor but the 32-bit bdist works.  Need to investigate.

    # Another option to create the shortcut is to bundle win32com w/ installer.

## the defsetup interface is here:

## pkg

pkg = "pyraf"

# data files

DATA_FILES = [ ( pkg,
                    ['data/blankcursor.xbm',
                    'data/epar.optionDB',
                    'data/pyraflogo_rgb_web.gif',
                    'data/ipythonrc-pyraf',
                    'LICENSE.txt',
                    ]
                )
        ]

if not ms_windows and sys.version_info[0] < 3:
    # clcache is a pre-loaded set of CL files already converted to
    # python.  There are none on Windows, so we don't need them.
    # We also are not yet using them in PY3K.
    # Leaving them out makes the install go a lot faster.
    DATA_FILES += [
                (pkg+'/clcache',  [ "data/clcache/*" ] )
        ]


## setupargs

setupargs = {
    'version' :			    "2.x", # see lib's __init__.py
    'description' :		    "A Python based CL for IRAF",
    'author' :			    "Rick White, Perry Greenfield",
    'maintainer_email' :	"help@stsci.edu",
    'url' :			        "http://www.stsci.edu/resources/software_hardware/pyraf",
    'license' :			    "http://www.stsci.edu/resources/software_hardware/pyraf/LICENSE",
    'platforms' :			["unix"],
    'data_files' :			DATA_FILES,
    'scripts' :			    scriptlist,
    'ext_modules' :			PYRAF_EXTENSIONS,
    'package_dir' :         { 'pyraf' : 'lib/pyraf' },
}


