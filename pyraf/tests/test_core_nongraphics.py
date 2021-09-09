"""These were tests under core/irafparlist and core/subproc in pandokia."""


import time
import uuid

import pytest

from .utils import HAS_IRAF

if HAS_IRAF:
    from ..irafpar import IrafParList
    from ..subproc import Subprocess
    from stsci.tools import basicpar
    from stsci.tools.basicpar import parFactory
else:
    pytestmark = pytest.mark.skip('IRAF must be installed to run')


@pytest.fixture
def _proc():
    return Subprocess('cat', expire_noisily=0)


def test_subproc_wait():
    proc = Subprocess('true', 1, expire_noisily=0)
    assert proc.wait(1), 'How is this still alive after 1 sec?'


def test_subproc_write_readline(_proc):
    """Buffer readback test; readline
    """
    _proc.write(b'test string one\n')
    _proc.write(b'test string two\n')
    time.sleep(0.01)

    assert _proc.readline() == b'test string one\n'
    assert _proc.readline() == b'test string two\n'


def test_subproc_write_readPendingChars(_proc):
    """Buffer readback test; readPendingChars
    """
    test_inputs = (b'one', b'two', b'three')
    for test_input in test_inputs:
        _proc.write(test_input + b'\n')
        time.sleep(0.01)

    expected = tuple(_proc.readPendingChars().splitlines())
    assert test_inputs == expected


def test_subproc_stop_resume(_proc):
    """Ensure we can stop and resume a process
    """
    assert _proc.stop()
    assert _proc.cont()


def test_subproc_stop_resume_write_read(_proc):
    """Ensure we can stop the process, write data to the pipe,
    resume, then read the buffered data back from the pipe.
    """
    assert _proc.stop()
    _proc.write(b'test string\n')
    assert not len(_proc.readPendingChars())
    assert _proc.cont()
    assert _proc.readline() == b'test string\n'


def test_subproc_kill_via_delete(_proc):
    """Kill the process by deleting the instance.
    We cannot assert anything, but an exception will bomb this out.
    """
    del _proc


def test_subproc_kill_via_die(_proc):
    """Kill the process the "right way."
    """
    assert _proc.pid is not None
    _proc.die()
    assert _proc.pid is None


@pytest.fixture
def _ipl_defaults(tmpdir):
    defaults = dict(name='bobs_pizza',
                    filename=str(tmpdir.join('bobs_pizza.par')))
    return defaults


@pytest.fixture
def _ipl(_ipl_defaults):
    """An IrafParList object
    """
    return IrafParList(_ipl_defaults['name'], _ipl_defaults['filename'])


@pytest.fixture
def _pars():
    values = (
        (('caller', 's', 'a', 'Ima Hungry', '', None, 'person calling Bobs'),
         True),
        (('diameter', 'i', 'a', '12', '', None, 'pizza size'), True),
        (('pi', 'r', 'a', '3.14159', '', None, 'Bob makes circles!'), True),
        (('delivery', 'b', 'a', 'yes', '', None, 'delivery? (or pickup)'),
         True),
        (('topping', 's', 'a', 'peps', '|toms|peps|olives', None,
          'the choices'), True),
    )
    return [parFactory(*x) for x in values]


def test_irafparlist_getName(_ipl, _ipl_defaults):
    assert _ipl.getName() == _ipl_defaults['name']


def test_irafparlist_getFilename(_ipl, _ipl_defaults):
    assert _ipl.getFilename() == _ipl_defaults['filename']


def test_irafparlist_getPkgname(_ipl, _ipl_defaults):
    assert not _ipl.getPkgname()


def test_irafparlist_hasPar_defaults(_ipl, _ipl_defaults):
    assert _ipl.hasPar('$nargs')
    assert _ipl.hasPar('mode')
    assert len(_ipl) == 2


def test_irafparlist_addParam_verify(_ipl, _pars):
    """Add a series of pars to _ipl while verifying
    the data can be read back as it appears.
    """
    for idx, par in enumerate(_pars, start=1):
        # Probably pointless.
        assert par.dpar().strip() == \
            f"{par.name} = {par.toString(par.value, quoted=1)}"
        # Add the paramater (+2 takes each par's default values into account)
        _ipl.addParam(par)
        assert len(_ipl) == idx + 2

        # Check that each par name exists in _ipl, plus defaults
        defaults = ['$nargs', 'mode']
        solution = sorted([x.name for x in _pars[:idx]] + defaults)
        assert sorted(_ipl.getAllMatches('')) == solution


