/* test of color index mode for togl */

#include "togl.h"
#include <Python.h>
#include <stdio.h>

static struct Togl *xtogl;

/* The way this is intended to be used from Python
**
** Calling the init function acts to set the widget create callback
** to call a function whose sole purpose is to return the togl struct
** pointer. A subsequent call to getToglStruct gets that pointer for
** python for future reference in color setting and freeing operations.
** So it is intended that the init function be called after Tk is imported
** but before the togl widget is created. After the togl widget is
** created, getToglStruct should be called and the structure pointer
** (saved as a hex string) should be kept for future use of the color
** functions.
*/

void togl_callback( struct Togl *togl) {
  xtogl = togl;
}

static PyObject *init(PyObject *self, PyObject *args) {
  Togl_CreateFunc( togl_callback );
  Py_INCREF(Py_None);
  return Py_None;
}

static PyObject *getToglStruct(PyObject *self, PyObject *args) {
  char structstr[20]; /* should be enough for 64-bit pointers */
  sprintf(structstr, "%x", xtogl);
  return Py_BuildValue("s",structstr);
}

static PyObject *AllocateColor(PyObject *self, PyObject *args) {
  float red, green, blue;
  char *structstr;
  struct Togl *togl_ptr;
  int colorindex;
  if (!PyArg_ParseTuple(args, "sfff", &structstr, &red, &green, &blue))
        return NULL;
  sscanf(structstr, "%x", &togl_ptr);
  colorindex = (long) Togl_AllocColor(togl_ptr, red, green, blue);
  return Py_BuildValue("i",colorindex);
}

static PyObject *FreeColorIndex(PyObject *self, PyObject *args) {
  int colorindex;
  char *structstr;
  struct Togl *togl_ptr;
  if (!PyArg_ParseTuple(args, "si", &structstr, &colorindex))
        return NULL;
  sscanf(structstr, "%x", &togl_ptr);
  Togl_FreeColor(togl_ptr, (unsigned long) colorindex);
  Py_INCREF(Py_None);
  return Py_None;
}

static PyMethodDef toglcolorsMethods[] = {
  { "init",init,1},
  { "getToglStruct", getToglStruct, 1},
  { "AllocateColor",AllocateColor, 1},
  { "FreeColorIndex",FreeColorIndex, 1},
  {NULL, NULL}
};

void inittoglcolors() {
  PyObject *m;
  m = Py_InitModule("toglcolors",toglcolorsMethods);
}
