"""Implements text rendering using stroked font and OpenGL

$Id$
"""

"""
General description and discussion about the assumptions of how
text is to be handled. This will be a phased implementation and
initially, some IRAF text features may not be implmented

From experiments, these are some properties of IRAF text:

1) Text does not zoom with plot. (affected by gki coordinate transformation
   only in cl level manipulations. Does not affect this code.
2) Escape sequences for fonts do not appear to match the documentation
   or code comments. Greek characters do not appear to be supported,
   nor does bold text. Will eventually support here though
3) Characters do not retain a constant aspect ratio. It appears to
   change with the aspect ratio of the screen. Either mode can be
   chosen
4) Characters are fixed width font. Same here, for now (and maybe forever).

This implementation will allow some of these properties to be overriden
by a system-wide configuration state. See gkiopengl.py

"""

import fontdata
import Numeric
import math
from OpenGL.GL import *
import openglutil

CHARPATH_LEFT  = 2
CHARPATH_RIGHT = 3
CHARPATH_UP = 4
CHARPATH_DOWN = 5
JUSTIFIED_NORMAL = 0
JUSTIFIED_CENTER = 1
JUSTIFIED_TOP = 6
JUSTIFIED_BOTTOM = 7
JUSTIFIED_LEFT = 2
JUSTIFIED_RIGHT = 3
FONT_ROMAN = 8
FONT_GREEK = 9
FONT_ITALIC = 10
FONT_BOLD = 11
FQUALITY_NORMAL = 0
FQUALITY_LOW = 12
FQUALITY_MEDIUM = 13
FQUALITY_HIGH = 14

class TextAttributes:

    # Used as a structure definition basically, perhaps it should be made
    # more sophisticated.
    def __init__(self):

        self.charUp = 90.
        self.charSize = 1.
        self.charSpace = 0.
        self.textPath = CHARPATH_RIGHT
        self.textHorizontalJust = JUSTIFIED_NORMAL
        self.textVerticalJust = JUSTIFIED_NORMAL
        self.textFont = FONT_ROMAN
        self.textQuality = FQUALITY_NORMAL
        self.textColor = 1
        self.font = fontdata.font1
        # Place to keep font size and aspect for current window dimensions
        self.hFontSize = None
        self.fontAspect = None

    def set(self,charUp=90., charSize=1.,charSpace=0.,
            textPath=CHARPATH_RIGHT, textHorizontalJust=JUSTIFIED_NORMAL,
            textVerticalJust=JUSTIFIED_NORMAL, textFont=FONT_ROMAN,
            textQuality=FQUALITY_NORMAL, textColor=1):

        self.charUp = charUp
        self.charSize = charSize
        self.charSpace = charSpace
        self.textPath = textPath
        self.textHorizontalJust = textHorizontalJust
        self.textVerticalJust = textVerticalJust
        self.textFont = textFont
        self.textQuality = textQuality
        self.textColor = textColor
        # Place to keep font size and aspect for current window dimensions

    def setFontSize(self, win):

        """Set the unit font size for a given window using the iraf
        configuration parameters contained in an attribute class"""

        conf = win.irafGkiConfig
        self.hFontSize, self.fontAspect = conf.fontSize(win.gwidget)

    def getFontSize(self):

        return self.hFontSize, self.fontAspect

