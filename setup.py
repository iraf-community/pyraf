#!/usr/bin/env python

try:
    from setuptools import setup
except ImportError:
    from distribute_setup import use_setuptools
    use_setuptools()
    from setuptools import setup

try:
    from stsci.distutils.command.easier_install import easier_install
except ImportError:
    import os
    import sys
    stsci_distutils = os.path.abspath(os.path.join('..', 'distutils', 'lib'))
    if os.path.exists(stsci_distutils) and stsci_distutils not in sys.path:
        sys.path.append(stsci_distutils)
    try:
        from stsci.distutils.command.easier_install import easier_install
        import setuptools.command.easy_install
    except ImportError:
        # If even this failed, we're not in an stsci_python source checkout,
        # so there's nothing gained from using easier_install
        from setuptools.command.easy_install import easy_install
        easier_install = easy_install
# This is required so that easier_install can be used for setup_requires
import setuptools
setuptools.command.easy_install.easy_install = easier_install

setup(
    setup_requires=['d2to1>=0.2.5', 'stsci.distutils==0.2'],
    d2to1=True,
    use_2to3=True,
    zip_safe=False
)
