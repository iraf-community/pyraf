#! /usr/local/bin/python -i 

# things to consider changing:
#
# 1) Heavy use of multiple return points in routines is probably bad
# 		practice 
# 2) Use of integer return values in place of string state identifiers
#     e.g. use INCOMPLETE (akin to enumerate) instead of "incomplete"
# 3) OO state representation model for block_group gcontinue.

"""Code for front end interpeter supplying block braces, system escapes,
and logging

$Id$ 
"""

import string, re, sys, os, traceback

def find_next_in_set(line, posstart, string_set):

	"""Which string of set occurs first in the given string?

Arguments are:

	line:			The line to be searched
	posstart:	Position to start search
	string_set:	List containing the set of strings to try matching
	
	Returns tuple: (start position of earliest matching string [-1 if no match],
						 String that matched first)
"""
	pos = -1
	firststring = None
	for sstring in string_set:
		tpos = string.find(line,sstring, posstart)
		if (tpos >= 0):
			if (tpos == pos):
				if len(sstring) > len(firststring):
					# longer string wins ties
					pos = tpos
					firststring = sstring
			if (tpos < pos) or (pos < 0):
				pos = tpos
				firststring = sstring
	return (pos, firststring)				

def makenext(pos, fstring):

	"""A factory function for pair group objects"""

	ret = None
	if fstring == "{":
		ret = brace_group(pos)
	elif fstring == "[":
		ret = bracket_group(pos)
	elif fstring == "(":
		ret = paren_group(pos)
	elif ((fstring == "'''") or (fstring == '"""') or 
			(fstring == "'")   or (fstring == '"')):
		ret = string_group(pos, fstring)
	elif fstring == "block":
		ret = block_group(pos)
	else:
		ret = "????"
	return ret

