"""Run a subprocess and communicate with it via stdin, stdout, and stderr.

Requires that platform supports, eg, posix-style os.pipe and os.fork.

Subprocess class features:

 - provides non-blocking stdin and stderr reads

 - provides subprocess stop and continue, kill-on-deletion

 - provides detection of subprocess startup failure

 - Subprocess objects have nice, informative string rep (as every good object
   ought).

 - RecordFile class provides record-oriented IO for file-like stream objects.

$Id$
"""

__version__ = "Revision: 1.7r "

# Id: subproc.py,v 1.7r 1998
# Originally by ken manheimer, ken.manheimer@nist.gov, jan 1995.
# Major revisions by R. White, rlw@stsci.edu, 1999 Jan 23

# Prior art: Initially based python code examples demonstrating usage of pipes
#			 and subprocesses, primarily one by jose pereira.

# Implementation notes:
# - I'm not using the fcntl module to implement non-blocking file descriptors,
#	because i don't know what all in it is portable and what is not.  I'm not
#	about to provide for different platform contingencies - at that extent, the
#	effort would be better spent hacking 'expect' into python.
# - Todo? - Incorporate an error-output handler approach, where error output is
#			checked on regular IO, when a handler is defined, and passed to the
#			handler (eg for printing) immediately as it shows...
# - Detection of failed subprocess startup is a gross kludge, at present.

# - new additions (1.3, 1.4):
#  - Readbuf, taken from donn cave's iobuf addition, implements non-blocking
#	 reads based solely on os.read with select, while capitalizing big-time on
#	 multi-char read chunking.
#  - Subproc deletion frees up pipe file descriptors, so they're not exhausted.
#
# ken.manheimer@nist.gov


import sys, os, string, time, types
import select
import signal


try:
	class SubprocessError(Exception):
		pass
except TypeError:
	# string based exceptions
	SubprocessError = 'SubprocessError'

# I have deleted this sleep because it does not seem to be necessary. rlw
# You may need to increase execvp_grace_seconds, if you have a large or slow
# path to search:
# execvp_grace_seconds = 0.1

