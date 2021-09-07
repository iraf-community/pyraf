"""module 'tpar.py' -- main module for generating the tpar task editor

tpar is curses based parameter editing similar to epar.  Tpar has the
primary goal of simplicity similar to IRAF's CL epar and as such is
missing many PyRAF epar features.  The primary advantage of tpar is
that it works in a simple terminal window (rather than requiring full
X-11 and Tk); this is an improvement for low bandwidth network
contexts or for people who prefer text interfaces to GUIs.

Todd Miller, 2006 May 30  derived from epar.py and IRAF CL epar.
"""


# XXXX Debugging tip:  uncomment self.inform() in the debug() method below

import os
import sys
import re


# Fake out import of urwid if it fails, to keep tpar from bringing down
# all of PyRAF.
class FakeModule:

    def __init__(*args, **keys):
        pass


class FakeClass:

    def __init__(*args, **keys):
        pass


URWID_PRE_9P9 = False

try:
    import urwid.curses_display
    import urwid.raw_display
    import urwid
    from . import urwutil
    from . import urwfiledlg
    urwid.set_encoding("ascii")  # gives better performance than 'utf8'
    if 0 == urwid.__version__.find('0.9.8') or 0 == urwid.__version__.find(
            '0.9.7'):
        URWID_PRE_9P9 = True
except Exception as e:
    urwid = FakeModule()
    urwid.Edit = FakeClass()
    urwid.Columns = FakeClass()
    urwid.AttrWrap = FakeClass()
    urwid.Pile = FakeClass()
    urwid.the_error = str(e)

# PyRAF modules
from . import iraf
from . import irafpar
from . import irafhelp
from . import iraftask
from . import iraffunctions

TPAR_HELP_EMACS = """                                EDIT COMMANDS (emacs)

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

           X-11 Paste:  hold down shift and click middle mouse button

           :e[!] [pset]         edit pset      "!" == no update
           :q[!]                exit tpar      "!" == no update
           :r!                  unlearn
           :w[!] [pset]         unsupported
           :g[!]                run task
"""

TPAR_BINDINGS_EMACS = {
    "ctrl c": "quit",
    "ctrl C": "quit",
    "ctrl d": "exit",
    "ctrl D": "exit",
    "ctrl z": "exit",
    "ctrl Z": "exit",
    "ctrl p": "up",
    "ctrl P": "up",
    "shift tab": "up",
    "ctrl n": "down",
    "ctrl N": "down",
    "esc v": "page down",
    "esc V": "page down",
    "esc p": "page up",
    "esc P": "page up",

    #   "ctrl l" : "redraw",        # re-draw... just ignore
    #   "ctrl L" : "redraw",
    "ctrl K": "del_line",
    "ctrl k": "del_line",
    "esc d": "del_word",
    "esc D": "del_word",
    "esc f": "next_word",
    "esc F": "next_word",
    "esc b": "prev_word",
    "esc B": "prev_word",
    "ctrl a": "move_bol",
    "ctrl A": "move_bol",
    "ctrl e": "move_eol",
    "ctrl E": "move_eol",
    "esc >": "end",
    "esc <": "home",
    "ctrl f": "right",
    "ctrl F": "right",
    "ctrl b": "left",
    "ctrl B": "left",
    "esc ctrl d": "undel_char",
    "esc ctrl k": "undel_line",
    "ctrl y": "undel_line",
    "esc ctrl w": "undel_word",
    "esc ?": "help"
}

TPAR_HELP_VI = """                                EDIT COMMANDS (vi)

           DEL_CHAR   = BACKSPACE              MOVE_LEFT  = ^H
           DEL_LEFT   = DEL                    MOVE_RIGHT = RIGHT_ARROW
           DEL_LINE   = ^I^D                   MOVE_RIGHT = ^L
           DEL_WORD   = ^I^W                   MOVE_START = ^T^S
           EXIT_NOUPD = ^C                     MOVE_UP    = UP_ARROW
           EXIT_UPDAT = ^D                     MOVE_UP    = ^K
           EXIT_UPDAT = ^Z                     NEXT_PAGE  = ^N
           GET_HELP   = ESC-?                  NEXT_WORD  = ^W
           MOVE_BOL   = ^A                     PREV_PAGE  = ^P
           MOVE_DOWN  = DOWN_ARROW             PREV_WORD  = ^B
           MOVE_DOWN  = ^J                     REPAINT    = ^R
           MOVE_END   = ^T^E                   UNDEL_CHAR = ^U^C
           MOVE_EOL   = ^E                     UNDEL_LINE = ^U^L
           MOVE_LEFT  = LEFT_ARROW             UNDEL_WORD = ^U^W

           X-11 Paste:  hold down shift and click middle mouse button

           :e[!] [pset]         edit pset      "!" == no update
           :q[!]                exit tpar      "!" == no update
           :r!                  unlearn
           :w[!] [pset]         unsupported
           :g[!]                run task
"""

