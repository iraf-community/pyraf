"""
IRAF GKI interpreter -- abstract implementation

The main classes here are GkiKernel and GkiController.

GkiKernel is the base class for graphics kernel implementations.  Methods:

	control() append()
		Called by irafexecute to plot IRAF GKI metacode.
	pushStdio() popStdio() getStdin/out/err()
 		Hooks to allow text I/O to special graphics devices, e.g. the
		status line.
	flush()
		Flush graphics.  May print or write a file for hardcopy devices.
	clearReturnData()
		Empty out return data buffer.
	gcur()
		Activate interactive graphics and return key pressed, position, etc.
	redrawOriginal()
		Redraw graphics without any annotations, overlays, etc.
	undoN()
		Allows annotations etc. to be removed. 

Classes that implement a kernel provide methods named gki_* and control_*
which are called by the translate and control methods using dispatch
tables (functionTable and controlFunctionTable).  The complete lists
of methods are in opcode2name and control2name.  Python introspection
is used to determine which methods are implemented; it is OK for
unused methods to be omitted.

GkiProxy is a GkiKernel proxy class that implements the GkiKernel
interface and allows switching between GkiKernel objects (effectively
allowing the kernel type to change.)

GkiController is a GkiProxy that allows switching between different
graphics kernels as directed by commands embedded in the metacode stream.

$Id$
"""

import Numeric
from types import *
import os, sys, string, wutil, graphcap, iraf

BOI = -1  # beginning of instruction sentinel
NOP = 0	  # no op value
GKI_MAX = 32767
GKI_MAX_FLOAT = Numeric.array(GKI_MAX,Numeric.Float32)
GKI_MAX_OP_CODE = 27
GKI_FLOAT_FACTOR = 100.
MAX_ERROR_COUNT = 7

# gki opcode constants

GKI_EOF = 0
GKI_OPENWS = 1
GKI_CLOSEWS = 2
GKI_REACTIVATEWS = 3
GKI_DEACTIVATEWS = 4
GKI_MFTITLE = 5
GKI_CLEARWS = 6
GKI_CANCEL = 7
GKI_FLUSH = 8
GKI_POLYLINE = 9
GKI_POLYMARKER = 10
GKI_TEXT = 11
GKI_FILLAREA = 12
GKI_PUTCELLARRAY = 13
GKI_SETCURSOR = 14
GKI_PLSET = 15
GKI_PMSET = 16
GKI_TXSET = 17
GKI_FASET = 18
GKI_GETCURSOR = 19
GKI_GETCELLARRAY = 20
GKI_ESCAPE = 25
GKI_SETWCS = 26
GKI_GETWCS = 27

GKI_ILLEGAL_LIST = (21,22,23,24)

# Names of methods in GkiKernel that handle the various opcodes
# This also can be useful for debug prints of opcode values.

opcode2name = {
	0: 'gki_eof',
	1: 'gki_openws',
	2: 'gki_closews',
	3: 'gki_reactivatews',
	4: 'gki_deactivatews',
	5: 'gki_mftitle',
	6: 'gki_clearws',
	7: 'gki_cancel',
	8: 'gki_flush',
	9: 'gki_polyline',
	10: 'gki_polymarker',
	11: 'gki_text',
	12: 'gki_fillarea',
	13: 'gki_putcellarray',
	14: 'gki_setcursor',
	15: 'gki_plset',
	16: 'gki_pmset',
	17: 'gki_txset',
	18: 'gki_faset',
	19: 'gki_getcursor',
	20: 'gki_getcellarray',
	21: 'gki_unknown',
	22: 'gki_unknown',
	23: 'gki_unknown',
	24: 'gki_unknown',
	25: 'gki_escape',
	26: 'gki_setwcs',
	27: 'gki_getwcs',
	}

# control channel opcodes

control2name = {
	1: 'control_openws',
	2: 'control_closews',
	3: 'control_reactivatews',
	4: 'control_deactivatews',
	6: 'control_clearws',
	26: 'control_setwcs',
	27: 'control_getwcs',
	}

