"""
IRAF GKI interpreter -- abstract implementation
$Id$
"""

import Numeric
from types import *
import gwm

BOI = -1  # beginning of instruction sentinel
NOP = 0	  # no op value
GKI_MAX = 32767
GKI_MAX_FLOAT = Numeric.array(GKI_MAX,Numeric.Float32)
GKI_MAX_OP_CODE = 27
GKI_FLOAT_FACTOR = 100.
MAX_ERROR_COUNT = 7

# need to treat this more generally
# Could do a test with struct & byte-swapping option to determine byte order

BYTESWAP = 0

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

class GkiBuffer:

	"""implement a buffer for gki which allocates memory in blocks so that 
	a new memory allocation is not needed everytime metacode is appended"""

	INCREMENT = 50000

	def __init__(self, metacode=None):
	
		getwcs = None  # Used to indicate a getwcs instruction was encountered
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
		self.nextTranslate = 0

	def append(self, metacode):

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
	
class GkiKernel:

	"""Abstract class intended to be subclassed by implementations of GKI
	kernels. This is to provide a standard interface to irafexecute"""

	
	def __init__(self):
	
		self.functionTable = []
		self.returnData = None
		self.errorMessageCount = 0

	def errorMessage(self, text):

		if self.errorMessageCount < MAX_ERROR_COUNT:
			print text
			self.errorMessageCount = self.errorMessageCount + 1
	
	def control(self, gkiMetacode):

		# stub routine to be overridden in subclass. Purpose is to act
		# on the GKI control instructions destined for that particular
		# graphics kernel.
		pass

	def append(self, gkiMetacode):
	
		# if input parameter is string, assume it is a filename and read into
		# a numeric array
		try:
			if gwm.getActiveWindow():
				if type(gkiMetacode) == StringType:
					gkiMetacode = getdata(gkiMetacode)
				win = gwm.getActiveWindow()
				buffer = win.iplot.gkiBuffer
				buffer.append(gkiMetacode)
				# a hook for acting on the metacode, but is only a stub routine
				# that must be overridden in the subclass (or not, depending)
				self.translate(buffer, self.functionTable)
		except AttributeError:
			print "ERROR: no IRAF plot window active"

	def translate(self, gkiBuffer, functionTable):

		# stub routine to be overridden in subclass of GkiKernel
		pass

	def clearReturnData(self):

		# intended to be called after return data is used by the client
		self.returnData = None
		
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
		apply(functionTable[opcode], (arg,))
		opcode, arg = gkiBuffer.getNextCode()


#********************************

def getdata(filename):

	f = open(filename, 'rb')
	rawbytes = f.read() 
	rawarray = Numeric.fromstring(rawbytes,'s')
	if BYTESWAP:
		# intel for example
		return rawarray.byteswapped()
	else:
		# sparcs for example
		return rawarray

def ndc(intarr):
		
	return intarr/GKI_MAX_FLOAT
	
def ndcpairs(intarr):
	
	f = ndc(intarr)
	return f[0::2],f[1::2]

