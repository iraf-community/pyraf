import pytest
from ..irafutils import csvSplit


@pytest.mark.parametrize('input_str,input_len,expected', [
    (None, 0, "[]"),
    ('', 0, "[]"),
    (' ', 1, "[' ']"),
    ('a', 1, "['a']"),
    (',', 2, "['', '']"),
    (',a', 2, "['', 'a']"),
    ('a,', 2, "['a', '']"),
    (',a,', 3, "['', 'a', '']"),
    ("abc'-hi,ya-'xyz", 1, """["abc'-hi,ya-'xyz"]"""),
    ('abc"double-quote,eg"xy,z', 2, """['abc"double-quote,eg"xy', 'z']"""),
    ('abc"""triple-quote,eg"""xyz', 1, '[\'abc"""triple-quote,eg"""xyz\']'),
    ("'s1', 'has, comma', z", 3, """["'s1'", " 'has, comma'", ' z']"""),
    ("a='s1', b='has,comma,s', c", 3, """["a='s1'", " b='has,comma,s'", ' c']"""),
])
def test_csvSplit(input_str, input_len, expected):
    result = csvSplit(input_str, ',', True)
    result_len = len(result)

    assert result_len == input_len and repr(result) == expected, \
        "For case: {} expected:\n{}\nbut got:\n{}".format(
            input_str, expected, repr(result))