class EditHistory:
	"""Keeps track of where undoable appends are made so they can be
	removed from the buffer on request. All it needs to know is
	how much as been added to the metacode stream for each edit.
	Since the process may add more gki, we distinguish specific edits
	with a marker, and those are used when undoing."""

	def __init__(self):
		self.editinfo = []

	def add(self, size, undomarker=0):
		self.editinfo.append((undomarker,size))

	def NEdits(self):
		count = 0
		for undomarker,size in self.editinfo:
			if undomarker:
				count = count+1
		return count

	def popLastSize(self):
		tsize = 0
		while len(self.editinfo) > 0:
			marker, size = self.pop()
			tsize = tsize + size
			if marker: break
		return tsize

class GkiBuffer:

	"""implement a buffer for gki which allocates memory in blocks so that 
	a new memory allocation is not needed everytime metacode is appended"""

	INCREMENT = 50000

	def __init__(self, metacode=None):

		if metacode:
			self.editHistory = EditHistory()
			self.undoable = 0
			self.buffer = metacode
			self.bufferSize = len(metacode)
			self.bufferEnd = len(metacode)
			# nextTranslate is pointer to next element in buffer to be
			# translated.  It is needed because we may get truncated
			# messages, leaving some metacode to be prepended to next
			# message.
			self.nextTranslate = 0
		else:
			self.init()

	def init(self):
		self.buffer = Numeric.zeros(0, Numeric.Int16)
		self.bufferSize = 0
		self.bufferEnd = 0
		self.editHistory = EditHistory()
		self.undoable = 0
		self.nextTranslate = 0

	def reset(self):

		# discard everything up to nextTranslate pointer

		newEnd = self.bufferEnd - self.nextTranslate
		if newEnd > 0:
			self.buffer[0:newEnd] = self.buffer[self.nextTranslate:self.bufferEnd]
			self.bufferEnd = newEnd
		else:
			# complete reset so buffer can shrink sometimes
			self.init()
		self.nextTranslate = 0

	def append(self, metacode, isUndoable=0):

		if isUndoable:
			self.undoable = 1
		if self.bufferSize < (self.bufferEnd + len(metacode)):
			# increment buffer size and copy into new array
			diff = self.bufferEnd + len(metacode) - self.bufferSize
			nblocks = diff/self.INCREMENT + 1
			self.bufferSize = self.bufferSize + nblocks * self.INCREMENT
			newbuffer = Numeric.zeros(self.bufferSize, Numeric.Int16)
			if self.bufferEnd > 0:
				newbuffer[0:self.bufferEnd] = self.buffer[0:self.bufferEnd]
			self.buffer = newbuffer
		self.buffer[self.bufferEnd:self.bufferEnd+len(metacode)] = metacode
		self.bufferEnd = self.bufferEnd + len(metacode)
		if self.undoable:
			self.editHistory.add(len(metacode), isUndoable)

	def undoN(self, nUndo=1):

		for i in xrange(nUndo):
			size = self.editHistory.popLastSize()
			self.bufferEnd = self.bufferEnd - size
			if size == 0: break
		if self.bufferEnd <= 0:
			self.init()
		# reset translation pointer to beginning so plot gets redone
		# entirely
		self.nextTranslate = 0

	def get(self):
		"""Return buffer contents (as Numeric array, even if empty)"""
		return self.buffer[0:self.bufferEnd]

	def getNextCode(self):
		"""Read next opcode and argument from buffer, returning a tuple
		with (opcode, arg).  Skips no-op codes and illegal codes.
		Returns (None,None) on end of buffer or when opcode is truncated."""
		ip = self.nextTranslate
		lenMC = self.bufferEnd
		buffer = self.buffer
		while ip < lenMC:
			if buffer[ip] == NOP:
				ip = ip+1
			elif buffer[ip] != BOI:
				print "WARNING: missynched graphics data stream"
				# find next possible beginning of instruction
				ip = ip + 1
				while ip < lenMC:
					if buffer[ip] == BOI: break
					ip = ip + 1
				else:
					# Unable to resync
					print "WARNING: unable to resynchronize in graphics data stream"
					break
			else:
				if ip+2 >= lenMC: break
				opcode = buffer[ip+1]
				arglen = buffer[ip+2]
				if (ip+arglen) > lenMC: break
				arg = buffer[ip+3:ip+arglen]
				ip = ip + arglen
				if ((opcode < 0) or 
					(opcode > GKI_MAX_OP_CODE) or
					(opcode in GKI_ILLEGAL_LIST)):
					print "WARNING: Illegal graphics opcode = ",opcode
				else:
					# normal return
					self.nextTranslate = ip
					return (opcode, arg)
		# end-of-buffer return
		self.nextTranslate = ip
		return (None, None)

	def __len__(self):
		return self.bufferEnd

	def __getitem__(self,i):
		if i >= self.bufferEnd:
			raise IndexError("buffer index out of range")
		return self.buffer[i]

	def __getslice__(self,i,j):
		if j > self.bufferEnd: j = self.bufferEnd
		return self.buffer[i:j]

