#include <Python.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xos.h>
#include <X11/Xatom.h>
#include <stdio.h>

/* Windows and cursor manipulations not provided by Tkinter or any other
** standard python library
*/

/* $Id$ */

void moveCursorTo(int win, int x, int y) {
  Display *d;
  Window w;
  Display *XOpenDisplay(char *);
  int s;
  d = XOpenDisplay("eclipse.stsci.edu:0");
  if (d == NULL)
    printf("could not open display!\n");
  w = (Window) win;
  s = XGrabPointer(d,w,True,ButtonPressMask | EnterWindowMask,GrabModeSync,
	GrabModeSync,None,None,CurrentTime);
  XWarpPointer(d,None,w,0,0,0,0,x,y);
  XUngrabPointer(d,CurrentTime);
  XFlush(d);
}

PyObject *wrap_moveCursorTo(PyObject *self, PyObject *args) {
  int x, y, w;
  if (!PyArg_ParseTuple(args,"iii:warp",&w, &x, &y))
    return NULL;
  moveCursorTo(w,x,y);
  return Py_None; 
}

int getWindowID() {
   Display *d;
   Window w;
   int revert;
   Display *XOpenDisplay(char *);
   d = XOpenDisplay(NULL);
   if (d == NULL)
     printf("could not open display!\n");
   XGetInputFocus(d,&w,&revert);
   return (int) w;
}

PyObject *wrap_getWindowID(PyObject *self, PyObject *args) {
  int result;
  result = getWindowID();
  return Py_BuildValue("i",result);
}

void setFocusTo(int win) {
  Window w;
  Display *d;   
  Display *XOpenDisplay(char *);
  w = (Window) win;
  d = XOpenDisplay(NULL);
  if (d == NULL)
    printf("could not open display!\n");
  XSetInputFocus(d,w,0,CurrentTime);
  XFlush(d);
}

PyObject *wrap_setFocusTo(PyObject *self, PyObject *args) {
  int win;
  if (!PyArg_ParseTuple(args,"i:warp", &win))
    return NULL;
  setFocusTo(win);
  return Py_None;
}

static PyMethodDef xlibtricksMethods[] = {
  { "moveCursorTo",wrap_moveCursorTo, 1},
  { "getWindowID",wrap_getWindowID, 1},
  { "setFocusTo",wrap_setFocusTo, 1},
  {NULL, NULL}
};

void initxlibtricks() {
  PyObject *m;
  m = Py_InitModule("xlibtricks", xlibtricksMethods);
}
