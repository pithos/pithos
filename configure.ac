AC_PREREQ(2.68)
AC_INIT([pithos], [1.1.1], [https://github.com/pithos/pithos/issues],
                           [pithos], [https://pithos.github.io])
AC_CONFIG_MACRO_DIR([m4])
AC_CONFIG_SRCDIR([pithos/__main__.py])

AM_INIT_AUTOMAKE([1.11 dist-xz no-dist-gzip foreign subdir-objects -Wall -Wno-portability])
AM_SILENT_RULES([yes])
AM_PATH_PYTHON([3.3])

DESKTOP_FILE
APPSTREAM_XML

AC_CONFIG_FILES([
    Makefile
])
AC_OUTPUT

echo "
    $PACKAGE $VERSION

    prefix: ${prefix}
"
