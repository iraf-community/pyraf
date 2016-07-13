#!/bin/csh -f
#
setenv TERM xterm
setenv PYRAF_NO_DISPLAY 1

# First create expected output dynamically from the pyraf script itself
# (use `which pyraf` to get the pyraf script to be used below)
/bin/rm -f test_usage.expected >& /dev/null
if ($#argv != 1) then
   echo "usage: $0 full-path-to-pyraf-source-script"
   exit 1
endif
set pyrafscript = $argv[1]
cat $pyrafscript |sed -n '3,$ p' |sed '/"""/,$ d' > test_usage.expected

#
# TRY '--help'
/bin/rm -f test_usage1.txt >& /dev/null
pyraf -s --help >& test_usage1.txt
if ($status != 0) then
   echo ERROR DURING PYRAF CALL
   echo "---------------------------------------------------------------"
   cat test_usage1.txt
   echo "---------------------------------------------------------------"
   exit 1
endif
# remove non-printable garbled first line chars which occur on some platforms
/bin/cp test_usage1.txt test_usage1.txt.orig
cat test_usage1.txt.orig | sed -n '/Copyright/,$ p' > test_usage1.txt

# Do the diff
/usr/bin/diff -Bw test_usage.expected test_usage1.txt
if ($status != 0) then
   echo ERROR DURING DIFF 1
   exit 1
endif

#
# TRY '-h'
/bin/rm -f test_usage2.txt >& /dev/null
pyraf --silent -h >& test_usage2.txt
# remove non-printable garbled first line chars which occur on some platforms
/bin/cp test_usage2.txt test_usage2.txt.orig
cat test_usage2.txt.orig | sed -n '/Copyright/,$ p' > test_usage2.txt

# Do the diff
/usr/bin/diff -Bw test_usage.expected test_usage2.txt
if ($status != 0) then
   echo ERROR DURING DIFF 2
   exit 1
endif

#
# If we get here then the test is successful, but we will print out some
# helpful PyRAF version info, to help in debugging the test runs themselves.
# This output goes to test harness (seen in web page) and is not captured
# or diffed (this kind of use is tested elsewhere).
pyraf -v -c 'print 123; prcache'
exit 0
