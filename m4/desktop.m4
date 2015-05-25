# desktop.m4
#
# serial 4

dnl DESKTOP_VALIDATE
dnl Validates and installs desktop files.
dnl
dnl To use:
dnl 1. Call DESKTOP_FILE in configure.ac to check for the desktop-file-utils tools.
dnl 2. Add @DESKTOP_FILE_RULES@ to a Makefile.am to substitute the make rules.
dnl 3. Add .desktop files to desktop_FILES in Makefile.am and they will be validated
dnl    at make check time and installed on make install.
dnl 4. Add --enable-desktop-validate to DISTCHECK_CONFIGURE_FLAGS
dnl    in Makefile.am to require valid desktop file when doing a distcheck.
dnl
dnl On installation desktop-file-install will be used when available which also
dnl rebuilds the mime info cache. After install update-desktop-database is called.
dnl 
dnl Author: TingPing <tingping@tingping.se>
dnl Based upon appdata-xml.m4

AC_DEFUN([DESKTOP_FILE],
[
  m4_pattern_allow([AM_V_GEN])
  AC_ARG_ENABLE([desktop-validate],
                [AS_HELP_STRING([--disable-desktop-validate],
                                [Disable validating desktop files during check phase])])

  AS_IF([test "x$enable_desktop_validate" != "xno"],
        [AC_PATH_PROG([DESKTOP_FILE_VALIDATE], [desktop-file-validate])
         AS_IF([test "x$DESKTOP_FILE_VALIDATE" = "x"],
               [have_desktop_validate=no],
               [have_desktop_validate=yes
                AC_SUBST([DESKTOP_FILE_VALIDATE])])],
        [have_desktop_validate=no])

  AC_PATH_PROG([UPDATE_DESKTOP_DATABASE], [update-desktop-database])
  AS_IF([test "x$UPDATE_DESKTOP_DATABASE" != "x"], [AC_SUBST([UPDATE_DESKTOP_DATABASE])])

  AC_PATH_PROG([DESKTOP_FILE_INSTALL], [desktop-file-install])
  AS_IF([test "x$DESKTOP_FILE_INSTALL" != "x"], [AC_SUBST([DESKTOP_FILE_INSTALL])])

  AS_IF([test "x$have_desktop_validate" != "xno"],
        [desktop_validate=yes],
        [desktop_validate=no
         AS_IF([test "x$enable_desktop_validate" = "xyes"],
               [AC_MSG_ERROR([Desktop validation was requested but desktop-file-validate was not found])])])

  AC_SUBST([desktopfiledir], [${datadir}/applications])

  DESKTOP_FILE_RULES='
.PHONY : uninstall-desktop-file install-desktop-file clean-desktop-file

mostlyclean-am: clean-desktop-file

%.desktop.valid: %.desktop
	$(AM_V_GEN) if test -f "$<"; then d=; else d="$(srcdir)/"; fi; \
		if test -n "$(DESKTOP_FILE_VALIDATE)"; \
			then $(DESKTOP_FILE_VALIDATE) $${d}$<; fi \
		&& touch [$]@

check-am: $(desktop_FILES:.desktop=.desktop.valid)
uninstall-am: uninstall-desktop-file
install-data-am: install-desktop-file

.SECONDARY: $(desktop_FILES)

install-desktop-file: $(desktop_FILES)
	@$(NORMAL_INSTALL)
	if test -n "$^"; then \
		test -z "$(desktopfiledir)" || $(MKDIR_P) "$(DESTDIR)$(desktopfiledir)"; \
		if test -n "$(DESKTOP_FILE_INSTALL)"; then \
			$(DESKTOP_FILE_INSTALL) --dir="$(DESTDIR)$(desktopfiledir)" --mode=644 $^; \
		else \
			$(INSTALL_DATA) $^ "$(DESTDIR)$(desktopfiledir)"; \
		fi; \
		#test -z "$(UPDATE_DESKTOP_DATABASE)" || $(UPDATE_DESKTOP_DATABASE) -q "$(DESTDIR)$(desktopfiledir)"; \
	fi

uninstall-desktop-file:
	@$(NORMAL_UNINSTALL)
	@list='\''$(desktop_FILES)'\''; test -n "$(desktopfiledir)" || list=; \
	files=`for p in $$list; do echo $$p; done | sed -e '\''s|^.*/||'\''`; \
	test -n "$$files" || exit 0; \
	echo " ( cd '\''$(DESTDIR)$(desktopfiledir)'\'' && rm -f" $$files ")"; \
	cd "$(DESTDIR)$(desktopfiledir)" && rm -f $$files; \
	#test -z "$(UPDATE_DESKTOP_DATABASE)" || $(UPDATE_DESKTOP_DATABASE) -q "$(DESTDIR)$(desktopfiledir)"

clean-desktop-file:
	rm -f $(desktop_FILES:.desktop=.desktop.valid)
'
  _DESKTOP_FILE_SUBST(DESKTOP_FILE_RULES)
])

dnl _DESKTOP_FILE_SUBST(VARIABLE)
dnl Abstract macro to do either _AM_SUBST_NOTMAKE or AC_SUBST
AC_DEFUN([_DESKTOP_FILE_SUBST],
[
AC_SUBST([$1])
m4_ifdef([_AM_SUBST_NOTMAKE], [_AM_SUBST_NOTMAKE([$1])])
]
)