TPAR_BINDINGS_VI = {
    "ctrl c": "quit",
    "ctrl d": "exit",
    "ctrl C": "quit",
    "ctrl D": "exit",
    "ctrl K": "up",
    "ctrl k": "up",
    "ctrl j": "down",
    "ctrl J": "down",
    "ctrl n": "page down",
    "ctrl N": "page down",
    "ctrl p": "page up",
    "ctrl P": "page up",

    #   "ctrl r" : "redraw",        # re-draw... just ignore
    #   "ctrl R" : "redraw",
    "tab ctrl D": "del_line",
    "tab ctrl d": "del_line",
    "tab ctrl W": "del_word",
    "tab ctrl w": "del_word",
    "ctrl w": "next_word",
    "ctrl W": "next_word",
    "ctrl b": "prev_word",
    "ctrl B": "prev_word",
    "ctrl a": "move_bol",
    "ctrl A": "move_bol",
    "ctrl e": "move_eol",
    "ctrl E": "move_eol",
    "ctrl T ctrl E": "end",
    "ctrl t ctrl e": "end",
    "ctrl T ctrl S": "home",
    "ctrl t ctrl s": "home",
    "ctrl L": "right",
    "ctrl l": "right",
    "ctrl H": "left",
    "ctrl h": "left",
    "ctrl U ctrl C": "undel_char",
    "ctrl u ctrl c": "undel_char",
    "ctrl U ctrl L": "undel_line",
    "ctrl u ctrl l": "undel_line",
    "ctrl U ctrl W": "undel_word",
    "ctrl u ctrl w": "undel_word",
    "esc ?": "help"
}


class Binder:
    """The Binder class manages keypresses for urwid and adds the
    ability to bind specific inputs to actions.
    """

    def __init__(self, bindings, inform, mode_keys=[]):
        self.bindings = bindings
        self.inform = inform
        self.mode_keys = mode_keys
        self.chord = []

    def bind(self, k, f):
        self.bindings[k] = f

    def keypress(self, pos, key):
        if key is None:
            return
        # Handle the "ready" binding specially to keep the rest simple.
        if key == "ready":
            if "ready" in self.bindings:
                return self.bindings["ready"]()
            else:
                return "ready"
        self.debug(f"pos: {pos}    key: {key}")
        if key in self.mode_keys:
            self.chord.append(key)
            return None
        elif not urwid.is_mouse_event(key):
            key = " ".join(self.chord + [key])
            self.chord = []
        visited = []
        while key in self.bindings and key not in visited:
            visited.append(key)
            f = self.bindings[key]
            if f is None:
                key = None
            elif isinstance(f, str):  # str & unicode?
                key = f
            else:
                key = f()
            self.debug(f"pos: {pos}  visited: {' --> '.join(visited)}  "
                       f"key: {key} mapping: {f}")
        return key

    def debug(self, s):
        # return self.inform(s)
        return None


class PyrafEdit(urwid.Edit):
    """PyrafEdit is a text entry widget which has keybindings similar
    to IRAF's CL epar command.
    """

    def __init__(self, *args, **keys):
        inform = keys["inform"]
        del keys["inform"]
        self.reset_del_buffers()
        urwid.Edit.__init__(self, *args, **keys)
        EDIT_BINDINGS  = {  # single field bindings
            "delete": self.DEL_CHAR,
            "del_line": self.DEL_LINE,
            "del_word": self.DEL_WORD,

            "undel_char": self.UNDEL_CHAR,
            "undel_word": self.UNDEL_WORD,
            "undel_line": self.UNDEL_LINE,

            "next_word": self.NEXT_WORD,
            "prev_word": self.PREV_WORD,

            "move_bol": self.MOVE_BOL,
            "move_eol": self.MOVE_EOL,

            "right": self.MOVE_RIGHT,
            "left": self.MOVE_LEFT,
        }
        self._binder = Binder(EDIT_BINDINGS, inform)

    def reset_del_buffers(self):
        self._del_words = []
        self._del_lines = []
        self._del_chars = []

    def DEL_CHAR(self):
        s = self.get_edit_text()
        if len(s):
            n = self.edit_pos
            if n >= len(s):
                n -= 1
            c = s[n]
            self.set_edit_text(s[:n] + s[n + 1:])
            self._del_chars.append(c)

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
        s = s[:i - len(word)] + s[i:]
        self._del_words.append(word)
        self.edit_pos = i
        self.set_edit_text(s)

    def DEL_LINE(self):
        s = self.get_edit_text()
        line = s[self.edit_pos:]
        self.set_edit_text(s[:self.edit_pos])
        self.set_edit_pos(len(self.get_edit_text()))
        self._del_lines.append(line)

    def NEXT_WORD(self):
        s = self.get_edit_text()
        i = self.edit_pos
        while s and i < len(s) - 1 and not s[i].isspace():
            i += 1
        while s and i < len(s) - 1 and s[i].isspace():
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

    def MOVE_EOL(self):
        self.edit_pos = len(self.get_edit_text())

    def MOVE_RIGHT(self):
        if self.edit_pos < len(self.get_edit_text()):
            self.edit_pos += 1

    def MOVE_LEFT(self):
        if self.edit_pos > 0:
            self.edit_pos -= 1

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
            if len(self._del_lines) > 1:
                line = self._del_lines.pop()
            else:
                line = self._del_lines[0]
        except:
            return
        self.insert_text(line)

    def keypress(self, pos, key):
        key = Binder.keypress(self._binder, pos, key)
        if key is not None and not urwid.is_mouse_event(key):
            key = urwid.Edit.keypress(self, pos, key)
        return key

    def get_result(self):
        return self.get_edit_text().strip()

    def verify(self):
        return True


