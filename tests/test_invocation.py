from __future__ import absolute_import

import subprocess
import sys

import pytest

import pyraf
from .utils import HAS_IRAF, HAS_PYRAF_EXEC

cl_cases = (
    (('print(1)'), '1'),
    (('print(1)'), '1'),
    (('print(1 + 2)'), '3'),
    (('print(6 - 1)'), '5'),
    (('print(14 / 2)'), '7'),
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


class PyrafEx(object):
    def __init__(self):
        self.code = 0
        self.stdout = None
        self.stderr = None

    def run(self, args, stdin=None):
        """Execute pyraf and store the relevant results
        """
        if isinstance(args, str):
            args = args.split()

        cmd = ['pyraf', '-x', '-s']
        cmd += args
        proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE, stdin=subprocess.PIPE)
        self.stdout, self.stderr = proc.communicate(stdin)

        if sys.hexversion >= 0x0300000F0:
            self.stdout = self.stdout.decode('ascii')
            self.stderr = self.stderr.decode('ascii')

        self.code = proc.returncode
        return self


@pytest.fixture
def _with_pyraf(tmpdir):
    return PyrafEx()


@pytest.mark.skipif((not HAS_PYRAF_EXEC) or (not HAS_IRAF),
                    reason='PyRAF and IRAF must be installed to run')
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


@pytest.mark.skipif((not HAS_PYRAF_EXEC) or (not HAS_IRAF),
                    reason='PyRAF and IRAF must be installed to run')
@pytest.mark.parametrize('test_input,expected', cl_cases)
def test_invoke_command(_with_pyraf, test_input, expected):
    """Issue basic commands to CL parser
    """
    result = _with_pyraf.run(['-c', test_input])
    assert result.stdout.startswith(expected)
    assert not result.stderr
    assert not result.code, result.stderr


@pytest.mark.skipif((not HAS_PYRAF_EXEC) or (not HAS_IRAF),
                    reason='PyRAF and IRAF must be installed to run')
@pytest.mark.parametrize('test_input,expected', cl_cases)
def test_invoke_command_direct(_with_pyraf, test_input, expected):
    """Issue basic commands on pyraf's native shell
    """
    result = _with_pyraf.run(['-s'], stdin=test_input+'\n.exit')
    assert result.stdout.strip().endswith(expected)
    #assert not result.stderr  # BUG: Why is there a single newline on stderr?
    assert not result.code, result.stderr


@pytest.mark.skipif((not HAS_PYRAF_EXEC) or (not HAS_IRAF),
                    reason='PyRAF and IRAF must be installed to run')
@pytest.mark.parametrize('test_input,expected', python_cases)
def test_invoke_command_no_wrapper_direct(_with_pyraf, test_input, expected):
    """Issue basic commands on pyraf's passthrough shell
    """
    result = _with_pyraf.run(['-i'], stdin=test_input)
    _output = result.stdout.strip()
    begin = _output.find('>>>')
    output = ''.join([x.replace('>>>', '').strip() for x in _output[begin:].splitlines()])

    assert output == expected
    assert not result.code, result.stderr


@pytest.mark.skipif((not HAS_PYRAF_EXEC) or (not HAS_IRAF),
                    reason='PyRAF and IRAF must be installed to run')
@pytest.mark.parametrize('test_input,expected', ipython_cases)
def test_invoke_command_ipython(_with_pyraf, test_input, expected):
    """Issue basic commands on pyraf's ipython shell wrapper
    """
    result = _with_pyraf.run('-y', stdin=test_input)
    assert expected in result.stdout
    assert not result.stderr
    assert not result.code, result.stderr
