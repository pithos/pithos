ACLOCAL_AMFLAGS = -I m4

# ----------- pithos --------------

pithosdir = $(pythondir)/pithos/
pithos_PYTHON = $(wildcard pithos/*.py)

pandoradir = $(pithosdir)/pandora
pandora_PYTHON = $(wildcard pithos/pandora/*.py)

pluginsdir = $(pithosdir)/plugins
plugins_PYTHON = $(wildcard pithos/plugins/*.py)

pithosmediadir = $(pithosdir)/data/media
pithosmedia_DATA = \
	$(wildcard pithos/data/media/*.svg) \
	$(wildcard pithos/data/media/*.png)

pithosuidir = $(pithosdir)/data/ui
pithosui_DATA = \
	$(wildcard pithos/data/ui/*.xml) \
	$(wildcard pithos/data/ui/*.ui)

bin_SCRIPTS = bin/pithos
bin/pithos: bin/pithos.in
	@$(MKDIR_P) bin
	$(AM_V_GEN)sed                          \
		-e s!\@prefix\@!$(prefix)!          \
		-e s!\@datadir\@!$(datadir)!        \
		-e s!\@pkgdatadir\@!$(pkgdatadir)!  \
		-e s!\@pkglibdir\@!$(pkglibdir)!    \
		-e s!\@localedir\@!$(localedir)!    \
		-e s!\@pythondir\@!$(pythondir)!    \
		-e s!\@pyexecdir\@!$(pyexecdir)!    \
		< $< > $@
	@chmod a+x $@

# ------------ data ----------------

desktop_in_files = data/pithos.desktop.in
desktop_FILES = $(desktop_in_files:.desktop.in=.desktop)
@INTLTOOL_DESKTOP_RULE@
@DESKTOP_FILE_RULES@

appstream_in_files = data/pithos.appdata.xml.in
appstream_XML = $(appstream_in_files:.xml.in=.xml)
@INTLTOOL_XML_RULE@
@APPSTREAM_XML_RULES@

hicolor_scalabledir = $(datadir)/icons/hicolor/scalable/apps
hicolor_scalable_DATA = $(wildcard data/icons/hicolor/pithos*.svg)

hicolor_48dir = $(datadir)/icons/hicolor/48x48/apps
hicolor_48_DATA = $(wildcard data/icons/hicolor/pithos*.png)

ubuntu_lightdir = $(datadir)/icons/ubuntu-mono-light/apps/16
ubuntu_light_DATA = $(wildcard data/icons/ubuntu-mono-light/pithos*.svg)

ubuntu_darkdir = $(datadir)/icons/ubuntu-mono-dark/apps/16
ubuntu_dark_DATA = $(wildcard data/icons/ubuntu-mono-dark/pithos*.svg)

UPDATE_ICON_CACHE = gtk-update-icon-cache -f -t $(datadir)/icons/hicolor || :

install-data-hook:
	$(UPDATE_ICON_CACHE);

uninstall-hook:
	$(UPDATE_ICON_CACHE);

SUBDIRS = po
CLEANFILES = $(bin_SCRIPTS) $(desktop_FILES) $(appstream_XML)
EXTRA_DIST = license README.md autogen.sh requirements-osx.txt bin/pithos.in \
	$(pithosui_DATA) $(pithosmedia_DATA) $(appstream_in_files) $(desktop_in_files) \
	$(hicolor_scalable_DATA) $(hicolor_48_DATA) $(ubuntu_light_DATA) $(ubuntu_dark_DATA)
