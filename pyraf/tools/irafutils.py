"""module irafutils.py -- general utility functions

printCols       Print elements of list in cols columns
printColsAuto   Print elements of list in the best number of columns
stripQuotes     Strip single or double quotes off string and remove embedded
                quote pairs
csvSplit        Split comma-separated fields in strings (cover bug in csv mod)
rglob           Recursive glob
setWritePrivs   Convenience function to add/remove write privs
removeEscapes   Remove escaped quotes & newlines from strings
translateName   Convert CL parameter or variable name to Python-acceptable name
untranslateName Undo Python conversion of CL parameter or variable name
tkread          Read n bytes from file while running Tk mainloop
tkreadline      Read a line from file while running Tk mainloop
launchBrowser   Given a URL, try to pop it up in a browser on most platforms.

$Id$

R. White, 1999 Jul 16
"""
import os
import stat
import string
import sys
import re
import fnmatch
import keyword
import select
from . import capable

if capable.OF_GRAPHICS:
    import tkinter as TKNTR


def printColsAuto(in_strings, term_width=80, min_pad=1):
    """ Print a list of strings centered in columns.  Determine the number
    of columns and lines on the fly.  Return the result, ready to print.
    in_strings is a list/tuple/iterable of strings
    min_pad is number of spaces to appear on each side of a single string (so
            you will see twice this many spaces between 2 strings)
    """
    # sanity check
    if not in_strings:
        raise ValueError('Unexpected: ' + repr(in_strings))

    # get max width in input
    maxWidth = len(max(in_strings, key=len)) + (2*min_pad) # width with pad
    numCols = term_width//maxWidth # integer div
    # set numCols so we take advantage of the whole line width
    numCols = min(numCols, len(in_strings))

    # easy case - single column or too big
    if numCols < 2:
        # one or some items are too big but print one item per line anyway
        lines = [x.center(term_width) for x in in_strings]
        return '\n'.join(lines)

    # normal case - 2 or more columns
    colWidth = term_width//numCols # integer div
    # colWidth is guaranteed to be larger than all items in input
    retval = ''
    for i in range(len(in_strings)):
        retval+=in_strings[i].center(colWidth)
        if (i+1)%numCols == 0:
            retval += '\n'
    return retval.rstrip()


def printCols(strlist,cols=5,width=80):

    """Print elements of list in cols columns"""

    # This may exist somewhere in the Python standard libraries?
    # Should probably rewrite this, it is pretty crude.

    nlines = (len(strlist)+cols-1)//cols
    line = nlines*[""]
    for i in range(len(strlist)):
        c, r = divmod(i,nlines)
        nwid = c*width//cols - len(line[r])
        if nwid>0:
            line[r] = line[r] + nwid*" " + strlist[i]
        else:
            line[r] = line[r] + " " + strlist[i]
    for s in line:
        print(s)

_re_doubleq2 = re.compile('""')
_re_singleq2 = re.compile("''")

def stripQuotes(value):

    """Strip single or double quotes off string; remove embedded quote pairs"""

    if value[:1] == '"':
        value = value[1:]
        if value[-1:] == '"':
            value = value[:-1]
        # replace "" with "
        value = re.sub(_re_doubleq2, '"', value)
    elif value[:1] == "'":
        value = value[1:]
        if value[-1:] == "'":
            value = value[:-1]
        # replace '' with '
        value = re.sub(_re_singleq2, "'", value)
    return value

