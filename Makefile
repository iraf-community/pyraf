# The following will need generalization to work on other platforms

xlibtricksmodule.so: xlibtricks.c
	cc -c -I/usr/local/Python1.5.2/include/python1.5 -I/opt/X11R5/include \
		 xlibtricks.c
	ld -G xlibtricks.o -o xlibtricksmodule.so
