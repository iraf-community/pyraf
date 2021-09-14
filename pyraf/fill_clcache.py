import os
import glob
from . import cl2py, clcache


def fill_clcache():
    """Fill the system cache with precompiled CL code"""
    cl2py.codeCache = clcache._CodeCache([os.path.join(
        clcache.clcache_path[-1], 'clcache')])
    n_compiled = 0
    n_fail = 0
    for cl_script in glob.glob(os.path.join(os.environ['iraf'], '**/*.cl'),
                               recursive=True):
        try:
            cl2py.cl2py(cl_script)
            n_compiled += 1
        except Exception:
            n_fail += 1
    print(f"Compiled: {n_compiled}, Failed: {n_fail}")


if __name__ == '__main__':
    fill_clcache()
