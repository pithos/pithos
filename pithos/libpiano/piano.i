 %module piano
 %{
 /* Includes the header in the wrapper code */
 
 #include "piano.h"
 typedef char bool;
 #define true 1
 #define false 0
 %}
 
%include "typemaps.i"


%typemap (in,numinputs=0) PianoStation_t** (PianoStation_t *temp)
{
	temp = 0;
    $1 = &temp;
}

%typemap (argout) PianoStation_t**
{
    PyObject *obj = SWIG_NewPointerObj(*$1, SWIGTYPE_p_PianoStation, 0);
    $result = PyTuple_Pack(2, $result, obj);
}

%typemap (in,numinputs=0) PianoSong_t** (PianoSong_t *temp)
{
	temp = 0;
    $1 = &temp;
}

%typemap (argout) PianoSong_t**
{
    PyObject *obj = SWIG_NewPointerObj(*$1, SWIGTYPE_p_PianoSong, 0);
    $result = PyTuple_Pack(2, $result, obj);
}

%include "piano.h"

%inline %{		
void PianoSetProxy(PianoHandle_t *ph, const char *proxystr){
	char tmpPath[2];
	WaitressSplitUrl (proxystr, ph->waith.proxyHost,
			sizeof (ph->waith.proxyHost), ph->waith.proxyPort,
			sizeof (ph->waith.proxyPort), tmpPath, sizeof (tmpPath));
}
%}
