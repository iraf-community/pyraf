import pytest
import os
from .utils import HAS_IRAF
from pyraf import gki
from stsci.tools import capable

if HAS_IRAF:
    from pyraf import iraf

no_graphics = False
try:
    import tkinter
    tkinter.Tk().destroy()
except Exception:
    no_graphics = True

markers = [None, 'point', 'box', 'plus', 'cross', 'circle']
graphics = ['tkplot', 'matplotlib']


@pytest.fixture(autouse=True)
def setup():
    capable.OF_GRAPHICS = True
    open('.hushiraf', 'a').close()
    iraf.plot()  # load plot pkg
#    gki._resetGraphicsKernel()
    # clean slate
    if 'PYRAFGRAPHICS' in os.environ:
        del os.environ['PYRAFGRAPHICS']
    os.environ['PYRAF_GRAPHICS_ALWAYS_ON_TOP'] = '1'
    yield
    gki.kernel.clear()
    if os.path.exists('.hushiraf'):
        os.remove('.hushiraf')


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.skipif(no_graphics, reason='No graphics available')
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


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.skipif(no_graphics, reason='No graphics available')
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


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.skipif(no_graphics, reason='No graphics available')
@pytest.mark.parametrize('graphics', graphics)
def test_plot_contour(graphics):
    os.environ['PYRAFGRAPHICS'] = graphics
    iraf.contour("dev$pix", Stdout='/dev/null')


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.skipif(no_graphics, reason='No graphics available')
@pytest.mark.parametrize('graphics', graphics)
def test_plot_surface(graphics):
    os.environ['PYRAFGRAPHICS'] = graphics
    iraf.surface("dev$pix", Stdout='/dev/null')
