import os
import sys

from astropy.utils.data import get_pkg_data_contents
from distutils.spawn import find_executable

DATA_DIR = os.path.join(os.path.dirname(__file__), 'data')

try:
    from pyraf import iraf
    iraf.imhead("dev$pix", Stdout=os.devnull, Stderr=os.devnull)
except (iraf.IrafError, AttributeError):
    HAS_IRAF = False
    HAS_STSDAS = False
else:
    HAS_IRAF = True
    try:
        iraf.stsdas(_doprint=0)
    except (iraf.IrafError, AttributeError):
        HAS_STSDAS = False
    else:
        HAS_STSDAS = True
