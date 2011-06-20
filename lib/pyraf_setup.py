import shutil
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
