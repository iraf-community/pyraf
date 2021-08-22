"""cl tokenizer/scanner using John Aycock's little languages (SPARK) framework

This version uses a context-sensitive pattern stack

R. White, 1999 September 10
"""


from .cgeneric import ContextSensitiveScanner
from .generic import GenericScanner
from .cltoken import Token
import re
from stsci.tools import irafutils
from . import pyrafglobals

# contexts for scanner

_START_LINE_MODE = 0  # beginning of line
_COMMAND_MODE = 1  # simple command mode
_COMPUTE_START_MODE = 2  # initial compute mode (similar to command mode)
_COMPUTE_EQN_MODE = 3  # compute mode in task arg when equation-mode
# change flag has been seen.  Reverts to
# _COMPUTE_START_MODE on comma, redirection, etc.
_COMPUTE_MODE = 4  # compute (script, equation) mode
_SWALLOW_NEWLINE_MODE = 5  # mode at points where embedded newlines allowed
_ACCEPT_REDIR_MODE = 6  # mode at points where redirection allowed

# ---------------------------------------------------------------------
# Regular Expressions for additional string replacement
# ---------------------------------------------------------------------
#
# Match embedded comments in a multi-line string
# Matches escaped newline followed by line with free-standing comment,
# which we ignore to match unusual (ahem) IRAF behavior.

comment_pat = re.compile(r'\\\s*\n\s*#.*\n\s*')

# needed to prevent certain escapes to be protected to match IRAF
# string behavior (only \\, \b, \n, \r, \t, \digits are converted into
# special characters, all other's are left as is)

special_escapes = re.compile(r'[\\\\]*(\\[^fnrt\\\'"\d])')


def filterEscapes(instr):
    """Turn all backslashes that aren't special character for IRAF into
    double backslashes"""

    return special_escapes.sub(r'\\\1', instr)


# ---------------------------------------------------------------------
# Scanners for various contexts
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# BasicScanner: tokens recognized in all modes
# ---------------------------------------------------------------------


class _BasicScanner_1(GenericScanner):
    """Scanner class for tokens that can be recognized late"""

    def t_whitespace(self, s, m, parent):
        r'[ \t]+'
        pass

    def t_newline(self, s, m, parent):
        r'\n'
        parent.addToken(type='NEWLINE')
        parent.lineno = parent.lineno + 1
        # reset mode at start of each line (unless newline was matched
        # as part of another pattern)
        parent.startLine()

    def t_rparen(self, s, m, parent):
        r'\)'
        parent.addToken(type=')')
        del parent.current[-1]
        parent.parencount = parent.parencount - 1
        # add , as argument separator after this
        if parent.current and parent.current[-1] == _COMMAND_MODE:
            parent.argsep = ','

    def t_pipe(self, s, m, parent):
        r'\|&?'
        # pipe is always recognized (it turns out)
        # this must be after the '||' pattern
        parent.addToken(type='PIPE', attr=s)
        # Pipe symbol puts us in start-line mode, but leaves
        # paren count (because pipes can occur inside task parentheses)
        parent.startLine(parencount=parent.parencount)
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_bkgd(self, s, m, parent):
        r'&'
        # background execution
        parent.addToken(type='BKGD', attr=s)

    def t_default(self, s, m, parent):
        r'.'
        parent.addToken(type=s)


class _BasicScanner_2:
    """Scanner class for tokens that must be recognized before those defined
    in the _BasicScanner_1 class.
    """

    def t_backslash(self, s, m, parent):
        r'\\[ \t]*\n'
        # trailing '\' completely absorbed
        # This allows spaces after \ and before newline -- I do not
        # allow that inside quotes.
        parent.lineno = parent.lineno + 1

    def t_colon(self, s, m, parent):
        r':'
        parent.addToken(type=s)
        # add a newline after colon (which may appear in
        # label or case stmt) and go to start-line mode
        parent.addToken(type='NEWLINE')
        parent.startLine()


