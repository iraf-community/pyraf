import os
import sys

import pytest
import six

from .utils import IS_PY2, HAS_IRAF

if HAS_IRAF:
    from pyraf import wutil

REF = {}


def setup_module():
    global REF

    # first turn off display
    os.environ['PYRAF_NO_DISPLAY'] = '1'

    # EXPECTED RESULTS
    REF[('2', 'linux')] = """python ver = 2.7
platform = linux2
PY3K = False
c.OF_GRAPHICS = False
/dev/console owner = <skipped>
tkinter use unattempted.
"""
    REF[('2', 'darwin')] = REF[('2', 'linux')].replace('linux2', 'darwin')

    REF[('3', 'linux')] = """python ver = 3.5
platform = linux
PY3K = True
c.OF_GRAPHICS = False
/dev/console owner = <skipped>
tkinter use unattempted.
"""
    REF[('3', 'darwin')] = REF[('3', 'linux')].replace('linux', 'darwin')


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_dumpspecs():
    # get dumpspecs output
    out_f = six.StringIO()
    wutil.dumpspecs(outstream=out_f, skip_volatiles=True)
    out_str = out_f.getvalue()
    out_f.close()

    # modify out_str to remove a path that will always be changing
    out_str = '\n'.join([l for l in out_str.split('\n')
                         if 'python exec =' not in l])
    # modify out_str to handle old versions which printed Tkinter as camel-case
    out_str = out_str.replace('Tkinter', 'tkinter')

    # verify it (is version dependent)
    key = ('2' if IS_PY2 else '3', sys.platform.replace('2', ''))
    expected = REF[key]
    assert expected.strip() == out_str.strip(), \
        'Unexpected output from wutil.dumpspecs: {}'.format(out_str)
