"""pycmdline.py -- simply command line interface for Pyraf

Eventually will have these functions:

- Command directives:
	.logfile [filename [append]]
	.debug
	.exit
- Shell escapes (!cmd, !!)
- Normal Python mode execution
- CL command-mode execution

Uses standard code module plus some ideas from cmd.py module
(and of course Perry's Monty design.)

R. White, 1999 December 12
"""

#XXX additional ideas:
#XXX add command-line completion?

import string, re, os, sys, code, types, keyword
import minmatch
import pyraf, iraf

class CmdConsole(code.InteractiveConsole):
	"""Base class for command console.

	Similar to InteractiveConsole, but provides local prompt control and
	hook for simple non-Python command processing.
	"""

	def __init__(self, locals=None, filename="<console>",
			cmddict=None, prompt1=">>> ", prompt2="... ",
			cmdchars=("a-zA-Z.","0-9_")):
		code.InteractiveConsole.__init__(self, locals=locals, filename=filename)
		self.ps1 = prompt1
		self.ps2 = prompt2
		if cmddict==None: cmddict={}
		self.cmddict = cmddict
		# cmdchars gives character set for first character, following
		# characters in the command name
		# create pattern that puts command in group 'cmd' and matches
		# optional leading and trailing whitespace
		self.recmd = re.compile( "[ \t]*(?P<cmd>" +
			"[" + cmdchars[0] + "][" + cmdchars[0] + cmdchars[1] + "]*" +
			")[ \t]*")

	def interact(self, banner=None):
		"""Emulate the interactive Python console, with extra commands."""
		if banner is None:
			self.write("Python %s on %s\n%s\n(%s)\n" %
						(sys.version, sys.platform, sys.copyright,
						self.__class__.__name__))
		else:
			self.write("%s\n" % str(banner))
		more = 0
		while 1:
			try:
				if more:
					prompt = self.ps2
				else:
					prompt = self.ps1
				try:
					line = self.raw_input(prompt)
				except EOFError:
					self.write("\n")
					break
				else:
					# note that this forbids combination of python & CL
					# code -- e.g. a for loop that runs CL tasks.
					if not more:
						line = self.cmd(line)
					if line or more: more = self.push(line)
			except KeyboardInterrupt:
				self.write("\nKeyboardInterrupt\n")
				self.resetbuffer()
				more = 0

	def cmd(self, line):
		"""Check for and execute commands from dictionary."""
		mo = self.recmd.match(line)
		if mo is None:
			i = 0
			cmd = ''
			method_name = None
		else:
			cmd = mo.group('cmd')
			i = mo.end()
			# look up command in dictionary
			try:
				method_name = self.cmddict[cmd]
			except KeyError:
				method_name = None
		if method_name is None:
			# no method, but have a look at it anyway
			return self.default(cmd,line,i)
		else:
			# if in cmddict, there must be a method by this name
			f = getattr(self, method_name)
			return apply(f, (line, i))

	def default(self, cmd, line, i):
		"""Hook to handle other commands (this version does nothing)"""
		return line

# put the executive commands in a minimum match dictionary

_cmdDict = minmatch.MinMatchDict({
				'.exit': 'do_exit',
				'.logfile': 'do_logfile',
				'.debug': 'do_debug',
				})

# short CL commands to allow
# there are others that I could add, but are they really necessary?
# bc, cv, dq, fc, nm, od, rc, rv, sh, su, w

_shortCmdDict = {
	'cd': 1,
	'cl': 1,
	'cp': 1,
	'df': 1,
	'du': 1,
	'ls': 1,
	'mv': 1,
	'ps': 1,
	'tv': 1,
	'vi': 1,
	'wc': 1,
	'xc': 1,
	}

