"""IRAF GKI interpreter"""

import Numeric
from types import *

BOI = -1  # beginning of instruction sentinel
NOP = 0	 # no op value
GKI_MAX = 32767
GKI_MAX_FLOAT = Numeric.array(GKI_MAX,Numeric.Float32)
GKI_MAX_OP_CODE = 27

# need to treat this more generally

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

class GkiBuffer:

	"""implement a buffer for gki which allocates memory in blocks so that 
	a new memory allocation is not needed everytime metacode is appended"""

	INCREMENT = 50000
	
	def __init__(self):
	
		self.reset()	
	
	def reset(self):
	
		self.buffer = None
		self.bufferSize = 0
		self.bufferEnd = 0 
		
	def append(self, metacode):
	
		if self.bufferSize < (self.bufferEnd + len(metacode)):
			# increment buffer size and copy into new array
			print "growing metacode buffer"
			self.bufferSize = self.bufferSize + self.INCREMENT
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

class GkiKernel:

	"""Abstract class intended to be subclassed by implementations of GKI
	kernels. This is to provide a standard interface to irafexecute"""

	
	def __init__(self):
	
		self.gkiBuffer = GkiBuffer()
		self.functionTable = []
	
	def clear(self):
	
		self.gkiBuffer.reset()
		
	def control(self, gkiMetacode):

		# stub routine to be overridden in subclass. Purpose is to act
		# on the GKI control instructions destined for that particular
		# graphics kernel.
		pass

	def append(self, gkiMetacode):
	
		# if input parameter is string, assume it is a filename and read into
		# a numeric array
		if type(gkiMetacode) == StringType:
			self.gkiBuffer.append(getdata(gkiMetacode))
		else:
			self.gkiBuffer.append(gkiMetacode)
		# a hook for acting on the metacode, but is only a stub routine
		# that must be overridden in the subclass (or not, depending)
		self.translate(gkiMetacode, self.functionTable)

	def translate(self, gkiMetacode, functionTable):

		# stub routine to be overridden in subclass of GkiKernel
		pass

#********************************

def getdata(filename):

	f = open(filename, 'rb')
	rawbytes = f.read(10000000l) 
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

def gkiTranslate(gkiMetacode, functionTable):

	"""General Function that can be used for decoding and interpreting
	the GKI metacode stream. FunctionTable is a 28 element list containing
	the functions to invoke for each opcode encountered. This table should
	be different for each kernel that uses this function and the control
	method"""

	# It is not expected that any metacode recieved from the iraf task
	# will have incomplete gki instructions (i.e., continued in the
	# next bunch of data from the iraf channel) but checks are performed
	# here in case that assumption is not true and a message to
	# that effect is printed out
	
	# initialize "instruction pointer"
	ip = 0
	lenMC = len(gkiMetacode)
	# start interpreting instructions
	while ip < lenMC:
		if gkiMetacode[ip] == NOP:
			ip = ip+1
		elif gkiMetacode[ip] != BOI:
			print "WARNING, missynched gki data stream"
			# find next possible beginning of instruction
			while gkiMetacode[ip] != BOI:
				if ip >= lenMC:
					print "Truncated GKI metacode?"
					return
				ip = ip+1
		else:
			if ip+2 >= lenMC:
				print "Truncated GKI metacode"
			opcode = gkiMetacode[ip+1]
			if ((opcode < 0) or 
				(opcode > GKI_MAX_OP_CODE) or
				(opcode in [21,22,23,24])):
					print "Illegal opcode found, opcode = ",opcode
			arglen = gkiMetacode[ip+2]
			if (ip+arglen) > lenMC:
				print "Truncated GKI metacode"
			arg = gkiMetacode[ip+3:ip+3+arglen-3]
			apply(functionTable[opcode], (arg,))
			ip = ip + arglen
