#! /usr/bin/env python
# Load all the packages in IRAF and compile all
# the CL scripts, storing the results in the system cache
# Run this in the directory with the system cache

import os, sys, traceback, time

def printcenter(s, length=70, char="-"):
	l1 = (length-len(s))/2
	l2 = length-l1-len(s)
	print l1*char, s, l2*char
	sys.stdout.flush()

# move the old system and user caches
sysCache = 'pyraf.Database'
usrCache = os.path.expanduser('~/iraf/pyraf/pyraf.Database')

if os.path.exists(sysCache): os.rename(sysCache, sysCache + '.old')
if os.path.exists(usrCache): os.rename(usrCache, usrCache + '.old')

# create dummy user cache with protections so that it is
# not readable or writable
# this forces all compiled code to go into the system cache

fh=open(usrCache,'w')
fh.close()
os.chmod(usrCache,0)
print 'Locked user cache to force updates into system cache'
sys.stdout.flush()

# start the timer

t0 = time.time()

# now do the IRAF startup

import pyraf, iraf, iraffunctions, cl2py
from iraftask import IrafCLTask, IrafPkg

iraf.setVerbose()

pkgs_tried = {}
tasks_tried = {}
npkg_total = 0
ntask_total = 0
ntask_failed = 0

# main loop -- keep loading packages as long as there are
# new ones to try, and after loading each package look for
# and initialize any CL tasks

npass = 0
pkg_list = iraf.getPkgList()
keepGoing = 1
while keepGoing and (npkg_total<len(pkg_list)):
	npass = npass + 1
	pkg_list.sort()
	npkg_new = 0
	printcenter("pass %d: %d packages (%d new)" %
		(npass,len(pkg_list),len(pkg_list)-npkg_total), char="=")
	for pkg in pkg_list:
		if not pkgs_tried.has_key(pkg):
			pkgs_tried[pkg] = 1
			npkg_new = npkg_new+1
			printcenter(pkg)
			if pkg in ["newimred","digiphotx"]:
				print """
					Working around bugs in newimred, digiphotx.
					They screw up subsequent loading of imred/digiphot tasks.
					(It happens in IRAF too.)"""
				sys.stdout.flush()
			else:
				try:
					# redirect stdin in case the package tries to
					# prompt for parameters (this aborts but keeps going)
					iraf.load(pkg,kw={'Stdin': 'dev$null'})
				except KeyboardInterrupt:
					print 'Interrupt'
					sys.stdout.flush()
					keepGoing = 0
					break
				except Exception, e:
					sys.stdout.flush()
					traceback.print_exc()
					if isinstance(e,MemoryError):
						keepGoing = 0
						break
					print "...continuing...\n"
					sys.stdout.flush()
			# load tasks after each package
			task_list = iraf.getTaskList()
			task_list.sort()
			for taskname in task_list:
				if not tasks_tried.has_key(taskname):
					tasks_tried[taskname] = 1
					taskobj = iraf.getTask(taskname)
					if isinstance(taskobj, IrafCLTask) and \
							not isinstance(taskobj,IrafPkg):
						ntask_total = ntask_total+1
						print "%d: %s" % (ntask_total, taskname)
						sys.stdout.flush()
						try:
							taskobj.initTask()
						except KeyboardInterrupt:
							print 'Interrupt'
							sys.stdout.flush()
							keepGoing = 0
							break
						except Exception, e:
							sys.stdout.flush()
							traceback.print_exc(10)
							if isinstance(e,MemoryError):
								keepGoing = 0
								break
							print "...continuing...\n"
							sys.stdout.flush()
							ntask_failed = ntask_failed+1
			if not keepGoing: break
	npkg_total = npkg_total + npkg_new
	if not keepGoing: break
	printcenter("Finished pass %d new pkgs %d total pkgs %d total tasks %d" %
		(npass, npkg_new, npkg_total, ntask_total), char="=")
	pkg_list = iraf.getPkgList()

cl2py.codeCache.close()

# get rid of the dummy user cache, and restore the old one
# if it exists

os.chmod(usrCache,0777)
os.remove(usrCache)
if os.path.exists(usrCache + '.old'):
	os.rename(usrCache + '.old', usrCache)

t1 = time.time()
print "Finished package and task loading (%f seconds)" % (t1-t0,)
print "Compiled %d CL tasks -- %d failed" % (ntask_total, ntask_failed)
sys.stdout.flush()
