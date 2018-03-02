#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

setup(
    setup_requires=['d2to1>=0.2.3', 'stsci.distutils>=0.3.2'],
    install_requires=['numpy', 'astropy', 'stsci.tools'],
    tests_require=['pytest', 'six'],
    package_dir={'pyraf.tests': 'lib/pyraf/tests'},
    package_data={'pyraf.tests': ['data/*.*']},
    d2to1=True,
    use_2to3=True,
    zip_safe=False
)
