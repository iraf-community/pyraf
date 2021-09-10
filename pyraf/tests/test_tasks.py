import pytest

from .utils import HAS_IRAF
from stsci.tools.irafglobals import INDEF

if HAS_IRAF:
    from pyraf import iraf
else:
    pytestmark = pytest.mark.skip('Need IRAF to run')


@pytest.mark.parametrize('pkg', [
    'clpackage', 'dataio', 'images', 'lists', 'plot', 'system',
    'utilities', 'softools', 'noao', 'imcoords', 'imfilter', 'imfit',
    'imgeom', 'immatch', 'imutil', 'tv', 'color', 'vol', 'nttools',
    'artdata', 'astcat', 'astutil', 'digiphot', 'imred', 'mtlocal',
    'obsutil', 'onedspec', 'rv', 'twodspec', ])
def test_load_package(pkg):
    iraf.load(pkg, doprint=False, hush=False)


@pytest.mark.parametrize('task', [
    'imcoords.mkcwcs', 'imcoords.mkcwwcs', 'imgeom.imlintran',
    'imgeom.rotate', 'immatch.gregister', 'immatch.imalign',
    'immatch.skymap', 'immatch.sregister', 'immatch.wcsmap',
    'immatch.wregister', 'proto.ringavg', 'utilities.bases',
    'lists.average', 'lists.raverage', 'system.allocate',
    'system.deallocate', 'system.devstatus', 'system.diskspace',
    'system.devices', 'system.references', 'system.phelp',
    'tv.bpmedit', 'softools.mkmanpage', 'color.rgbdisplay',
    'astutil.astradius',
])
def test_load_cl_task(task):
    t = iraf.getTask(task)
    t.initTask()


@pytest.mark.parametrize('task', ['user.date', 'softools.xc'])
def test_exec_foreign_task(task):
    t = iraf.getTask(task)
    t(Stdout="/dev/null")


@pytest.mark.parametrize('task, pars', [
    ('obsutil.specpars', {'xdispersion': INDEF, 'xbin': 1, 'filter': ''}),
])
def test_exec_pset(task, pars):
    t = iraf.getTask(task)
    pdict = t.getParDict()
    for name, value in pars.items():
        assert pdict[name].value == value
