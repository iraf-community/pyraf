/***********************************************************
Copyright 1991-1995 by Stichting Mathematisch Centrum, Amsterdam,
The Netherlands.

                        All Rights Reserved

Permission to use, copy, modify, and distribute this software and its
documentation for any purpose and without fee is hereby granted,
provided that the above copyright notice appear in all copies and that
both that copyright notice and this permission notice appear in
supporting documentation, and that the names of Stichting Mathematisch
Centrum or CWI not be used in advertising or publicity pertaining to
distribution of the software without specific, written prior permission.

STICHTING MATHEMATISCH CENTRUM DISCLAIMS ALL WARRANTIES WITH REGARD TO
THIS SOFTWARE, INCLUDING ALL IMPLIED WARRANTIES OF MERCHANTABILITY AND
FITNESS, IN NO EVENT SHALL STICHTING MATHEMATISCH CENTRUM BE LIABLE
FOR ANY SPECIAL, INDIRECT OR CONSEQUENTIAL DAMAGES OR ANY DAMAGES
WHATSOEVER RESULTING FROM LOSS OF USE, DATA OR PROFITS, WHETHER IN AN
ACTION OF CONTRACT, NEGLIGENCE OR OTHER TORTIOUS ACTION, ARISING OUT
OF OR IN CONNECTION WITH THE USE OR PERFORMANCE OF THIS SOFTWARE.

******************************************************************/

/*
 * This is a simple C sscanf() analog.  sscanf(input, format) parses
 * the input string according to the format specification and returns
 * a list of the converted values.  The C sscanf() assignment
 * suppression and maximum field width syntax is supported.  An 'l'
 * size modifier causes integer conversions to return a Python
 * long rather than a Python integer; it has no effect for float
 * conversions.
 *
 * Conversion specification are of the form:
 *    %[*][<max_width>]['l']<type_character>.
 *
 * The following format conversions are supported:
 *
 *    %c            Fixed width character string.
 *    %d            Signed integer (leading 0 => octal, 0x => hex).
 *    %f, %g, %e    Python float (C double).
 *    %i            Same as '%d'.
 *    %l            Python long.
 *    %n            Number of characters parsed so far.
 *    %o            Octal integer.
 *    %s            String of non-whitespace characters with leading
 *                     whitespace skipped.
 *    %u            Unsigned integer.
 *    %x            Hexadecimal integer.
 *    %[]           Character scan set.
 *
 * Parsing of the format string stops when the input string is exhausted,
 * so format conversion syntax errors will go undetected until there is
 * enough input to reveal them.
 *
 * There are some differences from C sscanf():
 *
 * 1) The %c conversion scans a fixed-width (default 1) character string
 *    rather than a single character, with no special interpretation of
 *    whitespace.  For example, '%5c' converts the next 5 characters or
 *    the remainder of the input string, whichever is the shorter, into
 *    a Python string.  Some C sscanf() implementations also work this
 *    way.
 *
 * 2) If a field width is specified, it sets the maximum number of
 *    characters, starting from the current position, that will be
 *    considered in the conversion.  C sscanf() conversions tend to
 *    skip white space before imposing the field width.  You can
 *    get the C sscanf() behaviour by inserting a space before the
 *    format specification.
 *
 * To install the module in Python, copy the source file into the
 * Modules directory, add the following line to the Modules/Setup
 * file:
 *    sscanf sscanfmodule.c
 * and do a make.
 *
 */
#include "Python.h"
#include <ctype.h>

/*
 * Size of copy buffer for conversions with a specified field width.
 */
#define FWBUFSIZE    1023

/*
 * Flag array for scansets.  Array is indexed by character,
 * with scanset[char] nonzero if char is in the scanset.
 */
#define BITSPERCHAR    (8 * sizeof(char))
static char scanset[1 << BITSPERCHAR];


/* ----------------------------------------------------- */

static char sscanf_sscanf__doc__[] =
""
;

