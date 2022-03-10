import pytest

from ..minmatch import MinMatchDict, AmbiguousKeyError

BASEKEYS = tuple(['test', 'text', 'ten'])
BASEVALUES = tuple([1, 2, 10])


@pytest.fixture
def mmd():
    d = MinMatchDict()
    for value in zip(*[BASEKEYS, BASEVALUES]):
        d.add(*value)
    return d


def test_ambiguous_assignment_key(mmd):
    with pytest.raises(AmbiguousKeyError):
        mmd['te'] = 5


def test_ambiguous_assignment_get_t(mmd):
    with pytest.raises(AmbiguousKeyError):
        mmd.get('t')


def test_ambiguous_assignment_get_tes(mmd):
    with pytest.raises(AmbiguousKeyError):
        mmd.get('te')


def test_ambiguous_assignment_del_tes(mmd):
    with pytest.raises(AmbiguousKeyError):
        del mmd['te']


def test_invalid_key_assignment(mmd):
    with pytest.raises(KeyError):
        mmd['t']


def test_dict_sort(mmd):
    result = [key for key, _ in sorted(mmd.items())]
    assert result[0] == 'ten'
    assert result[-1] == 'text'


@pytest.mark.parametrize('key', BASEKEYS)
def test_get_values(mmd, key):
    assert mmd.get(key)


def test_missing_key_returns_none(mmd):
    assert mmd.get('teq') is None


def test_getall(mmd):
    return mmd.getall('t')


def test_getall_returns_expected_values(mmd):
    result = mmd.getall('t')
    assert sorted(result) == [x for x in BASEVALUES]


def test_del_key(mmd):
    del mmd['test']


def test_del_keys(mmd):
    for key in BASEKEYS:
        del mmd[key]


def test_clear_dict(mmd):
    mmd.clear()
    assert mmd == dict()


def test_has_key(mmd):
    for key in BASEKEYS:
        # Ditch last character in string
        if len(key) > 3:
            key = key[:-1]

        assert mmd.has_key(key, exact=False)


def test_has_key_exact(mmd):
    for key in BASEKEYS:
        assert mmd.has_key(key, exact=True)


def test_key_in_dict(mmd):
    for key in BASEKEYS:
        assert key in mmd


def test_update_dict(mmd):
    new_dict = dict(ab=0)
    mmd.update(new_dict)
    assert 'test' in mmd and 'ab' in mmd