def test_irafparlist_getAllMatches(_ipl, _pars):
    for par in _pars:
        _ipl.addParam(par)

    # Check that each par name exists in _ipl
    defaults = ['$nargs', 'mode']
    solution = sorted([x.name for x in _pars] + defaults)
    assert sorted(_ipl.getAllMatches('')) == solution


def test_irafparlist_getAllMatches_known_needle(_ipl, _pars):
    """Expect to receive a list of pars starting with needle
    """
    for par in _pars:
        _ipl.addParam(par)

    needle = 'd'
    # Verify the pars returned by getAllMatches(needle) are correct
    solution = sorted(
        str(x.name) for x in _pars if str(x.name).startswith(needle))
    assert sorted(_ipl.getAllMatches(needle)) == solution


def test_irafparlist_getAllMatches_unknown_needle(_ipl, _pars):
    """Expect to receive an empty list with no par match
    """
    for par in _pars:
        _ipl.addParam(par)

    needle = 'jojo'
    assert sorted(_ipl.getAllMatches(needle)) == list()


def test_irafparlist_getParDict(_ipl, _pars):
    for par in _pars:
        _ipl.addParam(par)

    par_dict = _ipl.getParDict()

    for par in _pars:
        assert par.name in par_dict


def test_irafparlist_getParList(_ipl, _pars):
    for par in _pars:
        _ipl.addParam(par)

    par_list = _ipl.getParList()

    for par in _pars:
        assert par in par_list


def test_irafparlist_hasPar(_ipl, _pars):
    for par in _pars:
        _ipl.addParam(par)

    for par in _pars:
        assert _ipl.hasPar(par.name)


def test_irafparlist_setParam_string(_ipl, _pars):
    """Change existing parameter then verify it
    """
    # Use the first string parameter we come across
    for par in _pars:
        if par.type == 's':
            assert isinstance(par, basicpar.IrafParS)
            break

    _ipl.addParam(par)
    _ipl.setParam(par.name, 'different value')
    assert 'different value' == _ipl.getParDict()[par.name].value


def test_irafparlist_setParam_integer(_ipl, _pars):
    """Change existing parameter then verify it
    """
    # Use the first integer parameter we come across
    for par in _pars:
        if par.type == 'i':
            assert isinstance(par, basicpar.IrafParI)
            break

    _ipl.addParam(par)

    new_value = par.value + 1
    _ipl.setParam(par.name, new_value)
    assert new_value == _ipl.getParDict()[par.name].value


def test_irafparlist_setParam_float(_ipl, _pars):
    """Change existing parameter then verify it
    """
    # Use the first integer parameter we come across
    for par in _pars:
        if par.type == 'r':
            assert isinstance(par, basicpar.IrafParR)
            break

    _ipl.addParam(par)

    new_value = par.value + 1.0
    _ipl.setParam(par.name, new_value)
    assert new_value == _ipl.getParDict()[par.name].value


@pytest.mark.xfail(reason='Can overwrite string type with uncast integer')
def test_irafparlist_incompatible_assignment_raises(_ipl, _pars):
    """Assign incompatible values to existing pars
    """
    bsint = uuid.uuid1().hex[:8]
    break_with = dict(
        s=int(bsint, 16),
        b=bsint,
        i=bsint,
        l=bsint,
        f=bsint,
        r=bsint,
    )

    for par in _pars:
        _ipl.addParam(par)

    for par in _pars:
        with pytest.raises(ValueError):
            setattr(_ipl, par.name, break_with[par.type])


def test_irafparlist_boolean_convert_false(_ipl, _pars):
    # Select first boolean par
    for par in _pars:
        if par.type == 'b':
            break

    _ipl.addParam(par)

    test_inputs = (False, 0, 'NO')
    for test_input in test_inputs:
        setattr(_ipl, par.name, test_input)
        assert getattr(_ipl, par.name) == 'no'


def test_irafparlist_boolean_convert_true(_ipl, _pars):
    # Select first boolean par
    for par in _pars:
        if par.type == 'b':
            break

    _ipl.addParam(par)

    test_inputs = (True, 1, 'YES')
    for test_input in test_inputs:
        setattr(_ipl, par.name, test_input)
        assert getattr(_ipl, par.name) == 'yes'
