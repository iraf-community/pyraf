"""These were tests under cli in pandokia."""
import io
import math
from contextlib import contextmanager, redirect_stderr
import pytest

from .utils import HAS_IRAF

from .. import iraf
from .. import scanf
from .. import pyrafglobals


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
def test_division_task(ecl_flag):
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
def test_division(arg, expected, ecl_flag):
    with use_ecl(ecl_flag):
        stdout = io.StringIO()
        iraf.clExecute(f'print "i: " ({arg})', StdoutAppend=stdout)
        assert stdout.getvalue().strip() == f'i: {expected}'



@pytest.mark.parametrize('fmt,arg,expected', [
    # ===== Basic / aliveness =====
    ("%s %d %g %d", "seven 6 4.0 -7", ['seven', 6, 4.0, -7]),

    # ===== %c (character) =====
    ("%c", "a", ['a',]),
    ("%c", "x", ['x',]),
    ("%c", " ", [' ',]),
    ("%c", "123", ['1',]),
    ("%c%c%c", "abc", ['a', 'b', 'c']),
    ("%3c", "seven", ['sev',]),
    ("%1c", "seven", ['s',]),
    ("%99c", "seven", ['seven',]),
    ("%c%3c%99c", "seven", ['s', 'eve', 'n']),
    ("%c%2c", "a bcde", ['a', ' b']),
    ("%2c%2c", "ab cd", ['ab', ' c']),
    ("%3c%3c", "ab ", ['ab ',]),   # first %3c consumes all 3 chars; second absent -> single item

    # ===== %s (string of non-whitespace) =====
    ("%s", "hello", ['hello',]),
    ("%s %s", "hello world", ['hello', 'world']),
    ("%s", "  hello", ['hello',]),
    ("%s %s", "  hello  world  ", ['hello', 'world']),
    ("%3s", "hello", ['hel',]),
    ("%5s", "hello", ['hello',]),
    ("%10s", "hello", ['hello',]),
    ("%5s %5s", "hello world", ['hello', 'world']),
    ("%s%s", "one two three", ['one', 'two']),   # subsequent tokens remain unparsed
    ("%s%s", "hello world", ['hello', 'world']),
    ("%s%s%s", "one two three", ['one', 'two', 'three']),

    # %s failing when no non-whitespace -> no assigned items (empty tuple)
    ("%s", " ", []),
    ("%s", "", []),

    # ===== %d (signed integer) =====
    ("%d", "123", [123,]),
    ("%d", "0", [0,]),
    ("%d", "-42", [-42,]),
    ("%d", "+99", [99,]),
    ("%d", "  42", [42,]),
    ("%d %d %d", "1 2 3", [1, 2, 3]),
    ("%d %d", "0 75", [0, 75]),
    ("%2d%2d", "1234", [12, 34]),
    ("%3d%3d", "123456", [123, 456]),
    ("%1d", "42", [4,]),
    ("%d", "42", [42,]),
    ("%ld", "999", [999,]),
    ("%ld", "12345", [12345,]),
    ("%3ld", "789", [789,]),

    # ===== Floating (%f, %g, %e) =====
    ("%f", "3.25", [3.25,]),
    ("%f", ".5", [0.5]),
    ("%f", "+.5", [0.5]),
    ("%g", "0.5", [0.5,]),
    ("%e", "1.5625e-2", [1.5625e-2,]),
    ("%f", "-2.5", [-2.5,]),
    ("%g", "+1.0", [1.0,]),
    ("%f", "  4.0", [4.0,]),
    ("%g", "4.0", [4.0,]),
    ("%f %f %f", "1.0 2.5 3.25", [1.0, 2.5, 3.25]),
    ("%e", "1e10", [1e10,]),
    ("%g", "3.125E-2", [3.125E-2,]),
    ("%e", "-3.2768e+4", [-3.2768e+4,]),
    ("%f", "42", [42.0,]),
    ("%g", "42.", [42.0,]),
    ("%g", "123", [123.0,]),

    # ===== %x (hexadecimal) =====
    ("%x", "abc90", [0xabc90,]),
    ("%x", "ABC90", [0xABC90,]),
    ("%x", "FF", [0xFF,]),
    ("%x", "-FF", [-0xFF,]),
    ("%x", "0", [0,]),
    ("%x", "  1a2b", [0x1a2b,]),
    ("%x %x %x", "abc 123 def", [0xabc, 0x123, 0xdef]),
    ("%3x", "abcdef", [0xabc,]),
    ("%2x", "1234", [0x12,]),
    # %x with optional 0x prefix and optional sign is accepted by C extension
    ("%x", "0x0", [0,]),
    ("%lx", "DEADBEEF", [0xDEADBEEF,]),

    # ===== %o (octal) =====
    ("%o", "177", [0o177,]),
    ("%o", "-755", [-0o755,]),
    ("%o", "0", [0,]),
    ("%o", "  377", [0o377,]),
    ("%o %o %o", "123 456 777", [0o123, 0o456, 0o777]),
    ("%x %o", "abc90 177", [0xabc90, 0o177]),
    ("%3o", "12345", [0o123,]),
    ("%2o", "777", [0o77,]),
    ("%lo", "7777777777", [0o7777777777,]),

    # ===== %[... ] (character scan set) =====
    ("%[sev]", "seven", ['seve',]),
    ("%[abc]", "abcdef", ['abc',]),
    ("%[aeiou]", "hello", []),            # input begins at 'h' -> not in set -> conversion fails -> ()
    ("%[^aeiou]%[aeiou]", "hello", ['h', 'e']),  # negated + positive scanset
    ("%*[^aeiou]%[aeiou]", "hello", ['e',]),
    ("%[a-z]", "abcXYZ", ['abc',]),

    # ===== Skipping fields (%*) =====
    ("%s %*d %s", "hello 42 world", ['hello', 'world']),
    ("%s %*s %s", "foo bar baz", ['foo', 'baz']),
    ("%f %*f %f", "1.0 2.5 3.0", [1.0, 3.0]),
    ("%c %*d %c %*d %c", "a 1 b 2 c", ['a', 'b', 'c']),
    ("%*d", "123", []),                        # suppressed assignment -> no items appended -> empty result
    ("%*3c%3c", "abcdef", ['def',]),
    ("%*3s%s", "foobar", ['bar',]),

    # ===== Whitespace handling =====
    ("%s %s", "hello   world", ['hello', 'world']),
    ("%d %d %d", "1     2     3", [1, 2, 3]),
    ("%s %s", "hello\tworld", ['hello', 'world']),
    ("%d %d", "42\t99", [42, 99]),
    ("%s", "  hello  ", ['hello',]),
    ("%d", "  42  ", [42,]),
    ("%f", "  3.25  ", [3.25,]),

    # ===== Partial matches (incomplete conversions / failures) =====
    ("%d", "seven", []),                        # first conversion fails -> no assignments -> ()
    ("%d", "", []),                             # empty input -> no assignments
    ("%d%d", "1 2x3", [1, 2]),                  # third fails -> partial (1,2)
    ("%d %d", "42 x", [42,]),                   # second fails -> partial (42,)
    ("%d-%d", "42 -x", [42,]),                  # literal present then conversion fails -> partial (42,)
    ("%d%d", "123", [123,]),                    # second missing -> partial (123,)
    ("%s%d%d", "a 1 x", ['a', 1]),              # third fails -> partial first two
    ("%d%d", "a12", []),                        # first fails -> no assignments -> ()
    ("%d %s", "x hello", []),                   # first fails -> ()
    ("%2d%2d", "12 ", [12,]),                   # second has no digits -> partial (12,)
    ("%3c%3c", "abc", ['abc',]),                # second missing -> partial ('abc',)
    ("%3c%3c", "ab ", ['ab ',]),                # first consumed all available chars -> partial ('ab ',)
    ("%s%d", "   123", ['123',]),               # %s consumes digits -> second has nothing -> partial ('123',)
    ("%d %d", "42", [42,]),                     # missing second -> partial (42,)
    ("%d %d", "", []),
    ("%s %d", "    ", []),

    # ===== Literal matching & edge cases =====
    ("%d (int)", "42 (int)", [42,]),
    ("result: %f", "result:  3.25", [3.25,]),
    ("%s world", "hello world", ['hello',]),
    ("%s world", "hello  world", ['hello',]),
    ("%% %d", "% 42", [42,]),                   # literal '%' then %d
    ("%s   -   %d", "a - 1", ['a', 1]),
    ("ID:%d", "ID: 10", [10,]),
    ("foo%dbar", "foo 7 bar", [7,]),
    ("%%%d%%", "%42%", [42]),
    ("foo", "foo", []),
    ("foo", "bar", []),

    # ===== Mixed conversions / realistic combos =====
    ("%s %d %s %f", "John 25 Engineer 75000.50", ['John', 25, 'Engineer', 75000.50]),
    ("ID: 0x%x version: %f", "ID: 0x1A2B version: 2.5", [0x1A2B, 2.5]),  # %x accepts 0x prefix in C ext
    ("count: %d status: %2s", "count: 100 status: OK", [100, 'OK']),
    ("%d %f %s %x", "1 2.5 three F", [1, 2.5, 'three', 0xF]),
    ("%o %x %g", "0755 ABC 3.25", [0o755, 0xABC, 3.25]),

    # ===== Sign handling =====
    ("%d", "-123", [-123,]),
    ("%d", "+456", [456,]),
    ("%f", "-3.25", [-3.25,]),
    ("%g", "+2.5", [2.5,]),
    ("%x", "-AB", [-0xAB,]),                 # C extension accepts sign for hex conversion

    # ===== Special & zero cases =====
    ("%d", "0", [0,]),
    ("%f", "0.0", [0.0,]),
    ("%x", "0x0", [0,]),
    ("%o", "0o0", [0,]),                       # note: here %o expects octal digits "0o0" -> C's %o expects "0" or digits 0-7;
                                               # using "0o0" would parse leading '0' then stop at 'o' -> results (0,)
                                               # included here for parity with user expectations -> C behavior is (0,)
    ("%e", "1e0", [1.0,]),

    # ===== Width specification combinations =====
    ("%1d%2d%3d%3d", "123456789", [1, 23, 456, 789]),
    ("%1s%2s%3s%2s", "abcdefgh", ['a', 'bc', 'def', 'gh']),

    # ===== Concatenated formats with whitespace in input =====
    ("%d%d", "1 2", [1, 2]),
    ("%d%d", "1\t2", [1, 2]),
    ("%s%s", "hello world", ['hello', 'world']),
    ("%s%d", "abc 123", ['abc', 123]),
    ("%s%d", "abc   123", ['abc', 123]),
    ("%c%c", "a b", ['a', ' ']),
    ("%s%s%s", "one two three", ['one', 'two', 'three']),

    # ===== Additional partial-match focused cases =====
    ("%d%d%d", "1 2x3", [1, 2]),
    ("%d%d", "123", [123,]),
    ("%d-%d", "42 -x", [42,]),
    ("%d %d", "42 x", [42,]),
    ("%s%d%d", "a 1 x", ['a', 1]),
    ("%2d%2d", "12 ", [12,]),
    ("%3c%3c", "ab ", ['ab ',]),
    ("%s%d", "   123", ['123',]),
    ("%d", "", []),
    ("%s", "", []),

    # === More tests found in real scripts ======
    ("%s%s", "a b", ["a","b"]),
    ("%*d %d", "12 34", [34,]),
    ("%f %f %d %s", "1.25 -0.5 10 Dinsdale!", [1.25, -0.5, 10, 'Dinsdale!']),
    ("%f", "-5e-1", [-0.5,]),
    ("%2d:%2d:%2d", "12:34:56", [12, 34, 56]),
])
def test_scanf(fmt, arg, expected):
    """A basic unit test that sscanf was built/imported correctly and
    can run.
    """
    assert scanf.scanf(fmt, arg) == expected


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
def test_whereis(arg, expected):
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
def test_which(arg, expected):
    iraf.plot(_doprint=0)
    iraf.images(_doprint=0)

    # To Test: normal case, disambiguation, ambiguous, not found, multiple
    #          inputs for a single command

    stdout = io.StringIO()
    args = arg.split(" ")  # convert to a list
    kw = {"StderrAppend": stdout}
    iraf.which(*args, **kw)  # catches stdout+err
    actual_lines = stdout.getvalue().strip().splitlines()
    expected_lines = expected.splitlines()
    assert len(actual_lines) == len(expected_lines)
    for arg, actual_line, expected_line in zip(args, actual_lines,
                                               expected_lines):
        if 'ambiguous' in actual_line:
            if 'ambiguous' in expected_line:
                assert actual_line.startswith(expected_line.rstrip('"'))
            else:
                assert f'{expected_line}.{arg}' in actual_line
        else:
            assert actual_line == expected_line


