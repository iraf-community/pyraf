#! /usr/bin/env python3
import sys
import os

from setuptools import setup, Extension

IPYTHON_VERSION = ''
if sys.hexversion < 0x030000f0:
    IPYTHON_VERSION = '<6.0'

setup(install_requires=[
          'numpy', 'astropy', 'stsci.tools',
          'ipython{}'.format(IPYTHON_VERSION)
      ],
      ext_modules=[Extension('pyraf.sscanf', ['pyraf/sscanfmodule.c']),
                   Extension('pyraf.xutil', ['pyraf/xutil.c'],
                             libraries=['X11'])],
      use_scm_version={'write_to': os.path.join('pyraf', 'version.py')},
      )