def softText(win,x,y,textstr):

    # Generate text using software generated stroked fonts
    # except for the input x,y, all coordinates are in units of pixels

    # get unit font size
    ta = win.textAttributes
    hsize, fontAspect = ta.getFontSize()
    vsize = hsize * fontAspect
    # get current size in unit font units (!)
    fsize = ta.charSize
    # We draw the line at fontSizes less than 1/2! Get real.
    fsize = max(fsize,0.5)
    # Character spacing depends on whether text is 'vertical' or 'horizontal'
    #  (relative to character orientation). Figure out what the character
    #  delta offset is in the coordinate system where charUp is the y axis.
    # First include added space if any
    hspace = fsize * hsize * (1. + ta.charSpace)
    vspace = fsize * vsize * (1. + ta.charSpace)
    if ta.textPath in (CHARPATH_LEFT, CHARPATH_RIGHT):
        dx = hspace
        if ta.textPath == CHARPATH_LEFT: dx = -dx
        dy = 0.
    else:
        dx = 0.
        dy = -vspace
        if ta.textPath == CHARPATH_UP: dy = -dy
    # Figure out 'path' size of the text string for use in justification
    xpath,ypath = (dx*(len(textstr)-1),dy*(len(textstr)-1))
    charUp = math.fmod(ta.charUp, 360.)
    if charUp < 0: charUp = charUp + 360.
    if ta.textPath == CHARPATH_RIGHT:
        textdir = math.fmod(charUp+270,360.)
    elif ta.textPath == CHARPATH_LEFT:
        textdir = math.fmod(charUp+90,360.)
    elif ta.textPath ==     CHARPATH_UP:
        textdir = charUp
    elif ta.textPath ==     CHARPATH_DOWN:
        textdir = math.fmod(charUp+180,360.)
    # IRAF definition of justification is a bit weird, justification is
    # for the text string relative to the window. So a rotated string will
    # be justified relative to the window horizontal and vertical, not the
    # string's. Thus the need to compute the offsets in window oriented
    # coordinates.
    up = 0. < textdir < 180.
    left = 90. < textdir < 270.
    deg2rad = math.pi/180.
    cosv = math.cos((charUp-90.)*deg2rad)
    sinv = math.sin((charUp-90.)*deg2rad)
    xpathwin, ypathwin = (cosv*xpath-sinv*ypath,sinv*xpath+cosv*ypath)
    xcharsize = fsize * max(abs(cosv*hsize+sinv*vsize),
                                            abs(cosv*hsize-sinv*vsize))
    ycharsize = fsize * max(abs(-sinv*hsize+cosv*vsize),
                                            abs(-sinv*hsize-cosv*vsize))
    xoffset, yoffset = (0., 0.)
    xcharoff, ycharoff = (0., 0.)
    if ta.textHorizontalJust == JUSTIFIED_CENTER:
        xoffset = -xpathwin/2.
    elif ta.textHorizontalJust == JUSTIFIED_RIGHT:
        if not left: xoffset = -xpathwin
        xcharoff = -xcharsize/2.
    elif ta.textHorizontalJust in (JUSTIFIED_LEFT,JUSTIFIED_NORMAL):
        if left: xoffset = xpathwin
        xcharoff = xcharsize/2.
    if ta.textVerticalJust == JUSTIFIED_CENTER:
        yoffset = -ypathwin/2.
    elif ta.textVerticalJust == JUSTIFIED_TOP:
        if up: yoffset = -ypathwin
        ycharoff = -ycharsize/2.
    elif ta.textVerticalJust in (JUSTIFIED_BOTTOM, JUSTIFIED_NORMAL):
        if not up: yoffset = ypathwin
        ycharoff = ycharsize/2.
    xNetOffset = xoffset + xcharoff
    yNetOffset = yoffset + ycharoff
    # note, these offsets presume that the origin of character coordinates
    # is the center of the character box. This will be taken into account
    # when drawing the character.

    # Now start drawing!

    # Translate drawing coordinates to specified x,y and rescale to pixel units
    glMatrixMode(GL_MODELVIEW)
    glPushMatrix()
    try:
        glTranslatef(x,y,0.)
        xwin = float(win.gwidget.winfo_width())
        ywin = float(win.gwidget.winfo_height())
        glScalef(1./xwin,1./ywin,1.)
        # Apply above computed pixel offsets
        glTranslatef(xNetOffset,yNetOffset,0.)
        # Rotate so that charUp is aligned with x-axis (expects angle in deg!)
        glRotatef(charUp-90.,0.,0.,1.)
        # Apply offset to take into account our fonts have origin 0 at bottom
        #   left hand corner, not center as assumed above.
        glTranslatef(-fsize*hsize/2.,-fsize*vsize/2.,0)
        glLineWidth(1.0)
        win.colorManager.setDrawingColor(ta.textColor)
        # The main event!
        for char in textstr:
            drawchar(char,ta.font,fsize*hsize,fontAspect)
            glTranslatef(dx,dy,0.)
    finally:
        glPopMatrix()

def drawchar(char,font,size,aspect):

    # draw character with origin at bottom left corner of character box
    charstrokes = font[ord(char)-ord(' ')]
    for i in xrange(len(charstrokes[0])):
        vertex = Numeric.zeros((len(charstrokes[0][i]),2),Numeric.Float64)
        vertex[:,0] = size * charstrokes[0][i]/27.
        vertex[:,1] = size * charstrokes[1][i] * aspect/27.
        openglutil.glPlot(vertex.flat, GL_LINE_STRIP)
