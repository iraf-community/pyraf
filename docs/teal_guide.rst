Cookbook for Building TEAL Interfaces
=====================================

Authors: Warren J. Hack, Chris Sontag, Pey Lian Lim
Date: January 30, 2014

The release of the Task Editor And Launcher(TEAL) with STScI_Python
v2.10 in June 2010 provided the tools for building powerful GUI
interfaces for editing the parameters of complex tasks and running those
tasks with minimal effort. Learning how to use something new always
takes a special effort, and this document provides a step-by-step
walkthrough of how to build TEAL interfaces for any Python task to
make this effort as easy as possible.

Introduction
------------

The new TEAL GUI can be added to nearly any Python task that allows users to set parameters to control the operation of the task. Adding a TEAL interface to a Python task requires some minor updates to the task's code in order to allow TEAL to create and control the GUI for setting all the necessary parameters. TEAL itself relies on the `ConfigObj module`_ for the basic parameter handling functions, with additional commands for implementing enhanced logic for controlling the GUI itself based on parameter values. The GUI not only guides the user in setting the parameters, but also provides the capability to load and save parameter sets and the ability to read a help file while still editing the parameters.  The interface to TEAL can also be set up alongside a command-line interface to the task.  This document provides the basic information necessary for implementing a TEAL interface for nearly any Python task to take full advantage of the control it provides the user in setting the task parameters.

This document does not assume the user has any familiarity with using configobj in any manner and as as result includes very basic information which developers with some experience with configobj can simply skip over.

The development of the TEAL interface for the task `resetbits` in the `betadrizzle` package is used as an example.  More elaborate examples will be explained after the development of the TEAL interface for `resetbits` has been described.

Building the Interface
----------------------

The order of operations provided by this document is not the only order in which these steps can be performed.  This order starts with the simplest operation then leads the developer into what needs to be done next with the least amount of iteration.


Step 1: Defining the Parameters
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The primary purpose for developing a TEAL interface is to provide a GUI which can be used to set the values for the task's parameters. This requires that the developer identify the full set of task parameters which the user will be required to provide when running the task. The signature for the task `resetbits` is::

    def reset_dq_bits(input,bits,extver=None,extname='dq')

These parameters now have to be described in a pair of configobj parameter files in order to define the parameters, their types and any validation that may need to be performed on the input values.

