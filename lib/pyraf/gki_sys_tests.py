"""
GKI System tests

The first version of this will be under-representative of the GKI
functionality, but tests will be added over time, as code issues are
researched and addressed.

$Id$
"""
from __future__ import division # confidence high

import os, sys
from pyraf import iraf
from pyraf import gki


def psdevs_in_graphcap_test():
   """ Verify that the graphcap file supports psdump and psi_land """
   is_in_graphcap('psdump')
   is_in_graphcap('psi_land')

def is_in_graphcap(devname):
   """ Verify that the graphcap file supports a given device name """
   gc = gki.getGraphcap()
   assert gc, "default graphcap not found"
   assert devname in gc, "default graphcap does not support "+devname
   theDev = gc[devname]
   assert theDev.devname==devname, "Invalid graphcap device for "+devname

def opcodeList_test():
   """ Simple aliveness test for the opcode2name dict """
   for opc in gki.GKI_ILLEGAL_LIST:
      assert gki.opcode2name[opc] == 'gki_unknown'

def controlList_test():
   """ Simple aliveness test for the control2name dict """
   for ctl in gki.GKI_ILLEGAL_LIST:
      assert gki.control2name[ctl] == 'control_unknown'

def run_all():
   tsts = sorted([x for x in globals().keys() if x.find('test')>=0], reverse=1)

   for t in tsts:
      func = eval(t)
      print func.__doc__.strip()
      func()

   # If we get here with no exception, we have passed all of the tests
   print "\nSuccessfully passed "+str(len(tsts))+" tests"
   return len(tsts)


#
# main routine
#
if (__name__ == '__main__'):
   run_all()