class _BasicScanner_3:
    """Scanner class for Tokens that must be recognized before those defined
    in the _BasicScanner_2 or _BasicScanner_1 classes.
    """

    def t_complex_redir(self, s, m, parent):
        r'> (>? ( [GIP]+ | & ) | >)'
        # matches >> >& >>& >G >I >P >>G >>GI etc.
        parent.addToken(type='REDIR', attr=s)
        # XXX may not need following -- I think redirection in
        # XXX compute-eqn mode should always be trapped by
        # XXX accept-REDIR mode, and exitComputeEqnMode does
        # XXX not do anything in other modes
        parent.exitComputeEqnMode()
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_comment(self, s, m, parent):
        r'\#(?P<Comment>.*)'
        # skip comment, leaving newline in string
        # look for special mode-shifting commands
        comment = m.group('Comment')
        if comment[:1] == '{':
            parent.default_mode = _COMPUTE_START_MODE
        elif comment[:1] == '}':
            parent.default_mode = _COMMAND_MODE

    def t_osescape(self, s, m, parent):
        r'(^|\n)[ \t]*!.*'
        # Host OS command escape.  Strip off everything
        # up through the '!'.
        if s[0] == '\n':
            parent.addToken(type='NEWLINE')
            parent.lineno = parent.lineno + 1
        cmd = s.strip()[1:]
        parent.addToken(type='OSESCAPE', attr=cmd.strip())

    def t_singlequote(self, s, m, parent):
        r"' [^'\\\n]* ( ( ((\\(.|\n)|\n)[\s?]*) | '' ) [^'\\\n]* )*'"
        # this pattern allows both escaped embedded quotes and
        # embedded double quotes ('embedded''quotes')
        # it also allows escaped newlines
        if parent.current[-1] == _COMMAND_MODE:
            parent.addToken(type=parent.argsep)
            parent.argsep = ','

        nline = _countNewlines(s)
        # Recognize and remove any embedded comments
        s = comment_pat.sub('', s)

        s = filterEscapes(
            irafutils.removeEscapes(irafutils.stripQuotes(s), quoted=1))
        # We use a different type for quoted strings to protect them
        # against conversion to other token types by enterComputeEqnMode
        parent.addToken(type='QSTRING', attr=s)
        parent.lineno = parent.lineno + nline

    def t_doublequote(self, s, m, parent):
        r'" [^"\\\n]* ( ( ((\\(.|\n)|\n)[\s?]*) | "" ) [^"\\\n]* )* "'
        if parent.current[-1] == _COMMAND_MODE:
            parent.addToken(type=parent.argsep)
            parent.argsep = ','

        nline = _countNewlines(s)

        # Recognize and remove any embedded comments
        s = comment_pat.sub('', s)

        s = filterEscapes(
            irafutils.removeEscapes(irafutils.stripQuotes(s), quoted=1))
        parent.addToken(type='QSTRING', attr=s)
        parent.lineno = parent.lineno + nline

    def t_semicolon(self, s, m, parent):
        r';'
        parent.addToken(type=';')
        # usually we reset mode just like on newline
        # if semicolon inside parentheses, just stay in compute mode
        # this occurs legally only in the (e1;e2;e3) clause of a `for' stmt
        if parent.parencount <= 0:
            parent.startLine()


# addition for sloppy scanner
# ignores binary data embedded in CL files


class _LaxScanner:

    def t_default(self, s, m, parent):
        r'.'
        # skip binary data
        if '\x1a' < s < '\x7f':
            parent.addToken(type=s)


# ---------------------------------------------------------------------
# StartScanner: Tokens recognized in start-line mode
# ---------------------------------------------------------------------


class _StartScanner_1(_BasicScanner_1):

    def t_ident(self, s, m, parent):
        r'[a-zA-Z\$_][a-zA-Z\$_\d.]*'
        # Go to command mode
        parent.addIdent(s, mode=parent.default_mode)

    def t_lparen(self, s, m, parent):
        r'\('
        parent.addToken(type='(')
        parent.current.append(_COMPUTE_MODE)
        parent.parencount = parent.parencount + 1
        # redirection can follow open parens
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_equals(self, s, m, parent):
        r'='
        parent.addToken(type=s)
        parent.current.append(_COMPUTE_MODE)

    def t_help(self, s, m, parent):
        r'\?\??'
        if len(s) == 2:
            parent.addIdent('allPkgHelp', mode=parent.default_mode)
        else:
            parent.addIdent('pkgHelp', mode=parent.default_mode)


class _StrictStartScanner(_BasicScanner_3, _BasicScanner_2, _StartScanner_1):
    """Strict scanner class for tokens recognized in start-line mode"""
    pass