class GkiReturnBuffer:

	"""A fifo buffer used to queue up metacode to be returned to
	the IRAF subprocess"""

	# Only needed for getcursor and getcellarray, neither of which are
	# currently implemented.
	def __init__(self):

		self.fifo = []

	def reset(self):

		self.fifo = []

	def put(self, metacode):

		self.fifo[:0] = metacode

	def get(self):

		if len(self.fifo):
			metacode = self.fifo.pop()
		else:
			raise Exception("Attempted read on empty gki input buffer")


class GkiKernel:

	"""Abstract class intended to be subclassed by implementations of GKI
	kernels. This is to provide a standard interface to irafexecute"""

	def __init__(self):

		self.createFunctionTables()
		self.returnData = None
		self.errorMessageCount = 0
		self.stdin = None
		self.stdout = None
		self.stderr = None
		self._stdioStack = []
		self.gkibuffer = GkiBuffer() # no harm in allocating, doesn't
		                             # actually allocate space unless
									 # appended to.

	def createFunctionTables(self):

		"""Use Python introspection to create function tables"""

		self.functionTable =  [None]*(GKI_MAX_OP_CODE+1)
		self.controlFunctionTable =  [None]*(GKI_MAX_OP_CODE+1)

		# to protect against typos, make list of all gki_ & control_ methods
		gkilist, gkidict, classlist = [], {}, [self.__class__]
		for c in classlist:
			for b in c.__bases__:
				classlist.append(b)
			for name in dir(c):
				if (name[:4] == "gki_" or name[:8] == "control_") and \
				  not gkidict.has_key(name):
					gkilist.append(name)
					gkidict[name] = 0
		# now loop over all methods that might be present
		for opcode, name in opcode2name.items():
			if hasattr(self, name):
				self.functionTable[opcode] = getattr(self, name)
				gkidict[name] = 1
		# do same for control methods
		for opcode, name in control2name.items():
			if hasattr(self, name):
				self.controlFunctionTable[opcode] = getattr(self, name)
				gkidict[name] = 1
		# did we use all the gkidict methods?
		badlist = []
		for name, value in gkidict.items():
			if not value:
				badlist.append(name)
		if badlist:
			raise SyntaxError("Bug: error in definition of class %s\n"
				"Special method name is incorrect: %s" %
				(self.__class__.__name__, string.join(badlist," ")))

	def control(self, gkiMetacode):
		gkiTranslate(gkiMetacode, self.controlFunctionTable)
		return self.returnData

	def append(self, gkiMetacode, isUndoable=0):

		# append metacode to the buffer
		buffer = self.getBuffer()
   		buffer.append(gkiMetacode, isUndoable)
		# translate and display the metacode
		self.translate(buffer)

	def translate(self, gkiMetacode):
		gkiTranslate(gkiMetacode, self.functionTable)

	def errorMessage(self, text):

		if self.errorMessageCount < MAX_ERROR_COUNT:
			print text
			self.errorMessageCount = self.errorMessageCount + 1

	def getBuffer(self):

		# Normally, the buffer will be an attribute of the kernel, but
		# in some cases some kernels need more than one instance (interactive
		# graphics for example). In those cases, this method may be
		# overridden and the buffer will actually reside elsewhere

		return self.gkibuffer

	def flush(self): pass

	def clear(self):
		self.gkibuffer.reset()

	def undoN(self, nUndo=1):

		# Remove the last nUndo interactive appends to the metacode buffer
		buffer = self.getBuffer()
		buffer.undoN(nUndo)
		self.translate(buffer)

	def redrawOriginal(self):

		buffer = self.getBuffer()
		nUndo =  buffer.editHistory.NEdits()
		self.undoN(nUndo)

	def clearReturnData(self):

		# intended to be called after return data is used by the client
		self.returnData = None

	def gcur(self):
		# a default gcur routine to handle all the kernels that aren't
		# interactive
		raise iraf.IrafError("The specified graphics device is not interactive")

	# some special routines for getting and setting stdin/out/err attributes

	def pushStdio(self, stdin=None, stdout=None, stderr=None):
		"""Push current stdio settings onto stack at set new values"""
		self._stdioStack.append((self.stdin, self.stdout, self.stderr))
		self.stdin = stdin
		self.stdout = stdout
		self.stderr = stderr

	def popStdio(self):
		"""Restore stdio settings from stack"""
		if self._stdioStack:
			self.stdin, self.stdout, self.stderr = self._stdioStack.pop()
		else:
			self.stdin, self.stdout, self.stderr = None, None, None

	def getStdin(self, default=None):
		# if default is a file, don't redirect it
		# otherwise if graphics is active, redirect to status line
		try:
			if (not self.stdin) or \
			  (default and not default.isatty()):
				return default
		except AttributeError:
			pass
		return self.stdin

	def getStdout(self, default=None):
		# if default is a file, don't redirect it
		# otherwise if graphics is active, redirect to status line
		try:
			if (not self.stdout) or \
			  (default and not default.isatty()):
				return default
		except AttributeError:
			# OK if isatty is missing
			pass
		return self.stdout

	def getStderr(self, default=None):
		# stderr always redirected in graphics mode because IRAF
		# uses it for GUI code (go figure)
		return self.stderr or default


