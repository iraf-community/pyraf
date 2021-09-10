"""
Few simple tests based on

Preliminary Test Procedure for IRAF, IRAF Version V2.11, Jeannette Barnes,
Central Computer Services, National Optical Astronomy Observatories,
P.O. Box 26732, Tucson, AZ 85726, Revised September 23, 1997.

These tests are in no mean complete; they shall just test the
interaction between Pyraf and IRAF.

"""

import io
import os

import pytest
from astropy.io import fits

from .utils import HAS_IRAF

if HAS_IRAF:
    from pyraf import iraf
else:
    pytestmark = pytest.mark.skip('Need IRAF to run')


def teardown_module(self):
    files_to_del = [
        'image.real.fits', 'image.dbl.fits', 'image.short.fits'
    ]
    for fname in files_to_del:
        if os.path.exists(fname):
            os.remove(fname)

def test_imcopy():
    iraf.imcopy('dev$pix', 'image.short', verbose=False)
    with fits.open('image.short.fits') as f:
        assert len(f) == 1
        assert f[0].header['BITPIX'] == 16
        assert (f[0].header['ORIGIN'] ==
                'NOAO-IRAF FITS Image Kernel July 2003')
        assert f[0].data.shape == (512, 512)


def test_imhead():
    out = io.StringIO()
    iraf.imhead('dev$pix', Stdout=out)
    assert out.getvalue() == 'dev$pix[512,512][short]: m51  B  600s\n'


def test_imarith():
    iraf.imarith('dev$pix', '/', '1', 'image.real', pixtype='r')
    with fits.open('image.real.fits') as f:
        assert f[0].header['BITPIX'] == -32
        assert f[0].data.shape == (512, 512)
    iraf.imarith('dev$pix', '/', '1', 'image.dbl', pixtype='d')
    with fits.open('image.dbl.fits') as f:
        assert f[0].header['BITPIX'] == -64
        assert f[0].data.shape == (512, 512)


def test_hedit():
    if os.path.exists('image.real.fits'):
        os.remove('image.real.fits')

    iraf.imarith('dev$pix', '/', '1', 'image.real', pixtype='r')
    iraf.hedit('image.real',
               'title',
               'm51 real',
               verify=False,
               Stdout="/dev/null")
    with fits.open('image.real.fits') as f:
        assert f[0].header['OBJECT'] == 'm51 real'

