"""module irafutils.py -- general utility functions

$Id$

R. White, 1999 Jul 16
"""

import string, struct, re, keyword

def printCols(strlist,cols=5,width=80):

	"""Print elements of list in cols columns"""

	# This may exist somewhere in the Python standard libraries?
	# Should probably rewrite this, it is pretty crude.

	nlines = (len(strlist)+cols-1)/cols
	line = nlines*[""]
	for i in xrange(len(strlist)):
		c, r = divmod(i,nlines)
		nwid = c*width/cols - len(line[r])
		if nwid>0:
			line[r] = line[r] + nwid*" " + strlist[i]
		else:
			line[r] = line[r] + " " + strlist[i]
	for s in line:
		print s

def isBigEndian():

	"""Determine if processor is big endian or little endian"""

	i = 1
	tup = struct.unpack('hh',struct.pack('=i',i))
	if tup[1] == 1:
		return 1
	else:
		return 0

_re_doubleq2 = re.compile('""')
_re_singleq2 = re.compile("''")

def stripQuotes(value):

	"""Strip single or double quotes off string; remove embedded quote pairs"""

	if value[:1] == '"':
		value = value[1:]
		if value[-1:] == '"':
			value = value[:-1]
		# replace "" with "
		value = re.sub(_re_doubleq2, '"', value)
	elif value[:1] == "'":
		value = value[1:]
		if value[-1:] == "'":
			value = value[:-1]
		# replace '' with '
		value = re.sub(_re_singleq2, "'", value)
	return value

def removeEscapes(value):

	"""Remove escapes from in front of quotes (which IRAF seems to
	just stick in for fun sometimes.)  Remove \-newline too.
	Don't worry about multiple-backslash case -- this will replace
	\\" with just ", which is fine by me.
	"""

	i = string.find(value,r'\"')
	while i>=0:
		value = value[:i] + value[i+1:]
		# search from beginning every time to handle multiple \\ case
		i = string.find(value,r'\"')
	i = string.find(value,r"\'")
	while i>=0:
		value = value[:i] + value[i+1:]
		i = string.find(value,r"\'")
	# delete backslash-newlines
	i = string.find(value,"\\\n")
	while i>=0:
		value = value[:i] + value[i+2:]
		i = string.find(value,"\\\n")
	return value

# Must modify Python keywords to make Python code legal.  I add 'PY' to
# beginning of Python keywords (and some other illegal Python identifiers).
# It will be stripped off where appropriate.

def replaceReserved(s, dot=0):

	"""Convert CL parameter or variable name to Python-acceptable name

	Translate embedded dollar signs to 'DOLLAR'
	Add 'PY' prefix to components that are Python reserved words
	Add 'PY' prefix to components start with a number
	If dot != 0, also replaces '.' with 'DOT'
	"""

	i = string.find(s, '$')
	while (i >= 0):
		s = s[:i] + 'DOLLAR' + s[i+1:]
		i = string.find(s, '$', i+6)
	sparts = string.split(s,'.')
	for i in range(len(sparts)):
		if sparts[i] == "" or sparts[i][0] in string.digits or \
		  keyword.iskeyword(sparts[i]):
			sparts[i] = 'PY' + sparts[i]
	if dot:
		return string.join(sparts,'DOT')
	else:
		return string.join(sparts,'.')

def unreplaceReserved(s, dot=0):

	"""Undo Python conversion of CL parameter or variable name"""

	# translate 'DOT' embedded in name to '.'
	i = string.find(s, 'DOT')
	while (i>=0):
		s = s[:i] + '.' + s[i+3:]
		i = string.find(s, 'DOT', i+1)
	# translate 'DOLLAR' embedded in name to '$'
	i = string.find(s, 'DOLLAR')
	while (i>=0):
		s = s[:i] + '$' + s[i+6:]
		i = string.find(s, 'DOLLAR', i+1)
	# delete 'PY' embedded in name
	i = string.find(s, 'PY')
	while (i>=0):
		s = s[:i] + s[i+2:]
		i = string.find(s, 'PY', i)
	return s

