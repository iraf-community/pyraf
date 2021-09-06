"""generic.py: John Aycock's little languages (SPARK) framework
"""

#  Copyright (c) 1998-2000 John Aycock
#
#  Permission is hereby granted, free of charge, to any person obtaining
#  a copy of this software and associated documentation files (the
#  "Software"), to deal in the Software without restriction, including
#  without limitation the rights to use, copy, modify, merge, publish,
#  distribute, sublicense, and/or sell copies of the Software, and to
#  permit persons to whom the Software is furnished to do so, subject to
#  the following conditions:
#
#  The above copyright notice and this permission notice shall be
#  included in all copies or substantial portions of the Software.
#
#  THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND,
#  EXPRESS OR IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF
#  MERCHANTABILITY, FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT.
#  IN NO EVENT SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY
#  CLAIM, DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT,
#  TORT OR OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE
#  SOFTWARE OR THE USE OR OTHER DEALINGS IN THE SOFTWARE.

# Modifications by R. White:
# - Allow named groups in scanner patterns (other than the ones
#   inserted by the class constructor.)
# - Speed up GenericScanner.tokenize().
#   + Keep a list (indexlist) of the group numbers to check.
#   + Break out of loop after finding a match, since more than
#     one of the primary patterns cannot match (by construction of
#     the pattern.)
# - Add optional value parameter to GenericParser.error.
# - Add check for assertion error in ambiguity resolution.



__version__ = 'SPARK-0.6.1rlw'

import re
from . import cltoken


def _namelist(instance):
    namelist, namedict, classlist = [], {}, [instance.__class__]
    for c in classlist:
        for b in c.__bases__:
            classlist.append(b)
        for name in c.__dict__.keys():
            if name not in namedict:
                namelist.append(name)
                namedict[name] = 1
    return namelist


class GenericScanner:

    def __init__(self):
        pattern = self.reflect()
        self.re = re.compile(pattern, re.VERBOSE)

        self.index2func = {}
        self.indexlist = []
        for name, number in self.re.groupindex.items():
            # allow other named groups
            if hasattr(self, 't_' + name):
                self.index2func[number - 1] = getattr(self, 't_' + name)
                self.indexlist.append(number - 1)

    def makeRE(self, name):
        doc = getattr(self, name).__doc__
        rv = f'(?P<{name[2:]}>{doc})'
        return rv

    def reflect(self):
        rv = []
        for name in _namelist(self):
            if name[:2] == 't_' and name != 't_default':
                rv.append(self.makeRE(name))

        rv.append(self.makeRE('t_default'))
        return '|'.join(rv)

    def error(self, s, pos):
        raise SyntaxError(f"Lexical error at position {pos}")

    def tokenize(self, s):
        pos = 0
        n = len(s)
        match = self.re.match
        indexlist = self.indexlist
        index2func = self.index2func
        while pos < n:
            m = match(s, pos)
            if m is None:
                self.error(s, pos)

            groups = m.groups()
            for i in indexlist:
                if groups[i] is not None:
                    index2func[i](groups[i])
                    # assume there is only a single match
                    break
            pos = m.end()

    def t_default(self, s):
        r'( . | \n )+'
        pass


