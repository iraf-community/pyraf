"""gki metacode generating functions for use by Pyraf in generating
iraf gki metacode (primarily for interactive graphics)"""

import gki, gwm
import Numeric

def gkiCoord(ndcCoord):
	"""Convert Normalized Device Coordinates to GKI coordinates"""
	return Numeric.array(ndcCoord * gki.GKI_MAX,Numeric.Int16)

def appendMetacode(metacode):
	gki.kernel.append(metacode,1)

def undo():
	gki.kernel.undoN(1)

def redrawOriginal():
	gki.kernel.redrawOriginal()

def text(textstring, x, y):
	gkiX = gkiCoord(x)
	gkiY = gkiCoord(y)
	data = Numeric.fromstring(textstring,Numeric.Int8)
	data = data.astype(Numeric.Int16)
	size = 6 + len(textstring)
	metacode = Numeric.zeros(size,Numeric.Int16)
	metacode[0] = gki.BOI
	metacode[1] = gki.GKI_TEXT
	metacode[2] = size
	metacode[3:4] = gkiX
	metacode[4:5] = gkiY
	metacode[5] = len(textstring)
	metacode[6:] = data
	return metacode

def markCross(x, y, size=1., xflag=0, yflag=0):
	"""plot a cross at the given position. Size =1 => 10 pixels x 10 pixels.
	flags = 0 means normal, = 1 full screen"""

	gkiX = gkiCoord(x)
	gkiY = gkiCoord(y)
	gwidget = gwm.getActiveWindow()
	width = gwidget.winfo_width()
	height = gwidget.winfo_height()
	xsize = 5./width
	ysize = 5./height
	if not xflag:
		gkiXmin = gkiCoord(max(x - xsize*size, 0.))
		gkiXmax = gkiCoord(min(x + xsize*size, 1.))
	else:
		gkiXmin = gkiCoord(0.)
		gkiXmax = gkiCoord(1.)
	if not yflag:
		gkiYmin = gkiCoord(max(y - ysize*size, 0.))
		gkiYmax = gkiCoord(min(y + ysize*size, 1.))
	else:
		gkiYmin = gkiCoord(0.)
		gkiYmax = gkiCoord(1.)
	metacode = Numeric.zeros(16,Numeric.Int16)
	metacode[0] = gki.BOI
	metacode[8] = gki.BOI
	metacode[1] = gki.GKI_POLYLINE
	metacode[9] = gki.GKI_POLYLINE
	metacode[2] = 8
	metacode[10]= 8
	metacode[3] = 2
	metacode[11]= 2
	metacode[4] = gkiX[0]
	metacode[5] = gkiYmin[0]
	metacode[6] = gkiX[0]
	metacode[7] = gkiYmax[0]
	metacode[12]= gkiXmin[0]
	metacode[13]= gkiY[0]
	metacode[14]= gkiXmax[0]
	metacode[15]= gkiY[0]
	return metacode
