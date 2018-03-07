import os
import sys

from astropy.utils.data import get_pkg_data_contents

IS_PY2 = sys.version_info < (3, 0)

try:
    from pyraf import iraf
    iraf.imhead("dev$pix")
except:  # Only this can catch the error!
    HAS_IRAF = False
else:
    HAS_IRAF = True


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
            all_bad_lines.append('{} : {}'.format(x, y))

    if len(all_bad_lines) > 0:
        raise AssertionError(os.linesep.join(all_bad_lines))
