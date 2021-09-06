"""Finds device attributes from the graphcap
"""


from stsci.tools import compmixin
from . import filecache


def merge(inlines):
    out = []
    outbuff = []
    for inline in inlines:
        tline = inline.strip()
        if len(tline) > 0 and tline[0] != '#':
            if tline[-1] == '\\':
                # continuation
                outbuff.append(tline[:-1])
            else:
                outbuff.append(tline)
                out.append(''.join(outbuff))
                outbuff = []
    return out


def getAliases(entry):
    # return list of aliases (and dump the comment)
    aend = entry.find(':')
    if aend < 0:
        raise ValueError(f"Graphcap entry does not have any colons\n{entry}")
    return entry[:aend].split("|")[:-1]


def getAttributes(entry):
    abeg = entry.find(':')
    if abeg < 0:
        raise ValueError(f"Graphcap entry does not have any colons\n{entry}")
    astring = entry[abeg + 1:]
    attr = {}
    attrlist = astring.split(':')
    for attrstr in attrlist:
        if attrstr.strip():
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
                        print("problem reading graphcap")
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
        lines = open(self.filename).readlines()
        mergedlines = merge(lines)
        self.dict = getDevices(mergedlines)

    def getValue(self):
        return self.dict

    def __getitem__(self, key):
        """Get up-to-date version of dictionary"""
        thedict = self.get()
        if key not in thedict:
            print("Error: device not found in graphcap")
            raise KeyError()
        return Device(thedict, key)

    def has_key(self, key):
        return self._has(key)

    def __contains__(self, key):
        return self._has(key)

    def _has(self, key):
        thedict = self.get()
        return key in thedict


class Device(compmixin.ComparableMixin):

    def __init__(self, devices, devname):
        self.dict = devices
        self.devname = devname

    def getAttribute(self, attrName):
        thedict = self.dict[self.devname]
        value = None
        while True:
            if attrName in thedict:
                value = thedict[attrName]
                break
            else:
                if 'tc' in thedict:
                    nextdev = thedict['tc']
                    thedict = self.dict[nextdev]
                else:
                    break
        return value

    def _compare(self, other, method):
        if isinstance(other, Device):
            return method(id(self.dict[self.devname]),
                          id(other.dict[other.devname]))
        else:
            return method(id(self), id(other))

    def __getitem__(self, key):
        return self.getAttribute(key)