class _StartScanner(_LaxScanner, _StrictStartScanner):
    """Scanner class for tokens recognized in start-line mode"""
    pass


# ---------------------------------------------------------------------
# CommandScanner: Tokens recognized in command mode
# ---------------------------------------------------------------------


class _CommandScanner_1(_BasicScanner_1):

    def t_string(self, s, m, parent):
        r'[^ \t\n()\\;{}&]+(\\(.|\n)[^ \t\n()\\;{}&]*)*'
        # What other characters are forbidden in unquoted strings?
        # Allowing escaped newlines, blanks, quotes, etc.
        # Increment line count for embedded newlines (after adding token)
        parent.addToken(type=parent.argsep)
        parent.argsep = ','
        nline = _countNewlines(s)
        # Handle special escapes then, escape all remaining backslashes
        # since IRAF doesn't deal with special characters in this mode.
        # Thus PyRAF should leave them as literal backslashes within its
        # strings. Why IRAF does this I have no idea.
        s = irafutils.removeEscapes(s).replace('\\', '\\\\')
        parent.addToken(type='STRING', attr=s)
        parent.lineno = parent.lineno + nline

    def t_lbracket(self, s, m, parent):
        r'\['
        parent.addToken(type=s)
        # push to compute mode
        parent.current.append(_COMPUTE_MODE)

    def t_lparen(self, s, m, parent):
        r'\('
        parent.addToken(type=parent.argsep)
        parent.argsep = ','
        parent.addToken(type='(')
        # push to compute mode
        parent.current.append(_COMPUTE_MODE)
        parent.parencount = parent.parencount + 1
        # redirection can follow open parens
        parent.current.append(_ACCEPT_REDIR_MODE)


class _CommandScanner_2(_BasicScanner_2, _CommandScanner_1):

    def t_keyval(self, s, m, parent):
        r'(?P<KeyName>[a-zA-Z\$_\d][a-zA-Z\$_\d.]*) [ \t]* =(?!=)'
        # note that keywords can start with a number (!) in command mode
        parent.addToken(type=parent.argsep)
        parent.argsep = None
        parent.addIdent(m.group('KeyName'), usekey=0)
        parent.addToken(type='=')

    def t_keybool(self, s, m, parent):
        r'[a-zA-Z\$_\d][a-zA-Z\$_\d.]*[+\-]($|(?=[ \t\n<>\|]))'
        # note that keywords can start with a number (!) in command mode
        parent.addToken(type=parent.argsep)
        parent.argsep = ','
        parent.addIdent(s[:-1], usekey=0)
        parent.addToken(type=s[-1])

    def t_functioncall(self, s, m, parent):
        r'[a-zA-Z\$_\d][a-zA-Z\$_\d.]*\('
        # matches identifier follow by open parenthesis (no whitespace)
        # note that keywords can start with a number (!) in command mode
        parent.addToken(type=parent.argsep)
        parent.argsep = ','
        parent.addIdent(s[:-1], usekey=0)
        parent.addToken(type='(')
        # push to compute mode
        parent.current.append(_COMPUTE_MODE)
        parent.parencount = parent.parencount + 1
        # redirection can follow open parens
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_assignop(self, s, m, parent):
        r'( [+\-*/] | // )? ='
        if s == '=':
            parent.addToken(type=s)
        else:
            parent.addToken(type='ASSIGNOP', attr=s)
        parent.current.append(_COMPUTE_MODE)


class _StrictCommandScanner(_BasicScanner_3, _CommandScanner_2):
    """Strict scanner class for tokens recognized in command mode"""

    def t_redir(self, s, m, parent):
        r' < | >>? ([GIP]+|&?) | \|&? '
        # Redirection is accepted anywhere in command mode
        if s[0] == '|':
            parent.addToken(type='PIPE', attr=s)
            parent.startLine(parencount=parent.parencount)
        else:
            parent.addToken(type=parent.argsep)
            parent.argsep = None
            parent.addToken(type='REDIR', attr=s)
        parent.current.append(_SWALLOW_NEWLINE_MODE)


class _CommandScanner(_LaxScanner, _StrictCommandScanner):
    """Scanner class for tokens recognized in command mode"""
    pass


# ---------------------------------------------------------------------
# ComputeStartScanner: Tokens recognized in initial compute mode
#                      (similar to command mode)
# ---------------------------------------------------------------------


