"""clcache.py: Implement cache for Python translations of CL tasks

$Id$

R. White, 2000 January 19
"""

import os, sys, types, string
from irafglobals import Verbose, userIrafHome, pyrafDir

# set up pickle so it can pickle code objects

import copy_reg, marshal, types
try:
	import cPickle
	pickle = cPickle
except ImportError:
	import pickle

def code_unpickler(data):
	return marshal.loads(data)

def code_pickler(code):
	return code_unpickler, (marshal.dumps(code),)

copy_reg.pickle(types.CodeType, code_pickler, code_unpickler)

# Code cache is implemented using a dictionary clFileDict and a list of
# persistent dictionaries (shelves) in cacheList.
#
# - clFileDict uses CL filename as the key and has a tuple
#   value with the md5 digest of the file contents and
#	file attributes (file size, and file creation/modification
#	dates)
#
# - the persistent cache has the md5 digest as the key
#	and the Pycode object as the value.
#
# This scheme allows files with different path names to
# be found in the cache (since the file contents, not the
# name, determine the shelve key), and uses the size & dates
# in clFileDict for a quick check to see whether the Pycode
# is still up-to-date for the given file so the md5 digest
# does not have to be recomputed.

import dirshelve, stat, md5

_versionKey = 'CACHE_VERSION'
_currentVersion = "v1"

