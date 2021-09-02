#! /usr/bin/env python3
import os

from setuptools import setup, Extension

setup(ext_modules=[Extension('pyraf.sscanf', ['pyraf/sscanfmodule.c']),
                   Extension('pyraf.xutil', ['pyraf/xutil.c'],
                             libraries=['X11'])],
      use_scm_version={'write_to': os.path.join('pyraf', 'version.py')},
      )