class _ComputeStartScanner_1(_BasicScanner_1):

    def t_string(self, s, m, parent):
        r'[a-zA-Z_$][a-zA-Z_$.0-9]*'
        # This is a quoteless string with some strict syntax limits.
        # Most special characters are excluded.  Escapes are not allowed
        # either.
        parent.addToken(type='STRING', attr=s)

    def t_integer(self, s, m, parent):
        r' \d+([bB]|([\da-fA-F]*[xX]))? '
        parent.addToken(type='INTEGER', attr=s)

    def t_comma(self, s, m, parent):
        r','
        # commas are parameter separators in this mode
        # newlines, redirection allowed after comma
        parent.addToken(type=s)
        parent.current.append(_ACCEPT_REDIR_MODE)
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_lbracket(self, s, m, parent):
        r'\['
        parent.addToken(type=s)
        # push to compute mode
        parent.current.append(_COMPUTE_MODE)

    def t_lparen(self, s, m, parent):
        r'\('
        parent.enterComputeEqnMode()
        parent.addToken(type='(')
        # push to compute mode
        parent.current.append(_COMPUTE_MODE)
        parent.parencount = parent.parencount + 1
        # redirection can follow open parens
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_op(self, s, m, parent):
        r'\*\*|//|\*|\+|-|/|%'
        # XXX Could make this type OP if we don't need to distinguish them
        parent.enterComputeEqnMode()
        parent.addToken(type=s)
        # line breaks are allowed after operators
        parent.current.append(_SWALLOW_NEWLINE_MODE)


class _ComputeStartScanner_2(_BasicScanner_2, _ComputeStartScanner_1):

    def t_keyval(self, s, m, parent):
        r'(?P<KeyName>[a-zA-Z\$_][a-zA-Z\$_\d.]*) [ \t]* =(?!=)'
        parent.addIdent(m.group('KeyName'), usekey=0)
        parent.addToken(type='=')

    def t_keybool(self, s, m, parent):
        r'[a-zA-Z\$_][a-zA-Z\$_\d.]*[+\-]($|(?=[ \t]*[\n<>\|,)]))'
        # Difference from command mode t_keybool is that comma/paren can
        # terminate argument
        # This pattern requires a following comma, newline, or
        # redirection so that expressions can be distinguished from
        # boolean args in this mode
        parent.addIdent(s[:-1], usekey=0)
        parent.addToken(type=s[-1])
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_assignop(self, s, m, parent):
        r'( [+\-*/] | // )? ='
        if s == '=':
            parent.addToken(type=s)
        else:
            parent.addToken(type='ASSIGNOP', attr=s)
        parent.current.append(_COMPUTE_MODE)

    def t_redir(self, s, m, parent):
        r' < | >>? ([GIP]+|&?) | \|&? '
        # Redirection is accepted in command mode
        if s[0] == '|':
            parent.addToken(type='PIPE', attr=s)
            parent.startLine(parencount=parent.parencount)
        else:
            parent.addToken(type='REDIR', attr=s)
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_sexagesimal(self, s, m, parent):
        r'\d+:\d+(:\d+(\.\d*)?)?'
        parent.addToken(type='SEXAGESIMAL', attr=s)

    def t_float(self, s, m, parent):
        r'(\d+[eEdD][+\-]?\d+) | (((\d*\.\d+)|(\d+\.\d*))([eEdD][+\-]?\d+)?)'
        parent.addToken(type='FLOAT', attr=s)


class _StrictComputeStartScanner(_BasicScanner_3, _ComputeStartScanner_2):
    """Strict scanner class for tokens recognized in initial compute mode
    (similar to command mode)
    """
    pass


class _ComputeStartScanner(_LaxScanner, _StrictComputeStartScanner):
    """Scanner class for tokens recognized in initial compute mode
    (similar to command mode)
    """
    pass


# ---------------------------------------------------------------------
# ComputeEqnScanner: Tokens recognized in compute equation mode
# Mostly like standard Compute mode, but reverts to ComputeStart
# mode on comma
# ---------------------------------------------------------------------


