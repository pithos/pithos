AC_PREREQ(2.68)
AC_INIT([pithos], [1.2.0], [https://github.com/pithos/pithos/issues],
                           [pithos], [https://pithos.github.io])
AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_AUX_DIR([build-aux])
AC_CONFIG_SRCDIR([pithos/__main__.py])

AM_INIT_AUTOMAKE([1.11 dist-xz no-dist-gzip foreign subdir-objects -Wall -Wno-portability])
AM_SILENT_RULES([yes])
AM_PATH_PYTHON([3.4])

GETTEXT_PACKAGE=pithos
AC_SUBST(GETTEXT_PACKAGE)

m4_ifndef([GLIB_GSETTINGS], [AC_MSG_ERROR([gsettings.m4 not found])])
m4_ifndef([APPSTREAM_XML], [AC_MSG_ERROR([appstream-xml.m4 not found])])

IT_PROG_INTLTOOL([0.50.0])
DESKTOP_FILE
APPSTREAM_XML
GLIB_GSETTINGS

AC_PATH_PROG(GLIB_COMPILE_RESOURCES, glib-compile-resources)

AC_ARG_WITH(docs, AS_HELP_STRING([--with-docs], [Build documentation with Sphinx]))
AS_IF([test "$with_docs" = "yes"], [
    AC_PATH_PROG(SPHINX_BUILD, sphinx-build, [no])
	AS_IF([test "$SPHINX_BUILD" = "no"], [
		with_docs=no
	])
])
AM_CONDITIONAL([WITH_DOCS], [test "$with_docs" = "yes"])

AC_CONFIG_FILES([
    Makefile
    po/Makefile.in
])
AC_OUTPUT

echo "
    $PACKAGE $VERSION

    prefix:         ${prefix}
    documentation:  ${with_docs}
"
