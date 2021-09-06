"""clparse.py: Parse IRAF CL

R. White, 1999 August 24
"""


from .generic import GenericASTBuilder, GenericASTTraversal
from .clast import AST
from .cltoken import Token


class CLStrictParser(GenericASTBuilder):
    """Strict version of CL parser (flags some program errors that CL accepts)

    This can be used as the parser to get a lint-like mode.
    Use CLParser (which adds some more rules to allow the same
    errors as the CL) to run CL programs.
    """

    def __init__(self, AST, start='program'):
        GenericASTBuilder.__init__(self, AST, start)
        # list of tokens that should not be flattened by nonterminal()
        self.primaryTypes = {
            'proc_stmt': 1,
            'param_declaration_block': 1,
            'declaration_stmt': 1,
            'declaration_block': 1,
            'var_name': 1,
            'decl_init_list': 1,
            'decl_init_value': 1,
            'decl_array_dims': 1,
            'array_subscript': 1,
            'list_flag': 1,
            'body_block': 1,
            'statement_block': 1,
            'nonnull_stmt': 1,
            'osescape_stmt': 1,
            'assignment_stmt': 1,
            'task_call_stmt': 1,
            'if_stmt': 1,
            'for_stmt': 1,
            'while_stmt': 1,
            'break_stmt': 1,
            'next_stmt': 1,
            'return_stmt': 1,
            'goto_stmt': 1,
            'label_stmt': 1,
            'switch_stmt': 1,
            'case_block': 1,
            'case_stmt_block': 1,
            'case_value': 1,
            'compound_stmt': 1,
            'empty_compound_stmt': 1,
            'task_arglist': 1,
            'comma_arglist': 1,
            'fn_arglist': 1,
            'arg': 1,
            'empty_arg': 1,
            'non_empty_arg': 1,
            'no_arg': 1,
            'param_name': 1,
            'opt_comma': 1,
            'bool_expr': 1,
        }
        self._currentFname = None

    def parse(self, tokens, fname=None):
        """ Override this, only so we can add the optional fname arg.
            Delegate all parse logic to parent. """
        self._currentFname = fname
        return GenericASTBuilder.parse(self, tokens)

    def typestring(self, token):
        try:
            return token.type
        except AttributeError:
            return token

    def error(self, token, value=None):
        finfo = ''
        if self._currentFname:
            finfo = 'file "' + self._currentFname + '"'
        if hasattr(token, 'lineno'):
            if len(finfo):
                finfo += ', '
            errmsg = f"CL syntax error at `{token}' ({finfo}line {token.lineno:d})"
        else:
            if len(finfo):
                finfo = '(' + finfo + ')'
            errmsg = f"CL syntax error at `{token}' {finfo}"
        if value is not None:
            errmsg = errmsg + "\n" + str(value)
        raise SyntaxError(errmsg)

    def p_program(self, args):
        '''
                program ::= proc_stmt param_declaration_block body_block
                program ::= statement_block

                proc_stmt ::= PROCEDURE IDENT proc_arguments end_of_line
                proc_arguments ::= ( proc_arglist )
                proc_arguments ::=
                proc_arglist ::= IDENT
                proc_arglist ::= proc_arglist , IDENT
                proc_arglist ::=

                param_declaration_block ::= declaration_block

                declaration_block ::= declaration_list
                declaration_block ::=
                declaration_list ::= declaration_stmt end_of_line
                declaration_list ::= declaration_list declaration_stmt end_of_line
                declaration_stmt ::= TYPE decl_spec_list

                decl_spec_list ::= decl_spec
                decl_spec_list ::= decl_spec_list , decl_spec
                decl_spec ::= list_flag var_name opt_init_val declaration_options
                list_flag ::= *
                list_flag ::=
                decl_array_dims ::= INTEGER
                decl_array_dims ::= decl_array_dims , INTEGER
                var_name ::= IDENT
                var_name ::= IDENT [ decl_array_dims ]
                opt_init_val ::= = decl_init_list
                opt_init_val ::=
                decl_init_list ::= tdecl_init_list
                tdecl_init_list ::= decl_init_value
                tdecl_init_list ::= tdecl_init_list , decl_init_value
                decl_init_value ::= constant
                declaration_options ::= { decl_init_list , decl_options_list NEWLINE }
                declaration_options ::= { decl_options_list NEWLINE }
                declaration_options ::= { decl_init_list NEWLINE }
                declaration_options ::=
                decl_options_list ::= decl_option
                decl_options_list ::= decl_options_list , decl_option
                decl_option ::= IDENT = constant

                body_block ::= BEGIN end_of_line statement_block END end_of_line

                statement_block ::= statement_list
                statement_list ::= statement_list statement
                statement_list ::=
                statement ::= declaration_stmt end_of_line
                statement ::= nonnull_stmt end_of_line
                statement ::= end_of_line
                statement ::= label_stmt statement
                label_stmt ::= IDENT :
                end_of_line ::= NEWLINE
                end_of_line ::= ;

                nonnull_stmt ::= osescape_stmt
                nonnull_stmt ::= assignment_stmt
                nonnull_stmt ::= if_stmt
                nonnull_stmt ::= for_stmt
                nonnull_stmt ::= while_stmt
                nonnull_stmt ::= switch_stmt
                nonnull_stmt ::= break_stmt
                nonnull_stmt ::= next_stmt
                nonnull_stmt ::= return_stmt
                nonnull_stmt ::= goto_stmt
                nonnull_stmt ::= inspect_stmt
                nonnull_stmt ::= task_call_stmt
                nonnull_stmt ::= task_pipe_stmt
                nonnull_stmt ::= task_bkgd_stmt
                nonnull_stmt ::= { statement_list }

                opt_newline ::= NEWLINE
                opt_newline ::=
                opt_comma ::= ,
                opt_comma ::=
                compound_stmt ::= opt_newline one_compound_stmt
                one_compound_stmt ::= empty_compound_stmt
                one_compound_stmt ::= nonnull_stmt
                empty_compound_stmt ::= ;

                osescape_stmt ::= OSESCAPE

                assignment_stmt ::= IDENT assignop expr
                assignment_stmt ::= array_ref assignop expr
                assignop ::= =
                assignop ::= ASSIGNOP

                if_stmt ::= IF ( bool_expr ) compound_stmt else_clause
                else_clause ::= opt_newline ELSE compound_stmt
                else_clause ::=

                while_stmt ::= WHILE ( bool_expr ) compound_stmt
                break_stmt ::= BREAK
                next_stmt ::= NEXT
                return_stmt ::= RETURN
                goto_stmt ::= GOTO IDENT
                inspect_stmt ::= = expr

                for_stmt ::= FOR ( opt_assign_stmt ; opt_bool ; opt_assign_stmt ) compound_stmt
                opt_assign_stmt ::= assignment_stmt
                opt_assign_stmt ::=
                opt_bool ::= bool_expr
                opt_bool ::=

                switch_stmt ::= SWITCH ( expr ) case_block
                case_block ::= opt_newline { case_stmt_list default_stmt_block NEWLINE }
                case_stmt_list ::= case_stmt_block
                case_stmt_list ::= case_stmt_list case_stmt_block
                case_stmt_block ::= opt_newline CASE case_value_list : compound_stmt
                case_value_list ::= case_value
                case_value_list ::= case_value_list , case_value
                case_value ::= INTEGER
                case_value ::= STRING
                case_value ::= QSTRING
                case_value ::= EOF
                default_stmt_block ::= opt_newline DEFAULT : compound_stmt
                default_stmt_block ::=

                task_call_stmt ::= IDENT task_arglist
                task_arglist ::= ( comma_arglist2 )
                task_arglist ::= ( non_expr_arg )
                task_arglist ::= ( no_arg )
                task_arglist ::= comma_arglist
                no_arg ::=

                task_pipe_stmt ::= task_call_stmt PIPE task_call_stmt
                task_pipe_stmt ::= task_pipe_stmt PIPE task_call_stmt

                task_bkgd_stmt ::= task_call_stmt BKGD
                task_bkgd_stmt ::= task_pipe_stmt BKGD

                comma_arglist ::= ncomma_arglist
                comma_arglist ::=
                ncomma_arglist ::= non_empty_arg
                ncomma_arglist ::= empty_arg , arg
                ncomma_arglist ::= ncomma_arglist , arg

                comma_arglist2 ::= arg , arg
                comma_arglist2 ::= comma_arglist2 , arg

                non_empty_arg ::= expr
                non_empty_arg ::= non_expr_arg
                non_expr_arg ::= keyword_arg
                non_expr_arg ::= bool_arg
                non_expr_arg ::= redir_arg
                arg ::= non_empty_arg
                arg ::= empty_arg
                empty_arg ::=

                keyword_arg ::= param_name = expr
                bool_arg ::= param_name +
                bool_arg ::= param_name -
                param_name ::= IDENT
                redir_arg ::= REDIR expr

                bool_expr ::= expr

                expr ::= expr LOGOP not_expr
                expr ::= not_expr
                not_expr ::= ! comp_expr
                not_expr ::= comp_expr
                comp_expr ::= comp_expr COMPOP concat_expr
                comp_expr ::= concat_expr
                concat_expr ::= concat_expr // arith_expr
                concat_expr ::= arith_expr
                arith_expr ::= arith_expr + term
                arith_expr ::= arith_expr - term
                arith_expr ::= term
                term ::= term * factor
                term ::= term / factor
                term ::= term % factor
                term ::= factor
                factor ::= - factor
                factor ::= + factor
                factor ::= power
                power ::= power ** atom
                power ::= atom

                atom ::= number
                atom ::= IDENT
                atom ::= array_ref
                atom ::= STRING
                atom ::= QSTRING
                atom ::= EOF
                atom ::= BOOL
                atom ::= function_call
                atom ::= ( expr )

                number ::= INTEGER
                number ::= FLOAT
                number ::= SEXAGESIMAL
                number ::= INDEF

                array_subscript ::= expr
                array_subscript ::= array_subscript , expr
                array_ref ::= IDENT [ array_subscript ]

                function_call ::= IDENT ( fn_arglist )

                fn_arglist ::= comma_arglist

                constant ::= number
                constant ::= - number
                constant ::= + number
                constant ::= STRING
                constant ::= QSTRING
                constant ::= EOF
                constant ::= BOOL
        '''
        pass

    def resolve(self, list):
        # resolve ambiguities
        # choose shortest; raise exception if two have same length
        rhs0 = list[0][1]
        rhs1 = list[1][1]
        assert len(rhs0) != len(rhs1)
        # print 'Ambiguity:'
        # for rule in list:
        #       lhs, rhs = rule
        #       print len(rhs), rule
        return list[0]

    def nonterminal(self, atype, args):
        #
        # Flatten AST a bit by not making nodes if there's only
        # one child, but retain a few primary structural
        # elements.
        #
        if len(args) == 1 and atype not in self.primaryTypes:
            return args[0]
        return GenericASTBuilder.nonterminal(self, atype, args)


