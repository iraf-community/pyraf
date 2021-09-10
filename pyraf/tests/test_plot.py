import pytest
import os
from .utils import HAS_IRAF
from pyraf import gki
from stsci.tools import capable

if HAS_IRAF:
    from pyraf import iraf
else:
    pytestmark = pytest.mark.skip('Need IRAF to run')

try:
    import tkinter
    tkinter.Tk().destroy()
except Exception:
    pytestmark = pytest.mark.skip('No graphics available')

markers = [None, 'point', 'box', 'plus', 'cross', 'circle']
graphics = ['tkplot', 'matplotlib']


@pytest.fixture(autouse=True)
def setup():
    orig_graphics = capable.OF_GRAPHICS
    capable.OF_GRAPHICS = True
    iraf.plot()  # load plot pkg
#    gki._resetGraphicsKernel()
    # clean slate
    graphenv = os.environ.get('PYRAFGRAPHICS')
    if graphenv is not None:
        del os.environ['PYRAFGRAPHICS']
    yield
    gki.kernel.clear()
    capable.OF_GRAPHICS = orig_graphics
    if graphenv is not None:
        os.environ['PYRAFGRAPHICS'] = graphenv

@pytest.mark.parametrize('marker', markers)
@pytest.mark.parametrize('graphics', graphics)
def test_plot_prow(marker, graphics):
    os.environ['PYRAFGRAPHICS'] = graphics
    apd = False
    for row in range(150, 331, 90):
        if marker is None:
            iraf.prow('dev$pix', row, wy2=400, append=apd, pointmode=False)
        else:
            iraf.prow('dev$pix', row, wy2=400, append=apd, pointmode=True,
                      marker=marker)
        apd = True


@pytest.mark.parametrize('marker', markers)
@pytest.mark.parametrize('graphics', graphics)
def test_plot_graph(marker, graphics):
    os.environ['PYRAFGRAPHICS'] = graphics
    tstr = ''
    for row in range(150, 331, 90):
        tstr += 'dev$pix[*,' + str(row) + '],'
    tstr = tstr[:-1]  # rm final comma
    if marker is None:
        iraf.graph(tstr, wy2=400, pointmode=False, ltypes='1')
    else:
        iraf.graph(tstr, wy2=400, pointmode=True, marker=marker)


@pytest.mark.parametrize('graphics', graphics)
def test_plot_contour(graphics):
    os.environ['PYRAFGRAPHICS'] = graphics
    iraf.contour("dev$pix", Stderr='/dev/null')


@pytest.mark.parametrize('graphics', graphics)
def test_plot_surface(graphics):
    os.environ['PYRAFGRAPHICS'] = graphics
    iraf.surface("dev$pix", Stderr='/dev/null')
