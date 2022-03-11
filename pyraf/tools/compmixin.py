#!/usr/bin/env python
#
"""
   This module is from Lennart Regebro's ComparableMixin class, available at:

       http://regebro.wordpress.com/2010/12/13/
              python-implementing-rich-comparison-the-correct-way/

   The idea is to prevent you from having to define lt,le,eq,ne,etc...
   This may no longer be necessary after the functools total_ordering
   decorator (Python v2.7) is available on all Python versions
   supported by our software.

   For simple comparisons, all that is necessary is to derive your class
   from ComparableMixin and override the _cmpkey() method.

   For more complex comparisons (where type-checking needs to occur and
   comparisons to other types are allowed), simply override _compare() instead
   of _cmpkey().
"""


class ComparableMixin:
    def _compare(self, other, method):
        try:
            return method(self._cmpkey(), other._cmpkey())
        except (AttributeError, TypeError):
            # _cmpkey not implemented, or return different type,
            # so I can't compare with "other".
            return NotImplemented

    def __lt__(self, other):
        return self._compare(other, lambda s,o: s < o)

    def __le__(self, other):
        return self._compare(other, lambda s,o: s <= o)

    def __eq__(self, other):
        return self._compare(other, lambda s,o: s == o)

    def __ge__(self, other):
        return self._compare(other, lambda s,o: s >= o)

    def __gt__(self, other):
        return self._compare(other, lambda s,o: s > o)

    def __ne__(self, other):
        return self._compare(other, lambda s,o: s != o)


class ComparableIntBaseMixin(ComparableMixin):
    """ For those classes which, at heart, are comparable to integers. """
    def _compare(self, other, method):
        if isinstance(other, self.__class__): # two objects of same class
            return method(self._cmpkey(), other._cmpkey())
        else:
            return method(int(self._cmpkey()), int(other))


class ComparableFloatBaseMixin(ComparableMixin):
    """ For those classes which, at heart, are comparable to floats. """
    def _compare(self, other, method):
        if isinstance(other, self.__class__): # two objects of same class
            return method(self._cmpkey(), other._cmpkey())
        else:
            return method(float(self._cmpkey()), float(other))
