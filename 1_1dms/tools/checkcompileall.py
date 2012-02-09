#! /usr/bin/env python

"""checkcompileall.py: Read the output from compileallcl and print just the errors

$Id$
"""
from __future__ import division # confidence high
import re, sys

taskpat = re.compile(r'\d')

# read input from stdin
lines = sys.stdin.read().split('\n')

# keep track of current package & task and print them only if error is found
cpackage = None
ctask = None
expectTask = True
inError = False
for line in lines:
    if line.startswith("====="):
        print line
        expectTask = True
        if inError:
            inError = False
            print
    elif line.startswith("-----"):
        cpackage = line
        expectTask = False
        if inError:
            inError = False
            print
    elif taskpat.match(line):
        ctask = line
        expectTask = True
        if inError:
            inError = False
            print
    elif line == "...continuing...":
        expectTask = True
        print
        inError = False
    elif not line:
        if inError:
            inError = False
            print
    elif expectTask:
        # Some sort of unexpected output, so print it
        if cpackage:
            print cpackage
            cpackage = None
        if ctask:
            print ctask
            ctask = None
        print line
        inError = True