class PyCmdLine(CmdConsole):

	"""Simple Python interpreter with executive commands"""

	def __init__(self, locals=None, logfile=None, debug=0):
		CmdConsole.__init__(self, locals=locals,
			cmddict=_cmdDict, prompt1="--> ", prompt2="... ")
		self.debug = debug
		self.subshell = "/bin/sh"
		self.logfile = None
		if logfile is not None:
			if hasattr(logfile,'write'):
				self.logfile = logfile
			elif type(logfile) is types.StringType:
				self.do_logfile(logfile, 0)
			else:
				print 'logfile ignored -- not string or filehandle'

	def runsource(self, source, filename="<input>", symbol="single"):
		"""Compile and run some source in the interpreter.

		Modified from code.py to include logging."""
		try:
			pcode = code.compile_command(source, filename, symbol)
		except (OverflowError, SyntaxError):
			# Case 1
			self.showsyntaxerror(filename)
			return 0

		if pcode is None:
			# Case 2
			return 1

		# Case 3
		self.runcode(pcode)
		if self.logfile:
			self.logfile.write(source)
			if source[-1:] != '\n': self.logfile.write('\n')
			self.logfile.flush()
		return 0

	def do_exit(self, line, i):
		if self.debug: print 'do_exit:',line
		raise SystemExit

	def do_logfile(self, line, i):
		if self.debug: print 'do_logfile:',line
		args = string.split(line[i:])
		if len(args) == 0:	# turn off logging (if on)
			if self.logfile:
				self.logfile.close()
				self.logfile = None
			else:
				print "No log file currently open"
		else:
			filename = args[0]
			oflag = 'w'
			if len(args) > 1:
				if string.strip(args[1]) == 'append':
					oflag = 'a'
				else:
					print 'Ignoring unknown options', args[1:]
			try:
				oldlogfile = self.logfile
				self.logfile = open(filename,oflag)
				if oldlogfile: oldlogfile.close()
			except IOError, e:
				print "error opening logfile", filename
				print str(e)
		return ""

	def do_debug(self, line, i):
		if self.debug: print 'do_debug:', line
		self.debug = 1
		if line[i:] != "":
			try:
				self.debug = int(line[i:])
			except ValueError, e:
				if self.debug: print str(e)
				pass
		return ""

	def do_help(self):
		print 'Executive commands:  .exit    .logfile [filename [append]]'

	def default(self, cmd, line, i):
		"""Check for IRAF task calls and use CL emulation mode if needed

		cmd = alpha-numeric string from beginning of line
		line = full line (including cmd, preceding blanks, etc.)
		i = index in line of first non-blank character following cmd
		"""
		if self.debug: print 'default: %s - %s' % (cmd,line[i:])
		if len(cmd)==0:
			# leading '?' or '!' will be handled by CL code
			if line[i:i+1] not in ['?', '!']:
				return line
			elif line[i:i+2] == '!!':
				os.system(self.subshell)
				return ''
		elif (len(cmd)<3 and not _shortCmdDict.has_key(cmd)) or \
				keyword.iskeyword(cmd):
			# don't mess with Python keywords
			# require at least 3 characters in keywords to reduce chance
			# of spurious matches (except for a few special cases:
			# cd, cl, tv, etc.)
			return line
		elif line[i:i+1] in [ '=', ',', '[']:
			# don't even try if it doesn't look like a procedure call
			return line
		else:
			# see if cmd is an IRAF task or procedure name
			try:
				t = getattr(iraf,cmd)
				# OK, we found it in the iraf module
				# If it could be a Python function call, check to see
				# if the function exists in the local namespace
				if line[i:i+1] == '(':
					ff = string.split(cmd,'.')
					if self.locals.has_key(ff[0]): return line
					# Not a local function, so user presumably intends to
					# call IRAF task.  Force Python mode but add the 'iraf.'
					# string to the task name for convenience.
					j = string.find(line,cmd)
					return line[:j] + 'iraf.' + line[j:]
			except AttributeError, e:
				return line

		# OK, it looks like CL code
		if self.debug: print 'CL:',line
		try:
			code = iraf.clExecute(line, locals=self.locals, mode='single')
			if self.logfile is not None:
				# log CL code as comment
				cllines = string.split(line,'\n')
				for oneline in cllines:
					self.logfile.write('# %s\n' % oneline)
				self.logfile.write(code)
				self.logfile.flush()
			if line == 'help':
				# print extra help on executive commands
				self.do_help()
		except:
			self.showtraceback()
		return ''

	def start(self, banner="Python/CL command line wrapper"):
		self.interact(banner=banner)

