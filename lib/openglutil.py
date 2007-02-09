"""
OpenGL utility functions not part of the OpenGL distribution.
Presently this only handles compatiblity issues between pyopengl
v1.5 and v2.0.

$Id$
"""

import OpenGL
from OpenGL.GL import *
import numpy

if OpenGL.__version__[0] == '1':
    oldpyopengl = 1

    def glPlot(vertices, plottype):
        npts = len(vertices)/2
        glBegin(plottype)
        glVertex(numpy.reshape(vertices,(npts, 2)))
        glEnd()

else:
    oldpyopengl = 0

    def glPlot(vertices, plottype):
        npts = len(vertices)/2
        glVertexPointerd(numpy.reshape(vertices,(npts, 2)))
        glDrawArrays(plottype, 0, npts)
