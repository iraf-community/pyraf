"""
GKI System tests

The first version of this will be under-representative of the GKI
functionality, but tests will be added over time, as code issues are
researched and addressed.

$Id: gki_sys_tests.py 801 2007-08-2 sontag $
"""

import os, sys
import graphcap, iraf, gki, wutil


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