class monty:

	"""The main class for the interpreter"""

	# access to the following is needed by the group classes,
	# so rather than pass the monty object, the group classes
	# refer directly to the class variables
	block_mode = "indent"
	linenum = 0
	delimit_stack = []

	def __init__(self,
		locals={},
		primary_prompt="--> ",
		secondary_prompt = "... ",
		indent_str = "\t",
		exit = 0,
		debug = 0,
		subshell = "",
		logfile = None
		):
		self.locals = locals
		self.primary_prompt = primary_prompt
		self.secondary_prompt = secondary_prompt
		self.indent_str = indent_str
		self.exit = exit
		self.debug = debug
		if subshell:
			self.subshell = subshell
		else:
			if os.name == "posix":
				self.subshell = "/bin/sh"
			else:
				self.subshell = "cmd.exe"
		self.logfile = logfile
		exec "import os" in self.locals
		self.reset()

	def reset(self):

		self.ulines = []
		self.system_continuation = 0
		self.python_continuation = 0
		self.parse_stack = []
		monty.block_mode = "indent"
		monty.linenum = 0
		monty.delimit_stack = []

	def escape_string(self, line):
	
		"""Since strings meant for shell level execution must be imbedded in
a Python os.system() function as an argument. Since there is a string
constructed that includes the user supplied text, it is necessary to
convert all backslashes and quote characters into escaped versions so
that they do not get screwed up in the constructed string which will
be interpreted by python as a python string"""

		tline = string.replace(line,'\\','\\\\')
		tline = string.replace(tline,"'","\\'")
		return string.replace(tline,'"','\\"')

	def logging(self, argstring):
	
		"""Open (or close) logfile and set flag."""
	
		# and better definition of option syntax
		
		args = string.split(argstring)
		if len(args) == 0:	# turn off logging (if on)
			if self.logfile:
				self.logfile.close()
				self.logfile = None
			else:
				print	"No log file currently open."
		else:
			if len(args) > 1:
				option = args[1]
				if string.strip(option) == 'append':
					if self.logfile:
						self.logfile.close()
					try:
				 		self.logfile = open(args[0],'a')
				 	except:
				 		print "error: problem opening logfile"
			else:
				if self.logfile:
					self.logfile.close()
				try:
					self.logfile = open(args[0],'w')
					self.logfile.write("import os\n")
				except:
					print "error: problem opening or writing to logfile"
		return "start over"

	def showtraceback(self):
	
		"""Emulate python interpreter traceback display"""
		if sys.exc_type == SyntaxError and \
				sys.exc_value[0] == "invalid syntax":
			# emulate interpreter behaviour
			print "  File \"%s\", line %d" % \
				("<stdin>",sys.exc_value[1][1])
			print "    "+sys.exc_value[1][3],
			print " " * (sys.exc_value[1][2] + 3) + "^"
			print str(sys.exc_type) + ":", sys.exc_value[0]
		else:
			traceback.print_tb(sys.exc_traceback, None)
			print str(sys.exc_type) + ":", sys.exc_value
	
	def parse_line(self, line):

		"""Top level line parsing routine"""
	
		monty.linenum = len(self.ulines)
		sline = string.lstrip(line)
		if not self.python_continuation:
			# special commands can only start on first line
			status = self.parse_special_cmds(sline)
			if status != "parse python":
				return status 
		# not special command, treat as python, begin parsing
		# must try to parse first line in brace mode; if not consistent 
		# with brace mode then parse in indent mode
		if monty.linenum == 0:
			status = self.parse_python_line_brace(line)
			if monty.block_mode == "indent":
			# ok, redo and parse instead in indent mode
				self.reset()
			else:
				return status
		# This reached only if not first line and brace mode		
		# handle indent mode
		if monty.block_mode == "indent":
			if (len(line) == 0):
				return ("execute",)
			else:
				return self.parse_python_line_indent(line)
		# handle brace mode
		else:
				return self.parse_python_line_brace(line)

	def parse_special_cmds(self, line):
	
		"""Handles system command escapes and "executive" commands"""
		
		if not self.system_continuation:
			sline = string.lstrip(line)
			if len(sline) == 0:
				return ("execute",) 	# but nothing to execute!
			# subshell command? (!!)
			if sline[0:2] == '!!':
				## log command? Not for now
				status = os.system(self.subshell)
				self.reset()
				return "start over"
			# executive command?
			elif sline[0] == '.':
				if sline == '.exit':
					self.exit = 1
					return "exit"
				elif string.find(sline,'.logfile') == 0:
					return self.logging(sline[len('.logfile'):])
				elif string.find(sline,'.debug') == 0:
					if self.debug == 0:
						self.debug = 1
					else:
						self.debug = 0
					return "start over"
				else:
					print "****** Unknown executive command!"
					return "error"
				## add others here
			# system command? (!...)
			elif sline[0] == '!':
				# continued to next line?
				if sline[-3:] == "...":
					self.system_continuation = 1
					tline = self.escape_string(line[1:-3]) # escape \"'
					self.ulines.append('status=os.system("'+tline)
					return ("incomplete",)
				else:
					tline = self.escape_string(line[1:])	# escape \"'
					self.ulines.append('status=os.system("'+tline+'")')
					return ("execute",)			
			else: # apparently not a special command
				return "parse python"
		else: # handle system continuations here
			if line[-3:] == "...":
				tline = self.escape_string(line[:-3])
				self.ulines[0] = self.ulines[0]+tline
				return ("incomplete",)
			else:
				tline = self.escape_string(line[:])
				self.ulines[0] = self.ulines[0]+tline+'")'
				return ("execute",)
				
	def parse_python_line_indent(self, line):
	
		"""Parse line accepting only standard python syntax"""
	
		parse_stack = self.parse_stack
		posnext = 0
		if (monty.linenum == 0):
			# if start, push base pair group object to kick things off
			next = no_group(0)
			parse_stack.append(next)
		else:
			# otherwise, continue execution on what is already on the stack
			next = parse_stack[-1]
		while 1: # until the line is completely parsed
			tp = next.gcontinue(line,posnext)
			if (tp[0] == "pop")  and (len(parse_stack) > 1): 
				del parse_stack[-1]
				next = parse_stack[-1]
				posnext = tp[1]
			elif tp[0] == "push":
			# new group encountered, push and execute
				next = tp[1]
				parse_stack.append(next)
				posnext = tp[2]
			elif tp[0] == "incomplete": 
			# expect more, need to get more lines
				self.python_continuation = 1
				self.ulines.append(line)
				return tp
			elif tp[0] == "complete":
			# if no indentation used for line, or complete first line, execute
				self.ulines.append(line)
				if (((line[0] != "\t") and (line[0] !=" ")) or 
					len(self.ulines) == 1):
					return ("execute",)
				else:
					return ("incomplete",)
			elif tp[0] == "error":
				self.reset()
				return tp
			else:
				print "tp = ", tp
				print "whoops, appears to be a Monty bug!"
				return ("",)
	
	def parse_python_line_brace(self, line):

		"""Parse line using brace block mode, first line must contain the start
	of a block using braces, either at the very beginning, or after a block
	statement"""
	
	# possible return values: execute, incomplete, error and ""
		parse_stack = self.parse_stack
		delimit_stack = monty.delimit_stack
		posnext = 0
		if monty.linenum == 0:
			# if first call, push base pair group object on parse stack
			next = block_group(0)
			parse_stack.append(next)
		else:
			# else continue execution with object already on stack
			next = parse_stack[-1]
		while 1:  # until the line is completely parsed
			tp = next.gcontinue(line,posnext)
			if tp[0] == "pop":
				del parse_stack[-1]
				# stack should never, ever be empty, nor should the first
				# object ever be popped
				if len(parse_stack) > 0:
					next = parse_stack[-1]
					posnext = tp[1]
				else:
					return ("error","Syntax Error: unexpected '}'")
			elif tp[0] == "push":
				# new group encountered, push and execute
				next = tp[1]
				parse_stack.append(next)
				posnext = tp[2]
			elif tp[0] == "incomplete":
				# expecting more, need more input lines
				self.python_continuation = 1
				self.ulines.append(line)
				return tp
			elif tp[0] == "error":
				self.reset()
				return tp
			elif tp[0] == "indent":
				# no braces found on first line, change to indent mode
				return ("",)
			elif tp[0] == "eol":
				# end of line encountered, execute if no pending groups on stack
				self.ulines.append(line)
				if len(parse_stack) == 1:
					return ("execute",)
				else:
					self.python_continuation = 1
					return ("incomplete",)
			else:
				print "tp = ", tp
				print "whoops, appears to be a Monty bug!"
				self.reset()
				return ("",)
			
	def start(self, banner="Monty command-line wrapper"):
	
		"""Start the front end interpreter"""
	
		print banner
		currentPrompt = self.primary_prompt
		while not self.exit:
			try:
				# get line from user and parse
				line = raw_input(currentPrompt)
				status = self.parse_line(line)
				if status[0] == "execute":
					self.execute()
					self.reset()
					currentPrompt = self.primary_prompt
				elif self.python_continuation or self.system_continuation:
					if self.python_continuation:
						currentPrompt = self.secondary_prompt
					else: # may differ in future versions
						currentPrompt = self.secondary_prompt
				elif status[0] == "error":
					print status[1]
					currentPrompt = self.primary_prompt
				else: # start over
					self.reset()
					currentPrompt = self.primary_prompt
			except KeyboardInterrupt: 
				print "<KeyboardInterrupt>"
				self.reset()
				currentPrompt = self.primary_prompt
			except:
				print sys.exc_type
				self.reset()
				currentPrompt = self.primary_prompt
		print "\n quitting Monty"
		if self.logfile:
			self.logfile.close()
		self.exit = 0
		sys.exit()
	
	def execute(self):
	
		"""try executing the assembled input line(s)"""
	
		if monty.block_mode == "brace":
			# translate the block delimiters into appropriately indented 
			# python lines (and split at semicolons)
			pylines = self.split_lines()
		else:
			pylines = self.ulines
		# construct code string from line stack
		source = string.join(pylines, "\n") + "\n"
		if self.debug:
			print source
		try:
			if len(pylines) == 1:
				kind = "single"
			else:
				kind = "exec"
			code = compile(source, "monty", kind)
