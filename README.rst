=====
PyRAF
=====

|Release| |CI Status| |Coverage Status| |Documentation|

PyRAF is a command language for running IRAF tasks in a Python like
environment. It works very similar to IRAF, but has been updated to
allow such things as importing Python modules, starting in any
directory, GUI parameter editing and help. Most importantly, it can be
imported into Python allowing you to run IRAF commands from within a
larger script.

Installation
------------

To install PyRAF, it is required to have both IRAF_ and Python_
already installed. For the IRAF installation, both a self-compiled and
a binary IRAF package (f.e. in Ubuntu_) will work.

The IRAF installation should have a properly configured environment,
especially the ``iraf`` environment variable must be set to point to
the IRAF installation directory (i.e. to ``/usr/lib/iraf/`` on Ubuntu
or Debian systems). On multi-arch IRAF installations, the ``IRAFARCH``
environment variable should specify the architecture to use. This is
usually already set during the IRAF installation procedure.

The minimal Python required for PyRAF is 3.6, but it is recommended to
use the latest available version. An installation in an virtual
environment like venv_ or conda_ is possible.

The package can be installed from PyPI_ with the command ``pip3
install pyraf``. Note that if no binary installation is available on
PyPI, the package requires a compilation, so aside from pip3, the C
compiler and development libraries (on Linux ``libx11-dev``) should be
installed.

Contributing Code, Documentation, or Feedback
---------------------------------------------

IRAF and PyRAF can only survive by the contribution of its users, so
we welcome and encourage your contributions. The preferred way to
report a bug is to create a new issue on the `PyRAF GitHub
issue <https://github.com/iraf-community/pyraf/issues>`_ page.  To
contribute patches, we suggest to create a `pull request on
GitHub <https://github.com/iraf-community/pyraf/pulls>`_.

License
-------

PyRAF is licensed under a 3-clause BSD style license - see the
`LICENSE.txt <LICENSE.txt>`_ file.

Documentation
-------------

* `The PyRAF Tutorial <https://pyraf.readthedocs.io>`_


.. |CI Status| image:: https://github.com/iraf-community/pyraf/actions/workflows/citest.yml/badge.svg
    :target: https://github.com/iraf-community/pyraf/actions
    :alt: Pyraf CI Status

.. |Coverage Status| image:: https://codecov.io/gh/iraf-community/pyraf/branch/main/graph/badge.svg
    :target: https://codecov.io/gh/iraf-community/pyraf
    :alt: PyRAF Coverage Status
	  
.. |Release| image:: https://img.shields.io/github/release/iraf-community/pyraf.svg
    :target: https://github.com/iraf-community/pyraf/releases/latest
    :alt: Pyraf release

.. |Documentation| image:: https://readthedocs.org/projects/pyraf/badge/?version=latest
    :target: https://pyraf.readthedocs.io/en/latest/
    :alt: Documentation Status

.. _Python: https://www.python.org/

.. _venv: https://docs.python.org/3/library/venv.html

.. _conda: https://docs.conda.io/

.. _PyPI: https://pypi.org/project/pyraf

.. _IRAF: https://iraf-community.github.io

.. _iraf-community: https://iraf-community.github.io

.. _Ubuntu: https://www.ubuntu.com/