class _ComputeEqnScanner_1(_BasicScanner_1):

    def t_lparen(self, s, m, parent):
        r'\('
        parent.addToken(type='(')
        parent.current.append(_COMPUTE_MODE)
        parent.parencount = parent.parencount + 1
        # redirection can follow open parens
        # XXX get rid of this?
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_op(self, s, m, parent):
        r'\*\*|//|\*|\+|-|/|%'
        # XXX Could make this type OP if we don't need to distinguish them
        parent.addToken(type=s)
        # line breaks are allowed after operators
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_logop(self, s, m, parent):
        r'\|\||&&|!'
        # split '!' off separately
        if len(s) > 1:
            parent.addToken(type='LOGOP', attr=s)
        else:
            parent.addToken(type=s)
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_integer(self, s, m, parent):
        r' \d+([bB]|([\da-fA-F]*[xX]))? '
        parent.addToken(type='INTEGER', attr=s)

    def t_ident(self, s, m, parent):
        r'[a-zA-Z\$_][a-zA-Z\$_\d.]*'
        parent.addIdent(s)

    def t_comma(self, s, m, parent):
        r','
        # commas are parameter separators in this mode
        # commas also terminate this mode
        parent.exitComputeEqnMode()
        parent.addToken(type=s)
        # newlines, redirection allowed after comma
        parent.current.append(_ACCEPT_REDIR_MODE)
        parent.current.append(_SWALLOW_NEWLINE_MODE)


class _ComputeEqnScanner_2(_BasicScanner_2, _ComputeEqnScanner_1):

    def t_keyval(self, s, m, parent):
        r'(?P<KeyName>[a-zA-Z\$_][a-zA-Z\$_\d.]*) [ \t]* =(?!=)'
        parent.addIdent(m.group('KeyName'), usekey=0)
        parent.addToken(type='=')

    def t_keybool(self, s, m, parent):
        r'[a-zA-Z\$_][a-zA-Z\$_\d.]*[+\-]($|(?=[ \t]*[\n<>\|,)]))'
        # Difference from command mode t_keybool is that comma/paren can
        # terminate argument
        # This pattern requires a following comma, newline, or
        # redirection so that expressions can be distinguished from
        # boolean args in this mode
        parent.addIdent(s[:-1], usekey=0)
        parent.addToken(type=s[-1])
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_sexagesimal(self, s, m, parent):
        r'\d+:\d+(:\d+(\.\d*)?)?'
        parent.addToken(type='SEXAGESIMAL', attr=s)

    def t_assignop(self, s, m, parent):
        r'( [+\-*/] | // ) ='
        parent.addToken(type='ASSIGNOP', attr=s)
        # switch to compute mode
        parent.current[-1] = _COMPUTE_MODE

    def t_float(self, s, m, parent):
        r'(\d+[eEdD][+\-]?\d+) | (((\d*\.\d+)|(\d+\.\d*))([eEdD][+\-]?\d+)?)'
        parent.addToken(type='FLOAT', attr=s)


class _StrictComputeEqnScanner(_BasicScanner_3, _ComputeEqnScanner_2):
    """Strict scanner class for tokens recognized in compute equation mode"""

    def t_compop(self, s, m, parent):
        r'[<>!=]=|<|>'
        parent.addToken(type='COMPOP', attr=s)
        parent.current.append(_SWALLOW_NEWLINE_MODE)


class _ComputeEqnScanner(_LaxScanner, _StrictComputeEqnScanner):
    """Scanner class for tokens recognized in compute mode"""
    pass


# ---------------------------------------------------------------------
# ComputeScanner: Tokens recognized in compute mode
# ---------------------------------------------------------------------


class _ComputeScanner_1(_BasicScanner_1):

    def t_lparen(self, s, m, parent):
        r'\('
        parent.addToken(type='(')
        # push to compute mode
        parent.current.append(_COMPUTE_MODE)
        parent.parencount = parent.parencount + 1
        # redirection can follow open parens
        # XXX get rid of this?
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_op(self, s, m, parent):
        r'\*\*|//|\*|\+|-|/|%'
        # XXX Could make this type OP if we don't need to distinguish them
        parent.addToken(type=s)
        # line breaks are allowed after operators
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_logop(self, s, m, parent):
        r'\|\||&&|!'
        # split '!' off separately
        if len(s) > 1:
            parent.addToken(type='LOGOP', attr=s)
        else:
            parent.addToken(type=s)
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_integer(self, s, m, parent):
        r' \d+([bB]|([\da-fA-F]*[xX]))? '
        parent.addToken(type='INTEGER', attr=s)

    def t_ident(self, s, m, parent):
        r'[a-zA-Z\$_][a-zA-Z\$_\d.]*'
        parent.addIdent(s)

    def t_comma(self, s, m, parent):
        r','
        # commas are parameter separators in this mode
        parent.addToken(type=s)
        # newlines, redirection allowed after comma
        parent.current.append(_ACCEPT_REDIR_MODE)
        parent.current.append(_SWALLOW_NEWLINE_MODE)