#		except SyntaxError, why:
#			print "Syntax Error:", why
#			return
		except:
			self.showtraceback()
			return
		else:
			# execute
			if self.logfile:
				try:
					self.logfile.write(source)
					self.logfile.flush()
				except:
					print "error: problem writing to logfile"
			try:
				exec code in self.locals
			except:
				self.showtraceback()

	def split_lines(self):
	
		"""Translate brace mode block delimiters '{' & '}' into indented python
	lines & split lines at semicolons"""
	
	# split up lines and create new line list without block braces or semicolons
	# Current drawback of this setup is that continued triple quote lines will
	#  have tabs added to the continuation line (bug!)
	# Returns the translated list of lines.
	
		lines = []	# set of translated lines
		ndelim = 0
		indent = 0
		dstack = monty.delimit_stack
		dtpl = dstack[ndelim]
		# loop through delimiter list, split lines and apply appropriate
		# indentation. New set 
		for nline in range(len(self.ulines)):
			line = self.ulines[nline]
			if dtpl[2] > nline:
				# line has no delimiters, 
				# move to output with appropriate indentation
				lines.append(self.indent_str*indent + string.lstrip(line))
			else:
				pos = 0 # used to account for amount of current line already
							# extracted
				while dtpl[2] == nline:
					if dtpl[1]-pos > 0:
						# if nonzero in size, extract and output string before
						# delimiter
						lines.append(self.indent_str*indent + \
							string.lstrip(line[:dtpl[1]-pos]))
					line = line[dtpl[1]-pos+1:]
					pos = dtpl[1]+1
					# if a brace is involved, change indent level
					if ((dtpl[0] == "openbrace") and 
						not ((dtpl[1] == 0) and(dtpl[2] == 0))):
						indent = indent + 1
					elif dtpl[0] == "closebrace":
						indent = indent - 1
						if indent < 0: indent = 0
					# get next delimiter
					ndelim = ndelim + 1
					if ndelim < len(dstack):
						dtpl = dstack[ndelim]
					else:
						dtpl = (None, None, 9999)
				if len(line) > 0:
					# output rest of line
					lines.append(self.indent_str*indent + string.lstrip(line))
		return lines				
					