class CLParser(CLStrictParser):
    """Sloppy version of CL parser, with extra rules allowing some errors"""

    def __init__(self, AST, start='program'):
        CLStrictParser.__init__(self, AST, start)

    def p_additions(self, args):
        '''
                program ::= statement_block END NEWLINE
                task_arglist ::= ( comma_arglist
                task_arglist ::= comma_arglist )
                inspect_stmt ::= IDENT =
        '''
        # - end without matching begin
        # - task argument list with missing closing parenthesis
        # - task argument list with missing opening parenthesis
        # - peculiar 'var =' form of inspect statement (as opposed to
        #   normal '= var' form.)
        #
        #   Note that the missing parentheses versions of
        #   argument lists also permit parsing of 'pipe args'
        #   in format taskname(arg, arg, | task2 arg, arg)
        pass


class EclParser(CLParser):

    def __init__(self, AST, start='program'):
        CLParser.__init__(self, AST, start)
        self.primaryTypes['iferr_stmt'] = 1

    def p_additions2(self, args):
        '''
                nonnull_stmt ::= iferr_stmt
                iferr_stmt    ::= if_kind guarded_stmt except_action
                iferr_stmt    ::= if_kind guarded_stmt opt_newline THEN except_action
                iferr_stmt    ::= if_kind guarded_stmt opt_newline THEN except_action opt_newline ELSE else_action
                if_kind ::= IFERR
                if_kind ::= IFNOERR
                guarded_stmt  ::=  { opt_newline statement_list }
                except_action ::= compound_stmt
                else_action   ::= compound_stmt
        '''
        pass


