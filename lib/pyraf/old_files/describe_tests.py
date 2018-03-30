from __future__ import print_function

from pyraf.describe import describe, describeParams


def test():

    def foo(a, b=1, *c, **d):
        e = a + b + c
        f = None

    bar = lambda a: 0  # noqa

    # from Duncan Booth
    def baz(a, (b, c) = ('foo','bar'), (d, e, f) = (None, None, None), g = None):
        pass

    print("describeParams(foo)", describeParams(foo))
    print("describeParams(bar)", describeParams(bar))
    print("describeParams(baz)", describeParams(baz))

    print(describe(foo))
    print(describe(bar))
    print(describe(baz))
