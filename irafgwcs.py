import struct, Numeric, math

WCS_SLOTS = 16
WCS_RECORD_SIZE = 22  # (in 2 byte integers)
LINEAR = 0
LOG = 1
ELOG = 2 # ??? won't implement, for now
DEFINED = 1
CLIP = 2 # needed for this?
NEWFORMAT = 4 

class IrafGWcs:

	"""Class to handle the IRAF Graphics World Coordinate System
	Structure"""

	def __init__(self, arg):

		wcsStruct = arg[1:]
		if arg[0] != len(wcsStruct):
			raise "Error: inconsistency in length of WCS graphics structure"
		self.wcs = [None]*WCS_SLOTS
		for i in xrange(16):
			self.wcs[i] = struct.unpack('fffffffflll',
								   wcsStruct[WCS_RECORD_SIZE*i:
											 WCS_RECORD_SIZE*(i+1)].tostring())
		
	def transform(self, x, y, wcsID):

		"""Transform x,y to wcs coordinates for the given
		wcs (integer 0-16) and return as a 2-tuple"""

		if wcsID == 0: return x, y

		# Since transformation is defined by a direct linear (or log) mapping
		# between two rectangular windows, apply the usual linear
		# interpolation.

		# log scale does not affect the w numbers at all, a plot
		# ranging from 10 to 10,000 will have wx1,wx2 = (10,10000),
		# not (1,4)

		return (self.transform1d(coord=x,dimension='x',wcsID=wcsID),
				self.transform1d(coord=y,dimension='y',wcsID=wcsID),
				wcsID)
	
	def transform1d(self, coord, dimension, wcsID):
		
		wx1, wx2, wy1, wy2, sx1, sx2, sy1, sy2, xt, yt, flag = \
			 self.wcs[wcsID-1]
		if dimension == 'x':
			w1,w2,s1,s2,type = wx1,wx2,sx1,sx2,xt
		elif dimension == 'y':
			w1,w2,s1,s2,type = wy1,wy2,sy1,sy2,yt
		if (s2-s1) == 0.:
			raise "Error, IRAF graphics WCS is singular!"
		fract = (coord-s1)/(s2-s1)
		if type == LINEAR:
			val = (w2-w1)*fract + w1
		elif type == LOG:
			lw2, lw1 = math.log10(w2), math.log10(w1)
			lval = (lw2-lw1)*fract + lw1
			val = 10**lval
		else:
			raise "Error, Unknown or unsupported axis plotting type"
		return val
	
	def _isWcsDefined(self, i):
	
		w = self.wcs[i]
		if w[-1] & NEWFORMAT:
			if w[-1] & DEFINED: return 1
			else: return 0
		else:
			if w[4] or w[5] or w[6] or w[7]: return 0
			else: return 1
	
	def get(self, x, y, wcsID=None):

		"""Find the WCS (16 max possible) that should be used to
		transform x and y. return as a tuple (wx,wy, wnum) where
		wnum is the selected WCS (0 if none defined). The optional
		parameter wcsID is used to force a wcs selection"""

		# The algorithm for determining which of multiple wcs's
		# should be selected is thus (and is different in one
		# respect from the IRAF cl):
		#
		# 1 determine which viewports x,y fall in
		# 2 if more than one, the tie is broken by choosing the one
		#   whose center is closer.
		# 3 in case of ties, the higher number wcs is chosen.
		# 4 if inside none, the distance is computed to the nearest part 
		#   of the viewport border, the one that is closest is chosen
		# 5 in case of ties, the higher number wcs is chosen.
		
		index = []
		newindex = []
		dist = []
		if wcsID: return self.transform(x,y,wcsID)
		# select subset of those wcs slots which are defined
		for i in xrange(len(self.wcs)):
			if self._isWcsDefined(i): index.append(i)
		# if 0 or 1 found, we're done!
		if len(index) == 1: return self.transform(x,y,index[0]+1)
		if len(index) == 0: return (x,y,0)
		# look for viewports x,y is contained in
		for i in index:
			x1,x2,y1,y2 = self.wcs[i][4:8]
			if (x1 <= x <= x2) and (y1 <= y <= y2): newindex.append(i)
		# handle 3 cases
		if len(newindex) == 1: return self.transform(x,y,newindex[0]+1)
		# unique, so done
		elif len(newindex) == 0:
			# none, now look for closest border
			for i in newindex:
				x1,x2,y1,y2 = self.wcs[4:8]
				xdelt = min([abs(x-x1),abs(x-x2)])
				ydelt = min([abs(y-y1),abs(y-y2)])
				xout = not (x1 <= x <= x2)
				yout = not (y1 <= y <= y2)
				if xout and yout: dist.append(xdelt**2 + ydelt**2)
				elif xout: dist.append(ydelt**2)
				else: dist.append(xdelt**2)
		else: 
			# multiple, find one with closest center
			for i in newindex:
				x1,x2,y1,y2 = self.wcs[i][4:8]
				xcen,ycen = (x1+x2)/2,(y1+y2)/2
				dist.append((xcen-x)**2 + (ycen-y)**2)
			minDist = min(dist)
		# now return transform of minimum distance viewport
		#  reverse is used to give priority to highest value 
		return self.transform(x,y,dist.reverse.index(minDist)+1)
			