class _ComputeScanner_2(_BasicScanner_2, _ComputeScanner_1):

    def t_keyval(self, s, m, parent):
        r'(?P<KeyName>[a-zA-Z\$_][a-zA-Z\$_\d.]*) [ \t]* =(?!=)'
        parent.addIdent(m.group('KeyName'), usekey=0)
        parent.addToken(type='=')

    def t_keybool(self, s, m, parent):
        r'[a-zA-Z\$_][a-zA-Z\$_\d.]*[+\-]($|(?=[ \t]*[\n<>\|,)]))'
        # Difference from command mode t_keybool is that comma/paren can
        # terminate argument
        # This pattern requires a following comma, newline, or
        # redirection so that expressions can be distinguished from
        # boolean args in this mode
        parent.addIdent(s[:-1], usekey=0)
        parent.addToken(type=s[-1])
        parent.current.append(_ACCEPT_REDIR_MODE)

    def t_sexagesimal(self, s, m, parent):
        r'\d+:\d+(:\d+(\.\d*)?)?'
        parent.addToken(type='SEXAGESIMAL', attr=s)

    def t_assignop(self, s, m, parent):
        r'( [+\-*/] | // ) ='
        parent.addToken(type='ASSIGNOP', attr=s)

    def t_float(self, s, m, parent):
        r'(\d+[eEdD][+\-]?\d+) | (((\d*\.\d+)|(\d+\.\d*))([eEdD][+\-]?\d+)?)'
        parent.addToken(type='FLOAT', attr=s)


class _StrictComputeScanner(_BasicScanner_3, _ComputeScanner_2):
    """Strict scanner class for tokens recognized in compute mode"""

    def t_compop(self, s, m, parent):
        r'[<>!=]=|<|>'
        parent.addToken(type='COMPOP', attr=s)
        parent.current.append(_SWALLOW_NEWLINE_MODE)


class _ComputeScanner(_LaxScanner, _StrictComputeScanner):
    """Scanner class for tokens recognized in compute mode"""
    pass


# ---------------------------------------------------------------------
# SwallowNewlineScanner: Tokens recognized at points where
#                        embedded newlines are allowed
# ---------------------------------------------------------------------


class _StrictSwallowNewlineScanner(GenericScanner):
    """Strict scanner class where embedded newlines allowed"""

    def t_swallow_newlines(self, s, m, parent):
        r'[ \t\n]* ( ( \\ | (\#.*) ) [ \t\n]+ )*'
        # Just grab all the following newlines
        # Also consumes backslash continuations and comments
        # Note that this always matches, so we always leave this
        # mode after one match
        parent.lineno = parent.lineno + _countNewlines(s)
        # pop to previous mode
        del parent.current[-1]


_SwallowNewlineScanner = _StrictSwallowNewlineScanner

# ---------------------------------------------------------------------
# AcceptRedirScanner: Tokens that are recognized at points where
#                     redirection is allowed
# ---------------------------------------------------------------------


class _StrictAcceptRedirScanner(_BasicScanner_3, _BasicScanner_2,
                                _BasicScanner_1):
    """Strict scanner class where redirection is allowed"""

    def t_accept_redir(self, s, m, parent):
        r' < | >>? ([GIP]+|&?) | \|&? '
        if s[0] == '|':
            parent.addToken(type='PIPE', attr=s)
            parent.startLine(parencount=parent.parencount)
        else:
            parent.addToken(type='REDIR', attr=s)
            # pop this state
            del parent.current[-1]
        # allow following newlines
        parent.current.append(_SWALLOW_NEWLINE_MODE)

    def t_ignore_spaces(self, s, m, parent):
        r'[ \t]+'
        # whitespace ignored (but does not cause us to leave this mode)
        pass

    def t_not_redir(self, s, m, parent):
        r'(?![ \t<>\|])'
        # if not redirection or whitespace, just pop the state
        del parent.current[-1]


