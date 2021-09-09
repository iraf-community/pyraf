import math
import os
from io import StringIO

import pytest

from .utils import HAS_STSDAS, HAS_IRAF, DATA_DIR

pytestmark = pytest.mark.skipif(not HAS_STSDAS, reason='Need STSDAS to run')

if HAS_IRAF:
    os.environ['PYRAF_NO_DISPLAY'] = '1'
    from pyraf import iraf


# --- Helpers ---
def _unlearn_egstp(egstp_obj):
    """Reset PSET egstp's values
    """
    egstp_obj.unlearn()
    egstp_obj.lParam()
    assert egstp_obj.npix == 0, str(egstp_obj.npix)
    assert egstp_obj.min == 0.0, str(egstp_obj.min)
    assert egstp_obj.max == 0.0, str(egstp_obj.max)
    assert egstp_obj.sum == 0.0, str(egstp_obj.sum)


def _assertApproxEqual(afloat, bfloat, tolerance=1.0e-12):
    if math.fabs(bfloat) > tolerance:
        ratiodiff = math.fabs(1.0 - math.fabs(afloat / (1.0 * bfloat)))
        assert ratiodiff < tolerance, \
            f'{afloat} != {bfloat}, radiodiff = {math.fabs(ratiodiff)}'
    else:
        diff = math.fabs(afloat - bfloat)
        assert diff < tolerance, \
            f'{afloat} != {bfloat}, diff = {math.fabs.diff}'


def _check_all_dqbits(the_dqbits_obj, valtup):
    """ Convenience method to check the 16 bitN values of dqbits """
    # converts to iraf yes and no's
    yes_no_map = {True: "iraf.yes", False: "iraf.no"}

    # check each one
    for i in range(16):
        expect_is_true = f'the_dqbits_obj.bit{i+1} == {yes_no_map[bool(valtup[i])]}'
        result = eval(expect_is_true)
        msg = f"Expected this to be True: {expect_is_true}"
        msg = msg.replace('the_dqbits_obj', 'dqbits')
        assert result, msg


# --- Fixtures ---
@pytest.fixture
def _data(tmpdir):
    inputs = dict(
        pset=dict(input1=os.path.join(DATA_DIR, 'pset_msstat_input.fits')),
        dqbits=dict(input1=str(tmpdir.join('dqbits_im1.fits')),
                    input2=str(tmpdir.join('dqbits_im2.fits')),
                    output=str(tmpdir.join('dqbits_out.fits'))))
    return inputs


@pytest.fixture(scope='function')
def _iraf_pset_init():
    """Initialize common IRAF tasks for pset tests
    """
    if not HAS_IRAF:
        return

    # imports & package loading
    iraf.stsdas(_doprint=0)
    iraf.imgtools(_doprint=0)
    iraf.mstools(_doprint=0)

    # reset PSET egstp's values
    _unlearn_egstp(iraf.egstp)


@pytest.fixture(scope='function')
def _iraf_dqbits_init(_data):
    """Initialize common IRAF tasks for dqbits tests
    """
    if not HAS_IRAF:
        return

    # imports & package loading
    iraf.stsdas(_doprint=0)
    iraf.imgtools(_doprint=0)
    iraf.artdata(_doprint=0)
    iraf.mstools(_doprint=0)

    # create two data files as input (dont care if appropriate to mscombine)
    iraf.imcopy('dev$pix', _data['dqbits']['input1'])
    iraf.imcopy('dev$pix', _data['dqbits']['input2'])


