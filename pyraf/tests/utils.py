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


def diff_outputs(fin, reffile):
    """Compare output lines with reference file."""
    if isinstance(fin, list):
        lines = fin
    else:
        with open(fin) as f:
            lines = f.readlines()

    ans = get_pkg_data_contents(reffile).split(os.linesep)
    all_bad_lines = []

    for x, y in zip(lines, ans):
        if x.strip(os.linesep) != y:
            all_bad_lines.append(f'{x} : {y}')

    if len(all_bad_lines) > 0:
        raise AssertionError(os.linesep.join(all_bad_lines))
