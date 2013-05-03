#!/bin/csh -f
#
# $Id$
#

if ($#argv != 3) then
   echo "usage:  $0  dev|rel  2|3  py3-bin-dir (only used if py3)"
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
set py3bin = $argv[3]

set svnbin = /usr/bin/svn
if (`uname -n` == "somenode.stsci.edu") then
   set svnbin = svn
endif

# disable for now - all are being 2to3'd on the fly
#set out2to3 = ~/.pyraf_2to3_out
#if (($pyver == 3) && (!(-e $py3bin))) then
#   echo ERROR - py3bin dir does not exist - $py3bin - needed for 2to3ing
#   exit 1
#endif

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
   set co_pyraf = 'co -q -r HEAD http://svn6.assembla.com/svn/pyraf/trunk'
   set co_tools = 'co -q -r HEAD https://svn.stsci.edu/svn/ssb/stsci_python/stsci.tools/trunk'
else
   set pyr = "pyraf-2.1"
   echo -n 'What will the pyraf dir name be? ('$pyr'): '
   set ans = $<
   if ($ans != '') then
      set pyr = $ans
   endif
   set brn = "release_2013_07"
   echo -n 'What is branch name? ('$brn'): '
   set ans = $<
   if ($ans != '') then
      set brn = $ans
   endif
   set co_pyraf = "co -q http://svn6.assembla.com/svn/pyraf/branches/$brn"
   set co_tools = "co -q https://svn.stsci.edu/svn/ssb/stsci_python/stsci.tools/branches/$brn"
endif

# get all source via SVN
echo "Downloading source for: $pyr"
$svnbin $co_pyraf $pyr
if ($status != 0) then
   echo ERROR svn-ing pyraf
   exit 1
endif
# disable following for now as pyraf is being 2to3d on the fly
#if ($pyver == 3) then
#   cd $workDir
#   /bin/rm -f $out2to3.p
#   $py3bin/2to3 -w -n --no-diffs $pyr >& $out2to3.p
#   if ($status != 0) then
#      echo ERROR 2to3-ing pyraf
#      exit 1
#   endif
#   cat $out2to3.p |grep -v ': Skipping implicit ' |grep -v 'gTool: Refactored ' |grep -v 'gTool: No changes to' |grep -v '^RefactoringTool: pyraf' |grep -v '^RefactoringTool: stsci.tools/' |grep -v '^RefactoringTool: distutils/'
#endif

# for now, add svninfo file manually
cd $workDir/$pyr
set rev = `$svnbin info | grep '^Revision:' | sed 's/.* //'`
cd $workDir/$pyr/lib/pyraf
if (!(-e svninfo.py)) then
   echo '__svn_version__ = "'${rev}'"' > svninfo.py
   echo '__full_svn_info__ = ""' >> svninfo.py
   echo '__setup_datetime__ = "'`date`'"' >> svninfo.py
endif

# for now, remove new_setup* (it's confusing to users)
cd $workDir/$pyr
/bin/rm new_setup* >& /dev/null

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
#
# disable following for now as tools is being 2to3d on the fly
#if ($pyver == 3) then
#   cd $workDir/$pyr/required_pkgs
#   /bin/rm -f $out2to3.t
#   $py3bin/2to3 -w -n --no-diffs stsci.tools >& $out2to3.t
#   if ($status != 0) then
#      echo ERROR 2to3-ing stsci.tools
#      exit 1
#   endif
#   cat $out2to3.t |grep -v ': Skipping implicit ' |grep -v 'gTool: Refactored ' |grep -v 'gTool: No changes to' |grep -v '^RefactoringTool: pyraf' |grep -v '^RefactoringTool: stsci.tools/' |grep -v '^RefactoringTool: distutils/'
#endif

# for now, remove new_setup* (it's confusing to users)
cd $workDir/$pyr/required_pkgs/stsci.tools
/bin/rm new_setup* >& /dev/null

# get version info
set verinfo1 = `grep '__version__ *=' $workDir/$pyr/lib/pyraf/__init__.py | sed 's/.*= *//' | sed 's/"//g'`
set verinfo2 = `grep '__svn_version__' $workDir/$pyr/lib/pyraf/sv*.py | sed 's/.*= *//' | sed 's/"//g'`
set verinfo3 = "${verinfo1}-r$verinfo2"
echo "This build will show a version number of:  $verinfo3"
echo "$verinfo3" > ~/.pyraf_tar_ball_ver

# remove svn dirs
cd $workDir/$pyr
/bin/rm -rf `find . -name '.svn'`
if ($status != 0) then
   echo ERROR cleaning out .svn dirs
   exit 1
endif

# edit setup to comment out pyfits requirement (we dont need it for pyraf)
cd $workDir/$pyr/required_pkgs/stsci.tools
if (-e setup.cfg) then
   /bin/cp setup.cfg setup.cfg.orig
   cat setup.cfg.orig |grep -v 'pyfits *(' > setup.cfg
   echo DIFF for all required pkgs/versions
   diff setup.cfg.orig setup.cfg
endif

# edit pyraf setup stuff to use the required_pkgs sub-dir
cd $workDir/$pyr
# change line to: find-links = required_pkgs
if (-e setup.cfg) then
   /bin/cp setup.cfg setup.cfg.orig
   cat setup.cfg.orig | sed 's/^ *find-links *=.*/find-links = required_pkgs/' > setup.cfg
   echo DIFF for find-links
   diff setup.cfg.orig setup.cfg
endif

# tar and zip it - regular (non-win) version
cd $workDir
tar cf $pyr.tar $pyr
if ($status != 0) then
   echo ERROR tarring up
   exit 1
endif
gzip $pyr.tar
if ($status != 0) then
   echo ERROR gzipping
   exit 1
endif

# Now tar/zip the Windows version (via "zip")
if ($isdev == 1) then
   cd $workDir
   zip -rq ${pyr}-win $pyr
   if ($status != 0) then
      echo ERROR zipping up
      exit 1
   endif
endif

echo Successfully created tar-ball