class GenericParser:

    def __init__(self, start):
        self.rules = {}
        self.rule2func = {}
        self.rule2name = {}
        self.collectRules()
        self.startRule = self.augment(start)
        self.ruleschanged = 1

    _START = 'START'
    _EOF = 'EOF'

    #
    #  A hook for GenericASTBuilder and GenericASTMatcher.
    #
    def preprocess(self, rule, func):
        return rule, func

    def addRule(self, doc, func):
        rules = doc.split()

        index = []
        for i in range(len(rules)):
            if rules[i] == '::=':
                index.append(i - 1)
        index.append(len(rules))

        for i in range(len(index) - 1):
            lhs = rules[index[i]]
            rhs = rules[index[i] + 2:index[i + 1]]
            rule = (lhs, tuple(rhs))

            rule, fn = self.preprocess(rule, func)

            if lhs in self.rules:
                self.rules[lhs].append(rule)
            else:
                self.rules[lhs] = [rule]
            self.rule2func[rule] = fn
            self.rule2name[rule] = func.__name__[2:]
        self.ruleschanged = 1

    def collectRules(self):
        for name in _namelist(self):
            if name[:2] == 'p_':
                func = getattr(self, name)
                doc = func.__doc__
                self.addRule(doc, func)

    def augment(self, start):
        #
        #  Tempting though it is, this isn't made into a call
        #  to self.addRule() because the start rule shouldn't
        #  be subject to preprocessing.
        #
        startRule = (self._START, (start, self._EOF))
        self.rule2func[startRule] = lambda args: args[0]
        self.rules[self._START] = [startRule]
        self.rule2name[startRule] = ''
        return startRule

    def makeFIRST(self):
        # make the FIRST sets
        first = {}
        for key in self.rules.keys():
            first[key] = {}
        changed = 1
        npass = 0
        while (changed > 0):
            npass = npass + 1
            changed = 0
            for key, this in first.items():
                for lhs, rhs in self.rules[key]:
                    for token in rhs:
                        # add token or first[token] to this set
                        # also track whether token derives epsilon; if it
                        # does, need to add FIRST set for next token too
                        derivesEpsilon = 0
                        if token not in self.rules:
                            # this is a terminal
                            if token not in this:
                                this[token] = 1
                                changed = changed + 1
                        else:
                            # this is a nonterminal -- add its FIRST set
                            for ntkey in first[token].keys():
                                if ntkey == "":
                                    derivesEpsilon = 1
                                elif ntkey != key and ntkey not in this:
                                    this[ntkey] = 1
                                    changed = changed + 1
                        if not derivesEpsilon:
                            break
                    else:
                        # if get all the way through, add epsilon too
                        if "" not in this:
                            this[""] = 1
                            changed = changed + 1
        # make the rule/token lists
        self.makeTokenRules(first)

    def makeTokenRules(self, first):
        # make dictionary indexed by (nextSymbol, nextToken) with
        # list of all rules for nextSymbol that could produce nextToken
        tokenRules = {}
        # make a list of all terminal tokens
        allTokens = {}
        for key, rule in self.rules.items():
            for lhs, rhs in rule:
                for token in rhs:
                    if token not in self.rules:
                        # this is a terminal
                        allTokens[token] = 1
        for nextSymbol, flist in first.items():
            for nextToken in flist.keys():
                tokenRules[(nextSymbol, nextToken)] = []
            if "" in flist:
                for nextToken in allTokens.keys():
                    tokenRules[(nextSymbol, nextToken)] = []
            for prule in self.rules[nextSymbol]:
                prhs = prule[1]
                done = {}
                for element in prhs:
                    pflist = first.get(element)
                    if pflist is not None:
                        if element not in done:
                            done[element] = 1
                            # non-terminal
                            for nextToken in pflist.keys():
                                if nextToken and nextToken not in done:
                                    done[nextToken] = 1
                                    tokenRules[(nextSymbol,
                                                nextToken)].append(prule)
                        if "" not in pflist:
                            break
                    else:
                        # terminal token
                        if element not in done:
                            done[element] = 1
                            tokenRules[(nextSymbol, element)].append(prule)
                        break
                else:
                    # this entire rule can produce null
                    # add it to all FIRST symbols and to null list
                    tokenRules[(nextSymbol, "")].append(prule)
                    for nextToken in allTokens.keys():
                        if nextToken not in done:
                            done[nextToken] = 1
                            tokenRules[(nextSymbol, nextToken)].append(prule)
        self.tokenRules = tokenRules

    #
    #  An Earley parser, as per J. Earley, "An Efficient Context-Free
    #  Parsing Algorithm", CACM 13(2), pp. 94-102.  Also J. C. Earley,
    #  "An Efficient Context-Free Parsing Algorithm", Ph.D. thesis,
    #  Carnegie-Mellon University, August 1968, p. 27.
    #

    def typestring(self, token):
        return None

    def error(self, token, value=None):
        raise SyntaxError(f"Syntax error at or near `{token}' token")

    def parse(self, tokens):
        tree = {}
        # add a Token instead of a string so references to
        # token.type in buildState work for EOF symbol
        tokens.append(cltoken.Token(self._EOF))
        states = (len(tokens) + 1) * [None]
        states[0] = [(self.startRule, 0, 0)]

        if self.ruleschanged:
            self.makeFIRST()
            self.ruleschanged = 0

        for i in range(len(tokens)):
            states[i + 1] = []

            if states[i] == []:
                break
            self.buildState(tokens[i], states, i, tree)

        if i < len(tokens) - 1 or states[i + 1] != [(self.startRule, 2, 0)]:
            del tokens[-1]
            self.error(tokens[i - 1])
        rv = self.buildTree(tokens, tree, ((self.startRule, 2, 0), i + 1))
        del tokens[-1]
        return rv

    def buildState(self, token, states, i, tree):
        state = states[i]
        predicted = {}
        completed = {}

        # optimize inner loops
        state_append = state.append
        tokenRules_get = self.tokenRules.get
        for item in state:
            rule, pos, parent = item
            lhs, rhs = rule

            #
            #  A -> a . (completer)
            #
            if pos == len(rhs):
                # track items completed within this rule
                if parent == i:
                    if lhs in completed:
                        completed[lhs].append((item, i))
                    else:
                        completed[lhs] = [(item, i)]

                lhstuple = (lhs,)
                for prule, ppos, pparent in states[parent]:
                    plhs, prhs = prule
                    if prhs[ppos:ppos + 1] == lhstuple:
                        new = (prule, ppos + 1, pparent)
                        key = (new, i)
                        if key in tree:
                            tree[key].append((item, i))
                        else:
                            state_append(new)
                            tree[key] = [(item, i)]
                continue

            nextSym = rhs[pos]

            #
            #  A -> a . B (predictor)
            #
            if nextSym in self.rules:
                if nextSym in predicted:
                    #
                    # this was already predicted -- but if it was
                    # also completed entirely within this step, then
                    # need to add completed version here too
                    #
                    if nextSym in completed:
                        new = (rule, pos + 1, parent)
                        key = (new, i)
                        if key in tree:
                            tree[key].extend(completed[nextSym])
                        else:
                            state_append(new)
                            tree[key] = completed[nextSym]
                else:
                    predicted[nextSym] = 1
                    #
                    # Predictor using FIRST sets
                    # Use cached list for this (nextSym, token) combo
                    #
                    for prule in tokenRules_get((nextSym, token.type), []):
                        state_append((prule, 0, i))

            #
            #  A -> a . c (scanner)
            #
            elif token.type == nextSym:
                # assert new not in states[i+1]
                states[i + 1].append((rule, pos + 1, parent))

    def buildTree(self, tokens, tree, root):
        stack = []
        self.buildTree_r(stack, tokens, -1, tree, root)
        return stack[0]

    def buildTree_r(self, stack, tokens, tokpos, tree, root):
        (rule, pos, parent), state = root

        while pos > 0:
            want = ((rule, pos, parent), state)
            if want not in tree:
                #
                #  Since pos > 0, it didn't come from closure,
                #  and if it isn't in tree[], then there must
                #  be a terminal symbol to the left of the dot.
                #  (It must be from a "scanner" step.)
                #
                pos = pos - 1
                state = state - 1
                stack.insert(0, tokens[tokpos])
                tokpos = tokpos - 1
            else:
                #
                #  There's a NT to the left of the dot.
                #  Follow the tree pointer recursively (>1
                #  tree pointers from it indicates ambiguity).
                #  Since the item must have come about from a
                #  "completer" step, the state where the item
                #  came from must be the parent state of the
                #  item the tree pointer points to.
                #
                children = tree[want]
                if len(children) > 1:
                    # RLW I'm leaving in this try block for the moment,
                    # RLW although the current ambiguity resolver never
                    # RLW raises and assertion error (which I think may
                    # RLW be a bug.)
                    try:
                        child = self.ambiguity(children)
                    except AssertionError:
                        del tokens[-1]
                        print(stack[0])
                        # self.error(tokens[tokpos], 'Parsing ambiguity'+str(children[:]))
                        self.error(stack[0],
                                   'Parsing ambiguity' + str(children[:]))
                else:
                    child = children[0]

                tokpos = self.buildTree_r(stack, tokens, tokpos, tree, child)
                pos = pos - 1
                (crule, cpos, cparent), cstate = child
                state = cparent

        lhs, rhs = rule
        result = self.rule2func[rule](stack[:len(rhs)])
        stack[:len(rhs)] = [result]
        return tokpos

    def ambiguity(self, children):
        #
        #  XXX - problem here and in collectRules() if the same
        #        rule appears in >1 method.  But in that case the
        #        user probably gets what they deserve :-)  Also
        #        undefined results if rules causing the ambiguity
        #        appear in the same method.
        # RLW Modified so it uses rule as the key
        # RLW If we stick with this, can eliminate rule2name
        #
        sortlist = []
        name2index = {}
        for i in range(len(children)):
            ((rule, pos, parent), index) = children[i]
            lhs, rhs = rule
            # name = self.rule2name[rule]
            sortlist.append((len(rhs), rule))
            name2index[rule] = i
        sortlist.sort()
        alist = [s[1] for s in sortlist]
        return children[name2index[self.resolve(alist)]]

    def resolve(self, list):
        #
        #  Resolve ambiguity in favor of the shortest RHS.
        #  Since we walk the tree from the top down, this
        #  should effectively resolve in favor of a "shift".
        #
        # RLW Question -- This used to raise an assertion error
        # RLW here if there were two choices with the same RHS length.
        # RLW Why doesn't that happen now?  Looks like an error?
        return list[0]


