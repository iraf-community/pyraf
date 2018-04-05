"""These were tests under core/graphics_checks in pandokia."""
from __future__ import absolute_import
import six

import glob
import os
import sys
import time

import pytest

from .utils import IS_PY2, HAS_IRAF, DATA_DIR

if HAS_IRAF:
    from pyraf import iraf
    from pyraf import gki
    from pyraf import wutil

REF = {}
PSDEV = None
EXP2IGNORE = None


def setup_module():
    """ Does not work under Darwin, because c.OF_GRAPHICS is True
    TODO: ^Investigate^
    """
    global REF, PSDEV, EXP2IGNORE

    # TODO: Related to test_gki_prow_to_different_devices
    #os.environ['LPDEST'] = "hp_dev_null"
    #os.environ['PRINTER'] = "hp_dev_null"

    # first turn off display
    os.environ['PYRAF_NO_DISPLAY'] = '1'

    # The psi_land kernel seems not to be supported in
    # default graphcap on OSX 10.9.5.
    # And psdump kernel is too temperamental on Linux.
    if sys.platform.lower().startswith('linux'):
        PSDEV = 'psi_land'
        EXP2IGNORE = '.*CreationDate: .*'
    elif sys.platform.lower().startswith('darwin'):
        PSDEV = 'psdump'
        EXP2IGNORE = '(NOAO/IRAF '
    else:
        raise OSError('Unsupported test platform: {}'.format(sys.platform))

    # EXPECTED RESULTS
    REF[('2', 'linux')] = """python ver = 2.7
platform = linux2
PY3K = False
c.OF_GRAPHICS = False
/dev/console owner = <skipped>
tkinter use unattempted.
"""
    REF[('2', 'darwin')] = REF[('2', 'linux')].replace('linux2', 'darwin')

    REF[('3', 'linux')] = """python ver = 3.6
platform = linux
PY3K = True
c.OF_GRAPHICS = False
/dev/console owner = <skipped>
tkinter use unattempted.
"""
    REF[('3', 'darwin')] = REF[('3', 'linux')].replace('linux', 'darwin')


def diffit(exp2ig, f_new, f_ref, cleanup=True):
    """ Run the diff and check the return status """
    # don't do the diff if the new file isn't there or if it is empty
    assert os.path.exists(f_new), "New file unfound: {}".format(f_new)
    assert os.path.exists(f_ref), "Ref file unfound: {}".format(f_ref)
    # expect new file to at least be 80% as big as ref file, before we compare
    expected_sz = int(0.8*os.path.getsize(f_ref))
    sz = os.path.getsize(f_new)
    if sz < expected_sz:
        # sometimes the psdump kernel takes a moment to write+close
        time.sleep(1)
        sz = os.path.getsize(f_new)
        if sz < expected_sz:
            time.sleep(5)
    sz = os.path.getsize(f_new)
    assert sz > 0, "New file is empty: {}".format(f_new)
    cmd = "diff -I '{}' {} {}".format(exp2ig, f_ref, f_new)
    assert 0 == os.system(cmd), \
        "Diff of postscript failed!  Command = {}".format(cmd)
    if cleanup:
        os.remove(f_new)


def findAllTmpPskFiles():
    """ Do a glob in the tmp dir (and cwd) looking for psikern files.
    Return the list. """
    # Usually the files are dropped in the $tmp directory
    if PSDEV.find('dump') >= 0:
        flistCur = glob.glob('/tmp/irafdmp*.ps')  # always in /tmp
    else:
        flistCur = glob.glob(os.environ['tmp']+os.sep+'psk*')
    # sometimes the tmp files disappear on Solaris
    if sys.platform == 'sunos5':
        time.sleep(1)
        for f in flistCur:
            os.system("/bin/ls -ld "+f)
            if not os.path.exists(f):
                print("This existed then did not: ", f)
                flistCur.remove(f)
    # for some reason, on Solaris (at least), some files are dumped to cwd
    if PSDEV.find('dump') >= 0:
        flistCur += glob.glob(os.getcwd()+os.sep+'irafdmp*.ps')
    else:
        flistCur += glob.glob(os.getcwd()+os.sep+'psk*')
    return flistCur


def preTstCleanup():
    """For some reason, with the psdump kernel at least, having existing files
    in place during the test seems to affect whether new are 0-length
    """
    # So let's just start with a fresh area
    oldFlist = findAllTmpPskFiles()
    for f in oldFlist:
        try:
            os.remove(f)
        except Exception:
            pass  # may belong to another user - don't be chatty


