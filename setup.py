#!/usr/bin/env python

# We use the local copy of stsci_distutils_hack, unless
# the user asks for the stpytools version
from __future__ import division # confidence high

import os, sys
HAS_TOOLS = True

try :
    import stsci.tools.stsci_distutils_hack as H
except ImportError:
    try:
        import stsci_distutils_hack as H
    except ImportError:
        HAS_TOOLS = False

# Needs latest version of tools
reqdver = 3.1
if HAS_TOOLS:
   import stsci.tools as ST
   HAS_TOOLS = float(ST.__version__[:3]) >= reqdver
   del ST

if HAS_TOOLS:
   H.run()
else:
    print('The "stsci.tools" package (v%0.1f) is required by PyRAF.'%reqdver)
    toolsLoc = os.path.abspath('.'+os.sep+'required_pkgs'+os.sep+'tools')
    if os.path.exists(toolsLoc):
        print("It has been included in your download, in the following directory.\n"+\
              "Please install it first, and then install PyRAF.\n\t"+\
              toolsLoc)
    else:
        print("Please download it from STScI and install it before installing PyRAF.\n"+\
              "If you downloaded PyRAF, it is included under 'required_pkgs'.")
    sys.exit(1)
