# TODO: These were not ported to "tests" for Jenkins CI because
#       they are interactive.
import sys
import time

import Tkinter as TKNTR  # requires 2to3
from Tkinter import *  # requires 2to3
from stsci.tools import irafutils

from pyraf.msgiobuffer import MsgIOBuffer
from pyraf.msgiowidget import MsgIOWidget
from pyraf.splash import PyrafSplash


def test_buffer():
    """Test the MsgIOBuffer class"""
    width   = 500
    height  = 300
    vheight = 50
    text    = "Tiptop"

    top = Toplevel()
    f   = Frame(top, width = width, height = height, bg = "red")
    m   = MsgIOBuffer(top, width, vheight, text)
    m.msgIO.pack(side=BOTTOM, fill = X)
    f.pack(side = TOP, fill = BOTH, expand = TRUE)
    for i in range(10):
        t = "Text " + str(i)
        m.updateIO(t)
    m.updateIO("The quick brown fox jumps over the lazy dog with ease.")
    m.updateIO("What is your quest?")
    #inputValue = m.readline()
    #print "inputValue = ", inputValue

    top.mainloop()


def test_widget():
    m = None

    def quit():
        sys.exit()

    def clicked():
        m.updateIO("Clicked at "+time.asctime())

    def ask():
        m.updateIO("Type something in:")
        out = m.readline()

    # create the initial Tk window and immediately withdraw it
    irafutils.init_tk_default_root()

    # make our test window
    top = TKNTR.Toplevel()
    f = TKNTR.Frame(top, width=500, height=300)
    b = TKNTR.Button(f, text='Click Me', command=clicked)
    b.pack(side=TKNTR.LEFT, fill=TKNTR.X, expand=1)
    q = TKNTR.Button(f, text='Buh-Bye', command=quit)
    q.pack(side=TKNTR.LEFT)
    f.pack(side=TKNTR.TOP, fill=TKNTR.X) # , expand=1)
    p = TKNTR.Button(top, text='Prompt Me', command=ask)
    p.pack(side=TKNTR.TOP, fill=TKNTR.X, expand=1)
    fill = TKNTR.Frame(top, height=200, bg="green")
    fill.pack(side=TKNTR.TOP, fill=TKNTR.BOTH, expand=1)
    m = MsgIOWidget(top, 500, "Tiptop")
    m.pack(side=TKNTR.BOTTOM, fill=TKNTR.X)
    for i in range(10):
        t = "Text " + str(i)
        m.updateIO(t)
    m.updateIO("What is your quest?")
    inputValue = m.readline()

    # start
    top.mainloop()


def test_splash():
    s = PyrafSplash()
    print("Sleeping 2 seconds...")
    time.sleep(2)
    s.Destroy()