#*****************************************************************

standardWarning = """
The graphics kernel for IRAF tasks has just recieved a metacode
instruction it never expected to see. Please inform the STSDAS
group of this occurance"""

standardNotImplemented = """
You have tried to run an IRAF task which requires graphics kernel
facility not implemented in the Python graphics kernel for IRAF tasks"""

#**********************************************************************

def gkiTranslate(metacode, functionTable):

	"""General Function that can be used for decoding and interpreting
	the GKI metacode stream. FunctionTable is a 28 element list containing
	the functions to invoke for each opcode encountered. This table should
	be different for each kernel that uses this function and the control
	method.
	This may be called with either a gkiBuffer or a simple numerical
	array.  If a gkiBuffer, it translates only the previously untranslated
	part of the gkiBuffer and updates the nextTranslate pointer."""

	if isinstance(metacode, GkiBuffer):
		gkiBuffer = metacode
	else:
		gkiBuffer = GkiBuffer(metacode)

	opcode, arg = gkiBuffer.getNextCode()
	while opcode != None:
		f = functionTable[opcode]
		if f is not None:
			apply(f,(arg,))
		opcode, arg = gkiBuffer.getNextCode()

class GkiProxy(GkiKernel):

	"""Base class for kernel proxy

	stdgraph is an instance of a GkiKernel to which calls are deferred.
	openKernel() method must be supplied to create a kernel and assign
	it to stdgraph.
	"""

	def __init__(self):

		GkiKernel.__init__(self)
		self.stdgraph = None

	def __del__(self):
		self.flush()

	def openKernel(self):
		raise Exception("bug: do not use GkiProxy class directly")

	# methods simply defer to stdgraph
	# some create kernel and some simply return if no kernel is defined

	def errorMessage(self, text):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.errorMessage(text)

	def getBuffer(self):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.getBuffer()

	def undoN(self, nUndo=1):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.undoN(nUndo)

	def redrawOriginal(self):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.redrawOriginal()

	def translate(self, gkiMetacode):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.translate(gkiMetacode)

	def clearReturnData(self):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.clearReturnData()

	def gcur(self):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.gcur()

	# keep both local and stdgraph stdin/out/err up-to-date

	def pushStdio(self, stdin=None, stdout=None, stderr=None):
		"""Push current stdio settings onto stack at set new values"""
		if self.stdgraph:
			self.stdgraph.pushStdio(stdin,stdout,stderr)
		#XXX still need some work here?
		self._stdioStack.append((self.stdin, self.stdout, self.stderr))
		self.stdin = stdin
		self.stdout = stdout
		self.stderr = stderr

	def popStdio(self):
		"""Restore stdio settings from stack"""
		#XXX still need some work here?
		if self.stdgraph:
			self.stdgraph.popStdio()
		if self._stdioStack:
			self.stdin, self.stdout, self.stderr = self._stdioStack.pop()
		else:
			self.stdin, self.stdout, self.stderr = None, None, None

	def getStdin(self, default=None):
		if self.stdgraph:
			return self.stdgraph.getStdin(default)
		else:
			return GkiKernel.getStdin(self, default)

	def getStdout(self, default=None):
		if self.stdgraph:
			return self.stdgraph.getStdout(default)
		else:
			return GkiKernel.getStdout(self, default)

	def getStderr(self, default=None):
		if self.stdgraph:
			return self.stdgraph.getStderr(default)
		else:
			return GkiKernel.getStderr(self, default)

	def append(self, arg, isUndoable=0):
		if self.stdgraph:
			self.stdgraph.append(arg,isUndoable)

	def control(self, gkiMetacode):
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.control(gkiMetacode)

	def flush(self):
		if self.stdgraph:
			self.stdgraph.flush()

	def clear(self):
		if self.stdgraph:
			self.stdgraph.clear()