class _AcceptRedirScanner(_LaxScanner, _StrictAcceptRedirScanner):
    """Scanner class where redirection is allowed"""
    pass


# ---------------------------------------------------------------------
# Main context-sensitive scanner
# ---------------------------------------------------------------------

# dictionary of reserved keywords

# SEE ALSO ClScanner.__init__ for more ECL keywords.
_keywordDict = {
    'begin': 1,
    'break': 1,
    'case': 1,
    'default': 1,
    'else': 1,
    'end': 1,
    'for': 1,
    'goto': 1,
    'if': 1,
    'next': 1,
    'procedure': 1,
    'return': 1,
    'switch': 1,
    'while': 1,
}

_typeDict = {
    'bool': 1,
    'char': 1,
    'file': 1,
    'gcur': 1,
    'imcur': 1,
    'int': 1,
    'pset': 1,
    'real': 1,
    'string': 1,
    'struct': 1,
    'ukey': 1,
}

_boolDict = {
    'yes': 1,
    'no': 1,
}

# list of scanners for each state
# only need to create these once, since they are designed to
# contain no state information

_scannerDict = None
_strictScannerDict = None


def _getScannerDict():
    global _scannerDict
    if _scannerDict is None:
        _scannerDict = {
            _START_LINE_MODE: _StartScanner(),
            _COMMAND_MODE: _CommandScanner(),
            _COMPUTE_START_MODE: _ComputeStartScanner(),
            _COMPUTE_EQN_MODE: _ComputeEqnScanner(),
            _COMPUTE_MODE: _ComputeScanner(),
            _SWALLOW_NEWLINE_MODE: _SwallowNewlineScanner(),
            _ACCEPT_REDIR_MODE: _AcceptRedirScanner(),
        }
    return _scannerDict


def _getStrictScannerDict():
    global _strictScannerDict
    # create strict scanners
    if _strictScannerDict is None:
        _strictScannerDict = {
            _START_LINE_MODE: _StrictStartScanner(),
            _COMMAND_MODE: _StrictCommandScanner(),
            _COMPUTE_START_MODE: _StrictComputeStartScanner(),
            _COMPUTE_EQN_MODE: _StrictComputeEqnScanner(),
            _COMPUTE_MODE: _StrictComputeScanner(),
            _SWALLOW_NEWLINE_MODE: _StrictSwallowNewlineScanner(),
            _ACCEPT_REDIR_MODE: _StrictAcceptRedirScanner(),
        }
    return _strictScannerDict


