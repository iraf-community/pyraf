#include <Python.h>
#include <X11/X.h>
#include <X11/Xlib.h>
#include <X11/Xutil.h>
#include <X11/Xos.h>
#include <X11/Xatom.h>
#include <stdio.h>
#include <setjmp.h>
#include <string.h>

/* $Id$ */

/* Windows and cursor manipulations not provided by Tkinter or any other 
** standard python library 
*/ 

/* the following macro is used to trap x window exceptions and trigger 
** a python exception in turn 
*/

jmp_buf ErrorEnv;
int xstatus;
int (* oldErrorHandler)(Display *);
int (* oldIOErrorHandler)(Display *);
char XErrorMsg[80];
char ErrorPrefix[] = "XWindows Error!\n";
char ErrorMsg[120];

#define TrapXlibErrors \
  oldIOErrorHandler = XSetIOErrorHandler(&MyXlibErrorHandler); \
  oldErrorHandler = XSetErrorHandler(&MyXlibErrorHandler); \
  xstatus = setjmp(ErrorEnv); \
  if ( xstatus != 0) { \
    XSetIOErrorHandler(oldIOErrorHandler); \
    XSetErrorHandler(oldErrorHandler); \
    strncat(ErrorMsg,ErrorPrefix, 20); \
    strncat(ErrorMsg,XErrorMsg, 80); \
    PyErr_SetString(PyExc_EnvironmentError, ErrorMsg); \
    return NULL; \
  }

#define RestoreOldXlibErrorHandlers \
	XSetIOErrorHandler(oldIOErrorHandler); \
	XSetErrorHandler(oldErrorHandler); 

/* Exception handler for Xwindows I/O errors */

int MyXlibErrorHandler(Display *d, XErrorEvent *myerror) {
	XGetErrorText(d, myerror->error_code, XErrorMsg, 80);
	longjmp(ErrorEnv, 1);
}

