"""module irafutils.py -- general utility functions

printCols       Print elements of list in cols columns
stripQuotes     Strip single or double quotes off string and remove embedded
                quote pairs
removeEscapes   Remove escaped quotes & newlines from strings
translateName   Convert CL parameter or variable name to Python-acceptable name
untranslateName Undo Python conversion of CL parameter or variable name
tkread          Read n bytes from file while running Tk mainloop
tkreadline     Read a line from file while running Tk mainloop

$Id$

R. White, 1999 Jul 16
"""

import os, sys, string, struct, re, keyword, types, select
import Tkinter

def printCols(strlist,cols=5,width=80):

    """Print elements of list in cols columns"""

    # This may exist somewhere in the Python standard libraries?
    # Should probably rewrite this, it is pretty crude.

    nlines = (len(strlist)+cols-1)/cols
    line = nlines*[""]
    for i in xrange(len(strlist)):
        c, r = divmod(i,nlines)
        nwid = c*width/cols - len(line[r])
        if nwid>0:
            line[r] = line[r] + nwid*" " + strlist[i]
        else:
            line[r] = line[r] + " " + strlist[i]
    for s in line:
        print s

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

def removeEscapes(value, quoted=0):

    """Remove escapes from in front of quotes (which IRAF seems to
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
    if hasattr(file, 'fileno'):
        fd = file.fileno()
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
        if isinstance(file, types.IntType):
            fd = file
        elif hasattr(file, "fileno"):
            fd = file.fileno()
        else:
            raise TypeError("file must be an integer or a filehandle/socket")
        self.widget = Tkinter._default_root
        if not self.widget:
            # no Tk widgets yet, so no need for mainloop
            s = []
            while nbytes>0:
                snew = os.read(fd, nbytes)
                if snew:
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
                                    Tkinter.tkinter.READABLE | Tkinter.tkinter.EXCEPTION,
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
                self.value.append(snew)
                self.nbytes -= len(snew)
            else:
                snew = ''
            if (self.nbytes <= 0 or len(snew) == 0) and self.widget:
                # stop the mainloop
                self.widget.quit()
        except OSError, error:
            raise IOError("Error reading from %s" % (fd,))