def getNewTmpPskFile(theBeforeList, title, preferred=None):
    """ Do a glob in the tmp dir looking for psikern files, compare with the
    old list to find the new (expected) file.  If preferred is None, then only
    a single new file is expected.  If not None, then we assume that more than
    one new file may be present, and the arg is used as a search substring
    (regexp would be cooler) to choose which single file to return of the newly
    found set. Returns a single string filename. """

    flistAft = findAllTmpPskFiles()
    assert len(flistAft) >= len(theBeforeList), \
        "How can the list size be SMALLER now? ("+title+","+PSDEV+")\n" + \
        str(theBeforeList)+"\n"+str(flistAft)
    if len(flistAft) == len(theBeforeList):
        # sometimes the psdump kernel takes a moment to write+close (or start!)
        time.sleep(1)
        flistAft = findAllTmpPskFiles()
    assert len(flistAft) > len(theBeforeList), \
        'No postcript file(s) generated during: "'+title+'": ' + \
        str(theBeforeList)+' : PSDEV is: '+PSDEV
    for f in theBeforeList:
        flistAft.remove(f)
    if preferred is None:
        # In this case, we expect only a single ps file.
        if len(flistAft) != 1:
            # But, if there are two+ (sometimes occurs on Solaris), and one
            # is in /tmp and another is a local .eps, let's debug it a bit.
            if len(flistAft) >= 2 and flistAft[0].find('/tmp/') == 0 and \
               flistAft[-1].find('.eps') > 0:
                # Are these files related (copies?)
                print("Debugging multiple postscript files scenario")
                for f in flistAft:
                    os.system("/bin/ls -ld "+f)
                # Or, did the /tmp version suddenly get deleted?
                if not os.path.exists(flistAft[0]):
                    print("Am somehow missing the deletes.  Test: {}".format(title))
                    return flistAft[-1]
            # Either way, throw something
            raise Exception('Expected single postcript file during: "' +
                            title+'": '+str(flistAft))
    else:
        # Here we allow more than one, and return the preferred option.
        for f in flistAft:
            if f.find(preferred) >= 0:
                return f

    return flistAft[0]


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_dumpspecs():
    # get dumpspecs output
    out_f = six.StringIO()
    wutil.dumpspecs(outstream=out_f, skip_volatiles=True)
    out_str = out_f.getvalue()
    out_f.close()

    # modify out_str to remove a path that will always be changing
    out_str = '\n'.join([l for l in out_str.split('\n')
                         if 'python exec =' not in l])
    # modify out_str to handle old versions which printed Tkinter as camel-case
    out_str = out_str.replace('Tkinter', 'tkinter')

    # verify it (is version dependent)
    key = ('2' if IS_PY2 else '3', sys.platform.replace('2', ''))
    expected = REF[key]
    assert expected.strip() == out_str.strip(), \
        'Unexpected output from wutil.dumpspecs: {}'.format(out_str)


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_gkidecode(tmpdir):
    iraf.plot(_doprint=0)
    prow_stdout = str(tmpdir.join('test_prow_256.gki'))
    gki_stdout = str(tmpdir.join('gkidecode_stdout.txt'))
    gki_stderr = str(tmpdir.join('gkidecode_stderr.txt'))

    iraf.prow("dev$pix", row=256, StdoutG=prow_stdout)
    iraf.gkidecode(prow_stdout, Stdout=gki_stdout, Stderr=gki_stderr)
    assert 'close_workstation' in open(gki_stdout).readlines()[-1]
    assert not open(gki_stderr).readlines()


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.parametrize('test_input', [
    'psdump',
    'psi_land',
])
def test_gki_postscript_in_graphcap(test_input):
    """ Verify that the graphcap file supports psdump and psi_land """
    gc = gki.getGraphcap()
    assert gc, "default graphcap not found"
    assert test_input in gc, \
        "default graphcap does not support {}".format(test_input)
    device = gc[test_input]
    assert device.devname == test_input, \
        "Invalid graphcap device for {}".format(test_input)


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_gki_opcodes():
    """ Simple aliveness test for the opcode2name dict """
    for opc in gki.GKI_ILLEGAL_LIST:
        assert gki.opcode2name[opc] == 'gki_unknown'


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_gki_control_codes():
    """ Simple aliveness test for the control2name dict """
    for ctl in gki.GKI_ILLEGAL_LIST:
        assert gki.control2name[ctl] == 'control_unknown'


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_gki_single_prow():
    """ Test a prow-plot of a single row from dev$pix to .ps """
    iraf.plot(_doprint=0)  # load plot for prow
    # get look at tmp dir before plot/flush
    flistBef = findAllTmpPskFiles()
    # plot
    iraf.prow("dev$pix", row=256, dev=PSDEV)  # plot
    iraf.gflush()
    # get output postscript temp file name
    psOut = getNewTmpPskFile(flistBef, "single_prow")
    # diff
    diffit(EXP2IGNORE, psOut, os.path.join(DATA_DIR, PSDEV + "_prow_256.ps"))


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_gki_prow_1_append():
    """ Test a prow-plot with 1 append (2 rows total, dev$pix) to .ps """
    iraf.plot(_doprint=0)  # load plot for prow
    # get look at tmp dir before plot/flush
    flistBef = findAllTmpPskFiles()
    # plot
    iraf.prow("dev$pix", row=256, dev=PSDEV)  # plot
    iraf.prow("dev$pix", row=250, dev=PSDEV, append=True)  # append #1
    iraf.gflush()
    # get output postscript temp file name
    psOut = getNewTmpPskFile(flistBef, "prow_1_append")
    # diff
    diffit(EXP2IGNORE, psOut,
           os.path.join(DATA_DIR, PSDEV + "_prow_256_250.ps"))


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_gki_prow_2_appends():
    """ Test a prow-plot with 2 appends (3 rows total, dev$pix) to .ps """
    iraf.plot(_doprint=0)  # load plot for prow
    # get look at tmp dir before plot/flush
    flistBef = findAllTmpPskFiles()
    # plot
    iraf.prow("dev$pix", row=256, dev=PSDEV)  # plot
    iraf.prow("dev$pix", row=250, dev=PSDEV, append=True)  # append #1
    iraf.prow("dev$pix", row=200, dev=PSDEV, append=True)  # append #2
    iraf.gflush()
    # get output postscript temp file name
    psOut = getNewTmpPskFile(flistBef, "prow_2_appends")
    # diff
    diffit(EXP2IGNORE, psOut,
           os.path.join(DATA_DIR, PSDEV + "_prow_256_250_200.ps"))


