#!/usr/bin/env python

# We use the local copy of stsci_distutils_hack, unless
# the user asks for the stpytools version
from __future__ import division # confidence high

import os
try :
    import stsci.tools.stsci_distutils_hack as H
except ImportError :
    import stsci_distutils_hack as H

H.run()


