# SYSTEM.CL -- Dummy package script task for the SYSTEM package
#
# This file is used when no IRAF is available.
#

package system

# These tasks might be useful to convert to Python where no IRAF exists

#task cmdstr,
#    concatenate,
#    copy,
#    count,
#    delete,
#    directory,
#    files,
#    head,
#    lprint,
#    match,
#    mkdir,
#    movefiles,
#    mtclean,
#    $netstatus,
#    page,
#    pathnames,
#    protect,
#    rename,
#    sort,
#    tail,
#    tee,
#    touch,
#    type,
#    rewind,
#    unprotect,
#    help = "system$x_system.e"
#hidetask cmdstr
#hidetask mtclean

task  mkscript    = "system$mkscript.cl"
task  $news       = "system$news.cl"
task  allocate    = "hlib$allocate.cl"
task  gripes      = "hlib$gripes.cl"
task  deallocate  = "hlib$deallocate.cl"
task  devstatus   = "hlib$devstatus.cl"
task  $diskspace  = "hlib$diskspace.cl"
task  $spy        = "hlib$spy.cl"
task  $devices    = "system$devices.cl"
task  references  = "system$references.cl"
task  phelp       = "system$phelp.cl"

keep
