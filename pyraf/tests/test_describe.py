import pytest

from pyraf.describe import describe, describeParams


def test_desc():

    def foo(a, b=1, *c, **d):
        e = a + b + c
        f = None

    bar = lambda a: 0  # noqa

    # from Duncan Booth
    #    def baz(a, (b, c) = ('foo', 'bar'), (d, e, f) = (None, None, None), g = None):  # noqa
    #        pass

    assert describeParams(foo) == ['a', ('b', 1), '*c', '**d']
    assert describeParams(bar) == ['a']
    #    assert describeParams(baz) == ['a',
    #                                   ('(b, c)', ('foo', 'bar')),
    #                                   ('(d, e, f)', (None, None, None)),
    #                                   ('g', None)]
    assert describe(foo) == 'foo(a, b=1, *c, **d)'
    assert describe(bar) == 'lambda a'


#    assert describe(baz) == "baz(a, (b, c)=('foo', 'bar'), (d, e, f)=(None, None, None), g=None)"
