# The following will need generalization to work on other platforms

all: xutilmodule.so toglcolorsmodule.so sscanfmodule.so

xutilmodule.so: xutil.c
	cc -c -I/usr/local/Python1.5.2/include/python1.5 -I/opt/X11R5/include \
		 xutil.c
	ld -G xutil.o -o xutilmodule.so

sscanfmodule.so: sscanfmodule.c
	cc -c -I/usr/local/Python1.5.2/include/python1.5 sscanfmodule.c
	ld -G sscanfmodule.o -o sscanfmodule.so

toglcolorsmodule.so: toglcolors.c
	cc -c -I/usr/local/Python1.5.2/include/python1.5 -I/opt/X11R5/include \
		toglcolors.c
	ld -G toglcolors.o -o toglcolorsmodule.so -L /opt/X11R5/lib \
		/opt/X11R5/lib/Togl/togl.so