class Subprocess:
	"""Run and communicate asynchronously with a subprocess.

	Provides non-blocking reads in the form of .readPendingChars and
	.readPendingLine.

	.readline will block until it gets a complete line.

	.peekPendingChar does a non-blocking, non-consuming read for pending
	output, and can be used before .readline to check non-destructively for
	pending output.  .waitForPendingChar(timeout) blocks until
	a new character is pending, or timeout secs pass, with granularity of
	pollPause seconds.

	There are corresponding read and peekPendingErrXXX routines, to read from
	the subprocess stderr stream."""

	def __init__(self, cmd, control_stderr=0, expire_noisily=0,
				 in_fd=0, out_fd=1, err_fd=2, maxChunkSize=1024):
		"""Launch a subprocess, given command string COMMAND."""
		self.cmd = cmd
		self.pid = None
		self.expire_noisily = expire_noisily	# Announce subproc destruction?
		self.control_stderr = control_stderr
		self.maxChunkSize = maxChunkSize
		self.in_fd, self.out_fd, self.err_fd = in_fd, out_fd, err_fd
		self.readbuf = None 					# fork will assign to be a ReadBuf obj
		self.errbuf = None						# fork will assign to be a ReadBuf obj
		self.fork()

	def fork(self, cmd=None):
		"""Fork a subprocess with designated COMMAND (default, self.cmd)."""
		if cmd: self.cmd = cmd
		if type(self.cmd) == types.StringType:
			cmd = string.split(self.cmd)
		else:
			cmd = self.cmd
		# Create pipes
		pRc, cWp = os.pipe()			# parent-read-child, child-write-parent
		cRp, pWc = os.pipe()			# child-read-parent, parent-write-child
		self.parentPipes = [pRc, pWc]
		childPipes = [cWp, cRp]
		if self.control_stderr:
			pRe, cWe = os.pipe()		# parent-read-error, child-write-error
			self.parentPipes.append(pRe)
			childPipes.append(cWe)

		self.pid = os.fork()

		if self.pid == 0:		#### CHILD ####
			parentErr = os.dup(self.in_fd) # Preserve handle on *parent* stderr
			# Reopen stdin, out, err, on pipe ends:
			os.dup2(cRp, self.in_fd)			# cRp = sys.stdin
			os.dup2(cWp, self.out_fd)			# cWp = sys.stdout
			if self.control_stderr:
				os.dup2(cWe, self.err_fd)		# cWe = sys.stderr
			# close parent ends of pipes
			for i in self.parentPipes: os.close(i)
			# Ensure (within reason) stray file descriptors are closed:
			excludes = [self.in_fd, self.out_fd, self.err_fd, parentErr]
			for i in range(4,100):
				if i not in excludes:
					try: os.close(i)
					except os.error: pass
			try:
				os.execvp(cmd[0], cmd)
				os._exit(1) 					# Shouldn't get here

			except os.error, e:
				if self.control_stderr:
					os.dup2(parentErr, 2)		# Reconnect to parent's stdout
				sys.stderr.write("**execvp failed, '%s'**\n" % str(e))
				os._exit(1)
			os._exit(1) 				# Shouldn't get here.

		else:			### PARENT ###
			# Connect to the child's file descriptors and close child ends of pipes
			self.toChild = os.fdopen(pWc, 'w')
			self.toChild_fdlist = [pWc]
			self.readbuf = ReadBuf(pRc,self.maxChunkSize)
			if self.control_stderr:
				self.errbuf = ReadBuf(pRe,self.maxChunkSize)
			# close child ends of pipes
			for i in childPipes: os.close(i)
			# I have deleted this sleep because it does not seem to be necessary. rlw
			# time.sleep(execvp_grace_seconds)
			try:
				pid, err = os.waitpid(self.pid, os.WNOHANG)
			except os.error, (errno, msg):
				if errno == 10:
					raise SubprocessError, ("Subprocess '%s' failed." % self.cmd)
				else:
					raise SubprocessError, ("Subprocess failed[%d]: %s" % (errno, msg))
			if pid == self.pid:
				# child exited already
				if self.expire_noisily: self.__noisy_print(err)
				self.pid = None
				sig = err & 0xff
				rc = (err & 0xff00) >> 8
				if sig:
					raise SubprocessError, (
						"child killed by signal %d with a return code of %d"
						% (sig, rc))
				if rc:
					raise SubprocessError, (
						  "child exited with return code %d" % rc)
				# Child may have exited, but not in error, so we won't say
				# anything more at this point.

	### Write input to subprocess ###

	def write(self, str, timeout=10, printtime=2):
		"""Write a STRING to the subprocess.  Times out (and raises an
		exception) if the process is not ready in timeout seconds.
		Prints a message indicating that it is waiting every
		printtime seconds."""

		if not self.pid:
			raise SubprocessError, ("no child process")				# ===>

		# See if subprocess is ready for write.
		# Add a wait in case subprocess is still starting up or is
		# otherwise temporarily unable to respond.
		# Loop with message if wait takes longer than that, until wait
		# exceeds the total timeout.

		if timeout < 0: timeout = 0
		if printtime>timeout: printtime = timeout
		totalwait = 0
		while totalwait <= timeout:
			if totalwait: print "waiting for subprocess..."
			totalwait = totalwait + printtime
			if select.select([],self.toChild_fdlist,[],printtime)[1]:
				self.toChild.write(str)
				self.toChild.flush()
				return												# ===>
		raise SubprocessError, "write to %s blocked" % self			# ===>

	def writeline(self, line=''):
		"""Write STRING, with added newline termination, to subprocess."""
		self.write(line + '\n')

	def closeOutput(self):
		"""Close write pipe to subprocess"""
		self.toChild.close()

	### Get output from subprocess ###

	def peekPendingChar(self):
		"""Return, but (effectively) do not consume a single pending output
		char, or return null string if none pending."""

		return self.readbuf.peekPendingChar()

	def peekPendingErrChar(self):
		"""Return, but (effectively) do not consume a single pending output
		error char, or return null string if none pending."""

		if self.control_stderr:
			return self.errbuf.peekPendingChar()
		else:
			raise SubprocessError, ("Haven't grabbed subprocess error stream.")

	def waitForPendingChar(self, timeout, pollPause=.1):
		"""Block max TIMEOUT secs until we peek a pending char, returning the
		char, or '' if none encountered.
		pollPause is included for backward compatibility, but does nothing."""
		
		return self.readbuf.peekPendingChar(timeout)

	def waitForPendingErrChar(self, timeout, pollPause=.1):
		"""Block max TIMEOUT secs until we peek a pending error char, returning the
		char, or '' if none encountered.
		pollPause is included for backward compatibility, but does nothing."""
		
		if self.control_stderr:
			return self.errbuf.peekPendingChar(timeout)
		else:
			raise SubprocessError, ("Haven't grabbed subprocess error stream.")

	def read(self, n=None):
		"""Read N chars (blocking), or all pending if no N specified."""
		if n is None:
			return self.readPendingChars()
		else:
			return self.readbuf.read(n)

	def readErr(self, n=None):
		"""Read N chars from stderr (blocking), or all pending if no N specified."""
		if self.control_stderr:
			if n is None:
				return self.readPendingErrChars()
			else:
				return self.errbuf.read(n)
		else:
			raise SubprocessError, ("Haven't grabbed subprocess error stream.")

	def readPendingChars(self, max=None):
		"""Read all currently pending subprocess output as a single string."""
		return self.readbuf.readPendingChars(max)

	def readPendingErrChars(self, max=None):
		"""Read all currently pending subprocess error output as a single
		string."""
		if self.control_stderr:
			return self.errbuf.readPendingChars(max)
		else:
			raise SubprocessError, ("Haven't grabbed subprocess error stream.")

	def readPendingLine(self):
		"""Read currently pending subprocess output, up to a complete line
		(newline inclusive)."""
		return self.readbuf.readPendingLine()

	def readPendingErrLine(self):
		"""Read currently pending subprocess error output, up to a complete
		line (newline inclusive)."""
		if self.control_stderr:
			return self.errbuf.readPendingLine()
		else:
			raise SubprocessError, ("Haven't grabbed subprocess error stream.")

	def readline(self):
		"""Return next complete line of subprocess output, blocking until
		then."""
		return self.readbuf.readline()
	def readlineErr(self):
		"""Return next complete line of subprocess error output, blocking until
		then."""
		if self.control_stderr:
			return self.errbuf.readline()
		else:
			raise SubprocessError, ("Haven't grabbed subprocess error stream.")

	### Subprocess Control ###

	def active(self):
		"""True if subprocess is alive and kicking."""
		return self.status(boolean=1)

	def status(self, boolean=0):
		"""Return string indicating whether process is alive or dead."""
		active = 0
		if not self.cmd:
			status = 'sans command'
		elif not self.pid:
			status = 'sans process'
		elif not self.cont():
			status = "(unresponding) '%s'" % self.cmd
		else:
			status = "'%s'" % self.cmd
			active = 1
		if boolean:
			return active
		else:
			return status

	def wait(self,timeout=0):
		"""Wait timeout seconds for process to die.  Returns true if process
		is dead (and was reaped), false if alive."""
		# Try a few times to reap the process with waitpid:
		totalwait = timeout
		deltawait = timeout/10.0
		if deltawait < 0.01: deltawait = 0.01
		while totalwait >= 0:
			pid, err = os.waitpid(self.pid, os.WNOHANG)
			if pid:
				if self.expire_noisily: self.__noisy_print(err)
				for p in self.parentPipes:
					try: os.close(p)
					except os.error: pass
				self.pid = None
				return 1
			time.sleep(deltawait)
			totalwait = totalwait - deltawait
		return 0

	def __noisy_print(self,err):
		sig = err & 0xff
		rc = (err & 0xff00) >> 8
		if sig == 0:
			sigval = ''
		elif sig == signal.SIGTERM:
			sigval = 'TERMinated '
		elif sig == signal.SIGKILL:
			sigval = 'KILLed '
		else:
			sigval = 'Signal %d ' % sig
		if rc:
			retval = 'Status %d ' % rc
		else:
			retval = ''
		print ("\n(%ssubproc %d '%s' %s/ %s)" %
			   (sigval, self.pid, self.cmd, retval,
				hex(id(self))[2:]))

	def stop(self, verbose=1):
		"""Signal subprocess with STOP (17), returning 'stopped' if ok, or 0
		otherwise."""
		try:
			os.kill(self.pid, signal.SIGSTOP)
		except os.error:
			if verbose:
				print "Stop failed for '%s' - '%s'" % (self.cmd, sys.exc_value)
			return 0
		if verbose: print "Stopped '%s'" % self.cmd
		return 'stopped'

	def cont(self, verbose=0):
		"""Signal subprocess with CONT (19), returning 'continued' if ok, or 0
		otherwise."""
		try:
			os.kill(self.pid, signal.SIGCONT)
		except os.error:
			if verbose:
				print ("Continue failed for '%s' - '%s'" %
					   (self.cmd, sys.exc_value))
			return 0
		if verbose: print "Continued '%s'" % self.cmd
		return 'continued'

	def die(self):
		"""Send process PID signal SIG (default 9, 'kill'), returning once
		 it is successfully reaped.

		SubprocessError is raised if process is not successfully killed."""

		if not self.pid:
			raise SubprocessError, ("No process") 						# ===>
		elif not self.cont():
			raise SubprocessError, ("Can't signal subproc %s" % self) 	# ===>

		# Try sending first a TERM and then a KILL signal.
		sigs = [('TERM', signal.SIGTERM), ('KILL', signal.SIGKILL)]
		for sig in sigs:
			try:
				os.kill(self.pid, sig[1])
			except os.error:
				# keep trying
				pass
			# done if we can reap the process; else try next signal
			if self.wait(0.5): return		 							# ===>
		# Only got here if subprocess is not gone:
		raise SubprocessError, (
				"Failed kill of subproc %d, '%s', with signals %s" %
				(self.pid, self.cmd, map(lambda(x): x[0], sigs)))		# ===>

	def __del__(self):
		"""Terminate the subprocess"""
		if self.pid and not self.wait(0): self.die()

	def __repr__(self):
		status = self.status()
		return '<Subprocess ' + status + ', at ' + hex(id(self))[2:] + '>'

