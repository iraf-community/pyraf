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

$Id$

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
		if start is None: start = self.start
		self.current = [start]
		iend = 0
		slen = len(s)
		while iend < slen:
			if not self.current: self.current = [start]
			icur = self.current[-1]
			m = self.scanners[icur].re.match(s, iend)
			assert m

			j = 0
			for i in self.scanners[icur].indexlist:
				# code to check for group i match lifted from re
				a, b = m.regs[i]
				if a != -1 and b != -1:
					grp = s[a:b]
					self.scanners[icur].index2func[i](grp,m,self)
					# move-to-front strategy to speed up searches
					if j > 0:
						del self.scanners[icur].indexlist[j]
						self.scanners[icur].indexlist.insert(0, i)
					# assume there is only a single match
					break
				j = j+1
			else:
				print 'No group found in match?'
				print 'Returning match object for debug'
				self.rv = m
				return
			iend = m.end()

