#!/usr/bin/env python

import os, os.path, sys, shutil, glob
from distutils.core import setup,Extension
from distutils.command.build_ext import build_ext
from distutils.sysconfig import *
from distutils.command.install import install

try:
    import Tkinter

except:
    print "Tkinter not properly installed\n"
    exit(1)

if Tkinter.TkVersion < 8.3:
    print "Tcl/Tk v8.3 or later required\n"
    exit(1)

tk=Tkinter.Tk()
tk.withdraw()
tcl_lib = glob.glob(os.path.join((tk.getvar('tcl_library')), '../'))
tcl_inc = glob.glob(os.path.join((tk.getvar('tcl_library')), '../../include'))
local_libs = parse_makefile(get_makefile_filename())['LOCALMODLIBS']
py_includes = get_python_inc(plat_specific=1)
py_libs =  get_python_lib(plat_specific=1, standard_lib = 1)
py_bin = parse_makefile(get_makefile_filename())['BINDIR']
x_libraries = 'X11'
scripts = parse_makefile(get_makefile_filename())['SCRIPTDIR']
ver = sys.version_info
python_exec = 'python' + str(ver[0])+'.'+str(ver[1])


def getExtensions(args, x_inc_dirs, x_lib_dirs):
    for a in args:
        if string.find(a, '--with-opengl=') != 0:
            e1 = [Extension('pyraf/sscanfmodule', ['src/sscanfmodule.c'],
                           include_dirs=[py_includes]),
                  Extension('pyraf/xutilmodule', ['src/xutil.c'],
                           include_dirs=[py_includes, x_inc_dirs],
                           library_dirs=[x_lib_dirs],
                           libraries = [x_libraries])]
        else:
            opengl_inc=string.split(a, '=')[1]
            sys.argv.remove(a)
            e1 = [Extension('pyraf/sscanfmodule', ['src/sscanfmodule.c'],
                           include_dirs=[py_includes]),
                  Extension('pyraf/xutilmodule', ['src/xutil.c'],
                           include_dirs=[py_includes, x_inc_dirs],
                           library_dirs=[x_lib_dirs],
                           libraries = [x_libraries]),
                  Extension('pyraf/toglcolorsmodule', ['src/toglcolors.c'],
                           include_dirs=[py_includes, x_inc_dirs, 'src', opengl_inc, tcl_inc],
                           library_dirs=[x_lib_dirs, tcl_lib],
                           extra_objects = [tcl_lib+"/Togl.so"])]

    return e1

def get_x_libraries(localmodlibs):
    for x in string.split(localmodlibs, '-L'):
        if string.find(x, '-lX11') != -1:
            for y in string.split(x, ' '):
                if os.path.isdir(y):
                    return y

def get_x_libraries(localmodlibs):
    for x in string.split(localmodlibs, '-L'):
        if string.find(x, '-lX11') != -1:
            for y in string.split(x, ' '):
                if os.path.isdir(y):
                    return y

def getDataDir(args):
    for a in args:
        if string.find(a, '--home=') == 0:
            dir = string.split(a, '=')[1]
            data_dir = os.path.join(dir, 'lib/python/pyraf')
        elif string.find(a, '--prefix=') == 0:
            dir = string.split(a, '=')[1]
            data_dir = os.path.join(dir, 'lib', python_exec, 'site-packages/pyraf')
        elif string.find(a, '--install-data=') == 0:
            dir = string.split(a, '=')[1]
            print "dir = ", dir
            data_dir = dir
        else:
            data_dir = os.path.join(sys.prefix, 'lib', python_exec, 'site-packages/pyraf')
    return data_dir




def dosetup(x_lib_dirs, x_inc_dirs, data_dir, ext):
    r = setup(name="PyRAF",
     version="1.1",
     description="A Python based CL for IRAF",
     author="Rick White, Perry Greenfield",
     maintainer_email="help@stsci.edu",
     url="http://www.stsci.edu/resources/software_hardware/pyraf",
     packages=['pyraf'],
     package_dir = {'pyraf':'lib'},
     data_files=[(data_dir,['data/blankcursor.xbm']), (data_dir, ['data/dbcopy']), (data_dir, ['data/epar.optionDB']), (data_dir,['data/pyraflogo_rgb_web.gif']), (data_dir,['lib/LICENSE.txt'])],
     scripts=['lib/pyraf'],
     ext_modules=ext)

    return r


def main():
    x_lib_dirs = get_x_libraries(local_libs)
    x_inc_dirs  = os.path.normpath(os.path.join(x_lib_dirs, '../include'))
    args = sys.argv
    print args
    data_dir = getDataDir(args)
    print "data_dir = ", data_dir
    ext=getExtensions(args, x_inc_dirs, x_lib_dirs)
    dosetup(x_lib_dirs, x_inc_dirs, data_dir, ext)
    shutil.copytree('data/clcache/', os.path.join(data_dir,'clcache'))


if __name__ == "__main__":
    main()
