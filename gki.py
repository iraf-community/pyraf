"""
IRAF GKI interpreter -- abstract implementation
$Id$
"""

import Numeric
from types import *
import graphcap, iraf, wutil, string
import gkiopengl
#, gkiiraf

kernel = None # This will be set to an instance of gkiController when graphics
              # is first needed

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
GKI_DEACTIVATEWS =4
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

class EditHistory:
	"""keeps track of where undoable appends are made so they can be
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
		if len(self.editinfo) > 0:
			done = 0
			tsize = 0
			while not done and len(self.editinfo) > 0:
				marker, size = self.editinfo[-1]
				del self.editinfo[-1]
				tsize = tsize + size
				if marker:
					done = 1
			return tsize
		else:
			return 0

class GkiBuffer:

	"""implement a buffer for gki which allocates memory in blocks so that 
	a new memory allocation is not needed everytime metacode is appended"""

	INCREMENT = 50000

	def __init__(self, metacode=None):
	
		getwcs = None  # Used to indicate a getwcs instruction was encountered
		self.editHistory = EditHistory()
		self.undoable = 0
		if metacode:
			self.buffer = metacode
			self.bufferSize = len(metacode)
			self.bufferEnd = len(metacode)
			# nextTranslate is pointer to next element in buffer to be
			# translated.  It is needed because we may get truncated
			# messages, leaving some metacode to be prepended to next
			# message.
			self.nextTranslate = 0
		else:
			self.buffer = None
			self.bufferSize = 0
			self.bufferEnd = 0 
			self.nextTranslate = 0

	def reset(self):

		# discard everything up to nextTranslate pointer

		newEnd = self.bufferEnd - self.nextTranslate
		if newEnd > 0:
			self.buffer[0:newEnd] = self.buffer[self.nextTranslate:self.bufferEnd]
			self.bufferEnd = newEnd
		else:
			self.buffer = None
			self.bufferSize = 0
			self.bufferEnd = 0
			self.editHistory = EditHistory()
			self.undoable = 0
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
		# reset translation pointer to beginning so plot gets redone
		# entirely
		self.nextTranslate = 0

	def get(self):
	
		if self.buffer:
			return self.buffer[0:self.bufferEnd]
		else:
			return self.buffer

	def getNextCode(self):
		"""Read next opcode and argument from buffer, returning a tuple
		with (opcode, arg).  Skips no-op codes and illegal codes.
		Returns (None,None) on end of buffer or when opcode is truncated."""
		ip = self.nextTranslate
		lenMC = self.bufferEnd
		while ip < lenMC:
			if self.buffer[ip] == NOP:
				ip = ip+1
			elif self.buffer[ip] != BOI:
				print "WARNING: missynched graphics data stream"
				# find next possible beginning of instruction
				ip = ip + 1
				while ip < lenMC:
					if self.buffer[ip] == BOI: break
					ip = ip + 1
				else:
					# Unable to resync
					print "WARNING: unable to resynchronize in graphics data stream"
					break
			else:
				if ip+2 >= lenMC: break
				opcode = self.buffer[ip+1]
				arglen = self.buffer[ip+2]
				if (ip+arglen) > lenMC: break
				arg = self.buffer[ip+3:ip+arglen]
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
			metacode = self.fifo[-1]
			del self.fifo[-1]
		else:
			raise Exception("Attempted read on empty gki input buffer")


def _nullAction(arg):
	pass

class GkiKernel:

	"""Abstract class intended to be subclassed by implementations of GKI
	kernels. This is to provide a standard interface to irafexecute"""

	
	def __init__(self):
	
		self.functionTable = gkiFunctionTable
		self.returnData = None
		self.errorMessageCount = 0
		self._gkiAction = _nullAction
		self.gkibuffer = GkiBuffer() # no harm in allocating, doesn't
		                             # actually allocate space unless
									 # appended to.
	

	def errorMessage(self, text):

		if self.errorMessageCount < MAX_ERROR_COUNT:
			print text
			self.errorMessageCount = self.errorMessageCount + 1
	
	def control(self, gkiMetacode):

		# stub routine to be overridden in subclass. Purpose is to act
		# on the GKI control instructions destined for that particular
		# graphics kernel.
		pass

	def getBuffer(self):

		# Normally, the buffer will be an attribute of the kernel, but
		# in some cases some kernels need more than one instance (interactive
		# graphics for example). In those cases, this method will be
		# overridden and the buffer will actually reside elsewhere
		return self.gkibuffer

	def append(self, gkiMetacode, isUndoable=0):
	
		buffer = self.getBuffer()
   		buffer.append(gkiMetacode, isUndoable)
		# a hook for acting on the metacode, but is only a stub routine
		# that must be overridden in the subclass (or not, depending)
		self.translate(buffer, self.functionTable)

	def flush(self): pass

	def undoN(self, nUndo=1):

		# Remove the last nUndo interactive appends to the metacode buffer
		buffer = self.getBuffer()
		buffer.undoN(nUndo)
		self.translate(buffer, self.functionTable)

	def redrawOriginal(self):

		buffer = self.getBuffer()
		nUndo =  buffer.editHistory.NEdits()
		self.undoN(nUndo)

	def translate(self, gkiBuffer, functionTable):

		# stub routine to be overridden in subclass of GkiKernel
		pass

	def clearReturnData(self):

		# intended to be called after return data is used by the client
		self.returnData = None

	def gcur(self):
		# a default gcur routine to handle all the kernels that aren't
		# interactive
		raise iraf.IrafError("The specified graphics device is not interactive")
#*****************************************************************

standardWarning = """
The graphics kernel for IRAF tasks has just recieved a metacode
instruction it never expected to see. Please inform the STSDAS
group of this occurance"""

standardNotImplemented = """
You have tried to run an IRAF task which requires graphics kernel
facility not implemented in the Python graphics kernel for IRAF tasks"""

def gki_eof(applyfunc, arg): pass # ignored
def gki_openws(applyfunc, arg): pass	# handled in control channel
def gki_closews(applyfunc, arg): pass # handled in control channel
def gki_reactivatews(applyfunc, arg): pass # ignored
def gki_deactivatews(applyfunc, arg): pass # ignored
def gki_mftitle(applyfunc, arg): pass # ignored
def gki_clearws(applyfunc, arg): apply(applyfunc,(GKI_CLEARWS,(0,)))

def gki_cancel(applyfunc, arg): gki_clearws(arg)

def gki_flush(applyfunc, arg): apply(applyfunc,(GKI_FLUSH,(arg,)))

def gki_polyline(applyfunc, arg): apply(applyfunc,(GKI_POLYLINE,
														 (ndc(arg[1:]),)))

def gki_polymarker(applyfunc, arg):	apply(applyfunc, (GKI_POLYMARKER,
													  (ndc(arg[1:]),)))
		
def gki_text(applyfunc, arg):
	
#	print "GKI_TEXT:", arg[3:].tostring()
	x = ndc(arg[0])
	y = ndc(arg[1])
	text = arg[3:].astype(Numeric.Int8).tostring()
	apply(applyfunc,(GKI_TEXT, (x, y, text)))

def gki_fillarea(applyfunc, arg): 

	apply(applyfunc,(GKI_FILLAREA,(ndc(arg[1:]),)))

def gki_putcellarray(applyfunc, arg): 
	
	errorMessage(standardNotImplemented)
	
def gki_setcursor(applyfunc, arg):

	cursorNumber = arg[0]
	x = arg[1]/GKI_MAX
	y = arg[2]/GKI_MAX
	apply(applyfunc,(GKI_SETCURSOR, (cursorNumber, x, y)))
	
def gki_plset(applyfunc, arg):

	linetype = arg[0]
	linewidth = arg[1]/GKI_FLOAT_FACTOR
	color = arg[2]
	apply(applyfunc,(GKI_PLSET, (linetype, linewidth, color)))
	
def gki_pmset(applyfunc, arg):

	marktype = arg[0]
	marksize = arg[1]/GKI_MAX
	color = arg[2]
	apply(applyfunc,(GKI_PMSET, (marktype, marksize, color)))


def gki_txset(applyfunc, arg):

	charUp = float(arg[0])
	charSize = arg[1]/GKI_FLOAT_FACTOR
	charSpace = arg[2]/GKI_FLOAT_FACTOR
	textPath = arg[3]
	textHorizontalJust = arg[4]
	textVerticalJust = arg[5]
	textFont = arg[6]
	textQuality = arg[7]
	textColor = arg[8]
	apply(applyfunc,(GKI_TXSET, (charUp, charSize, charSpace, textPath,
		textHorizontalJust, textVerticalJust, textFont,
		textQuality, textColor)))

def gki_faset(applyfunc, arg):

	fillstyle = arg[0]
	color = arg[1]
	apply(applyfunc,(GKI_FASET,(fillstyle, color)))

def gki_getcursor(applyfunc, arg):

	print "GKI_GETCURSOR"
	raise standardNotImplemented
	 
def gki_getcellarray(applyfunc, arg):

	print "GKI_GETCELLARRAY"
	raise standardNotImplemented
	
def gki_unknown(applyfunc, arg): 
	
	errorMessage("GKI_UNKNOWN:\n"+standardWarning)
	
def gki_escape(applyfunc, arg): print "GKI_ESCAPE"
def gki_setwcs(applyfunc, arg): pass #print "GKI_SETWCS"
def gki_getwcs(applyfunc, arg): print "GKI_GETWCS"

# function table
gkiFunctionTable = [
	gki_eof,			# 0
	gki_openws,  
	gki_closews,
	gki_reactivatews,
	gki_deactivatews,
	gki_mftitle,	# 5
	gki_clearws,
	gki_cancel,
	gki_flush,
	gki_polyline,
	gki_polymarker,# 10
	gki_text,
	gki_fillarea,
	gki_putcellarray,
	gki_setcursor,
	gki_plset,		# 15
	gki_pmset,
	gki_txset,
	gki_faset,
	gki_getcursor, # also gki_cursorvalue,
	gki_getcellarray,#20  also	gki_cellarray,
	gki_unknown,
	gki_unknown,
	gki_unknown,
	gki_unknown,
	gki_escape,		# 25
	gki_setwcs,
	gki_getwcs]

#**********************************************************************		

def gkiTranslate(metacode, functionTable, applyfunc):

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
		apply(functionTable[opcode],(applyfunc,arg))
		opcode, arg = gkiBuffer.getNextCode()

class GkiController(GkiKernel):

	"""Indended to be used as a layer between the actual kernel being used
	and the pyraf. This is so that it can gracefully
	handle changes in kernels which can appear in any open workstation
	instruction. In one sense it is a factory class that will instantiate
	the necessary kernels as they are requested."""

	def __init__(self):

		GkiKernel.__init__(self)
		self.stdgraph = None
		self.interactiveKernel = None
		self.functionTable = []
		self.controlFunctionTable =  [self.noAction]*(GKI_MAX_OP_CODE+1)
		self.controlFunctionTable[GKI_OPENWS] = self.openWS
		self.devices = graphcap.GraphCap(iraf.osfn('dev$graphcap'))
		self.lastDevName = None
		self.gcount = 0 # an activity counter
		self.lastFlushCount = 0
		self.flushInProgress = 0

	def append(self, arg):

		self.gcount = self.gcount + 1     # used by self.flush()
		if self.gcount >= 30000000:
			self.gcount = 0
		if self.stdgraph:
			self.stdgraph.append(arg)
			
	def noAction(self, dummy, arg): pass

	def flush(self):

		if self.stdgraph and self.stdgraph.__class__.__name__ == "GkiIrafKernel":
			if self.gcount != self.lastFlushCount:
				# this is to prevent flushes when no graphics activity
				# occurred since the last time a task finished.
				self.lastFlushCount = self.gcount
				self.stdgraph.flush()

	def gcur(self):
		if not self.stdgraph:
			self.openKernel()
		return self.stdgraph.gcur()
	
	def openWS(self, dummy, arg):

		mode = arg[0]
		device = string.strip(arg[2:].astype(Numeric.Int8).tostring())
		device = self.getDevice(device)
		if device != self.lastDevName:
			self.openKernel(device)
			self.lastDevName = device
			# call the active kernel's openws function
			#self.stdgraph.controlFunctionTable[GKI_OPENWS](dummy, arg) 

	def getDevice(self, device=None):
		"""Starting with stdgraph, drill until a device is found in
		the graphcap or isn't"""
		devstr = iraf.envget("stdgraph")
		if (not device) or (not self.devices.has_key(device)):
			while 1:
				# no protection against circular definitions!
				if self.devices.has_key(devstr):
					device = devstr
					break
				else:
					devstr = iraf.envget(devstr)
					if not devstr:
						raise IrafError(
							"No entry found for specified stdgraph device")
		
		return device

	def openKernel(self, device=None):

		"""This is a generic open function that determines which kernel
		should become active based on the current value of stdgraph (this
		will be generalized to allow other means of selecting graphics
		kernels"""
		if not device:
			device = self.getDevice()
		kernel = self.devices[device]['kf']
  		if kernel == 'cl':
			self.openInteractiveKernel()
		else:
			task = self.devices[device]['tn']
			import gkiiraf
			self.stdgraph = gkiiraf.GkiIrafKernel(device, kernel, task)

	def openInteractiveKernel(self):
		"""Used so that an existing opened interactive session persists"""

		if not wutil.hasGraphics and not self.interactiveKernel:
			self.interactiveKernel = GkiNull()
		if self.interactiveKernel:
			self.stdgraph = self.interactiveKernel
		else:
			self.stdgraph = gkiopengl.GkiOpenGlKernel()
			self.interactiveKernel = self.stdgraph

	def control(self, gkiMetacode):

		gkiTranslate(gkiMetacode, self.controlFunctionTable, self._gkiAction)
		return self.stdgraph.control(gkiMetacode)
	