def csvSplit(line, delim=',', allowEol=True):
    """ Take a string as input (e.g. a line in a csv text file), and break
    it into tokens separated by commas while ignoring commas embedded inside
    quoted sections.  This is exactly what the 'csv' module is meant for, so
    we *should* be using it, save that it has two bugs (described next) which
    limit our use of it.  When these bugs are fixed, this function should be
    forsaken in favor of direct use of the csv module (or similar).

    The basic use case is to split a function signature string, so for:
        afunc(arg1='str1', arg2='str, with, embedded, commas', arg3=7)
    we want a 3 element sequence:
        ["arg1='str1'", "arg2='str, with, embedded, commas'", "arg3=7"]

    but:
    >>> import csv
    >>> y = "arg1='str1', arg2='str, with, embedded, commas', arg3=7"
    >>> rdr = csv.reader( (y,), dialect='excel', quotechar="'", skipinitialspace=True)
    >>> l = rdr.next(); print(len(l), str(l))  # doctest: +SKIP
    6 ["arg1='str1'", "arg2='str", 'with', 'embedded', "commas'", "arg3=7"]

    which we can see is not correct - we wanted 3 tokens.  This occurs in
    Python 2.5.2 and 2.6.  It seems to be due to the text at the start of each
    token ("arg1=") i.e. because the quote isn't for the whole token.  If we
    were to remove the names of the args and the equal signs, it works:

    >>> x = "'str1', 'str, with, embedded, commas', 7"
    >>> rdr = csv.reader( (x,), dialect='excel', quotechar="'", skipinitialspace=True)
    >>> l = rdr.next(); print(len(l), str(l))  # doctest: +SKIP
    3 ['str1', 'str, with, embedded, commas', '7']

    But even this usage is delicate - when we turn off skipinitialspace, it
    fails:

    >>> x = "'str1', 'str, with, embedded, commas', 7"
    >>> rdr = csv.reader( (x,), dialect='excel', quotechar="'")
    >>> l = rdr.next(); print(len(l), str(l))  # doctest: +SKIP
    6 ['str1', " 'str", ' with', ' embedded', " commas'", ' 7']

    So, for now, we'll roll our own.
    """
    # Algorithm:  read chars left to right, go from delimiter to delimiter,
    # but as soon as a single/double/triple quote is hit, scan forward
    # (ignoring all else) until its matching end-quote is found.
    # For now, we will not specially handle escaped quotes.
    tokens = []
    ldl = len(delim)
    keepOnRollin = line is not None and len(line) > 0
    while keepOnRollin:
        tok = _getCharsUntil(line, delim, True, allowEol=allowEol)
        # len of token should always be > 0 because it includes end delimiter
        # except on last token
        if len(tok) > 0:
            # append it, but without the delimiter
            if tok[-ldl:] == delim:
                tokens.append(tok[:-ldl])
            else:
                tokens.append(tok) # tok goes to EOL - has no delimiter
                keepOnRollin = False
            line = line[len(tok):]
        else:
            # This is the case of the empty end token
            tokens.append('')
            keepOnRollin = False
    return tokens

# We'll often need to search a string for 3 possible characters.  We could
# loop and check each one ourselves; we could do 3 separate find() calls;
# or we could do a compiled re.search().  For VERY long strings (hundreds
# of thousands of chars), it turns out that find() is so fast and that
# re (even compiled) has enough overhead, that 3 find's is the same or
# slightly faster than one re.search with three chars in the re expr.
# Of course, both methods are much faster than an explicit loop.
# Since these strings will be short, the fastest method is re.search()
_re_sq = re.compile(r"'")
_re_dq = re.compile(r'"')
_re_comma_sq_dq = re.compile(r'[,\'"]')

def _getCharsUntil(buf, stopChar, branchForQuotes, allowEol):

    # Sanity checks
    if buf is None: return None
    if len(buf) <= 0: return ''

    # Search chars left-to-right looking for stopChar
    sought = (stopChar,)
    theRe = None
    if branchForQuotes:
        sought = (stopChar,"'",'"') # see later, we'll handle '"""' too
        if stopChar == ',': theRe = _re_comma_sq_dq # pre-compiled common case
    else:
        if stopChar == '"': theRe = _re_dq # pre-compiled common case
        if stopChar == "'": theRe = _re_sq # pre-compiled common case

    if theRe is None:
        theRe = re.compile('['+''.join(sought)+']')

    mo = theRe.search(buf)

    # No match found; stop
    if mo is None:
        if not stopChar in ('"', "'"):
            # this is a primary search, not a branch into quoted text
            return buf # searched until we hit the EOL, must be last token
        else:
            # this is a branch into a quoted string - do we allow EOL here?
            if allowEol:
                return buf
            else:
                raise ValueError('Unfound end-quote, buffer: '+buf)

    # The expected match was found. Stop.
    if mo.group() == stopChar:
        return buf[:1 + mo.start()] # return token plus stopChar at end

    # Should not get to this point unless in a branch-for-quotes situation.
    if not branchForQuotes:
        raise RuntimeError("Programming error! Shouldn't be here w/out branching")

    # Quotes were found.
    # There are two kinds, but double quotes could be the start of
    # triple double-quotes. (""") So get the substring to create the token.
    #
    #    token = preQuote+quotedPart+postQuote (e.g.: "abc'-hi,ya-'xyz")
    #
    preQuote = buf[:mo.start()]
    if mo.group() == "'":
        quotedPart = "'"+_getCharsUntil(buf[1+mo.start():],"'",False,allowEol)
    else:
        # first double quote (are there 3 in a row?)
        idx = mo.start()
        if len(buf) > idx+2 and '"""' == buf[idx:idx+3]:
            # We ARE in a triple-quote sub-string
            end_t_q = buf[idx+3:].find('"""')
            if end_t_q < 0:
                # hit end of line before finding end quote
                if allowEol:
                    quotedPart = buf[idx:]
                else:
                    raise ValueError('Unfound triple end-quote, buffer: '+buf)
            else:
                quotedPart = buf[idx:idx+3+end_t_q+1]
        else:
            quotedPart = '"'+_getCharsUntil(buf[1+mo.start():],'"',False,allowEol)
    lenSoFar = len(preQuote)+len(quotedPart)
    if lenSoFar < len(buf):
        # now get back to looking for end delimiter
        postQuote = _getCharsUntil(buf[lenSoFar:], stopChar,
                                   branchForQuotes, allowEol)
        return preQuote+quotedPart+postQuote
    else:
        return buf # at end

