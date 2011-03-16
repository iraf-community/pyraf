""" 'msgiowidget.py' -- this is a replacement for the msgiobuffer module.
   This contains the MsgIOWidget class, which is an optionally hidden
   scrolling canvas composed of a text widget and frame.  When "hidden",
   it turns into a single-line text widget.
   $Id$
"""
from __future__ import division # confidence high

# System level modules
import sys
import Tkinter as Tki
from pytools import tkrotext

USING_X = not sys.platform.startswith('win') # in most cases we use X
if sys.platform == 'darwin':
    USING_X = ",".join(sys.path).lower().find('/pyobjc') < 0

class MsgIOWidget(Tki.Frame):

    """MsgIOWidget class"""

    def __init__(self, parent, width=100, text=""):
        """Constructor"""

        # We are the main frame that holds everything we do
        Tki.Frame.__init__(self, parent)
        self._parent = parent

        # Create two sub-frames, one to hold the 1-liner msg I/O, and
        # the other one to hold the whole scrollable history.
        self._nowFrame = Tki.Frame(self, bd=2, relief=Tki.SUNKEN,
                                   takefocus=False)
        self._histFrame = Tki.Frame(self, bd=2, relief=Tki.SUNKEN,
                                   takefocus=False)

        # Put in the expand/collapse button (determine it's sizes)
        self._expBttnHasTxt = True
        btxt= '+'
        if USING_X:
            px = 2
            py = 0
        else: # Aqua ?
            px = 5
            py = 3
            if Tki.TkVersion > 8.4:
                px = py = 0
                btxt = ''
                self._expBttnHasTxt = False
        self._expBttn = Tki.Checkbutton(self._nowFrame, command=self._expand,
                                        padx=px, pady=py,
                                        text=btxt, indicatoron=0,
                                        state = Tki.DISABLED)
        self._expBttn.pack(side=Tki.LEFT, padx=3)#, ipadx=0)

        # Overlay a label on the frame
        self._msgLabelVar = Tki.StringVar()
        self._msgLabelVar.set(text)
        self._msgLabelMaxWidth = 65 # 70 works but causes plot redraws when
                                    # the history panel is opened/closed
        self._msgLabel = Tki.Label(self._nowFrame,
                                   textvariable=self._msgLabelVar,
                                   anchor=Tki.W,
                                   justify=Tki.LEFT,
                                   width=self._msgLabelMaxWidth,
                                   wraplength=width-100,
                                   takefocus=False)
        self._msgLabel.pack(side=Tki.LEFT,
                            fill=Tki.X,
                            expand=False)
        self._msgLabel.bind('<Double-Button-1>', self._lblDblClk)

        self._entry = Tki.Entry(self._nowFrame,
                                state=Tki.DISABLED,
                                width=1,
                                takefocus=False,
                                relief=Tki.FLAT,
                                highlightthickness=0)
        self._entry.pack(side=Tki.LEFT, fill=Tki.X, expand=True)
        self._entry.bind('<Return>', self._enteredText)
        self._entryTyping = Tki.BooleanVar()
        self._entryTyping.set(False)

        # put in a spacer here for label height stability
        self._spacer = Tki.Label(self._nowFrame, text='', takefocus=False)
        self._spacer.pack(side=Tki.LEFT, expand=False, padx=5)

        self._nowFrame.pack(side=Tki.TOP, fill=Tki.X, expand=True)

        self._hasHistory = False
        self._histScrl = Tki.Scrollbar(self._histFrame)
        self._histScrl.pack(side=Tki.RIGHT, fill=Tki.Y)

        self._histText = tkrotext.ROText(self._histFrame, wrap=Tki.WORD,
                         takefocus=False,
                         height=10, yscrollcommand=self._histScrl.set)
# (use if just Tki.Text) state=Tki.DISABLED, takefocus=False,
#                        exportselection=True is the default
        self._histText.pack(side=Tki.TOP, fill=Tki.X, expand=True)
        self._histScrl.config(command=self._histText.yview)

        # don't pack this one now - start out with it hidden
