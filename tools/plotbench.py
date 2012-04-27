#!/usr/bin/env python
#
# Come up with some PyRAF plotting benchmarks.  Created for the performance
# tests necessary for #122.  This compares the default Tk kernel to all other
# choices.  Feel free to add test cases!
#
# This will take over your screen while it is running, popping the mouse and
# the focus back and forth, so be prepared.
#
# $Id$
#
from __future__ import division # confidence high

from pyraf import iraf, gki
import os, time, random

# note that box, plus, and cross take about the same amount of time.
CASES=(None, 'point', 'box', 'plus', 'cross', 'circle')
#ASES=(None, 'point', 'box',                  'circle')


def manyPoints(task, pkind):
   """ Plot a bunch of points, return the time it took (s). """

   assert task in ('prow','graph','surface','contour'), \
          "Unexpected task: "+str(task)
   assert pkind in (None, 'point','box','plus','cross','circle'), \
          'Unknown: '+str(pkind)

   # plot 10 rows.  in dev$pix this is 5120 pts
   start = time.time()

   if task == 'prow':
      apd = False
      for row in range(150, 331, 20):
         if pkind == None:
            iraf.prow('dev$pix', row, wy2=400, append=apd, pointmode=False)
         else:
            iraf.prow('dev$pix', row, wy2=400, append=apd, pointmode=True, marker=pkind)
         apd = True
   elif task == 'graph':
      tstr = ''
      for row in range(150, 331, 20):
         tstr += 'dev$pix[*,'+str(row)+'],'
      tstr = tstr[:-1] # rm final comma
      if pkind == None:
         iraf.graph(tstr, wy2=400, pointmode=False, ltypes='1')
      else:
         iraf.graph(tstr, wy2=400, pointmode=True, marker=pkind)
   elif task == 'contour':
         iraf.contour("dev$pix", Stdout='/dev/null')
   elif task == 'surface':
         iraf.surface("dev$pix", Stdout='/dev/null')
   else:
       raise Exception("How did we get here?")

   delay = time.time() - start

   # clear out kernel memory explicitly
   time.sleep(2)
   gki.kernel.clear()
   return delay


def runAllCases(suiteName, resDict):
   """ run through unique test cases; allow caller to change major things
   like the graphics kernel, etc """

   # we reset gki to pick up the current graphics kernel of choice
   # we also close the graphics window and then throw away the first plot
   print ("\n"+suiteName+":")
   gki._resetGraphicsKernel()

   for mo in ('graph','prow','surface','contour'):
      did = 0
      # duplicate the first plot since it will be tossed.
      for test in CASES[:1]+CASES:
         secs = manyPoints(mo, test)
#        secs = random.randint(0,100000)/10000.
         if did > 0:
            case = str(test)+'-'+mo
            print(case+': '+"%.5g" %secs+' secs')
            # add case name to results dict
            if 'case names' in resDict:
               if not case in resDict['case names']:
                  resDict['case names'].append(case)
            else:
               resDict['case names'] = [case]
            # add times to results dict
            if case in resDict:
               resDict[case].append(secs)
            else:
               resDict[case] = [secs]
            # only do one plot for surface or contour (not varied cases)
            if mo in ('surface','contour'):
               break
         did = 1


if __name__ == '__main__':
   iraf.plot() # load plot pkg

   # clean slate
   if 'PYRAFGRAPHICS' in os.environ:
      del os.environ['PYRAFGRAPHICS']
   os.environ['PYRAF_GRAPHICS_ALWAYS_ON_TOP']='1' # rm display bounce dur test
   total = time.time()

   res = {} # mostly a dict of test case times, but 1 item is list of case names

   # Tk
   os.environ['PYRAFGRAPHICS'] = 'tkplot'
   runAllCases('TK', res)

   # MPL kernel
   os.environ['PYRAFGRAPHICS'] = 'matplotlib'
   runAllCases('MPL', res)

   # MPL kernel (again, just for more data)
   runAllCases('MPL-again', res)

   # report
   total = (time.time() - total)/60.
   print("\nTOTAL TIME (min): %.1f" % total+"\n")

   print("                TK               MPL              MPL again\n")
   for ccc in res['case names']:
      times = res[ccc]
      line = "%12s"%ccc+':   '
      for t in times:
         line += "%-8.5g" %t
         line += "("+ ("%.5f"%(t/times[0]))[:4]+")"
         line += "   "
      line += ' secs'
      print(line)
