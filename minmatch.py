"""Dictionary allowing minimum-match of string keys.  Entries can be
retrieved using an abbreviated key as long as the key is unambiguous.
__getitem__ and get() raise an error if the key is ambiguous.

A key is not consider ambiguous if it matches a full key, even if it
also is an abbreviation for a longer key.  E.g., if there are keys
'spam' and 'spameggs' in the dictionary, d['spam'] returns the value
associated with 'spam', while d['spa'] is an error due to ambiguity.

New key/value pairs must be inserted using the add() method to avoid
ambiguities with when to overwrite and when to add a new key.  Assignments
using setitem (e.g. d[key] = value) will raise an exception unless the
key already exists and is unambiguous.

The getall(key) method returns a list of all the matching values,
containing a single entry for unambiguous matches and multiple entries
for ambiguous matches.

$Id$

R. White, 1999 March 24
"""

import types
from UserDict import UserDict

class AmbiguousKeyError(KeyError):
	pass

class MinMatchDict(UserDict):

	def __init__(self,dict=None):
		self.data = {}
		self.mmkeys = {}
		if dict:
			for key in dict.keys(): self.add(key,dict[key])

	def getfullkey(self, key, new=0):
		if type(key) != types.StringType:
			raise KeyError("MinMatchDict keys must be strings")
		keylist = self.mmkeys.get(key)
		if not keylist:
			# no such key -- ok only if new flag is set
			if new: return key
			raise KeyError("Key "+key+" not found")
		elif len(keylist) == 1:
			# unambiguous key
			return keylist[0]
		elif key in keylist:
			# ambiguous key is ok if there is exact match
			return key
		else:
			raise AmbiguousKeyError("Ambiguous key "+ `key` +
				", could be any of " + `keylist`)

	def add(self, key, item):
		"""Add a new key/item pair to the dictionary.  Resets an existing
		key value only if this is an exact match to a known key."""
		if not self.has_exact_key(key):
			for i in xrange(len(key)):
				s = key[0:i+1]
				value = self.mmkeys.get(s)
				if value is None:
					self.mmkeys[s] = [key]
				else:
					value.append(key)
		self.data[key] = item

	def __setitem__(self, key, item):
		"""Set value of existing key/item in dictionary"""
		try:
			key = self.getfullkey(key)
			self.data[key] = item
		except KeyError, e:
			raise e.__class__(str(e) + "\nUse add() method to add new items")
			# raise KeyError(str(e) + "\nUse add() method to add new items")

	def __getitem__(self, key):
		key = self.getfullkey(key)
		return self.data[key]

	def get(self, key, failobj=None):
		"""Raises exception if key is ambiguous"""
		key = self.getfullkey(key,new=1)
		return self.data.get(key,failobj)

	def __delitem__(self, key):
		key = self.getfullkey(key)
		del self.data[key]
		for i in xrange(len(key)):
			s = key[0:i+1]
			value = self.mmkeys.get(s)
			value.remove(key)

	def clear(self):
		self.mmkeys.clear()
		return self.data.clear()

	def has_key(self, key):
		"""Raises an exception if key is ambiguous"""
		key = self.getfullkey(key,new=1)
		return self.data.has_key(key)

	def has_exact_key(self, key):
		"""Returns true if there is an exact match for this key"""
		return self.data.has_key(key)

	def update(self, other):
		if type(other) is type(self.data):
			for key in other.keys():
				self.add(key,other[key])
		else:
			for key, value in other.items():
				self.add(key,value)

	def getall(self, key, failobj=None):
		"""Returns a list of all the matching values for key,
		containing a single entry for unambiguous matches and
		multiple entries for ambiguous matches."""
		k = self.mmkeys.get(key)
		if not k: return failobj
		v = len(k)*[None]
		for i in xrange(len(k)):
			v[i] = self.data[k[i]]
		return v

# some simple tests

if __name__ == "__main__":
	d = MinMatchDict()
	d.add('test',1)
	d.add('text',2)
	d.add('ten',10)
	print "d.items()", d.items()
	print "d['tex']=", d['tex']
	print "Changing d['tes'] to 3"
	d['tes'] = 3
	print "d.items()", d.items()
	try:
		print "Trying ambiguous assignment to d['te']"
		d['te'] = 5
	except AmbiguousKeyError, e:
		print str(e)
		print '---'
	print "d.get('tes')", d.get('tes')
	print "d.get('teq')", d.get('teq')
	print "d.getall('t')", d.getall('t')
	try:
		print "d.get('t')",
		print d.get('t')
	except AmbiguousKeyError, e:
		print str(e)
		print '---'
	print "d.add('tesseract',100)"
	d.add('tesseract',100)
	print "d.items()", d.items()
	try:
		print "d.get('tes')",
		print d.get('tes')
	except AmbiguousKeyError, e:
		print str(e)
		print '---'
	try:
		print "del d['tes']",
		del d['tes']
	except AmbiguousKeyError, e:
		print str(e)
		print '---'
	print "del d['tess']"
	del d['tess']
	print "d.items()", d.items()
	print "d.get('tes')", d.get('tes')
	print "d.has_key('tes')", d.has_key('tes')
	print "d.clear()"
	d.clear()
	print "d.items()", d.items()
	print "d.update({'ab': 0, 'cd': 1, 'ce': 2})"
	d.update({'ab': 0, 'cd': 1, 'ce': 2})
	print "d.items()", d.items()
	print "d['a']", d['a']
	try:
		print "d['t']",
		print d['t'],
	except KeyError, e:
		print str(e)
		print '---'

