"""module 'tpar.py' -- main module for generating the tpar task editor

tpar is curses based parameter editing similar to epar.  Tpar has the
primary goal of simplicity similar to IRAF's CL epar and as such is
missing many PyRAF epar features.  The primary advantage of tpar is
that it works in a simple terminal window (rather than requiring full
X-11 and Tk);  this is an improvement for low bandwidth network contexts
or for people who prefer text interfaces to GUIs.

$Id: $

Todd Miller, 2006 May 30  derived from epar.py and IRAF CL epar.

"""
import os, sys, string, commands, re

import urwid.curses_display
import urwid

# PyRAF modules
import iraf, irafpar, irafhelp, cStringIO, wutil, iraffunctions
from irafglobals import pyrafDir, userWorkingHome, IrafError
		
TPAR_HELP = """
                                EDIT COMMANDS (emacs)

           DEL_CHAR   = DEL                    MOVE_RIGHT = RIGHT_ARROW
           DEL_LEFT   = ^H_or_BS               MOVE_RIGHT = ^F
           DEL_LINE   = ^K                     MOVE_START = ESC-<
           DEL_WORD   = ESC-D                  MOVE_UP    = UP_ARROW
           DEL_WORD   = ESC-d                  MOVE_UP    = ^P
           EXIT_NOUPD = ^C                     NEXT_PAGE  = ^V
           EXIT_UPDAT = ^D                     NEXT_WORD  = ESC-F
                                               NEXT_WORD  = ESC-f
           GET_HELP   = ESC-?                  PREV_PAGE  = ESC-V
           MOVE_BOL   = ^A                     PREV_PAGE  = ESC-v
           MOVE_DOWN  = DOWN_ARROW             PREV_WORD  = ESC-B
           MOVE_DOWN  = ^N                     PREV_WORD  = ESC-b
           MOVE_END   = ESC->                  REPAINT    = ^L
           MOVE_EOL   = ^E                     UNDEL_CHAR = ESC-^D
           MOVE_LEFT  = LEFT_ARROW             UNDEL_LINE = ESC-^K
           MOVE_LEFT  = ^B                     UNDEL_WORD = ESC-^W

           :e[!] [pset]         edit pset      "!" == no update
           :q[!]                exit tpar      "!" == no update
           :r! [pset]           unlearn or load from pset
           :w[!] [pset]         unsupported
           :g[!]                run task 
"""

class Binder(object):
	"""The Binder class manages keypresses for urwid and adds the
	ability to bind specific inputs to actions.
	"""
	def __init__(self, bindings, debug, mode_keys=[]):
		self.bindings = bindings
		self.debug = debug
		self.mode_keys = mode_keys
		self.chord = []

	def bind(self, k, f):
		self.bindings[k] = f
	
	def keypress(self, pos, key):
		if key is None:
			return
		self.debug("pos: %s    key: %s" % (pos, key))
		if key in self.mode_keys:
			self.chord.append(key)
			return None
		elif not urwid.is_mouse_event(key):
			key = " ".join(self.chord + [key])
			self.chord = []
		if self.bindings.has_key(key):
			oldkey = key
			f = self.bindings[key]
			if f is None:
				key = None
			elif isinstance(f, str):
				key = f
			else:
				key = f()
			self.debug("pos: %s  chord: %s  oldkey: %s  key: %s mapping: %s" % (pos, self.chord, oldkey, key, f))
		return key

