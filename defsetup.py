#!/usr/bin/env python

import os, os.path, sys, commands
import distutils.core
import distutils.sysconfig 

x_libraries = 'X11'

add_lib_dirs = [ distutils.sysconfig.get_python_lib(plat_specific=1, standard_lib = 1) ]

add_inc_dirs = [ distutils.sysconfig.get_python_inc(plat_specific=1) ]



def find_x(xdir=""):
    if xdir != "":
        add_lib_dirs.append(os.path.join(xdir,'lib64'))
        add_lib_dirs.append(os.path.join(xdir,'lib'))
        add_inc_dirs.append(os.path.join(xdir,'include'))
    elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
        add_lib_dirs.append('/usr/X11R6/lib64')
        add_lib_dirs.append('/usr/X11R6/lib')
        add_inc_dirs.append('/usr/X11R6/include')
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

find_x()

def dir_clean(list) :
    # We have a list of directories.  Remove any that don't exist.
    r = [ ]
    for x in list :
        if os.path.isdir(x) :
            r.append(x)
    return r

add_lib_dirs = dir_clean(add_lib_dirs)
add_inc_dirs = dir_clean(add_inc_dirs)

PYRAF_EXTENSIONS = [distutils.core.Extension('pyraf.sscanfmodule', ['src/sscanfmodule.c'],
                              include_dirs=add_inc_dirs),
                    distutils.core.Extension('pyraf.xutilmodule', ['src/xutil.c'],
                              include_dirs=add_inc_dirs,
                              library_dirs=add_lib_dirs,
                              libraries = [x_libraries])]

pkg = "pyraf"

DATA_FILES = [ ( pkg, 
                    ['data/blankcursor.xbm',
                    'data/epar.optionDB',
                    'data/pyraflogo_rgb_web.gif',
                    'data/ipythonrc-pyraf',
                    'lib/LICENSE.txt',
                    ]
                ),
                (pkg+'/clcache',  [ "data/clcache/*" ] ) 
        ]


setupargs = {
    'version' :			    "1.x", # see lib's __init__.py
    'description' :		    "A Python based CL for IRAF",
    'author' :			    "Rick White, Perry Greenfield",
    'maintainer_email' :	"help@stsci.edu",
    'url' :			        "http://www.stsci.edu/resources/software_hardware/pyraf",
    'license' :			    "http://www.stsci.edu/resources/software_hardware/pyraf/LICENSE",
    'platforms' :			["unix"],
    'data_files' :			DATA_FILES,
    'scripts' :			    ['lib/pyraf'],
    'ext_modules' :			PYRAF_EXTENSIONS

}

