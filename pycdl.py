"""Python wrapper around the NOAO Client Display Library to interact
with SAOIMAGE and XIMTOOL image servers"""

from cdl import *
import Numeric
n = Numeric

def cdl_arrayPrep(image):
	if type(image) != n.ArrayType:
		raise TypeError("must be a Numeric Array")
	if len(image.shape) != 2:
		raise TypeError("must be a two dimensional Numeric Array")
	# since cdl autoscaling automatically writes over the image given
	# as an argument, safest thing to do is to copy it.
	timage = n.array(image,copy=1)
	tc = timage.typecode()
	if tc not in (n.Int, n.Int8, n.Int16, n.Int32, n.Float,
				  n.Float32, n.Float64):
		raise TypeError("Item type of array is not supported")
	bitpix = timage.itemsize()*8
	if timage.typecode() in (n.Float32, n.Float64):
		bitpix = -bitpix
	ny, nx = timage.shape
	return (timage, nx, ny, bitpix)

def cdl_displayPix(displayDevPtr, image, frame, fbconfig, zscale):
	timage, nx, ny, bitpix = cdl_arrayPrep(image)
	if not zscale and timage.typecode() != n.Int8:
		raise TypeError("CDL routines too stupid to deal with non-byte" +
						" images without zscaling option")
	xcdl_displayPix(displayDevPtr, timage, nx, ny, bitpix,
				   frame, fbconfig, zscale)
	
def cdl_computeZscale(displayDevPtr, image):
	timage, nx, ny, bitpix = cdl_arrayPrep(image)
	return xcdl_computeZscale(displayDevPtr, timage, nx, ny, bitpix)

def cdl_printPix(displayDevPtr, cmd, image, annotate):
	timage, nx, ny, bitpix = cdl_arrayPrep(image)
	xcdl_printPix(displayDevPtr, cmd, timage, nx, ny, annotate)
	
def cdl_printPixToFile(displayDevPtr, filename, image, annotate):
	timage, nx, ny, bitpix = cdl_arrayPrep(image)
	xcdl_printPixToFile(displayDevPtr, filename, timage, nx, ny, annotate)
	
def cdl_writeSubRaster(displayDevPtr, lx, ly, image):
	timage, nx, ny, bitpix = cdl_arrayPrep(image)
	if bitpix != 8:
		raise TypeError("Numeric Array must be of Int8 (byte) type")
	xcdl_writeSubRaster(displayDevPtr, lx, ly, nx, ny, timage)

#int cdl_displayPix(CDLPtr cdl, uchar *pix_in, int nx, int ny, int bitpix, int frame, int fbconfig, int zscale);
#void cdl_computeZscale(CDLPtr cdl, uchar *pix_in, int nx, int ny, int bitpix, float *z1, float *z2);
#int cdl_printPix(CDLPtr cdl, char *cmd, uchar *pix_in, int nx, int ny, int annotate);
#int cdl_printPixToFile(CDLPtr cdl, char *fname, uchar *pix_in, int nx, int ny, int annotate);
#int cdl_writeSubRaster(CDLPtr cdl, int lx, int ly, int nx, int ny, uchar *pix_in);



# int cdl_readImage(CDLPtr cdl, uchar **pix, int *nx, int *ny);
# int cdl_readFrameBuffer(CDLPtr cdl, uchar **pix, int *nx, int *ny);
# void cdl_zscaleImage(CDLPtr cdl, uchar **pix, int nx, int ny, int bitpix, flo# int cdl_readSubRaster(CDLPtr cdl, int lx, int ly, int nx, int ny, uchar **pix);