#############################################################################
#####				  Non-blocking read operations						#####
#############################################################################

class ReadBuf:
	"""Output buffer for non-blocking reads on selectable files like pipes and
	sockets.  Init with a file descriptor for the file."""

	def __init__(self, fd, maxChunkSize=1024):
		"""Encapsulate file descriptor FD, with optional MAX_READ_CHUNK_SIZE
		(default 1024)."""

		if fd < 0:
			raise ValueError("File descriptor fd is negative")
		self.fd = fd
		self.eof = 0					# May be set with stuff still in .buf
		self.buf = ''
		self.chunkSize = maxChunkSize	# Biggest read chunk, default 1024.

	def fileno(self):
		return self.fd

	def peekPendingChar(self,timeout=0):
		"""Return, but don't consume, first character of unconsumed output from
		file, or empty string if none.  If timeout is set, waits maximum of
		timeout seconds before returning.  Default is timeout=0 (do not wait
		at all.)"""

		if self.buf: return self.buf[0]									# ===>

		if self.eof: return ''											# ===>

		sel = select.select([self.fd], [], [self.fd], timeout)
		if sel[0]:
			self.buf = os.read(self.fd, self.chunkSize)
			if self.buf:
				return self.buf[0] 										# ===>
			else:
				self.eof = 1
				return ''	 											# ===>
		else: return '' 												# ===>

	def readPendingChar(self):
		"""Consume first character of unconsumed output from file, or empty
		string if none."""

		if self.buf:
			got, self.buf = self.buf[0], self.buf[1:]
			return got													# ===>

		if self.eof: return ''											# ===>

		sel = select.select([self.fd], [], [self.fd], 0)
		if sel[0]:
			self.buf = os.read(self.fd, self.chunkSize)
			if self.buf:
				got, self.buf = self.buf[0], self.buf[1:]
				return got
			else:
				self.eof = 1
				return ''												# ===>
		else: return '' 												# ===>

	def readPendingChars(self, max=None):
		"""Consume uncomsumed output from FILE, or empty string if nothing
		pending."""

		if (max is not None) and (max <= 0): return ''					# ===>

		if self.buf:
			if max and (len(self.buf) > max):
				got, self.buf = self.buf[0:max], self.buf[max:]
			else:
				got, self.buf = self.buf, ''
			return got													# ===>

		if self.eof: return ''											# ===>

		sel = select.select([self.fd], [], [self.fd], 0)
		if sel[0]:
			got = os.read(self.fd, self.chunkSize)
			if got:
				if max and (len(got) > max):
					self.buf = got[max:]
					return got[:max]									# ===>
				else:
					return got											# ===>
			else:
				self.eof = 1
				return ''												# ===>
		else: return ''													# ===>

	def readPendingLine(self, block=0):
		"""Return pending output from FILE, up to first newline (inclusive).

		Does not block unless optional arg BLOCK is true.  This may return
		a partial line if the input line is longer than chunkSize (default
		1024) characters."""

		if self.buf:
			to = string.find(self.buf, '\n')
			if to != -1:
				got, self.buf = self.buf[:to+1], self.buf[to+1:]
				return got												# ===>
			got, self.buf = self.buf, ''
		elif self.eof:
			return ''													# ===>
		else:
			got = ''

		# 'got' contains the (former) contents of the buffer, but it
		# doesn't include a newline.
		fdlist = [self.fd]
		if block:
			# wait indefinitely for input
			waittime = None
		else:
			# don't wait at all
			waittime = 0
		while 1:						# (we'll only loop if block set)
			sel = select.select(fdlist, [], fdlist, waittime)
			if sel[0]:
				newgot = os.read(self.fd, self.chunkSize)
				if newgot:
					got = got + newgot
					to = string.find(got, '\n')
					if to != -1:
						got, self.buf = got[:to+1], got[to+1:]
						return got										# ===>
				else:
					# return partial line on EOF
					self.eof = 1
					return got											# ===>
			if not block:
				return got												# ===>
			# otherwise - no newline, blocking requested, no eof - loop. # ==^

	def readline(self):
		"""Return next output line from file, blocking until it is received."""

		return self.readPendingLine(1)									# ===>

	def read(self, nchars):
		"""Read nchars from input, blocking until they are available.
		Returns a shorter string on EOF."""

		if nchars <= 0: return ''
		if self.buf:
			if len(self.buf) >= nchars:
				got, self.buf = self.buf[:nchars], self.buf[nchars:]
				return got												# ===>
			got, self.buf = self.buf, ''
		elif self.eof:
			return ''													# ===>
		else:
			got = ''

		fdlist = [self.fd]
		while 1:
			sel = select.select(fdlist, [], fdlist)
			if sel[0]:
				newgot = os.read(self.fd, self.chunkSize)
				if newgot:
					got = got + newgot
					if len(got) >= nchars:
						got, self.buf = got[:nchars], got[nchars:]
						return got										# ===>
				else:
					self.eof = 1
					return got
			else:
				print 'Select returned without input?'