Default Values for the Parameters
"""""""""""""""""""""""""""""""""

The first file which needs to be defined provides the default values for each parameter.  Default values can be any string or numerical value, including "" or None.

This task will simply need::

    _task_name_ = resetbits
    input = "*flt.fits"
    bits = 4096
    extver = None
    extname = "dq"

The first line tells TEAL what task should be associated with this file. The default values for `extver` and `extname` simply match the defaults provided in the function signature. No default values were required for the other parameters, but these values were provided to support the most common usage of this task.

This file needs to be saved with a filename extension of `.cfg` in a `pars/` subdirectory of the task's package. For `resetbits`, this file would be saved in the installation directory as the file::

    betadrizzle/lib/pars/resetbits.cfg

This file will then get installed in the directory `betadrizzle/pars/resetbits.cfg` with the instructions on how to set that up coming in the last step of this process.

Parameter Validation Rules
""""""""""""""""""""""""""

The type for the parameter values, along with the definition of any range of valid values, is defined in the second configobj file: the configobj specification (configspec) file or `cfgspc` file.  This file can also provide rules for how the GUI should respond to input values as well, turning the TEAL GUI into an active assistant for the user when editing large or complex sets of parameters.

For this example, we have a very basic set of parameters to define without any advance logic required. TEAL provides validators for a wide range of parameter types, including:

  * `strings`: matches any string
        Defined using `string_kw()`
  * `integer`: matches any integer when a value is always required
        Defined using `integer_kw()`
  * `integer` or `None`: matches any integer or a value of None
        Defined using `integer_or_none_kw()`
  * `float`: matches any floating point value, when a value is always required
        Defined using  `float_kw()`
  * `float` or `None`: matches any floating point value or a value of None
        Defined using `float_or_none_kw()`
  * `boolean`: matches boolean values - ``True`` or ``False``
        Defined using `boolean_kw()`
  * `option`: matches only those values provided in the list of valid options
        Defined using `option_kw()` command with the list of valid values as a parameter

ConfigObj also has support for IP addresses as input parameters, and lists or tuples of any of these basic parameter types. Information on how to use those types, though, can be found within the `ConfigObj module`_ documentation.

With these available parameter types in mind, the parameters for the task can be defined in the configspec file. For the `resetbits` task, we would need::

    _task_name_ = string_kw(default="resetbits")
    input = string_kw(default="*flt.fits", comment="Input files (name, suffix, or @list)")
    bits = integer_kw(default=4096, comment="Bit value in array to be reset to 0")
    extver = integer_or_none_kw(default=None, comment="EXTVER for arrays to be reset")
    extname = string_kw(default="dq", comment= "EXTNAME for arrays to be reset")
    mode = string_kw(default="all")

Each of these parameter types includes a description of the parameter as the `comment` parameter, while default values can also be set using the `default` parameter value. This configspec file would then need to be saved alongside the .cfg file we just created as::

    betadrizzle/lib/pars/resetbits.cfgspc

.. note:: If you find that you need or want to add logic to have the GUI respond to various parameter inputs, this can always be added later by updating the parameter definitions in this file.  A more advanced example demonstrating how this can be done is provided in later sections.


Step 2: TEAL Functions for the Task
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

TEAL requires that a couple of functions be defined within the task in order for the GUI to know how to get the help for the task and to run the task.  The functions that need to be defined are:

  * ``run(configObj)``
      This function serves as the hook to allow the GUI to run the task
  * ``getHelpAsString()``
      This function returns a long string which provides the help for the task

The sole input from TEAL will be a ConfigObj instance, a class which provides all the input parameters and their values after validation by the configobj validators.  This instance gets passed by TEAL to the task's ``run()`` function and needs to be interpreted by that function in order to run the task.

.. note:: The ``run()`` and ``getHelpAsString()`` functions, along with the task's primary user interface function, all need to be in the module with the same name as the task, as TEAL finds the task by importing the taskname. Or, these two functions may instead be arranged as methods of a task class, if desired.

Defining the Help String
""""""""""""""""""""""""

The help information presented by the TEAL GUI comes from the ``getHelpAsString()`` function and gets displayed in a simple ASCII window.  The definition of this function can rely on help information included in the source code as docstrings or from an entirely separate file for tasks which have a large number of parameters or require long explanations to understand how to use the task.  The example from the `resetbits` task was simply::

    def getHelpAsString():
        helpString = 'resetbits Version '+__version__+'\n'
        helpString += __doc__+'\n'

        return helpString

This function simply relies on the module level docstring to describe how to use this task, since it is a simple enough task with only a small number of parameters.

.. note:: The formatting for the docstrings or help files read in by this function can use the numpy documentation restructured text markup format to be compatible with Sphinx when automatically generating documentation on this task using Sphinx. The numpy extension results in simple enough formatting that works well in the TEAL Help window without requiring any translation. More information on this format can be found in the `Numpy Documentation`_ pages.

More complex tasks may require the documentation which would be too long to comfortably fit within docstrings in the code itself.  In those cases, separate files with extended discussions formatted using the numpy restructured text (reST) markup can be written and saved using the naming convention of ```<taskname>.help``` in the same directory as the module. The function can then simply use Python file operations to read it in as a list of strings which are concatenated together and passed along as the output. This operation has been made extremely simple through the definition of a new function within the TEAL package; namely, ``teal.getHelpFileAsString()``.  An example of how this could be used to extend the help file for `resetbits` would be::

    def getHelpAsString():
        helpString = 'resetbits Version '+__version__+__vdate__+'\n'
        helpString += __doc__+'\n'
        helpString += teal.getHelpFileAsString(__taskname__,__file__)

        return helpString

The parameter ``__taskname__`` should already have been defined for the task and gets used to find the file on disk with the name ``__taskname__.help``. The parameter ``__file__`` specifies where the task's module has been installed with the assumption that the help file has been installed in the same directory.  The task `betadrizzle` uses separate files and can be used as an example of how this can be implemented.

Defining How to Run the Task
""""""""""""""""""""""""""""

