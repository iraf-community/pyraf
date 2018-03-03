// Obtain files from source control system.
if (utils.scm_checkout()) return

// Globals
PIP_INST = "pip install"
CONDA_INST = "conda install -y -q"
PY_SETUP = "python setup.py"
PYTEST_ARGS = "--basetemp=tests_output --junitxml results.xml"

matrix_python = ["2.7", "3.5", "3.6"]
matrix_astropy = ["2", "3"]
matrix = []

// Define each build configuration, copying and overriding values as necessary.

// RUN ONCE:
//    PyRAF is technically 2.7-only. Don't bother testing with >2.7.
test27 = new BuildConfig()
test27.nodetype = "linux-stable"
test27.build_mode = "test-suite"
test27.env_vars = []
test27.build_cmds = ["conda config --add channels http://ssb.stsci.edu/astroconda",
                     "${CONDA_INST} python=2.7 iraf-all six",
                     "${CONDA_INST} --only-deps pyraf",
                     "${PY_SETUP} build",
                     "${PY_SETUP} build_ext --inplace"]
test27.test_cmds = ["with_env mkiraf -f xterm",
                    "with_env pytest ${PYTEST_ARGS} lib/pyraf/tests"]
test27.failedUnstableThresh = 1
test27.failedFailureThresh = 6
matrix += test27

// RUN ONCE:
//    "sdist" is agnostic enough to work without any dependencies
sdist = new BuildConfig()
sdist.nodetype = "linux-stable"
sdist.build_mode = "sdist"
sdist.build_cmds = ["${PY_SETUP} sdist"]
matrix += sdist

// Generate installation compatibility matrix
for (python_ver in matrix_python) {
    for (astropy_ver in matrix_astropy) {
        // Astropy >=3.0 no longer supports Python 2.7
        if (python_ver == "2.7" && astropy_ver == "3") {
            continue
        }

        DEPS = "python=${python_ver} astropy=${astropy_ver}"

        install = new BuildConfig()
        install.nodetype = "linux-stable"
        install.build_mode = "install ${DEPS}"
        install.build_cmds = ["${CONDA_INST} ${DEPS}",
                              "${PY_SETUP} egg_info",
                              "${PY_SETUP} install",
                              "pyraf --help",
                              "pyraf --version"]
        matrix += install
    }
}



// Generate dev build compatibility matrix
for (python_ver in matrix_python) {
    PIP_DEPS = ["git+https://github.com/spacetelescope/stsci.tools#egg=stsci.tools --upgrade --no-deps",
                "numpy --upgrade --no-deps",
                "ipython --upgrade",
                "matplotlib --upgrade"]

    install_pypi = new BuildConfig()
    install_pypi.nodetype = "linux-stable"
    install_pypi.build_mode = "install ${python_ver}-DEV"

    // 2.7 doesn't work with Astropy-dev, so skip it.
    if (python_ver == "2.7") {
        PIP_DEPS += ["'astropy<3.0' --force --upgrade --no-deps"]
    }
    else {
        PIP_DEPS += ["Cython",
                     "git+https://github.com/astropy/astropy.git#egg=astropy --upgrade --no-deps"]
    }

    for (dep in PIP_DEPS) {
        install_pypi.build_cmds += "${PIP_INST} ${dep}"
    }
    install_pypi.build_cmds += ["${PY_SETUP} egg_info",
                                "${PY_SETUP} install",
                                "pyraf --help",
                                "pyraf --version"]
    matrix += install_pypi
}


// Iterate over configurations that define the (distibuted) build matrix.
// Spawn a host of the given nodetype for each combination and run in parallel.
utils.concurrent(matrix)
