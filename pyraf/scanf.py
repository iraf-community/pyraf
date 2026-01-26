"""PyRAF scanf module

Implements a subset of C-style scanf functionality in Python using regular expressions.

Features:

 - Supports %d, %f, %g, %e, %x, %o, %s, %c, %% and %[...] scan sets
 - Handles optional field widths and suppressed assignments (%*d, etc.)
 - Returns parsed values as Python types (int, float, str)
 - Partial matches are allowed; parsing stops at first mismatch
 - Leading whitespace is consumed for most numeric and string conversions

Differences from IRAF scanf:

 - Sexagesimal numbers (hh:mm:ss) are not supported
 - no INDEF handling

Differences from original PyRAF implementation (on purpose, to
establish more conformity to IRAF scanf):

 - "0x" prefix is not allowed when parsing integer values
 - leading zero does not indicate octal when parsing integer values
 - %i, %l, %u, %E, %X are not implemented

Original code was taken from https://github.com/joshburnett/scanf
(version 1.5.2) and heavily modified.

"""
import re
import sys
try:
    from functools import lru_cache
except ImportError:
    from backports.functools_lru_cache import lru_cache


__all__ = ["scanf", 'scanf_translate', 'scanf_compile']


# Each tuple is: (format_regex, regex_pattern, cast_function)
#
# - format_regex: regex to identify the format specifier in the format string.
#   The first group item is always for the optional "*" to suppress conversion.
#   All other groups are used to replace the placeholders in the second pattern.
#
# - regex_pattern: regex to match the corresponding input field.
#   As replacement placeholder, %s is used.
#
# - cast_function: Python callable to convert matched string to int/float/str
#   Setting to None indicates that the match is ignored for the result, otherwise
#   it is called with the first group of the match from the regexp_pattern.
#
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


@lru_cache(maxsize=1000)
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
    # Iterate over the format string, identifying literal text and conversion specifiers
    # For each conversion:
    # - Determine width, suppression, and conversion type
    # - Translate to regex pattern with proper field width
    # - Append regex and cast function to compiled pattern list
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

                # If the assignment is suppressed (indicated by *), the cast function
                # is set to None. This allows regex matching without capturing a value.
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

    # Return compiled list of all patterns
    return [(re.compile(pattern), cast) for pattern, cast in pat_list]


def scanf(format, s):
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

    scanf returns a tuple of found values or None if the format does
    not match.

    """
    # Start scanning input at index 0
    # For each compiled pattern:
    # 1. Apply regex match at current position
    # 2. If no match: break loop and return parsed values so far
    # 3. If match:
    #    - Apply cast function (unless suppressed)
    #    - Advance current index to end of matched substring
    i = 0
    res = []
    for format_re, cast in scanf_compile(format):
        found = format_re.match(s, i)
        if found:
            if cast is not None:
                res.append(cast(found.groups()[0]))
            i = found.end()
        else:
            break

    return res