class _CodeCache:

	"""Python code cache class"""

	def __init__(self, cacheFileList):
		# 
		cacheList = []
		flist = []
		nwrite = 0
		for file in cacheFileList:
			db = self._cacheOpen(file)
			if db is not None:
				cacheList.append(db)
				nwrite = nwrite+db[0]
				flist.append(file)
		self.clFileDict = {}
		self.cacheList = cacheList
		self.cacheFileList = flist
		self.nwrite = nwrite
		# flag indicating preference for system cache
		self.useSystem = 0
		if not cacheList:
			self.warning("Unable to open any CL script cache, "
				"performance will be slow")
		elif nwrite == 0:
			self.warning("Unable to open any CL script cache for writing")

	def _cacheOpen(self, filename):
		"""Open shelve database in filename and check version to make sure it is OK

		Returns tuple (writeflag, shelve-object) on success or None on failure.
		"""
		# first try opening the cache read-write
		try:
			fh = dirshelve.open(filename)
			writeflag = 1
		except dirshelve.error:
			# initial open failed -- try opening the cache read-only
			try:
				fh = dirshelve.open(filename,"r")
				writeflag = 0
			except dirshelve.error:
				self.warning("Unable to open CL script cache file %s" %
					(filename,))
				return None
		# check version of cache -- don't use it if out-of-date
		if fh.has_key(_versionKey):
			oldVersion = fh[_versionKey]
		elif len(fh) == 0:
			fh[_versionKey] = _currentVersion
			oldVersion = _currentVersion
		else:
			oldVersion = 'v0'
		if oldVersion == _currentVersion:
			return (writeflag, fh)
		# open succeeded, but version looks out-of-date
		fh.close()
		rv = None
		msg = ["CL script cache file is obsolete version (old %s, current %s)" %
			(`oldVersion`, `_currentVersion`)]
		if not writeflag:
			# we can't replace it if we couldn't open it read-write
			msg.append("Ignoring obsolete cache file %s" % filename)
		else:
			# try renaming the old file and creating a new one
			rfilename = filename + "." + oldVersion
			try:
				os.rename(filename, rfilename)
				msg.append("Renamed old cache to %s" % rfilename)
				try:
					# create new cache file
					fh = dirshelve.open(filename)
					fh[_versionKey] = _currentVersion
					msg.append("Created new cache file %s" % filename)
					rv = (writeflag, fh)
				except dirshelve.error:
					msg.append("Could not create new cache file %s" % filename)
			except OSError:
				msg.append("Could not rename old cache file %s" % filename)
		self.warning(string.join(msg,"\n"))
		return rv

	def warning(self, msg, level=0):

		"""Print warning message to stderr, using verbose flag"""

		if Verbose >= level:
			sys.stdout.flush()
			sys.stderr.write(msg + "\n")
			sys.stderr.flush()

	def writeSystem(self, value=1):

		"""Add scripts to system cache instead of user cache"""

		if value==0:
			self.useSystem = 0
		elif self.cacheList:
			writeflag, cache = self.cacheList[-1]
			if writeflag:
				self.useSystem = 1
			else:
				self.warning("System CL script cache is not writable")
		else:
			self.warning("No CL script cache is active")

	def close(self):

		"""Close all cache files"""

		for writeflag, cache in self.cacheList:
			cache.close()
		self.cacheList = []
		self.nwrite = 0
		# Note that this does not delete clFileDict since the
		# in-memory info for files already read is still OK 
		# (Just in case there is some reason to close cache files
		# while keeping _CodeCache object around for future use.)

	def __del__(self):
		self.close()

	def getAttributes(self, filename):

		"""Get file attributes for a file or filehandle"""

		if type(filename) is types.StringType:
			st = os.stat(filename)
		elif hasattr(filename, 'fileno') and hasattr(filename, 'name'):
			fh = filename
			st = os.fstat(fh.fileno())
		else:
			return None
		# file attributes are size, creation, and modification times
		return st[stat.ST_SIZE], st[stat.ST_CTIME], st[stat.ST_MTIME]

	def getIndex(self, filename, source=None):

		"""Get cache key for a file or filehandle"""

		attributes = self.getAttributes(filename)
		if attributes is None: return None
		# get key from clFileDict if file attributes are up-to-date
		if self.clFileDict.has_key(filename):
			oldkey, oldattr = self.clFileDict[filename]
			if oldattr == attributes:
				return oldkey
			#XXX Note that old out-of-date cached code never gets
			#XXX removed in this system.  That's because another CL
			#XXX script might still exist with the same code.  Need a
			#XXX utility to clean up the cache by looking for unused keys...
		else:
			oldkey = None
		# use md5 digest as key
		# read the source code if source is not defined
		if hasattr(filename, 'fileno') and hasattr(filename, 'name'):
			fh = filename
			filename = fh.name
		if source is None:
			if type(filename) is types.StringType:
				source = open(filename).read()
			else:
				source = fh.read()
		key = md5.new(source).digest()
		self.clFileDict[filename] = (key, attributes)
		# print a warning if current file appears older than cached version
		if oldkey is not None and oldkey != key and \
		  (oldattr[1]>attributes[1] or oldattr[2]>attributes[2]):
			self.warning("Warning: cached CL script (%s)"
				" in %s was newer than current script"
				 % (filename,self.cacheFileList[i]))
		return key

	def add(self, index, pycode):

		"""Add pycode to cache with key = index.  Ignores if index=None."""

		if index is None or self.nwrite==0: return
		if self.useSystem:
			# system cache is last in list
			cacheList = self.cacheList[:]
			cacheList.reverse()
		else:
			cacheList = self.cacheList
		for writeflag, cache in cacheList:
			if writeflag:
				cache[index] = pycode
				return

	def get(self, filename, mode="proc", source=None):

		"""Get pycode from cache for this file.
		
		Returns tuple (index, pycode).  Pycode=None if not found
		in cache.  If mode != "proc", assumes that the code should not be
		cached.
		"""

		if mode != "proc": return None, None

		index = self.getIndex(filename, source=source)
		if index is None: return None, None

		for i in range(len(self.cacheList)):
			writeflag, cache = self.cacheList[i]
			if cache.has_key(index):
				pycode = cache[index]
				pycode.index = index
				return index, pycode
		return index, None

	def remove(self, filename):

		"""Remove pycode from cache for this file or IrafTask object.
		
		This deletes the entry from the shelve persistent database, under
		the assumption that this routine may be called to fix a bug in
		the code generation (so we don't want to keep the old version of
		the Python code around.)
		"""

		if type(filename) is not types.StringType:
			try:
				task = filename
				filename = task.getFullpath()
			except (AttributeError, TypeError):
				raise TypeError(
					"Filename parameter must be a string or IrafCLTask")
		index = self.getIndex(filename)
		# system cache is last in list
		irange = range(len(self.cacheList))
		if self.useSystem: irange.reverse()
		nremoved = 0
		for i in irange:
			writeflag, cache = self.cacheList[i]
			if cache.has_key(index):
				if writeflag:
					del cache[index]
					self.warning("Removed %s from CL script cache %s" % \
						(filename,self.cacheFileList[i]), 2)
					nremoved = nremoved+1
				else:
					self.warning("Cannot remove %s from read-only "
						"CL script cache %s" % \
						(filename,self.cacheFileList[i]))
		if nremoved==0:
			self.warning("Did not find %s in CL script cache" % filename, 2)


# create code cache

userCacheDir = os.path.join(userIrafHome,'pyraf')
if not os.path.exists(userCacheDir):
	try:
		os.mkdir(userCacheDir)
		print 'Created directory %s for cache' % userCacheDir
	except OSError:
		print 'Could not create directory %s' % userCacheDir

dbfile = 'clcache'
codeCache = _CodeCache([
	os.path.join(userCacheDir,dbfile),
	os.path.join(pyrafDir,dbfile),
	])
del userCacheDir, dbfile

