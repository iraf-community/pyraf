#! /usr/bin/env python
# rename clcache files
# $Id$
#

from __future__ import division # confidence high
import os

def fixit(trylist, verbose=0):
    for cachedir in trylist:
        cachedir = os.path.expanduser(cachedir)
        if os.path.exists(cachedir):
            break
    else:
        raise OSError("clcache directory not found (tried %s)" %        (trylist,))
    flist = os.listdir(cachedir)
    fcount = 0
    rcount = 0
    for file in flist:
        fcount = fcount+1
        if file[-2:] != "==":
            rcount = rcount+1
            fpath = os.path.join(cachedir,file)
            os.rename(fpath, fpath+"==")
    if verbose:
        print "Renamed %d of %d files in %s" % (rcount, fcount, cachedir)

if __name__ == "__main__":
    # looks in ~/iraf/pyraf/clcache, ./clcache, and ./pyraf/clcache
    import sys
    if len(sys.argv) > 1:
        trylist = sys.argv[1:]
    else:
        trylist = ["~/iraf/pyraf/clcache", "./clcache", "./pyraf/clcache"]
    fixit(trylist, verbose=1)