#############################################################################
#####				  Encapsulated reading and writing					#####
#############################################################################
# Encapsulate messages so the end can be unambiguously identified, even
# when they contain multiple, possibly empty lines.

class RecordFile:
	"""Encapsulate stream object for record-oriented IO.

	Particularly useful when dealing with non-line oriented communications
	over pipes, eg with subprocesses."""

	# Message is written preceded by a line containing the message length.

	def __init__(self, f):
		self.file = f

	def write_record(self, s):
		"Write so self.read knows exactly how much to read."
		f = self.__dict__['file']
		f.write("%s\n%s" % (len(s), s))
		if hasattr(f, 'flush'):
			f.flush()

	def read_record(self):
		"Read and reconstruct message as prepared by self.write."
		f = self.__dict__['file']
		line = f.readline()[:-1]
		if line:
			try:
				l = string.atoi(line)
			except ValueError:
				raise IOError, ("corrupt %s file structure"
								% self.__class__.__name__)
			return f.read(l)
		else:
			# EOF.
			return ''

	def __getattr__(self, attr):
		"""Implement characteristic file object attributes."""
		f = self.__dict__['file']
		if hasattr(f, attr):
			return getattr(f, attr)
		else:
			raise AttributeError, attr

	def __repr__(self):
		return "<%s of %s at %s>" % (self.__class__.__name__,
									 self.__dict__['file'],
									 hex(id(self))[2:])

