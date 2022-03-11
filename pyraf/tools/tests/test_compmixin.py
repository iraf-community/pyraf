import pytest

from ..compmixin import ComparableMixin


class SimpleStr(ComparableMixin):
    def __init__(self, v):
        self.val = str(v)  # all input turned to string

    def __str__(self):
        return str(self.val)

    def _cmpkey(self):
        return self.val


class AnyType(ComparableMixin):
    def __init__(self, v):
        self.val = v  # leave all input typed as is

    def __str__(self):
        return str(self.val)

    # define this instead of _cmpkey - handle ALL sorts of scenarios,
    # except intentionally don't compare self strings (strlen>1) with integers
    # so we have a case which fails in our test below
    def _compare(self, other, method):
        if isinstance(other, self.__class__):
            # recurse, get 2 logic below
            return self._compare(other.val, method)
        if isinstance(other, str):
            return method(str(self.val), other)
        elif other is None and self.val is None:
            return method(0, 0)
        elif other is None:
            # coerce to str compare
            return method(str(self.val), '')
        elif isinstance(other, int):
            # handle ONLY case where self.val is a single char or an int
            if isinstance(self.val, str) and len(self.val) == 1:
                return method(ord(self.val), other)
            else:
                # assume we are int-like
                return method(int(self.val), other)
        try:
            return method(self.val, other)
        except (AttributeError, TypeError):
            return NotImplemented


def test_SimpleStr():
    a = SimpleStr('a')
    b = SimpleStr('b')
    c = SimpleStr('c')
    two = SimpleStr(2)

    # compare two SimpleStr objects
    assert str(a > b) == "False"
    assert str(a < b) == "True"
    assert str(a <= b) == "True"
    assert str(a == b) == "False"
    assert str(b == b) == "True"
    assert str(a < c) == "True"
    assert str(a <= c) == "True"
    assert str(a != c) == "True"
    assert str(c != c) == "False"
    assert str(c == c) == "True"
    assert str(b < two) == "False"
    assert str(b >= two) == "True"
    assert str(b == two) == "False"
    assert str([str(jj) for jj in sorted([b, a, two, c])]
               ) == "['2', 'a', 'b', 'c']"


def test_AnyType():
    x = AnyType('x')
    y = AnyType('yyy')
    z = AnyType(0)
    nn = AnyType(None)

    # compare two AnyType objects
    assert str(x > y) == "False"
    assert str(x < y) == "True"
    assert str(x <= y) == "True"
    assert str(x == y) == "False"
    assert str(y == y) == "True"
    assert str(x < z) == "False"
    assert str(x <= z) == "False"
    assert str(x > z) == "True"
    assert str(x != z) == "True"
    assert str(z != z) == "False"
    assert str(z == z) == "True"
    assert str(y < nn) == "False"
    assert str(y >= nn) == "True"
    assert str(y == nn) == "False"
    assert str(nn == nn) == "True"
    assert str([str(jj) for jj in sorted([y, x, nn, z])]
               ) == "['None', '0', 'x', 'yyy']"

    # compare AnyType objects to built-in types
    assert str(x < 0) == "False"
    assert str(x <= 0) == "False"
    assert str(x > 0) == "True"
    assert str(x != 0) == "True"
    assert str(x == 0) == "False"
    assert str(x < None) == "False"
    assert str(x <= None) == "False"
    assert str(x > None) == "True"
    assert str(x != None) == "True"
    assert str(x == None) == "False"
    assert str(x < "abc") == "False"
    assert str(x <= "abc") == "False"
    assert str(x > "abc") == "True"
    assert str(x != "abc") == "True"
    assert str(x == "abc") == "False"
    assert str(y < None) == "False"
    assert str(y <= None) == "False"
    assert str(y > None) == "True"
    assert str(y != None) == "True"
    assert str(y == None) == "False"
    assert str(y < "abc") == "False"
    assert str(y <= "abc") == "False"
    assert str(y > "abc") == "True"
    assert str(y != "abc") == "True"
    assert str(y == "abc") == "False"


def test_raise_on_integer_comparison():
    y = AnyType('yyy')
    z = AnyType(0)
    with pytest.raises(ValueError):
        y == z  # AnyType intentionally doesn't compare strlen>1 to ints


def test_raise_on_sort():
    y = AnyType('yyy')
    z = AnyType(0)
    with pytest.raises(ValueError):
        sorted([z, y])