void moveCursorTo(int win, int x, int y) {
  Display *d;
  Window w;
  /*  Display *XOpenDisplay(char *); */
  int s;
  d = XOpenDisplay(NULL);
  if (d == NULL) {
    /* printf("could not open XWindow display\n"); */
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
  TrapXlibErrors /* macro code to handle xlib exceptions */
  moveCursorTo(w,x,y);
  RestoreOldXlibErrorHandlers /* macro */
  return Py_None; 
}

int getWindowID() {
   Display *d;
   Window w;
   int revert;
   /*  Display *XOpenDisplay(char *); */
   d = XOpenDisplay(NULL);
   if (d == NULL) {
     /* printf("could not open XWindow display\n"); */
     return -1;
	}
   XGetInputFocus(d,&w,&revert);
   XFlush(d);
   XCloseDisplay(d);
   return (int) w;
}

PyObject *wrap_getDeepestVisual(PyObject *self, PyObject *args) {
  int depth;
  TrapXlibErrors /* macro code to handle xlib exceptions */
  depth = getDeepestVisual();
  RestoreOldXlibErrorHandlers /* macro */
  return Py_BuildValue("i",depth);
}

int getDeepestVisual() {
  Display *d;   
  XVisualInfo vTemplate;
  XVisualInfo *visualList;
  int i, visualsMatched, maxDepth;
  maxDepth = 1;
  d = XOpenDisplay(NULL);
  visualList = XGetVisualInfo (d, VisualNoMask, NULL, &visualsMatched);
  for (i=0;i<visualsMatched;i++) {
    if (visualList[i].depth > maxDepth) {
      maxDepth = visualList[i].depth;
    }
  }
  XFree(visualList);
  XFlush(d);
  XCloseDisplay(d);
  return maxDepth;
}

PyObject *wrap_getWindowID(PyObject *self, PyObject *args) {
  int result;
  TrapXlibErrors /* macro code to handle xlib exceptions */
  result = getWindowID();
  RestoreOldXlibErrorHandlers /* macro */
  return Py_BuildValue("i",result);
}

void setFocusTo(int win) {
  Window w;
  Display *d;   
  /* Display *XOpenDisplay(char *); */
  w = (Window) win;
  d = XOpenDisplay(NULL);
  if (d == NULL) {
    /* printf("could not open XWindow display\n"); */
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
  TrapXlibErrors /* macro code to handle xlib exceptions */
  setFocusTo(win);
  RestoreOldXlibErrorHandlers /* macro */
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
    /* printf("could not open XWindow display\n"); */
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
  TrapXlibErrors /* macro code to handle xlib exceptions */
  setBackingStore(win);
  RestoreOldXlibErrorHandlers /* macro */
  return Py_None;
}

void getWindowAttributes(int win, XWindowAttributes *winAttr, char **visual) {
  Window w;
  Display *d;
  XVisualInfo visual_info;
  static char *visual_class[] = {
	  "StaticGray",
	  "GrayScale",
	  "StaticColor",
	  "PseudoColor",
	  "TrueColor",
	  "DirectColor"
  };
  int i;
  int screen_num;
  Status XGetWindowAttributes(Display *, Window, XWindowAttributes *);
  i = 5;
  w = (Window) win;
  d = XOpenDisplay(NULL);
  if (d == NULL) {
    /* printf("could not open XWindow display\n"); */
    return;
  }
  XGetWindowAttributes(d, w, winAttr);
  screen_num = DefaultScreen(d);
  while (!XMatchVisualInfo(d, screen_num, DefaultDepth(d, screen_num),
                 i--, &visual_info));
  *visual = visual_class[++i];
  XCloseDisplay(d);
}

PyObject *wrap_getWindowAttributes(PyObject *self, PyObject *args) {
	int win, viewable;
	XWindowAttributes wa;
	char *visual;
	if (!PyArg_ParseTuple(args,"i", &win))
		return NULL;
	TrapXlibErrors /* macro code to handle xlib exceptions */
	getWindowAttributes(win, &wa, &visual);
	if (wa.map_state == IsViewable) {
	  viewable = 1;
	} else {
	  viewable = 0;
	}
	RestoreOldXlibErrorHandlers /* macro */
	return Py_BuildValue("{s:i,s:i,s:i,s:i,s:i,s:i,s:i,s:i,s:s}",
		"x", wa.x,
		"y", wa.y,
		"rootID", (int) wa.root,
		"width", wa.width,
		"height", wa.height,
		"borderWidth", wa.border_width,
						 "viewable", viewable,
		"depth", wa.depth,
		"visualClass", visual);
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
	TrapXlibErrors /* macro code to handle xlib exceptions */
	d = XOpenDisplay(NULL);
	if (d == NULL) {
		printf("could not open XWindow display\n");
		RestoreOldXlibErrorHandlers /* macro */
		return;
	}
	inScreen = XQueryPointer(d, w, &root, &child, &root_x, &root_y,
		&win_x, &win_y, &mask);
	XCloseDisplay(d);
	RestoreOldXlibErrorHandlers /* macro */
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
	if ((w==PointerRoot) | (w==None)) {
	  return Py_BuildValue("i", (int) w);
	}
	TrapXlibErrors /* macro code to handle xlib exceptions */
	d = XOpenDisplay(NULL);
	if (d == NULL) {
		printf("could not open XWindow display\n");
		RestoreOldXlibErrorHandlers /* macro */
		return;
	}
	XQueryTree(d, w, &root, &parent, &children, &nchildren);
	XFree(children);
	XCloseDisplay(d);
	RestoreOldXlibErrorHandlers /* macro */
	if (root == parent) {
	  return Py_None;
	} else {
	  return Py_BuildValue("i", (int) parent);
	}
}

long getColorCell(long red, long green, long blue) {

  /* not much error checking in this to see that read/write colors are
	 supported */
  Display *d;
  int screen_num;
  Colormap cmap;
  XColor singlecolor;
  long colorindex;
  Status status;

  d = XOpenDisplay(NULL);

  if (d == NULL) {
    /* printf("could not open XWindow display\n"); */
    return; 
  }
  screen_num = DefaultScreen(d);
  cmap = DefaultColormap(d, screen_num);
  singlecolor.flags = DoRed | DoGreen | DoBlue;
  singlecolor.pixel = 0;
  singlecolor.red = (unsigned short) red;
  singlecolor.green = (unsigned short) green;
  singlecolor.blue = (unsigned short) blue;
  status = XAllocColor(d, cmap, &singlecolor);
  if (status==0)
	colorindex = -1;
  else
	colorindex = (long) singlecolor.pixel;

  XFlush(d);
  XCloseDisplay(d);
  return colorindex;
}

PyObject *wrap_getColorCell(PyObject *self, PyObject *args) {
  
  long colorindex, red, green, blue;
  if (!PyArg_ParseTuple(args,"lll",&red,&green,&blue))
    return NULL;
  TrapXlibErrors /* macro code to handle xlib exceptions */
  colorindex = getColorCell(red, green, blue);
  RestoreOldXlibErrorHandlers /* macro */
  if (colorindex == -1)
    return Py_BuildValue("");
  else
	return Py_BuildValue("l",(long) colorindex); 
}
void getColor(long colorindex, long *red, long *green, long *blue) {

  /* not much error checking in this to see that read/write colors are
	 supported */
  Display *d;
  int screen_num;
  Colormap cmap;
  XColor color;

  d = XOpenDisplay(NULL);
  if (d == NULL) {
    /* printf("could not open XWindow display\n"); */
    return; 
  }
  screen_num = DefaultScreen(d);
  cmap = DefaultColormap(d, screen_num);
  color.pixel = (unsigned long) colorindex;
  XQueryColor(d, cmap, &color);
  XFlush(d);
  XCloseDisplay(d);
  *red   = color.red;
  *green = color.green;
  *blue  = color.blue;
}

PyObject *wrap_getColor(PyObject *self, PyObject *args) {
  
  long colorindex, red, green, blue;

  if (!PyArg_ParseTuple(args,"l",&colorindex))
    return NULL;
  TrapXlibErrors /* macro code to handle xlib exceptions */
  getColor(colorindex, &red, &green, &blue);
  RestoreOldXlibErrorHandlers /* macro */
  return Py_BuildValue("lll",red, green, blue); 
}


void freeColor(long colorindex) {

  /* not much error checking in this to see that read/write colors are
	 supported */
  Display *d;
  int screen_num;
  unsigned long colorindicies[1];
  Colormap cmap;
  XColor color;

  d = XOpenDisplay(NULL);
  if (d == NULL) {
    /* printf("could not open XWindow display\n"); */
    return; 
  }
  colorindicies[0] = (unsigned long) colorindex;
  screen_num = DefaultScreen(d);
  cmap = DefaultColormap(d, screen_num);
  XFreeColors(d, cmap, colorindicies, 1, 0);
  XFlush(d);
  XCloseDisplay(d);
}

PyObject *wrap_freeColor(PyObject *self, PyObject *args) {
  
  long colorindex;

  if (!PyArg_ParseTuple(args,"l",&colorindex))
    return NULL;
  TrapXlibErrors /* macro code to handle xlib exceptions */
  freeColor(colorindex);
  RestoreOldXlibErrorHandlers /* macro */
  return Py_BuildValue(""); 
}


static PyMethodDef xlibtricksMethods[] = {
  { "moveCursorTo",wrap_moveCursorTo, 1},
  { "getWindowID",wrap_getWindowID, 1},
  { "setFocusTo",wrap_setFocusTo, 1},
  { "setBackingStore",wrap_setBackingStore, 1},
  { "getWindowAttributes",wrap_getWindowAttributes, 1},
  { "getPointerPosition",wrap_getPointerPosition, 1},
  { "getParentID",wrap_getParentID, 1},
  { "getColorCell",wrap_getColorCell, 1},
  { "getColor",wrap_getColor, 1},
  { "freeColor",wrap_freeColor, 1},
  { "getDeepestVisual", wrap_getDeepestVisual, 1},
  {NULL, NULL}
};

void initxlibtricks() {
  PyObject *m;
  m = Py_InitModule("xlibtricks", xlibtricksMethods);
}
