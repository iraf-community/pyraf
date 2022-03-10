""" Contains the TaskPars class and any related functions.

$Id$
"""


class NoExecError(Exception):
    pass


class TaskPars:
    """ This represents a task's collection of configurable parameters.
    This class is meant to be mostly abstract, though there is some
    functionality included which could be common to most derived classes.
    This also serves to document the interface which must be met for EPAR.
    """

    def getName(self, *args, **kw):
        """ Returns the string name of the task. """
        raise NotImplementedError("class TaskPars is not to be used directly")

    def getPkgname(self, *args, **kw):
        """ Returns the string name of the package, if applicable. """
        raise NotImplementedError("class TaskPars is not to be used directly")

    def getParList(self, *args, **kw):
        """ Returns a list of parameter objects. """
        raise NotImplementedError("class TaskPars is not to be used directly")

    def getDefaultParList(self, *args, **kw):
        """ Returns a list of parameter objects with default values set. """
        raise NotImplementedError("class TaskPars is not to be used directly")

    def setParam(self, *args, **kw):
        """ Allows one to set the value of a single parameter.
            Initial signature is setParam(name, value, scope='', check=1) """
        raise NotImplementedError("class TaskPars is not to be used directly")

    def getFilename(self, *args, **kw):
        """ Returns the string name of any associated config/parameter file. """
        raise NotImplementedError("class TaskPars is not to be used directly")

    def saveParList(self, *args, **kw):
        """ Allows one to save the entire set to a file. """
        raise NotImplementedError("class TaskPars is not to be used directly")

    def run(self, *args, **kw):
        """ Runs the task with the known parameters. """
        raise NoExecError("Bug: class TaskPars is not to be used directly")

    def canPerformValidation(self):
        """ Returns bool.  If True, expect tryValue() to be called next. """
        return False

    def knowAsNative(self):
        """ Returns bool.  Return true if the class prefers in-memory objects
        to keep (know) their parameter values in native format instead of as
        strings. """
        return False

    def getHelpAsString(self):
        """ Meant to be overridden - return a task specific help string. """
        return 'No help string available for task "'+self.getName()+'".\n '+ \
               'Implement getHelpAsString() in your TaskPars sub-class.'

    # also, eparam, lParam, tParam, dParam, tryValue ?
