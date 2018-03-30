from __future__ import division  # confidence high

import sys

from stsci.tools import basicpar
from stsci.tools.irafglobals import yes, no

from pyraf.irafpar import IrafParList


def test_IrafParList(fout=sys.stdout):
    """ Test the IrafParList class """
    # check our input (may be stdout)
    assert hasattr(fout, 'write'), "Input not a file object: "+str(fout)

    # create default, empty parlist for task 'bobs_task'
    pl = IrafParList('bobs_pizza', 'bobs_pizza.par')
    x = pl.getName()
    assert x == 'bobs_pizza.par', "Unexpected name: "+str(x)
    x = pl.getFilename()
    assert x == 'bobs_pizza.par', "Unexpected fname: "+str(x)
    x = pl.getPkgname()
    assert x == '', "Unexpected pkg name: "+str(x)
    assert not pl.hasPar('jojo'), "How did we get jojo?"
    assert pl.hasPar('mode'), "We should have only: mode"
    # length of 'empty' list is 2 - it has 'mode' and '$nargs'
    assert len(pl) == 2, "Unexpected length: "+str(len(pl))
    fout.write("lParam should show 1 par (mode)\n"+pl.lParamStr()+'\n')

    # let's add some pars
    par1 = basicpar.parFactory(
        ('caller','s','a','Ima Hungry','',None,'person calling Bobs'), True)
    x = par1.dpar().strip()
    assert x == "caller = 'Ima Hungry'", "par1 is off: "+str(x)
    par2 = basicpar.parFactory(
        ('diameter','i','a','12','',None,'pizza size'), True)
    x = par2.dpar().strip()
    assert x == "diameter = 12", "par2 is off: "+str(x)
    par3 = basicpar.parFactory(
        ('pi','r','a','3.14159','',None,'Bob makes circles!'), True)
    x = par3.dpar().strip()
    assert x == "pi = 3.14159", "par3 is off: "+str(x)
    par4 = basicpar.parFactory(
        ('delivery','b','a','yes','',None,'delivery? (or pickup)'), True)
    x = par4.dpar().strip()
    assert x == "delivery = yes", "par4 is off: "+str(x)
    par5 = basicpar.parFactory(
        ('topping','s','a','peps','|toms|peps|olives',None,'the choices'), True)
    x = par5.dpar().strip()
    assert x == "topping = 'peps'", "par5 is off: "+str(x)

    pl.addParam(par1)
    assert len(pl) == 3, "Unexpected length: "+str(len(pl))
    pl.addParam(par2)
    pl.addParam(par3)
    pl.addParam(par4)
    pl.addParam(par5)
    assert len(pl) == 7, "Unexpected length: "+str(len(pl))

    # now we have a decent IrafParList to play with - test some
    fout.write("lParam should show 6 actual pars (our 5 + mode)\n" +
               pl.lParamStr() + '\n')
    assert pl.__doc__ == 'List of Iraf parameters', "__doc__ = "+str(pl.__doc__)
    x = sorted(pl.getAllMatches(''))
    assert x == ['$nargs', 'caller', 'delivery', 'diameter', 'mode', 'pi', 'topping'], \
        "Unexpected all: "+str(x)
    x = sorted(pl.getAllMatches('d'))
    assert x == ['delivery', 'diameter'], "Unexpected d's: "+str(x)
    x = sorted(pl.getAllMatches('jojo'))
    assert x == [], "Unexpected empty list: "+str(x)
    x = pl.getParDict()
    assert 'caller' in x, "Bad dict? "+str(x)
    x = pl.getParList()
    assert par1 in x, "Bad list? "+str(x)
    assert pl.hasPar('topping'), "hasPar call failed"
    # change a par val
    pl.setParam('topping', 'olives')  # should be no prob
    assert 'olives' == pl.getParDict()['topping'].value, \
        "Topping error: "+str(pl.getParDict()['topping'].value)
    try:
        # the following setParam should fail - not in choice list
        pl.setParam('topping', 'peanutbutter')  # oh the horror
        raise RuntimeError("The bad setParam didn't fail?")
    except ValueError:
        pass

    # Now try some direct access (also tests IrafPar basics)
    assert pl.caller == "Ima Hungry", 'Ima? '+pl.getParDict()['caller'].value
    pl.pi = 42
    assert pl.pi == 42.0, "pl.pi not 42, ==> "+str(pl.pi)
    try:
        pl.pi = 'strings are not allowed'  # should throw
        raise RuntimeError("The bad pi assign didn't fail?")
    except ValueError:
        pass
    pl.diameter = '9.7'  # ok, string to float to int
    assert pl.diameter == 9, "pl.diameter?, ==> "+str(pl.diameter)
    try:
        pl.diameter = 'twelve'  # fails, not parseable to an int
        raise RuntimeError("The bad diameter assign didn't fail?")
    except ValueError:
        pass
    assert pl.diameter == 9, "pl.diameter after?, ==> "+str(pl.diameter)
    pl.delivery = False  # converts
    assert pl.delivery == no, "pl.delivery not no? "+str(pl.delivery)
    pl.delivery = 1  # converts
    assert pl.delivery == yes, "pl.delivery not yes? "+str(pl.delivery)
    pl.delivery = 'NO'  # converts
    assert pl.delivery == no, "pl.delivery not NO? "+str(pl.delivery)
    try:
        pl.delivery = "maybe, if he's not being recalcitrant"
        raise RuntimeError("The bad delivery assign didn't fail?")
    except ValueError:
        pass
    try:
        pl.topping = 'peanutbutter'  # try again
        raise RuntimeError("The bad topping assign didn't fail?")
    except ValueError:
        pass
    try:
        x = pl.pumpkin_pie
        raise RuntimeError("The pumpkin_pie access didn't fail?")
    except KeyError:
        pass

    # If we get here, then all is well
    # sys.exit(0)
    fout.write("Test successful\n")
    return pl


if __name__ == '__main__':
    pl = test_IrafParList()