The ConfigObj instance passed by TEAL into the module needs to be interpreted and used to run the application.  There are a couple of different models which can be used to define the interface between the ``run()`` function and the task's primary user interface function (i.e. how it would be called in a script).

  #. The ``run()`` function interprets the ConfigObj instance and calls the user interface
     function. This works well for tasks which have a small number of parameters.

  #. The ``run()`` function serves as the primary driver for the task and a separate function
     gets defined to provide a simpler interface for the user to call interactively. This
     works well for tasks which have a large number of parameters or sets of parameters
     defined in the ConfigObj interface.

Our simple example for the task ``resetbits`` uses the first model, since it only has the 4 parameters as input. The ``run()`` function can simply be defined in this case as::

    def run(configobj=None):
        ''' Teal interface for running this code. '''

        reset_dq_bits(configobj['input'],configobj['bits'],
                      extver=configobj['extver'],extname=configobj['extname'])

    def reset_dq_bits(input,bits,extver=None,extname='dq'):

Interactive use of this function would use the function ``reset_dq_bits()``.  The TEAL interface would pass the parameter values in through the run function to parse out the parameters and send it to that same function as if it were run interactively.


Step 3: Advertising TEAL-enabled Tasks
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

Any task which has a TEAL interface implemented can be advertised to users of the package through the use of a ``teal`` function: ``teal.print_tasknames()``.  This function call can be added to the package's `__init__.py` module so that everytime the package gets imported, or reloaded, interactively, it will print out a message listing all the tasks which have TEAL GUI's available for use.  This listing will not be printed out when importing the package from another task.  The `__init__.py` module for the `betadrizzle` package has the following lines::

    # These lines allow TEAL to print out the names of TEAL-enabled tasks
    # upon importing this package.
    from stsci.tools import teal
    teal.print_tasknames(__name__, os.path.dirname(__file__))


Step 4: Setting Up Installation
^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^^

The additional files which have been added to the package with the task now need to be installed alongside the module for the task.  Packages in the `STScI_Python` release get installed using Python's `distutils` mechanisms defined through the ``defsetup.py`` module. This file includes a dictionary for `setupargs` that describe the package and the files which need to be installed.  This needs to be updated to include all the new files as ``data_files`` by adding the following line to the ``setupargs`` dictionary definition::

  'data_files':  [(pkg+"/pars",['lib/pars/*']),( pkg, ['lib/*.help'])],

This will add the ConfigObj files in the `pars/` directory to the package while copying any ``.help`` files that were added to the same directory as the module.


Step 5: Testing the GUI
^^^^^^^^^^^^^^^^^^^^^^^

Upon installing the new code, the TEAL interface will be available for the task.  There are a couple of ways of starting the GUI along with a way to grab the ConfigObj instance directly without starting up the GUI at all.

Fundamentally, TEAL is a Python GUI that can be run interactively under any Python interpreter.  It can be called for our example task using the syntax::

    >>> from stsci.tools import teal
    >>> cobj = teal.teal('resetbits')

