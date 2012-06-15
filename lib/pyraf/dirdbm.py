"""Version of dbm that uses files in a directory

Allows simultaneous read-write access to the data since
the OS allows multiple processes to have access to the
file system.

$Id$

XXX need to implement 'n' open flag (force new database creation)
XXX maybe allow for known key with None as value in dict?
XXX keys, len are incomplete if directory is not writable?

R. White, 2000 September 26
"""

from __future__ import division # confidence high

import os, binascii, string, __builtin__
_os = os
_binascii = binascii
_string = string
del os, binascii, string

# For anydbm
error = IOError

class _Database(object):

    """Dictionary-like object with entries stored in separate files

    Keys and values must be strings.
    Name of file is constructed using base64 translation of key.
    """

    def __init__(self, directory, flag='c'):
        self._directory = directory
        self._dict = {}
        self._writable = flag in ['w','c']
        if not _os.path.exists(directory):
            if flag == 'c':
                # create directory if it doesn't exist
                try:
                    _os.mkdir(directory)
                except OSError, e:
                    raise IOError(str(e))
            else:
                raise IOError("Directory "+directory+" does not exist")
        elif not _os.path.isdir(directory):
            raise IOError("File "+directory+" is not a directory")
        elif self._writable:
            # make sure directory is writable
            try:
                testfile = _os.path.join(directory, 'junk' + `_os.getpid()`)
                fh = __builtin__.open(testfile, 'w')
                fh.close()
                _os.remove(testfile)
            except IOError, e:
                raise IOError("Directory %s cannot be opened for writing" %
                        (directory,))
        # initialize dictionary
        # get list of files from directory and translate to keys
        try:
            flist = _os.listdir(self._directory)
        except OSError:
            raise IOError("Directory "+directory+" is not readable")
        for fname in flist:
            # replace hyphens and add newline in base64
            key = fname.replace('-', '/') + '\n'
            try:
                key = _binascii.a2b_base64(key)
                self._dict[key] = None
            except _binascii.Error:
                # just ignore files with names that do not look like keys
                pass

    def _getFilename(self, key):

        """Return filename equivalent to this string key"""

        filename = _binascii.b2a_base64(key)
        # get rid of trailing newline in base64 and replace slashes
        filename = filename[:-1].replace('/', '-')
        return _os.path.join(self._directory, filename)

    def __getitem__(self, key):
        if key in self._dict and self._dict[key]:
            return self._dict[key]
        # look for file even if dict doesn't have key because
        # another process could create it
        try:
            fh = __builtin__.open(self._getFilename(key),'rb')
            value = fh.read()
            fh.close()
            # cache object in memory
            self._dict[key] = value
            return value
        except IOError:
            raise KeyError(key)

    def __setitem__(self, key, value):
        # use just in-memory dictionary if directory is not writable
        self._dict[key] = value
        if self._writable:
            try:
                fname = self._getFilename(key)
                fh = __builtin__.open(fname,'wb')
                fh.write(value)
                fh.close()
            except IOError, e:
                # clean up on IO error (e.g., if disk fills up)
                try:
                    if _os.path.exists(fname):
                        _os.remove(fname)
                except IOError:
                    pass
                raise e

    def __delitem__(self, key):
        del self._dict[key]
        if self._writable: _os.remove(self._getFilename(key))

    def has_key(self, key): return self._has(key)

    def __contains__(self, key): return self._has(key)

    def _has(self, key):
        return key in self._dict or _os.path.exists(self._getFilename(key))

    def __len__(self):
        return len(self._dict)

    def keys(self):
        return self._dict.keys()

    def close(self):
        self._dict = None
        self._writable = 0


def open(filename, flag='c', mode=None):
    # mode is ignored
    return _Database(filename, flag)