class GkiNull(GkiKernel):
	
	"""A version of the graphics kernel that does nothing except warn the
	user that it does nothing. Used when graphics display isn't possible"""

	def __init__(self):

		print "No graphics display available for this session " + \
			  "(Xwindow unavailable)"
		print "Graphics tasks that attempt to plot to an interactive " + \
			  "screen will fail"
		GkiKernel.__init__(self)
		self.functionTable = []
		self.controlFunctionTable = [self.controlDefault]*(GKI_MAX_OP_CODE+1)
		self.controlFunctionTable[GKI_OPENWS] = self.openWS
		self.controlFunctionTable[GKI_CLOSEWS] = self.closeWS
		self.controlFunctionTable[GKI_REACTIVATEWS] = self.reactivateWS
		self.controlFunctionTable[GKI_DEACTIVATEWS] = self.deactivateWS
		self.controlFunctionTable[GKI_CLEARWS] = self.clearWS
		self.controlFunctionTable[GKI_SETWCS] = self.setWCS
		self.controlFunctionTable[GKI_GETWCS] = self.getWCS
		self.name = 'Null'

	def control(self, gkiMetacode):

		gkiTranslate(gkiMetacode, self.controlFunctionTable, self._gkiAction)
		return self.returnData

	def translate(self, gkiMetacode, fTable): pass
	def controlDefault(self, dummy, arg): pass
	def controlDoNothing(self, dummy, arg): pass
	def openWS(self, dummy, arg):
		print "Unable to plot graphics to screen"
		raise iraf.IrafError
	def clearWS(self, dummy, arg): pass
	def reactivateWS(self, dummy, arg):
		raise iraf.IrafError
	def deactivateWS(self, dummy, arg): pass
	def setWCS(self, dummy, arg): pass
	def getWCS(self, dummy, arg):
		print "Attempt to access graphics when it isn't available"
		raise iraf.IrafError
	def closeWS(self, dummy, arg): pass


#********************************

def ndc(intarr):
		
	return intarr/GKI_MAX_FLOAT
	
def ndcpairs(intarr):
	
	f = ndc(intarr)
	return f[0::2],f[1::2]