def test_parse_cl_array_subscripts():
    # Check that square brackets are parsed correctly
    # https://github.com/iraf-community/pyraf/issues/115
    stdout = io.StringIO()
    iraf.task(xyz='char cenwavvalue[4]\n'
              'cenwavvalue[1] = "580"\n'
              'print(cenwavvalue[1])',
              IsCmdString=True)
    iraf.xyz(StdoutAppend=stdout)
    assert stdout.getvalue() == "580\n"


@pytest.mark.parametrize('call, expected', [
    ('acos(0.67)', math.acos(0.67)),
    ('asin(0.67)', math.asin(0.67)),
    ('atan2(2.,3.)', math.atan2(2.,3.)),
    ('cos(1.2)', math.cos(1.2)),
    ('dacos(0.67)', math.degrees(math.acos(0.67))),
    ('dasin(0.67)', math.degrees(math.asin(0.67))),
    ('datan2(2.,3.)', math.degrees(math.atan2(2.,3.))),
    ('dcos(12.)', math.cos(math.radians(12.))),
    ('deg(1.2)', math.degrees(1.2)),
    ('dsin(12.)', math.sin(math.radians(12.))),
    ('dtan(12.)', math.tan(math.radians(12.))),
    ('exp(1.2)', math.exp(1.2)),
    ('frac(1.2)', 1.2 % 1),
    ('hypot(2.,3.)', math.hypot(2.,3.)),
    ('int(-1.2)', int(-1.2)),
    ('isindef(0)', False),
    ('isindef(INDEF)', True),
    ('log(1.2)', math.log(1.2)),
    ('log10(1.2)', math.log10(1.2)),
    ('max(2,3,4,2)', max(2,3,4,2)),
    ('min(2,3,4,2)', min(2,3,4,2)),
    ('mod(123, 7)', 123 % 7),
    ('nint(1.5)', 2),
    ('nint(2.5)', 3),
    ('rad(12)', math.radians(12)),
    ('radix(123, 10)', '123'),
    ('radix(123, 16)', '7B'),
    ('radix(-123, 10)', '4294967173'),
    ('radix(-123, 16)', 'FFFFFF85'),
    ('real("1.23")', 1.23),
    ('sign(-1.2)', -1),
    ('sign(1.2)', 1),
    ('sin(1.2)', math.sin(1.2)),
    ('sqrt(1.2)', math.sqrt(1.2)),
    ('stridx("fd", "abcdefg")', 4),
    ('strldx("fd", "abcdefg")', 6),
    ('strlen("abcdefg")', 7),
    ('strlstr("def", "abcdefg")', 4),
    ('strlwr("aBcDeF")', "abcdef"),
    ('strstr("def", "abcdefg")', 4),
    ('strupr("aBcDeF")', "ABCDEF"),
    ('substr("abcdefg", 2, 5)', "bcde"),
    ('tan(1.2)', math.tan(1.2)),
    ('trim("--abcdefg---", "-")', "abcdefg"),
    ('triml("--abcdefg---", "-")', "abcdefg---"),
    ('trimr("--abcdefg---", "-")', "--abcdefg"),
    ])
