#!/usr/bin/env python

import os, os.path, sys, shutil, commands, fnmatch, glob
from distutils.core import setup,Extension
from distutils.command.build_ext import build_ext
from distutils.sysconfig import *
from distutils.command.install import install
from distutils.command.install_data import install_data

py_includes = get_python_inc(plat_specific=1)
py_libs =  get_python_lib(plat_specific=1, standard_lib = 1)
x_libraries = 'X11'
pythonlib = get_python_lib(plat_specific=1)
pythoninc = get_python_inc()
ver = get_python_version()
pythonver = 'python' + ver


PYRAF_DATA_FILES = ['data/blankcursor.xbm', 'data/epar.optionDB', 'data/pyraflogo_rgb_web.gif', 'lib/LICENSE.txt']

PYRAF_CLCACHE = glob.glob(os.path.join('data', 'clcache', '*'))


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



PYRAF_EXTENSIONS = [Extension('pyraf/sscanfmodule', ['src/sscanfmodule.c'],
                              include_dirs=add_inc_dirs),
                    Extension('pyraf/xutilmodule', ['src/xutil.c'],
                              include_dirs=add_inc_dirs,
                              library_dirs=add_lib_dirs,
                              libraries = [x_libraries])]


args = sys.argv[:]
for a in args:
    if a.startswith("--local="):
         """Adds a command line option --local=<install-dir> which is an abbreviation for
         'put all of pyraf in <install-dir>/pyraf'."""
         dir = os.path.abspath(a.split("=")[1])
         sys.argv.extend([
                "--install-lib="+dir,
                "--install-scripts=%s" % os.path.join(dir,"pyraf"),
                ])
         sys.argv.remove(a)
         args.remove(a)

    
PYRAF_CLCACHE_DIR = os.path.join('pyraf', 'clcache')
DATA_FILES = [('pyraf', PYRAF_DATA_FILES), (PYRAF_CLCACHE_DIR, PYRAF_CLCACHE)]

class smart_install_data(install_data):
    def run(self):
        #need to change self.install_dir to the library dir
        install_cmd = self.get_finalized_command('install')
        self.install_dir = getattr(install_cmd, 'install_lib')
        return install_data.run(self)


def dosetup():
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
              cmdclass = {'install_data':smart_install_data},
              data_files = DATA_FILES,
              scripts = ['lib/pyraf'],
              ext_modules = PYRAF_EXTENSIONS)
    
    return r


def main():
    args = sys.argv[2:]
    x_dir = ""
    for a in args:
        if a.startswith('--with-x='):
            x_dir = a.split("=")[1]
            sys.argv.remove(a)
    find_x(x_dir)
    dosetup()

if __name__ == "__main__":
    main()
