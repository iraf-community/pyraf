"""Dictionary allowing minimum-match of string keys.  Entries are a
list of the associated values.  The returned list has a single entry
for unambiguous matches and has multiple entries for ambiguous
matches."""

import types
from UserDict import UserDict

class MinMatchDict(UserDict):
    def __init__(self,dict=None):
		self.data = {}
		if dict:
			for key in dict.keys(): self[key] = dict[key]
    def __setitem__(self, key, item):
		if type(key) != types.StringType:
			raise KeyError("MinMatchDict keys must be strings")
		for i in xrange(len(key)):
			s = key[0:i+1]
			value = self.data.get(s)
			if value == None:
				self.data[s] = [item]
			else:
				value.append(item)
