"""
GKI System tests

The first version of this will be under-representative of the GKI
functionality, but tests will be added over time, as code issues are
researched and addressed.

$Id$
"""

import os, sys
from pyraf import iraf
from pyraf import gki


def psi_land_in_graphcap_test():
   """ Verify that the graphcap file supports psi_land """
   gc = gki.getGraphcap()
   assert gc, "default graphcap not found"
   assert gc.has_key('psi_land'), "default graphcap does not support psi_land"
   theDev = gc['psi_land']
   assert theDev.devname=='psi_land', "Invalid graphcap device for psi_land"

def opcodeList_test():
   """ Simple aliveness test for the opcode2name dict """
   for opc in gki.GKI_ILLEGAL_LIST:
      assert gki.opcode2name[opc] == 'gki_unknown'

def controlList_test():
   """ Simple aliveness test for the control2name dict """
   for ctl in gki.GKI_ILLEGAL_LIST:
      assert gki.control2name[ctl] == 'control_unknown'

def run_all():
   tsts = [x for x in globals().keys() if x.find('test')>=0]
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
