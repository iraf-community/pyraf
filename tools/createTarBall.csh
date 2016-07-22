#!/bin/csh -f
#
# $Id$
#

set use_git = 1
   # trying to do this from git repos as of nightly on 9 Mar 2016

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

set vcsbin = /usr/bin/svn
if (`uname -n` == "somenode.stsci.edu") then
   set vcsbin = svn
endif
# trying git as of 3/3
if ($use_git == "1") then
   set vcsbin = git
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
   set co_pyraf = 'co -q -r HEAD https://aeon.stsci.edu/ssb/svn/pyraf/trunk'
   set co_tools = 'co -q -r HEAD https://svn.stsci.edu/svn/ssb/stsci_python/stsci.tools/trunk'
   if ($use_git == "1") then
      set co_pyraf = 'clone -q https://github.com/spacetelescope/pyraf.git'
      set co_tools = 'clone -q https://github.com/spacetelescope/stsci.tools.git'
   endif
else
   set pyr = "pyraf-2.1.717"
   echo -n 'What will the pyraf dir name be? ('$pyr'): '
   set ans = $<
   if ($ans != '') then
      set pyr = $ans
   endif

   if ($use_git != "1") then
      set brn = "tags/release_2.1.717"
      echo -n 'What is branch name? ('$brn'): '
      set ans = $<
      if ($ans != '') then
         set brn = $ans
      endif
      set co_pyraf = "co -q https://aeon.stsci.edu/ssb/svn/pyraf/${brn}"
      set co_tools = "co -q https://svn.stsci.edu/svn/ssb/stsci_python/stsci.tools/trunk"
   else
      set co_pyraf = 'clone -q https://github.com/spacetelescope/pyraf.git'
      set co_tools = 'clone -q https://github.com/spacetelescope/stsci.tools.git'
   endif
endif

# get all source via SVN
echo "Downloading source for: $pyr from: `echo $co_pyraf | sed 's/.*:\/\///'` "
$vcsbin $co_pyraf $pyr
if ($status != 0) then
   echo ERROR checking out pyraf
   exit 1
endif

# used to add version info manually right here

# get extra pkgs into a subdir
cd $workDir/$pyr
mkdir required_pkgs
cd $workDir/$pyr/required_pkgs
echo "Downloading source for: stsci.tools and dist. stuff"

#
if ($use_git == "1") then
   $vcsbin clone -q         https://github.com/spacetelescope/d2to1.git            d2to1
   set save_stat = $status
else
   $vcsbin co    -q -r HEAD https://svn.stsci.edu/svn/ssb/stsci_python/d2to1/trunk d2to1
   set save_stat = $status
endif
if ($save_stat != 0) then
   echo ERROR checking out d2to1
   exit 1
endif
#
if ($use_git == "1") then
   $vcsbin clone -q         https://github.com/spacetelescope/stsci.distutils.git            stsci.distutils
   set save_stat = $status
else
   $vcsbin co    -q -r HEAD https://svn.stsci.edu/svn/ssb/stsci_python/stsci.distutils/trunk stsci.distutils
   set save_stat = $status
endif
if ($save_stat != 0) then
   echo ERROR checking out stsci.distutils
   exit 1
endif

#
$vcsbin $co_tools stsci.tools
if ($status != 0) then
   echo ERROR checking out stsci.tools
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

# ---------------- HACK TO ADD GIT REV INFO ----------------------------------
if ($use_git == "1") then
   cd $workDir/$pyr/lib/pyraf
   set vcs_says = `git rev-parse --verify HEAD |sed 's/^\(........\).*/\1/'`
   echo '"This is automatically generated at package time.  Do not edit"' > version_vcs.py
   echo "__vcs_revision__ = '${vcs_says}'"                               >> version_vcs.py
   echo 'ADDED version_vcs.py:'
   cat version_vcs.py
endif
# ---------END OF  HACK TO ADD GIT REV INFO ----------------------------------

# Now that we have setup.cfg working better, run sdist to
# generate the version.py file (this imports pyraf) AND generate the .tar.gz file
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
cd $workDir/$pyr/lib/pyraf
#et verinfo1 = `grep '__version__ *=' $workDir/$pyr/lib/pyraf/__init__.py | sed 's/.*= *//' | sed 's/"//g'`
#et verinfo2 = `grep '__svn_version__' $workDir/$pyr/lib/pyraf/sv*.py | sed 's/.*= *//' | sed 's/"//g'`
#et verinfo3 = "${verinfo1}-r$verinfo2"
set verinfo1 = `grep '__version__ *=' $workDir/$pyr/lib/pyraf/version.py |sed 's/.*= *//' |sed "s/'//g"`
if ($use_git != "1") then
   set vcs_says = `${vcsbin}version |sed 's/M//'`
   set verinfo2 = `grep '__svn_revision__ *=' $workDir/$pyr/lib/pyraf/version.py |head -1 |sed 's/.*= *//' |sed "s/'//g"`
else
   # vcs_says is set above
   set verinfo2 = "$vcs_says"
endif

# ---------------- HACK 2 TO WORK AROUND BUGS IN stsci_distutils ---------------
set junk = `echo $verinfo2 |grep Unable.to.determine`
if ("$junk" == "$verinfo2") then
   # __svn_revision__ did not get set, let's set it manually...
   cd $workDir/$pyr/lib/pyraf
   cp version.py version.py.orig2
   cat version.py.orig2 |sed 's/^\( *\)__svn_revision__ *=.*/\1__svn_revision__ = "'${vcs_says}'"/' > version.py
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
   set verinfo2 = "$vcs_says"
endif
# ---------END OF  HACK 2 TO WORK AROUND BUGS IN stsci_distutils ---------------

# set full ver (verinfo3) to be n.m.devNNNNN (if dev) or n.m.rNNNNN (if not)
set junk = `echo $verinfo1 |grep dev`
if ("$junk" == "$verinfo1") then
   if ($use_git == "1") then
       set verinfo3 = "${verinfo1}-${verinfo2}"
   else
       set verinfo3 = "${verinfo1}${verinfo2}"
   endif
else
   if ($use_git == "1") then
      set verinfo3 = "${verinfo1}.${verinfo2}"
   else
      set verinfo3 = "${verinfo1}.r${verinfo2}"
   endif
endif
echo "This build will show a version number of:  $verinfo3 ... is same as $vcs_says ..."
echo "$verinfo3" > ~/.pyraf_tar_ball_ver

# remove svn dirs (not needed if we use sdist)
cd $workDir/$pyr
if ($use_git == "1") then
   /bin/rm -rf `find . -name '.git*'`
   if ($status != 0) then
      echo ERROR cleaning out vcs dirs
      exit 1
   endif
else
   /bin/rm -rf `find . -name '.svn'`
   if ($status != 0) then
      echo ERROR cleaning out vcs dirs
      exit 1
   endif
endif

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
