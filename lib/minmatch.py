"""minmatch.py: Dictionary allowing minimum-match of string keys

Entries can be retrieved using an abbreviated key as long as the key
is unambiguous.  __getitem__ and get() raise an error if the key is
ambiguous.

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

R. White, 2000 January 28
"""

import copy
from types import StringType
from UserDict import UserDict

class AmbiguousKeyError(KeyError):
    pass

class MinMatchDict(UserDict):

    def __init__(self,dict=None,minkeylength=1):
        self.data = {}
        # use lazy instantiation for min-match dictionary
        # it may never be created if full keys are always used
        self.mmkeys = None
        if minkeylength<1: minkeylength = 1
        self.minkeylength = minkeylength
        if dict:
            add = self.add
            for key in dict.keys(): add(key,dict[key])

    def __deepcopy__(self, memo=None):
        """Deep copy of dictionary"""
        # this is about twice as fast as the default implementation
        return self.__class__(copy.deepcopy(self.data,memo), self.minkeylength)

    def __getinitargs__(self):
        """Return __init__ args for pickle"""
        return (self.data, self.minkeylength)

    def __getstate__(self):
        """Return state info for pickle"""
        # no additional state after init
        return None

    def __setstate__(self, state):
        """Restore state info from pickle"""
        pass

    def _mmInit(self):
        """Create the minimum match dictionary of keys"""
        # cache references to speed up loop a bit
        mmkeys = {}
        mmkeysGet = mmkeys.setdefault
        minkeylength = self.minkeylength
        for key in self.data.keys():
            # add abbreviations as short as minkeylength
            # always add at least one entry (even for key="")
            lenkey = len(key)
            start = min(minkeylength,lenkey)
            for i in xrange(start,lenkey+1):
                mmkeysGet(key[0:i],[]).append(key)
        self.mmkeys = mmkeys

    def getfullkey(self, key, new=0):
        # check for exact match first
        # ambiguous key is ok if there is exact match
        if self.data.has_key(key): return key
        if type(key) != StringType:
            raise KeyError("MinMatchDict keys must be strings")
        # no exact match, so look for unique minimum match
        if self.mmkeys is None: self._mmInit()
        keylist = self.mmkeys.get(key)
        if keylist is None:
            # no such key -- ok only if new flag is set
            if new: return key
            raise KeyError("Key "+key+" not found")
        elif len(keylist) == 1:
            # unambiguous key
            return keylist[0]
        else:
            return self.resolve(key,keylist)

    def resolve(self, key, keylist):
        """Hook to resolve ambiguities in selected keys"""
        raise AmbiguousKeyError("Ambiguous key "+ `key` +
                ", could be any of " + `keylist`)

    def add(self, key, item):
        """Add a new key/item pair to the dictionary.  Resets an existing
        key value only if this is an exact match to a known key."""
        mmkeys = self.mmkeys
        if mmkeys is not None and not self.data.has_key(key):
            # add abbreviations as short as minkeylength
            # always add at least one entry (even for key="")
            lenkey = len(key)
            start = min(self.minkeylength,lenkey)
            # cache references to speed up loop a bit
            mmkeysGet = mmkeys.setdefault
            for i in xrange(start,lenkey+1):
                mmkeysGet(key[0:i],[]).append(key)
        self.data[key] = item

    def __setitem__(self, key, item):
        """Set value of existing key/item in dictionary"""
        try:
            key = self.getfullkey(key)
            self.data[key] = item
        except KeyError, e:
            raise e.__class__(str(e) + "\nUse add() method to add new items")

    def __getitem__(self, key):
        try:
            # try the common case that the exact key is given first
            return self.data[key]
        except KeyError:
            return self.data[self.getfullkey(key)]

    def get(self, key, failobj=None, exact=0):
        """Raises exception if key is ambiguous"""
        if not exact:
            key = self.getfullkey(key,new=1)
        return self.data.get(key,failobj)

    def get_exact_key(self, key, failobj=None):
        """Returns failobj if key does not match exactly"""
        return self.data.get(key,failobj)

    def __delitem__(self, key):
        key = self.getfullkey(key)
        del self.data[key]
        if self.mmkeys is not None:
            start = min(self.minkeylength,len(key))
            for i in xrange(start,len(key)+1):
                s = key[0:i]
                value = self.mmkeys.get(s)
                value.remove(key)
                if not value:
                    # delete entry from mmkeys if that was last value
                    del self.mmkeys[s]

    def clear(self):
        self.mmkeys = None
        self.data.clear()

    def has_key(self, key, exact=0):
        """Raises an exception if key is ambiguous"""
        if not exact:
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
        if self.mmkeys is None: self._mmInit()
        k = self.mmkeys.get(key)
        if not k: return failobj
        return map(self.data.get, k)

    def getallkeys(self, key, failobj=None):
        """Returns a list of the full key names (not the items)
        for all the matching values for key.  The list will
        contain a single entry for unambiguous matches and
        multiple entries for ambiguous matches."""
        if self.mmkeys is None: self._mmInit()
        return self.mmkeys.get(key, failobj)


class QuietMinMatchDict(MinMatchDict):

    """Minimum match dictionary that does not raise unexpected AmbiguousKeyError

    Unlike MinMatchDict, if key is ambiguous then both get() and
    has_key() methods return false (just as if there is no match).
    For most uses this is probably not the preferred behavior (use
    MinMatchDict instead), but for applications that rely on the
    usual dictionary behavior where .get() and .has_key() do not
    raise exceptions, this is useful.
    """

    def get(self, key, failobj=None, exact=0):

        """Returns failobj if key is not found or is ambiguous"""

        if not exact:
            try:
                key = self.getfullkey(key)
            except KeyError:
                return failobj
        return self.data.get(key,failobj)


    def has_key(self, key, exact=0):

        """Returns false if key is not found or is ambiguous"""

        if not exact:
            try:
                key = self.getfullkey(key)
                return 1
            except KeyError:
                return 0
        else:
            return self.data.has_key(key)


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