class GkiController(GkiProxy):

	"""Proxy for the actual kernel being used

	This can gracefully handle changes in kernels which can appear
	in any open workstation instruction.  It also uses lazy
	instantiation of the real kernel (which can be expensive).  In
	one sense it is a factory class that will instantiate the
	necessary kernels as they are requested.

	Most external modules should access the gki functions through
	an instance of this class, gki.kernel.
	"""

	def __init__(self):

		GkiProxy.__init__(self)
		self.interactiveKernel = None
		self.lastDevName = None
		self.gcount = 0 # an activity counter
		self.lastFlushCount = 0

	def append(self, arg, isUndoable=0):

		self.gcount = self.gcount + 1     # used by self.flush()
		if self.gcount >= 30000000:
			self.gcount = 0
		if self.stdgraph:
			self.stdgraph.append(arg,isUndoable)

	def control(self, gkiMetacode):

		# some control functions get executed here because they can
		# change the kernel
		gkiTranslate(gkiMetacode, self.controlFunctionTable)
		# rest of control is handled by the kernel
		if not self.stdgraph: self.openKernel()
		return self.stdgraph.control(gkiMetacode)

	def flush(self):

		if self.stdgraph and isinstance(self.stdgraph, gkiiraf.GkiIrafKernel):
			if self.gcount != self.lastFlushCount:
				# this is to prevent flushes when no graphics activity
				# occurred since the last time a task finished.
				self.lastFlushCount = self.gcount
				self.stdgraph.flush()

	def openKernel(self, device=None):

		"""This is a generic open function that determines which kernel
		should become active based on the current value of stdgraph (this
		will be generalized to allow other means of selecting graphics
		kernels)"""
		if not device:
			device = self.getDevice()
		devices = getGraphcap()
		kernel = devices[device]['kf']
  		if kernel == 'cl':
			self.openInteractiveKernel()
		else:
			task = devices[device]['tn']
			self.stdgraph = gkiiraf.GkiIrafKernel(device, kernel, task)
			self.stdin = self.stdgraph.stdin
			self.stdout = self.stdgraph.stdout
			self.stderr = self.stdgraph.stderr

	def openInteractiveKernel(self):
		"""Used so that an existing opened interactive session persists"""

		if not self.interactiveKernel:
			if wutil.hasGraphics:
				self.interactiveKernel = gwm.getGraphicsWindowManager()
			else:
				self.interactiveKernel = GkiNull()
		self.stdgraph = self.interactiveKernel
		self.stdin = self.stdgraph.stdin
		self.stdout = self.stdgraph.stdout
		self.stderr = self.stdgraph.stderr

	def control_reactivatews(self,arg):
		if not self.stdgraph: self.openKernel()
		func = self.stdgraph.controlFunctionTable[GKI_REACTIVATEWS]
		if func is not None: func(arg) 

	def control_deactivatews(self,arg):
		if self.stdgraph:
			func = self.stdgraph.controlFunctionTable[GKI_DEACTIVATEWS]
			if func is not None: func(arg) 

	def control_closews(self,arg):
		if self.stdgraph:
			closews = self.stdgraph.controlFunctionTable[GKI_CLOSEWS]
			if closews is not None: closews(arg) 

	def control_openws(self, arg):

		mode = arg[0]
		device = string.strip(arg[2:].astype(Numeric.Int8).tostring())
		device = self.getDevice(device)
		if device != self.lastDevName:
			self.flush()
			self.openKernel(device)
			self.lastDevName = device
			# call the active kernel's openws function
			func = self.stdgraph.controlFunctionTable[GKI_OPENWS]
			if func is not None: func(arg) 

	def getDevice(self, device=None):
		"""Starting with stdgraph, drill until a device is found in
		the graphcap or isn't"""
		if not device:
			device = iraf.envget("stdgraph")
		devices = getGraphcap()
		# protect against circular definitions
		devstr = device
		tried = {devstr: None}
		while 1:
			if devices.has_key(devstr):
				device = devstr
				break
			else:
				pdevstr = devstr
				devstr = iraf.envget(pdevstr)
				if not devstr:
					raise iraf.IrafError(
						"No entry found for specified stdgraph device `%s'" %
						device)
				elif tried.has_key(devstr):
					# track back through circular definition
					s = [devstr]
					next = pdevstr
					while next and (next != devstr):
						s.append(next)
						next = tried[next]
					if next: s.append(next)
					s.reverse()
					raise iraf.IrafError(
					"Circular definition in graphcap for device\n%s"
						% (string.join(s,' -> '),))
				else:
					tried[devstr] = pdevstr
		return device

