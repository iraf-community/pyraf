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
		self.executable = executable
		self.device = device
		self.taskname = taskname
		self.wcs = None

	def control_setwcs(self, arg):
		self.wcs = irafgwcs.IrafGWcs(arg)

	def control_getwcs(self, arg):
		if not self.wcs:
			#YYY clean up - raise exception with message
			self.errorMessage("Error: can't append to a nonexistent plot!")
			raise iraf.IrafError
		if self.returnData:
			self.returnData = self.returnData + self.wcs.pack()
		else:
			self.returnData = self.wcs.pack()

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

