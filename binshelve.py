"""Version of shelve that uses binary pickle format

$Id$

R. White, 2000 January 19
"""

import shelve, anydbm

# tuple of errors that anydbm can raise
from anydbm import error

class Shelf(shelve.Shelf):
	"""Extension of Shelf using binary pickling"""

	def __getitem__(self, key):
		f = shelve.StringIO(self.dict[key])
		return shelve.Unpickler(f).load()

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

class BsdDbShelf(Shelf, shelve.BsdDbShelf):
	"""Shelf implementation using the "BSD" db interface."""

	def __init__(self, dict):
	    Shelf.__init__(self, dict)

class DbfilenameShelf(Shelf):
	"""Shelf implementation using the "anydbm" generic dbm interface."""

	def __init__(self, filename, flag='c'):
		import anydbm
		Shelf.__init__(self, anydbm.open(filename, flag))


class GdbfilenameShelf(Shelf):
	"""Shelf implementation using the gdbm interface."""

	def __init__(self, filename, flag='c'):
		import gdbm
		Shelf.__init__(self, gdbm.open(filename, flag))


def open(filename, flag='c'):
	"""Open a persistent dictionary for reading and writing."""

	try:
		return GdbfilenameShelf(filename, flag)
	except error:
		return DbfilenameShelf(filename, flag)
