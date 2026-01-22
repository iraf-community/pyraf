package testpkg

task clpars = testpkg$clpars.cl
task psetpar = testpkg$psetpar.par
task psetpar1 = testpkg$psetpar1.par

task simplepars psetpars0 psetpars1 = testpkg$spppars.e

clbye()
