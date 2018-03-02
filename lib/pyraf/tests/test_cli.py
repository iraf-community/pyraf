"""These were tests under cli in pandokia."""
from __future__ import absolute_import, division

import sys
import traceback

import pytest

from .utils import diff_outputs, HAS_IRAF

if HAS_IRAF:
    from pyraf import iraf

    # Turn off the test probe output since it comes with
    # path info that is ever changing
    import pyraf
    pyraf.irafexecute.test_probe = False


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

    diff_outputs(stripped, 'data/cli_div_output.ref')


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_sscanf(tmpdir):
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    outfile = str(tmpdir.join('output.txt'))

    try:
        with open(outfile, 'w') as f:
            sys.stdout = sys.stderr = f  # redirect all output

            # simple test of iraf.printf
            # (assume MUST have at least that working)
            iraf.printf('About to import sscanf and test it\n')
            from pyraf import iraffunctions  # noqa
            iraffunctions.test_sscanf()  # prints to stdout
    except:
        sys.stdout = old_stdout
        raise IOError(traceback.format_exc())
    finally:
        sys.stdout = old_stdout
        sys.stderr = old_stderr

    diff_outputs(outfile, 'data/cli_sscanf_output.ref')


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_whereis(tmpdir):
    iraf.plot(_doprint=0)
    iraf.images(_doprint=0)
    outfile = str(tmpdir.join('output.txt'))

    cases = ("pw", "lang", "st", "std", "stdg", "stdpl", "star", "star man",
             "vi", "noao", "impl", "ls", "surf", "surf man", "smart man",
             "img", "prot", "pro", "prow", "prows", "prowss", "dis", "no")

    # Test the whereis function
    for arg in cases:
        args = arg.split(" ")  # convert to a list
        iraf.printf("--> whereis " + arg + '\n', StdoutAppend=outfile)
        kw = {'StderrAppend': outfile}
        iraf.whereis(*args, **kw)  # catches stdout+err

    diff_outputs(outfile, 'data/cli_whereis_output.ref')


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_which(tmpdir):
    iraf.plot(_doprint=0)
    iraf.images(_doprint=0)
    outfile = str(tmpdir.join('output.txt'))

    # To Test: normal case, disambiguation, ambiguous, not found, multiple
    #          inputs for a single command
    cases = ("pw", "lang", "stdg", "stdp", "star", "star man", "vi", "noao",
             "impl", "ls", "surf", "surface", "img", "pro", "prot", "prow",
             "prows", "prowss", "dis")

    # Test the which function
    for arg in cases:
        args = arg.split(" ")  # convert to a list
        iraf.printf("--> which " + arg + '\n', StdoutAppend=outfile)
        kw = {"StderrAppend": outfile}
        iraf.which(*args, **kw)  # catches stdout+err

    diff_outputs(outfile, 'data/cli_which_output.ref')