#----------------------------------------------------------------------			

# the general set of pair group classes
		
class pgroup:

	"""Abstract class"""

	def __init__(self, pos):
	
		self.group_type = None
		self.pos_start = pos
		self.terminating_str = None
		self.search_set = ["#",'"',"'",'"""',"'''","{","[","("]
		self.terminating_set = ["}","]",")"]
		
	def __str__(self):
	
		return self.group_type
		
	def __repr__(self):
	
		return repr(self.group_type)
		
	def gcontinue(self, line, pos):

		"""Method that looks for either the termination of the group the
		object represents or the beginning of a new one"""

		start = pos
		if self.terminating_str:
			# none expected for comments for example
			str_search_set = self.search_set + [self.terminating_str]
		else:
			str_search_set = self.search_set
		posnext, fstring = find_next_in_set(line, start, str_search_set)
		posnext_gterm, fstring_gterm = find_next_in_set(line, start,
			self.terminating_set)
		if (((posnext_gterm <= posnext) or (posnext == -1)) and 
			(fstring_gterm != self.terminating_str) and
			(posnext_gterm >= 0)):
			# found unmatched terminator
			return "error", "Syntax Error: found '"+fstring_gterm+ \
						"' before '"+self.terminating_str+"'"
		if (posnext < 0) or (fstring == "#"):
			# line end found before group termination, group is incomplete
			return "incomplete", -1
		elif fstring == self.terminating_str:
			# end of group found
			return "pop", posnext+len(self.terminating_str)
		else:
			# new group start found
			return "push",makenext(posnext,fstring), posnext+len(fstring)
		
class brace_group(pgroup):

	def __init__(self, pos):
	
		pgroup.__init__(self, pos)
		self.group_type = "brace"
		self.terminating_str = "}"
	
