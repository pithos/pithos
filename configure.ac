AC_PREREQ(2.68)
AC_INIT([pithos], [1.1.1], [https://github.com/pithos/pithos/issues],
                           [pithos], [https://pithos.github.io])
AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([pithos/__main__.py])

AM_INIT_AUTOMAKE([1.11 dist-xz no-dist-gzip foreign subdir-objects -Wall -Wno-portability])
AM_SILENT_RULES([yes])
AM_PATH_PYTHON([3.3])

GETTEXT_PACKAGE=pithos
AC_SUBST(GETTEXT_PACKAGE)

IT_PROG_INTLTOOL([0.50.0])
DESKTOP_FILE
APPSTREAM_XML

AC_PATH_PROG(GLIB_COMPILE_RESOURCES, glib-compile-resources)

AC_CONFIG_FILES([
    Makefile
    po/Makefile.in
])
AC_OUTPUT

echo "
    $PACKAGE $VERSION

    prefix: ${prefix}
"
