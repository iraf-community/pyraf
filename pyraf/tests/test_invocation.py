import sys
import subprocess

import pytest

import pyraf
from .utils import HAS_IRAF

pytestmark = pytest.mark.skipif(not HAS_IRAF,
                                reason='IRAF must be installed to run')

HAS_IPYTHON = True
try:
    import IPython
except ImportError:
    HAS_IPYTHON = False

cl_cases = (
    (('print(1)'), '1'),
    (('print(1)'), '1'),
    (('print(1 + 2)'), '3'),
    (('print(6 - 1)'), '5'),
    (('print(14 / 3))'), '4'),
    (('print(3 * 3)'), '9'),
    (('imhead("dev$pix")'), 'dev$pix[512,512][short]: m51  B  600s'),
    (('unlearn imcoords'), ''),
    (('bye'), ''),
)

ipython_cases = (
    ('print("ipython test")', 'In [1]: ipython test'),
    ('s = "hello world";s', 'Out[1]: \'hello world\''),
)

python_cases = (
    ('print("ipython test")', 'ipython test'),
    ('s = "hello world";s', '\'hello world\''),
)


class PyrafEx:
    def __init__(self):
        self.code = 0
        self.stdout = None
        self.stderr = None

    def run(self, args, stdin=None, silent=True, use_ecl=False):
        """Execute pyraf and store the relevant results
        """
        if isinstance(args, str):
            args = args.split()

        cmd = [sys.executable, '-m', 'pyraf', '-x']
        if silent:
            cmd += ['-s']
        if use_ecl:
            cmd += ['-e']
        cmd += args
        proc = subprocess.Popen(cmd,
                                stdout=subprocess.PIPE,
                                stderr=subprocess.PIPE,
                                stdin=subprocess.PIPE)

        if stdin is not None:
            stdin = stdin.encode('ascii')

        self.stdout, self.stderr = proc.communicate(stdin)

        self.stdout = self.stdout.decode('ascii')
        self.stderr = self.stderr.decode('ascii')

        self.code = proc.returncode
        return self


@pytest.fixture
def _with_pyraf(tmpdir):
    return PyrafEx()


@pytest.mark.parametrize('test_input', [
    ('--version'),
    ('-V'),
])
def test_invoke_version(_with_pyraf, test_input):
    """Ensure version reported by command-line options originates in __version__
    """
    result = _with_pyraf.run(test_input)
    assert not result.code
    assert pyraf.__version__ in result.stdout


@pytest.mark.parametrize('test_input,expected', cl_cases)
@pytest.mark.parametrize('use_ecl', [False, True])
def test_invoke_command(_with_pyraf, test_input, expected, use_ecl):
    """Issue basic commands to CL parser
    """
    result = _with_pyraf.run(['-c', test_input], use_ecl=use_ecl)
    assert result.stdout.startswith(expected)
    assert not result.code, result.stderr


@pytest.mark.parametrize('test_input,expected', cl_cases)
@pytest.mark.parametrize('use_ecl', [False, True])
def test_invoke_command_direct(_with_pyraf, test_input, expected, use_ecl):
    """Issue basic commands on pyraf's native shell
    """
    if '/' in test_input:
        pytest.xfail('Integer division is different as the Python 3 '
                     'parser is used here')
    result = _with_pyraf.run(['-m'], use_ecl=use_ecl,
                             stdin=test_input + '\n.exit')
    assert result.stdout.strip().endswith(expected)
    # assert not result.stderr  # BUG: Why is there a single newline on stderr?
    assert not result.code, result.stderr


@pytest.mark.parametrize('test_input,expected', python_cases)
@pytest.mark.parametrize('use_ecl', [False, True])
def test_invoke_command_no_wrapper_direct(_with_pyraf, test_input, expected, use_ecl):
    """Issue basic commands on pyraf's passthrough shell
    """
    result = _with_pyraf.run(['-i'], use_ecl=use_ecl, stdin=test_input)
    _output = result.stdout.strip()
    begin = _output.find('>>>')
    output = ''.join(
        [x.replace('>>>', '').strip() for x in _output[begin:].splitlines()])

    assert output == expected
    assert not result.code, result.stderr


@pytest.mark.skipif(not HAS_IPYTHON,
                    reason='IPython must be installed to run')
@pytest.mark.parametrize('test_input,expected', ipython_cases)
@pytest.mark.parametrize('use_ecl', [False, True])
def test_invoke_command_ipython(_with_pyraf, test_input, expected, use_ecl):
    """Issue basic commands on pyraf's ipython shell wrapper
    """
    result = _with_pyraf.run('-y', use_ecl=use_ecl, stdin=test_input)
    assert expected in result.stdout
    assert not result.code, result.stderr


@pytest.mark.parametrize('test_input', [
    '--commandwrapper',
    '--no-commandwrapper',
    '--ipython',
])
def test_invoke_nosilent(_with_pyraf, test_input):
    """Ensure full invocation is somehow verbose
    """
    if test_input in ('--ipython', '-y') and not HAS_IPYTHON:
        pytest.skip('IPython must be installed to run')
    result = _with_pyraf.run(test_input, silent=False)
    assert not result.code
    assert "Welcome to IRAF." in result.stdout
    assert "clpackage" in result.stdout
    assert f"PyRAF {pyraf.__version__}" in result.stdout