def test_intrinsic_functions(call, expected):
    with redirect_stderr(io.StringIO()):  # silence task redefinition warnings
        iraf.task(xyz=f'print({call})', IsCmdString=True)
    stdout = io.StringIO()
    iraf.xyz(Stdout=stdout)
    if isinstance(expected, float):
        assert float(stdout.getvalue().strip()) == pytest.approx(expected, 1e-8)
    elif isinstance(expected, int):
        assert int(stdout.getvalue().strip()) == expected
    else:
        assert stdout.getvalue().strip() == expected


@pytest.mark.parametrize('ecl_flag', [False, True])
@pytest.mark.parametrize('encoding', ['utf-8', 'iso-8859-1'])
@pytest.mark.parametrize('code,expected', [
    ('print AA #  Ångström\n', 'AA\n'),
    ('print("test") | cat', 'test\n'),
])
def test_clfile(tmpdir, ecl_flag, encoding, code, expected):
    # Check proper reading of CL files with different encodings
    fname = tmpdir / 'cltestfile.cl'
    with fname.open("w", encoding=encoding) as fp:
        fp.write(code)

    stdout = io.StringIO()

    with use_ecl(ecl_flag):
        iraf.task(xyz=str(fname))
        iraf.xyz(StdoutAppend=stdout)
        assert stdout.getvalue() == expected


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.parametrize('ecl_flag', [False, True])
@pytest.mark.parametrize('code', [
    'cat {datafile}',                     # foreign
    'type {datafile} map_cc=no',          # internal
    'concatenate {datafile} out_type=t',  # system
])
@pytest.mark.parametrize('data', [
    b'test for plain ASCII',
    'Unicode Ångström'.encode('utf-8'),
    b'\x8fq\x96\x7f\xe6\xfd\xf8\x12\xb03{U\x81\x11\x014',  # some random data
])
@pytest.mark.parametrize('redir_stdin', [False, True])
@pytest.mark.parametrize('redir_stdout', [False, True])
def test_redir_data(tmpdir, ecl_flag, code, data, redir_stdin, redir_stdout):
    datafile = tmpdir / 'cltestdata.dat'
    with datafile.open('wb') as fp:
        fp.write(data)
    if redir_stdin:
        code = code.format(datafile='') + f' < {str(datafile)}'
    else:
        code = code.format(datafile=str(datafile))

    if redir_stdout:
        outfile = tmpdir / 'cltestoutput.dat'
        code += f' > {str(outfile)}'

    with use_ecl(ecl_flag):
        iraf.task(xyz=code, IsCmdString=True)
        stdout = io.TextIOWrapper(io.BytesIO())  # Emulate a "real" stdout
        iraf.xyz(Stdout=stdout)

    if redir_stdout:
        with open(outfile, 'rb') as fp:
            assert fp.read() == data
    else:
        assert stdout.buffer.getvalue() == data


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_binary_stdout(tmpdir):
    # Test writing binary data to STDOUT, one of several issues mentioned in
    # https://github.com/iraf-community/pyraf/issues/117
    outfile = str(tmpdir / 'testout.gki')
    expected = [
        f"METAFILE '{outfile}':",
        '[1] (2855 words) The SINC Function',
        '[2] (5701 words) .2',
        '[3] (2525 words) Line 250 of dev$pix[200:300,*]',
        '[4] (7637 words) Log Scaling',
        '[5] (97781 words) NOAO/IRAF V2.3 tody@lyra Fri 23:30:27 08-Aug-86',
        '[6] (2501 words) The Sinc Function'
    ]
    iraf.gkiextract('dev$vdm.gki', '2-7', iraf.yes, verify=False,
                    Stdout=outfile)
    stdout = io.StringIO()
    iraf.gkidir(outfile, Stdout=stdout)
    # Require gkidir output to match list above, ignoring spacing:
    assert [' '.join(line.split())
            for line in stdout.getvalue().splitlines() if line] == expected

def test_real_parameter_str_precision():
    # Check that PyRAF uses the same precision for real parameters on Python 3
    # as on 2 (see https://github.com/iraf-community/pyraf/issues/127)
    iraf.task(
        print_real='''procedure print_real(value)
                      real value
                      begin
                          print(value)
                      end''',
        IsCmdString=True
    )
    stdout = io.StringIO()
    iraf.print_real(1.2345678901234567, Stdout=stdout)
    assert stdout.getvalue() == "1.23456789012\n"
    stdout = io.StringIO()
    iraf.print_real(1000000000000000.0, Stdout=stdout)
    assert stdout.getvalue() == "1e+15\n"
