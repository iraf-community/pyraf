import numpy
from matplotlib.lines import Line2D

from pyraf import gki
from pyraf import GkiMpl


# Minimal stand-ins for GUI and plotting objects used by GkiMplKernel.
# They allow these tests to run without creating a real Tk window.

class DummyWcs:
    def commit(self):
        pass


class DummyColorManager:
    def setDrawingColor(self, color):
        return "black"


def make_kernel():
    """Create a minimal GkiMplKernel without opening a Tk window."""
    kernel = object.__new__(GkiMpl.GkiMplKernel)

    kernel._GkiMplKernel__normLines = []
    kernel._GkiMplKernel__normPatches = []
    kernel._GkiMplKernel__skipPlotAppends = False
    kernel._GkiMplKernel__allowDrawing = True
    kernel.drawBuffer = gki.DrawBuffer()
    kernel.wcs = DummyWcs()
    kernel.colorManager = DummyColorManager()
    kernel.lineAttributes = gki.LineAttributes()
    kernel.markerAttributes = gki.MarkerAttributes()
    kernel.markerAttributes.color = "black"

    return kernel


def polyline_arg(*points):
    """Create a GKI polyline argument from integer GKI coordinates."""
    coordinates = numpy.asarray(points, dtype=numpy.int16)

    return numpy.concatenate(
        (
            numpy.array([len(points)], dtype=numpy.int16),
            coordinates.ravel(),
        )
    )


def plset_arg(linestyle):
    """Create the relevant part of a GKI PLSET argument."""
    return numpy.array(
        [linestyle, gki.GKI_FLOAT_FACTOR, 1],
        dtype=numpy.int16,
    )


def test_clear_polyline():
    """Regression test for #206"""
    kernel = make_kernel()

    line = polyline_arg((1000, 2000), (3000, 4000))

    kernel.gki_plset(plset_arg(1))
    kernel.gki_polyline(line)

    assert len(kernel._GkiMplKernel__normLines) == 1

    kernel.gki_plset(plset_arg(0))
    kernel.gki_polyline(line)

    assert kernel._GkiMplKernel__normLines == []


def test_clear_polyline_keeps_other_lines():
    """Regression test for #206"""
    kernel = make_kernel()

    line_a = polyline_arg((1000, 2000), (3000, 4000))
    line_b = polyline_arg((5000, 6000), (7000, 8000))

    kernel.gki_plset(plset_arg(1))
    kernel.gki_polyline(line_a)
    kernel.gki_polyline(line_b)

    kernel.gki_plset(plset_arg(0))
    kernel.gki_polyline(line_a)

    lines = kernel._GkiMplKernel__normLines

    assert len(lines) == 1
    assert isinstance(lines[0], Line2D)

    expected = gki.ndc(line_b[1:]).reshape(line_b[0], 2)

    numpy.testing.assert_array_equal(lines[0].get_xdata(), expected[:, 0])
    numpy.testing.assert_array_equal(lines[0].get_ydata(), expected[:, 1])


def test_clear_polyline_does_not_remove_marker():
    """Regression test for #206"""
    kernel = make_kernel()
    line = polyline_arg((1000, 2000), (3000, 4000))

    kernel.gki_polymarker(line)
    marker = kernel._GkiMplKernel__normLines[0]

    kernel.gki_plset(plset_arg(0))
    kernel.gki_polyline(line)

    lines = kernel._GkiMplKernel__normLines

    assert len(lines) == 1
    assert lines[0] is marker


def test_clear_polyline_survives_redraw():
    """Regression test for #206"""
    kernel = make_kernel()
    line = polyline_arg((1000, 2000), (3000, 4000))

    kernel.gki_plset(plset_arg(1))
    kernel.gki_polyline(line)

    kernel.gki_plset(plset_arg(0))
    kernel.gki_polyline(line)

    assert kernel._GkiMplKernel__normLines == []

    # Reproduce the relevant part of the retained-mode redraw:
    # start with an empty display and replay the draw buffer.
    kernel._GkiMplKernel__normLines = []
    kernel._GkiMplKernel__skipPlotAppends = True

    for function, args in kernel.drawBuffer.get():
        function(*args)

    assert kernel._GkiMplKernel__normLines == []
