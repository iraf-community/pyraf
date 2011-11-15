"""
GKI PyRAF-to-psikern tests

The first version of this will be under-representative of the total
functionality, but tests will be added over time, as code issues are
researched and addressed.

$Id$
"""
from __future__ import division # confidence high

import glob, os, sys, time
from pyraf import iraf

diff = "diff"
if 'PYRAF_TEST_DIFF' in os.environ:
   diff = os.environ['PYRAF_TEST_DIFF']

PSDEV = EXP2IGNORE = None

def gki_single_prow_test():
   """ Test a prow-plot of a single row from dev$pix to .ps """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = findAllTmpPskFiles()
   # plot
   iraf.prow("dev$pix", row=256, dev=PSDEV) # plot
   iraf.gflush()
   # get output postscript temp file name
   psOut = getNewTmpPskFile(flistBef, "single_prow")
   # diff
   cmd = diff+" -I '"+EXP2IGNORE+"' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+PSDEV+"_prow_256.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_prow_1_append_test():
   """ Test a prow-plot with 1 append (2 rows total, dev$pix) to .ps """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = findAllTmpPskFiles()
   # plot
   iraf.prow("dev$pix", row=256, dev=PSDEV) # plot
   iraf.prow("dev$pix", row=250, dev=PSDEV, append=True) # append #1
   iraf.gflush()
   # get output postscript temp file name
   psOut = getNewTmpPskFile(flistBef, "prow_1_append")
   # diff
   cmd = diff+" -I '"+EXP2IGNORE+"' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+PSDEV+"_prow_256_250.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_prow_2_appends_test():
   """ Test a prow-plot with 2 appends (3 rows total, dev$pix) to .ps """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = findAllTmpPskFiles()
   # plot
   iraf.prow("dev$pix", row=256, dev=PSDEV) # plot
   iraf.prow("dev$pix", row=250, dev=PSDEV, append=True) # append #1
   iraf.prow("dev$pix", row=200, dev=PSDEV, append=True) # append #1
   iraf.gflush()
   # get output postscript temp file name
   psOut = getNewTmpPskFile(flistBef, "prow_2_appends")
   # diff
   cmd = diff+" -I '"+EXP2IGNORE+"' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+PSDEV+"_prow_256_250_200.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_2_prows_no_append_test():
   """ Test 2 prow calls with no append (2 dev$pix rows) to 2 .ps's """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = findAllTmpPskFiles()
   # plot
   iraf.prow("dev$pix", row=256, dev=PSDEV) # plot
   iraf.prow("dev$pix", row=250, dev=PSDEV) # plot again (flushes 1st)
   # get output postscript temp file name
   prf = None
   if os.uname()[0] == 'SunOS': prf = '.eps' # Solaris can leave extras here
   psOut = getNewTmpPskFile(flistBef, "2_prows_no_append - A", preferred=prf)
   # diff
   cmd = diff+" -I '"+EXP2IGNORE+"' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+PSDEV+"_prow_256.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   os.remove(psOut)
   # NOW flush second
   flistBef = findAllTmpPskFiles()
   iraf.gflush()
   # get output postscript temp file name
   prf = None
   if os.uname()[0] == 'SunOS': prf = '.eps' # Solaris can leave extras here
   psOut = getNewTmpPskFile(flistBef, "2_prows_no_append - B", preferred=prf)
   # diff
   cmd = diff+" -I '"+EXP2IGNORE+"' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+PSDEV+"_prow_250.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)


def gki_prow_to_different_devices_test():
   """ Test 2 prow calls, each to different devices - one .ps written """
   iraf.plot(_doprint=0) # load plot for prow
   # get look at tmp dir before plot/flush
   flistBef = findAllTmpPskFiles()
   # use a fake printer name so we don't waste a sheet of paper with each test
   os.environ['LPDEST'] = "hp_dev_null"
   # plot
   iraf.prow("dev$pix", row=256, dev=PSDEV) # plot (no .ps file yet)
   iraf.prow("dev$pix", row=250, dev="lw") # plot to fake printer, should flush
                                           # last plot, and should warn @ fake
   # get output postscript temp file name
   psOut = getNewTmpPskFile(flistBef, "prow_to_different_devices")
   # diff
   cmd = diff+" -I '"+EXP2IGNORE+"' "+os.environ['PYRAF_TEST_DATA']+ \
         os.sep+PSDEV+"_prow_256.ps "+psOut
   assert 0==os.system(cmd), "Diff of postscript failed!  Command = "+cmd
   # clean up
   os.remove(psOut)
   # NOW flush - should do nothing
   flistBef = findAllTmpPskFiles()
   iraf.gflush()
   flistAft = findAllTmpPskFiles()
   assert flistBef==flistAft, "Extra tmp .ps file written? "+str(flistAft)


