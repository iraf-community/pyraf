import os
from pathlib import Path
from io import StringIO
import shutil
import pytest

from .utils import HAS_IRAF

from pyraf import iraf

try:
    from iraf import softools
except ImportError:
    pytest.skip("IRAF softools not available", allow_module_level=True)


@pytest.fixture(scope="session", autouse=True)
def setup_testpkg(tmp_path_factory):
    """Copy the test package to a temporary dir, compile the SPP tasks and
    load the package

    """
    base = tmp_path_factory.mktemp("iraf")
    for fname in (Path(__file__).parent / "testpkg").iterdir():
        shutil.copy(fname, base)
    iraf.set(testpkg=str(base) + "/")
    cwd = Path.cwd()
    os.chdir(base)
    try:
        iraf.xc("spppars.x")
    finally:
        os.chdir(cwd)
    iraf.task(testpkgDOTpkg="testpkg$testpkg.cl")
    from iraf import testpkg

    yield


def showpars(taskname, **kwargs):
    """Run the task with given parameters

    Return the output as a dictionary of key-value pairs with proper
    type for the value

    """
    task = iraf.module.getTask(taskname)
    params = task.getParDict()
    stdout = StringIO()
    task(StdoutAppend=stdout, **kwargs)
    stdout.seek(0)
    res = {}
    for l in stdout.read().splitlines():
        key, val = l.split("=", 1)
        res[key] = params[key].checkValue(val)
    return res


@pytest.mark.parametrize(
    "name,value",
    [
        ("strpar", "foo.fits"),
        ("intpar", 2),
        ("intpar", -2),
        ("fltpar", 2.0),
        ("fltpar", 2.0e1),
        ("fltpar", 2),
        ("boolpar", True),
        ("boolpar", 1),
    ],
)
@pytest.mark.parametrize("task", ["clpars", "simplepars"])
def test_simplepars(task, name, value):
    """Check that simple parameters work for CL and SPP tasks"""
    ref = showpars(task)
    shortname = name.split(".", 1)[-1]
    ref[shortname] = value
    assert ref == showpars(task, **{name: value})


@pytest.mark.parametrize(
    "name,value",
    [
        ("psetpar.psintpar", 3),
        ("psintpar", 3),
        ("psetpar.psstrpar", "bar"),
        ("psstrpar", "bar"),
    ],
)
@pytest.mark.parametrize("task", ["clpars", "psetpars0", "psetpars1"])
def test_pset(task, name, value):
    """Check that parameter sets for for CL and SPP tasks"""
    ref = showpars(task)
    shortname = name.split(".", 1)[-1]
    ref[shortname] = value
    assert ref == showpars(task, **{name: value})


@pytest.mark.xfail(reason="Not implemented in PyRAF")
@pytest.mark.parametrize("task", ["clpars", "psetpars0", "psetpars1"])
def test_pars_other_pset(task):
    """Check that setting another parameter set works in CL and SPP tasks"""
    ref = showpars(task)
    ref["psstrpar"] = "foobar"
    ref["psintpar"] = -1
    assert ref == showpars(task, psetpar="psetpar1")


@pytest.mark.parametrize(
    "name,value",
    [
        ("intpar", "-20"),
        ("intpar", "20"),
        ("intpar", "foo"),
        ("fltpar", "-100.5"),
        ("fltpar", "1e3"),
        ("fltpar", "foo"),
        ("boolpar", "foo"),
        ("boolpar", -99),
    ],
)
@pytest.mark.parametrize("task", ["clpars", "simplepars"])
def test_pars_invalid_value(task, name, value):
    """Check that invalid values raise a ValueError"""
    with pytest.raises(ValueError):
        showpars(task, **{name: value})


@pytest.mark.parametrize(
    "name,value",
    [
        ("invalidpar", "foo"),
        ("psetpar", "foo"),
    ],
)
@pytest.mark.parametrize("task", ["clpars", "simplepars"])
def test_pars_invalid_name(task, name, value):
    """Check that unknown parameters raise a KeyError"""
    with pytest.raises(KeyError):
        showpars(task, **{name: value})
