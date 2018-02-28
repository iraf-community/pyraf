import unittest

from io import StringIO
import os
import sys
import tempfile


wd = os.getenv('ADTTMP')
if not wd:
    wd = tempfile.mkdtemp()

os.chdir(wd)
open('.hushiraf', 'a').close()

from stsci.tools import capable
capable.OF_GRAPHICS = False
from pyraf import iraf
from astropy.io import fits


class TestPyraf(unittest.TestCase):
    '''Few simple tests based on
    
    Preliminary Test Procedure for IRAF, IRAF Version V2.11, Jeannette Barnes,
    Central Computer Services, National Optical Astronomy Observatories,
    P.O. Box 26732, Tucson, AZ 85726, Revised September 23, 1997.

    These tests are in no mean complete; they shall just test the
    interaction between Pyraf and IRAF.
    '''

    def setUp(self):
        os.chdir(wd)
    
    def test_imcopy(self):
        iraf.imcopy('dev$pix', 'image.short', verbose=False)
        with fits.open('image.short.fits') as f:
            self.assertEqual(len(f), 1)
            self.assertEqual(f[0].header['BITPIX'], 16)
            self.assertEqual(f[0].header['ORIGIN'],
                             'NOAO-IRAF FITS Image Kernel July 2003')
            self.assertEqual(f[0].data.shape, (512, 512))

    @unittest.skipIf(sys.version_info < (3,0),
                     'see https://github.com/spacetelescope/pyraf/issues/41')
    def test_imhead(self):
        out = StringIO()
        iraf.imhead('dev$pix', Stdout=out)
        self.assertEqual(out.getvalue(),
                         'dev$pix[512,512][short]: m51  B  600s\n')

    def test_imarith(self):
        iraf.imarith('dev$pix', '/', '1', 'image.real', pixtype='r')
        with fits.open('image.real.fits') as f:
            self.assertEqual(f[0].header['BITPIX'], -32)
            self.assertEqual(f[0].data.shape, (512, 512))
        iraf.imarith('dev$pix', '/', '1', 'image.dbl', pixtype='d')
        with fits.open('image.dbl.fits') as f:
            self.assertEqual(f[0].header['BITPIX'], -64)
            self.assertEqual(f[0].data.shape, (512, 512))

    def test_hedit(self):
        iraf.imarith('dev$pix', '/', '1', 'image.real', pixtype='r')
        iraf.hedit('image.real', 'title', 'm51 real', verify=False,
                   Stdout="/dev/null")
        with fits.open('image.real.fits') as f:
            self.assertEqual(f[0].header['OBJECT'], 'm51 real')
            
    def tearDown(self):
        if os.path.exists('image.real.fits'):
            os.remove('image.real.fits')
        if os.path.exists('image.double.fits'):
            os.remove('image.double.fits')
        if os.path.exists('image.short.fits'):
            os.remove('image.short.fits')
        
if __name__ == '__main__':
    unittest.main()