def test_task_min_match(_iraf_pset_init, _data):
    # Determine whether pyraf can use min-matching to resolve the task
    # (msstatistics -> msstat)
    #
    # Note:
    # iraf.task does not raise an exception if it fails due to invalid input to
    # the function. We're scanning stdout/err here as a stop gap measure.

    stdout, stderr = StringIO(), StringIO()
    iraf.msst(_data['pset']['input1'],
              arrays='science',
              clarray='science',
              StdoutAppend=stdout,
              StderrAppend=stderr)
    iraf.mssta(_data['pset']['input1'],
               arrays='science',
               clarray='science',
               StdoutAppend=stdout,
               StderrAppend=stderr)
    iraf.msstat(_data['pset']['input1'],
                arrays='science',
                clarray='science',
                StdoutAppend=stdout,
                StderrAppend=stderr)
    iraf.msstati(_data['pset']['input1'],
                 arrays='science',
                 clarray='science',
                 StdoutAppend=stdout,
                 StderrAppend=stderr)
    iraf.msstatis(_data['pset']['input1'],
                  arrays='science',
                  clarray='science',
                  StdoutAppend=stdout,
                  StderrAppend=stderr)
    iraf.msstatist(_data['pset']['input1'],
                   arrays='science',
                   clarray='science',
                   StdoutAppend=stdout,
                   StderrAppend=stderr)
    iraf.msstatisti(_data['pset']['input1'],
                    arrays='science',
                    clarray='science',
                    StdoutAppend=stdout,
                    StderrAppend=stderr)
    iraf.msstatistic(_data['pset']['input1'],
                     arrays='science',
                     clarray='science',
                     StdoutAppend=stdout,
                     StderrAppend=stderr)
    iraf.msstatistics(_data['pset']['input1'],
                      arrays='science',
                      clarray='science',
                      StdoutAppend=stdout,
                      StderrAppend=stderr)

    assert "ERROR" not in stdout.getvalue()
    assert not stderr.getvalue()


def test_task_ambiguous_name_raises_exception(_iraf_pset_init, _data):
    stdout, stderr = StringIO(), StringIO()

    with pytest.raises(AttributeError):
        iraf.m(_data['pset']['input1'],
               arrays='science',
               clarray='science',
               StdoutAppend=stdout,
               StderrAppend=stderr)

    with pytest.raises(AttributeError):
        iraf.ms(_data['pset']['input1'],
                arrays='science',
                clarray='science',
                StdoutAppend=stdout,
                StderrAppend=stderr)

    with pytest.raises(AttributeError):
        iraf.mss(_data['pset']['input1'],
                 arrays='science',
                 clarray='science',
                 StdoutAppend=stdout,
                 StderrAppend=stderr)


def test_pset_msstatistics_science_array(_iraf_pset_init, _data):
    """Expect decent data
    """
    # Run msstat, which sets egstp values.  Test PSET par passing to task
    # command function as a task top-level par passing msstat.nsstatpar.arrays
    # and msstat.nsstatpar.clarray, as if they were just msstat pars...
    #     arrays='science' (check "science" arrays only)
    #    clarray='science' (return data to egstp from final "error" array)
    # So, expect vals from second (final) science array.

    iraf.msstatistics(_data['pset']['input1'],
                      arrays='science',
                      clarray='science')
    iraf.egstp.lParam()

    assert iraf.egstp.npix == 277704, str(iraf.egstp.npix)
    _assertApproxEqual(iraf.egstp.min, 1116.0)
    _assertApproxEqual(iraf.egstp.max, 14022.0)
    _assertApproxEqual(iraf.egstp.sum, 321415936.0)


def test_pset_msstatistics_zeroed_error_array(_iraf_pset_init, _data):
    """Expect zeros
    """
    # Run and get data for retval from error arrays (which are empty)
    #     arrays='science' (check "science" arrays only)
    #    clarray='error'   (return data to egstp from final "error" array)
    # so, since the 'error' arrays are empty (and unchecked), expect all zeroes
    iraf.msstatistics(_data['pset']['input1'],
                      arrays='science',
                      clarray='error')
    iraf.egstp.lParam()

    assert iraf.egstp.npix == 0, str(iraf.egstp.npix)
    assert iraf.egstp.min == 0.0, str(iraf.egstp.min)
    assert iraf.egstp.max == 0.0, str(iraf.egstp.max)
    assert iraf.egstp.sum == 0.0, str(iraf.egstp.sum)


