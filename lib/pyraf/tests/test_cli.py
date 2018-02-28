"""These were tests under cli in pandokia."""
from __future__ import division

import os

import pytest
from astropy.utils.data import get_pkg_data_contents

try:
    from pyraf import iraf
    iraf.imhead("dev$pix")

    # Turn off the test probe output since it comes with
    # path info that is ever changing
    import pyraf
    pyraf.irafexecute.test_probe = False

except:  # Only this can catch the error!
    HAS_IRAF = False
else:
    HAS_IRAF = True


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_division(tmpdir):
    outfile = str(tmpdir.join('output.txt'))

    # First show straight Python
    case1 = 9 / 5
    case2 = 9 / 5.
    case3 = 9 // 5
    case4 = 9 // 5.
    iraf.printf('a: 9/5 ->   ' + str(case1) + '\n', StdoutAppend=outfile)
    iraf.printf('b: 9/5. ->  ' + str(case2) + '\n', StdoutAppend=outfile)
    iraf.printf('c: 9//5 ->  ' + str(case3) + '\n', StdoutAppend=outfile)
    iraf.printf('d: 9//5. -> ' + str(case4) + '\n', StdoutAppend=outfile)
    iraf.printf('\n', StdoutAppend=outfile)

    # Then show how a .cl script would be run
    iraf.task(xyz='print "e: " (9/5)\nprint "f: " (9/5.)\n'
              'print "g: " (9//5)\nprint "h: " (9//5.)', IsCmdString=1)
    iraf.xyz(StdoutAppend=outfile)
    iraf.printf('\n', StdoutAppend=outfile)

    # Then show how pyraf executes command-line instructions via cl2py
    iraf.clExecute('print "i: " (9/5)', StdoutAppend=outfile)
    iraf.clExecute('print "j: " (9/5.)', StdoutAppend=outfile)
    iraf.clExecute('print "k: " (9//5)', StdoutAppend=outfile)
    iraf.clExecute('print "l: " (9//5.)', StdoutAppend=outfile)

    # Quick step to strip whitespace from lines in output.
    # Much easier this way than messing with ancient comparator code.
    with open(outfile) as f_in:
        stripped = [l.replace('   ', ' ').replace('  ', ' ').strip()
                    for l in f_in.readlines()]

    # Read in the answer
    ans = get_pkg_data_contents('data/cli_div_output.ref').split(os.linesep)

    for x, y in zip(stripped, ans):
        assert x.strip(os.linesep) == y


def test_sscanf():
    pass


def test_whereis():
    pass


def test_which():
    pass