class StringTparOption(urwid.Columns):

    def __init__(self, paramInfo, defaultParamInfo, inform):

        MODE_KEYS = []

        BINDINGS = {
            "enter": self.ENTER,
            "up": self.MOVE_UP,
            "down": self.MOVE_DOWN,
            "page up": self.PAGE_UP,
            "page down": self.PAGE_DOWN,
            "undel_line": self.UNDEL_LINE,
            "ready": self.READY_LINE,
            "end": self.MOVE_END,
            "home": self.MOVE_START
        }

        self._binder = Binder(BINDINGS, inform, MODE_KEYS)

        self._mode = "clear"
        self._newline = True
        self.inform = inform
        self.paramInfo = paramInfo
        self.defaultParamInfo = defaultParamInfo

        name = self.paramInfo.name
        value = self.paramInfo.get(field="p_filename", native=0, prompt=0)
        self._previousValue = value

        # Generate the input label
        if (self.paramInfo.get(field="p_mode") == "h"):
            required = False
        else:
            required = True

        help = self.paramInfo.get(field="p_prompt", native=0, prompt=0)
        self._args = (name, value, help, required)
        if not required:
            name = "(" + name
            help = ") " + help
        else:
            help = "  " + help
        self._name = urwid.Text(f"{name:<10s}=")
        self._edit = PyrafEdit("",
                               "",
                               wrap="clip",
                               align="right",
                               inform=inform)
        self._edit.verify = self.verify
        self._value = urwid.Text(f"{value:10s}", align="right")
        self._help = urwid.Text(f"{help:<30s}")
        urwid.Columns.__init__(self, [('weight', 0.20, self._name),
                                      ('weight', 0.20, self._edit),
                                      ('weight', 0.20, self._value),
                                      ('weight', 0.40, self._help)], 0, 1, 1)

    def keypress(self, pos, key):
        key = Binder.keypress(self._binder, pos, key)
        if key:
            key = self._edit.keypress(pos, key)
        return key

    def get_name(self):
        return self._args[0]

    def get_candidate(self):
        return self._edit.get_edit_text()

    def set_candidate(self, s):
        self._edit.set_edit_text(s)
        self._edit.edit_pos = len(s)

    def normalize(self, v):
        """abstract method called to standardize equivalent values
        when the 'result' is set."""
        return v

    def get_result(self):
        return self._value.get_text()[0].strip()

    def set_result(self, r):
        self._value.set_text(self.normalize(str(r)))

    def unlearn_value(self):
        self.set_result(self._previousValue)

    def verify(self, v):
        self.inform("")
        return True

    def UNDEL_LINE(
        self
    ):  # a little iffy.  handle first copy from value field to edit field here.  defer subsequent calls.
        v = self.get_result()
        if v:
            self.set_candidate(self.get_candidate() + v)
            self.set_result("")
        else:
            return "undel_line"

    def ENTER(self):
        return self.linechange("down")

    def MOVE_UP(self):
        return self.linechange("up")

    def MOVE_DOWN(self):
        return self.linechange("down")

    def PAGE_UP(self):
        return self.linechange("page up")

    def PAGE_DOWN(self):
        return self.linechange("page down")

    def MOVE_START(self):
        return self.linechange("home")

    def MOVE_END(self):
        return self.linechange("end")

    def linechange(self, rval):
        """Updates this field when changing the field focus,
        i.e. switching lines."""
        s = self.get_candidate()
        if s != "":
            if self.verify(s):
                self.set_result(s)
                self.set_candidate("")
            else:
                return None
        else:  # clear old error messages
            self.inform("")
        self._edit.set_edit_pos(0)
        self._edit.reset_del_buffers()
        self._newline = True
        return rval

    def READY_LINE(self):
        """Prepares this field for editing in the current
        mode: default clear or default edit."""
        if not self._newline:
            return
        self._newline = False
        if self._mode == "clear":
            self.set_candidate("")
        else:
            s = self.get_result()
            self.set_candidate(s)
            self._edit.set_edit_pos(len(s))

    def klass(self):
        return "string"