def test_pset_msstatistics_191(_iraf_pset_init, _data):
    """Expect egstp to be properly cleared and used again
    NOTE: Referenced issue, 191, is no longer available (trac).
    """
    # Regression test to make sure a task can be sent an unadorned PSET
    # par as a regular function argument (without scope/PSET name given).
    # This regression-tests #191.

    # repeat first call to msstat, verify correct results and that we did
    # not hit anything which exists due to previous calls
    iraf.msstat(_data['pset']['input1'], arrays='science', clarray='science')
    iraf.egstp.lParam()

    assert iraf.egstp.npix == 277704, str(iraf.egstp.npix)
    _assertApproxEqual(iraf.egstp.min, 1116.0)
    _assertApproxEqual(iraf.egstp.max, 14022.0)
    _assertApproxEqual(iraf.egstp.sum, 321415936.0)

    _unlearn_egstp(iraf.egstp)
    iraf.msstatistics(_data['pset']['input1'],
                      arrays='science',
                      clarray='error')
    iraf.egstp.lParam()

    assert iraf.egstp.npix == 0, str(iraf.egstp.npix)
    assert iraf.egstp.min == 0.0, str(iraf.egstp.min)
    assert iraf.egstp.max == 0.0, str(iraf.egstp.max)
    assert iraf.egstp.sum == 0.0, str(iraf.egstp.sum)

    _unlearn_egstp(iraf.egstp)
    iraf.msstat(_data['pset']['input1'], arrays='science', clarray='science')
    iraf.egstp.lParam()

    assert iraf.egstp.npix == 277704, str(iraf.egstp.npix)
    _assertApproxEqual(iraf.egstp.min, 1116.0)
    _assertApproxEqual(iraf.egstp.max, 14022.0)
    _assertApproxEqual(iraf.egstp.sum, 321415936.0)


def test_pset_msstatistics_save_data(_iraf_pset_init, _data):
    """Expect a task can save data into a PSET
    """
    # run msstat, which sets egstp values
    # check PSET egstp's values
    iraf.msstatistics('dev$pix')
    iraf.egstp.lParam()
    assert iraf.egstp.npix == 262144, str(iraf.egstp.npix)
    assert iraf.egstp.min == -1.0, str(iraf.egstp.min)
    assert iraf.egstp.max == 19936.0, str(iraf.egstp.max)
    assert iraf.egstp.sum == 28394234.0, str(iraf.egstp.sum)

    # reset PSET egstp's values
    _unlearn_egstp(iraf.egstp)
    iraf.egstp.lParam()
    assert iraf.egstp.npix == 0, str(iraf.egstp.npix)
    assert iraf.egstp.min == 0.0, str(iraf.egstp.min)
    assert iraf.egstp.max == 0.0, str(iraf.egstp.max)
    assert iraf.egstp.sum == 0.0, str(iraf.egstp.sum)

    # run msstat again
    iraf.msstatistics('dev$pix')

    # recheck PSET egstp's values
    iraf.egstp.lParam()
    assert iraf.egstp.npix == 262144, str(iraf.egstp.npix)
    assert iraf.egstp.min == -1.0, str(iraf.egstp.min)
    assert iraf.egstp.max == 19936.0, str(iraf.egstp.max)
    assert iraf.egstp.sum == 28394234.0, str(iraf.egstp.sum)


def test_dqbits_mscombine(_iraf_dqbits_init, _data, tmpdir):
    """Expect dqbits unaltered after combining data
    """
    # reset PSET dqbits' values
    iraf.dqbits.unlearn()
    _check_all_dqbits(iraf.dqbits,
                      (0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0, 0))
    iraf.dqbits.lParam()

    # now set PSET dqbits' values to a non-default set
    iraf.dqbits.bit2 = iraf.dqbits.bit4 = iraf.dqbits.bit6 = iraf.dqbits.bit8 = iraf.yes
    _check_all_dqbits(iraf.dqbits,
                      (0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0))
    iraf.dqbits.lParam()

    # run mscombine to see what is does with the dqbit pars (shouldn't alter)
    inputs = ','.join([_data['dqbits']['input1'], _data['dqbits']['input2']])
    output = _data['dqbits']['output']
    iraf.mscombine(inputs, output)

    # now, check the PSET - should be unaltered (fixed by #207)
    iraf.dqbits.lParam()
    _check_all_dqbits(iraf.dqbits,
                      (0, 1, 0, 1, 0, 1, 0, 1, 0, 0, 0, 0, 0, 0, 0, 0))
