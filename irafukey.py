"""
implement IRAF ukey functionality

$id$
"""

import sys
import wutil, gwm
import termios, TERMIOS, sys, os, string

# This class emulates the IRAF ukey parameter mechanism. IRAF calls for
# a ukey parameter and expects that the user will type a character in
# response. The value of this character is then returned to the iraf task

def getSingleTTYChar():

	"""Returns None if Control-C is typed or any other exception occurs"""

	# Ripped off from python FAQ
	fd = sys.stdin.fileno()
	old = termios.tcgetattr(fd)
	new = termios.tcgetattr(fd)
	new[3] = new[3] & ~TERMIOS.ICANON & ~TERMIOS.ECHO
	new[6][TERMIOS.VMIN] = 1
	new[6][TERMIOS.VTIME] = 0
	termios.tcsetattr(fd, TERMIOS.TCSANOW, new)
	c = None
	try:
		c = os.read(fd, 1)
	finally:
		termios.tcsetattr(fd, TERMIOS.TCSAFLUSH, old)
		return c

def ukey():

	"""Returns the string expected for the IRAF ukey parameter"""

	char = getSingleTTYChar()
	# should determine what Control-C maps to, for now, CR
	if not char: returnStr = r'\012'
	elif ord(char) <= ord(' '):
		# convert to octal ascii representation
		returnStr = '\\'+"%03o" % ord(char)
	elif char == ':':
		# suck in colon string until newline is encountered
		done = 0
		sys.stdout.write(':')
		sys.stdout.flush()
		colonString = ''
		while not done:
			char = getSingleTTYChar()
			if (not char) or (char == '\n'):
				done = 1
			elif char == '\b':
				# backspace
				colonString = colonString[:-1]
				sys.stdout.write('\b \b')
				sys.stdout.flush()
			elif ord(char) >= ord(' '):
				colonString = colonString+char
				sys.stdout.write(char)
				sys.stdout.flush()
			else:
				# ignore all other characters
				pass
		returnStr = ': '+colonString
	else:
		returnStr = char
	return returnStr
