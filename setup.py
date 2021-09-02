#! /usr/bin/env python3
import os
import platform

from setuptools import setup, Extension

modules = [Extension('pyraf.sscanf', ['pyraf/sscanfmodule.c'])]

# On a Mac, xutil is not required since the graphics is done directly with Aqua.
# If one still wants to include it, the parameters
#     library_dirs="/usr/X11/libs"
#     include_dirs="/usr/X11/include"
# need to be added to the Extension
if platform.system() not in ('Darwin', 'Windows'):
    modules.append(Extension('pyraf.xutil', ['pyraf/xutil.c'],
                             libraries=['X11']))

setup(ext_modules=modules,
      use_scm_version={'write_to': os.path.join('pyraf', 'version.py')})
