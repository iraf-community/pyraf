"""module 'msgiobuffer.py' -- module containing the MsgIOBuffer class.  This
   class creates a scrolling canvas composed of a message box and an I/O
   frame.  The message box contains the history of I/O messages; the I/O
   frame contains the latest I/O from the interactive program.

M.D. De La Pena, 2000 June 28
"""


# System level modules
from tkinter import (StringVar, BooleanVar, Canvas, Frame, Scrollbar, Label,
                     Entry, Message, TRUE, FALSE, VERTICAL, NORMAL, DISABLED,
                     FLAT, SUNKEN, RAISED, TOP, LEFT, RIGHT, Y, X, NW, SW, END)


class MsgIOBuffer(Frame):
    """MsgIOBuffer class"""

    def __init__(self, parent, width=100, viewHeight=None, text=""):
        """Constructor for the MsgIOBuffer class"""

        Frame.__init__(self)

        # Initialize class attributes
        self.messageText = ""
        self.currentText = text
        self.minHgt = 25  # try 65 with Tk8.5 on OSX
        self.viewHeight = viewHeight
        self.entrySetting = StringVar()
        self.entrySetting.set("")
        self.entryValue = self.entrySetting.get()

        self.waitFlag = BooleanVar()
        self.waitFlag.set(TRUE)

        # Set up the frame to hold the message and the I/O
        self.parent = parent
        self.msgIO = Frame(self.parent, bd=2, relief=FLAT, takefocus=FALSE)

        # Overlay a canvas on the frame
        self.msgIO.canvas = Canvas(self.msgIO,
                                   takefocus=FALSE,
                                   highlightthickness=0)

        # Attach a vertical scrollbar to the canvas
        self.msgIO.vscroll = Scrollbar(self.msgIO,
                                       orient=VERTICAL,
                                       width=11,
                                       relief=SUNKEN,
                                       activerelief=RAISED,
                                       takefocus=FALSE)
        self.msgIO.canvas['yscrollcommand'] = self.msgIO.vscroll.set
        self.msgIO.vscroll['command'] = self.msgIO.canvas.yview
        self.msgIO.vscroll.pack(side=RIGHT, fill=Y)

        # Pack the canvas
        self.msgIO.canvas.pack(side=LEFT, fill=X, expand=TRUE, padx=4)

        # Do not pack the frame here.  Do it in the application. ###
        # self.msgIO.pack(side = TOP, fill = X, expand = TRUE)

        # Define a frame that will sit on the canvas
        # This frame will hold a message box and a small I/O frame
        self.msgIO.canvas.f = Frame(self.msgIO.canvas)
        self.msgIO.canvas.f.pack(fill=X, expand=TRUE)

        # Generate the window for the canvas
        self.msgIO.canvas.create_window(0,
                                        0,
                                        anchor=NW,
                                        window=self.msgIO.canvas.f)

        # Define a frame for I/O to be placed on the canvas
        self.msgIO.canvas.f.iomb = Frame(self.msgIO.canvas.f,
                                         relief=FLAT,
                                         bd=0)

        # Frame may contain message and a label, or message, label and entry.
        self.msgIO.canvas.f.iomb.label = Label(self.msgIO.canvas.f.iomb,
                                               text=self.currentText,
                                               bd=5,
                                               takefocus=FALSE)

        self.msgIO.canvas.f.iomb.entry = Entry(self.msgIO.canvas.f.iomb,
                                               highlightthickness=0,
                                               bg="#d9d9d9",
                                               relief=FLAT,
                                               textvariable=self.entrySetting,
                                               state=DISABLED,
                                               insertwidth=2,
                                               takefocus=FALSE)

        # Bind the carriage return to the entry
        self.msgIO.canvas.f.iomb.entry.bind('<Return>', self.__getEntryValue)

        # Define a message box to be placed in the frame
        self.msgIO.canvas.f.iomb.msg = Message(self.msgIO.canvas.f.iomb,
                                               bd=0,
                                               relief=FLAT,
                                               text=self.messageText,
                                               anchor=SW,
                                               width=width,
                                               takefocus=FALSE)

        # Pack the widgets in the frame
        self.msgIO.canvas.f.iomb.msg.pack(side=TOP, fill=X, expand=TRUE)
        self.msgIO.canvas.f.iomb.label.pack(side=LEFT)
        self.msgIO.canvas.f.iomb.entry.pack(side=LEFT, fill=X, expand=TRUE)
        self.msgIO.canvas.f.iomb.pack(side=TOP, fill=X, expand=TRUE)

        # The full scrolling region is the width of the parent and
        # the height of the label/entry (25) and the message box (18)
        # combined.  Hardcoded to avoid too much updating which causes
        # redraws in PyRAF.
        scrollHgt = 43
        self.msgIO.canvas.itemconfigure(1, height=scrollHgt)
        self.msgIO.canvas.configure(scrollregion=(0, 0, 0, scrollHgt))

        # The displayed portion of the window on the canvas is primarily
        # the label/entry region.
        if (self.viewHeight is None or self.viewHeight < self.minHgt):
            self.msgIO.canvas.configure(height=self.minHgt)
        else:
            self.msgIO.canvas.configure(height=self.viewHeight)

        # View is to show the information just moved into the message area
        self.msgIO.canvas.yview_moveto(1)

    def updateIO(self, text=""):
        """Method to update the I/O portion of the scrolling canvas"""

        # Move the current contents of the I/O frame to the message box
        self.__updateMsg(self.currentText)

        # Update the class variable with the latest text
        self.currentText = text

        # Now reconfigure the I/O frame
        self.msgIO.canvas.f.iomb.label.configure(text=text)

    def readline(self):
        """Method to set focus to the Entry widget and XXX"""

        self.__enableEntry()
        self.msgIO.canvas.f.iomb.entry.wait_variable(self.waitFlag)
        self.waitFlag.set(TRUE)

        # Important to have the "\n" on the returned value
        return (self.entryValue + "\n")

    def __getEntryValue(self, event=None):
        """Private method to obtain any value entered in the Entry"""

        self.entryValue = self.entrySetting.get()
        self.msgIO.canvas.f.iomb.entry.delete(0, END)

        # Combine any label value and the entry value in order
        # to update the current text
        self.currentText = self.currentText + " " + self.entryValue

        # Disable the entry
        self.msgIO.canvas.f.iomb.entry.configure(state=DISABLED)
        self.waitFlag.set(FALSE)
        if self.lastFocus:
            self.lastFocus.focus_set()

    def __enableEntry(self):
        """Private method to put the Entry into a normal state for input."""

        # Input is requested, so enable the entry box
        f = self.focus_displayof()
        if f:
            self.lastFocus = f.focus_lastfor()
        else:
            self.lastFocus = None
        self.msgIO.canvas.f.iomb.entry.configure(state=NORMAL)
        self.msgIO.canvas.f.iomb.entry.focus_set()

    def __updateMsg(self, text=""):
        """Private method to update the message box of the scrolling canvas."""

        # Ensure there is a new line
        text = "\n" + text

        # Append the new text to the previous message text
        self.messageText = self.messageText + text
        self.msgIO.canvas.f.iomb.msg.configure(text=self.messageText)
        self.msgIO.canvas.f.update_idletasks()

        # Reconfigure the canvas size/scrollregion based upon the message box
        mbHgt = self.msgIO.canvas.f.iomb.msg.winfo_height()
        scrollHgt = mbHgt + self.minHgt
        self.msgIO.canvas.itemconfigure(1, height=scrollHgt)
        self.msgIO.canvas.configure(scrollregion=(0, 0, 0, scrollHgt))
        self.msgIO.canvas.yview_moveto(1)
