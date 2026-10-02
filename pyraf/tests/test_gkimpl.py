import sys
import types

import numpy
from matplotlib.lines import Line2D
import pytest

from pyraf import gki


@pytest.fixture
def fake_tk_root(monkeypatch):
    """Provide a fake Tk root for tests that require Tk to be initialized."""
    import tkinter
    monkeypatch.setattr(tkinter, "_default_root", object())


# Minimal stand-ins for GUI and plotting objects used by GkiMplKernel.
# They allow these tests to run without creating a real Tk window.

class DummyWcs:
    def commit(self):
        pass


class DummyColorManager:
    def setDrawingColor(self, color):
        return "black"


@pytest.fixture
def fake_gkimplkernel(fake_tk_root):
    """Create a minimally initialized GkiMplKernel for headless tests."""
    from pyraf import GkiMpl

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


def test_clear_polyline(fake_gkimplkernel):
    """Regression test for #206"""
    kernel = fake_gkimplkernel

    line = polyline_arg((1000, 2000), (3000, 4000))

    kernel.gki_plset(plset_arg(1))
    kernel.gki_polyline(line)

    assert len(kernel._GkiMplKernel__normLines) == 1

    kernel.gki_plset(plset_arg(0))
    kernel.gki_polyline(line)

    assert kernel._GkiMplKernel__normLines == []


def test_clear_polyline_keeps_other_lines(fake_gkimplkernel):
    """Regression test for #206"""
    kernel = fake_gkimplkernel

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


def test_clear_polyline_does_not_remove_marker(fake_gkimplkernel):
    """Regression test for #206"""
    kernel = fake_gkimplkernel

    line = polyline_arg((1000, 2000), (3000, 4000))

    kernel.gki_polymarker(line)
    marker = kernel._GkiMplKernel__normLines[0]

    kernel.gki_plset(plset_arg(0))
    kernel.gki_polyline(line)

    lines = kernel._GkiMplKernel__normLines

    assert len(lines) == 1
    assert lines[0] is marker


def test_clear_polyline_survives_redraw(fake_gkimplkernel):
    """Regression test for #206"""
    kernel = fake_gkimplkernel

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


def test_full_window_cursor_draw_erase(monkeypatch, fake_tk_root):
    """Regression test for #208"""
    from pyraf import Ptkplot

    class DummyCanvas:
        width = 100
        height = 200

        def __init__(self):
            self.created = []
            self.deleted = []

        def create_line(self, *args, **kwargs):
            item = len(self.created) + 1
            self.created.append((item, args, kwargs))
            return item

        def delete(self, item):
            self.deleted.append(item)

    canvas = DummyCanvas()
    xor_draws = []

    def xor_draw(*args):
        xor_draws.append(args)

    monkeypatch.setattr(Ptkplot.wutil, "drawCursor", xor_draw)

    cursor = Ptkplot.FullWindowCursor(0.25, 0.75, canvas)

    assert cursor.isVisible()
    assert len(canvas.created) == 2
    assert canvas.deleted == []
    assert xor_draws == []

    cursor.erase()

    assert not cursor.isVisible()
    assert canvas.deleted == [1, 2]
    assert xor_draws == []

    cursor.draw()

    assert cursor.isVisible()
    assert len(canvas.created) == 4
    assert canvas.deleted == [1, 2]
    assert xor_draws == []

