"""These were tests under cli in pandokia."""
from __future__ import absolute_import, division

import pytest

from .utils import diff_outputs, HAS_IRAF

if HAS_IRAF:
    from pyraf import iraf

    try:
        from pyraf import sscanf  # C-extension
    except ImportError:
        sscanf = None

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
    """A basic unit test that sscanf was built/imported correctly and
    can run.
    """
    assert sscanf is not None, \
        'Error importing sscanf during iraffunctions init'

    # aliveness
    l = sscanf.sscanf("seven 6 4.0 -7", "%s %d %g %d")
    assert l == ['seven', 6, 4.0, -7]

    # bad format
    l = sscanf.sscanf("seven", "%d")
    assert l == []

    # %c
    l = sscanf.sscanf("seven", "%c%3c%99c")
    assert l == ['s', 'eve', 'n']

    # hex
    l = sscanf.sscanf("0xabc90", "%x")
    assert l == [703632]

    # API error
    with pytest.raises(TypeError):
        sscanf.sscanf()


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

    with open(outfile) as f:
        for line in f:
            if 'task not found' in line:
                continue

            row = line.split()
            if line.startswith('-->'):
                cmd = row[2]
                if len(row) > 3:
                    cmd2 = row[3]
            elif row[0] == 'user.man' and cmd2 == 'man':
                pass
            else:
                assert all([s.split('.')[1].startswith(cmd) for s in row]), \
                    '{}'.format(row)


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