#
#  GenericASTBuilder automagically constructs a concrete/abstract syntax tree
#  for a given input.  The extra argument is a class (not an instance!)
#  which supports the "__setslice__" and "__len__" methods.
#
#  XXX - silently overrides any user code in methods.
#


class GenericASTBuilder(GenericParser):

    def __init__(self, AST, start):
        GenericParser.__init__(self, start)
        self.AST = AST

    def preprocess(self, rule, func):

        def rebind(lhs, self=self):
            return (
                lambda args, lhs=lhs, self=self: self.buildASTNode(args, lhs))

        lhs, rhs = rule
        return rule, rebind(lhs)

    def buildASTNode(self, args, lhs):
        children = []
        for arg in args:
            if isinstance(arg, self.AST):
                children.append(arg)
            else:
                children.append(self.terminal(arg))
        return self.nonterminal(lhs, children)

    def terminal(self, token):
        return token

    def nonterminal(self, type, args):
        rv = self.AST(type)
        rv[:len(args)] = args
        return rv


#
#  GenericASTTraversal is a Visitor pattern according to Design Patterns.  For
#  each node it attempts to invoke the method n_<node type>, falling
#  back onto the default() method if the n_* can't be found.  The preorder
#  traversal also looks for an exit hook named n_<node type>_exit (no default
#  routine is called if it's not found).  To prematurely halt traversal
#  of a subtree, call the prune() method -- this only makes sense for a
#  preorder traversal.
#


