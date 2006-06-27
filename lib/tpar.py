"""module 'tpar.py' -- main module for generating the tpar task editor

tpar is curses based parameter editing similar to epar.  Tpar has the
primary goal of simplicity similar to IRAF's CL epar and as such is
missing many PyRAF epar features.  The primary advantage of tpar is
that it works in a simple terminal window rather than requiring full
X-11.

$Id: $

Todd Miller, 2006 May 30  derived from tpar.py

   Parameter types:
   string  - Entry widget
   *gcur   - NOT IMPLEMENTED AT THIS TIME
   ukey    - NOT IMPLEMENTED AT THIS TIME
   pset    - Action button
   real    - Entry widget
   int     - Entry widget
   boolean - Radiobutton widget
   array real - NOT IMPLEMENTED AT THIS TIME
   array int  - NOT IMPLEMENTED AT THIS TIME

   Enumerated lists - Menubutton/Menu widget

"""
import os, sys, string, commands

import urwid.curses_display
import urwid

# PyRAF modules
import iraf, irafpar, irafhelp, cStringIO, wutil
from irafglobals import pyrafDir, userWorkingHome, IrafError
		
"""
Feature todos:

2. Optional buttons for PyRAF functions.

3. Validation.

4. Colon commands


Needed curses widgets:

1. Menus: file, option, help

2. Message area for package/task names.

3. Message

4. Text entry

5. Yes / No radio button

6. drop down enumeration selection with hotkeys.

7. Buttons: execute, save, unlearn, cancel, task help

8. Dynamic buttons (PSet refdata)

9. y-scroll bars


Problem: Tk launches a new window for epar and each PSet.  What should
tpar do?


Rescope:  tpar just needs to do what the CL epar could do:


                                   I R A F
                    Image Reduction and Analysis Facility

PACKAGE = synphot
   TASK = calcphot

obsmode =                       Instrument observation mode
spectrum=                       Synthetic spectrum to calculate
form    =              photlam  Form for output data
(func   =              effstim) Function of output data
(vzero  =                     ) List of values for variable zero
(output =                 none) Output table name
(append =                   no) Append to existing table?
(wavetab=                     ) Wavelength table name
(result =                     ) Result of synphot calculation for form
(refdata=                     ) Reference data
(mode   =                    a)

Psets are edited as independent tasks.


Help Screen:
"""

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
	   :r! [pset]           read/merge from pset, always first resetting
	   :w[!] [pset]         write to pset  "!" == no update current
	   :g[o][!]             run task 
	   

           <press any key to exit help>