@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
def test_gki_2_prows_no_append():
    """ Test 2 prow calls with no append (2 dev$pix rows) to 2 .ps's """
    iraf.plot(_doprint=0)  # load plot for prow
    # get look at tmp dir before plot/flush
    flistBef = findAllTmpPskFiles()
    # plot
    iraf.prow("dev$pix", row=256, dev=PSDEV)  # plot
    iraf.prow("dev$pix", row=250, dev=PSDEV)  # plot again (flushes 1st)
    # get output postscript temp file name
    prf = None
    if os.uname()[0] == 'SunOS':
        prf = '.eps'  # Solaris can leave extras here
    psOut = getNewTmpPskFile(flistBef, "2_prows_no_append - A", preferred=prf)
    # diff
    # NOTE - this seems to get 0-len files when (not stdin.isatty()) for psdump
    diffit(EXP2IGNORE, psOut,
           os.path.join(DATA_DIR, PSDEV + "_prow_256.ps"))
    # NOW flush second
    flistBef = findAllTmpPskFiles()
    iraf.gflush()
    # get output postscript temp file name
    prf = None
    if os.uname()[0] == 'SunOS':
        prf = '.eps'  # Solaris can leave extras here
    psOut = getNewTmpPskFile(flistBef, "2_prows_no_append - B", preferred=prf)
    # diff
    diffit(EXP2IGNORE, psOut,
           os.path.join(DATA_DIR, PSDEV + "_prow_250.ps"))


#@pytest.mark.skipif(not HAS_IRAF, reason='Need IRAF to run')
@pytest.mark.skip(reason="Erroneously sends jobs to network printers")
def test_gki_prow_to_different_devices():  # rename to disable for now
    """Test 2 prow calls, each to different devices - one .ps written.

    10 May 2012 - rename to disable for now - is sending nightly prints
    to hpc84.
    It seems that the cups system takes the print to hp_dev_null and
    changes that to an existing printer, knowing it is wrong ...
    When there is time, look into a way to start this test up again without any
    danger of prints going to an actual printer.
    """
    iraf.plot(_doprint=0)  # load plot for prow
    # get look at tmp dir before plot/flush
    flistBef = findAllTmpPskFiles()
    # use a fake printer name so we don't waste a sheet of paper with each test
    os.environ['LPDEST'] = "hp_dev_null"
    os.environ['PRINTER'] = "hp_dev_null"
    # plot
    iraf.prow("dev$pix", row=256, dev=PSDEV)  # plot (no .ps file yet)
    # plot to fake printer, should flush
    iraf.prow("dev$pix", row=333, dev="lw")
    # last plot, and should warn @ fake
    # get output postscript temp file name
    psOut = getNewTmpPskFile(flistBef, "prow_to_different_devices")
    # diff
    diffit(EXP2IGNORE, psOut,
           os.path.join(DATA_DIR, PSDEV + "_prow_256.ps"))
    # NOW flush - should do nothing
    flistBef = findAllTmpPskFiles()
    iraf.gflush()
    flistAft = findAllTmpPskFiles()
    assert flistBef == flistAft, "Extra tmp .ps file written? "+str(flistAft)
