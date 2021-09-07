"""filecache.py: In-memory cache for files with automatic update

FileCache is the base class for objects that get data from files and
that need to stay in sync with files in case they change.  It tracks the
file creation/modification times and size and calls the updateValue()
method if the file has gotten out of date.  If the file has not previously
been accessed, calls the newValue() method (which by default is the same
as updateValue).

Use the get() method to get the value associated with a file.  The
getValue() method does not check to see if the file has changed and
may also be called if that is the desired effect.

The base implementation of FileCache just stores and returns the file
contents as a string.  Extensions should implement at a minimum the
getValue and updateValue methods.

MD5Cache is an implementation of a FileCache that returns the MD5 digest
value for a file's contents, updating it only if the file has changed.

FileCacheDict is a dictionary-like class that keeps FileCache objects
for a list of filenames.  It is instantiated with the *class* (not an
instance) of the objects to be created for each entry.  New files
are added with the add() method, and values are retrieved by
index (cachedict[filename]) or using the .get() method.

R. White, 2000 October 1
"""

import os
import stat
import sys
import hashlib


class FileCache:
    """File cache base class"""

    def __init__(self, filename):
        self.filename = filename
        self.attributes = self._getAttributes()
        self.newValue()

    # methods that should be supplied in extended class

    def getValue(self):
        """Get info associated with file.

        Usually this is not called directly by the user (use the
        get() method instead.)
        """

        return self.value

    def updateValue(self):
        """Called when file has changed."""

        self.value = self._getFileHandle().read()

    # method that may be changed in extended class

    def newValue(self):
        """Called when file is new.  By default same as updateValue."""

        self.updateValue()

    # basic method to get cached value or to update if needed

    def get(self, update=1):
        """Get info associated with file.

        Updates cache if needed, then calls getValue.  If the
        update flag is false, simply returns the value without
        checking to see if it is out-of-date.
        """

        if update:
            newattr = self._getAttributes()
            # update value if file has changed
            oldattr = self.attributes
            if oldattr != newattr:
                if oldattr[1] > newattr[1] or oldattr[2] > newattr[2]:
                    # warning if current file appears older than cached version
                    self._warning("Warning: current version "
                                  f"of file {self.filename} "
                                  "is older than cached version")
                self.updateValue()
                self.attributes = newattr
        return self.getValue()

    # internal utility methods

    def _getFileHandle(self, filename=None):
        """Get file handle for a filename or filehandle instance"""

        if filename is None:
            filename = self.filename
        if isinstance(filename, str):
            fh = open(filename)
        elif hasattr(filename, 'read'):
            fh = filename
            if hasattr(filename, 'seek'):
                fh.seek(0)
        else:
            raise TypeError(
                "Argument to _getFileHandle must be name or file handle")
        return fh

    def _getAttributes(self, filename=None):
        """Get file attributes for a file or filehandle"""

        if filename is None:
            filename = self.filename
        if not filename:
            return None
        elif isinstance(filename, str):
            st = os.stat(filename)
        elif hasattr(filename, 'fileno') and hasattr(filename, 'name'):
            fh = filename
            st = os.fstat(fh.fileno())
        else:
            return None
        # file attributes are size, creation, and modification times
        return st[stat.ST_SIZE], st[stat.ST_CTIME], st[stat.ST_MTIME]

    def _warning(self, msg):
        """Print warning message to stderr, using verbose flag"""

        sys.stdout.flush()
        sys.stderr.write(msg + "\n")
        sys.stderr.flush()


class MD5Cache(FileCache):
    """Cached MD5 digest for file contents"""

    def getValue(self):
        """Return MD5 digest value associated with file."""

        return self.value

    def updateValue(self):
        """Called when file has changed."""

        contents = self._getFileHandle().read()
        # md5 digest is the value associated with the file
        h = hashlib.md5()
        h.update(contents.encode())
        self.value = h.hexdigest()


class FileCacheDict:
    """Dictionary-like set of cached values for a set of files

    Initialize with class to be instantiated for each file
    """

    def __init__(self, FileCacheClass):
        self.__Class = FileCacheClass
        self.data = {}

    def add(self, filename):
        """Add filename to dictionary.  Does not overwrite existing entry."""
        abspath = self.abspath(filename)
        if abspath not in self.data:
            self.data[abspath] = self.__Class(abspath)

    def abspath(self, filename):
        if isinstance(filename, str):
            return os.path.abspath(filename)
        elif hasattr(filename, 'name') and hasattr(filename, 'read'):
            return os.path.abspath(filename.name)
        else:
            return filename

    def __getitem__(self, filename):
        abspath = self.abspath(filename)
        return self.data[abspath].get()

    def get(self, filename, update=1):
        """Get value; add it if filename is not already in cache

        Note that this behavior differs from the usual dictionary
        get() method -- effectively it never fails.
        """
        abspath = self.abspath(filename)
        obj = self.data.get(abspath)
        if obj is None:
            self.add(abspath)
            obj = self.data[abspath]
        return obj.get(update=update)

    def __delitem__(self, filename):
        abspath = self.abspath(filename)
        del self.data[abspath]

    def has_key(self, key):
        return self._has(key)

    def __contains__(self, key):
        return self._has(key)

    def _has(self, filename):
        abspath = self.abspath(filename)
        return abspath in self.data

    def keys(self):
        return self.data.keys()
