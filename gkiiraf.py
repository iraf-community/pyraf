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
		self.controlFunctionTable[gki.GKI_OPENWS] = self.openws
		self.controlFunctionTable[gki.GKI_GETWCS] = self.getWCS
		self.controlFunctionTable[gki.GKI_SETWCS] = self.setWCS
		self._gkiAction = self._irafAction
		self.executable = executable
		self.device = device
		self.taskname = taskname
		self.stdin = None
		self.stdout = None
		self.stderr = None
		self.wcs = None
		self.returnData = None
		
	def getBuffer(self):

		return self.gkiBuffer

	def nullAction(self, arg): pass
	
	def control(self, gkiMetacode):

		gki.gkiTranslate(gkiMetacode, self.controlFunctionTable,
						 self.nullAction)
		return self.returnData

#	def translate(self, gkiMetacode, fTable):

#		gki.gkiTranslate(gkiMetacode, fTable, self._irafAction)

	def noAction(self, dummy, arg): pass

	def openws(self, dummy, arg):

		mode = arg[0]
		if mode == 5:
			self.gkiBuffer = gki.GkiBuffer()
			
	def setWCS(self, dummy, arg):

		self.wcs = irafgwcs.IrafGWcs(arg)

	def getWCS(self, dummy, arg):

		if not self.wcs:
			self.errorMessage("Error: can't append to a nonexistent plot!")
			raise iraf.IrafError
		if self.returnData:
			self.returnData = self.returnData + self.wcs.pack()
		else:
			self.returnData = self.wcs.pack()
			
#	def translate(self, gkiMetacode, fTable):

#		gki.gkiTranslate(gkiMetacode, fTable, self._gkiAction)

	def _irafAction(self, opcode, arg): pass

#		print opcode
#		"""Look for a gki_open, otherwise, do nothing"""
#		if opcode == gki.GKI_OPENWS:
#			print "gkiiraf openws", arg[0]
#			mode = arg[0]
#			if mode == 5:
#				self.gkiBuffer.reset()

	def flush(self):

		# only plot if buffer contains something
		if len(self.gkiBuffer):
			# write to a temporary file
			tmpfn = iraf.mktemp("iraf") + ".gki"
			fout = open(tmpfn,'w')
			fout.write(self.gkiBuffer.get().tostring())
			fout.close()
			#self.gkiBuffer.reset()
			try:
				if self.taskname == "stdgraph":
					# this is to allow users to specify via the
					# stdgraph device parameter the device they really
					# want to display to		
					task = iraf.getTask(self.taskname)
					task(tmpfn,generic="yes")
				elif self.taskname == "psikern":
					tempmode = iraf.stsdas.motd
					iraf.stsdas.motd="no"
					iraf.load("stsdas",doprint=0)
					iraf.stsdas.motd=tempmode
					iraf.load("graphics",doprint=0)
					iraf.load("stplot",doprint=0)
					task = iraf.getTask("psikern")
					task(tmpfn,device=self.device,generic='yes')
				else:
					task = iraf.getTask(self.taskname)
					task(tmpfn,device=self.device,generic='yes')
			finally:
				os.remove(tmpfn)