"""

class Binder(object):
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
	def __init__(self, *args, **keys):
		debug = keys["debug"]
		del keys["debug"]
		urwid.Edit.__init__(self, *args, **keys)
		EDIT_BINDINGS  = {  # single field bindings
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
		
	def DEL_LINE(self):
		s = self.get_edit_text()
		self.set_edit_text(s[:self.edit_pos])

	def DEL_WORD(self):
		s = self.get_edit_text()
		i = self.edit_pos
		while s and not s[i].isspace():
			s = s[:i] + s[i+1:]
			if i > 0:
				i -= 1
		if s and s[i].isspace():
			s = s[:i] + s[i+1:]			
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
	
	def UNDEL_CHAR(self):  # XXXX
		return "undel char"

	def UNDEL_WORD(self):  # XXXX
		return "undel word"

	def UNDEL_LINE(self):  # XXX
		return "undel line"

	def keypress(self, pos, key):
		key = Binder.keypress(self, pos, key)
		if key is not None:
			key = urwid.Edit.keypress(self, pos, key)
		# self.verify()
		return key
		
	def get_result(self):
		return self.get_edit_text().strip()

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
		urwid.Columns.__init__( self, [('weight',0.15, n),
					       ('weight',0.15, e),
					       ('weight',0.30, h)],
					0, 1, 1)		
	def get_name(self):
		return self._args[0]

	def get_result(self):
		return self.cols[1].get_edit_text().strip()

	def set_result(self, r):
		self.cols[1].set_edit_text( r ) 

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
		# e.bind("space", self.toggle_state())
		# e.bind("n", self.set_no())
		# e.bind("N", self.set_no())
		# e.bind("y", self.set_yes())
		# e.bind("Y", self.set_yes())

	def toggle_state(self):
		state = self.get_result()
		if state == "yes":
			self.set_result("no")
		elif state == "no":
			self.set_result("yes")
		else:
			self.set_result("no")

	def set_yes(self):
		self.set_result("yes")

	def set_no(self):
		self.set_result("no")

	def verify(self):
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

	MODE_KEYS = [ "esc", ":" ] 

	def __init__(self,  taskName):
		
		TPAR_BINDINGS = {  # Page level bindings
			": q"    : self.quit,
			": Q"    : self.quit,
			": e"    : self.edit_pset,
			": E"    : self.edit_pset,
			": r"    : self.read_pset,
			": R"    : self.read_pset,
			": w"    : self.write_pset,
			": W"    : self.write_pset,
			": g"    : self.go,
			": G"    : self.go,
			"ctrl c" : self.cancel,
			"ctrl d" : self.quit,
			"ctrl z" : self.quit,   # probably intercepted by unix shell
			"ctrl Z" : self.quit,
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
		self.help_button = urwid.Padding(
			urwid.Button("Help",self.help),
			align="center",	width=('fixed',8))
		self.buttons = urwid.Columns([self.help_button])
		self.listbox = urwid.ListBox(
			[urwid.Divider(" ")] + 
			self.entryNo +
			[urwid.Divider(" ")] + 
			[self.help_button])
		self.listbox.set_focus(1)
		self.footer = urwid.Text("")
		self.header = TparHeader(self.pkgName, self.taskName)
		self.view = urwid.Frame(
			self.listbox,
			header=self.header,
			footer=self.footer)
		Binder.__init__(self, TPAR_BINDINGS, self.debug, self.MODE_KEYS)
		self.main()

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
			keys = self.get_keys()
			for k in keys:
                                if urwid.is_mouse_event(k):
                                        event, button, col, row = k
                                        self.view.mouse_event(
						size, event,
						button, col, row, focus=True )
                                elif k == 'window resize':
					size = self.ui.get_cols_rows()
				k = Binder.keypress(self, size, k)
				widget, pos = self.listbox.get_focus()
				if k == "enter":
					if hasattr(widget,'get_edit_text'):
						widget.set_edit_pos(0)
				self.view.keypress( size, k )

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

	def help(self):
		self.info(TPAR_HELP, self.help_button)

	def asknocancel(self, title, msg):
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


	# QUIT: save the parameter settings and exit epar
	def quit(self, event=None):
		self.debug("quit!")
		self.done = True
		return
		
		# Save all the entries and verify them, keeping track of the
		# invalid entries which have been reset to their original input values
		self.badEntriesList = self.save_entries()

		# If there were invalid entries, prepare the message dialog
		if (self.badEntriesList):
			ansOKCANCEL = self.process_bad_entries(
				self.badEntriesList,
				self.taskName)
			if not ansOKCANCEL:
				return

	# EXECUTE: save the parameter settings and run the task
	def go(self, event=None):
		self.debug("go!")
		self.done = True
		return
		# Now save the parameter values of the parent
		self.badEntriesList = self.save_entries()
		
		# If there were invalid entries in the parent epar dialog, prepare
		# the message dialog
		ansOKCANCEL = FALSE
		if (self.badEntriesList):
			ansOKCANCEL = self.process_bad_entries(
				self.badEntriesList, self.taskName)
			if not ansOKCANCEL:
				return

		print "\nTask %s is running...\n" % self.taskName
		
		self.run_task()

	# ABORT: abort this epar session
	def cancel(self, event=None):
		self.debug("abort!")
		self.done = True
		return

	# UNLEARN: unlearn all the parameters by setting their values
	# back to the system default
	def unlearn(self, event=None):
		# Reset the values of the parameters
		self.unlearn_all_entries()

	def edit_pset(self):
		self.debug("edit pset!")
		return

	def read_pset(self):
		self.debug("read pset!")
		return

	def write_pset(self):
		self.debug("write pset!")
		return

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

			# Update the task parameter (also does the conversion
			# from string)
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
	TparDisplay(taskName)

if __name__ == "__main__":
	main()

