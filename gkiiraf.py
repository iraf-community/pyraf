"""
OpenGL implementation of the gki kernel class

$Id$
"""

# from OpenGL.GL import *
#from gki import *
import gki
import iraf
#import Numeric
import irafgwcs
import sys, os
import string

class GkiIrafKernel(gki.GkiKernel):

	"""This is designed to route metacode to an IRAF kernel executable.
	It needs very minimal functionality. The basic function is to collect
	metacode in the buffer and ship it off on flushes and when the kernel
	is shut down"""

	def __init__(self, device, executable, taskname):

		gki.GkiKernel.__init__(self)
		self.gkiBuffer = gki.GkiBuffer()
		self.controlFunctionTable = [self.noAction]*(gki.GKI_MAX_OP_CODE+1)
		self._gkiAction = self._irafAction
		self.executable = executable
		self.taskname = taskname
		self.stdout = sys.__stdout__
		self.stderr = sys.__stderr__

	def getBuffer(self):

		return self.gkiBuffer

	def translate(self, gkiMetacode, fTable):

		gki.gkiTranslate(gkiMetacode, fTable, self._irafAction)

	def noAction(self, dummy, arg): pass

	def _irafAction(self, opcode, arg):

		"""Look for a gki_flush, otherwise, do nothing"""
		if opcode == gki.GKI_FLUSH:
			self.flush()

	def flush(self):

		# only plot if buffer contains something
		if self.gkiBuffer.get():
			# write to a temporary file
			tmpfn = iraf.mktemp("iraf") + ".gki"
			fout = open(tmpfn,'w')
			fout.write(self.gkiBuffer.get().tostring())
			fout.close()
			try:
				task = iraf.getTask(self.taskname)
				task(tmpfn)
			finally:
				os.remove(tmpfn)
		
