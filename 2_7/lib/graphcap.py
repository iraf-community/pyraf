"""Finds device attributes from the graphcap

$Id$
"""

import string, filecache

def merge(inlines):
    out = []
    outbuff = []
    for inline in inlines:
        tline = string.strip(inline)
        if len(tline) > 0 and tline[0] != '#':
            if tline[-1] == '\\':
                # continuation
                outbuff.append(tline[:-1])
            else:
                outbuff.append(tline)
                out.append(string.join(outbuff,''))
                outbuff = []
    return out

def getAliases(entry):
    # return list of aliases (and dump the comment)
    aend = string.find(entry,':')
    if aend<0:
        raise ValueError("Graphcap entry does not have any colons\n%s" % entry)
    return string.split(entry[:aend], "|")[:-1]

def getAttributes(entry):
    abeg = string.find(entry,':')
    if abeg<0:
        raise ValueError("Graphcap entry does not have any colons\n%s" % entry)
    astring = entry[abeg+1:]
    attr = {}
    attrlist = string.split(astring,':')
    for attrstr in attrlist:
        if string.strip(attrstr):
            attrname = attrstr[:2]
            attrval = attrstr[2:]
            if len(attrstr) <= 2:
                value = -1
            elif attrval[0] == '=':
                value = attrval[1:]
            elif attrval[0] == '#':
                try:
                    value = int(attrval[1:])
                except ValueError:
                    try:
                        value = float(attrval[1:])
                    except ValueError:
                        print "problem reading graphcap"
                        raise
            elif attrval[0] == '@':
                # implies false
                value = None
            else:
                # ignore silently, at least as long as IRAF has a bad
                # entry in its distribution (illegal colons)
                # print "problem reading graphcap attributes: ", attrstr
                # print entry
                pass
            attr[attrname] = value
    return attr

def getDevices(devlist):
    devices = {}
    for devdef in devlist:
        aliases = getAliases(devdef)
        attributes = getAttributes(devdef)
        for alias in aliases:
            devices[alias] = attributes
    return devices

class GraphCap(filecache.FileCache):

    """Graphcap class that automatically updates if file changes"""

    def __init__(self, graphcapPath):
        filecache.FileCache.__init__(self, graphcapPath)

    def updateValue(self):
        """Called on init and if file changes"""
        lines = open(self.filename,'r').readlines()
        mergedlines = merge(lines)
        self.dict = getDevices(mergedlines)

    def getValue(self):
        return self.dict

    def __getitem__(self, key):
        """Get up-to-date version of dictionary"""
        dict = self.get()
        if not dict.has_key(key):
            print "Error: device not found in graphcap"
            raise KeyError
        return Device(dict, key)

    def has_key(self, key):
        dict = self.get()
        if dict.has_key(key):
            return 1
        else:
            return 0

class Device:

    def __init__(self, devices, devname):
        self.dict = devices
        self.devname = devname

    def getAttribute(self, attrName):
        dict = self.dict[self.devname]
        value = None
        while 1:
            if dict.has_key(attrName):
                value = dict[attrName]
                break
            else:
                if dict.has_key('tc'):
                    nextdev = dict['tc']
                    dict = self.dict[nextdev]
                else:
                    break
        return value

    def __cmp__(self, other):
        if isinstance(other, Device):
            return cmp(id(self.dict[self.devname]),
                            id(other.dict[other.devname]))
        else:
            return cmp(id(self), id(other))

    def __getitem__(self, key):
        return self.getAttribute(key)
