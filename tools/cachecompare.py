#! /usr/bin/env python

"""cachecompare.py: Compare contents of new CL to old cache
$Id$
"""
from __future__ import division # confidence high

import os
import pyraf

newname = os.path.expanduser('~/iraf/pyraf/clcache')
oldname1 = os.path.join(pyraf.irafglobals.pyrafDir,'clcache.old')
oldname2 = os.path.expanduser('~/iraf/pyraf/clcache.old')

dbnew = pyraf.dirshelve.open(newname,'r')
dbold1 = pyraf.dirshelve.open(oldname1,'r')
dbold2 = pyraf.dirshelve.open(oldname2,'r')

notfound = 0
found1 = 0
found2 = 0
ok1 = 0
ok2 = 0
diff1 = 0
diff2 = 0
for key in dbnew.keys():
    if dbold1.has_key(key):
        oldcode = dbold1[key]
        found1 += 1
        select = 1
    elif dbold2.has_key(key):
        oldcode = dbold2[key]
        found2 += 1
        select = 2
    else:
        notfound += 1
        continue
    newcode = dbnew[key]
    if newcode == oldcode or newcode.code == oldcode.code:
        if select==1:
            ok1 += 1
        else:
            ok2 += 1
    else:
        if select==1:
            diff1 += 1
        else:
            diff2 += 1
        print select,"Different", newcode.vars.proc_name

dbnew.close()
dbold1.close()
dbold2.close()
print "Checked",notfound+ok1+ok2+diff1+diff2,"entries from new cache"
print notfound,"not found in old cache"
print found1,"found in old cache 1",oldname1
print ok1,"same"
print diff1,"different"
print found2,"found in old cache 2",oldname2
print ok2,"same"
print diff2,"different"