class bracket_group(pgroup):

	def __init__(self, pos):
	
		pgroup.__init__(self, pos)
		self.group_type = "bracket"
		self.terminating_str = "]"
		
class paren_group(pgroup):

	def __init__(self, pos):
	
		pgroup.__init__(self, pos)
		self.group_type = "paren"
		self.terminating_str = ")"
		
class string_group(pgroup):

	def __init__(self, pos, string_delimiter):
	
		pgroup.__init__(self, pos)
		self.group_type = "string"
		self.terminating_str = string_delimiter
		self.search_set = ["\\"] # nothing trumps the string!
		
	def gcontinue(self, line, pos):
	
		start = pos
		while 1:
			posnext, fstring = find_next_in_set(line, start,
				self.search_set + [self.terminating_str])
			if fstring == "\\":	   # backslash char sets come in pairs regardless
				start = posnext + 2  # of what the manual says, raw mode or not.
			elif (posnext < 0):
				if	((self.terminating_str == '"""') or
					(self.terminating_str == "'''")):
					return "incomplete", -1
				else:
					return "error", "Syntax Error: incomplete string"
			elif fstring == self.terminating_str:
				return "pop", posnext+len(self.terminating_str)
			else:
				return "error", "string parser is confused (bug?)"

class no_group(pgroup):

# used as the base group for indent mode, will never be found inside
# any other group

	def __init__(self, pos):
	
		pgroup.__init__(self, pos)
		self.group_type = "no group"
		
	def gcontinue(self, line, pos):

		# look for the next statement, end of line, or end of a block
		posnext, fstring = find_next_in_set(line, pos,
			self.search_set+["\\"])
		if (posnext < 0) or (fstring == "#"):
			# for the first line there is no avoiding trying to
			# compile to see if it is complete (for block statements)
			if monty.linenum == 0:
				try:
					code = compile(line, "monty", "single")
				except SyntaxError, why:
					if why[0] == "unexpected EOF while parsing":
						return ("incomplete",)
					else:
						return("complete",)
				else:
					return ("complete",)
			else:
				return ("complete",)
		elif (fstring == "\\"):
			# end of line, done 
			return ("incomplete",)
		else:
			# return found group to be pushed and executed	
			return "push", makenext(posnext+len(fstring), fstring), \
				posnext+len(fstring)
			
class block_group(pgroup):

