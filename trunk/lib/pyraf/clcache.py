"""clcache.py: Implement cache for Python translations of CL tasks

$Id$

R. White, 2000 January 19
"""
from __future__ import division # confidence high

import os, sys
from stsci.tools.irafglobals import Verbose, userIrafHome
if __name__.find('.') < 0: # for unit test
   import filecache # revert to simple import after 2to3
   import pyrafglobals # revert to simple import after 2to3
   import dirshelve # revert to simple import after 2to3
else:
   import filecache
   import pyrafglobals
   import dirshelve


# set up pickle so it can pickle code objects

import copy_reg, marshal, types
try:
    import cPickle as pickle
except ImportError:
    import pickle

def code_unpickler(data):
    return marshal.loads(data)

def code_pickler(code):
    return code_unpickler, (marshal.dumps(code),)

copy_reg.pickle(types.CodeType, code_pickler, code_unpickler)

# Code cache is implemented using a dictionary clFileDict and
# a list of persistent dictionaries (shelves) in cacheList.
#
# - clFileDict uses CL filename as the key and has
#   the md5 digest of the file contents as its value.
#   The md5 digest is automatically updated if the file changes.
#
# - the persistent cache has the md5 digest as the key
#       and the Pycode object as the value.
#
# This scheme allows files with different path names to
# be found in the cache (since the file contents, not the
# name, determine the shelve key) while staying up-to-date
# with changes of the CL file contents when the script is
# being developed.

import stat, hashlib

_versionKey = 'CACHE_VERSION'

def _currentVersion():
    if not pyrafglobals._use_ecl:
        return "v2"
    else:
        return "v3"

class _FileContentsCache(filecache.FileCacheDict):
    def __init__(self):
        # create file dictionary with md5 digest as value
        filecache.FileCacheDict.__init__(self,filecache.MD5Cache)

class _CodeCache:

    """Python code cache class

    Note that old out-of-date cached code never gets
    removed in this system.  That's because another CL
    script might still exist with the same code.  Need a
    utility to clean up the cache by looking for unused keys...
    """

    def __init__(self, cacheFileList):
        cacheList = []
        flist = []
        nwrite = 0
        for file in cacheFileList:
            db = self._cacheOpen(file)
            if db is not None:
                cacheList.append(db[0:2])
                nwrite = nwrite+db[0]
                flist.append(db[2])
        self.clFileDict = _FileContentsCache()
        self.cacheList = cacheList
        self.cacheFileList = flist
        self.nwrite = nwrite
        # flag indicating preference for system cache
        self.useSystem = 0
        if not cacheList:
            self.warning("Warning: unable to open any CL script cache, "
                    "performance will be slow")
        elif nwrite == 0:
            self.warning("Unable to open any CL script cache for writing")

    def _cacheOpen(self, filename):
        """Open shelve database in filename and check version

        Returns tuple (writeflag, shelve-object, filename) on success or
        None on failure.
        This may modify the filename if necessary to open the correct version of
        the cache.
        """
        # filenames to try, open flags to use
        filelist = [(filename, "w"),
                    ('%s.%s' % (filename, _currentVersion()), "c")]
        msg = []
        for fname, flag in filelist:
            # first try opening the cache read-write
            try:
                fh = dirshelve.open(fname, flag)
                writeflag = 1
            except dirshelve.error:
                # initial open failed -- try opening the cache read-only
                try:
                    fh = dirshelve.open(fname,"r")
                    writeflag = 0
                except dirshelve.error:
                    # give up on this file and try the next one
                    msg.append("Unable to open CL script cache %s" % fname)
                    continue
            # check version of cache -- don't use it if version mismatch
            if len(fh) == 0:
                fh[_versionKey] = _currentVersion()
            oldVersion = fh.get(_versionKey, 'v0')
            if oldVersion == _currentVersion():
                # normal case -- cache version is as expected
                return (writeflag, fh, fname)
            elif fname.endswith(_currentVersion()):
                # uh-oh, something is seriously wrong
                msg.append("CL script cache %s has version mismatch, may be corrupt?" %
                    fname)
            elif oldVersion > _currentVersion():
                msg.append(("CL script cache %s was created by " +
                    "a newer version of pyraf (cache %s, this pyraf %s)") %
                    (fname, `oldVersion`, `_currentVersion()`))
            else:
                msg.append("CL script cache %s is obsolete version (old %s, current %s)" %
                        (fname, `oldVersion`, `_currentVersion()`))
            fh.close()
        # failed to open either cache
        self.warning("\n".join(msg))
        return None

    def warning(self, msg, level=0):

        """Print warning message to stderr, using verbose flag"""

        if Verbose >= level:
            sys.stdout.flush()
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()

    def writeSystem(self, value=1):

        """Add scripts to system cache instead of user cache"""

        if value==0:
            self.useSystem = 0
        elif self.cacheList:
            writeflag, cache = self.cacheList[-1]
            if writeflag:
                self.useSystem = 1
            else:
                self.warning("System CL script cache is not writable")
        else:
            self.warning("No CL script cache is active")

    def close(self):

        """Close all cache files"""

        for writeflag, cache in self.cacheList:
            cache.close()
        self.cacheList = []
        self.nwrite = 0
        # Note that this does not delete clFileDict since the
        # in-memory info for files already read is still OK
        # (Just in case there is some reason to close cache files
        # while keeping _CodeCache object around for future use.)

    def __del__(self):
        self.close()

    def getIndex(self, filename, source=None):
        """Get cache key for a file or filehandle"""

        if filename:
            return self.clFileDict.get(filename)
        elif source:
            # there is no filename, but return md5 digest of source as key
            h = hashlib.md5()

            if sys.version_info[0] > 2: # unicode must be encoded to be hashed
                h.update(source.encode('utf-8'))
                return str(h.digest())
            else:
                h.update(source)
                return h.digest()

    def add(self, index, pycode):
        """Add pycode to cache with key = index.  Ignores if index=None."""

        if index is None or self.nwrite==0: return
        if self.useSystem:
            # system cache is last in list
            cacheList = self.cacheList[:]
            cacheList.reverse()
        else:
            cacheList = self.cacheList
        for writeflag, cache in cacheList:
            if writeflag:
                cache[index] = pycode
                return

    def get(self, filename, mode="proc", source=None):

        """Get pycode from cache for this file.

        Returns tuple (index, pycode).  Pycode=None if not found
        in cache.  If mode != "proc", assumes that the code should not be
        cached.
        """

        if mode != "proc": return None, None

        index = self.getIndex(filename, source=source)
        if index is None: return None, None

        for i in range(len(self.cacheList)):
            writeflag, cache = self.cacheList[i]
            if cache.has_key(index):
                pycode = cache[index]
                pycode.index = index
                pycode.setFilename(filename)
                return index, pycode
        return index, None

    def remove(self, filename):

        """Remove pycode from cache for this file or IrafTask object.

        This deletes the entry from the shelve persistent database, under
        the assumption that this routine may be called to fix a bug in
        the code generation (so we don't want to keep the old version of
        the Python code around.)
        """

        if not isinstance(filename,str):
            try:
                task = filename
                filename = task.getFullpath()
            except (AttributeError, TypeError):
                raise TypeError(
                        "Filename parameter must be a string or IrafCLTask")
        index = self.getIndex(filename)
        # system cache is last in list
        irange = range(len(self.cacheList))
        if self.useSystem: irange.reverse()
        nremoved = 0
        for i in irange:
            writeflag, cache = self.cacheList[i]
            if cache.has_key(index):
                if writeflag:
                    del cache[index]
                    self.warning("Removed %s from CL script cache %s" % \
                            (filename,self.cacheFileList[i]), 2)
                    nremoved = nremoved+1
                else:
                    self.warning("Cannot remove %s from read-only "
                            "CL script cache %s" % \
                            (filename,self.cacheFileList[i]))
        if nremoved==0:
            self.warning("Did not find %s in CL script cache" % filename, 2)


