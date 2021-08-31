""" 'msgiowidget.py' -- this is a replacement for the msgiobuffer module.
   This contains the MsgIOWidget class, which is an optionally hidden
   scrolling canvas composed of a text widget and frame.  When "hidden",
   it turns into a single-line text widget.
"""


# System level modules
import tkinter

# Our modules
from stsci.tools import tkrotext


def is_USING_X():
    """ This is specifically in a function and not at the top
    of this module so that it is not done until needed.  We do
    not want to casually import wutil anywhere. The import mechanism
    makes this speedy on the 2nd-Nth attempt anyway. """
    from . import wutil
    return wutil.WUTIL_USING_X


class MsgIOWidget(tkinter.Frame):
    """MsgIOWidget class"""

    def __init__(self, parent, width=100, text=""):
        """Constructor"""

        # We are the main frame that holds everything we do
        tkinter.Frame.__init__(self, parent)
        self._parent = parent

        # Create two sub-frames, one to hold the 1-liner msg I/O, and
        # the other one to hold the whole scrollable history.
        self._nowFrame = tkinter.Frame(self,
                                     bd=2,
                                     relief=tkinter.SUNKEN,
                                     takefocus=False)
        self._histFrame = tkinter.Frame(self,
                                      bd=2,
                                      relief=tkinter.SUNKEN,
                                      takefocus=False)

        # Put in the expand/collapse button (determine it's sizes)
        self._expBttnHasTxt = True
        btxt = '+'
        if is_USING_X():
            px = 2
            py = 0
        else:  # Aqua
            px = 5
            py = 3
            if tkinter.TkVersion > 8.4:
                px = py = 0
                btxt = ''
                self._expBttnHasTxt = False
        self._expBttn = tkinter.Checkbutton(self._nowFrame,
                                          command=self._expand,
                                          padx=px,
                                          pady=py,
                                          text=btxt,
                                          indicatoron=0,
                                          state=tkinter.DISABLED)
        self._expBttn.pack(side=tkinter.LEFT, padx=3)  # , ipadx=0)

        # Overlay a label on the frame
        self._msgLabelVar = tkinter.StringVar()
        self._msgLabelVar.set(text)
        self._msgLabelMaxWidth = 65  # 70 works but causes plot redraws when
        # the history panel is opened/closed
        self._msgLabel = tkinter.Label(self._nowFrame,
                                     textvariable=self._msgLabelVar,
                                     anchor=tkinter.W,
                                     justify=tkinter.LEFT,
                                     width=self._msgLabelMaxWidth,
                                     wraplength=width - 100,
                                     takefocus=False)
        self._msgLabel.pack(side=tkinter.LEFT, fill=tkinter.X, expand=False)
        self._msgLabel.bind('<Double-Button-1>', self._lblDblClk)

        self._entry = tkinter.Entry(self._nowFrame,
                                  state=tkinter.DISABLED,
                                  width=1,
                                  takefocus=False,
                                  relief=tkinter.FLAT,
                                  highlightthickness=0)
        self._entry.pack(side=tkinter.LEFT, fill=tkinter.X, expand=True)
        self._entry.bind('<Return>', self._enteredText)
        self._entryTyping = tkinter.BooleanVar()
        self._entryTyping.set(False)

        # put in a spacer here for label height stability
        self._spacer = tkinter.Label(self._nowFrame, text='', takefocus=False)
        self._spacer.pack(side=tkinter.LEFT, expand=False, padx=5)

        self._nowFrame.pack(side=tkinter.TOP, fill=tkinter.X, expand=True)

        self._hasHistory = False
        self._histScrl = tkinter.Scrollbar(self._histFrame)
        self._histScrl.pack(side=tkinter.RIGHT, fill=tkinter.Y)

        self._histText = tkrotext.ROText(self._histFrame,
                                         wrap=tkinter.WORD,
                                         takefocus=False,
                                         height=10,
                                         yscrollcommand=self._histScrl.set)
        # (use if just tkinter.Text) state=tkinter.DISABLED, takefocus=False,
        #                        exportselection=True is the default
        self._histText.pack(side=tkinter.TOP, fill=tkinter.X, expand=True)
        self._histScrl.config(command=self._histText.yview)

        # don't pack this one now - start out with it hidden
        #       self._histFrame.pack(side=tkinter.TOP, fill=tkinter.X)

        ### Do not pack the main frame here.  Let the application do it. ###

        # At very end of ctor, add the init text to our history
        self._appendToHistory(text)

    def _lblDblClk(self, event=None):
        if self._hasHistory:
            # change the button appearance
            self._expBttn.toggle()  # or .select() / .deselect()
            # and then act as if it was clicked
            self._expand()

    def _expand(self):
        ism = self._histFrame.winfo_ismapped()
        if ism:  # need to collapse
            self._histFrame.pack_forget()
            if self._expBttnHasTxt:
                self._expBttn.configure(text='+')
        else:  # need to expand
            self._histFrame.pack(side=tkinter.TOP, fill=tkinter.BOTH,
                                 expand=True)  # .X)
            if self._expBttnHasTxt:
                self._expBttn.configure(text='-')
            if self._hasHistory:
                self._histText.see(tkinter.END)

    def updateIO(self, text=""):
        """ Update the text portion of the scrolling canvas """
        # Update the class variable with the latest text, and append the
        # new text to the end of the history.
        self._appendToHistory(text)
        self._msgLabelVar.set(text)
        # this is a little debugging "easter egg"
        if text.find('long debug line') >= 0:
            self.updateIO(
                'and now we are going to talk and talk for a while' +
                ' about nothing at all because we want a lot of text')
        self._nowFrame.update_idletasks()

    def readline(self):
        """ Set focus to the entry widget and return it's contents """
        # Find what had focus up to this point
        lastFoc = self.focus_get()

        # Collapse the label as much as possible, it is too big on Linux & OSX
        lblTxt = self._msgLabelVar.get()
        lblTxtLen = len(lblTxt.strip())
        lblTxtLen -= 3
        self._msgLabel.configure(width=min(self._msgLabelMaxWidth, lblTxtLen))

        # Enable the entry widget
        self._entry.configure(state=tkinter.NORMAL,
                              relief=tkinter.SUNKEN,
                              width=15,
                              takefocus=True,
                              highlightthickness=2)
        self._entry.focus_set()
        self._entryTyping.set(True)

        # Wait until they are done entering their answer
        self._entry.wait_variable(self._entryTyping)

        # By now they have hit enter
        ans = self._entry.get().strip()

        # Clear and disable the entry widget
        self._entry.delete(0, tkinter.END)
        self._entry.configure(state=tkinter.DISABLED,
                              takefocus=False,
                              width=1,
                              relief=tkinter.FLAT,
                              highlightthickness=0)
        self._entryTyping.set(False)

        # Expand the label back to normal width
        self._msgLabel.configure(width=self._msgLabelMaxWidth)

        # list the answer
        self.updateIO(ans)

        # return focus
        if lastFoc:
            lastFoc.focus_set()

        # return the answer - important to have the "\n" on it
        return ans + "\n"

    def _enteredText(self, event=None):
        self._entryTyping.set(False)  # end the waiting
        self._expBttn.focus_set()

    def _appendToHistory(self, txt):
        # sanity check - need no blank lines in the history
        if len(txt.strip()) < 1:
            return

        # enable widget temporarily so we can add text
#       self._histText.config(state=tkinter.NORMAL)
#       self._histText.delete(1.0, END)

# add the new text
        if self._hasHistory:
            self._histText.insert(tkinter.END, '\n' + txt.strip(), force=True)
        else:
            self._histText.insert(tkinter.END, txt.strip(), force=True)
            self._hasHistory = True

        # disable it again
#       self._histText.config(state=tkinter.DISABLED)

# show it
        if self._histFrame.winfo_ismapped():
            self._histText.see(tkinter.END)


#       self._histFrame.update_idletasks()

# finally, make sure expand/collapse button is enabled now
        self._expBttn.configure(state=tkinter.NORMAL)
