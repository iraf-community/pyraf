"""clcache.py: Implement cache for Python translations of CL tasks

R. White, 2000 January 19
"""
import os
import sys
import hashlib

from stsci.tools.irafglobals import Verbose, userIrafHome

from . import filecache
from . import pyrafglobals
from . import sqliteshelve


if 'PYRAF_CLCACHE_PATH' in os.environ:
    clcache_path = os.environ['PYRAF_CLCACHE_PATH'].split(':')
    if 'disable' in clcache_path:
        clcache_path = []
else:
    # create code cache
    userCacheDir = os.path.join(userIrafHome, 'pyraf')
    if not os.path.exists(userCacheDir):
        try:
            os.mkdir(userCacheDir)
            if '-s' not in sys.argv and '--silent' not in sys.argv:
                print(f'Created directory {userCacheDir} for cache')
        except OSError:
            print(f'Could not create directory {userCacheDir}')
    clcache_path = [userCacheDir, pyrafglobals.pyrafDir]


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


def _currentVersion():
    return "v3" if pyrafglobals._use_ecl else "v2"


class _FileContentsCache(filecache.FileCacheDict):

    def __init__(self):
        # create file dictionary with md5 digest as value
        filecache.FileCacheDict.__init__(self, filecache.MD5Cache)


class _CodeCache:
    """Python code cache class

    Note that old out-of-date cached code never gets
    removed in this system.  That's because another CL
    script might still exist with the same code.  Need a
    utility to clean up the cache by looking for unused keys...
    """

    def __init__(self, cacheFileList):
        self.writeCache = None
        self.cacheList = []
        self.cacheFileList = []
        write_flag = 'w'
        if cacheFileList:
            try:
                fname = cacheFileList[0]
                self.writeCache = sqliteshelve.open(fname, 'w')
                self.cacheList.append(self.writeCache)
                self.cacheFileList.append(fname)
                cacheFileList = cacheFileList[1:]
            except OSError as e:
                self.warning("Unable to open CL script cache "
                             f"{fname} for writing")

        if self.writeCache is None:
            self.warning("Using in-memory cache as primary CL script cache")
            self.writeCache = dict()
            self.cacheList.append(self.writeCache)
            self.cacheFileList.append(':mem:')

        for fname in cacheFileList:
            try:
                db = sqliteshelve.open(fname, 'r')
                self.cacheList.append(db)
                self.cacheFileList.append(fname)
            except OSError as e:
                self.warning("Unable to open CL script cache "
                             f"{fname} for reading", 1)

        self.clFileDict = _FileContentsCache()

    def warning(self, msg, level=0):
        """Print warning message to stderr, using verbose flag"""

        if Verbose >= level:
            sys.stdout.flush()
            sys.stderr.write(msg + "\n")
            sys.stderr.flush()

    def close(self):
        """Close all cache files"""

        for cache in self.cacheList:
            try:
                cache.close()
            except AttributeError:
                pass
        self.cacheList.clear()
        self.writeCache = None
        # Note that this does not delete clFileDict since the
        # in-memory info for files already read is still OK
        # (Just in case there is some reason to close cache files
        # while keeping _CodeCache object around for future use.)

    def __del__(self):
        self.close()

    def getIndex(self, filename, source=None):
        """Get cache key for a file or filehandle"""

        if filename:
            return self.clFileDict.get(filename) + _currentVersion()
        elif source:
            # there is no filename, but return md5 digest of source as key
            h = hashlib.md5()

            h.update(source.encode())
            return h.hexdigest() + _currentVersion()

    def add(self, index, pycode):
        """Add pycode to cache with key = index.  Ignores if index=None."""
        if index is not None and self.writeCache is not None:
            self.writeCache[index] = pycode

    def get(self, filename, mode="proc", source=None):
        """Get pycode from cache for this file.

        Returns tuple (index, pycode).  Pycode=None if not found
        in cache.  If mode != "proc", assumes that the code should not be
        cached.
        """

        if mode != "proc":
            return None, None

        index = self.getIndex(filename, source=source)
        if index is None:
            return None, None

        for cache in self.cacheList:
            if index in cache:
                pycode = cache[index]
                pycode.index = index
                pycode.setFilename(filename)
                return index, pycode
        else:
            return index, None

    def remove(self, filename):
        """Remove pycode from cache for this file or IrafTask object.

        This deletes the entry from the shelve persistent database, under
        the assumption that this routine may be called to fix a bug in
        the code generation (so we don't want to keep the old version of
        the Python code around.)
        """

        if not isinstance(filename, str):
            try:
                task = filename
                filename = task.getFullpath()
            except (AttributeError, TypeError):
                raise TypeError(
                    "Filename parameter must be a string or IrafCLTask")
        index = self.getIndex(filename)
        if self.writeCache:
            if index in self.writeCache:
                del self.writeCache[index]
                self.warning(f"Removed {filename} from CL script cache "
                             f"{self.cacheFileList[0]}", 2)
            else:
                self.warning(f"Did not find {filename} in CL script cache", 2)
        else:
            self.warning(f"Cannot remove {filename} from read-only "
                         f"CL script cache {self.cacheFileList[0]}")


codeCache = _CodeCache([os.path.join(d, 'clcache') for d in clcache_path])
