from __future__ import absolute_import

import os

import pytest

from .utils import HAS_IRAF

if HAS_IRAF:
    from pyraf.clcache import _CodeCache


# simple class to mimic pycode, for unit test (save us from importing others)
class DummyCodeObj(object):

    def setFilename(self, f):
        self.filename = f

    def __str__(self):
        retval = '<DummyCodeObj:'
        if hasattr(self, 'filename'):
            retval += ' filename="'+self.filename+'"'
        if hasattr(self, 'code'):
            retval += ' code="'+self.code+'"'
        retval += '>'
        return retval


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_codecache(tmpdir):
    # Dummy file for caching test
    fname = 'dummyfile.py'
    f = tmpdir.join(fname)
    f.write('Hello world\n')

    codeCache = _CodeCache([os.path.join(tmpdir.strpath, 'clcache')])
    fpath = str(f)
    idx = codeCache.getIndex(fpath)

    pc = DummyCodeObj()
    pc.code = 'print(123)'

    codeCache.add(idx, pc)  # goes in here
    codeCache.add(idx, pc)  # NOT duplicated here
    assert len(codeCache.cacheList) == 1
    assert list(codeCache.clFileDict.keys())[0].endswith(fname)

    newidx, newpycode = codeCache.get(fpath)
    assert newidx == idx
    assert isinstance(newpycode, DummyCodeObj)