static PyObject *
sscanf_sscanf( PyObject *self, PyObject *args )
{
    char c, *fmt, *input, *inptr;
    char *s, *start, *end, mfwbuf[FWBUFSIZE + 1];
    int i, base, err, doassign, inplen, ellmod, sense, inprem, width;
    long lval;
    double dval;
    PyObject *item, *list;

    if (!PyArg_ParseTuple(args, "ss;input_string, format_string",
                  &input, &fmt)) {
        return NULL;
    }

    /* Create an empty list object to hold scanned values */
    if ((list = PyList_New(0)) == NULL)
        return NULL;

    inptr = input;
    inplen = strlen(input);

    /*
     * Parse the format string and apply the matches/conversions
     * found to the input string as we go.  Inside the loop, a
     * break generally means that a mismatch of some kind has
     * occurred, and the show is over.
     */
    while ((c = *fmt++) != '\0') {

        /* Skip whitespace? */
        if (isspace(c)) {
            while (isspace(*inptr))
                inptr++;
            continue;
        }

        /* Ordinary character or '%%' match? */
        if (c != '%' || *fmt == '%') {
            if (inptr[0] != c || inptr[1] == '\0')
                break;        /* Mismatch: finished */
            inptr++;
            if (c == '%')
                fmt++;    /* Skip the second '%' */
            continue;
        }

        /*
         * Start of conversion specification.
         */
        c = *fmt++;

        /* Assignment suppression? */
        doassign = 1;
        if (c == '*') {
            c = *fmt++;
            doassign = 0;
        }

        /* Field width? */
        for (width = 0; isdigit(c); c = *fmt++)
            width = width*10 + (c - '0');

        /* 'l' modifier? */
        ellmod = 0;
        if (c == 'l' && strchr("defgilnoux", *fmt) != NULL) {
            ellmod = 1;
            c = *fmt++;
        }

        if (width < 0) {
            PyErr_SetString(PyExc_ValueError, "insane field width");
            goto fail;
        } else if (width == 0) {
            start = inptr;
        } else if (width > FWBUFSIZE) {
            PyErr_SetString(PyExc_ValueError,
                "field width exeeds internal limits");
            goto fail;
        } else {
            /* Copy to max-field-width-buffer */
            inprem = inplen - (inptr - input);
            if (width > inprem)
                width = inprem;
            start = mfwbuf;
            if (width > 0)
                memcpy(start, inptr, width);
            start[width] = '\0';
        }


        /*
         * We have a format conversion - apply it
         * to the input string.
         */
        errno = 0;
        item = NULL;

        if (c == 'c') {

            /* Character field */
            if (*start == '\0')
                break;
            if (width < 1)
                width = 1;
            if (doassign)
                item = PyUnicode_FromStringAndSize(start, width);
            inptr += width;

        } else if (c == 'd' || c == 'i' || c == 'l' ||
               c == 'o' || c == 'u' || c == 'x') {

            /* Python integer or long */
            for (s = start; isspace(*s); s++)
                ;
            if (*s == '\0')
                break;

            /* Fake out '%l' */
            if (c == 'l')
                ellmod = 1;

            if (c == 'o') {
                base = 8;
            } else if (c == 'x') {
                base = 16;
            } else {
                base = 0;
            }

            if (ellmod) {
                /* Result is a Python long */
                if (c == 'u' && *s == '-')    /* Oops */
                    break;
                item = PyLong_FromString(s, &end, base);
                if (item == NULL)
                    goto fail;
                if (end == s) {
                    Py_DECREF(item);
                    break;
                }
                if (doassign == 0) {
                    Py_DECREF(item);
                    item = NULL;
                }
            } else {
                /* Result is a Python integer */
                if (c == 'u')
                    lval = PyOS_strtoul(s, &end, base);
                else
                    lval = PyOS_strtol(s, &end, base);
                if (errno != 0) {
                    PyErr_SetString(PyExc_OverflowError,
                        (c == 'u') ?
                            "unsigned overflow" :
                            "integer overflow");
                    goto fail;
                }
                if (end == s)
                    break;
                if (doassign)
                    item = PyLong_FromLong(lval);
            }
            inptr += end - start;

        } else if (c == 'f' || c == 'g' || c == 'e') {

            /* Python float */
            for (s = start; isspace(*s); s++)
                ;
            if (*s == '\0')
                break;

            dval = strtod(s, &end);
            if (errno != 0) {
                PyErr_SetString(PyExc_OverflowError,
                    "float overflow");
                goto fail;
            }
            if (end == s)
                break;
            if (doassign)
                item = PyFloat_FromDouble(dval);
            inptr += end - start;

        } else if (c == 'n') {

            /* Characters scanned so far */
            if (doassign) {
                lval = inptr - input;
                if (ellmod) {
                    item = PyLong_FromLong(lval);
                } else {
                    item = PyLong_FromLong(lval);
                }
            }

        } else if (c == 's') {

            /* Non-whitespace string */
            for (s = start; isspace(*s); s++)
                ;
            for (end = s; *end && !isspace(*end); end++)
                ;
            if (end == s)
                break;
            if (doassign)
                item = PyUnicode_FromStringAndSize(s, end - s);
            inptr += end - start;

        } else if (c == '[') {

            /* Character scanset */
            c = *fmt++;

            if (c == '^') {
                c = *fmt++;
                sense = 0;
                memset(scanset, 1, sizeof(scanset));
            } else {
                sense = 1;
                memset(scanset, 0, sizeof(scanset));
            }
            scanset[0] = 0;    /* Don't match trailing '\0' */

            if (c == ']') {
                scanset[Py_CHARMASK(c)] = sense;
                c = *fmt++;
            }

            while (1) {
                if (c == '\0') {
                    PyErr_SetString(PyExc_ValueError,
                        "bad scanset specification");
                    goto fail;
                } else if (c == ']') {    /* End of scanset */
                    break;
                } else if (fmt[0] != '-' ||
                       fmt[1] == ']' || fmt[1] < c) {
                    scanset[Py_CHARMASK(c)] = sense;
                    c = *fmt++;
                } else {        /* Character range */
                    for (i = Py_CHARMASK(c);
                         i <= Py_CHARMASK(fmt[1]); i++) {
                        scanset[i] = sense;
                    }
                    fmt += 2;
                    c = *fmt++;
                }
            }

            /* Match characters in the scanset */
            for (end = start; scanset[Py_CHARMASK(*end)]; end++)
                ;
            if (end == start)
                break;
            if (doassign)
                item = PyUnicode_FromStringAndSize(start, end - start);
            inptr += end - start;

        } else {

            PyErr_SetString(PyExc_ValueError,
                "unrecognised format conversion");
            goto fail;
        }

        /*
         * Add the converted value to the result list.
         */
        if (doassign) {
            if (item == NULL)
                goto fail;
            err = PyList_Append(list, item);
            Py_DECREF(item);
            if (err < 0)
                goto fail;
        }

    }

    /* Return the list of converted values */
    return list;

fail:
    Py_DECREF(list);
    return NULL;
}


/* List of methods defined in the module */

static struct PyMethodDef sscanf_methods[] = {
    {"sscanf",    sscanf_sscanf,    1,    sscanf_sscanf__doc__},
    {NULL,        NULL}        /* sentinel */
};


/*
* Initialization function for the module
* - must be called initsscanf on linux/mac
* - must be called initsscanfmodule on windows
*	(idiots.)
*/
#ifdef _WIN32
#define initsscanf initsscanfmodule
#define PyInit_sscanf PyInit_sscanfmodule
#endif

static struct PyModuleDef moduledef = {
        PyModuleDef_HEAD_INIT,
        "sscanf",
        NULL,
        -1,
        sscanf_methods,
        NULL, NULL, NULL, NULL,
};
PyObject* PyInit_sscanf(void)
{
   /* Create the module and add the functions */
   PyObject *m;
   m = PyModule_Create(&moduledef);

   return m;
}