class CLScanner(ContextSensitiveScanner):
    """CL scanner class"""

    def __init__(self, strict=0):

        if pyrafglobals._use_ecl:
            _keywordDict["iferr"] = 1
            _keywordDict["ifnoerr"] = 1
            _keywordDict["then"] = 1

        self.strict = strict
        if strict:
            sdict = _getStrictScannerDict()
        else:
            sdict = _getScannerDict()
        ContextSensitiveScanner.__init__(self, sdict)

    def startLine(self, parencount=0, argsep=None):
        # go to _START_LINE_MODE
        self.parencount = parencount
        self.argsep = argsep
        self.current = [_START_LINE_MODE]

    def tokenize(self, input, default_mode=_COMMAND_MODE):
        self.rv = []
        self.lineno = 1
        # default mode when leaving _START_LINE_MODE
        self.default_mode = default_mode
        # argsep is used to insert commas as argument separators
        # in command mode
        self.argsep = None
        self.parencount = 0
        ContextSensitiveScanner.tokenize(self, input)
        self.addToken(type='NEWLINE')
        return self.rv

    def addToken(self, type, attr=None):
        # add a token to the list (with some twists to simplify parsing)

        if type is None:
            return

        # insert NEWLINE before '}'

        if type == '}' and self.rv and self.rv[-1].type != 'NEWLINE':
            self.rv.append(Token(type='NEWLINE', attr=None,
                                 lineno=self.lineno))

        # suppress newline after '{' or ';'
        # if type != 'NEWLINE' or (self.rv and self.rv[-1].type != 'NEWLINE' and
        #                                               self.rv[-1].type != '{' and
        #                                               self.rv[-1].type != ';'):

        # compress out multiple/leading newlines
        # suppress newline after '{'

        if type != 'NEWLINE' or (self.rv and self.rv[-1].type != 'NEWLINE' and
                                 self.rv[-1].type != '{'):

            # Another ugly hack -- the syntax
            #
            # taskname(arg, arg, | taskname2 arg, arg)
            #
            # causes parsing problems.  To help solve them, delete any
            # comma that just precedes a PIPE

            if type == 'PIPE' and self.rv and self.rv[-1].type == ',':
                del self.rv[-1]

            self.rv.append(Token(type=type, attr=attr, lineno=self.lineno))

        # insert NEWLINE after '}' too
        # go to start-line mode
        if type == '}' and self.rv and self.rv[-1].type != 'NEWLINE':
            self.rv.append(Token(type='NEWLINE', attr=None,
                                 lineno=self.lineno))
            self.startLine()

    def addIdent(self, name, mode=None, usekey=1):
        # Add identifier token, recognizing keywords if usekey parameter is set
        # Note keywords may be in any case
        # For normal (non-keyword) identifiers, goes to mode

        keyword = name.lower()
        if usekey and keyword in _keywordDict:

            self.addToken(type=keyword.upper(), attr=keyword)
            if keyword == "procedure":
                # Procedure scripts are always in compute mode
                self.default_mode = _COMPUTE_START_MODE
            if keyword == "if" or keyword == "else":
                # For `if', `else' go into _START_LINE_MODE
                self.startLine()
            elif self.current[-1] != _COMPUTE_MODE:
                # Other keywords put us into _COMPUTE_MODE
                self.current.append(_COMPUTE_MODE)

        elif usekey and keyword in _typeDict and \
                self.current[-1] == _START_LINE_MODE:

            # types are treated as keywords only if first token on line
            self.addToken(type='TYPE', attr=keyword)
            self.current.append(_COMPUTE_MODE)

        elif keyword == "indef" or keyword == "eof":

            # INDEF, EOF always get recognized
            self.addToken(type=keyword.upper())

        elif keyword == "epsilon":

            # epsilon always gets recognized
            self.addToken(type="FLOAT", attr=keyword)
            # xxx self.addToken(type="FLOAT")
            #     AttributeError: 'NoneType' object has no attribute 'find'
            # xxx self.addToken(type=keyword.upper())
            #     epsilon was quoted

        elif keyword in _boolDict:

            # boolean yes, no always gets recognized
            self.addToken(type='BOOL', attr=keyword)

        else:

            self.addToken(type='IDENT', attr=name)
            if mode is not None:
                self.current.append(mode)

    def enterComputeEqnMode(self):
        # Nasty hack to work around weird CL syntax
        # In compute-start mode, tokens are strings or identifiers
        # or numbers depending on what follows them, and the mode
        # once switched to compute-mode stays there until a
        # terminating comma.  Ugly stuff.
        #
        # This is called when a token is received that triggers the
        # transition to the compute-eqn mode from compute-start mode.
        # It may be necessary to change tokens already on the
        # list when this is called...

        self.current.append(_COMPUTE_EQN_MODE)
        if self.rv and self.rv[-1].type == "STRING":
            # if last token was a string, we must remove it and
            # rescan it using the compute-mode scanner
            # Hope this works!
            last = self.rv[-1].attr
            del self.rv[-1]
            ContextSensitiveScanner.tokenize(self, last)

    def exitComputeEqnMode(self):
        # Companion to enterComputeEqnMode -- called when we encounter
        # a token that may cause us to exit the mode
        if self.current[-1] == _COMPUTE_EQN_MODE:
            del self.current[-1]


def _countNewlines(s):
    """Return number of newlines in string"""
    n = 0
    i = s.find('\n')
    while (i >= 0):
        n = n + 1
        i = s.find('\n', i + 1)
    return n


def scan(f):
    input = f.read()
    scanner = CLScanner()
    return scanner.tokenize(input)


def toklist(tlist, filename=None):
    # list tokens
    from . import cltoken
    if filename:
        import sys
        sys.stdout = open(filename, 'w')
    for tok in tlist:
        if tok.type == 'NEWLINE':
            if cltoken.verbose:
                print('NEWLINE')
            else:
                print()
        else:
            print(repr(tok), end=' ')
    if filename:
        sys.stdout.close()
        sys.stdout = sys.__stdout__