class GkiNull(GkiKernel):

	"""A version of the graphics kernel that does nothing except warn the
	user that it does nothing. Used when graphics display isn't possible"""

	def __init__(self):

		print "No graphics display available for this session " + \
			  "(X Window unavailable)"
		print "Graphics tasks that attempt to plot to an interactive " + \
			  "screen will fail"
		GkiKernel.__init__(self)
		self.name = 'Null'

	def control(self, gkiMetacode):
		gkiTranslate(gkiMetacode, self.controlFunctionTable)
		return self.returnData

	def control_openws(self, arg):
		raise iraf.IrafError("Unable to plot graphics to screen")

	def control_reactivatews(self, arg):
		raise iraf.IrafError("Attempt to access graphics when "
			"it isn't available")

	def control_getwcs(self, arg):
		raise iraf.IrafError("Attempt to access graphics when "
			"it isn't available")

	def translate(self, gkiMetacode):
		pass

# Dictionary of all graphcap files known so far

graphcapDict = {}

def getGraphcap(filename=None):
	"""Get graphcap file from filename (or cached version if possible)"""
	if filename is None:
		filename = iraf.osfn(iraf.envget('graphcap') or 'dev$graphcap')
	if not graphcapDict.has_key(filename):
		graphcapDict[filename] = graphcap.GraphCap(filename)
	return graphcapDict[filename]

def printPlot(window=None):

	"""Print contents of window (default active window) to stdplot
	
	window must be a GkiKernel object (with a gkibuffer attribute.)
	"""

	if window is None:
		window = gwm.getActiveGraphicsWindow()
		if window is None: return
	gkibuff = window.gkibuffer.get()
	if gkibuff:
		# write to a temporary file
		tmpfn = iraf.mktemp("snap") + ".gki"
		fout = open(tmpfn,'w')
		fout.write(gkibuff.tostring())
		fout.close()
		try:
			devices = getGraphcap()
			stdplot = iraf.envget('stdplot')
			if not stdplot:
				msg = 'No hardcopy device defined in stdplot'
			elif not devices.has_key(stdplot):
				msg = "Unknown hardcopy device stdplot=`%s'" % stdplot
			else:
				printtaskname = devices[stdplot]['tn']
				if printtaskname == "psikern" and not iraf.stsdas.isLoaded():
					iraf.stsdas(motd=0, _doprint=0)
				printtask = iraf.getTask(printtaskname)
				# Need to redirect input because running this task with
				# input from StatusLine does not work for some reason.
				# May need to do this for other IRAF tasks run while in
				# gcur mode (if there are more added in the future.)
				printtask(tmpfn,Stdin=sys.__stdin__,Stdout=sys.__stdout__)
				msg = "snap completed"
		finally:
			os.remove(tmpfn)
	stdout = kernel.getStdout(default=sys.stdout)
	stdout.write("%s\n" % msg)


#********************************

def ndc(intarr):
	return intarr/GKI_MAX_FLOAT

def ndcpairs(intarr):
	f = ndc(intarr)
	return f[0::2],f[1::2]


# import these last so everything in this module is defined

import gwm, gkiiraf

# This is the proxy for the current graphics kernel

kernel = GkiController()
