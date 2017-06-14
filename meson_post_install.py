#!/usr/bin/env python3

from compileall import compile_dir
from os import environ, path
from subprocess import call

prefix = environ.get('MESON_INSTALL_PREFIX', '/usr/local')
datadir = path.join(prefix, 'share')
destdir = environ.get('DESTDIR', '')

# Package managers set this so we don't need to run
if not destdir:
    print('Updating icon cache...')
    for theme in ('hicolor', 'ubuntu-mono-dark', 'ubuntu-mono-light'):
        call(['gtk-update-icon-cache', '-qtf', path.join(datadir, 'icons', theme)])

    print('Compiling GSettings schemas...')
    call(['glib-compile-schemas', path.join(datadir, 'glib-2.0', 'schemas')])

print('Compiling python bytecode...')
compile_dir(destdir + path.join(datadir, 'pithos', 'pithos'), optimize=2)