# Not a pair group in the usual sense but involves brace pairs
# in a much more complex construct, thus the more complicated
# gcontinue routine. It must recognize all python block mode
# statements so that block mode braces may be identified in
# the correct context.

	re_class = r"^\s*class\s"
	re_def = r"^\s*def\s"
	re_for = r"^\s*for[\s\(]"
	re_if = r"^\s*if[\s\-+\({[]"
	re_elif = r"^\s*elif[\s\-+\({[]"
	re_else = r"^\s*else[\s:]"
	re_while = r"^\s*while[\s\-+\({[]"
	re_except = r"^\s*except[\s:]"
	re_try = r"^\s*try[\s:]"
	re_finally = r"^\s*finally[\s:]"
	re_lambda = r"\s*lambda[\s:]"
	re_brace = re.compile(r"\s*{")
	re_or = ")|("
	re_block = re.compile("(" +re_class + re_or + re_def + re_or +
			re_for + re_or + re_if + re_or + re_elif + re_or + re_else +
			re_or + re_while + re_or + re_except + re_or + re_try + re_or +
			re_finally + ")")

	def __init__(self, pos):
	
		pgroup.__init__(self, pos)
		self.group_type = "block"
		self.state = "begin"	# possible states: begin, block_statement_start
									#    colon, closeblock, nonblock, closeblock
	def gcontinue(self, line, pos):
	
		# A big, ugly parsing routine. It cycles through several states until
		# it detects the end of a block. Part of the complication is due to
		# having to determine if the first line is in brace mode (if it is,
		# a different routine is used to parse indented input.)
		
		# Conceivably this should be implemented using standard techniques for
		# representing a state machine with OO methods. If it were only a
		# little more complicated, I would have.
		
		start = pos
		linenum = monty.linenum
		if (pos == 0) and (linenum == 0): 
			#  first time called?
			mo = self.re_brace.match(line)
			if mo:
				monty.block_mode = "brace"
				start = mo.end()
				self.state = "closeblock"
				monty.delimit_stack.append(("openbrace",start-1,linenum))
				return "push", makenext(start,"block"), start
		while 1: # until finished with the line
			if self.state == "begin":
				# search for block structure starting elements (or groups) if any
				mo = self.re_block.match(line[start:])
				if mo:
					# beginning of a block statement detected
					self.state = "block_statement_start"
					start = start + mo.end()-1  # position at character after word
				else:
					self.state = "nonblock"
			elif self.state == "nonblock":
				# look for the next statement, end of line, or end of a block
				posnext, fstring = find_next_in_set(line, start,
					self.search_set+[";","\\","}"])
				if (posnext < 0) or (fstring == "#"):
					# end of line, done 
					if monty.block_mode == "indent":
						return ("indent",)
					else:
						return ("eol",)
				elif fstring == "\\":
					# explicit line continuation
					return ("incomplete",)
				elif fstring == ";":
					# start of new statement, start again to look for block statement
					self.state = "begin"
					start = posnext+1
					monty.delimit_stack.append(("semicolon",posnext,linenum))
				elif fstring == "}":
					# end of a block
					monty.delimit_stack.append(("closebrace",posnext,linenum))
					return "pop",posnext+1
				else:
					# return found group to be pushed and executed	
					return "push", makenext(posnext+len(fstring), fstring), \
						posnext+len(fstring)
			elif self.state == "block_statement_start":
				# look for the expected colon
				posnext, fstring = find_next_in_set(line, start,
					self.search_set+[":","\\"])
				if (posnext < 0) or (fstring == "#") or (fstring == "\\"):
					# end of line, done
					return ("incomplete",)
				elif fstring == ":":
					self.state = "colon"
					start = posnext+1
				else:
					# return found group to be pushed and executed	
					return "push", makenext(posnext+len(fstring), fstring),  \
							posnext+len(fstring)
			elif self.state == "colon":
				# look for brace
				mo = self.re_brace.match(line[start:])
				if mo:
					if monty.block_mode == "indent":
						monty.block_mode = "brace"
					start = start + mo.end()
					self.state = "closeblock"
					monty.delimit_stack.append(("openbrace",start-1,linenum))
					return "push", makenext(start,"block"), start
				else:
					# not brace mode if none found on first line
					if (linenum == 0) and (monty.block_mode == "indent"):
						return ("indent",)			
					else:
						# if none, any non-comment non-whitespace characters left?
						posnext = string.find(line[start:],"#")
						tline = line[start:]
						if posnext >= 0:
							tline = tline[:posnext]
						else:
							tline = line[start:]
						if len(string.strip(tline)) != 0:
							return ("error","Syntax Error: Brace mode requires braces"+
								" where\n blocks of statements may appear")
						else:
							return ("incomplete",)
			elif self.state == "closeblock":
				# four cases to consider at the close of a block
				tline = string.strip(line[start:])
				if len(tline) == 0:
					# end of line
					return ("eol",)
				if tline[0] == ";":
					# start of new statement, start over
					self.state = "begin"
					monty.delimit_stack.append(("semicolon",start,linenum))
					start = string.find(line,";",start) + 1
				elif tline[0] == "#":
					# end of line
					return ("eol",)
				elif tline[0] == "\\": 
					# explicit line continuation
					return ("incomplete",)
				elif tline[0] == "}":
					# another block close
					start = string.find(line,"}",start) + 1
					monty.delimit_stack.append(("closebrace",start-1,linenum))
					return ("pop", start)
				else:
					return ("error","Syntax Error: brace blocks must be" +
						" followed by either ';' or '}'")
						
if __name__ == "__main__":
 
	#
	# start up monty
	#

	print 'Monty, Python front end (copyright AURA 1998)'
	print 'Python: ' + sys.copyright

	m = monty().start()