def record_trial(s):
	"""Exercise encapsulated write/read with an arbitrary string.

	Raise IOError if the string gets distorted through transmission!"""
	from StringIO import StringIO
	sf = StringIO()
	c = RecordFile(sf)
	c.write(s)
	c.seek(0)
	r = c.read()
	show = " start:\t %s\n end:\t %s\n" % (`s`, `r`)
	if r != s:
		raise IOError, "String distorted:\n%s" % show

#############################################################################
#####					An example subprocess interfaces				#####
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
			raise SubprocessError, ("failure starting ph: %s" %	 		# ===>
									str(sys.exc_value))

	def query(self, q):
		"""Send a query and return a list of dicts for responses.

		Raise a ValueError if ph responds with an error."""

		self.clear()

		self.proc.writeline('query ' + q)
		got = []; it = {}
		while 1:
			response = self.getreply()	# Should get null on new prompt.
			errs = self.proc.readPendingErrChars()
			if errs:
				sys.stderr.write(errs)
			if it:
				got.append(it)
				it = {}
			if not response:
				return got												# ===>
			elif type(response) == types.StringType:
				raise ValueError, "ph failed match: '%s'" % response	# ===>
			for line in response:
				# convert to a dict:
				line = string.splitfields(line, ':')
				it[string.strip(line[0])] = (
					string.strip(string.join(line[1:])))
		
	def getreply(self):
		"""Consume next response from ph, returning list of lines or string
		err."""
		# Key on first char:  (First line may lack newline.)
		#  - dash		discard line
		#  - 'ph> ' 	conclusion of response
		#  - number 	error message
		#  - whitespace beginning of next response

		nextChar = self.proc.waitForPendingChar(60)
		if not nextChar:
			raise SubprocessError, ('ph subprocess not responding')		# ===>
		elif nextChar == '-':
			# dashed line - discard it, and continue reading:
			self.proc.readline()
			return self.getreply()										# ===>
		elif nextChar == 'p':
			# 'ph> ' prompt - don't think we should hit this, but what the hay:
			return ''													# ===>
		elif nextChar in '0123456789':
			# Error notice - we're currently assuming single line errors:
			return self.proc.readline()[:-1]							# ===>
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
		pause = .5; maxIter = 10		# 5 seconds to clear
		iterations = 0
		got = ''
		self.proc.write('')
		while iterations < maxIter:
			got = got + self.proc.readPendingChars()
			# Strip out all but the last incomplete line:
			got = string.splitfields(got, '\n')[-1]
			if got == 'ph> ': return	# Ok.							  ===>
			time.sleep(pause)
		raise SubprocessError, ('ph not responding within %s secs' %
								pause * maxIter)

