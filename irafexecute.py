"""Module contains functions to allow the execution of IRAF connected
subprocesses

$Id$
"""

import os, re, signal, string, struct, sys, time
import subproc
import gki
import gkiopengl
import gwm

# for debugging purposes (for generating a tk window for listing
# subprocess communication events
monitor = 0
monwidget = None
if monitor and (monwidget == None):
	import irafmonitor, StringIO
	monwidget = irafmonitor.IRAFmonitor()

stdgraph = None

class IrafProcessError(Exception):
	pass

def IrafExecute(task, executable, envdict, paramDictList):

	"""Execute IRAF task in the given executable (full path included)
	using the provided envionmental variables and parameters.
	paramDictList is a list of parameter dictionaries."""

	# Start'er up
	try:
		process = subproc.Subprocess(executable+' -c')
	except subproc.SubprocessError, value:
		raise IrafProcessError("problems starting IRAF executable\n" + value)
	try:
		keys = envdict.keys()
		if len(keys) > 0:
			for i in xrange(len(keys)):
				outenvstr = "set "+keys[i]+"="+envdict[keys[i]]+"\n"
				WriteStringToIrafProc(process, outenvstr)
		# terminate set up mode
		WriteStringToIrafProc(process,'_go_\n')
		# start IRAF logical task
		WriteStringToIrafProc(process,task+'\n')
		# begin slave mode
		IrafIO(process,paramDictList)
		# kill the damn thing, process caches are for weenies
		IrafTerminate(process)
	except KeyboardInterrupt:
		# On keyboard interrupt (^c), kill the subprocess
		IrafKill(process)
	except IrafProcessError, exc:
		# on error, kill the subprocess, then re-raise the original exception
		try:
			IrafKill(process)
		except Exception, exc2:
			# append new exception text to previous one (right thing to do?)
			exc.args = exc.args + exc2.args
		raise exc
	return

# XXX is _re_chan_len supposed to match to end of string?  I added
# a '$' at end of pattern.  Since we always read some binary
# data after this, I assume it is never in a combined message.

_re_chan_len = re.compile(r'\((\d+),(\d+)\)$')
_re_parmset = re.compile(r'([a-zA-Z_][a-zA-Z0-9_.]*)\s*=\s*(.*)\n')

def IrafIO(process,paramDictList):

	"""Talk to the IRAF process in slave mode. Raises an IrafProcessError
	if an error occurs."""

	global stdgraph
	msg = ''
	while 1:
		# each read may return multiple lines; only
		# read new data when old has been used up
		if not msg:
			data = ReadFromIrafProc(process)
			msg = Iraf2AscString(data)
		if msg[0:4] == 'bye\n':
			return
		elif msg[0:5] == "ERROR" or msg[0:5] == 'error':
			raise IrafProcessError("IRAF task terminated abnormally\n" + msg)
		elif msg[0:4] == 'xmit':
			mo = _re_chan_len.match(msg,4)
			if not mo:
				raise IrafProcessError("Illegal xmit command format\n" + msg)
			chan = int(mo.group(1))
			nbytes = int(mo.group(2))
			# this is always the last command in a message
			msg = ''
			xdata = ReadFromIrafProc(process)
			if len(xdata) != 2*nbytes:
				raise IrafProcessError("Error, wrong number of bytes read\n" +
					("(got %d, expected %d, chan %d)" %
						(len(xdata), 2*nbytes, chan)))
			else:
				if chan == 4:
					print Iraf2AscString(xdata),
				elif chan == 5:
					sys.stderr.write(Iraf2AscString(xdata))
				elif chan == 6:
					print "data for STDGRAPH"
					stdgraph.append(Numeric.fromstring(xdata,'s'))
				elif chan == 7:
					print "data for STDIMAGE"
				elif chan == 8:
					print "data for STDPLOT"
				elif chan == 9:
					print "data for PSIOCNTRL"
					sdata = Numeric.fromstring(xdata,'s')
					forChan = sdata[1] # a bit sloppy here
					print forChan
					if forChan == 6:
						# STDPLOT control
						# first see if OPENWS to get device, otherwise
						# pass through to current kernel, use braindead
						# interpetation to look for openws 
						if (sdata[2] == -1) and (sdata[3] == 1):
							print "openws for stdgraph"
							length = sdata[4]
							device = sdata[5:length+2].astype('b').tostring()
							# but of course, for the time being (until
							# we manage another graphics kernel, we ignore
							# device!
							if stdgraph == None:
								stdgraph = gkiopengl.GkiOpenGlKernel()
						
						# pass it to the kernel to deal with
						stdgraph.control(sdata[2:])
 					else:
						print "GRAPHICS control data for channel",forChan
						