#       self._histFrame.pack(side=Tki.TOP, fill=Tki.X)

        ### Do not pack the main frame here.  Let the application do it. ###

        # At very end of ctor, add the init text to our history
        self._appendToHistory(text)


    def _lblDblClk(self, event=None):
        if self._hasHistory:
            # change the button appearance
            self._expBttn.toggle() # or .select() / .deselect()
            # and then act as if it was clicked
            self._expand()


    def _expand(self):
        ism = self._histFrame.winfo_ismapped()
        if ism: # need to collapse
            self._histFrame.pack_forget()
            if self._expBttnHasTxt:
                self._expBttn.configure(text='+')
        else:   # need to expand
            self._histFrame.pack(side=Tki.TOP, fill=Tki.BOTH, expand=True) #.X)
            if self._expBttnHasTxt:
                self._expBttn.configure(text='-')
            if self._hasHistory:
                self._histText.see(Tki.END)


    def updateIO(self, text=""):
        """ Update the text portion of the scrolling canvas """
        # Update the class variable with the latest text, and append the
        # new text to the end of the history.
        self._appendToHistory(text)
        self._msgLabelVar.set(text)
        # this is a little debugging "easter egg"
        if text.find('long debug line') >=0:
           self.updateIO('and now we are going to talk and talk for a while'+\
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
        self._entry.configure(state=Tki.NORMAL, relief=Tki.SUNKEN, width=15,
                              takefocus=True, highlightthickness=2)
        self._entry.focus_set()
        self._entryTyping.set(True)

        # Wait until they are done entering their answer
        self._entry.wait_variable(self._entryTyping)

        # By now they have hit enter
        ans = self._entry.get().strip()

        # Clear and disable the entry widget
        self._entry.delete(0, Tki.END)
        self._entry.configure(state=Tki.DISABLED, takefocus=False, width=1,
                              relief=Tki.FLAT, highlightthickness=0)
        self._entryTyping.set(False)

        # Expand the label back to normal width
        self._msgLabel.configure(width=self._msgLabelMaxWidth)

        # list the answer
        self.updateIO(ans)

        # return focus
        if lastFoc:
            lastFoc.focus_set()

        # return the answer - important to have the "\n" on it
        return ans+"\n"


    def _enteredText(self, event=None):
        self._entryTyping.set(False) # end the waiting
        self._expBttn.focus_set()


    def _appendToHistory(self, txt):
        # sanity check - need no blank lines in the history
        if len(txt.strip()) < 1:
            return

        # enable widget temporarily so we can add text
#       self._histText.config(state=Tki.NORMAL)
#       self._histText.delete(1.0, END)

        # add the new text
        if self._hasHistory:
            self._histText.insert(Tki.END, '\n'+txt.strip(), force=True)
        else:
            self._histText.insert(Tki.END, txt.strip(), force=True)
            self._hasHistory = True

        # disable it again
#       self._histText.config(state=Tki.DISABLED)

        # show it
        if self._histFrame.winfo_ismapped():
            self._histText.see(Tki.END)
#       self._histFrame.update_idletasks()

        # finally, make sure expand/collapse button is enabled now
        self._expBttn.configure(state = Tki.NORMAL)


# Test the above class
if __name__ == '__main__':

    import sys, time

    m = None

    def quit():
        sys.exit()

    def clicked():
        m.updateIO("Clicked at "+time.asctime())

    def ask():
        m.updateIO("Type something in:")
        out = m.readline()

    # create the initial Tk window and immediately withdraw it
    if not Tki._default_root:
        _default_root = Tki.Tk()
    else:
        _default_root = Tki._default_root
    _default_root.withdraw()

    # make our test window
    top = Tki.Toplevel()
    f = Tki.Frame(top, width=500, height=300)
    b = Tki.Button(f, text='Click Me', command=clicked)
    b.pack(side=Tki.LEFT, fill=Tki.X, expand=1)
    q = Tki.Button(f, text='Buh-Bye', command=quit)
    q.pack(side=Tki.LEFT)
    f.pack(side=Tki.TOP, fill=Tki.X) # , expand=1)
    p = Tki.Button(top, text='Prompt Me', command=ask)
    p.pack(side=Tki.TOP, fill=Tki.X, expand=1)
    fill = Tki.Frame(top, height=200, bg="green")
    fill.pack(side=Tki.TOP, fill=Tki.BOTH, expand=1)
    m = MsgIOWidget(top, 500, "Tiptop")
    m.pack(side=Tki.BOTTOM, fill=Tki.X)
    for i in range(10):
        t = "Text " + str(i)
        m.updateIO(t)
    m.updateIO("What is your quest?")
    inputValue = m.readline()

    # start
    top.mainloop()
