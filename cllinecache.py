"""cllinecache.py: Modify linecache so it works with translated CL scripts too

CL scripts have special filename "<CL script taskname>"

$Id$
"""

import linecache, string, os, sys
from stat import *
import iraf

# Discard cache entries that are out of date.
# (This is not checked upon each call!)

def checkcache():
	for filename in linecache.cache.keys():
		size, mtime, lines, fullname = linecache.cache[filename]
		try:
			if filename[:10] == "<CL script":
				# special CL script case - find original script file for time check
				taskname = fullname
				taskobj = iraf.getTask(taskname)
				fullname = taskobj.getFullpath()
			stat = os.stat(fullname)
			newsize = stat[ST_SIZE]
			newmtime = stat[ST_MTIME]
		except (os.error, iraf.IrafError):
			del linecache.cache[filename]
			continue
		if size <> newsize or mtime <> newmtime:
			del linecache.cache[filename]


# Update a cache entry and return its list of lines.
# If something's wrong, print a message, discard the cache entry,
# and return an empty list.

def updatecache(filename):
	if linecache.cache.has_key(filename):
		del linecache.cache[filename]
	if not filename or filename[0] + filename[-1] == '<>':
		if filename[:10] == "<CL script":
			# special CL script case
			return updateCLscript(filename)
		else:
			# normal case
			return []
	fullname = filename
	try:
		stat = os.stat(fullname)
	except os.error, msg:
		# Try looking through the module search path
		basename = os.path.split(filename)[1]
		for dirname in sys.path:
			fullname = os.path.join(dirname, basename)
			try:
				stat = os.stat(fullname)
				break
			except os.error:
				pass
		else:
			# No luck
##			print '*** Cannot stat', filename, ':', msg
			return []
	try:
		fp = open(fullname, 'r')
		lines = fp.readlines()
		fp.close()
	except IOError, msg:
##		print '*** Cannot open', fullname, ':', msg
		return []
	size, mtime = stat[ST_SIZE], stat[ST_MTIME]
	linecache.cache[filename] = size, mtime, lines, fullname
	return lines

def updateCLscript(filename):
	try:
		taskname = filename[11:-1]
		taskobj = iraf.getTask(taskname)
		fullname = taskobj.getFullpath()
		stat = os.stat(fullname)
		size = stat[ST_SIZE]
		mtime = stat[ST_MTIME]
		lines = string.split(taskobj.getCode(),'\n')
		linecache.cache[filename] = size, mtime, lines, taskname
		return lines
	except (iraf.IrafError, KeyError, AttributeError):
		return []

# insert these symbols into standard linecache module

_original_checkcache = linecache.checkcache
_original_updatecache = linecache.updatecache

def install():
	linecache.checkcache = checkcache
	linecache.updatecache = updatecache

def uninstall():
	linecache.checkcache = _original_checkcache
	linecache.updatecache = _original_updatecache

install()