def rglob(root, pattern):
    """ Same thing as glob.glob, but recursively checks subdirs. """
    # Thanks to Alex Martelli for basics on Stack Overflow
    retlist = []
    if None not in (pattern, root):
        for base, dirs, files in os.walk(root):
            goodfiles = fnmatch.filter(files, pattern)
            retlist.extend(os.path.join(base, f) for f in goodfiles)
    return retlist

def setWritePrivs(fname, makeWritable, ignoreErrors=False):
    """ Set a file named fname to be writable (or not) by user, with the
    option to ignore errors.  There is nothing ground-breaking here, but I
    was annoyed with having to repeate this little bit of code. """
    privs = os.stat(fname).st_mode
    try:
        if makeWritable:
            os.chmod(fname, privs | stat.S_IWUSR)
        else:
            os.chmod(fname, privs & (~ stat.S_IWUSR))
    except OSError:
        if ignoreErrors:
            pass # just try, don't whine
        else:
            raise


def removeEscapes(value, quoted=0):

    r"""Remove escapes from in front of quotes (which IRAF seems to
    just stick in for fun sometimes.)  Remove \-newline too.
    If quoted is true, removes all blanks following \-newline
    (which is a nasty thing IRAF does for continuations inside
    quoted strings.)
    XXX Should we remove \\ too?
    """

    i = value.find(r'\"')
    while i>=0:
        value = value[:i] + value[i+1:]
        i = value.find(r'\"',i+1)
    i = value.find(r"\'")
    while i>=0:
        value = value[:i] + value[i+1:]
        i = value.find(r"\'",i+1)
    # delete backslash-newlines
    i = value.find("\\\n")
    while i>=0:
        j = i+2
        if quoted:
            # ignore blanks and tabs following \-newline in quoted strings
            for c in value[i+2:]:
                if c not in ' \t':
                    break
                j = j+1
        value = value[:i] + value[j:]
        i = value.find("\\\n",i+1)
    return value

# Must modify Python keywords to make Python code legal.  I add 'PY' to
# beginning of Python keywords (and some other illegal Python identifiers).
# It will be stripped off where appropriate.

def translateName(s, dot=0):

    """Convert CL parameter or variable name to Python-acceptable name

    Translate embedded dollar signs to 'DOLLAR'
    Add 'PY' prefix to components that are Python reserved words
    Add 'PY' prefix to components start with a number
    If dot != 0, also replaces '.' with 'DOT'
    """

    s = s.replace('$', 'DOLLAR')
    sparts = s.split('.')
    for i in range(len(sparts)):
        if sparts[i] == "" or sparts[i][0] in string.digits or \
          keyword.iskeyword(sparts[i]):
            sparts[i] = 'PY' + sparts[i]
    if dot:
        return 'DOT'.join(sparts)
    else:
        return '.'.join(sparts)

def untranslateName(s):

    """Undo Python conversion of CL parameter or variable name"""

    s = s.replace('DOT', '.')
    s = s.replace('DOLLAR', '$')
    # delete 'PY' at start of name components
    if s[:2] == 'PY': s = s[2:]
    s = s.replace('.PY', '.')
    return s

# procedures to read while still allowing Tk widget updates

def init_tk_default_root(withdraw=True):

    """ In case the _default_root value is required, you may
    safely call this ahead of time to ensure that it has been
    initialized.  If it has already been, this is a no-op.
    """
    if not capable.OF_GRAPHICS:
        raise RuntimeError("Cannot run this command without graphics")

    if not TKNTR._default_root: # TKNTR imported above
        junk = TKNTR.Tk()

    # tkinter._default_root is now populated (== junk)
    retval = TKNTR._default_root
    if withdraw and retval:
        retval.withdraw()

    return retval


def tkread(file, n=0):

    """Read n bytes from file (or socket) while running Tk mainloop.

    If n=0 then this runs the mainloop until some input is ready on
    the file.  (See tkreadline for an application of this.)  The
    file must have a fileno method.
    """

    return _TkRead().read(file, n)

