"""irafexecute.py: Functions to execute IRAF connected subprocesses

$Id$
"""

import os, re, signal, string, struct, sys, time, types, Numeric, cStringIO
import subproc, iraf, gki, gkiopengl, gwm, wutil, irafutils, iraftask

stdgraph = None
firstPlotDone = 0

IPC_PREFIX = Numeric.array([01120],Numeric.Int16).tostring()

class IrafProcessError(Exception):
	pass

def _getExecutable(arg):
	"""Get executable pathname.
	
	Arg may be a string with the path, an IrafProcess, an IrafTask,
	or a string with the name of an IrafTask.
	"""
	if isinstance(arg, IrafProcess):
		return arg.executable
	elif isinstance(arg, iraftask.IrafTask):
		return arg.getFullpath()
	elif isinstance(arg, types.StringType):
		if os.path.exists(arg):
			return arg
		task = iraf.getTask(arg, found=1)
		if task:
			return task.getFullpath()
	raise IrafProcessError("Cannot find task or executable %s" % arg)

class _ProcessCache:

	"""Cache of active processes indexed by executable path"""

	def __init__(self, limit=8):
		self._data = {}          # dictionary with active processes
		self._pcount = 0         # total number of processes started
		self._plimit = limit     # number of active processes allowed
		self._locked = {}        # processes locked into cache

	def get(self, task, envdict):
		"""Get process for given task.  Create a new one if needed."""
		executable = _getExecutable(task)
		value = self._data.get(executable)
		if value is None:
			# create and initialize a new process
			process = IrafProcess(executable)
			process.initialize(envdict)
		else:
			# use existing process
			rank, process = value
		return process

	def add(self, process):
		"""Add process to cache or update its rank if already there"""
		if self._plimit <= len(self._locked):
			# no cache if plimit is zero or if all processes are locked
			process.terminate()
			return
		self._pcount = self._pcount+1
		executable = process.executable
		if (len(self._data) >= self._plimit) and \
		  not self._data.has_key(executable):
			# delete the oldest entry
			self._deleteOldest()
		self._data[executable] = (self._pcount, process)

	def _deleteOldest(self):
		"""Delete oldest unlocked process from the cache
		
		If all processes are locked, delete oldest locked process.
		"""
		# each entry contains rank (to sort and find oldest) and process
		values = self._data.values()
		values.sort()
		if len(self._locked) >= len(self._data):
			rank, oldprocess = values[0]
			self.terminate(oldprocess.executable)
		else:
			for rank, oldprocess in values:
				executable = oldprocess.executable
				if not self._locked.has_key(executable):
					# terminate it
					self.terminate(executable)

	def setenv(self, msg):
		"""Update process value of environment variable by sending msg"""
		for rank, process in self._data.values():
			process.writeString(msg)

	def setSize(self, limit):
		"""Set number of processes allowed in cache"""
		self._plimit = limit
		if self._plimit <= 0:
			self._locked = {}
			self.flush()
		else:
			while len(self._data) > self._plimit:
				self._deleteOldest()

	def lock(self, *args):
		"""Lock the specified tasks into the cache
		
		Takes task names (strings) as arguments.
		"""
		# don't bother if cache is disabled or full
		if self._plimit <= len(self._locked):
			return
		for taskname in args:
			task = iraf.getTask(taskname, found=1)
			if not task:
				print "No such task `%s'" % taskname
			elif task.__class__ == iraftask.IrafTask:
				# cache only executable tasks (not CL tasks, etc.)
				executable = task.getFullpath()
				process = self.get(task, iraf.getVarDict())
				self.add(process)
				if self._data.has_key(executable):
					self._locked[executable] = 1
				else:
					if iraf.Verbose>0: print "Cannot cache %s" % taskname

	def kill(self, process):
		"""Kill process and delete it from cache"""
		executable = _getExecutable(process)
		if self._data.has_key(executable):
			rank, process = self._data[executable]
			del self._data[executable]
			if self._locked.has_key(executable):
				del self._locked[executable]
				#XXX could restart the process if locked
		if isinstance(process, IrafProcess):
			process.kill()

	def terminate(self, process):
		"""Terminate process and delete it from cache"""
		# This is gentler than kill(), which should be used only
		# when there are process errors.
		executable = _getExecutable(process)
		if self._data.has_key(executable):
			rank, process = self._data[executable]
			del self._data[executable]
			if self._locked.has_key(executable):
				del self._locked[executable]
				#XXX could restart the process if locked
		if isinstance(process, IrafProcess):
			process.terminate()

	def flush(self, *args):
		"""Flush given processes (all non-locked if no args given)
		
		Takes task names (strings) as arguments.
		"""
		if args:
			for taskname in args:
				task = iraf.getTask(taskname, found=1)
				if task: self.terminate(task)
		else:
			for rank, process in self._data.values():
				executable = process.executable
				if not self._locked.has_key(executable):
					self.terminate(executable)

	def list(self):
		"""List processes sorted from newest to oldest with locked flag"""
		values = self._data.values()
		values.sort()
		values.reverse()
		n = 0
		for rank, process in values:
			n = n+1
			executable = process.executable
			if self._locked.has_key(executable):
				print "%2d: L %s" % (n, executable)
			else:
				print "%2d:   %s" % (n, executable)

	def __del__(self):
		self._locked = {}
		self.flush()

