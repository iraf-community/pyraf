#! /usr/bin/env python

"""cachesearch.py: Check all entries in CL cache for a particular string
$Id$
"""
from __future__ import division # confidence high

import os, re
import pyraf

def search(pattern):
    if isinstance(pattern, str):
        pattern = re.compile(pattern)
    cachename1 = os.path.expanduser('~/iraf/pyraf/clcache')
    cachename2 = os.path.join(pyraf.irafglobals.pyrafDir,'clcache')

    db1 = pyraf.dirshelve.open(cachename1,'r')
    db2 = pyraf.dirshelve.open(cachename2,'r')

    keys1 = db1.keys()
    keys2 = db2.keys()
    keydict = {}
    for key in db1.keys(): keydict[key] = 1
    for key in db2.keys(): keydict[key] = 1

    match = 0
    nomatch = 0
    pmatch = []
    for key in keydict.keys():
        if db1.has_key(key):
            pycode = db1[key]
        elif db2.has_key(key):
            pycode = db2[key]
        else:
            raise Exception("Error: not in cache on second pass??")
        if not hasattr(pycode,'code'):
            continue
        mm = pattern.search(pycode.code)
        if mm:
            match += 1
            print '%d: %s' % (match, pycode.vars.proc_name)
            pmatch.append(pycode.vars.proc_name)
            # print matching lines
            lines = pycode.code.split('\n')
            i = 0
            ilast = -1
            sum = len(lines[0])+1
            while mm:
                while sum<mm.start():
                    i = i+1
                    sum = sum+len(lines[i])+1
                if ilast != i:
                    print lines[i]
                    ilast = i
                mm = pattern.search(pycode.code, mm.end())
        else:
            nomatch += 1
        if match+nomatch == 1:
            print dir(pycode)
            print dir(pycode.vars)
    db1.close()
    db2.close()
    print "Checked",match+nomatch,"entries from caches"
    print nomatch,"did not match pattern"
    print match,"did match pattern"
    return pmatch
