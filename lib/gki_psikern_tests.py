"""
GKI PyRAF-to-psikern tests

The first version of this will be under-representative of the total
functionality, but tests will be added over time, as code issues are
researched and addressed.

$Id: gki_psikern_tests.py 801 2007-08-2 sontag $
"""

import glob, os, sys
from pyraf import iraf


def gki_single_prow_test():
   """ Test a prow-plot of a single row from dev$pix to .ps """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = glob.glob(os.environ['tmp']+os.sep+'psk*')
   # plot
   iraf.prow("dev$pix", row=256, dev="psi_land") # plot
   iraf.gflush()
   # get output postscript temp file name
   psOut = getNewestTmpPskFile(flistBef)
   # diff
   cmd = "diff -I '.*CreationDate: .*' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+"prow_256.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_prow_1_append_test():
   """ Test a prow-plot with 1 append (2 rows total, dev$pix) to .ps """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = glob.glob(os.environ['tmp']+os.sep+'psk*')
   # plot
   iraf.prow("dev$pix", row=256, dev="psi_land") # plot
   iraf.prow("dev$pix", row=250, dev="psi_land", append=True) # append #1
   iraf.gflush()
   # get output postscript temp file name
   psOut = getNewestTmpPskFile(flistBef)
   # diff
   cmd = "diff -I '.*CreationDate: .*' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+"prow_256_250.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_prow_2_appends_test():
   """ Test a prow-plot with 2 appends (3 rows total, dev$pix) to .ps """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = glob.glob(os.environ['tmp']+os.sep+'psk*')
   # plot
   iraf.prow("dev$pix", row=256, dev="psi_land") # plot
   iraf.prow("dev$pix", row=250, dev="psi_land", append=True) # append #1
   iraf.prow("dev$pix", row=200, dev="psi_land", append=True) # append #1
   iraf.gflush()
   # get output postscript temp file name
   psOut = getNewestTmpPskFile(flistBef)
   # diff
   cmd = "diff -I '.*CreationDate: .*' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+"prow_256_250_200.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_2_prows_no_append_test():
   """ Test 2 prow calls with no append (2 dev$pix rows) to 2 .ps's """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = glob.glob(os.environ['tmp']+os.sep+'psk*')
   # plot
   iraf.prow("dev$pix", row=256, dev="psi_land") # plot
   iraf.prow("dev$pix", row=250, dev="psi_land") # plot again (flushes 1st)
   # get output postscript temp file name
   psOut = getNewestTmpPskFile(flistBef)
   # diff
   cmd = "diff -I '.*CreationDate: .*' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+"prow_256.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   os.remove(psOut)
   # NOW flush second
   flistBef = glob.glob(os.environ['tmp']+os.sep+'psk*')
   iraf.gflush()
   # get output postscript temp file name
   psOut = getNewestTmpPskFile(flistBef)
   # diff
   cmd = "diff -I '.*CreationDate: .*' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+"prow_250.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_prow_to_different_devices_test():
   """ Test 2 prow calls, each to different devices - one .ps written """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = glob.glob(os.environ['tmp']+os.sep+'psk*')
   # use a fake printer name so we don't waste a sheet of paper w/ each test
   os.environ['LPDEST'] = "hp_dev_null"
   # plot
   iraf.prow("dev$pix", row=256, dev="psi_land") # plot (no .ps file yet)
   iraf.prow("dev$pix", row=250, dev="lw") # plot to fake printer, should flush
                                           # last plot, and should warn @ fake
   # get output postscript temp file name
   psOut = getNewestTmpPskFile(flistBef)
   # diff
   cmd = "diff -I '.*CreationDate: .*' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+"prow_256.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)
   # NOW flush - should do nothing
   flistBef = glob.glob(os.environ['tmp']+os.sep+'psk*')
   iraf.gflush()
   flistAft = glob.glob(os.environ['tmp']+os.sep+'psk*')
   assert flistBef==flistAft, "Extra tmp .ps file written? "+repr(flistAft)


def getNewestTmpPskFile(theBeforeList):
   """ Do a glob in the tmp dir looking for psikern files, compare with the
   old list to find the single new (expected) file. Return string filename. """
   flistAft = glob.glob(os.environ['tmp']+os.sep+'psk*')
   for f in theBeforeList: flistAft.remove(f)
   assert len(flistAft) == 1, "Expected single postcript file: "+repr(flistAft)
   return flistAft[0]


if __name__ == "__main__":
   """ This main is not necessary for testing via nose, but it was handy
   in development. """
   import gki_psikern_tests
   junk = gki_psikern_tests.__dict__.keys()
   mthds = [j for j in junk if j.find("_test")>0]
   for m in mthds:
      print "Running test: "+m
      eval(m)
