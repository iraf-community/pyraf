"""
implement IRAF gcur functionality

$Id$
"""

import string, os, sys, Numeric, Tkinter
import gwm, wutil, iraf, openglcmd, gki, irafutils

# The following class attempts to emulate the standard IRAF gcursor
# mode of operation. That is to say, it is basically a keyboard driven
# system that uses the same keys that IRAF does for the same purposes.
# The keyboard I/O will use Tkinter event handling instead of terminal
# I/O primarily because it is simpler and it is necessary to use Tkinter
# anyway.

class Gcursor:

    """This handles the classical IRAF gcur mode"""

    def __init__(self, window):

        self.x = 0
        self.y = 0
        self.top = None
        self.window = window
        self.gwidget = window.gwidget
        self.top = window.top
        self.markcur = 0
        self.retString = None
        self.active = 0
        self.eof = None

    def __call__(self): return self.startCursorMode()

    def startCursorMode(self):

        # bind event handling from this graphics window
        self.window.raiseWindow()
        self.window.update()
        wutil.focusController.setFocusTo(self.window)
        self.cursorOn()
        self.bind()
        activate = self.window.getStdout() is None
        if activate:
            self.window.control_reactivatews(None)
        try:
            self.active = 1
            self.eof = None
            self.top.mainloop()
        finally:
            try:
                self.active = 0
                self.unbind()
                self.cursorOff()
            except Tkinter.TclError:
                pass
        # EOF flag can get set by window-close event or 'I' keystroke
        # It should be set to string message
        if self.eof:
            if self.eof[:9] == 'interrupt':
                raise KeyboardInterrupt(self.eof)
            else:
                raise EOFError(self.eof)
        if activate:
            self.window.control_deactivatews(None)
        return self.retString

    def cursorOn(self):
        """Turn cross-hair cursor on"""
        if self.gwidget.lastX is not None:
            self.gwidget.activateSWCursor(
                    (self.gwidget.lastX+0.5)/self.gwidget.winfo_width(),
                    (self.gwidget.lastY+0.5)/self.gwidget.winfo_height())
        else:
            self.gwidget.activateSWCursor()

    def cursorOff(self):
        """Turn cross-hair cursor off"""
        self.gwidget.deactivateSWCursor()
        self.gwidget.lastX = self.x
        self.gwidget.lastY = self.y

    def bind(self):

        self.gwidget.bind("<Button-1>",self.getMousePosition)
        self.gwidget.bind("<Key>",self.getKey)
        self.gwidget.bind("<Up>",self.moveUp)
        self.gwidget.bind("<Down>",self.moveDown)
        self.gwidget.bind("<Right>",self.moveRight)
        self.gwidget.bind("<Left>",self.moveLeft)
        self.gwidget.bind("<Shift-Up>",self.moveUpBig)
        self.gwidget.bind("<Shift-Down>",self.moveDownBig)
        self.gwidget.bind("<Shift-Right>",self.moveRightBig)
        self.gwidget.bind("<Shift-Left>",self.moveLeftBig)

    def unbind(self):

        self.gwidget.unbind("<Button-1>")
        self.gwidget.unbind("<Key>")
        self.gwidget.unbind("<Up>")
        self.gwidget.unbind("<Down>")
        self.gwidget.unbind("<Right>")
        self.gwidget.unbind("<Left>")
        self.gwidget.unbind("<Shift-Up>")
        self.gwidget.unbind("<Shift-Down>")
        self.gwidget.unbind("<Shift-Right>")
        self.gwidget.unbind("<Shift-Left>")

    def getNDCCursorPos(self):

        """Do an immediate cursor read and return coordinates in
        NDC coordinates"""

        gwidget = self.gwidget
        sx = gwidget.winfo_pointerx() - gwidget.winfo_rootx()
        sy = gwidget.winfo_pointery() - gwidget.winfo_rooty()
        self.x = sx
        self.y = sy
        # get current window size
        winSizeX = gwidget.winfo_width()
        winSizeY = gwidget.winfo_height()
        ndcX = (sx+0.5)/winSizeX
        ndcY = (winSizeY-0.5-sy)/winSizeY
        return ndcX, ndcY

    def getMousePosition(self, event):

        self.x = event.x
        self.y = event.y

    def moveCursorRelative(self, event, deltaX, deltaY):

        gwidget = self.gwidget
        # only force focus if window is viewable
        if not wutil.isViewable(self.top.winfo_id()):
            return
        # if no previous position, ignore
        newX = event.x + deltaX
        newY = event.y + deltaY
        if newX < 0:
            newX = 0
        if newY < 0:
            newY = 0
        if newX >= gwidget.winfo_width():
            newX = gwidget.winfo_width() - 1
        if newY >= gwidget.winfo_height():
            newY = gwidget.winfo_height() - 1
        wutil.moveCursorTo(gwidget.winfo_id(),newX,newY)

    def moveUp(self, event): self.moveCursorRelative(event, 0, -1)
    def moveDown(self, event): self.moveCursorRelative(event, 0, 1)
    def moveRight(self, event): self.moveCursorRelative(event, 1, 0)
    def moveLeft(self, event): self.moveCursorRelative(event, -1, 0)
    def moveUpBig(self, event): self.moveCursorRelative(event, 0, -5)
    def moveDownBig(self, event): self.moveCursorRelative(event, 0, 5)
    def moveRightBig(self, event): self.moveCursorRelative(event, 5, 0)
    def moveLeftBig(self, event): self.moveCursorRelative(event, -5, 0)

    def writeString(self, s):
        """Write a string to status line"""
        stdout = self.window.getStdout(default=sys.stdout)
        stdout.write(s)
        stdout.flush()

    def readString(self, prompt=""):
        """Prompt and read a string"""
        self.writeString(prompt)
        stdin = self.window.getStdin(default=sys.stdin)
        return irafutils.tkreadline(stdin)[:-1]

    def getKey(self, event):

        # The main character handling routine where no special keys
        # are used (e.g., control or arrow keys)
        key = event.char
        if not key:
            # ignore keypresses of non printable characters
            return
        x,y = self.getNDCCursorPos()
        if self.markcur and key not in 'q?:=UR':
            metacode = openglcmd.markCross(x,y)
            self.appendMetacode(metacode)
        if key == ':':
            colonString = self.readString(prompt=": ")
            if colonString:
                if colonString[0] == '.':
                    if colonString[1:] == 'markcur+':
                        self.markcur = 1
                    elif colonString[1:] == 'markcur-':
                        self.markcur = 0
                    elif colonString[1:] == 'markcur':
                        self.markcur = not self.markcur
                    else:
                        self.writeString("Unimplemented CL gcur `:%s'" % colonString)
                else:
                    self._setRetString(key,x,y,colonString)
        elif key == '=':
            # snap command - print the plot
            gki.printPlot(self.window)
        elif key in string.uppercase:
            if key == 'I':
                # I is equivalent to keyboard interrupt
                self.window.gcurTerminate("interrupted by `I' keyboard command")
            elif key == 'R':
                self.window.redrawOriginal()
            elif key == 'T':
                textString = self.readString(prompt="Annotation string: ")
                metacode = openglcmd.text(textString,x,y)
                self.appendMetacode(metacode)
            elif key == 'U':
                self.window.undoN()
            elif key == 'C':
                wx,wy,gwcs = self._convertXY(x,y)
                self.writeString("%g %g" % (wx,wy))
            else:
                self.writeString("Unimplemented CL gcur command `%s'" % key)
        else:
            self._setRetString(key,x,y,"")

    def appendMetacode(self, metacode):
        # appended code is undoable
        self.window.append(metacode, 1)

    def _convertXY(self, x, y):
        """Returns x,y,gwcs converted to physical units using current WCS"""
        wcs = self.window.wcs
        if wcs:
            return wcs.get(x,y)
        else:
            return (x,y,0)

    def _setRetString(self, key, x, y, colonString):

        wx,wy,gwcs = self._convertXY(x,y)
        if key <= ' ' or ord(key) >= 127:
            key = '\\%03o' % ord(key)
        self.retString = str(wx)+' '+str(wy)+' '+str(gwcs)+' '+key
        if colonString:
            self.retString = self.retString +' '+colonString
        self.top.quit() # time to go!
