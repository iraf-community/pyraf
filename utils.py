#
#	Return whether a file exists or not.
#	The file "" is deemed to not exist
#

def file_exists(file_name):
	from posixpath import exists
	import string
	if len(file_name) == 0:
		return 0
	else:
		return exists(file_name)

#
#	read the lines from a file and strip them of their trailing newlines
#

def readlines(fd):
	from string import strip
	return map(lambda s, f=strip: f(s), fd.readlines())

#
#	Various set operations on sequence arguments.
#	in joins the values in 'a' take precedence over those in 'b'
#

def seq_join(a, b):
	res = a[:]
	for x in b:
		if x not in res:
			res.append(x)
	return res

def seq_meet(a, b):
	res = []
	for x in a:
		if x in b:
			res.append(x)
	return res

def seq_diff(a, b):
	res = []
	for x in a:
		if x not in b:
			res.append(x)
	return res

#
#	Various set operations on map arguments.
#	The values in 'a' take precedence over those in 'b' in all cases.
#

def map_join(a, b):
	res = {}
	for x in a.keys():
		res[x] = a[x]
	for x in b.keys():
		if not res.has_key(x):
			res[x] = b[x]
	return res

def map_meet(a, b):
	res = {}
	for x in a.keys():
		if b.has_key(x):
			res[x] = a[x]
	return res

def map_diff(a, b):
	res = {}
	for x in a.keys():
		if not b.has_key(x):
			res[x] = a[x]
	return res

#
#	Join a map of defaults values with a map of set values. The defaults 
#	map is taken to be total, and hence any keys not in the defaults, but 
#	in the settings, must be errors.
#

def map_join_total(settings, defaults):
	res = map_join(settings, defaults)
	for x in settings.keys():
		if not defaults.has_key(x):
			raise "merge_defaults"
	return res

#
#	Return a string being the concatenation of a sequence of objects
#	NOTE: we apply the routine recursively to sequences of sequences
#

def seq_to_str(s):
	if type(s) == type((1,)) or type(s) == type([]):
		return reduce(lambda sum, a: sum + seq_to_str(a), s, "")
	else:
		return str(s)

#
#	a dummy function for any number of arguments
#

def dummy(*args):
	pass

#
#	the true and false functions for any number of args
#

def true(*args):
	return 1

def false(*args):
	return 0

#
#	return whether a char is printable or not
#

def is_printable(c):
	o = ord(c)
	return c == "\n" or (o >= 32 and o <= 126)

#
#	return a printable version of a given string
#	by simply omitting non printable characters
#

def string_printable(s):
	length = len(s)
	ok = 1
	res = ""
	l = 0
	for i in range(length):
		if not is_printable(s[i]):
			res = res + s[l:i]
			l = i+1
			ok = 0
	if ok:
		return s
	else:
		return res + s[l:length]
