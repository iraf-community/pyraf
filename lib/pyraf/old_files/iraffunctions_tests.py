from __future__ import print_function

from pyraf import sscanf


def test_sscanf():
    """ A basic unit test that sscanf was built/imported correctly and
    can run. """
    assert sscanf is not None, 'Error importing sscanf during iraffunctions init'
    # aliveness
    l = sscanf.sscanf("seven 6 4.0 -7", "%s %d %g %d")
    assert l==['seven', 6, 4.0, -7], 'Unexpected!  l = '+str(l)
    # bad format
    l = sscanf.sscanf("seven", "%d")
    assert l==[], 'Unexpected!  l = '+str(l)
    # %c
    l = sscanf.sscanf("seven", "%c%3c%99c")
    assert l==['s', 'eve', 'n'], 'Unexpected!  l = '+str(l)
    # hex
    l = sscanf.sscanf("0xabc90", "%x")
    assert l==[703632], 'Unexpected!  l = '+str(l)
    # API error
    try:
        l = sscanf.sscanf()
    except TypeError:
        pass # this is expected - anything else should raise

    # finished successfully
    print('test_sscanf successful')
