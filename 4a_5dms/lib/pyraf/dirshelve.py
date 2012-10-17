"""Version of shelve that uses files in a directory with binary pickle format

Allows simultaneous read-write access to the data since
the OS allows multiple processes to have access to the
file system.

$Id$

XXX keys, len may be incorrect if directory database is modified
XXX by another process after open

R. White, 2000 Sept 26
"""

from __future__ import division # confidence high

import shelve, sys
from stsci.tools.for2to3 import PY3K

if __name__.find('.') < 0: # for unit test need absolute import
    exec('import dirdbm', globals()) # 2to3 messes up simpler form
else:
    import dirdbm

# tuple of errors that can be raised
error = (dirdbm.error, )

class Shelf(shelve.Shelf):
    """Extension of Shelf using binary pickling"""

    def __getitem__(self, key):
        f = shelve.StringIO(self.dict[key])
        try:
            return shelve.Unpickler(f).load()
        except EOFError:
            # apparently file is truncated; delete it and raise
            # and exception
            del self.dict[key]
            raise KeyError("Corrupted or truncated file for key %s "
                    "(bad file has been deleted)" % (`key`,))

    def __setitem__(self, key, value):
        f = shelve.StringIO()
        p = shelve.Pickler(f,1)
        p.dump(value)
        self.dict[key] = f.getvalue()

    def close(self):
        if hasattr(self,'dict') and hasattr(self.dict,'close'):
            try:
                self.dict.close()
            except:
                pass
        self.dict = 0

class DirectoryShelf(Shelf):
    """Shelf implementation using the directory db interface.

    This is initialized with the filename for the dirdbm database.
    """

    def __init__(self, filename, flag='c'):
        Shelf.__init__(self, dirdbm.open(filename, flag))

def open(filename, flag='c'):
    """Open a persistent dictionary for reading and writing.
    Argument is the filename for the dirdbm database.
    Start using builtin shelve.DbfilenameShelf class as of Python 3.

    Note - flags to the anydbm.open() function mean:
           'r'     Open existing database for reading only (default)
           'w'     Open existing database for reading and writing
           'c'     Open db for read and write, creating if it doesn't exist
           'n'     Always create a new, empty db, open for reading and writing
    """

    if PY3K:
        try:
            return shelve.DbfilenameShelf(filename, flag)
        except Exception, ex: # is dbm.error
            raise dirdbm.error(str(ex))
    else:
       return DirectoryShelf(filename, flag)
