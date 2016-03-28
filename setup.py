#!/usr/bin/env python
import recon.release
from glob import glob
from numpy import get_include as np_include
from setuptools import setup, find_packages, Extension


version = recon.release.get_info()
recon.release.write_template(version, 'lib/pyraf')

setup(
    name = 'pyraf',
    version = version.pep386,
    author = 'Rick White, Perry Greenfield, Chris Sontag',
    author_email = 'help@stsci.edu',
    description = 'Provides a Pythonic interface to IRAF that can be used in place of the existing IRAF CL',
    url = 'https://github.com/spacetelescope/pyraf',
    classifiers = [
        'Intended Audience :: Science/Research',
        'License :: OSI Approved :: BSD License',
        'Operating System :: OS Independent',
        'Programming Language :: Python',
        'Topic :: Scientific/Engineering :: Astronomy',
        'Topic :: Software Development :: Libraries :: Python Modules',
    ],
    install_requires = [
        'astropy',
        'nose',
        'numpy',
        'scipy',
        'sphinx',
    ],

    package_dir = {
        '':'lib'
    },
    packages = find_packages('lib'),
    package_data = {
        'pyraf': [
            'data/*',
        ]
    },
    scripts=[
        'scripts/*'
    ],
    ext_modules=[
        Extension('pyraf.sscanfmodule',
            ['src/sscanfmodule.c'],
            optional=True,
            fail_message='If this is Windows, it is ok.'),

        Extension('pyraf.xutilmodule',
            ['src/xutil.c'],
            libraries=['X11']),
    ],
)
