from os.path import abspath, dirname, exists, join
import sys


# Try to guarantee our results are based on the local source code, not site-packages
_PYRAF_LOCAL = abspath(join(dirname(__file__), '..', 'lib'))
if exists(_PYRAF_LOCAL) and _PYRAF_LOCAL not in sys.path:
    sys.path.insert(0, _PYRAF_LOCAL)