processCache = _ProcessCache()

def IrafExecute(task, envdict, stdin=None, stdout=None, stderr=None):

	"""Execute IRAF task (defined by the IrafTask object task)
	using the provided envionmental variables."""

	global firstPlotDone, processCache
	try:
		# Start 'er up
		irafprocess = processCache.get(task, envdict)
	except (iraf.IrafError, subproc.SubprocessError, IrafProcessError), value:
		raise IrafProcessError("Cannot start IRAF executable\n" + value)

	# Run it
	try:
		irafprocess.run(task, stdin=stdin,stdout=stdout,stderr=stderr)
		wutil.focusController.restoreLast()
		if stdgraph:
			stdgraph.stdout = None
			stdgraph.stderr = None
	except KeyboardInterrupt:
		# On keyboard interrupt (^C), kill the subprocess
		processCache.kill(irafprocess)
		wutil.focusController.resetFocusHistory()
		if stdgraph:
			stdgraph.stdout = None
			stdgraph.stderr = None
		raise KeyboardInterrupt
	except (iraf.IrafError, IrafProcessError), exc:
		# on error, kill the subprocess, then re-raise the original exception
		try:
			processCache.kill(irafprocess)
		except Exception, exc2:
			# append new exception text to previous one (right thing to do?)
			exc.args = exc.args + exc2.args
		raise exc
	else:
		# add to the process cache on successful exit
		processCache.add(irafprocess)
	# this next bit is really a hack to prevent the double redraw on first
	# plots (when they are not interactive plots). This should be done
	# better, but it appears to work.
	if not firstPlotDone and wutil.hasGraphics:
		gwin = gwm.getActiveWindow()
		if gwin:
			if gwin.interactive:
				interactive = 0
			else:
				gwin.ignoreNextNRedraws = 2
			firstPlotDone = 1
	return

# patterns for matching messages from process

# '=param' and '_curpack' have to be treated specially because
# they write to the task rather than to stdout
# 'param=value' is special because it allows errors

_p_par_get = r'=(?P<gname>[a-zA-Z_$][\w.]*(?:\[\d+\])?)\n'
_p_par_set = r'(?P<sname>[a-zA-Z_][\w.]*(?:\[\d+\])?)\s*=\s*(?P<svalue>.*)\n'
_re_msg = re.compile(
			r'(?P<par_get>' + _p_par_get + ')|' +
			r'(?P<par_set>' + _p_par_set + ')'
			)

_p_curpack   = r'_curpack(?:\s.*|)\n'
_p_sysescape = r'!!(?P<sys_cmd>.*)\n'

_re_clcmd = re.compile(
			r'(?P<curpack>'   + _p_curpack   + ')|' +
			r'(?P<sysescape>' + _p_sysescape + ')'
			)

