"""
OpenGL implementation of the gki kernel class

$Id$
"""

import gki
import iraf
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
		self.controlFunctionTable = [self.noAction]*(gki.GKI_MAX_OP_CODE+1)
		self.controlFunctionTable[gki.GKI_OPENWS] = self.openWS
		self.controlFunctionTable[gki.GKI_GETWCS] = self.getWCS
		self.controlFunctionTable[gki.GKI_SETWCS] = self.setWCS
		self.executable = executable
		self.device = device
		self.taskname = taskname
		self.stdin = None
		self.stdout = None
		self.stderr = None
		self.wcs = None
		self.returnData = None

	def nullAction(self, arg): pass

	def control(self, gkiMetacode):

		gki.gkiTranslate(gkiMetacode, self.controlFunctionTable,
						 self.nullAction)
		return self.returnData

	def noAction(self, dummy, arg):
		pass

	def openWS(self, dummy, arg):
		pass

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

	def _gkiAction(self, opcode, arg):
		pass

	def flush(self):

		# only plot if buffer contains something
		if len(self.gkibuffer):
			# write to a temporary file
			tmpfn = iraf.mktemp("iraf") + ".gki"
			fout = open(tmpfn,'w')
			fout.write(self.gkibuffer.get().tostring())
			fout.close()
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

