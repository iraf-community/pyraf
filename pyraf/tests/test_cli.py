"""These were tests under cli in pandokia."""
import io
from contextlib import contextmanager
import pytest

from .utils import HAS_IRAF

if HAS_IRAF:
    from .. import iraf
    from .. import pyrafglobals
    from .. import sscanf

    # Turn off the test probe output since it comes with
    # path info that is ever changing
    from .. import irafexecute
    irafexecute.test_probe = False


@contextmanager
def use_ecl(flag):
    """Temporary enable/disable usage of ECL"""
    # This is a quite dirty hack that is adjusted to do just enough to
    # let the tests here pass. It is not meant to be used outside.
    # Re-initialization of IRAF takes more that what is done here.
    if flag != pyrafglobals._use_ecl:
        old_ecl = pyrafglobals._use_ecl
        pyrafglobals._use_ecl = flag
        from .. import iraffunctions
        iraffunctions._pkgs.clear()
        iraffunctions._tasks.clear()
        iraf.Init(doprint=False, hush=True)
    yield
    if flag != pyrafglobals._use_ecl:
        pyrafglobals._use_ecl = old_ecl
        iraffunctions._pkgs.clear()
        iraffunctions._tasks.clear()
        iraf.Init(doprint=False, hush=True)


@pytest.mark.parametrize('ecl_flag', [False, True])
def test_division_task(ecl_flag, tmpdir):
    # Show how a .cl script would be run
    with use_ecl(ecl_flag):
        stdout = io.StringIO()
        iraf.task(xyz='print "e: " (9/5)\nprint "f: " (9/5.)\n'
                  'print "g: " (9//5)\nprint "h: " (9//5.)',
                  IsCmdString=True)
        iraf.xyz(StdoutAppend=stdout)
        assert stdout.getvalue() == "e: 1\nf: 1.8\ng: 95\nh: 95.0\n"


@pytest.mark.parametrize('arg,expected', [
    ('9/5', '1'),
    ('9/5.', '1.8'),
    ('9//5', '95'),     # string concatenation
    ('9//5.', '95.0'),  # string concatenation
])
@pytest.mark.parametrize('ecl_flag', [False, True])
def test_division(arg, expected, ecl_flag, tmpdir):
    with use_ecl(ecl_flag):
        stdout = io.StringIO()
        iraf.clExecute(f'print "i: " ({arg})', StdoutAppend=stdout)
        assert stdout.getvalue().strip() == f'i: {expected}'


@pytest.mark.parametrize('arg,fmt,expected', [
    ("seven 6 4.0 -7", "%s %d %g %d", ['seven', 6, 4.0, -7]), # aliveness
    ("seven", "%d", []),
    ("seven", "%c%3c%99c", ['s', 'eve', 'n']),
    ("0xabc90", "%x", [703632]),
])  
def test_sscanf(arg, fmt, expected, tmpdir):
    """A basic unit test that sscanf was built/imported correctly and
    can run.
    """
    l = sscanf.sscanf(arg, fmt)
    assert l == expected


def test_sscanf_error(tmpdir):
    # API error
    with pytest.raises(TypeError):
        sscanf.sscanf()


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.parametrize('arg,expected', [
    ("pw", "user.pwd"),
    ("lang", "clpackage.language"),
    ("st", "plot.stdplot plot.stdgraph user.strings imcoords.starfind"),
    ("std", "plot.stdplot plot.stdgraph"),
    ("stdg", "plot.stdgraph"),
    ("stdpl", "plot.stdplot"),
    ("star", "imcoords.starfind"),
    ("star man", "imcoords.starfind user.man"),
    ("vi", "tv.vimexam user.vi"),
    ("noao", "clpackage.noao"),
    ("impl", "plot.implot"),
    ("ls", "user.ls"),
    ("surf", "plot.surface noao.surfphot utilities.surfit"),
    ("surf man", "plot.surface noao.surfphot utilities.surfit user.man"),
    ("smart man", "user.man"),
    ("img", "imutil.imgets images.imgeom"),
    ("prot", "system.protect clpackage.proto"),
    ("pro", "plot.prows plot.prow system.protect clpackage.proto"),
    ("prow", "plot.prows plot.prow"),
    ("prows", "plot.prows"),
    ("prowss", None),
    ("dis", "tv.display system.diskspace"),
    ("no", "noao.nobsolete clpackage.noao"),
])
def test_whereis(arg, expected, tmpdir):
    iraf.plot(_doprint=0)
    iraf.images(_doprint=0)

    stdout = io.StringIO()
    args = arg.split(" ")  # convert to a list
    kw = {'StderrAppend': stdout}
    iraf.whereis(*args, **kw)  # catches stdout+err

    # Check that we get one line per argument
    assert len(stdout.getvalue().splitlines()) == len(args)

    # Check that each argument appears in the coresponding line
    for res, a in zip(stdout.getvalue().splitlines(), args):
        assert a in res

    # If task not found
    if expected is None:
        assert f"{arg}: task not found." in stdout.getvalue()
    else:
        # Check that all expected found places are returned
        for f in expected.split():
            assert f in stdout.getvalue()


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.parametrize('arg, expected', [
    ("pw", "user"),
    ("lang", "clpackage"),
    ("stdg", "plot"),
    ("stdp", "plot"),
    ("star", "imcoords"),
    ("star man", "imcoords\nuser"),
    ("vi", "user"),
    ("noao", "clpackage"),
    ("impl", "plot"),
    ("ls", "user"),
    ("surf", "\"Task `surf' is ambiguous, could be "
             "utilities.surfit, noao.surfphot, plot.surface\""),
    ("surface", "plot"),
    ("img", "\"Task `img' is ambiguous, could be "
            "images.imgeom, imutil.imgets\""),
    ("pro", "\"Task `pro' is ambiguous, could be "
            "clpackage.proto, system.protect, plot.prow, ...\""),
    ("prot", "\"Task `prot' is ambiguous, could be "
             "clpackage.proto, system.protect\""),
    ("prow", "plot"),
    ("prows", "plot"),
    ("prowss", "prowss: task not found."),
    ("dis", "\"Task `dis' is ambiguous, could be "
            "system.diskspace, tv.display\""),
])
def test_which(tmpdir, arg, expected):
    iraf.plot(_doprint=0)
    iraf.images(_doprint=0)

    # To Test: normal case, disambiguation, ambiguous, not found, multiple
    #          inputs for a single command

    stdout = io.StringIO()
    args = arg.split(" ")  # convert to a list
    kw = {"StderrAppend": stdout}
    iraf.which(*args, **kw)  # catches stdout+err
    assert stdout.getvalue().strip() == expected