class PyrafEdit(urwid.Edit, Binder):
	"""PyrafEdit is a text entry widget which has keybindings similar
	to IRAF's CL epar command.
	"""
	def __init__(self, *args, **keys):
		debug = keys["debug"]
		del keys["debug"]
		self._del_words = []
		self._del_lines = []
		self._del_chars = []
		urwid.Edit.__init__(self, *args, **keys)
		EDIT_BINDINGS  = {  # single field bindings

			"delete" : self.DEL_CHAR,			
			
			"ctrl k": self.DEL_LINE,
			"ctrl K": self.DEL_LINE,
			
			"esc d": self.DEL_WORD,
			"esc D": self.DEL_WORD,
			
			"esc f": self.NEXT_WORD,
			"esc F": self.NEXT_WORD,
			
			"esc b": self.PREV_WORD,
			"esc B": self.PREV_WORD,
			
			"ctrl a": self.MOVE_BOL,
			"ctrl A": self.MOVE_BOL,
			
			"ctrl e": self.MOVE_EOL,
			"ctrl E": self.MOVE_EOL,
			
			"esc >": self.MOVE_END,
			"esc <": self.MOVE_START,
			
			"ctrl f": self.MOVE_RIGHT,
			"ctrl F": self.MOVE_RIGHT,
			
			"ctrl b": self.MOVE_LEFT,
			"ctrl B": self.MOVE_LEFT,
			
			"esc ctrl d": self.UNDEL_CHAR,
			"esc ctrl k": self.UNDEL_LINE,
			"esc ctrl w": self.UNDEL_WORD,
			
			"ctrl p": self.MOVE_UP, # Can't explain these...
			"ctrl P": self.MOVE_UP,
			"shift tab": self.MOVE_UP,
			
			"ctrl n": self.MOVE_DOWN,
			"ctrl N": self.MOVE_DOWN,
			"tab": self.MOVE_DOWN,
			"enter": self.MOVE_DOWN,
			
			"esc ?": "help"
		}
		Binder.__init__(self, EDIT_BINDINGS, debug)

	def DEL_CHAR(self):
		s = self.get_edit_text()
		if len(s):
			n = self.edit_pos
			if n >= len(s):
				n -= 1
			c = s[n]
			self.set_edit_text(s[:n] + s[n+1:])
			self._del_chars += [c]
			
	def DEL_LINE(self):
		s = self.get_edit_text()
		line = s[self.edit_pos:]
		self.set_edit_text(s[:self.edit_pos])
		self._del_lines += [line]

	def DEL_WORD(self):
		s = self.get_edit_text()
		i = self.edit_pos
		while i > 0 and not s[i].isspace():
			i -= 1
		if s[i].isspace():
			i += 1
		word = ""
		while i < len(s) and not s[i].isspace():
			word += s[i]
			i += 1			
		s = s[:i-len(word)] + s[i:]
		self._del_words += [word]
		self.edit_pos = i
		self.set_edit_text(s)

	def NEXT_WORD(self):
		s = self.get_edit_text()
		i = self.edit_pos
		while s and i < len(s)-1 and not s[i].isspace():
			i += 1		
		while s and i < len(s)-1 and s[i].isspace():
			i += 1
		self.edit_pos = i
		
	def PREV_WORD(self):
		s = self.get_edit_text()
		i = self.edit_pos
		while s and i > 0 and s[i].isspace():
			i -= 1
		while s and i > 0 and not s[i].isspace():
			i -= 1		
		self.edit_pos = i

	def MOVE_BOL(self):
		self.edit_pos = 0

	def MOVE_START(self):
		self.MOVE_BOL()
		
	def MOVE_EOL(self):
		self.edit_pos = len(self.get_edit_text())

	def MOVE_END(self):
		self.MOVE_EOL()

	def MOVE_RIGHT(self):
		if self.edit_pos < len(self.get_edit_text()):
			self.edit_pos += 1

	def MOVE_LEFT(self):
		if self.edit_pos > 0:
			self.edit_pos -= 1

	def MOVE_UP(self):
		if self.verify():
			return "up"

	def MOVE_DOWN(self):
		if self.verify():
			return "down"
	
	def UNDEL_CHAR(self):
		try:
			char = self._del_chars.pop()
		except:
			return
		self.insert_text(char)
		self.edit_pos -= 1

	def UNDEL_WORD(self):
		try:
			word = self._del_words.pop()
		except:
			return
		self.insert_text(word)

	def UNDEL_LINE(self):
		try:
			line = self._del_lines.pop()
		except:
			return
		self.insert_text(line)

	def keypress(self, pos, key):
		key = Binder.keypress(self, pos, key)
		if key is not None:
			key = urwid.Edit.keypress(self, pos, key)
		# self.verify()
		return key
		
	def get_result(self):
		return self.get_edit_text().strip()

	def verify(self):
		return True

