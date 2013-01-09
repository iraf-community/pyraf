#############################################################################
#####                   An example subprocess interfaces                #####
#############################################################################

class Ph:
    """Convenient interface to CCSO 'ph' nameserver subprocess.

    .query('string...') method takes a query and returns a list of dicts, each
    of which represents one entry."""

    # Note that i made this a class that handles a subprocess object, rather
    # than one that inherits from it.  I didn't see any functional
    # disadvantages, and didn't think that full support of the entire
    # Subprocess functionality was in any way suitable for interaction with
    # this specialized interface.  ?  klm 13-Jan-1995

    def __init__(self):
        try:
            self.proc = Subprocess("ph", expire_noisily=1)
        except:
            raise SubprocessError("failure starting ph: %s" %
                                  str(sys.exc_value))

    def query(self, q):
        """Send a query and return a list of dicts for responses.

        Raise a ValueError if ph responds with an error."""

        self.clear()

        self.proc.writeline('query ' + q)
        got = []; it = {}
        while 1:
            response = self.getreply()      # Should get null on new prompt.
            errs = self.proc.readPendingErrChars()
            if errs:
                bytes_write(sys.stderr.fileno(), errs)
            if it:
                got.append(it)
                it = {}
            if not response:
                return got                                              # ===>
            elif isinstance(response, (str, unicode)):
                raise ValueError("ph failed match: '%s'" % response)
            for line in response:
                # convert to a dict:
                line = line.split(':')
                it[line[0].strip()] = ' '.join(line[1:]).strip()

    def getreply(self):
        """Consume next response from ph, returning list of lines or string
        err."""
        # Key on first char:  (First line may lack newline.)
        #  - dash               discard line
        #  - 'ph> '     conclusion of response
        #  - number     error message
        #  - whitespace beginning of next response

        nextChar = self.proc.waitForPendingChar(60)
        if not nextChar:
            raise SubprocessError('ph subprocess not responding')
        elif nextChar == '-':
            # dashed line - discard it, and continue reading:
            self.proc.readline()
            return self.getreply()                                      # ===>
        elif nextChar == 'p':
            # 'ph> ' prompt - don't think we should hit this, but what the hay:
            return ''                                                   # ===>
        elif nextChar in '0123456789':
            # Error notice - we're currently assuming single line errors:
            return self.proc.readline()[:-1]                            # ===>
        elif nextChar in ' \t':
            # Get content, up to next dashed line:
            got = []
            while nextChar != '-' and nextChar != '':
                got.append(self.proc.readline()[:-1])
                nextChar = self.proc.peekPendingChar()
            return got
    def __repr__(self):
        return "<Ph instance, %s at %s>\n" % (self.proc.status(),
                                                hex(id(self))[2:])
    def clear(self):
        """Clear-out initial preface or residual subproc input and output."""
        pause = .5; maxIter = 10                # 5 seconds to clear
        iterations = 0
        got = ''
        self.proc.write('')
        while iterations < maxIter:
            got = got + self.proc.readPendingChars()
            # Strip out all but the last incomplete line:
            got = got.split('\n')[-1]
            if got == 'ph> ': return        # Ok.                       ===>
            time.sleep(pause)
        raise SubprocessError('ph not responding within %s secs' %
                                                        pause * maxIter)
