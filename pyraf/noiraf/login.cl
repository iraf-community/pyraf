# LOGIN.CL -- Dummy user login file
#
# This file is used when no IRAF is available.
#
set home = envget("PWD")
set userid = envget("USER")
set uparm = "home$uparm/"
stty xterm
showtype = yes
printf ("\nThis is a minimal PyRAF environment without access to IRAF.\n")
printf ("It just defined the bare-bones functionality needed for PyRAF itself.\n\n")
clpackage
# Default USER package - to be modified by the user
package user
# Basic foreign tasks from UNIX

task $bc $cal $cat $cp $csh $date $df $diff $du $find    = "$foreign"
task $grep $ls $make $man $mv $nm $od $ps $scp $ssh $sh	 = "$foreign"
task $strings $su $top $vi $emacs $w $wc $less $more	 = "$foreign"
task $sync $pwd $cc $gdb $xc $mkpkg $generic $rtar $wtar = "$foreign"
task $tar $bash $tcsh $buglog $who $ssh $scp $mkdir $rm	 = "$foreign"
task $chmod $sort					 = "$foreign"
keep
