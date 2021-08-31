"""gki metacode generating functions for use by Pyraf in generating
iraf gki metacode (primarily for interactive graphics)"""



from . import gki
from . import gwm
import numpy


def gkiCoord(ndcCoord):
    """Convert Normalized Device Coordinates to GKI coordinates"""
    return numpy.array(ndcCoord * (gki.GKI_MAX + 1), numpy.int16)


def text(textstring, x, y):
    """Return metacode for text string written at x,y"""
    gkiX = gkiCoord(x)
    gkiY = gkiCoord(y)
    data = numpy.frombuffer(textstring.encode('ascii'), numpy.int8)
    data = data.astype(numpy.int16)
    size = 6 + len(textstring)
    metacode = numpy.zeros(size, numpy.int16)
    metacode[0] = gki.BOI
    metacode[1] = gki.GKI_TEXT
    metacode[2] = size
    metacode[3:4] = gkiX
    metacode[4:5] = gkiY
    metacode[5] = len(textstring)
    metacode[6:] = data
    return metacode


def markCross(x,
              y,
              size=1.,
              xflag=0,
              yflag=0,
              linetype=1,
              linewidth=100,
              color=1):
    """Return metacode to plot a cross at the given position.

    Size = 1 => 10 pixels x 10 pixels.
    flags = 0 means normal, = 1 full screen.
    """

    gkiX = gkiCoord(x)
    gkiY = gkiCoord(y)
    gwidget = gwm.getActiveWindowGwidget()
    width = gwidget.winfo_width()
    height = gwidget.winfo_height()
    xsize = 5. / width
    ysize = 5. / height
    limit = gki.NDC_MAX
    if not xflag:
        gkiXmin = gkiCoord(max(x - xsize * size, 0.))
        gkiXmax = gkiCoord(min(x + xsize * size, limit))
    else:
        gkiXmin = gkiCoord(0.)
        gkiXmax = gkiCoord(limit)
    if not yflag:
        gkiYmin = gkiCoord(max(y - ysize * size, 0.))
        gkiYmax = gkiCoord(min(y + ysize * size, limit))
    else:
        gkiYmin = gkiCoord(0.)
        gkiYmax = gkiCoord(limit)
    metacode = numpy.zeros(22, numpy.int16)
    i = 0
    metacode[i] = gki.BOI
    metacode[i + 1] = gki.GKI_PLSET
    metacode[i + 2] = 6
    metacode[i + 3] = linetype
    metacode[i + 4] = linewidth
    metacode[i + 5] = color
    i = i + 6
    metacode[i] = gki.BOI
    metacode[i + 1] = gki.GKI_POLYLINE
    metacode[i + 2] = 8
    metacode[i + 3] = 2
    metacode[i + 4] = gkiX[0]
    metacode[i + 5] = gkiYmin[0]
    metacode[i + 6] = gkiX[0]
    metacode[i + 7] = gkiYmax[0]
    i = i + 8
    metacode[i] = gki.BOI
    metacode[i + 1] = gki.GKI_POLYLINE
    metacode[i + 2] = 8
    metacode[i + 3] = 2
    metacode[i + 4] = gkiXmin[0]
    metacode[i + 5] = gkiY[0]
    metacode[i + 6] = gkiXmax[0]
    metacode[i + 7] = gkiY[0]
    return metacode
