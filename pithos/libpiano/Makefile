SOURCE = piano.c crypt.c http.c xml.c ezxml.c waitress.c

_piano.so: $(SOURCE) piano_wrap.c
	gcc -Wall -I . -I /usr/include/python2.6/ $(SOURCE) piano_wrap.c -shared -o _piano.so

piano_wrap.c: piano.i
	swig -python piano.i