class NumberTparOption(StringTparOption):

    def normalize(self, v):
        if v in ["INDEF", "Indef", "indef"]:
            return "INDEF"
        else:
            return v

    def verify(self, v):
        try:
            if v != self._previousValue:
                self.paramInfo.set(v)
            self.paramInfo.set(self._previousValue)
            return True
        except ValueError as e:
            self.set_candidate("")
            self.inform(str(e))
            return False

    def klass(self):
        return "number"


class BooleanTparOption(StringTparOption):

    def __init__(self, *args, **keys):
        StringTparOption.__init__(self, *args, **keys)
        self._binder.bind(" ", "space")
        self._binder.bind("space", self.TOGGLE)
        self._binder.bind("right", self.TOGGLE)
        self._binder.bind("left", self.TOGGLE)

    def TOGGLE(self):
        if self.get_result() == "yes":
            self.set_result("no")
        else:
            self.set_result("yes")

    def normalize(self, v):
        if v in ["n", "N"]:
            return "no"
        elif v in ["y", "Y"]:
            return "yes"
        else:
            return v

    def verify(self, v):
        v = self.normalize(v)
        if v in ["yes", "no"]:
            self.inform("")
            return True
        else:
            self.set_candidate("")
            self.inform("Not a valid boolean value.")
            return False

    def klass(self):
        return "boolean"


class EnumTparOption(StringTparOption):

    def __init__(self, *args, **keys):
        StringTparOption.__init__(self, *args, **keys)
        self._binder.bind(" ", "space")
        self._binder.bind("space", self.SPACE)
        self._binder.bind("right", self.SPACE)
        self._binder.bind("left", self.LEFT)

    def adjust(self, delta, wrap):
        choices = self.paramInfo.choice
        try:
            v = choices[choices.index(self.get_result()) + delta]
        except IndexError:
            v = choices[wrap]
        self.set_result(v)

    def SPACE(self):
        return self.adjust(1, 0)

    def LEFT(self):
        return self.adjust(-1, -1)

    def klass(self):
        return "enumeration"

    def verify(self, v):
        if v not in self.paramInfo.choice:
            self.inform("What? choose: " + "|".join(self.paramInfo.choice))
            self.set_candidate("")
            return False
        return True


class PsetTparOption(StringTparOption):

    def klass(self):
        return "pset"


class TparHeader(urwid.Pile):
    banner = """                                   I R A F
                    Image Reduction and Analysis Facility
"""

    def __init__(self, package, task=None):
        top = urwid.Text(("header", self.banner))
        s = f"{'PACKAGE':>8}= {package:<10}\n"
        if task is not None:
            s += f"{'TASK':>8}= {task:<10}"
        info = urwid.Text(("body", s))
        urwid.Pile.__init__(self, [top, info])