# simple class to mimic pycode, for unit test (save us from importing others)
class DummyCodeObj:
    def setFilename(self, f):
        self.filename = f
    def __str__(self):
        retval = '<DummyCodeObj:'
        if hasattr(self, 'filename'): retval += ' filename="'+self.filename+'"'
        if hasattr(self, 'code'):     retval += ' code="'+self.code+'"'
        retval += '>'
        return retval


def test():
    """ Just run through the paces """
    global codeCache
    import os

    print('Starting codeCache is: '+str(codeCache.cacheList))
    print('keys = '+str(codeCache.clFileDict.keys()))

    for fname in ('clcache.py', 'filecache.py'):
        # lets cache this file
        print('\ncaching: '+fname)
        idx = codeCache.getIndex(fname)
        pc = DummyCodeObj()
        pc.code = 'print(123)'
        print('fname:', fname, ', idx:', idx)
        codeCache.add(idx, pc) # goes in here
        codeCache.add(idx, pc) # NOT duplicated here
        codeCache.add(idx, pc) # or here
        print('And now, codeCache is: '+str(codeCache.cacheList))
        print('keys = '+str(codeCache.clFileDict.keys()))
        # try to get it out
        newidx, newpycode = codeCache.get(fname)
        assert newidx==idx, 'ERROR: was'+str(idx)+', but now is: '+str(newidx)
        print('The -get- gave us: '+str(newpycode))


# create code cache
userCacheDir = os.path.join(userIrafHome,'pyraf')
if not os.path.exists(userCacheDir):
    try:
        os.mkdir(userCacheDir)
        if '-s' not in sys.argv and '--silent' not in sys.argv:
            print 'Created directory %s for cache' % userCacheDir
    except OSError:
        print 'Could not create directory %s' % userCacheDir

dbfile = 'clcache'
codeCache = _CodeCache([
        os.path.join(userCacheDir,dbfile),
        os.path.join(pyrafglobals.pyrafDir,dbfile),
        ])
del userCacheDir, dbfile

if __name__ == '__main__':
    test()
