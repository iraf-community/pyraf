"""Implements text rendering using stroked font and OpenGL

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


from . import fontdata

CHARPATH_LEFT = 2
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

    def set(self,
            charUp=90.,
            charSize=1.,
            charSpace=0.,
            textPath=CHARPATH_RIGHT,
            textHorizontalJust=JUSTIFIED_NORMAL,
            textVerticalJust=JUSTIFIED_NORMAL,
            textFont=FONT_ROMAN,
            textQuality=FQUALITY_NORMAL,
            textColor=1):

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