#############################################################################
#####							  Test									#####
#############################################################################

def test():
	print "\tOpening subprocess:"
	p = Subprocess('cat', expire_noisily=1)			# set to expire noisily...
	print p
	print "\tOpening bogus subprocess, should fail:"
	try:
		# grab stderr just to make sure the error message still appears 
		b = Subprocess('/', 1, expire_noisily=1)
		print "\tOops!	Null-named subprocess startup *succeeded*?!?"
	except SubprocessError:
		print "\t...yep, it failed."
	print '\tWrite, then read, two newline-terminated lines, using readline:'
	p.write('first full line written\n'); p.write('second.\n')
	print `p.readline()`
	print `p.readline()`
	print '\tThree lines, last sans newline, read using combination:'
	p.write('first\n'); p.write('second\n'); p.write('third, (no cr)')
	print '\tFirst line via readline:'
	print `p.readline()`
	print '\tRest via readPendingChars:'
	print p.readPendingChars()
	print "\tStopping then continuing subprocess (verbose):"
	if not p.stop(1):					# verbose stop
		print '\t** Stop seems to have failed!'
	else:
		print '\tWriting line while subprocess is paused...'
		p.write('written while subprocess paused\n')
		print '\tNonblocking read of paused subprocess (should be empty):'
		print p.readPendingChars()
		print '\tContinuing subprocess (verbose):'
		if not p.cont(1):				# verbose continue
			print '\t** Continue seems to have failed!	Probly lost subproc...'
			return p
		else:
			print '\tReading accumulated line, blocking read:'
			print p.readline()
			print "\tDeleting subproc, which was set to die noisily:"
			del p
			print "\tDone."
			return None

if __name__ == "__main__":
	test()
