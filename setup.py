#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup


setup(
    setup_requires=['d2to1>=0.2.6', 'stsci.distutils>=0.3'],
    dependency_links=['http://stsdas.stsci.edu/download/packages'],
    d2to1=True,
    use_2to3=True
)