#						print adata[0:10]
#						oldstdout = sys.stdout
#						sys.stdout = StringIO.StringIO()
#						gkistr = sys.stdout.getvalue()
#						monwidget.append(gkistr)
#						sys.stdout.close()
#						sys.stdout = oldstdout
				else:
					print "data for channel", chan
		elif msg[0:4] == 'xfer':
			# XXX Is setting msg to '' the right thing to do?
			msg = ''
		elif msg[0] == '=':
			# param get request
			# XXX is this correct?  Can this command be stacked?
			# If so, need to match to end of line
			value = msg[1:-1]
			msg = ''
			WriteStringToIrafProc(process, _getParam(paramDictList,value) + '\n')
		else:
			# last possibility: set value of parameter
			mo = _re_parmset.match(msg)
			if mo:
				msg = msg[mo.end():]
				paramname, newvalue = mo.groups()
				_setParam(paramDictList,paramname,newvalue)
			else:
				print "Warning, unrecognized IRAF pipe protocol"
				print msg

def _setParam(paramDictList,paramname,newvalue):
	"""Set parameter specified by paramname to newvalue."""
	# XXX need to add capability to set field (e.g. x1.p_maximum
	# is set in iraf/pkg/plot/t_pvector.x)
	for paramdict in paramDictList:
		if paramdict.has_key(paramname):
			paramdict[paramname].set(newvalue)
			return
	else:
		raise IrafProcessError(
			"Task attempts to set unknown parameter " + paramname)

def _getParam(paramDictList,value):

	"""Return parameter specified by value, which can be a simple parameter
	name or can be [[package.]task.]paramname[.field]"""

	slist = string.split(value,'.')
	field = None
	package = None
	task = None
	ip = len(slist)-1
	if ip>0 and slist[ip][:2] == "p_":
		field = slist[ip]
		ip = ip-1
	paramname = slist[ip]
	if ip > 0:
		ip = ip-1
		task = slist[ip]
	if ip > 0:
		ip = ip-1
		package = slist[ip]
	if ip > 0:
		raise IrafProcessError(
			"Illegal parameter request from IRAF task: " + value)

	# array parameters may have subscript

	pstart = string.find(paramname,'[')
	if pstart < 0:
		pindex = None
	else:
		try:
			pend = string.rindex(paramname,']')
			pindex = int(paramname[pstart+1:pend])-1
			paramname = paramname[:pstart]
		except:
			raise IrafProcessError(
				"IRAF task asking for illegal array parameter: " + value)

	if task and (not package):
		# maybe this task is the name of one of the dictionaries?
		for dictname, paramdict in paramDictList:
			if dictname == task:
				if paramdict.has_key(paramname):
					return paramdict[paramname].get(index=pindex,field=field)
				else:
					raise IrafProcessError(
						"IRAF task asking for parameter not in list: " +
						value)

	# XXX still need to add full-blown package and package.task handling
	if package or task:
		raise IrafProcessError(
			"Cannot yet handle parameter request with task and/or package: " +
			value)

	for dictname, paramdict in paramDictList:
		if paramdict.has_key(paramname):
			return paramdict[paramname].get(index=pindex,field=field)
	else:
		raise IrafProcessError(
			"IRAF task asking for parameter not in list: " +
			value)

def IrafKill(process):
	"""Try stopping process in IRAF approved way first; if that fails
	blow it away. Copied with minor mods from subproc.py."""

	if not process.pid: return		# no need, process gone

	print " Killing IRAF task"
	if not process.cont():
		raise IrafProcessError("Can't kill IRAF subprocess")
	# get the task's attention for input
	try:
		os.kill(process.pid, signal.SIGTERM)
	except os.error:
		pass
	IrafTerminate(process)

def IrafTerminate(process):
	"""Standard IRAF task termination (assuming we already have the task's
	attention for input.)"""

	# Send bye message to task
	# Wait briefly for EOF, which signals task is done
	# Kill it anyway if it is still hanging around

	if process.pid:
		WriteStringToIrafProc(process,"bye\n")
		if not process.wait(0.5): process.die()

# IRAF string conversions using Numeric module
import Numeric

def Asc2IrafString(ascii_string):
	"""translate ascii to IRAF 16-bit string format"""
	inarr = Numeric.fromstring(ascii_string, Numeric.Int8)
	return inarr.astype(Numeric.Int16).tostring()

def Iraf2AscString(iraf_string):
	"""translate 16-bit IRAF characters to ascii"""
	inarr = Numeric.fromstring(iraf_string, Numeric.Int16)
	return inarr.astype(Numeric.Int8).tostring()

def WriteStringToIrafProc(process, astring):

	"""convert ascii string to IRAF form, prepend necessary bytes,
	and write to IRAF process"""

	istring = Asc2IrafString(astring)
	#     IRAF magic number    number of following bytes
	# XXX In these calls, should we check for len(istring) > 65535?
	record = '\002\120'    + struct.pack('>h',len(istring)) + istring
	process.write(record)
	return

def WriteToIrafProc(process, data):

	"""write binary data to IRAF process"""

	process.write('\002\120'+struct.pack('>h',len(data))+data)
	return

def ReadFromIrafProc(process):
	
	"""read input from IRAF pipe"""
	
	# read pipe header first
	header = process.read(4)
	if (header[0:2] != '\002\120'):
		raise IrafProcessError("Not a legal IRAF pipe record")
	ntemp = struct.unpack('>h',header[2:])
	nbytes = ntemp[0]
	# read the rest
	data = process.read(nbytes)
	return data
