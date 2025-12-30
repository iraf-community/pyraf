"""
Small scanf implementation.

Python has powerful regular expressions but sometimes they are totally overkill
when you just want to parse a simple-formatted string.
C programmers use the scanf-function for these tasks (see link below).

This implementation of scanf translates the simple scanf-format into
regular expressions. Unlike C you can be sure that there are no buffer overflows
possible.

For more information see
  * http://www.python.org/doc/current/lib/node49.html
  * http://en.wikipedia.org/wiki/Scanf

Original code from:
    https://github.com/joshburnett/scanf (version 1.5.2)

Modified for the needs of PyRAF:
 * all fields may have a max width (not a fixed width)
 * add "l" (for [outdated] long ints)
 * allow "0x" and "0o" prefixes in ints for hexa/octal numbers

Differences to the original PyRAF sscanf module:
 * "n" coversion missing (number of characters so far)


"""
import re
import sys
try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache

__version__ = '1.5.2'

__all__ = ["scanf", 'scanf_translate', 'scanf_compile']


DEBUG = False

def sint(s):
    if s.startswith("0o"):
        return int(s[2:], 8)
    elif s.startswith("0x"):
        return int(s[2:], 16)
    else:
        return int(s)

# As you can probably see it is relatively easy to add more format types.
# Make sure you add a second entry for each new item that adds the extra
#   few characters needed to handle the field ommision.
scanf_translate = [
    (re.compile(_token), _pattern, _cast) for _token, _pattern, _cast in [
        (r"%c", r"(.)", lambda x:x),
        (r"%\*c", r"(?:.)", None),

        (r"%(\d+)c", r"(.{0,%s})", lambda x:x),
        (r"%\*(\d+)c", r"(?:.{0,%s})", None),

        (r"%s", r"(\S+)", lambda x: x),
        (r"%\*s", r"(?:\S+)", None),

        (r"%(\d+)s", r"(\S{1,%s})", lambda x:x),
        (r"%\*(\d+)s", r"(?:\S{1,%s})", None),

        (r"%\[([^\]]+)\]", r"([%s]+)", lambda x:x),
        (r"%\*\[([^\]]+)\]", r"(?:[%s]+)", None),

        (r"%l?[dil]", r"([+-]?(?:0o[0-7]+|0x[\da-fA-F]+|\d+))", sint),
        (r"%\*l?[dil]", r"(?:[+-]?0o[0-7]+|0x[\da-fA-F]+|\d+)", None),

        (r"%(\d+)l?[dil]", r"([+-]?(?:0o[0-7]+|0x[\da-fA-F]+|\d+)", sint),
        (r"%\*(\d+)l?[dil]", r"(?:[+-]?(?:0o[0-7]+|0x[\da-fA-F]+|\d+)", None),

        (r"%l?u", r"(\d+)", int),
        (r"%\*l?u", r"(?:\d+)", None),

        (r"%(\d+)l?u", r"(\d{1,%s})", int),
        (r"%\*(\d+)l?u", r"(?:\d{1,%s})", None),

        (r"%[fgeE]", r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", float),
        (r"%\*[fgeE]", r"(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", None),

        (r"%(\d+)[fgeE]", r"([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", float),
        (r"%\*(\d+)[fgeE]", r"(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", None),

        (r"%l?[xX]", r"((?:0[xX])?[\dA-Za-f]+)", lambda x: int(x, 16)),
        (r"%\*l?[xX]", r"(?:(?:0[xX])?[\dA-Za-f]+)", None),

        (r"%(\d+)l?[xX]", r"((?:0[xX])?[\dA-Za-f]{1,%s})", lambda x: int(x, 16)),
        (r"%\*(\d+)l?[xX]", r"(?:(?:0[xX])?[\dA-Za-f]{1,%s})", None),

        (r"%l?o", r"([0-7]*)", lambda x:int(x, 8)),
        (r"%\*l?o", r"(?:[0-7]*)", None),

        (r"%(\d+)l?o", r"([0-7]{1,%s})", lambda x: int(x, 8)),
        (r"%\*(\d+)l?o", r"(?:[0-7]{1,%s})", None),
    ]]


# Cache formats
SCANF_CACHE_SIZE = 1000


@lru_cache(maxsize=SCANF_CACHE_SIZE)
def scanf_compile(format, collapseWhitespace=True):
    """
    Translate the format into a regular expression

    For example:

        >>> format_re, casts = scanf_compile('%s - %d errors, %d warnings')
        >>> print format_re.pattern
        (\\S+) \\- ([+-]?\\d+) errors, ([+-]?\\d+) warnings

    Translated formats are cached for faster reuse
    """

    format_pat = ""
    cast_list = []
    i = 0
    length = len(format)
    while i < length:
        found = None
        for token, pattern, cast in scanf_translate:
            found = token.match(format, i)
            if found:
                if cast: # cast != None
                    cast_list.append(cast)
                groups = found.groupdict() or found.groups()
                if groups:
                    pattern = pattern % groups
                format_pat += pattern
                i = found.end()
                break
        if not found:
            char = format[i]
            # escape special characters
            if char in "|^$()[]-.+*?{}<>\\":
                format_pat += "\\"
            format_pat += char
            i += 1
    if DEBUG:
        print("DEBUG: %r -> %s" % (format, format_pat))
    if collapseWhitespace:
        format_pat = re.sub(r'\s+', r'\\s+', format_pat)

    format_re = re.compile(format_pat)
    return format_re, cast_list


def scanf(format, s=None, collapseWhitespace=True):
    """Conversion specification are of the form:

        %[*][<max_width>]['l']<type_character>.

    The following format conversions are supported:

    %c            Fixed width character string.
    %s            String of non-whitespace characters with leading
                     whitespace skipped.
    %d, %i, %l    Signed integer (leading 0 => octal, 0x => hex).
    %o            Octal integer.
    %u            Unsigned integer.
    %x            Hexadecimal integer.
    %f, %g, %e    Python float
    %[]           Character scan set

    scanf.scanf returns a tuple of found values or None if the format
    does not match.

    """

    if s is None:
        s = sys.stdin

    if hasattr(s, "readline"):
        s = s.readline()

    format_re, casts = scanf_compile(format, collapseWhitespace)

    found = format_re.search(s)
    if found:
        groups = found.groups()
        return tuple([casts[i](groups[i]) for i in range(len(groups))])
