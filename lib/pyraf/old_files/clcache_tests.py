from __future__ import division, print_function

from pyraf.clcache import codeCache


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
    #global codeCache

    print('Starting codeCache is: '+str(codeCache.cacheList))
    print('keys = '+str(codeCache.clFileDict.keys()))

    for fname in ('../clcache.py', '../filecache.py'):
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


if __name__ == '__main__':
    test()
