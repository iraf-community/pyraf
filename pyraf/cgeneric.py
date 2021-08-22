"""cgeneric.py: Context-sensitive scanner class

Maintains a stack of instances of John Aycock's generic.py scanner
class and allows context-sensitive switches between them.

Self.current is a stack (list) of integers, with the last value
pointing to the current scanner to use; by default it is initialized
to zero.  The ContextSensitiveScanner object is passed to the action
functions, which are permitted to access and modify the current stack
in order to change the state.  The ContextSensitiveScanner object
should also be used for instance-specific attributes (e.g., the
generated token list and current line number) so that the same
scanners list can be used by several different ContextSensitiveScanner
objects.

I also added the re match object as an argument to the action function.

Created 1999 September 10 by R. White
"""



class ContextSensitiveScanner:
    """Context-sensitive scanner"""

    def __init__(self, scanners, start=0):
        # scanners is a list or dictionary containing the
        # stack of scanners
        # start is default starting state
        self.scanners = scanners
        self.start = start

    def tokenize(self, s, start=None):
        if start is None:
            start = self.start
        self.current = [start]
        iend = 0
        slen = len(s)
        while iend < slen:
            if not self.current:
                self.current = [start]
            scanner = self.scanners[self.current[-1]]
            m = scanner.re.match(s, iend)
            assert m
            groups = m.groups()
            for i in scanner.indexlist:
                if groups[i] is not None:
                    scanner.index2func[i](groups[i], m, self)
                    # assume there is only a single match
                    break
            else:
                print('cgeneric: No group found in match?')
                print('Returning match object for debug')
                self.rv = m
                return
            iend = m.end()
