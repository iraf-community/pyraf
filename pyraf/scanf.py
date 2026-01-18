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

# The first group item in the match is always for the optional "*"
# indicating that the field shall be skipped. Optional other item is
# the length which will replace the "%s" in the pattern.
scanf_translate = [
    (re.compile(_token), _pattern, _cast) for _token, _pattern, _cast in [
        # %c - Fixed width character string
        (r"%(\*)?c", r"(.)", lambda x:x),
        (r"%(\*)?(\d+)c", r"(.{1,%s})", lambda x:x),

        # %s - String of non-whitespace characters
        (r"%(\*)?s", r"\s*(\S+)", lambda x: x),
        (r"%(\*)?(\d+)s", r"\s*(\S{1,%s})", lambda x:x),

        # %[] - Character scan set
        (r"%(\*)?\[([^\]]+)\]", r"\s*([%s]+)", lambda x:x),

        # %d - Signed integer
        (r"%(\*)?l?d", r"\s*([+-]?\d+)", int),
        (r"%(\*)?(\d+)l?d", r"\s*([+-]?\d{1,%s})", int),

        # %f, %g, %e - Float
        (r"%(\*)?[fge]", r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", float),
        (r"%(\*)?(\d+)[fge]", r"\s*([-+]?(?:\d+(?:\.\d*)?|\.\d+)(?:[eE][-+]?\d+)?)", float),

        # %x - Hexadecimal integer.
        (r"%(\*)?l?x", r"\s*([-+]?[\da-fA-F]+)", lambda x: int(x, 16)),
        (r"%(\*)?(\d+)l?x", r"\s*([-+]?[\dA-Fa-f]{1,%s})", lambda x: int(x, 16)),

        # %o - Octal integer.
        (r"%(\*)?l?o", r"\s*([-+]?[0-7]+)", lambda x:int(x, 8)),
        (r"%(\*)?(\d+)l?o", r"\s*([-+]?[0-7]{1,%s})", lambda x: int(x, 8)),

        # %% - single percent sign
        (r"%%", r"%", None),

        # white spaces
        (r"\s+", r"\s*", None),

        # special chars in regexps
        (r"()([\\^$.|?*+()[\]{}-])", r"\%s", None),

        # All other non-whitespaces
        (r"()([^\s\\^$.|?*+()[\]{}%-]+)", r"%s", None),
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
                groups = found.groups()

                # Add optional argument (length) to pattern
                if len(groups) > 1:
                    pattern = pattern % groups[1:]

                # Ignore this format pattern
                if len(groups) > 0 and groups[0] == "*":
                    cast = None

                if cast is None and len(pat_list) > 0 and pat_list[-1][1] is None:
                    # Combine all subsequent non-consuming patterns into one
                    pat_list[-1][0] += pattern
                else:
                    pat_list.append([pattern, cast])
                i = found.end()
                break
        else:
            raise ValueError(f"Unknown char '{format[i]}' in pos {i} of format string \"{format}\"")

    # Compile all patterns
    re_list = []
    for pattern, cast in pat_list:
        re_list.append((re.compile(pattern), cast))

    return re_list


def scanf(format, s=None, collapseWhitespace=True):
    """Conversion specification are of the form:

        %[*][<max_width>]['l']<type_character>.

    The following format conversions are supported:

    %c            Fixed width character string.
    %s            String of non-whitespace characters
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

    return res
