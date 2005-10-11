#!/usr/bin/env python

import os, os.path, sys, shutil, commands, fnmatch
from distutils.core import setup,Extension
from distutils.command.build_ext import build_ext
from distutils.sysconfig import *
from distutils.command.install import install


#local_libs = parse_makefile(get_makefile_filename())['LOCALMODLIBS']
py_includes = get_python_inc(plat_specific=1)
py_libs =  get_python_lib(plat_specific=1, standard_lib = 1)
#py_bin = parse_makefile(get_makefile_filename())['BINDIR']
x_libraries = 'X11'
#scripts = parse_makefile(get_makefile_filename())['SCRIPTDIR']
ver = sys.version_info
python_exec = 'python' + str(ver[0]) + '.' + str(ver[1])
add_lib_dirs = []
add_inc_dirs = []
add_inc_dirs.append(py_includes)
add_lib_dirs.append(py_libs)

def find_x(xdir=""):
    if xdir != "":
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



def getExtensions(args, add_inc_dirs, add_lib_dirs):
    for a in args:
        if string.find(a, '--with-opengl=') != 0:
            e1 = [Extension('pyraf/sscanfmodule', ['src/sscanfmodule.c'],
                           include_dirs=add_inc_dirs),
                  Extension('pyraf/xutilmodule', ['src/xutil.c'],
                           include_dirs=add_inc_dirs,
                           library_dirs=add_lib_dirs,
                           libraries = [x_libraries])]
        else:
            opengl_inc=string.split(a, '=')[1]
            add_inc_dirs.append(opengl_inc)
            add_inc_dirs.append(tcl_inc)
            add_inc_dirs.append(src)
            add_lib_dirs.append(tcl_lib)
            sys.argv.remove(a)
            e1 = [Extension('pyraf/sscanfmodule', ['src/sscanfmodule.c'],
                           include_dirs=add_inc_dirs),
                  Extension('pyraf/xutilmodule', ['src/xutil.c'],
                           include_dirs=add_inc_dirs,
                           library_dirs=add_lib_dirs,
                           libraries = [x_libraries]),
                  Extension('pyraf/toglcolorsmodule', ['src/toglcolors.c'],
                           include_dirs=add_inc_dirs,
                           library_dirs=add_lib_dirs,
                           extra_objects = [os.path.join(tcl_lib, "Togl.so")],
                            )]

    return e1


def getDataDir(args):
    for a in args:
        if string.find(a, '--home=') == 0:
            dir = os.path.abspath(string.split(a, '=')[1])
            data_dir = os.path.join(dir, 'lib/python/pyraf')
        elif string.find(a, '--prefix=') == 0:
            dir = os.path.abspath(string.split(a, '=')[1])
            data_dir = os.path.join(dir, 'lib', python_exec, 'site-packages/pyraf')
        elif a.startswith('--install-data='):
            dir = os.path.abspath(string.split(a, '=')[1])
            data_dir = dir
        else:
            data_dir = os.path.join(sys.prefix, 'lib', python_exec, 'site-packages/pyraf')
    return data_dir

def dolocal():
    """Adds a command line option --local=<install-dir> which is an abbreviation for
    'put all of pyraf in <install-dir>/pyraf'."""
    if "--help" in sys.argv:
        print >>sys.stderr
        print >>sys.stderr, " options:"
        print >>sys.stderr, "--local=<install-dir>    same as --install-lib=<install-dir> --install-headers=<install-dir>/pyraf --install-scripts=<install-dir>/pyraf --install-data=<install-dir>/pyraf"
    for a in sys.argv:
        if a.startswith("--local="):
            dir = os.path.abspath(a.split("=")[1])
            print 'dir ', dir
            sys.argv.extend([
                "--install-lib="+dir,
                "--install-headers="+os.path.join(dir,"pyraf"),
                "--install-scripts="+os.path.join(dir,"pyraf"),
                "--install-data="+os.path.join(dir,"pyraf")
                ])
            sys.argv.remove(a)


def dosetup(data_dir, ext):
    r = setup(name = "PyRAF",
     version = "1.2",
     description = "A Python based CL for IRAF",
     author = "Rick White, Perry Greenfield",
     maintainer_email = "help@stsci.edu",
     url = "http://www.stsci.edu/resources/software_hardware/pyraf",
     license = "http://www.stsci.edu/resources/software_hardware/pyraf/LICENSE",
     platforms = ["unix"],
     packages = ['pyraf'],
     package_dir = {'pyraf':'lib'},
     data_files = [(data_dir,['data/blankcursor.xbm']), (data_dir, ['data/epar.optionDB']), (data_dir,['data/pyraflogo_rgb_web.gif']), (data_dir,['lib/LICENSE.txt'])],
     scripts = ['lib/pyraf'],
     ext_modules = ext)

    return r

def copy_clcache(data_dir, args):
    if 'install' in args:
        clcache_dir = os.path.join(data_dir,'clcache')
        if os.path.exists(clcache_dir):
            shutil.rmtree(clcache_dir)
        os.mkdir(clcache_dir)
        for file in os.listdir('data/clcache'):
            if fnmatch.fnmatch(file, '.svn'):
                pass
            else:
                shutil.copy2(os.path.join('data/clcache', file), clcache_dir)


def main():
    args = sys.argv
    x_dir = ""
    for a in args:
        if a.startswith('--with-x='):
            x_dir = a.split("=")[1]
            sys.argv.remove(a)
    find_x(x_dir)
    dolocal()
    print add_lib_dirs, add_inc_dirs
    data_dir = getDataDir(args)

    ext = getExtensions(args, add_inc_dirs, add_lib_dirs)
    dosetup(data_dir, ext)
    copy_clcache(data_dir, args)


if __name__ == "__main__":
    main()