def tkreadline(file=None):

    """Read a line from file while running Tk mainloop.

    If the file is not line-buffered then the Tk mainloop will stop
    running after one character is typed.  The function will still work
    but Tk widgets will stop updating.  This should work OK for stdin and
    other line-buffered filehandles.  If file is omitted, reads from
    sys.stdin.

    The file must have a readline method.  If it does not have a fileno
    method (which can happen e.g. for the status line input on the
    graphics window) then the readline method is simply called directly.
    """

    if file is None:
        file = sys.stdin
    if not hasattr(file, "readline"):
        raise TypeError("file must be a filehandle with a readline method")

    # Call tkread now...
    # BUT, if we get in here for something not GUI-related (e.g. terminal-
    # focused code in a sometimes-GUI app) then skip tkread and simply call
    # readline on the input eg. stdin.  Otherwise we'd fail in _TkRead().read()

    try:
        fd = file.fileno()
    except:
        fd = None

    if (fd and capable.OF_GRAPHICS):
        tkread(fd, 0)
        # if EOF was encountered on a tty, avoid reading again because
        # it actually requests more data
        if not select.select([fd],[],[],0)[0]:
            return ''
    return file.readline()

class _TkRead:

    """Run Tk mainloop while waiting for a pending read operation"""

    def read(self, file, nbytes):
        """Read nbytes characters from file while running Tk mainloop"""
        if not capable.OF_GRAPHICS:
            raise RuntimeError("Cannot run this command without graphics")
        if isinstance(file, int):
            fd = file
        else:
            # Otherwise, assume we have Python file object
            try:
                fd = file.fileno()

            except:
                raise TypeError("file must be an integer or a filehandle/socket")
        init_tk_default_root() # harmless if already done
        self.widget = TKNTR._default_root
        if not self.widget:
            # no Tk widgets yet, so no need for mainloop
            # (shouldnt happen now with init_tk_default_root)
            s = []
            while nbytes>0:
                snew = os.read(fd, nbytes)
                if snew:
                    snew = snew.decode('ascii', 'replace')
                    s.append(snew)
                    nbytes -= len(snew)
                else:
                    # EOF -- just return what we have so far
                    break
            return "".join(s)
        else:
            self.nbytes = nbytes
            self.value = []
            self.widget.tk.createfilehandler(fd,
                                    TKNTR.READABLE | TKNTR.EXCEPTION,
                                    self._read)
            try:
                self.widget.mainloop()
            finally:
                self.widget.tk.deletefilehandler(fd)
            return "".join(self.value)


    def _read(self, fd, mask):
        """Read waiting data and terminate Tk mainloop if done"""
        try:
            # if EOF was encountered on a tty, avoid reading again because
            # it actually requests more data
            if select.select([fd],[],[],0)[0]:
                snew = os.read(fd, self.nbytes)
                snew = snew.decode('ascii', 'replace')
                self.value.append(snew)
                self.nbytes -= len(snew)
            else:
                snew = ''
            if (self.nbytes <= 0 or len(snew) == 0) and self.widget:
                # stop the mainloop
                self.widget.quit()
        except OSError:
            raise IOError("Error reading from %s" % (fd,))


def launchBrowser(url, brow_bin='mozilla', subj=None):
    """ Given a URL, try to pop it up in a browser on most platforms.
    brow_bin is only used on OS's where there is no "open" or "start" cmd.
    """

    if not subj:
        subj = url

    # Tries to use webbrowser module on most OSes, unless a system command
    # is needed.  (E.g. win, linux, sun, etc)
    if sys.platform not in ('os2warp, iphone'): # try webbrowser w/ everything?
        import webbrowser
        if not webbrowser.open(url):
            print("Error opening URL: "+url)
        else:
            print('Help on "'+subj+'" is now being displayed in a web browser')
        return

    # Go ahead and fork a subprocess to call the correct binary
    pid = os.fork()
    if pid == 0: # child
        if sys.platform == 'darwin':
            if os.system('open "'+url+'"'): # does not seem to keep '#.*'  # nosec
                print("Error opening URL: "+url)
        os._exit(0)
#       The following retries if "-remote" doesnt work, opening a new browser
#       cmd = brow_bin+" -remote 'openURL("+url+")' '"+url+"' 1> /dev/null 2>&1"
#       if 0 != os.system(cmd)
#           print "Running "+brow_bin+" for HTML help..."
#           os.execvp(brow_bin,[brow_bin,url])
#       os._exit(0)

    else: # parent
        if not subj:
            subj = url
        print('Help on "'+subj+'" is now being displayed in a browser')