#
# list tree
#


class PrettyTree(GenericASTTraversal):

    def __init__(self, ast, terminal=1):
        GenericASTTraversal.__init__(self, ast)
        self.terminal = terminal
        self.indent = 0
        self.nodeCount = 0
        self.preorder()
        print()
        print(self.nodeCount, 'total nodes in tree')

    def n_NEWLINE(self, node):
        self.nodeCount = self.nodeCount + 1

    def n_compound_stmt(self, node):
        self.indent = self.indent + 1
        # self.printIndentNode(node)
        self.default(node)
        self.nodeCount = self.nodeCount + 1

    def n_compound_stmt_exit(self, node):
        self.indent = self.indent - 1
        self.printIndentNode(node, tail='_exit')
        # self.default(node,tail='_exit')

    def n_declaration_block(self, node):
        # dedent declaration blocks
        self.indent = self.indent - 1
        self.default(node)
        self.nodeCount = self.nodeCount + 1

    def n_declaration_block_exit(self, node):
        self.indent = self.indent + 1
        self.default(node, tail='_exit')
        print()

    def n_BEGIN(self, node):
        self.printIndentNode(node)
        self.indent = self.indent + 1
        self.nodeCount = self.nodeCount + 1

    def n_END(self, node):
        self.indent = self.indent - 1
        self.printIndentNode(node)
        self.nodeCount = self.nodeCount + 1

    def n_nonnull_stmt(self, node):
        self.printIndentNode(node)
        self.nodeCount = self.nodeCount + 1

    def n_declaration_stmt(self, node):
        self.printIndentNode(node)
        self.nodeCount = self.nodeCount + 1

    def n_iferr_stmt(self, node):
        self.printIndentNode(node)
        self.nodeCount += 1

    # print newline and indent

    def printIndent(self):
        print('\n', end=' ')
        for i in range(self.indent):
            print('   ', end=' ')

    # print newline, indent, and token

    def printIndentNode(self, node, tail=''):
        self.printIndent()
        self.default(node, tail=tail)

    def default(self, node, tail=''):
        if node.type == '}':
            self.printIndent()
        if isinstance(node, Token) or (not self.terminal):
            print(repr(node) + tail, end=' ')
        self.nodeCount = self.nodeCount + 1


class TreeList(GenericASTTraversal):

    def __init__(self, ast, terminal=0):
        GenericASTTraversal.__init__(self, ast)
        self.terminal = terminal
        self.indent = ''
        # self.postorder()
        self.preorder()

    def n_compound_stmt(self, node):
        self.indent = self.indent + '\t'

    def n_compound_stmt_exit(self, node):
        self.indent = self.indent[:-1]

    def default(self, node):
        if node.type == 'NEWLINE':
            print('\n' + self.indent, end=' ')
        elif isinstance(node, Token) or (not self.terminal):
            print(node, end=' ')


def treelist(ast, terminal=1):
    PrettyTree(ast, terminal)


def getParser():
    from . import pyrafglobals
    if pyrafglobals._use_ecl:
        _parser = EclParser(AST)
    else:
        _parser = CLParser(AST)
    return _parser


def parse(tokens, fname=None):
    global _parser
    return _parser.parse(tokens, fname=fname)
