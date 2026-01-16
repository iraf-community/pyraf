"""Small scanf implementation.

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
 * return partial results for partially matching strings

Differences to the original PyRAF sscanf module:
 * "n" coversion missing (number of characters so far)

"""
import re
import sys
try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache


__all__ = ["scanf", 'scanf_translate', 'scanf_compile']



# As you can probably see it is relatively easy to add more format types.
# Make sure you add a second entry for each new item that adds the extra
#   few characters needed to handle the field ommision.
scanf_translate = [
    (re.compile(_token), _pattern, _cast) for _token, _pattern, _cast in [
        (r"%c", r"(.)", lambda x:x),
        (r"%\*c", r"(?:.)", None),

        (r"%(\d+)c", r"(.{0,%s})", lambda x:x),
        (r"%\*(\d+)c", r"(?:.{0,%s})", None),

        (r"%s", r"\s*(\S*)", lambda x: x),
        (r"%\*s", r"\s*(?:\S*)", None),

        (r"%(\d+)s", r"\s*(\S{0,%s})", lambda x:x),
        (r"%\*(\d+)s", r"\s*(?:\S{0,%s})", None),

        (r"%\[([^\]]+)\]", r"\s*([%s]+)", lambda x:x),
        (r"%\*\[([^\]]+)\]", r"\s*(?:[%s]+)", None),

        (r"%l?d", r"\s*([+-]?\d+)", int),
        (r"%\*l?d", r"\s*(?:[+-]?\d+)", None),

        (r"%(\d+)l?d", r"\s*([+-]?\d{1,%s})", int),
        (r"%\*(\d+)l?d", r"\s*(?:[+-]?\d{1,%s})", None),

        (r"%[fge]", r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", float),
        (r"%\*[fge]", r"\s*(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", None),

        (r"%(\d+)[fge]", r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", float),
        (r"%\*(\d+)[fge]", r"\s*(?:[-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", None),

        (r"%l?x", r"\s*([\dA-Za-f]+)", lambda x: int(x, 16)),
        (r"%\*l?x", r"\s*[\dA-Za-f]+)", None),

        (r"%(\d+)l?x", r"\s*([\dA-Za-f]{1,%s})", lambda x: int(x, 16)),
        (r"%\*(\d+)l?x", r"\s*[\dA-Za-f]{1,%s})", None),

        (r"%l?o", r"\s*([0-7]+)", lambda x:int(x, 8)),
        (r"%\*l?o", r"(?:[0-7]+)", None),

        (r"%(\d+)l?o", r"\s*([0-7]{1,%s})", lambda x: int(x, 8)),
        (r"%\*(\d+)l?o", r"\s*(?:[0-7]{1,%s})", None),
    ]]


# Cache formats
SCANF_CACHE_SIZE = 1000


@lru_cache(maxsize=SCANF_CACHE_SIZE)
def scanf_compile(format):
    """
    Translate the format into a regular expression

    For example:

        >>> re_list = scanf_compile('%s - %d errors, %d warnings')
        >>> for pattern, cast in re_list:
        ...     print(pattern, cast)
        re.compile('(\\S*)') <function <lambda> at 0x7f5da8f1b060>
        re.compile('\\s+\\-\\s+') None
        re.compile('([+-]?(?:0o[0-7]+|0x[\\da-fA-F]+|\\d+))') int
        re.compile('\\s+errors,\\s+') None
        re.compile('([+-]?(?:0o[0-7]+|0x[\\da-fA-F]+|\\d+))') int
        re.compile('\\s+warnings') None

    Translated formats are cached for faster reuse
    """

    pat_list = []
    i = 0
    length = len(format)
    while i < length:
        found = None
        for token, pattern, cast in scanf_translate:
            found = token.match(format, i)
            if found:
                groups = found.groupdict() or found.groups()
                if groups:
                    pattern = pattern % groups
                pat_list.append([pattern, cast])
                i = found.end()
                break
        else:
            char = format[i]
            # escape special characters
            if char in "|^$()[]-.+*?{}<>\\":
                char = "\\" + char
            if len(pat_list) and pat_list[-1][1] is None:
                pat_list[-1][0] += char
            else:
                pat_list.append([char, None])
            i += 1

    # Compile all patterns, collapsing whitespaces
    re_list = []
    for pattern, cast in pat_list:
        if cast is None:
            pattern = re.sub(r'\s+', r'\\s*', pattern)
        re_list.append((re.compile(pattern), cast))

    return re_list


def scanf(format, s=None, collapseWhitespace=True):
    """Conversion specification are of the form:

        %[*][<max_width>]['l']<type_character>.

    The following format conversions are supported:

    %c            Fixed width character string.
    %s            String of non-whitespace characters with leading
                     whitespace skipped.
    %d            Signed integer
    %o            Octal integer.
    %x            Hexadecimal integer.
    %f, %g, %e    Float
    %[]           Character scan set

    scanf.scanf returns a tuple of found values or None if the format
    does not match.

    """
    if s is None:
        s = sys.stdin

    if hasattr(s, "readline"):
        s = s.readline()

    i = 0
    res = []
    for format_re, cast in scanf_compile(format):
        found = format_re.match(s, i)
        if found:
            if cast:
                res.append(cast(found.groups()[0]))
            i = found.end()
        if not found or i == len(s):
            break

    if len(res) > 0:
        return tuple(res)
    else:
        return None
