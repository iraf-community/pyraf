#! /usr/bin/env python3
"""loadall.py: Load all the main packages in IRAF with verbose turned on
"""


import sys
import traceback

from pyraf import iraf

iraf.setVerbose()


def printcenter(s, length=70, char="-"):
    l1 = (length - len(s)) // 2
    l2 = length - l1 - len(s)
    print(l1 * char, s, l2 * char)


ptried = {}
npass = 0
ntotal = 0
plist = iraf.getPkgList()
keepGoing = 1
while keepGoing and (ntotal < len(plist)):
    plist.sort()
    nnew = 0
    npass = npass + 1
    printcenter("pass " + repr(npass) + " trying " + repr(len(plist)),
                char="=")
    for pkg in plist:
        if pkg not in ptried:
            ptried[pkg] = 1
            nnew = nnew + 1
            l1 = (70 - len(pkg)) // 2
            l2 = 70 - l1 - len(pkg)
            printcenter(pkg)
            if pkg == "digiphotx":
                print("""
                        Working around bug in digiphotx.
                        It screws up subsequent loading of digiphot tasks.
                        (It happens in IRAF too.)""")
            else:
                try:
                    iraf.load(pkg)
                except KeyboardInterrupt:
                    print('Interrupt')
                    keepGoing = 0
                    break
                except Exception as e:
                    sys.stdout.flush()
                    traceback.print_exc()
                    if e.__class__ == MemoryError:
                        keepGoing = 0
                        break
                    print("...continuing...\n")
    ntotal = ntotal + nnew
    printcenter("Finished pass " + repr(npass) + " new pkgs " + repr(nnew) +
                " total pkgs " + repr(ntotal),
                char="=")
    plist = iraf.getPkgList()
