"""irafgwcs.py: WCS handling for graphics

This contains some peculiar code to work around bugs in splot (and
possibly other tasks) where the WCS for an existing plot gets changed
before the plot is cleared.  I save the changed wcs in self.pending and
only commit the change when it appears to really be applicable.
"""


import numpy
import math
from stsci.tools.irafglobals import IrafError
from . import irafinst

# global vars
_IRAF64BIT = False
_WCS_RECORD_SIZE = 0

# constants
WCS_SLOTS = 16
WCSRCSZ_vOLD_32BIT = 22
WCSRCSZ_v215_32BIT = 24
WCSRCSZ_v215_64BIT = 48
LINEAR = 0
LOG = 1
ELOG = 2
DEFINED = 1
CLIP = 2  # needed for this?
NEWFORMAT = 4


def init_wcs_sizes(forceResetTo=None):
    """ Make sure global size var has been defined correctly """
    global _WCS_RECORD_SIZE, _IRAF64BIT
    # _WCS_RECORD_SIZE is 24 in v2.15, but was 22 in prior versions.
    # It counts in 2 byte integers, ie. it was 11 shorts when it was size=22.
    # Either way however, there are still only 11 pieces of information - in
    # the case of size=24, it is padded by/in IRAF.
    # The 64-bit case uses a size of 48.
    #
    # This function HAS TO BE FAST.  It is called multiple times during a
    # single plot.  Do not check IRAF version unless absolutely necessary.
    #
    # See ticket #156 and http://iraf.net/phpBB2/viewtopic.php?p=1466296

    if _WCS_RECORD_SIZE != 0 and forceResetTo is None:
        return  # been here already

    # Given a value for _WCS_RECORD_SIZE ?
    if forceResetTo:
        if forceResetTo not in (WCSRCSZ_vOLD_32BIT, WCSRCSZ_v215_32BIT,
                                WCSRCSZ_v215_64BIT):
            raise IrafError("Unexpected value for wcs record size: " +
                            str(forceResetTo))
        _WCS_RECORD_SIZE = forceResetTo
        _IRAF64BIT = _WCS_RECORD_SIZE == WCSRCSZ_v215_64BIT
        return

    # Define _WCS_RECORD_SIZE, based on IRAF ver - assume 32-bit for now
    vertup = irafinst.getIrafVerTup()
    _WCS_RECORD_SIZE = WCSRCSZ_vOLD_32BIT
    if vertup[0] > 2 or vertup[1] > 14:
        _WCS_RECORD_SIZE = WCSRCSZ_v215_32BIT


def elog(x):
    """Extended range log scale. Handles negative and positive values.

    values between 10 and -10 are linearly scaled, values outside are
    log scaled (with appropriate sign changes.
    """

    if x > 10:
        return math.log10(float(x))
    elif x > -10.:
        return x / 10.
    else:
        return -math.log10(-float(x))


