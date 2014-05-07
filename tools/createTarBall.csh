#!/bin/csh -f
#
# $Id$
#

if ($#argv != 3) then
   echo "usage:  $0  dev|rel  2|3  py-bin-dir"
   exit 1
endif
set isdev = 0
if ($argv[1] == "dev") then
   set isdev = 1
endif
set pyver = 2
if ($argv[2] == "3") then
   set pyver = 3
endif
set pybin = $argv[3]

set svnbin = /usr/bin/svn
if (`uname -n` == "somenode.stsci.edu") then
   set svnbin = svn
endif

if (!(-d ~/.stsci_tmp)) then
   mkdir ~/.stsci_tmp
   if ($status != 0) then
      echo "ERROR creating ~/.stsci_tmp"
      exit 1
   endif
endif

set workDir = "~/.stsci_tmp/pyraf_tar_py${pyver}_`uname -n`"
echo Creating work area: $workDir
/bin/rm -rf $workDir
mkdir $workDir
cd $workDir
if ($status != 0) then
   exit 1
endif
#
if ($isdev == 1) then
   set pyr = "pyraf-dev"
#  set co_pyraf = 'co -q -r HEAD http://svn6.assembla.com/svn/pyraf/trunk'
   set co_pyraf = 'co -q -r HEAD https://aeon.stsci.edu/ssb/svn/pyraf/trunk'
   set co_tools = 'co -q -r HEAD https://svn.stsci.edu/svn/ssb/stsci_python/stsci.tools/trunk'
else
   set pyr = "pyraf-2.1"
   echo -n 'What will the pyraf dir name be? ('$pyr'): '
   set ans = $<
   if ($ans != '') then
      set pyr = $ans
   endif
   set brn = "tags/release_2.1"
   echo -n 'What is branch name? ('$brn'): '
   set ans = $<
   if ($ans != '') then
      set brn = $ans
   endif
   set co_pyraf = "co -q https://aeon.stsci.edu/ssb/svn/pyraf/${brn}"
   set co_tools = "co -q https://svn.stsci.edu/svn/ssb/stsci_python/stsci.tools/trunk"
endif

# get all source via SVN
echo "Downloading source for: $pyr from: `echo $co_pyraf | sed 's/.*:\/\///'` "
$svnbin $co_pyraf $pyr
if ($status != 0) then
   echo ERROR svn-ing pyraf
   exit 1
endif

# for now, add svninfo file manually
#cd $workDir/$pyr
#set rev = `$svnbin info | grep '^Revision:' | sed 's/.* //'`
#cd $workDir/$pyr/lib/pyraf
#if (!(-e svninfo.py)) then
#   echo '__svn_version__ = "'${rev}'"' > svninfo.py
#   echo '__full_svn_info__ = ""' >> svninfo.py
#   echo '__setup_datetime__ = "'`date`'"' >> svninfo.py
#endif

# get extra pkgs into a subdir
cd $workDir/$pyr
mkdir required_pkgs
cd $workDir/$pyr/required_pkgs
echo "Downloading source for: stsci.tools and dist. stuff"
#
# STABLE!: -q -r '{2013-02-11}', but continue to use HEAD if possible
$svnbin co -q -r HEAD https://svn.stsci.edu/svn/ssb/stsci_python/d2to1/trunk d2to1
if ($status != 0) then
   echo ERROR svn-ing d2to1
   exit 1
endif
#
$svnbin co -q -r HEAD https://svn.stsci.edu/svn/ssb/stsci_python/stsci.distutils/trunk stsci.distutils
if ($status != 0) then
   echo ERROR svn-ing stsci.distutils
   exit 1
endif
#
$svnbin $co_tools stsci.tools
if ($status != 0) then
   echo ERROR svn-ing stsci.tools
   exit 1
endif

# edit setup to comment out pyfits/astropy requirements (dont need for pyraf)
cd $workDir/$pyr/required_pkgs/stsci.tools
if (-e setup.cfg) then
   /bin/cp setup.cfg setup.cfg.orig
   cat setup.cfg.orig |grep -v 'pyfits *(' |grep -v 'astropy *(' > setup.cfg
   echo DIFF for all required pkgs/versions
   diff setup.cfg.orig setup.cfg
endif

# Now that we have setup.cfg working better, run sdist to
# generate the version.py file (this imports pyraf)
# and generate the .tar.gz file
cd $workDir/$pyr
setenv PYRAF_NO_DISPLAY
# FORCE_USE_PY27... $pybin/python setup.py sdist >& $workDir/sdist.out
/user/${USER}/info/usrlcl273/bin/python setup.py sdist >& $workDir/sdist.out
if ($status != 0) then
   cat $workDir/sdist.out
   exit 1
endif

# ---------------- HACK 1 TO WORK AROUND BUGS IN stsci_distutils ---------------
# change code to NOT run update_svn_info() on first import of version.py
cd $workDir/$pyr/lib/pyraf
cp version.py version.py.orig1
cat version.py.orig1 |sed 's/^ *update_svn_info *(/#update_svn_info(/' > version.py
echo 'DIFF of update_svn_info() line'
diff version.py.orig1 version.py
# --------- END OF HACK 1 TO WORK AROUND BUGS IN stsci_distutils ---------------

# get version info
#et verinfo1 = `grep '__version__ *=' $workDir/$pyr/lib/pyraf/__init__.py | sed 's/.*= *//' | sed 's/"//g'`
#et verinfo2 = `grep '__svn_version__' $workDir/$pyr/lib/pyraf/sv*.py | sed 's/.*= *//' | sed 's/"//g'`
#et verinfo3 = "${verinfo1}-r$verinfo2"
set verinfo1 = `grep '__version__ *=' $workDir/$pyr/lib/pyraf/version.py |sed 's/.*= *//' |sed "s/'//g"`
set verinfo2 = `grep '__svn_revision__ *=' $workDir/$pyr/lib/pyraf/version.py |head -1 |sed 's/.*= *//' |sed "s/'//g"`
set svn_says = `${svnbin}version |sed 's/M//'`

# ---------------- HACK 2 TO WORK AROUND BUGS IN stsci_distutils ---------------
set junk = `echo $verinfo2 |grep Unable.to.determine`
if ("$junk" == "$verinfo2") then
   # __svn_revision__ did not get set, let's set it manually...
   cd $workDir/$pyr/lib/pyraf
   cp version.py version.py.orig2
   cat version.py.orig2 |sed 's/^\( *\)__svn_revision__ *=.*/\1__svn_revision__ = "'${svn_says}'"/' > version.py
   echo 'DIFF of __svn_revision__ line(s)'
   diff version.py.orig2 version.py

   # now re-run the sdist
   cd $workDir/$pyr
   /bin/rm -rf *.egg
   /bin/rm -rf dist
   # FORCE_USE_PY27... $pybin/python setup.py sdist >& $workDir/sdist2.out
   /user/${USER}/info/usrlcl273/bin/python setup.py sdist >& $workDir/sdist2.out
   if ($status != 0) then
      cat $workDir/sdist2.out
      exit 1
   endif

   # now set verinfo2 correctly
   set verinfo2 = "$svn_says"
endif
# ---------END OF  HACK 2 TO WORK AROUND BUGS IN stsci_distutils ---------------

# set full ver (verinfo3) to be n.m.devNNNNN (if dev) or n.m.rNNNNN (if not)
set junk = `echo $verinfo1 |grep dev`
if  ("$junk" == "$verinfo1") then
   set verinfo3 = "${verinfo1}${verinfo2}"
else
   set verinfo3 = "${verinfo1}.r${verinfo2}"
endif
echo "This build will show a version number of:  $verinfo3 ... is same as r$svn_says ..."
echo "$verinfo3" > ~/.pyraf_tar_ball_ver

# remove svn dirs (not needed if we use sdist)
cd $workDir/$pyr
/bin/rm -rf `find . -name '.svn'`
if ($status != 0) then
   echo ERROR cleaning out .svn dirs
   exit 1
endif

# OLD - uses tar and gzip directly:
## tar and zip it - regular (non-win) version
#cd $workDir
#tar cf $pyr.tar $pyr
#if ($status != 0) then
#   echo ERROR tarring up
#   exit 1
#endif
#gzip $pyr.tar
#if ($status != 0) then
#   echo ERROR gzipping
#   exit 1
#endif

# New - use the file generated by sdist:
cd $workDir
/bin/mv $pyr/dist/pyraf* $pyr.tar.gz
if ($status != 0) then
   echo ERROR finding sdist-created tarball
   exit 1
endif

# Now tar/zip the Windows version (via "zip")
if ($isdev == 1) then
   cd $workDir/$pyr
   rm -rf dist
   cd $workDir
   zip -rq ${pyr}-win $pyr
   if ($status != 0) then
      echo ERROR zipping up
      exit 1
   endif
endif

echo "Successfully created tar-ball: $pyr.tar.gz"