class StringTparOption(urwid.Columns):
	def __init__(self, paramInfo, defaultParamInfo, debug):

		self.debug = debug
		self.paramInfo    = paramInfo
		self.defaultParamInfo = defaultParamInfo
		
		name  = self.paramInfo.name
		value = self.paramInfo.get(field = "p_filename", native = 0,
						prompt = 0)
		self._previousValue = value

		# Generate the input label
		if (self.paramInfo.get(field = "p_mode") == "h"):
			required=False
		else:
			required=True

		help = self.paramInfo.get(field = "p_prompt", native = 0, prompt = 0)
		self._args = (name, value, help, required)
		if not required:
			name = "(" + name
			help = ") " + help
		else:
			help = "  " + help
		self._name = "%-10s=" % name
		self._value = "%10s" % value
		self._help = "%-30s" % help
		n = urwid.Text(self._name)
		e = PyrafEdit("", self._value, wrap="clip", align="right", debug=debug)
		e.verify = self.verify
		h = urwid.Text(self._help)
		self.cols = (n,e,h)
		urwid.Columns.__init__( self, [('weight',0.25, n),
					       ('weight',0.25, e),
					       ('weight',0.50, h)],
					0, 1, 1)		
	def get_name(self):
		return self._args[0]

	def get_result(self):
		return self.cols[1].get_edit_text().strip()

	def set_result(self, r):
		self.cols[1].set_edit_text( str(r) ) 

	def unlearn_value(self):
		self.set_result(self._previousValue)
		
	def alert(self, s):
		self.debug(s)

	def verify(self):
		return True

	def get_edit(self):
		return self.cols[1]

class NumberTparOption(StringTparOption):
	def verify(self):
		try:
			f = float(self.get_result())
			return True
		except:
			self.alert("Not a valid floating point number.")
			return False

class BooleanTparOption(StringTparOption):
	def __init__(self, *args, **keys):
		StringTparOption.__init__(self, *args, **keys)
		e = self.get_edit()

	def normalize(self):
		if self.get_result() in ["n","N"]:
			self.set_result("no")
		elif self.get_result() in ["y","Y"]:
			self.set_result("yes")

	def verify(self):
		self.normalize()
		return self.get_result() in ["yes","no"]		

class EnumTparOption(StringTparOption):
	pass

class PsetTparOption(StringTparOption):
	pass

class TparHeader(urwid.AttrWrap):
        banner = """                                   I R A F
                    Image Reduction and Analysis Facility

"""

	def __init__(self, package, task=None):
		s = self.banner
		s += "%8s= %-10s\n" %  ("PACKAGE", package)
		if task is not None:
			s += "%8s= %-10s" % ("TASK", task)
		urwid.AttrWrap.__init__(self, urwid.Text(s), "header")