class IrafGWcs:
    """Class to handle the IRAF Graphics World Coordinate System
    Structure"""

    def __init__(self, arg=None):
        self.wcs = None
        self.pending = None
        self.set(arg)

    def commit(self):
        if self.pending:
            self.wcs = self.pending
            self.pending = None

    def clearPending(self):
        self.pending = None

    def __bool__(self):
        self.commit()
        return self.wcs is not None

    def set(self, arg=None):
        """Set wcs from metacode stream"""
        init_wcs_sizes()
        if arg is None:
            # commit immediately if arg=None
            self.wcs = _setWCSDefault()
            self.pending = None
            # print "Default WCS set for plotting window."
            return

        # Even in v2.14, arg[] elements are of type int64, but here we cast to
        # int16 and assume we lose no data
        wcsStruct = arg[1:].astype(numpy.int16)

        # Every time set() is called, reset the wcs sizes.  We may be plotting
        # with old-compiled 32-bit tasks, then with new-compiled 32-bit tasks,
        # then with 64-bit tasks, all within the same PyRAF session.
        init_wcs_sizes(forceResetTo=int(arg[0] / (1. * WCS_SLOTS)))

        # Check that eveything is sized as expected
        if arg[0] != len(wcsStruct):
            raise IrafError(
                "Inconsistency in length of WCS graphics struct: " +
                str(arg[0]))
        if len(wcsStruct) != _WCS_RECORD_SIZE * WCS_SLOTS:
            raise IrafError("Unexpected length of WCS graphics struct: " +
                            str(len(wcsStruct)))

        # Read through the input to populate self.pending
        SZ = 2
        if _IRAF64BIT:
            SZ = 4
        self.pending = [None] * WCS_SLOTS
        for i in range(WCS_SLOTS):
            record = wcsStruct[_WCS_RECORD_SIZE * i:_WCS_RECORD_SIZE * (i + 1)]
            # read 8 4-byte floats from beginning of record
            fvals = numpy.frombuffer(record[:8 * SZ].tobytes(), numpy.float32)
            if _IRAF64BIT:
                # seems to send an extra 0-valued int32 after each 4 bytes
                fvalsView = fvals.reshape(-1, 2).transpose()
                if fvalsView[1].sum() != 0:
                    raise IrafError("Assumed WCS float padding is non-zero")
                fvals = fvalsView[0]
            # read 3 4-byte ints after that
            ivals = numpy.frombuffer(record[8 * SZ:11 * SZ].tobytes(),
                                     numpy.int32)
            if _IRAF64BIT:
                # seems to send an extra 0-valued int32 after each 4 bytes
                ivalsView = ivals.reshape(-1, 2).transpose()
                if ivalsView[1].sum() != 0:
                    raise IrafError("Assumed WCS int padding is non-zero")
                ivals = ivalsView[0]
            self.pending[i] = tuple(fvals) + tuple(ivals)
            if len(self.pending[i]) != 11:
                raise IrafError("Unexpected WCS struct record length: " +
                                str(len(self.pending[i])))
        if self.wcs is None:
            self.commit()

    def pack(self):
        """Return the WCS in the original IRAF format (in bytes-string)"""
        init_wcs_sizes()
        self.commit()
        wcsStruct = numpy.zeros(_WCS_RECORD_SIZE * WCS_SLOTS, numpy.int16)
        pad = b'\x00\x00\x00\x00'
        if _IRAF64BIT:
            pad = b'\x00\x00\x00\x00\x00\x00\x00\x00'
        for i in range(WCS_SLOTS):
            x = self.wcs[i]
            farr = numpy.array(x[:8], numpy.float32)
            iarr = numpy.array(x[8:11], numpy.int32)
            if _IRAF64BIT:
                # see notes in set(); adding 0-padding after every data point
                lenf = len(farr)  # should be 8
                farr_rs = farr.reshape(lenf,
                                       1)  # turn array into single column
                farr = numpy.append(farr_rs,
                                    numpy.zeros((lenf, 1), numpy.float32),
                                    axis=1)
                farr = farr.flatten()
                leni = len(iarr)  # should be 3
                iarr_rs = iarr.reshape(leni,
                                       1)  # turn array into single column
                iarr = numpy.append(iarr_rs,
                                    numpy.zeros((leni, 1), numpy.int32),
                                    axis=1)
                iarr = iarr.flatten()
            # end-pad?
            if len(farr) + len(iarr) == (_WCS_RECORD_SIZE // 2):
                pad = b''  # for IRAF2.14 or prior; all new vers need end-pad

            # Pack the wcsStruct - this will throw "ValueError: shape mismatch"
            # if the padding doesn't bring the size out to exactly the
            # correct length (_WCS_RECORD_SIZE)
            wcsStruct[_WCS_RECORD_SIZE*i:_WCS_RECORD_SIZE*(i+1)] = \
                numpy.frombuffer(farr.tobytes()+iarr.tobytes()+pad, numpy.int16)
        return wcsStruct.tobytes()

    def transform(self, x, y, wcsID):
        """Transform x,y to wcs coordinates for the given
        wcs (integer 0-16) and return as a 2-tuple"""

        self.commit()
        if wcsID == 0:
            return (x, y, wcsID)

        # Since transformation is defined by a direct linear (or log) mapping
        # between two rectangular windows, apply the usual linear
        # interpolation.

        # log scale does not affect the w numbers at all, a plot
        # ranging from 10 to 10,000 will have wx1,wx2 = (10,10000),
        # not (1,4)

        return (self.transform1d(coord=x, dimension='x', wcsID=wcsID),
                self.transform1d(coord=y, dimension='y', wcsID=wcsID), wcsID)

    def transform1d(self, coord, dimension, wcsID):

        wx1, wx2, wy1, wy2, sx1, sx2, sy1, sy2, xt, yt, flag = \
            self.wcs[wcsID-1]
        if dimension == 'x':
            w1, w2, s1, s2, type = wx1, wx2, sx1, sx2, xt
        elif dimension == 'y':
            w1, w2, s1, s2, type = wy1, wy2, sy1, sy2, yt
        if (s2 - s1) == 0.:
            raise IrafError("IRAF graphics WCS is singular!")
        fract = (coord - s1) / (s2 - s1)
        if type == LINEAR:
            val = (w2 - w1) * fract + w1
        elif type == LOG:
            lw2, lw1 = math.log10(w2), math.log10(w1)
            lval = (lw2 - lw1) * fract + lw1
            val = 10**lval
        elif type == ELOG:
            # Determine inverse mapping to determine corresponding values of s to w
            # This must be done to figure out which regime of the elog function the
            # specified point is in. (cs*ew + c0 = s)
            ew1, ew2 = elog(w1), elog(w2)
            cs = (s2 - s1) / (ew2 - ew1)
            c0 = s1 - cs * ew1
            # linear part is between ew = 1 and -1, so just map those to s
            s10p = cs + c0
            s10m = -cs + c0
            if coord > s10p:  # positive log area
                frac = (coord - s10p) / (s2 - s10p)
                val = 10. * (w2 / 10.)**frac
            elif coord >= s10m and coord <= s10p:  # linear area
                frac = (coord - s10m) / (s10p - s10m)
                val = frac * 20 - 10.
            else:  # negative log area
                frac = -(coord - s10m) / (s10m - s1)
                val = -10. * (-w1 / 10.)**frac
        else:
            raise IrafError("Unknown or unsupported axis plotting type")
        return val

    def _isWcsDefined(self, i):

        w = self.wcs[i]
        if w[-1] & NEWFORMAT:
            if w[-1] & DEFINED:
                return 1
            else:
                return 0
        else:
            if w[4] or w[5] or w[6] or w[7]:
                return 0
            else:
                return 1

    def get(self, x, y, wcsID=None):
        """Returned transformed values of x, y using given wcsID or
        closest WCS if none given.  Return a tuple (wx,wy,wnum) where
        wnum is the selected WCS (0 if none defined)."""

        self.commit()
        if wcsID is None:
            wcsID = self._getWCS(x, y)
        return self.transform(x, y, wcsID)

    def _getWCS(self, x, y):
        """Return the WCS (16 max possible) that should be used to
        transform x and y. Returns 0 if no WCS is defined."""

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

        indexlist = []
        # select subset of those wcs slots which are defined
        for i in range(len(self.wcs)):
            if self._isWcsDefined(i):
                indexlist.append(i)
        # if 0 or 1 found, we're done!
        if len(indexlist) == 1:
            return indexlist[0] + 1
        elif len(indexlist) == 0:
            return 0
        # look for viewports x,y is contained in
        newindexlist = []
        for i in indexlist:
            x1, x2, y1, y2 = self.wcs[i][4:8]
            if (x1 <= x <= x2) and (y1 <= y <= y2):
                newindexlist.append(i)
        # handle 3 cases
        if len(newindexlist) == 1:
            # unique, so done
            return newindexlist[0] + 1
        # have to find minimum distance either to centers or to edge
        dist = []
        if len(newindexlist) > 1:
            # multiple, find one with closest center
            for i in newindexlist:
                x1, x2, y1, y2 = self.wcs[i][4:8]
                xcen = (x1 + x2) / 2
                ycen = (y1 + y2) / 2
                dist.append((xcen - x)**2 + (ycen - y)**2)
        else:
            # none, now look for closest border
            newindexlist = indexlist
            for i in newindexlist:
                x1, x2, y1, y2 = self.wcs[i][4:8]
                xdelt = min([abs(x - x1), abs(x - x2)])
                ydelt = min([abs(y - y1), abs(y - y2)])
                if x1 <= x <= x2:
                    dist.append(ydelt**2)
                elif y1 <= y <= y2:
                    dist.append(xdelt**2)
                else:
                    dist.append(xdelt**2 + ydelt**2)
        # now return minimum distance viewport
        # reverse is used to give priority to highest WCS value
        newindexlist.reverse()
        dist.reverse()
        minDist = min(dist)
        return newindexlist[dist.index(minDist)] + 1


def _setWCSDefault():
    """Define default WCS for STDGRAPH plotting area."""
    # set 8 4 byte floats
    farr = numpy.array([0., 1., 0., 1., 0., 1., 0., 1.], numpy.float32)
    # set 3 4 byte ints
    iarr = numpy.array([LINEAR, LINEAR, CLIP + NEWFORMAT], numpy.int32)
    wcsarr = tuple(farr) + tuple(iarr)

    wcs = []
    for i in range(WCS_SLOTS):
        wcs.append(wcsarr)

    return wcs
