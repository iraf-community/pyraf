"""cllinecache.py: Modify linecache so it works with translated CL scripts too

CL scripts have special filename "<CL script taskname>"
"""


import linecache
import os
from stat import ST_SIZE, ST_MTIME
from stsci.tools.irafglobals import IrafError


def checkcache(filename=None, orig_checkcache=linecache.checkcache):
    """Discard cache entries that are out of date.
    (This is not checked upon each call!)"""

    # Rather than repeat linecache.checkcache code, we check & save the
    # CL script entries, call the original function, and then
    # restore the saved entries.  (Modelled after Idle/PyShell.py.)
    cache = linecache.cache
    save = {}
    if filename is None:
        filenames = list(cache.keys())
    else:
        if filename in cache:
            filenames = [filename]
        else:
            return

    from . import iraf  # used below

    for filename in filenames:
        #    for filename in cache.keys():
        if filename[:10] == "<CL script":
            entry = cache[filename]
            del cache[filename]
            # special CL script case - find original script file for time check
            if filename[10:13] == " CL":
                # temporary script created dynamically -- just save it
                save[filename] = entry
            else:
                size, mtime, lines, taskname = entry
                try:
                    taskobj = iraf.getTask(taskname)
                    fullname = taskobj.getFullpath()
                    stat = os.stat(fullname)
                    newsize = stat[ST_SIZE]
                    newmtime = stat[ST_MTIME]
                except (os.error, IrafError):
                    continue
                if size == newsize and mtime == newmtime:
                    # save the ones that didn't change
                    save[filename] = entry

    orig_checkcache()
    cache.update(save)


def updatecache(filename,
                module_globals=None,
                orig_updatecache=linecache.updatecache):
    """Update a cache entry and return its list of lines.  If something's
    wrong, discard the cache entry and return an empty list."""

    if filename[:10] == "<CL script":
        # special CL script case
        return updateCLscript(filename)
    else:
        # original version handles other cases
        if module_globals is None:
            return orig_updatecache(filename)
        else:
            return orig_updatecache(filename, module_globals=module_globals)


def updateCLscript(filename):
    cache = linecache.cache
    if filename in cache:
        del cache[filename]
    try:
        from . import iraf
        taskname = filename[11:-1]
        taskobj = iraf.getTask(taskname)
        fullname = taskobj.getFullpath()
        stat = os.stat(fullname)
        size = stat[ST_SIZE]
        mtime = stat[ST_MTIME]
        lines = taskobj.getCode().split('\n')
        cache[filename] = size, mtime, lines, taskname
        return lines
    except (IrafError, KeyError, AttributeError):
        return []


# insert these symbols into standard linecache module

_original_checkcache = linecache.checkcache
_original_updatecache = linecache.updatecache


def install():
    linecache.checkcache = checkcache
    linecache.updatecache = updatecache


def uninstall():
    linecache.checkcache = _original_checkcache
    linecache.updatecache = _original_updatecache


install()
