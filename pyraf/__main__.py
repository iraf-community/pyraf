#! /usr/bin/env python3
import sys
import os
import shutil
import argparse

from stsci.tools import capable
from stsci.tools.irafglobals import yes, no, INDEF, EOF
from . import iraf
from .irafpar import makeIrafPar

try:
    import IPython
except ImportError:
    IPython = None

def main():
    if "." not in sys.path:
        sys.path.insert(0, ".")

    from . import __version__


    # command-line options
    desc = '''
    PyRAF is a command language for running IRAF tasks in a Python
    environment.
    '''
    epilog = '''
    For more info on PyRAF and IRAF see https://iraf-community.github.io
    '''
    parser = argparse.ArgumentParser(prog='pyraf', description=desc,
                                     epilog=epilog)
    parser.add_argument('-c', '--command',
                        help='Command passed in as string'
                             ' (any valid PyRAF command)',
                        metavar='cmd')
    parser.add_argument('-e', '--ecl',
                        help='Turn on ECL mode',
                        action='store_true', default=False)
    parser.add_argument('-m','--commandwrapper',
                        help='Run command line wrapper to provide extra'
                             ' capabilities (default)',
                        action='store_true', dest='commandwrapper',
                        default=True)
    parser.add_argument('-i','--no-commandwrapper',
                        help='No command line wrapper, just run standard'
                             ' interactive Python shell',
                        action='store_false', dest='commandwrapper')
    parser.add_argument('-n', '--nosplash',
                        help='No splash screen during startup (also see -x)',
                        action='store_true', default=not capable.OF_GRAPHICS)
    parser.add_argument('-s', '--silent',
                        help='Silent initialization (does not print'
                             ' startup messages)',
                        action='store_true', default=False)
    parser.add_argument('-V', '--version',
                        help='Print version info and exit',
                        action='version', version=__version__)
    parser.add_argument('-v', '--verbose',
                        help='Set verbosity level (may be repeated'
                             ' to increase verbosity)',
                        action='count', default=0)
    parser.add_argument('-x', '--nographics',
                        help='No graphics will be attempted/loaded'
                             ' during session',
                        action='store_true', default=False)
    if IPython is not None:
        parser.add_argument('-y', '--ipython',
                            help='Run the IPython shell instead of the normal'
                            ' PyRAF command shell',
                            action='store_true', default=False)

    parser.add_argument('savefile',
                        help='Optional savefile to start from',
                        nargs='?')

    # allow the use of PYRAF_ARGS
    extraArgs = os.environ.get('PYRAF_ARGS', '').split()

    # Special case that the executable is called epyraf --> ECL mode
    if sys.argv[0] == 'epyraf':
        extraArgs.append('-e')

    args = parser.parse_args(sys.argv[1:] + extraArgs)

    # handle any warning supression right away, before any more imports
    if args.silent:
        import warnings
        warnings.simplefilter("ignore")

    # allow them to specifiy no graphics, done before any imports
    if args.nographics:
        os.environ['PYRAF_NO_DISPLAY'] = '1'  # triggers on the rest of PyRAF
        capable.OF_GRAPHICS = False
        args.nosplash = True

    from . import pyrafglobals
    pyrafglobals._use_ecl = args.ecl

    from . import iraf
    iraf.setVerbose(args.verbose)

    # If not silent and graphics is available, use splash window
    if args.silent:
        splash_screen = None
        initkw = {'doprint': False, 'hush': True}
    else:
        initkw = {}
        if not args.nosplash:
            from . import splash
            splash_screen = splash.splash(f'PyRAF {__version__}')
        else:
            splash_screen = None

    if args.verbose > 0:
        print("pyraf: splashed")

    # read the user's startup file (if there is one)
    if 'PYTHONSTARTUP' in os.environ and \
            os.path.isfile(os.environ["PYTHONSTARTUP"]):
        exec(
            compile(
                open(os.environ["PYTHONSTARTUP"]).read(),
                os.environ["PYTHONSTARTUP"], 'exec'))

    if args.savefile:
        iraf.Init(savefile=args.savefile, **initkw)
    else:
        iraf.Init(**initkw)

    if args.verbose > 0:
        print("pyraf: finished iraf.Init")

    if splash_screen is not None:
        splash_screen.Destroy()

    if not args.silent:
        print(f"PyRAF {__version__}")

    if args.command:
        iraf.task(cmd_line=args.command, IsCmdString=True)
        iraf.cmd_line()
    elif IPython is not None and args.ipython:
        if args.silent:
            IPython.embed(banner1='')
        else:
            IPython.embed()
    elif args.commandwrapper:
        from . import pycmdline
        cmdline = pycmdline.PyCmdLine(locals=globals())
        if args.silent:
            cmdline.start('')  # use no banner
        else:
            cmdline.start()  # use default banner
    else:
        # run the standard Python interpreter
        import code
        if args.silent:
            code.interact(banner='', local=locals(), exitmsg='')
        else:
            code.interact(local=locals())


if __name__ == '__main__':
    main()