class TparDisplay(Binder):
        palette = [
                ('body','default','default', 'standout'),
		('header', 'default', 'default', ('standout', 'underline')),
                ('help','black','light gray'),
                ('reverse','light gray','black'),
                ('important','dark blue','light gray',('standout','underline')),
                ('editfc','white', 'dark blue', 'bold'),
                ('editbx','light gray', 'dark blue'),
                ('editcp','black','light gray', 'standout'),
                ('bright','dark gray','light gray', ('bold','standout')),
                ('buttn','black','dark cyan'),
                ('buttnf','white','dark blue','bold'),
                ]

	MODE_KEYS = [ "esc"] 

	def __init__(self,  taskName):		
		TPAR_BINDINGS = {  # Page level bindings
			"ctrl c" : self.quit,
			"ctrl d" : self.exit,
			"ctrl z" : self.exit,   # probably intercepted by unix shell
			"ctrl Z" : self.exit,
			"esc v"  : "page down",
			"esc V"  : "page down",
			"esc p"  : "page up",
			"esc P"  : "page up",
			"esc ?"  : self.help,
			"ctrl l" : None,        # re-draw... just ignore
			"ctrl L" : None
			}

		# Get the Iraftask object
		if isinstance(taskName, irafpar.IrafParList):
			# IrafParList acts as an IrafTask for our purposes
			self.taskObject = taskName
		else:
			# taskName must be a string or an IrafTask object
			self.taskObject = iraf.getTask(taskName)

		# Now go back and ensure we have the full taskname
		self.taskName = self.taskObject.getName()
		self.pkgName = self.taskObject.getPkgname()
		self.paramList = self.taskObject.getParList(docopy=1)
		
		# Ignore the last parameter which is $nargs
		self.numParams = len(self.paramList) - 1
		
		# Get default parameter values for unlearn
		self.get_default_param_list()
		self.make_entries()

		self.escape = False

		bwidth = ('fixed', 14)
		
		self.help_button = urwid.Padding(
			urwid.Button("Help",self.help),
			align="center",	width=('fixed', 8))
		self.cancel_button = urwid.Padding(
			urwid.Button("Cancel",self.quit),
			align="center",	width=('fixed', 10))
		self.save_button = urwid.Padding(
			urwid.Button("Save",self.exit),
			align="center",	width=('fixed', 8))
		self.exec_button = urwid.Padding(
			urwid.Button("Exec",self.go),
			align="center",	width=('fixed', 8))
		
		self.buttons = urwid.Columns([
			('weight', 0.2, self.exec_button),
			('weight', 0.2, self.save_button),
			('weight', 0.2, self.cancel_button),
			('weight', 0.4, self.help_button)])

		self.colon_edit = PyrafEdit("", "", wrap="clip", align="left", debug=self.debug)
		self.listitems = [urwid.Divider(" ")] + self.entryNo + \
				 [urwid.Divider(" "), self.colon_edit,
				  self.buttons]
		self.listbox = urwid.ListBox( self.listitems )

		self.listbox.set_focus(1)
		self.footer = urwid.Text("")
		self.header = TparHeader(self.pkgName, self.taskName)

		self.view = urwid.Frame(
			self.listbox,
			header=self.header,
			footer=self.footer)
		Binder.__init__(self, TPAR_BINDINGS, self.debug, self.MODE_KEYS)
	def get_default_param_list(self):
		# Obtain the default parameter list
		dlist = self.taskObject.getDefaultParList()
		if len(dlist) != len(self.paramList):
		    # whoops, lengths don't match
		    raise ValueError("Mismatch between default, current par lists"
			" for task %s (try unlearn)" % self.taskName)
		dict = {}
		for par in dlist:
			dict[par.name] = par

		# Build default list sorted into same order as current list
		try:
			dsort = []
			for par in self.paramList:
				dsort.append(dict[par.name])
		except KeyError:
			raise ValueError("Mismatch between default, current par lists"
					 " for task %s (try unlearn)" % self.taskName)
		self.defaultParamList = dsort

	# Method to create the parameter entries
	def make_entries(self):
		# Loop over the parameters to create the entries
		self.entryNo = [None] * self.numParams
		for i in range(self.numParams):
			self.entryNo[i] = self.tpar_option_factory(
				self.paramList[i], self.defaultParamList[i])

	def main(self):
		self.ui = urwid.curses_display.Screen()
		self.ui.register_palette( self.palette )
		self.ui.run_wrapper( self.run )
		self.done()

	def get_keys(self):
		keys = []
		while not keys:
			try:
				keys = self.ui.get_input()
			except KeyboardInterrupt:
				keys = ["ctrl c"]
		return keys
	
	def run(self):
		self.ui.set_mouse_tracking()
		size = self.ui.get_cols_rows()
		self.done = False
		while not self.done:
                        canvas = self.view.render( size, focus=1 )
                        self.ui.draw_screen( size, canvas )
			for k in self.get_keys():
				if k == ":":
					self.colon_escape()
					break
                                elif urwid.is_mouse_event(k):
                                        event, button, col, row = k
                                        self.view.mouse_event(
						size, event,
						button, col, row, focus=True )
                                elif k == 'window resize':
					size = self.ui.get_cols_rows()
				k = self.keypress(size, k)
				if k == "enter":
					widget, pos = self.listbox.get_focus()
					if hasattr(widget,'get_edit_text'):
						widget.set_edit_pos(0)
				self.view.keypress( size, k )
				
	def colon_escape(self):
		w, pos0 = self.listbox.get_focus()
		try:
			default_file = w.get_result()
		except:
			default_file = ""
		self.listbox.set_focus(len(self.listitems)-2)
		size = self.ui.get_cols_rows()
		self.colon_edit.set_edit_text("")
		self.colon_edit.set_edit_pos(0)
		self.view.keypress(size, ":")
		done = False
		while not done:
                        canvas = self.view.render( size, focus=1 )
                        self.ui.draw_screen( size, canvas )
			for k in self.get_keys():
				if urwid.is_mouse_event(k) or \
				       k == "ctrl c" or k == "ctrl g":
					self.colon_edit.set_edit_text("")
					return
                                elif k == 'window resize':
					size = self.ui.get_cols_rows()
				elif k == 'enter':
					done = True
					break
				k = self.keypress(size, k)
				self.view.keypress( size, k )
		cmd = self.colon_edit.get_edit_text()
		self.listbox.set_focus(pos0)
		self.colon_edit.set_edit_text("")
		self.process_colon(cmd)
		
	def process_colon(self, cmd):
		# : <cmd_letter> [!] [<filename>]
		groups = re.match("^:(?P<cmd>[a-z])"
				  "(?P<emph>!?)"
				  "(?P<file>\w*)",  cmd)
		if not groups:
			self.debug("bad command: " + cmd)
		else:
			letter    = groups.group("cmd")
			emph = groups.group("emph") == "!"
			file   = groups.group("file")
			try:
				{ "q" : self.quit,
				  "g" : self.go,
				  "r" : self.read_pset,
				  "w" : self.write_pset,
				  "e" : self.edit_pset
				  }[letter](file, emph)
			except KeyError:
				self.inform("bad command: " + cmd, None)
		
	def save(self, emph):
		# Save all the entries and verify them, keeping track of the
		# invalid entries which have been reset to their original input values
		if emph:
			return
		self.badEntriesList = self.save_entries()

		# If there were invalid entries, prepare the message dialog
		ansOKCANCEL = True
		if (self.badEntriesList):
			ansOKCANCEL = self.process_bad_entries(
				self.badEntriesList,
				self.taskName)
		return ansOKCANCEL

	# For the following routines,  event is either a urwid event *or*
	# a Pset filename

	def quit(self, event=None, emph=True):  # maybe save
		self.save(emph)
		def quit_continue():
			pass
		self.done = quit_continue

	def exit(self, event=None):  # always save
		self.quit(event, False)

	# EXECUTE: save the parameter settings and run the task
	def go(self, event=None, emph=False):
		"""Executes the task."""
		self.save(emph)
		def go_continue():
			print "\nTask %s is running...\n" % self.taskName
			self.run_task()
		self.done = go_continue

	def edit_pset(self, file, emph):
		"""Edits the pset referred to by the specifiefd file or the current field."""
		self.save(emph)
		w, pos0 = self.listbox.get_focus()
		try:
			default_file = w.get_result()
		except:
			default_file = ""
		if file == "":
			iraffunctions.tparam(default_file)
		else:
			def edit_pset_continue():
				self.__init__(file)
			self.done = edit_pset_continue

 	def read_pset(self, file, emph):
		"""Unlearns the current changes *or* reads in the specified file."""
		if file == "":
			self.unlearn_all_entries()
		else:
			def new_pset():
				self.__init__(file)
			self.done = new_pset

 	def write_pset(self, file, overwrite):
		if os.path.exists(file) and not overwrite:
			self.inform("File '%s' exists and overwrite (!) not used." % (file,))
		# XXXX write out parameters to file
 		self.debug("write pset: %s" % (file,))

	# Method to "unlearn" all the parameter entry values in the GUI
	# and set the parameter back to the default value
	def unlearn_all_entries(self):
		for entry in self.entryNo:
			entry.unlearn_value()

	# Read, save, and verify the entries
	def save_entries(self):

		self.badEntries = []

		# Loop over the parameters to obtain the modified information
		for i in range(self.numParams):

		    par = self.paramList[i]
		    entry = self.entryNo[i]
		    # Cannot change an entry if it is a PSET, just skip
		    if par.type == "pset":
			continue

		    value = entry.get_result()

		    # Set new values for changed parameters - a bit tricky,
		    # since changes that weren't followed by a return or
		    # tab have not yet been checked.  If we eventually
		    # use a widget that can check all changes, we will
		    # only need to check the isChanged flag.
		    if par.isChanged() or value != entry._previousValue:
			# Verify the value is valid. If it is invalid,
			# the value will be converted to its original valid value.
			# Maintain a list of the reset values for user notification.
			if not entry.verify():
				self.badEntries.append([
					entry.paramInfo.name, value,
					entry.get_result()])
			else:
				self.taskObject.setParam(par.name, entry.get_result())

		# Save results to the uparm directory
		# Skip the save if the thing being edited is an IrafParList without
		# an associated file (in which case the changes are just being
		# made in memory.)

		taskObject = self.taskObject
		if (not isinstance(taskObject, irafpar.IrafParList)) or \
		  taskObject.getFilename():
		    taskObject.saveParList()

		return self.badEntries

	# Run the task
	def run_task(self):

		# Use the run method of the IrafTask class
		# Set mode='h' so it does not prompt for parameters (like IRAF epar)
		# Also turn on parameter saving
		self.taskObject.run(mode='h', _save=1)

	def get_results(self):
		results = {}
		for i in self.items:
			results[i.get_name()] = i.get_result()
		return results

	def draw_screen(self, size):
		canvas = self.view.render( size, focus=True )
		self.ui.draw_screen( size, canvas )

	def inform(self, s):
		"""output any message to status bar"""
		self.footer.set_text(s)

	def debug(self, s):
		"""output debug message to status bar... eventually disabled for normal users."""
		return self.inform(s)

	def info(self, msg, b):
		self.exit_flag = False
		size = self.ui.get_cols_rows()
		exit_button = urwid.Padding(
			urwid.Button("Exit", self.exit_info),
			align="center",	width=('fixed',8))
		frame = urwid.Frame( urwid.Filler(
			urwid.AttrWrap(urwid.Text(msg), "help"),
			valign="top"),
				     header=self.header,
				     footer=exit_button)
		canvas = frame.render( size )
		self.ui.draw_screen( size, canvas )
		self.get_keys() # wait for keypress
				
	def exit_info(self, ehb):
		self.exit_flag = True

	def help(self, event=None):
		self.info(TPAR_HELP, self.help_button)

	def askokcancel(self, title, msg):
		self.info(msg, None)

	# Process invalid input values and invoke a query dialog
	def process_bad_entries(self, badEntriesList, taskname):

		badEntriesString = "Task " + taskname.upper() + " --\n" \
				   "Invalid values have been entered.\n\n" \
				   "Parameter   Bad Value   Reset Value\n"

		for i in range (len(badEntriesList)):
			badEntriesString = badEntriesString + \
			   "%15s %10s %10s\n" % (badEntriesList[i][0], \
			    badEntriesList[i][1], badEntriesList[i][2])

			badEntriesString + "\nOK to continue using"\
		  " the reset\nvalues or cancel to re-enter\nvalues?\n"

		# Invoke the modal message dialog
		return (self.askokcancel("Notice", badEntriesString))

	# TparOption values for non-string types
	_tparOptionDict = { "b": BooleanTparOption,
			    "r": NumberTparOption,
			    "d": NumberTparOption,
			    "i": NumberTparOption,
			    "pset": PsetTparOption,
			    "ar": NumberTparOption,
			    "ai": NumberTparOption,
			    }

	def tpar_option_factory(self, param, defaultParam):
		"""Return TparOption item of appropriate type for the parameter param"""
		# If there is an enumerated list, regardless of datatype, use
		# the EnumTparOption
		if (param.choice != None):
			tparOption = EnumTparOption
		else:
			# Use String for types not in the dictionary
			tparOption = self._tparOptionDict.get(param.type, StringTparOption)
		return tparOption(param, defaultParam, self.debug)


def tpar(taskName):
	TparDisplay(taskName).main()

if __name__ == "__main__":
	main()

