"""Implements text rendering using stroked font and Tkplot/X

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


import numpy
import math
from .textattrib import (CHARPATH_LEFT, CHARPATH_RIGHT, CHARPATH_UP,
                        CHARPATH_DOWN, JUSTIFIED_CENTER, JUSTIFIED_RIGHT,
                        JUSTIFIED_LEFT, JUSTIFIED_NORMAL, JUSTIFIED_TOP,
                        JUSTIFIED_BOTTOM)


def softText(win, x, y, textstr):

    # Generate text using software generated stroked fonts
    # except for the input x,y, all coordinates are in units of pixels

    # get unit font size
    ta = win.textAttributes
    hsize, fontAspect = ta.getFontSize()
    vsize = hsize * fontAspect
    # get current size in unit font units (!)
    fsize = ta.charSize
    # We draw the line at fontSizes less than 1/2! Get real.
    fsize = max(fsize, 0.5)
    # Character spacing depends on whether text is 'vertical' or 'horizontal'
    #  (relative to character orientation). Figure out what the character
    #  delta offset is in the coordinate system where charUp is the y axis.
    # First include added space if any
    hspace = fsize * hsize * (1. + ta.charSpace)
    vspace = fsize * vsize * (1. + ta.charSpace)
    if ta.textPath in (CHARPATH_LEFT, CHARPATH_RIGHT):
        dx = hspace
        if ta.textPath == CHARPATH_LEFT:
            dx = -dx
        dy = 0.
    else:
        dx = 0.
        dy = -vspace
        if ta.textPath == CHARPATH_UP:
            dy = -dy
    # Figure out 'path' size of the text string for use in justification
    xpath, ypath = (dx * (len(textstr) - 1), dy * (len(textstr) - 1))
    charUp = math.fmod(ta.charUp, 360.)
    if charUp < 0:
        charUp = charUp + 360.
    if ta.textPath == CHARPATH_RIGHT:
        textdir = math.fmod(charUp + 270, 360.)
    elif ta.textPath == CHARPATH_LEFT:
        textdir = math.fmod(charUp + 90, 360.)
    elif ta.textPath == CHARPATH_UP:
        textdir = charUp
    elif ta.textPath == CHARPATH_DOWN:
        textdir = math.fmod(charUp + 180, 360.)
    # IRAF definition of justification is a bit weird, justification is
    # for the text string relative to the window. So a rotated string will
    # be justified relative to the window horizontal and vertical, not the
    # string's. Thus the need to compute the offsets in window oriented
    # coordinates.
    up = 0. < textdir < 180.
    left = 90. < textdir < 270.
    deg2rad = math.pi / 180.
    cosv = math.cos((charUp - 90.) * deg2rad)
    sinv = math.sin((charUp - 90.) * deg2rad)
    xpathwin, ypathwin = (cosv * xpath - sinv * ypath,
                          sinv * xpath + cosv * ypath)
    xcharsize = fsize * max(abs(cosv * hsize + sinv * vsize),
                            abs(cosv * hsize - sinv * vsize))
    ycharsize = fsize * max(abs(-sinv * hsize + cosv * vsize),
                            abs(-sinv * hsize - cosv * vsize))
    xoffset, yoffset = (0., 0.)
    xcharoff, ycharoff = (0., 0.)
    if ta.textHorizontalJust == JUSTIFIED_CENTER:
        xoffset = -xpathwin / 2.
    elif ta.textHorizontalJust == JUSTIFIED_RIGHT:
        if not left:
            xoffset = -xpathwin
        xcharoff = -xcharsize / 2.
    elif ta.textHorizontalJust in (JUSTIFIED_LEFT, JUSTIFIED_NORMAL):
        if left:
            xoffset = xpathwin
        xcharoff = xcharsize / 2.
    if ta.textVerticalJust == JUSTIFIED_CENTER:
        yoffset = -ypathwin / 2.
    elif ta.textVerticalJust == JUSTIFIED_TOP:
        if up:
            yoffset = -ypathwin
        ycharoff = -ycharsize / 2.
    elif ta.textVerticalJust in (JUSTIFIED_BOTTOM, JUSTIFIED_NORMAL):
        if not up:
            yoffset = ypathwin
        ycharoff = ycharsize / 2.
    xNetOffset = xoffset + xcharoff
    yNetOffset = yoffset + ycharoff
    # note, these offsets presume that the origin of character coordinates
    # is the center of the character box. This will be taken into account
    # when drawing the character.

    # Now start drawing!
    gw = win.gwidget
    xwin = float(gw.winfo_width())
    ywin = float(gw.winfo_height())
    color = win.colorManager.setDrawingColor(ta.textColor)
    options = {"fill": color}
    size = fsize * hsize
    cosrot = numpy.cos((charUp - 90) * numpy.pi / 180)
    sinrot = numpy.sin((charUp - 90) * numpy.pi / 180)
    nchar = 0
    # The main event!
    for char in textstr:
        # draw character with origin at bottom left corner of character box
        charstrokes = ta.font[ord(char) - ord(' ')]
        for i in range(len(charstrokes[0])):
            vertex = numpy.zeros((len(charstrokes[0][i]), 2), numpy.float64)
            xf = size * charstrokes[0][i] / 27. - fsize * hsize / 2.
            yf = size * charstrokes[1][
                i] * fontAspect / 27. - fsize * vsize / 2.
            vertex[:, 0]= cosrot*(xf + nchar*dx) \
                - sinrot*(yf + nchar*dy) + xNetOffset + xwin*x
            vertex[:, 1] = ywin - (sinrot * (xf + nchar * dx) + cosrot *
                                   (yf + nchar * dy) + yNetOffset + ywin * y)
            gw.create_line(*(tuple(vertex.ravel().astype(numpy.int32))),
                           **options)
        nchar = nchar + 1