class GenericASTTraversalPruningException(Exception):
    pass


class GenericASTTraversal:

    def __init__(self, ast):
        self.ast = ast
        self.collectRules()

    def collectRules(self):
        self.rules = {}
        self.exitrules = {}
        for name in _namelist(self):
            if name[:2] == 'n_':
                self.rules[name[2:]] = getattr(self, name)
                if name[-5:] == '_exit':
                    self.exitrules[name[2:-5]] = getattr(self, name)

    def prune(self):
        raise GenericASTTraversalPruningException()

    def preorder(self, node=None):
        if node is None:
            node = self.ast

        try:
            name = node.type
            func = self.rules.get(name)
            if func is None:
                # add rule to cache so next time it is faster
                func = self.default
                self.rules[name] = func
            func(node)
        except GenericASTTraversalPruningException:
            return

        for kid in node:
            #          if kid.type=='term' and len(kid._kids)==3 and kid._kids[1].type=='/':
            #              # Not the place to check for integer divsion - the type is
            #              # either INTEGER or IDENT (and we dont know yet what the
            #              # underlying type of the IDENT is...)
            #              print(kid._kids[0].type, kid._kids[1].type, kid._kids[2].type)
            self.preorder(kid)

        func = self.exitrules.get(name)
        if func is not None:
            func(node)

    def postorder(self, node=None):
        if node is None:
            node = self.ast

        for kid in node:
            self.postorder(kid)

        name = node.type
        func = self.rules.get(name)
        if func is None:
            # add rule to cache so next time it is faster
            func = self.default
            self.rules[name] = func
        func(node)

    def default(self, node):
        pass


#
#  GenericASTMatcher.  AST nodes must have "__getitem__" and "__cmp__"
#  implemented.
#
#  XXX - makes assumptions about how GenericParser walks the parse tree.
#


class GenericASTMatcher(GenericParser):

    def __init__(self, start, ast):
        GenericParser.__init__(self, start)
        self.ast = ast

    def preprocess(self, rule, func):

        def rebind(func, self=self):
            return (
                lambda args, func=func, self=self: self.foundMatch(args, func))

        lhs, rhs = rule
        rhslist = list(rhs)
        rhslist.reverse()

        return (lhs, tuple(rhslist)), rebind(func)

    def foundMatch(self, args, func):
        func(args[-1])
        return args[-1]

    def match_r(self, node):
        self.input.insert(0, node)
        children = 0

        for child in node:
            if children == 0:
                self.input.insert(0, '(')
            children = children + 1
            self.match_r(child)

        if children > 0:
            self.input.insert(0, ')')

    def match(self, ast=None):
        if ast is None:
            ast = self.ast
        self.input = []

        self.match_r(ast)
        self.parse(self.input)

    def resolve(self, list):
        #
        #  Resolve ambiguity in favor of the longest RHS.
        #
        return list[-1]