class TparDisplay(Binder):
    palette = [
        ('body', 'default', 'default', 'standout'),
        ('header', 'default', 'default', ('standout', 'underline')),
        ('help', 'black', 'light gray'),
        ('reverse', 'light gray', 'black'),
        ('important', 'dark blue', 'light gray', ('standout', 'underline')),
        ('editfc', 'white', 'dark blue', 'bold'),
        ('editbx', 'light gray', 'dark blue'),
        ('editcp', 'black', 'light gray', 'standout'),
        ('bright', 'dark gray', 'light gray', ('bold', 'standout')),
        ('buttn', 'black', 'dark cyan'),
        ('buttnf', 'white', 'dark blue', 'bold'),
    ]

    def __init__(self, taskName):

        MODE_KEYS_EMACS = ["esc"]

        MODE_KEYS_VI = ["esc", "tab", "ctrl u", "ctrl U", "ctrl t", "ctrl T"]

        TPAR_BINDINGS = {  # Page level bindings
            "quit": self.QUIT,
            "exit ": self.EXIT,
            "help": self.HELP,
            "end": self.MOVE_END,
            "home": self.MOVE_START,
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

        # See if there exist any special versions on disk to load
        self.__areAnyToLoad = irafpar.haveSpecialVersions(
            self.taskName, self.pkgName)  # irafpar caches them

        # Ignore the last parameter which is $nargs
        self.numParams = len(self.paramList) - 1

        # Get default parameter values for unlearn
        self.get_default_param_list()
        self.make_entries()

        self.escape = False

        if URWID_PRE_9P9:
            self._createButtonsOld()
        else:
            self._createButtons()

        self.colon_edit = PyrafEdit("",
                                    "",
                                    wrap="clip",
                                    align="left",
                                    inform=self.inform)
        self.listitems = [urwid.Divider(" ")] + self.entryNo + \
                         [urwid.Divider(" "), self.colon_edit,
                          self.buttons]
        self.listbox = urwid.ListBox(self.listitems)

        self.listbox.set_focus(1)
        self.footer = urwid.Text("")
        self.header = TparHeader(self.pkgName, self.taskName)

        self.view = urwid.Frame(self.listbox,
                                header=self.header,
                                footer=self.footer)

        self._editor = iraf.envget("editor")
        BINDINGS = {}
        BINDINGS.update(TPAR_BINDINGS)
        if self._editor == "vi":
            BINDINGS.update(TPAR_BINDINGS_VI)
            MODE_KEYS = MODE_KEYS_VI
        else:
            BINDINGS.update(TPAR_BINDINGS_EMACS)
            MODE_KEYS = MODE_KEYS_EMACS
        Binder.__init__(self, BINDINGS, self.inform, MODE_KEYS)

    def _createButtonsOld(self):
        """ Set up all the bottom row buttons and their spacings """

        isPset = isinstance(self.taskObject, iraftask.IrafPset)

        self.help_button = urwid.Padding(urwid.Button("Help", self.HELP),
                                         align="center",
                                         width=('fixed', 8))
        self.cancel_button = urwid.Padding(urwid.Button("Cancel", self.QUIT),
                                           align="center",
                                           width=('fixed', 10))
        if not isPset:
            self.save_as_button = urwid.Padding(urwid.Button(
                "Save As", self.SAVEAS),
                                                align="center",
                                                width=('fixed', 11))
        self.save_button = urwid.Padding(urwid.Button("Save", self.EXIT),
                                         align="center",
                                         width=('fixed', 8))
        self.exec_button = urwid.Padding(urwid.Button("Exec", self.go),
                                         align="center",
                                         width=('fixed', 8))
        if self.__areAnyToLoad:
            self.open_button = urwid.Padding(urwid.Button("Open", self.PFOPEN),
                                             align="center",
                                             width=('fixed', 8))

        # GUI button layout - weightings
        if isPset:  # show no Open nor Save As buttons
            self.buttons = urwid.Columns([('weight', 0.2, self.exec_button),
                                          ('weight', 0.2, self.save_button),
                                          ('weight', 0.2, self.cancel_button),
                                          ('weight', 0.4, self.help_button)])
        else:
            if not self.__areAnyToLoad:  # show Save As but not Open
                self.buttons = urwid.Columns([
                    ('weight', 0.175, self.exec_button),
                    ('weight', 0.175, self.save_button),
                    ('weight', 0.175, self.save_as_button),
                    ('weight', 0.175, self.cancel_button),
                    ('weight', 0.3, self.help_button)
                ])
            else:  # show all possible buttons (iterated on this spacing)
                self.buttons = urwid.Columns([
                    ('weight', 0.20, self.open_button),
                    ('weight', 0.15, self.exec_button),
                    ('weight', 0.15, self.save_button),
                    ('weight', 0.15, self.save_as_button),
                    ('weight', 0.18, self.cancel_button),
                    ('weight', 0.20, self.help_button)
                ])

    def _createButtons(self):
        """ Set up all the bottom row buttons and their spacings """

        isPset = isinstance(self.taskObject, iraftask.IrafPset)

        self.help_button = urwid.Padding(urwid.Button("Help", self.HELP),
                                         align="center",
                                         width=8,
                                         right=4,
                                         left=5)
        self.cancel_button = urwid.Padding(urwid.Button("Cancel", self.QUIT),
                                           align="center",
                                           width=10)
        if not isPset:
            self.save_as_button = urwid.Padding(urwid.Button(
                "Save As", self.SAVEAS),
                                                align="center",
                                                width=11)
        self.save_button = urwid.Padding(urwid.Button("Save", self.EXIT),
                                         align="center",
                                         width=8)
        self.exec_button = urwid.Padding(urwid.Button("Exec", self.go),
                                         align="center",
                                         width=8)
        if self.__areAnyToLoad:
            self.open_button = urwid.Padding(urwid.Button("Open", self.PFOPEN),
                                             align="center",
                                             width=8)

        # GUI button layout - weightings
        if isPset:  # show no Open nor Save As buttons
            self.buttons = urwid.Columns([('weight', 0.20, self.exec_button),
                                          ('weight', 0.23, self.save_button),
                                          ('weight', 0.23, self.cancel_button),
                                          ('weight', 0.20, self.help_button)])
        else:
            if not self.__areAnyToLoad:  # show Save As but not Open
                self.buttons = urwid.Columns([
                    ('weight', 0.15, self.exec_button),
                    ('weight', 0.15, self.save_button),
                    ('weight', 0.18, self.save_as_button),
                    ('weight', 0.18, self.cancel_button),
                    ('weight', 0.15, self.help_button)
                ])
            else:  # show all possible buttons (iterated on this spacing)
                self.buttons = urwid.Columns([
                    ('weight', 0.10, self.open_button),
                    ('weight', 0.10, self.exec_button),
                    ('weight', 0.10, self.save_button),
                    ('weight', 0.12, self.save_as_button),
                    ('weight', 0.12, self.cancel_button),
                    ('weight', 0.10, self.help_button)
                ])

    def get_default_param_list(self):
        # Obtain the default parameter list
        dlist = self.taskObject.getDefaultParList()
        if len(dlist) != len(self.paramList):
            # whoops, lengths don't match
            raise ValueError("Mismatch between default, current par lists"
                             f" for task {self.taskName} (try unlearn)")
        pardict = {}
        for par in dlist:
            pardict[par.name] = par

        # Build default list sorted into same order as current list
        try:
            dsort = []
            for par in self.paramList:
                dsort.append(pardict[par.name])
        except KeyError:
            raise ValueError("Mismatch between default, current par lists"
                             f" for task {self.taskName} (try unlearn)")
        self.defaultParamList = dsort

    # Method to create the parameter entries
    def make_entries(self):
        # Loop over the parameters to create the entries
        self.entryNo = [None] * self.numParams
        for i in range(self.numParams):
            self.entryNo[i] = self.tpar_option_factory(
                self.paramList[i], self.defaultParamList[i])

    def main(self):
        # Create the Screen using curses_display.
        self.ui = urwid.curses_display.Screen()
        self.ui.register_palette(self.palette)
        self.ui.run_wrapper(self.run)  # raw_display has alternate_buffer=True
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
        self._newline = True
        while not self.done:
            self.view.keypress(size, "ready")
            canvas = self.view.render(size, focus=1)
            self.ui.draw_screen(size, canvas)
            for k in self.get_keys():
                if k == ":":
                    self.colon_escape()
                    break
                elif urwid.is_mouse_event(k):
                    event, button, col, row = k
                    self.view.mouse_event(size,
                                          event,
                                          button,
                                          col,
                                          row,
                                          focus=True)
                elif k == 'window resize':
                    size = self.ui.get_cols_rows()
                    self.inform(f"resize {str(size)}")
                k = self.keypress(size, k)
                self.view.keypress(size, k)

    def colon_escape(self):
        """colon_escape switches the focus to the 'mini-buffer' and
        accepts and executes a one line colon command."""
        w, pos0 = self.listbox.get_focus()
        try:
            default_file = w.get_result()
        except:
            default_file = ""
        self.listbox.set_focus(len(self.listitems) - 2)
        size = self.ui.get_cols_rows()
        self.colon_edit.set_edit_text("")
        self.colon_edit.set_edit_pos(0)
        self.view.keypress(size, ":")
        done = False
        while not done:
            canvas = self.view.render(size, focus=1)
            self.ui.draw_screen(size, canvas)
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
                self.view.keypress(size, k)
        cmd = self.colon_edit.get_edit_text()
        self.listbox.set_focus(pos0)
        self.colon_edit.set_edit_text("")
        self.process_colon(cmd)

    def process_colon(self, cmd):
        # : <cmd_letter> [!] [<filename>]
        groups = re.match(
            "^:(?P<cmd>[a-z])\\s*"
            "(?P<emph>!?)\\s*"
            "(?P<file>\\w*)", cmd)
        if not groups:
            self.inform("bad command: " + cmd)
        else:
            letter = groups.group("cmd")
            emph = groups.group("emph") == "!"
            file = groups.group("file")
            try:
                f = {
                    "q": self.QUIT,
                    "g": self.go,
                    "r": self.read_pset,
                    "w": self.write_pset,
                    "e": self.edit_pset
                }[letter]
            except KeyError:
                self.inform("unknown command: " + cmd)
                return
            try:
                f(file, emph)
            except Exception as e:
                self.inform(f"command '{cmd}' failed with exception '{e}'")

    def save_as(self):
        """ Save the parameter settings to a user-specified file.  Any
        changes here must be coordinated with the corresponding epar saveAs
        function. """

        # The user wishes to save to a different name.
        fname = self.select_file("Save parameter values to which file?",
                                 overwriteCheck=True)

        # Now save the parameters
        if fname is None:
            msg = "Parameters NOT saved to a file."
            okdlg = urwutil.DialogDisplay(msg, 8, 0)
            okdlg.add_buttons([("OK", 0)])
            okdlg.main()
            return

        # Tpar apparently does nothing with children (PSETs), so skip the
        # check or set or save of them

        # Notify them that pset children will not be saved as part of
        # their special version
        pars = []
        for par in self.paramList:
            if par.type == "pset":
                pars.append(par.name)
        if len(pars):
            msg = "If you have made any changes to the PSET "+ \
                  "values for:\n\n"
            for p in pars:
                msg += "     " + p + "\n"
            msg = msg+"\nthose changes will NOT be explicitly saved to:"+ \
                '\n\n"'+fname+'"'
            # title='PSET Save-As Not Yet Supported
            okdlg = urwutil.DialogDisplay(msg, 0, 0)
            okdlg.add_buttons([("OK", 0)])
            okdlg.main()

        # Verify all the entries (without save), keeping track of the invalid
        # entries which have been reset to their original input values
        self.badEntriesList = self.check_set_save_entries(False)

        # If there were invalid entries, prepare the message dialog
        ansOKCANCEL = True
        if self.badEntriesList:
            ansOKCANCEL = self.process_bad_entries(self.badEntriesList,
                                                   self.taskName)
        if not ansOKCANCEL:
            return  # should we tell them we are not saving ?

        # If there were no invalid entries or the user said OK, finally
        # save to their stated file.  Since we have already processed the
        # bad entries, there should be none returned.
        mstr = "TASKMETA: task=" + self.taskName + " package=" + self.pkgName
        if self.check_set_save_entries(doSave=True,
                                       filename=fname,
                                       comment=mstr):
            raise Exception("Unexpected bad entries for: " + self.taskName)

        # Let them know what they just did
        msg = 'Saved to: "' + fname + '"'
        okdlg = urwutil.DialogDisplay(msg, 8, 0)
        okdlg.add_buttons([("OK", 0)])
        okdlg.main()

        # Notify irafpar that there is a new special-purpose file on the scene
        irafpar.newSpecialParFile(self.taskName, self.pkgName, fname)

    def pfopen(self):
        """ Load the parameter settings from a user-specified file.  Any
        changes here must be coordinated with the corresponding epar pfopen
        function. """

        flist = irafpar.getSpecialVersionFiles(self.taskName, self.pkgName)
        if len(flist) <= 0:
            msg = "No special-purpose parameter files found for " + self.taskName
            okdlg = urwutil.DialogDisplay(msg, 8, 0)
            okdlg.add_buttons([("OK", 0)])
            okdlg.main()
            return

        fname = None
        if len(flist) == 1:
            msg = "One special-purpose parameter file found.\n"+ \
                  "Load file?\n\n"+flist[0]
            yesnodlg = urwutil.DialogDisplay(msg, 12, 0)
            yesnodlg.add_buttons([("OK", 0), ("Cancel", 1)])
            rv, junk = yesnodlg.main()
            if rv == 0:
                fname = flist[0]  # if not, fname is still None
        else:  # >1 file, need a select dialog
            flist.sort()
            chcs = []  # ListDialogDisplay takes a 2-column tuple
            for i in range(len(flist)):
                chcs.append(str(i))  # need index as tag - it is the return val
                chcs.append(flist[i])

            def menuItemConstr(tag, state):
                return urwutil.MenuItem(tag)

            selectdlg = urwutil.ListDialogDisplay("Select from these:",
                                                  len(flist) + 7,
                                                  75, menuItemConstr,
                                                  tuple(chcs), False)
            selectdlg.add_buttons([
                ("Cancel", 1),
            ])
            rv, ans = selectdlg.main()
            if rv == 0:
                fname = flist[int(ans)]

        # check-point: if fname is not None, we load a file
        msg = "\n\nPress any key to continue..."

        if fname is not None:
            newParList = irafpar.IrafParList(self.taskName, fname)  # load it
            self.set_all_entries_from_par_list(newParList)  # set GUI entries
            msg = "\n\nLoaded:\n\n     " + fname + msg

        # Notify them (also forces a screen redraw, which we need)
        try:
            self.ui.clear()  # fixes clear when next line calls draw_screen
        except AttributeError:
            self.ui._clear()  # older urwid vers use different method name
        self.info(msg, None)

    def save(self, emph):
        # Save all the entries and verify them, keeping track of the invalid
        # entries which have been reset to their original input values
        if emph:
            return
        self.badEntriesList = self.check_set_save_entries(True)

        # If there were invalid entries, prepare the message dialog
        ansOKCANCEL = True
        if (self.badEntriesList):
            ansOKCANCEL = self.process_bad_entries(self.badEntriesList,
                                                   self.taskName)
        return ansOKCANCEL

    def MOVE_START(self):
        self.listbox.set_focus(1)
        return "home"

    def MOVE_END(self):
        self.listbox.set_focus(len(self.entryNo))
        return "end"

    # For the following routines,  event is either a urwid event *or*
    # a Pset filename
    def QUIT(self, event=None, emph=True):  # maybe save
        self.save(emph)

        def quit_continue():
            pass

        self.done = quit_continue

    def PFOPEN(self, event=None):
        """ Open button - load parameters from a user specified file"""
        self.pfopen()
        self.done = None  # simply continue

    def SAVEAS(self, event=None):
        """ SaveAs button - save parameters to a user specified file"""
        self.save_as()

        def save_as_continue():  # get back to editing
            iraffunctions.tparam(self.taskObject)

        self.done = save_as_continue  # self.done = None # will also continue

    def EXIT(self, event=None):  # always save
        self.QUIT(event, False)

    # EXECUTE: save the parameter settings and run the task
    def go(self, event=None, emph=False):
        """Executes the task."""
        self.save(emph)

        def go_continue():
            print(f"\nTask {self.taskName} is running...\n")
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
                iraffunctions.tparam(file)

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
            self.inform(f"File '{file}' exists and overwrite (!) not used.")
        # XXXX write out parameters to file
        self.inform(f"write pset: {file}")

    def set_all_entries_from_par_list(self, aParList):
        """ Set all the parameter entry values in the GUI to the values
            in the given par list. Note corresponding EditParDialog method. """
        for i in range(self.numParams):
            par = self.paramList[i]
            if par.type == "pset":
                continue  # skip PSET's for now
            gui_entry = self.entryNo[i]
            par.set(aParList.getValue(par.name, native=1, prompt=0))
            # gui holds a str, but par.value is native; conversion occurs
            gui_entry.set_result(par.value)

    def unlearn_all_entries(self):
        """ Method to "unlearn" all the parameter entry values in the GUI
            and set the parameter back to the default value """
        for entry in self.entryNo:
            entry.unlearn_value()

    # Read, save, and verify the entries
    def check_set_save_entries(self, doSave, filename=None, comment=None):

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
                if not entry.verify(value):
                    self.badEntries.append(
                        [entry.paramInfo.name, value, entry._previousValue])
                else:
                    self.taskObject.setParam(par.name, value)

        # Save results to the uparm directory
        # Skip the save if the thing being edited is an IrafParList without
        # an associated file (in which case the changes are just being
        # made in memory.)

        if doSave and ((not isinstance(self.taskObject, irafpar.IrafParList))
                       or self.taskObject.getFilename()):
            self.taskObject.saveParList(filename=filename, comment=comment)

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
        canvas = self.view.render(size, focus=True)
        self.ui.draw_screen(size, canvas)

    def inform(self, s):
        """output any message to status bar"""
        self.footer.set_text(s)

    def info(self, msg, b):
        self.exit_flag = False
        size = self.ui.get_cols_rows()
        exit_button = urwid.Padding(urwid.Button("Exit", self.exit_info),
                                    align="center",
                                    width=8)
        frame = urwid.Frame(urwid.Filler(urwid.AttrWrap(
            urwid.Text(msg), "help"),
                                         valign="top"),
                            header=self.header,
                            footer=exit_button)
        canvas = frame.render(size)
        self.ui.draw_screen(size, canvas)
        self.get_keys()  # wait for keypress

    def exit_info(self, ehb):
        self.exit_flag = True

    def HELP(self, event=None):
        if self._editor == "vi":
            self.info(TPAR_HELP_VI, self.help_button)
        else:
            self.info(TPAR_HELP_EMACS, self.help_button)

    def select_file(self, prompt, overwriteCheck=False):
        """ Allow user to input a file - handle whether it is expected
        to be new or existing. Returns file name on success, None on error. """

        # Allow the user to select a specific file.  Note that urwid's
        # browser example (browse.py) doesn't work with 0.9.7.
        while True:
            try:
                fname = urwfiledlg.main()
            except:
                prompt = "(File chooser error, enter choice manually.)\n" + prompt
                inputdlg = urwutil.InputDialogDisplay(prompt, 9, 0)
                inputdlg.add_buttons([("OK", 0), ("Cancel", 1)])
                rv, fname = inputdlg.main()
                if rv > 0:
                    fname = None

            if fname is None:
                return None  # they canceled
            fname = fname.strip()
            if len(fname) == 0:
                return None

            # See if the file exists (if we care)
            if overwriteCheck and os.path.exists(fname):
                yesnodlg = urwutil.DialogDisplay(
                    "File exists!  Overwrite?\n\n    " + fname, 9, 0)
                yesnodlg.add_buttons([("Yes", 0), ("No", 1)])
                rv, junk = yesnodlg.main()
                if rv == 0:
                    return fname
                # if no, then go thru selection again
            else:
                return fname

    def askokcancel(self, title, msg):
        self.info(msg, None)
        return False

    # Process invalid input values and invoke a query dialog
    def process_bad_entries(self, badEntriesList, taskname):

        tpl = "{:>20s} {:>20s} {:>20s}\n"
        badEntriesString = "\nTask " + taskname.upper() + \
                           " -- Invalid values have been entered.\n\n"
        badEntriesString += tpl.format("Parameter", "Bad Value", "Reset Value")
        for i in range(len(badEntriesList)):
            badEntriesString += tpl.format(badEntriesList[i][0].strip(),
                                           badEntriesList[i][1].strip(),
                                           badEntriesList[i][2].strip())

            badEntriesString += "\nOK to continue using"\
                " the reset\nvalues or cancel to re-enter\nvalues?\n"

        # Invoke the modal message dialog
        return (self.askokcancel("Notice", badEntriesString))

    # TparOption values for non-string types
    _tparOptionDict = {
        "b": BooleanTparOption,
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
        if (param.choice is not None):
            tparOption = EnumTparOption
        else:
            # Use String for types not in the dictionary
            tparOption = self._tparOptionDict.get(param.type, StringTparOption)
        return tparOption(param, defaultParam, self.inform)


def tpar(taskName):
    if isinstance(urwid, FakeModule):
        print(
            "The urwid package isn't found on your Python system so tpar can't be used.",
            file=sys.stderr)
        print('    (the error given: "' + urwid.the_error + '")',
              file=sys.stderr)
        print("Please install urwid version >= 0.9.7 or use epar instead.",
              file=sys.stderr)
        return
    TparDisplay(taskName).main()