def findAllTmpPskFiles():
   """ Do a glob in the tmp dir (and cwd) looking for psikern files.
   Return the list. """
   # Usually the files are dropped in the $tmp directory
   if PSDEV.find('dump') >= 0:
       flistCur = glob.glob('/tmp/irafdmp*') # always in /tmp
   else:
       flistCur = glob.glob(os.environ['tmp']+os.sep+'psk*')
   # sometimes the tmp files disappear on Solaris
   if sys.platform=='sunos5':
       time.sleep(1)
       for f in flistCur:
           os.system("/bin/ls -ld "+f)
           if not os.path.exists(f):
               print "This existed then did not: "+f
               flistCur.remove(f)
   # for some reason, on Solaris (at least), some files are dumped to cwd
   if PSDEV.find('dump') >= 0:
       flistCur += glob.glob(os.getcwd()+os.sep+'irafdmp*')
   else:
       flistCur += glob.glob(os.getcwd()+os.sep+'psk*')
   return flistCur


def getNewTmpPskFile(theBeforeList, title, preferred=None):
   """ Do a glob in the tmp dir looking for psikern files, compare with the
   old list to find the new (expected) file.  If preferred is None, then only
   a single new file is expected.  If not None, then we assume that more than
   one new file may be present, and the arg is used as a search substring
   (regexp would be cooler) to choose which single file to return of the newly
   found set. Returns a single string filename. """

   flistAft = findAllTmpPskFiles()
   assert len(flistAft) > len(theBeforeList), \
          'No postcript file(s) generated during: "'+title+'": '+ \
          str(theBeforeList)+' : looking in: '+os.environ['tmp']
   for f in theBeforeList: flistAft.remove(f)
   if preferred == None:
       # In this case, we expect only a single ps file.
       if len(flistAft) != 1:
           # But, if there are two+ (sometimes occurs on Solaris), and one
           # is in /tmp and another is a local .eps, let's debug it a bit.
           if len(flistAft) >= 2 and flistAft[0].find('/tmp/') == 0 and \
              flistAft[-1].find('.eps') > 0:
               # Are these files related (copies?)
               print "Debugging multiple postscript files scenario"
               for f in flistAft: os.system("/bin/ls -ld "+f)
               # Or, did the /tmp version suddenly get deleted?
               if not os.path.exists(flistAft[0]):
                   print "Am somehow missing the deletes.  Test: "+title
                   return flistAft[-1]
           # Either way, throw something
           raise Exception('Expected single postcript file during: "'+ \
                           title+'": '+str(flistAft))
   else:
       # Here we allow more than one, and return the preferred option.
       for f in flistAft:
           if f.find(preferred) >= 0: return f

   return flistAft[0]


def run_all():
   global PSDEV, EXP2IGNORE
   tsts = [x for x in globals().keys() if x.find('test')>=0]
   ran = 0

   PSDEV = 'psi_land'
   EXP2IGNORE = '.*CreationDate: .*'
   for t in tsts:
      func = eval(t)
      print PSDEV, ':', func.__doc__.strip()
      func()
      ran += 1

#   PSDEV = 'psdump'
#   EXP2IGNORE = '(NOAO/IRAF '
#   for t in tsts:
#      func = eval(t)
#      print PSDEV, ':', func.__doc__.strip()
#      func()
#      ran += 1

   # If we get here with no exception, we have passed all of the tests
   print "\nSuccessfully passed "+str(ran)+" tests"
   return ran


#
#
if __name__ == "__main__":
   """ This main is not necessary for testing via nose, but it was handy
   in development. """
   run_all()
