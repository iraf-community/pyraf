"""Finds device attributes from the graphcap

$Id$
"""

import string

def rdgraphcap(graphcapPath):
	f = open(graphcapPath)
	lines = f.readlines()
	f.close()
	return lines

def merge(inlines):
	out = []
	outbuff = []
	for inline in inlines:
		tline = string.strip(inline)
		if len(tline) > 0 and tline[0] != '#':
			if tline[-1] == '\\':
				# continuation
				outbuff.append(tline[:-1])
			else:
				outbuff.append(tline)
				out.append(string.join(outbuff,''))
				outbuff = []
	return out

def getAliases(entry):
	# return list of aliases (and dump the comment)
	aend = string.find(entry,':')
	astring = entry[:aend]
	done = 0
	alist = []
	while not done:
		pos = string.find(astring, '|')
		if pos > 0:
			alist.append(astring[:pos])
			astring = astring[pos+1:]
		else:
			done = 1
	return alist

def getAttributes(entry):
	abeg = string.find(entry,':')
	astring = entry[abeg+1:]
	attr = {}
	attrlist = string.split(astring,':')
	for attrstr in attrlist:
		if string.strip(attrstr):
			try:
				attrname = attrstr[:2]
				attrval = attrstr[2:]
				if len(attrstr) <= 2:
					value = -1
				elif attrval[0] == '=':
					value = attrval[1:]
				elif attrval[0] == '#':
					try:
						value = int(attrval[1:])
					except ValueError:
						try:
							value = float(attrval[1:])
						except ValueError:
							print "problem reading graphcap"
							raise
				elif attrval[0] == '@':
					# implies false
					value = None
				else:
					# ignore silently, at least as long as IRAF has a bad
					# entry in its distribution (illegal colons)
					# print "problem reading graphcap attributes: ", attrstr
					# print entry
					pass
				attr[attrname] = value
			except:
				raise
	return attr

def getDevices(devlist):
	devices = {}
	for devdef in devlist:
		aliases = getAliases(devdef)
		attributes = getAttributes(devdef)
		for alias in aliases:
			devices[alias] = attributes
	return devices

class GraphCap:

	def __init__(self, graphcapPath):
		lines = rdgraphcap(graphcapPath)
		mergedlines = merge(lines)	
		self.dict = getDevices(mergedlines)
	def __getitem__(self, key):
		if not self.dict.has_key(key):
			print "Error: device not found in graphcap"
			raise KeyError
		return Device(self.dict, key)
	def has_key(self, key):
		if self.dict.has_key(key):
			return 1
		else:
			return 0

class Device:

	def __init__(self, devices, devname):
		self.dict = devices
		self.devname = devname
	def getAttribute(self, attrName):
		dict = self.dict[self.devname]
		value = None
		while 1:
			if dict.has_key(attrName):
				value = dict[attrName]
				break
			else:
				if dict.has_key('tc'):
					nextdev = dict['tc']
					dict = self.dict[nextdev]
				else:
					break
		return value
	
	def __getitem__(self, key):
		return self.getAttribute(key)
