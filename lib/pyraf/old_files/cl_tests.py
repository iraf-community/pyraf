# NOTE: These currently do not work because there is no "simple.cl" file
#       in the repository. For that reason, these were also not ported to
#       "tests" for CI.
from __future__ import print_function

import time

from pyraf.cl2py import clscan, _parser, VarList, TypeCheck, Tree2Python
from pyraf.clparse import getParser
from pyraf.clscan import CLScanner, toklist


def test_cl2py():

    t0 = time.time()

    # scan file "simple.cl"

    filename = "simple.cl"
    lines = open(filename).read()
    scanner = clscan.CLScanner()
    tokens = scanner.tokenize(lines)
    t1 = time.time()

    # parse
    tree = _parser.parse(tokens, fname=filename)
    tree.filename = filename
    t2 = time.time()

    # first pass -- get variables

    vars = VarList(tree)

    # second pass -- check all expression types
    # type info is added to tree

    TypeCheck(tree, vars, '')

    # third pass -- generate python code

    pycode = Tree2Python(tree, vars)

    t3 = time.time()

    print("Scan:", t1-t0, "sec,   Parse:", t2-t1, "sec")
    print("CodeGen:", t3-t2, "sec")


def test_clparse():

    t0 = time.time()

    # scan file 'simple.cl'

    fnm = 'simple.cl'
    lines = open(fnm).read()
    scanner = clscan.CLScanner()
    tokens = scanner.tokenize(lines)
    t1 = time.time()

    # parse
    p = getParser()
    tree = p.parse(tokens, fname=fnm)
    t2 = time.time()

    print('Scan:', t1-t0, 'sec, Parse:', t2-t1, 'sec')


def test_clscan():
    s = CLScanner()

    # scan file 'simple.cl'

    lines = open('simple.cl').read()
    tokens = s.tokenize(lines)

    toklist(tokens[:30])