class IrafProcess:

	"""IRAF process class"""

	def __init__(self, executable):

		"""Start IRAF task executable."""

		self.executable = executable
		self.process = subproc.Subprocess(executable+' -c')

	def initialize(self, envdict):

		"""Initialization: Copy environment variables to process"""

		outenvstr = []
		for key, value in envdict.items():
			outenvstr.append("set %s=%s\n" % (key, str(value)))
		outenvstr.append("chdir %s\n" % os.getcwd())
		if outenvstr: self.writeString(string.join(outenvstr,""))

		# end set up mode
		self.writeString('_go_\n')

	def run(self, task, stdin=None, stdout=None, stderr=None):

		"""Run the IRAF logical task (which must be in this executable)

		The IrafTask object must have these methods:

		getName(): return the name of the task
		getParam(param): get parameter value
		setParam(param,value): set parameter value
		"""

		self.task = task
		# set IO streams
		if stdin is None: stdin = sys.stdin
		if stdout is None:
			if stderr is not None:
				stdout = stderr
			else:
				stdout = sys.stdout
		if stderr is None: stderr = sys.stderr
		self.stdin = stdin
		self.stdout = stdout
		self.stderr = stderr
		self.default_stdout = stdout
		self.default_stderr = stderr
		try:
			self.isatty = self.stdin.isatty()
		except:
			self.isatty = 0

		# redir_info tells task that IO has been redirected

		redir_info = ''
		if stdin != sys.__stdin__: redir_info = '<'
		if stdout != sys.__stdout__: redir_info = redir_info+'>'

		# if stdout is a terminal, set the lines & columns sizes
		# this ensures that they are up-to-date at the start of the task
		# (which is better than the CL does)
		if stdout.isatty():
			iraf.stty('resize')

		self.writeString(self.task.getName()+redir_info+'\n')
		# begin slave mode
		self.slave()

	def terminate(self):

		"""Terminate the IRAF process"""

		# Standard IRAF task termination (assuming we already have the
		# task's attention for input):
		#   Send bye message to task
		#   Wait briefly for EOF, which signals task is done
		#   Kill it anyway if it is still hanging around

		if self.process.pid:
			self.writeString("bye\n")
			if not self.process.wait(0.5): self.process.die()

	def kill(self):

		"""Kill the IRAF process"""

		# Try stopping process in IRAF-approved way first; if that fails
		# blow it away. Copied with minor mods from subproc.py.

		if not self.process.pid: return		# no need, process gone

		self.stdout.flush()
		self.stderr.flush()
		sys.stderr.write("Killing IRAF task `%s'\n" % self.task.getName())
		sys.stderr.flush()
		if not self.process.cont():
			raise IrafProcessError("Can't kill IRAF subprocess")
		# get the task's attention for input
		try:
			os.kill(self.process.pid, signal.SIGTERM)
		except os.error:
			pass
		self.terminate()

	def writeString(self, s):

		"""Convert ascii string to IRAF form and write to IRAF process"""

		self.write(Asc2IrafString(s))

	def readString(self):

		"""Read IRAF string from process and convert to ascii string"""

		return Iraf2AscString(self.read())

	def write(self, data):

		"""write binary data to IRAF process in blocks of <= 4096 bytes"""

		i = 0
		block = 4096
		while i<len(data):
			# Write:
			#  IRAF magic number
			#  number of following bytes
			#  data
			dsection = data[i:i+block]
			self.process.write(IPC_PREFIX +
							struct.pack('=h',len(dsection)) +
							dsection)
			i = i + block

	def read(self):

		"""Read binary data from IRAF pipe"""

		# read pipe header first
		header = self.process.read(4)
		if (header[0:2] != IPC_PREFIX):
			raise IrafProcessError("Not a legal IRAF pipe record")
		ntemp = struct.unpack('=h',header[2:])
		nbytes = ntemp[0]
		# read the rest
		data = self.process.read(nbytes)
		return data

	def slave(self):

		"""Talk to the IRAF process in slave mode.
		Raises an IrafProcessError if an error occurs."""

		self.msg = ''
		self.xferline = ''
		# try to speed up loop a bit
		re_match = _re_msg.match
		xfer = self.xfer
		xmit = self.xmit
		par_get = self.par_get
		par_set = self.par_set
		executeClCommand = self.executeClCommand
		while 1:

			# each read may return multiple lines; only
			# read new data when old has been used up

			if not self.msg: self.msg = self.readString()

			msg = self.msg
			msg5 = msg[:5]

			if msg5 == 'xfer(':
				xfer()
			elif msg5 == 'xmit(':
				xmit()
			elif msg[:4] == 'bye\n':
				return
			elif msg5 in ['error','ERROR']:
				raise IrafProcessError("IRAF task terminated abnormally\n"+msg)
			else:
				# pattern match to see what this message is
				mcmd = re_match(msg)
				if mcmd is None:
					# Could be any legal CL command.
					executeClCommand()
				elif mcmd.group('par_get'):
					par_get(mcmd)
				elif mcmd.group('par_set'):
					par_set(mcmd)
				else:
					# should never get here
					raise RuntimeError("Program bug: uninterpreted message `%s'"
							% (msg,))

	def par_get(self, mcmd):
		# parameter get request
		paramname = mcmd.group('gname')
		# list parameters can generate EOF exception
		try:
			pmsg = self.task.getParam(paramname) + '\n'
		except EOFError:
			pmsg = 'EOF\n'
		self.writeString(pmsg)
		self.msg = self.msg[mcmd.end():]

	def par_set(self, mcmd):
		# set value of parameter
		group = mcmd.group
		paramname = group('sname')
		newvalue = group('svalue')
		self.msg = self.msg[mcmd.end():]
		try:
			self.task.setParam(paramname,newvalue)
		except ValueError, e:
			# on ValueError, just print warning and then force set
			if iraf.Verbose>0:
				self.stderr.write('Warning: %s\n' % (e,))
				self.stderr.flush()
			self.task.setParam(paramname,newvalue,check=0)

	def xmit(self):

		"""Handle xmit data transmissions"""

		global stdgraph

		chan, nbytes = self.chanbytes()

		checkForEscapeSeq = (chan == 4 and (nbytes==6 or nbytes==5))
		xdata = self.read()
		if len(xdata) != 2*nbytes:
			raise IrafProcessError(
				"Error, wrong number of bytes read\n" +
				("(got %d, expected %d, chan %d)" %
					(len(xdata), 2*nbytes, chan)))
		if chan == 4:
			txdata = Iraf2AscString(xdata)
			if checkForEscapeSeq:
				if ((txdata[0:5] == "\033=rDw") or
					(txdata[0:5] == "\033+rAw") or
					(txdata[0:5] == "\033-rAw")):
					# ignore IRAF io escape sequences for now
					return
			self.stdout.write(txdata)
			self.stdout.flush()
		elif chan == 5:
			sys.stdout.flush()
			self.stderr.write(Iraf2AscString(xdata))
			self.stderr.flush()
		elif chan == 6:
			# need to handle cases where WS not open yet
			if not stdgraph:
				stdgraph = gkiopengl.GkiOpenGlKernel()
			stdgraph.append(Numeric.fromstring(xdata,'s'))
		elif chan == 7:
			self.stdout.write("data for STDIMAGE\n")
			self.stdout.flush()
		elif chan == 8:
			self.stdout.write("data for STDPLOT\n")
			self.stdout.flush()
		elif chan == 9:
			sdata = Numeric.fromstring(xdata,'s')
			if irafutils.isBigEndian():
				# Actually, the channel destination is sent
				# by the iraf process as a 4 byte int, the following
				# code basically chooses the right two bytes to
				# find it in.
				forChan = sdata[1]
			else:
				forChan = sdata[0]
			if forChan == 6:
				# STDPLOT control
				# first see if OPENWS to get device, otherwise
				# pass through to current kernel, use braindead
				# interpretation to look for openws
				if stdgraph is None:
					if wutil.hasGraphics:
						stdgraph = gkiopengl.GkiOpenGlKernel()
					else:
						# install the "do nothing" kernel
						stdgraph = gki.GkiNull()
				if (sdata[2] == -1) and (sdata[3] == 1):
					length = sdata[4]
					device = sdata[5:length+2].astype('b').tostring()
					# but of course, for the time being (until
					# we manage another graphics kernel) we ignore
					# device!

				# Pass it to the kernel to deal with
				# Only returns a value for getwcs
				wcs = stdgraph.control(sdata[2:])
				if wcs:
					# Write directly to stdin of subprocess;
					# strangely enough, it doesn't use the
					# STDGRAPH I/O channel.
					self.write(wcs)
					stdgraph.clearReturnData()
				if stdgraph.stdout:
					self.stdout = stdgraph.stdout
				else:
					self.stdout = self.default_stdout
				if stdgraph.stderr:
					self.stderr = stdgraph.stderr
				else:
					self.stderr = self.default_stderr
			else:
				self.stdout.write("GRAPHICS control data for channel %d\n" % (forChan,))
				self.stdout.flush()
		else:
			self.stdout.write("data for channel %d\n" % (chan,))
			self.stdout.flush()

	def xfer(self):

		"""Handle xfer data requests"""

		chan, nbytes = self.chanbytes()
		nchars = nbytes/2
		if chan == 3:

			# Read data from stdin unless xferline already has
			# some untransmitted data from a previous read

			line = self.xferline
			if not line:
				if self.isatty:
					# tty input, read a single line
					line = self.stdin.readline()
				else:
					# file input, read a big chunk of data

					# NOTE: Here we are reading ahead in the stdin stream,
					# which works fine with a single IRAF task.  This approach
					# could conceivably cause problems if some program expects
					# to continue reading from this stream starting at the
					# first line not read by the IRAF task.  That sounds
					# very unlikely to be a good design and will not work
					# as a result of this approach.  Sending the data in
					# large chunks is *much* faster than sending many
					# small messages (due to the overhead of handshaking
					# between the CL task and this main process.)  That's
					# why it is done this way.

					line = self.stdin.read(nchars)
				self.xferline = line

			# Send two messages, the first with the number of characters
			# in the line and the second with the line itself.
			# For very long lines, may need multiple messages.  Task
			# will keep sending xfer requests until it gets the
			# newline.

			if len(line)<=nchars:
				# short line
				self.writeString(str(len(line)))
				self.writeString(line)
				self.xferline = ''
			else:
				# long line
				self.writeString(str(nchars))
				self.writeString(line[:nchars])
				self.xferline = line[nchars:]
		else:
			raise IrafProcessError("xfer request for unknown channel %d" % chan)

	def chanbytes(self):
		"""Parse xmit(chan,nbytes) and return integer tuple
		
		Assumes first 5 characters have already been checked
		"""
		msg = self.msg
		try:
			i = string.find(msg,",",5)
			if i<0 or msg[-2:] != ")\n": raise ValueError
			chan = int(msg[5:i])
			nbytes = int(msg[i+1:-2])
			self.msg = ''
		except ValueError:
			raise IrafProcessError("Illegal message format `%s'" % self.msg)
		return chan, nbytes

	def executeClCommand(self):

		"""Execute an arbitrary CL command"""

		# pattern match to handle special commands that write to task
		mcmd = _re_clcmd.match(self.msg)
		if mcmd is None:
			# general command
			i = string.find(self.msg,"\n")
			if i>=0:
				cmd = self.msg[:i+1]
				self.msg = self.msg[i+1:]
			else:
				cmd = self.msg
				self.msg = ""
			iraf.clExecute(cmd)
		elif mcmd.group('curpack'):
			# current package request
			self.writeString(iraf.curpack() + '\n')
			self.msg = self.msg[mcmd.end():]
		elif mcmd.group('sysescape'):
			# OS escape
			tmsg = mcmd.group('sys_cmd')
			# use my version of system command so redirection works
			sysstatus = iraf.clOscmd(tmsg, Stdin=self.stdin,
				Stdout=self.stdout, Stderr=self.stderr)
			self.writeString(str(sysstatus)+"\n")
			self.msg = self.msg[mcmd.end():]
			# self.stdout.write(self.msg + "\n")
		else:
			# should never get here
			raise RuntimeError(
					"Program bug: uninterpreted message `%s'"
					% (self.msg,))

# IRAF string conversions using Numeric module

def Asc2IrafString(ascii_string):
	"""translate ascii to IRAF 16-bit string format"""
	inarr = Numeric.fromstring(ascii_string, Numeric.Int8)
	return inarr.astype(Numeric.Int16).tostring()

def Iraf2AscString(iraf_string):
	"""translate 16-bit IRAF characters to ascii"""
	inarr = Numeric.fromstring(iraf_string, Numeric.Int16)
	return inarr.astype(Numeric.Int8).tostring()

