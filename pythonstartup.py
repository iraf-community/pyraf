# python startup file, rlw, 1998 Oct 7
import Numeric
from math import acos, asin, atan, atan2, ceil, cos, \
	cosh, exp, fabs, floor, fmod, log, log10, \
	modf, pi, pow, sin, sinh, sqrt, tan, tanh

# activate command completion with ctrl-g as completion key
# fix weird behavior for ctrl-z too

import rlcompleter
rlcompleter.readline.parse_and_bind("C-g: complete")
rlcompleter.readline.parse_and_bind("C-z: self-insert")

