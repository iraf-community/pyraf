"""
OpenGL implementation of the gki kernel class

$Id$
"""

import gki
import iraf
import irafgwcs
import sys, os
import string

# kernels to flush frequently
# imdkern does not erase, so always flush it
alwaysFlush = {"imdkern": 1}

class GkiIrafKernel(gki.GkiKernel):

	"""This is designed to route metacode to an IRAF kernel executable.
	It needs very minimal functionality. The basic function is to collect
	metacode in the buffer and ship it off on flushes and when the kernel
	is shut down."""

	def __init__(self, device, executable, taskname):

		gki.GkiKernel.__init__(self)
		self.executable = executable
		self.device = device
		self.taskname = taskname
		self.wcs = None

	def control_openws(self, arg):
		# control_openws precedes gki_openws, so trigger on it to
		# send everything before the open to the device
		mode = arg[0]
		if mode == 5 or alwaysFlush.has_key(self.taskname):
			self.flush()
 
	def control_setwcs(self, arg):
		self.wcs = irafgwcs.IrafGWcs(arg)

	def control_getwcs(self, arg):
		if not self.wcs:
			raise iraf.IrafError("Can't append to a nonexistent plot!")
		if self.returnData:
			self.returnData = self.returnData + self.wcs.pack()
		else:
			self.returnData = self.wcs.pack()

	def gki_closews(self, arg):
		# gki_closews follows control_closews, so trigger on it to
		# send everything up through the close to the device
		if alwaysFlush.has_key(self.taskname):
			self.flush()

	def gki_flush(self, arg):
		if alwaysFlush.has_key(self.taskname):
			self.flush()

	def flush(self):
		# grab last part of buffer and delete it
		metacode = self.gkibuffer.delget().tostring()
		# only plot if buffer contains something
		if metacode:
			# write to a temporary file
			tmpfn = iraf.mktemp("iraf") + ".gki"
			fout = open(tmpfn,'w')
			fout.write(metacode)
			fout.close()
			try:
				if self.taskname == "stdgraph":
					# this is to allow users to specify via the
					# stdgraph device parameter the device they really
					# want to display to
					task = iraf.getTask(self.taskname)
					device = task.device
				elif self.taskname == "psikern":
					#XXX Note that parameters are always the same for
					#XXX graphics kernels as long as generic=yes.
					#XXX Should not load stsdas here,
					#XXX but rather create a (hidden) task if it does
					#XXX not exist.  That would work for any kernel
					#XXX that has a defined executable...
					if not iraf.stsdas.isLoaded():
						# load stsdas for this kernel
						iraf.stsdas(motd="no", _doprint=0)
					task = iraf.getTask("psikern")
					device = self.device
				else:
					task = iraf.getTask(self.taskname)
					device = self.device

				#XXX In principle we could read from Stdin by
				#XXX wrapping the string in a StringIO buffer instead of
				#XXX writing it to a temporary file.  But that will not
				#XXX work until binary redirection is implemented in
				#XXX irafexecute
				#XXX task(Stdin=tmpfn,device=device,generic="yes")

				# Set stdin/out to defaults because if they have been
				# redirected the task will try to read from them.
				task(tmpfn,device=device,generic="yes",
					Stdin=sys.__stdin__, Stdout=sys.__stdout__)
			finally:
				os.remove(tmpfn)
