#include <Python.h>
#include <X11/X.h>
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
  /*  Display *XOpenDisplay(char *); */
  int s;
  d = XOpenDisplay(NULL);
  if (d == NULL) {
    printf("could not open display!\n");
    return; 
  }
  w = (Window) win;
  s = XGrabPointer(d,w,True,ButtonPressMask | EnterWindowMask,GrabModeSync,
	GrabModeSync,None,None,CurrentTime);
  XWarpPointer(d,None,w,0,0,0,0,x,y);
  XUngrabPointer(d,CurrentTime);
  XFlush(d);
  XCloseDisplay(d);
}

PyObject *wrap_moveCursorTo(PyObject *self, PyObject *args) {
  int x, y, w;
  if (!PyArg_ParseTuple(args,"iii",&w, &x, &y))
    return NULL;
  moveCursorTo(w,x,y);
  return Py_None; 
}

int getWindowID() {
   Display *d;
   Window w;
   int revert;
   /*  Display *XOpenDisplay(char *); */
   d = XOpenDisplay(NULL);
   if (d == NULL) {
     printf("could not open display!\n");
     return -1;
	}
   XGetInputFocus(d,&w,&revert);
   XFlush(d);
   XCloseDisplay(d);
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
  /* Display *XOpenDisplay(char *); */
  w = (Window) win;
  d = XOpenDisplay(NULL);
  if (d == NULL) {
    printf("could not open display!\n");
    return;
  }
  XSetInputFocus(d,w,0,CurrentTime);
  XFlush(d);
  XCloseDisplay(d);
}

PyObject *wrap_setFocusTo(PyObject *self, PyObject *args) {
  int win;
  if (!PyArg_ParseTuple(args,"i", &win))
    return NULL;
  setFocusTo(win);
  return Py_None;
}

void setBackingStore(int win) {
  Window w;
  XWindowAttributes wa;
  XSetWindowAttributes  NewWinAttributes;
  Display *d;
  /*  Display *XOpenDisplay(char *); */
  Status XGetWindowAttributes(Display *, Window, XWindowAttributes *);
  int XChangeWindowAttributes(Display *, Window, unsigned long, 
			       XSetWindowAttributes *);
  w = (Window) win;
  d = XOpenDisplay(NULL);
  if (d == NULL) {
    printf("could not open display!\n");
    return;
  }
  XGetWindowAttributes(d, w, &wa);
  if (XDoesBackingStore(wa.screen) != NotUseful) {
    NewWinAttributes.backing_store = Always;
    XChangeWindowAttributes(d, w, CWBackingStore, &NewWinAttributes);
  }
  XFlush(d);
  XCloseDisplay(d);
}

PyObject *wrap_setBackingStore(PyObject *self, PyObject *args) {
  int win;
  if (!PyArg_ParseTuple(args,"i", &win))
    return NULL;
  setBackingStore(win);
  return Py_None;
}

void getWindowAttributes(int win, XWindowAttributes *winAttr) {
  Window w;
  Display *d;
  /*  Display *XOpenDisplay(char *); */
  Status XGetWindowAttributes(Display *, Window, XWindowAttributes *);
  w = (Window) win;
  d = XOpenDisplay(NULL);
  if (d == NULL) {
    printf("could not open display!\n");
    return;
  }
  XGetWindowAttributes(d, w, winAttr);
  XCloseDisplay(d);
}

PyObject *wrap_getWindowAttributes(PyObject *self, PyObject *args) {
	int win, viewable;
	XWindowAttributes wa;
	if (!PyArg_ParseTuple(args,"i", &win))
		return NULL;
	getWindowAttributes(win, &wa);
	if (wa.map_state == IsViewable) {
	  viewable = 1;
	} else {
	  viewable = 0;
	}
	return Py_BuildValue("{s:i,s:i,s:i,s:i,s:i,s:i,s:i}",
		"x", wa.x,
		"y", wa.y,
		"rootID", (int) wa.root,
		"width", wa.width,
		"height", wa.height,
		"borderWidth", wa.border_width,
		"viewable", viewable);
}

PyObject *wrap_getPointerPosition(PyObject *self, PyObject *args) {
	int win;  
	Window w;
	Bool inScreen;
	Window root, child;
	int root_x, root_y, win_x, win_y;
	unsigned int mask;
	Display *d;
	/* Display *XOpenDisplay(char *); */
	Bool XQueryPointer(Display *, Window, Window *, Window *,
		int *, int *, int *, int *, unsigned int *);	
	if (!PyArg_ParseTuple(args,"i", &win))
		return NULL;
	w = (Window) win;
	d = XOpenDisplay(NULL);
	if (d == NULL) {
		printf("could not open display!\n");
		return;
	}
	inScreen = XQueryPointer(d, w, &root, &child, &root_x, &root_y,
		&win_x, &win_y, &mask);
	XCloseDisplay(d);
	return Py_BuildValue("{s:i,s:i,s:i,s:i,s:i,s:i,s:i}",
		"inScreen", (int) inScreen,
		"rootID", (int) root,
		"childID", (int) child,
		"root_x", root_x,
		"root_y", root_y,
		"win_x", win_x,
		"win_y", win_y);
}

PyObject *wrap_getParentID(PyObject *self, PyObject *args) {

	int win;  
	Window w;
	Window root, parent, *children;
	unsigned int nchildren;
	Display *d;
	/*	Display *XOpenDisplay(char *); */
	Status XQueryTree(Display *, Window, Window *, Window *,
		Window **, unsigned int *);
	if (!PyArg_ParseTuple(args,"i", &win))
		return NULL;
	w = (Window) win;
	d = XOpenDisplay(NULL);
	if (d == NULL) {
		printf("could not open display!\n");
		return;
	}
	XQueryTree(d, w, &root, &parent, &children, &nchildren);
	XFree(children);
	XCloseDisplay(d);
	if (root == parent) {
	  return Py_None;
	} else {
	  return Py_BuildValue("i", (int) parent);
	}
}

static PyMethodDef xlibtricksMethods[] = {
  { "moveCursorTo",wrap_moveCursorTo, 1},
  { "getWindowID",wrap_getWindowID, 1},
  { "setFocusTo",wrap_setFocusTo, 1},
  { "setBackingStore",wrap_setBackingStore, 1},
  { "getWindowAttributes",wrap_getWindowAttributes, 1},
  { "getPointerPosition",wrap_getPointerPosition, 1},
  { "getParentID",wrap_getParentID, 1},
  {NULL, NULL}
};

void initxlibtricks() {
  PyObject *m;
  m = Py_InitModule("xlibtricks", xlibtricksMethods);
}