Getting the ConfigObj Without Starting the GUI
""""""""""""""""""""""""""""""""""""""""""""""

The function for starting the TEAL GUI, ``teal.teal()``, has a parameter to control whether or not to start the GUI at all.  The ConfigObj instance can be returned for the task without starting the GUI by using the `loadOnly` parameter. For our example task, we would use the command::

    >>> cobj = teal.teal('resetbits',loadOnly=True)

The output variable `cobj` can then be passed along or examined depending on what needs to be done at the time.

Advanced Topics
---------------

The topics presented here describe how to take advantage of some of TEAL's more advanced functions for controlling the behavior of the GUI and for working with complex sets of parameters.

Most of the examples for these advanced topics use the ConfgObj files and code defined for betadrizzle.


Parameter Sections
^^^^^^^^^^^^^^^^^^

The ConfigObj specification allows for parameters to be organized into sections of related parameters.  The parameters defined in these sections remain together in a single dictionary within the ConfigObj instance so that they can be passed into tasks or interpreted as a single unit.  Use of sections within TEAL provides for the opportunity to control the GUI's behaviors based on whether or not the parameters in a given section need to be edited by the user.

A parameter section can be defined simply by providing a title using the following syntax in both the .cfg and .cfgspc files::

    [<title>]

In betadrizzle, multiple sections are defined within the parameter interface.  One section has been defined in the .cfg file as::

    [STEP 1: STATIC MASK]
    static = True
    static_sig = 4.0

The .cfgspc definition for this section was specified as::

    [STEP 1: STATIC MASK ]
    static = boolean_kw(default=True, triggers='_section_switch_', comment="Create static bad-pixel mask from the data?")
    static_sig = float_kw(default=4.0, comment= "Sigma*rms below mode to clip for static mask")

These two sets of definitions work together to define the 'STEP 1: STATIC MASK' parameter section within the ConfigObj instance.  A program can then access the parameters in that section using the name of the section as the index in the ConfigObj instance.  The `static` and `static_sig` parameters would be accessed as::

     >>> cobj = teal.teal('betadrizzle',loadOnly=True)
     >>> step1 = cobj['STEP 1: STATIC MASK']
     >>> step1
     {'static': True, 'static_sig': 4.0}
     >>> step1['static']
     True


Section Triggers
^^^^^^^^^^^^^^^^

The behavior of the TEAL GUI can be controlled for each section in a number of ways, primarily as variations on the behavior of turning off the ability to edit the parameters in a section based on another parameters value.  A section parameter can be defined to allow the user to explicitly specify whether or not they need to work with those parameters.  This can the control whether or not the remainder of the parameters are editable through the use of the `triggers` argument in the .cfgspc file for the section parameter.

The supported values for the `triggers` argument currently understood by TEAL are:

    * ``_section_switch_``: Activates/Deactivates the ability to edit the values of the parameters in this section
    * ``_rule<#>_``: Runs the code in this rule (defined elsewhere in the .cfgspc file) to automatically set this parameter, and control the behavior of other parameters like section defintions as well.

The example for defining the section 'STEP 1: STATIC MASK' illustrates how to use the ``_section_switch_`` trigger to control the editing of the parameters in that section.

Another argument defined as ``is_set_by="_rule<#>"`` allows the user to define when this section trigger can be set by other parameters using code and logic provided by the user. The value, ``_rule<#>_`` refers to code in the specified rule (defined at the end of the `.cfgspc` file) to determine what to do. The code which will be run must be found in the configspec file itself, although that code could reference other packages which are already installed.

Use of Rules
^^^^^^^^^^^^

A special section can be appended to the end of the ConfigObj files (.cfg and .cfgspc files) to define rules which can implement nearly arbitrary code to determine how the GUI should treat parameter sections or even individual parameter settings. The return value for a rule should always be a boolean value that can be used in the logic of setting parameter values.

This capability has been implemented in `betadrizzle` to control whether or not whole sections of parameters are even editable (used) to safeguard the user from performing steps which need more than 1 input when only 1 input is provided. The use of the ``_rule<#>_`` trigger can be seen in the `betadrizzle` .cfgspc file::

    _task_name_ = string_kw(default="betadrizzle")
    input = string_kw(default="*flt.fits", triggers='_rule1_', comment="Input files (name, suffix, or @list)")

    <other parameters removed...>

    [STEP 3: DRIZZLE SEPARATE IMAGES]
    driz_separate = boolean_kw(default=True, triggers='_section_switch_', is_set_by='_rule1_', comment= "Drizzle onto separate output images?")
    driz_sep_outnx = float_or_none_kw(default=None, comment="Size of separate output frame's X-axis (pixels)" )

    <more parameters removed, until we get to the end of the file...>

    [ _RULES_ ]
    _rule1_ = string_kw(default='', when='defaults,entry', code='from stsci.tools import check_files; ans={ True:"yes",False:"no"}; OUT = ans[check_files.countInput(VAL) > 1]')

In this case, ``_rule1_`` gets defined in the special parameter section ``[_RULES_]`` and triggered upon the editing of the parameter ``input``.  The result of this logic will then automatically set the value of any section parameter with the ``is_set_by=_rule1_`` argument, such as the parameter ``driz_separate`` in the section ``[STEP 3: DRIZZLE SEPARATE IMAGES]``

The rule is executed within Python via two reserved words: ``VAL``, and ``OUT``.  ``VAL`` is automatically set to the value of the parameter which was used to trigger the execution of the rule, right before the rule is executed.  ``OUT`` will be the outcome of the rule code - the way it returns data to the rule execution machinery without calling a Python `return`.

For the rule itself, one can optionally state (via the ``when`` argument) when the rule will be evaluated.  The currently supported options for the ``when`` argument (used for rules only) are:

   * ``init``: Evaluate the rule upon starting the GUI
   * ``defaults``: Evaluate the rule when the parameter value changes because the user clicked the "Defaults" button
   * ``entry``: Evaluate the rule any time the value is changed in the GUI by the user manually
   * ``fopen``: Evaluate the rule any time a saved file is opened by the user, changing the value
   * ``always``: Evaluate the rule under any of these circumstances

These options can be provided as a comma-separated list for combinations, although care should be taken to avoid any logic problems for when the rule gets evaluated.  If a ``when`` argument is not supplied, the value of ``always`` is assumed.

Tricky Rules
^^^^^^^^^^^^

A parameter can also be controlled by multiple other parameters using the same
rule. The example below shows how to get ``par1`` to be grayed out if
``do_step1`` and ``do_step2`` are both disabled.

In the .cfgspc file::

    _task_name_ = string_kw(default="mytask")
    par1 = string_kw(default="", active_if="_rule1_", comment="Shared parameter")

    <other parameters removed...>

    [STEP 1: FOO]
    do_step1 = boolean_kw(default=True, triggers='_section_switch_', triggers='_rule1_', comment="Do Step 1?")

    <other parameters removed...>

    [STEP 2: BAR]
    do_step2 = boolean_kw(default=True, triggers='_section_switch_', triggers='_rule1_', comment="Do Step 2?")

    <more parameters removed, until we get to the end of the file...>

    [ _RULES_ ]

    _rule1_ = string_kw(default='', code='import mytask; OUT = mytask.tricky_rule(NAME, VAL)')

In mytask.py file::

    MY_FLAGS = {'do_step1': 'yes', 'do_step2': 'yes'}

    def tricky_rule(in_name, in_val):
        global MY_FLAGS
        MY_FLAGS[in_name] = in_val
        if MY_FLAGS['do_step1'] == 'yes' or MY_FLAGS['do_step2'] == 'yes':
            ans = True
        else:
            ans = False
        return ans

For the rule itself, each rule has access to:

    * ``SCOPE``
    * ``NAME`` - Parameter name.
    * ``VAL`` - Parameter value.
    * ``TEAL`` - Reference to the main TEAL object, which knows the value
      of all of its parameters. However, ``TEAL.getValue(NAME)`` returns
      its value *before* it is updated.

To debug your tricky rule, you can add print-out lines to your rule. TEAL log
under ``Help`` menu also shows you what it is doing.


.. _`ConfigObj module`: https://configobj.readthedocs.io
.. _`Numpy Documentation`: https://numpydoc.readthedocs.io/en/latest/format.html
