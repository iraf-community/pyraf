// Obtain files from source control system.
if (utils.scm_checkout()) return

// Define each build configuration, copying and overriding values as necessary.
bc0 = new BuildConfig()
bc0.nodetype = "linux-stable"
bc0.build_mode = "test"
bc0.env_vars = ['IRAFARCH=linux']
bc0.build_cmds = []
bc0.test_cmds = ["conda config --set auto_update_conda false",
                 "conda config --add channels http://ssb.stsci.edu/astroconda",
                 "conda install -y -q python=2.7 six",
                 "conda install -y -q --only-deps pyraf",
                 "conda install -y -q iraf-all",
                 "mkiraf -f xterm",
                 "source activate base; python setup.py install; pytest lib/pyraf/tests --basetemp=tests_output --junitxml results.xml"]
bc0.failedUnstableThresh = 1
bc0.failedFailureThresh = 6

// Iterate over configurations that define the (distibuted) build matrix.
// Spawn a host of the given nodetype for each combination and run in parallel.
utils.concurrent([bc0])
