"""splash.py: Display PyRAF splash screen

$Id$

R. White, 2001 Dec 15
"""

from __future__ import division # confidence high

import os, sys, Tkinter
from stsci.tools.irafglobals import IrafPkg
import wutil

logo = "pyraflogo_rgb_web.gif"

class SplashScreen(Tkinter.Toplevel):

    """Base class for splash screen

    Subclass and override createWidgets().
    In constructor of main window/application call
    - S = SplashScreen(main=self)        (if caller is Toplevel)
    - S = SplashScreen(main=self.master) (if caller is Frame)
    - S.Destroy()  after you are done creating your widgets etc.

    Based closely on news posting by Alexander Schliep, 07 Apr 1999
    """

    def __init__(self, master=None, borderwidth=4, relief=Tkinter.RAISED, **kw):
        Tkinter.Toplevel.__init__(self, master, relief=relief,
            borderwidth=borderwidth, **kw)
        if self.master.master != None: # Why?
            self.master.master.withdraw()
        self.master.withdraw()
        self.overrideredirect(1)
        self.createWidgets()
        self.after_idle(self.centerOnScreen)
        self.update()

    def centerOnScreen(self):
        self.update_idletasks()
        xmax = self.winfo_screenwidth()
        ymax = self.winfo_screenheight()
        x0 = (xmax - self.winfo_reqwidth()) // 2
        y0 = (ymax - self.winfo_reqheight()) // 2
        self.geometry("+%d+%d" % (x0, y0))

    def createWidgets(self):
        # Implement in derived class
        pass

    def Destroy(self):
        self.master.update()
        self.master.deiconify()
        self.withdraw()


class PyrafSplash(SplashScreen):

    """PyRAF splash screen

    Contains an image and one or more text lines underneath.  The number
    of lines is determined by the value of the text argument, which may be
    a string (for a single line or, with embedded newlines, multiple lines)
    or a list of strings.  The text line(s) can be changed using the write()
    method.
    """

    def __init__(self, filename=logo, text=None, textcolor="blue", **kw):
        # look for file in both local directory and this script's directory
        if not os.path.exists(filename):
            tfilename = os.path.join(os.path.dirname(__file__),filename)
            if not os.path.exists(tfilename):
                raise ValueError("Splash image `%s' not found" % filename)
            filename = tfilename
        self.filename = filename
        self.nlines = 1
        self.textcolor = textcolor
        if text:
            if isinstance(text, type("")):
                text = text.split("\n")
            self.nlines = len(text)
            self.initialText = text
        else:
            self.initialText = [None]
        # put focus on this app (Mac only)
        self.__termWin = None
        if wutil.hasGraphics and wutil.WUTIL_ON_MAC:
            self.__termWin = wutil.getFocalWindowID() # the terminal window
            wutil.forceFocusToNewWindow()
        # create it
        SplashScreen.__init__(self, **kw)
        self.defaultCursor = self['cursor']
        self.bind("<Button>", self.killCursor)
        self.bind("<ButtonRelease>", self.Destroy)

    def createWidgets(self):
        """Create pyraf splash image"""
        self.img = Tkinter.PhotoImage(file=self.filename)
        width = self.img.width()+20
        iheight = self.img.height()
        height = iheight+10+15*self.nlines
        self.canvas = Tkinter.Canvas(self, width=width, height=height,
            background=self["background"])
        self.image = self.canvas.create_image(width//2, 5+iheight//2, image=self.img)
        self.text = self.nlines*[None]
        minx = 0
        font = ("helvetica", 12)
        for i in range(self.nlines):
            y = height-(self.nlines-i)*15+8
            tval = self.initialText[i] or ""
            self.text[i] = self.canvas.create_text(width//2, y,
                text=tval, fill=self.textcolor, font=font)
            minx = min(minx, self.canvas.bbox(self.text[i])[0])
        if minx<3:
            # expand window and recenter all items
            width = width+(3-minx)*2
            self.canvas.configure(width=width)
            self.canvas.coords(self.image, width//2, 5+iheight//2)
            for i in range(self.nlines):
                y = height-(self.nlines-i)*15+8
                self.canvas.coords(self.text[i], width//2, y)
        self.canvas.pack()

    def write(self, s):
        """Set text string"""
        if self.text is None:
            return
        if isinstance(s, type('')):
            s = s.split("\n")
        s = s[:len(self.text)]
        for i in range(len(s)):
            if s[i] is not None:
                self.canvas.itemconfigure(self.text[i], text=s[i])
        self.update_idletasks()

    def killCursor(self, event=None):
        """Set 'pirate' kill cursor on button down"""
        self['cursor'] = 'pirate'

    def Destroy(self, event=None):
        if event:
            # make sure button release occurred in window
            # Tkinter should take care of this but doesn't
            if event.x<0 or event.x>=self.winfo_width() or \
               event.y<0 or event.y>=self.winfo_height():
                self['cursor'] = self.defaultCursor
                return
        self.destroy()
        # disable future writes
        self.text = None
        self.update_idletasks()
        # put focus back on terminal (if set)
        if self.__termWin:
            wutil.setFocusTo(self.__termWin)

class IrafMonitorSplash(PyrafSplash):

    """PyRAF splash screen that also acts as IRAF task execution monitor

    Usually start this by calling the splash() function in this module.
    """

    def __init__(self, label="PyRAF Execution Monitor", **kw):
        PyrafSplash.__init__(self, text=[None, label], **kw)
        # self.stack tracks messages displayed in monitor
        self.stack = []
        import iraftask
        iraftask.executionMonitor = self.monitor

    def monitor(self, task=None):
        if task is None:
            # if arg is omitted, restore monitor message to previous value
            try:
                self.stack.pop()
                msg = self.stack[-1]
            except IndexError:
                msg = ""
        else:
            name = task.getName()
            if name != 'cl':
                if isinstance(task, IrafPkg):
                    msg = "Loading %s" % name
                else:
                    msg = "Running %s" % name
            else:
                # cl task message includes input file name
                try:
                    msg = "cl %s" % os.path.basename(sys.stdin.name)
                except AttributeError:
                    msg = "cl <pipe>"
            self.stack.append(msg)
        self.write(msg)

    def Destroy(self, event=None):
        """Shut down window and disable monitor"""
        import iraftask
        if iraftask.executionMonitor == self.monitor:
            iraftask.executionMonitor = None
        PyrafSplash.Destroy(self, event)

def splash(label="PyRAF Execution Monitor", background="LightYellow", **kw):
    """Display the PyRAF splash screen

    Silently does nothing if Tkinter is not usable.
    """
    if wutil.hasGraphics:
        try:
            return IrafMonitorSplash(label, background=background, **kw)
        except Tkinter.TclError:
            pass
    return None


if __name__ == "__main__":
    import time
    s = PyrafSplash()
    print "Sleeping 2 seconds..."
    time.sleep(2)
