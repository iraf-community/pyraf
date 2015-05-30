import itertools
import os
import shutil
import subprocess
import sys


def setup_hook(config):
    """
    This setup hook adds additional script files in the platform is Windows.

    It should be noted that this can also be achieved with packaging/distutils2
    enivronment markers, but they are not yet supported by d2to1.

    TODO: Replace this hook script if/when d2to1 adds support for environment
    markers.
    """

    if sys.platform.startswith('win'):
        additional_scripts = [os.path.join('scripts', 'runpyraf.py'),
                              os.path.join('scripts', 'pyraf.bat')]

        # This part has to be unncessary...
        shutil.copy2(os.path.join('scripts', 'pyraf'), additional_scripts[0])

        config['files']['scripts'] += '\n' + '\n'.join(additional_scripts)


def build_ext_hook(command):
    """Adds the correct library directories for X11.  I've found that on Linux
    (or at least RHEL5, though presumably most other common distros) this is
    unncessary.  But on OSX it probably is.  It probably depends on what the
    system default LD_LIBARARY_PATH is.
    """

    lib_dirs, inc_dirs = _find_x()

    for ext in command.extensions:
        for lib_dir in lib_dirs:
            if lib_dir not in ext.library_dirs:
                ext.library_dirs.append(lib_dir)
        for inc_dir in inc_dirs:
            if inc_dir not in ext.include_dirs:
                ext.include_dirs.append(inc_dir)


def _find_x(xdir=None):
    # TODO: Perhaps find a way to pass xdir via an extension option? (though
    # that would work best if and when environment markers are implemented)
    lib_dirs = []
    inc_dirs = []

    if sys.platform.startswith('win'):
       return lib_dirs, inc_dirs

    if xdir is not None:
        lib_dirs.append(os.path.join(xdir, 'lib64'))
        lib_dirs.append(os.path.join(xdir, 'lib'))
        inc_dirs.append(os.path.join(xdir, 'include'))
    elif sys.platform == 'darwin' or sys.platform.startswith('linux'):
        lib_dirs.append('/usr/X11R6/lib64')
        lib_dirs.append('/usr/X11R6/lib')
        inc_dirs.append('/usr/X11R6/include')
    elif sys.platform == 'sunos5' :
        lib_dirs.append('/usr/openwin/lib')
        inc_dirs.append('/usr/openwin/include')
    else:
        try:
            import Tkinter
        except:
            raise ImportError('Tkinter is not installed')
        tk = Tkinter.Tk()
        tk.withdraw()
        tcl_lib = os.path.join(str(tk.getvar('tcl_library')), os.pardir)
        tcl_inc = os.path.join(str(tk.getvar('tcl_library')), os.pardir, os.pardir,
                               'include')
        tk_lib = os.path.join(str(tk.getvar('tk_library')), os.pardir)
        tkv = str(Tkinter.TkVersion)[:3]
        # yes, the version number of Tkinter really is a float...
        if Tkinter.TkVersion < 8.3:
            print('Tcl/Tk v8.3 or later required\n')
            sys.exit(1)
        else:
            suffix = '.so'
            tklib = 'libtk' + tkv + suffix
            pipe = subprocess.Popen(['ldd', os.path.join(tk_lib, tklib)],
                                    stdout=subprocess.PIPE)
            pipe.wait()
            lib_list = pipe.stdout.read()
            for lib in lib_list:
                if lib.startswith('libX11'):
                    ind = lib_list.index(lib)
                    lib_dirs.append(os.path.dirname(lib_list[ind + 2]))
                    inc_dirs.append(os.path.join(
                        os.path.dirname(lib_list[ind + 2]), os.pardir,
                        'include'))

    return lib_dirs, inc_dirs
