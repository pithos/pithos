# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2015 Patrick Griffis <tingping@tingping.se>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.


import os
import logging
from gi.repository import GLib, Gio
from .Secrets import SecretService


def _get_plugin_settings(name):
    return Gio.Settings.new_with_path('io.github.Pithos.plugin', '/io/github/Pithos/{}/'.format(name))


def maybe_migrate_settings():
    config_file = os.path.join(GLib.get_user_config_dir(), 'pithos.ini')
    prefs = {}
    try:
        with open(config_file) as f:
            for line in f:
                sep = line.find('=')
                key = line[:sep]
                val = line[sep + 1:].strip()
                if val == 'None':
                    val = None
                elif val == 'False':
                    val = False
                elif val == 'True':
                    val = True
                prefs[key] = val
    except IOError:
        logging.debug('Not migrating old config')
        return

    migration_map = {
        'username': 'email',
    }

    plugin_migration = {
        'notify': 'notify',
        'enable_screesaverpause': 'screensaver_pause',
        'show_icon': 'notification_icon',
    }

    ignore_migration = (
        'unsafe_permissions',
        'x_pos',
        'y_pos',
        'audio_format' # Pre 0.3.18
    )

    settings = Gio.Settings.new('io.github.Pithos')
    for key, val in prefs.items():
        logging.debug('migrating {}: {}'.format(key, val))
        if not val:
            continue
        if key in ignore_migration:
            continue

        if key == 'lastfm_key' and val:
            s = _get_plugin_settings('lastfm')
            s.set_string('data', val)
        elif key in migration_map:
            settings.set_string(migration_map[key], val)
        elif key in plugin_migration:
            s = _get_plugin_settings(plugin_migration[key])
            s.set_boolean('enabled', val)
        elif key.startswith('enable_'):
            s = _get_plugin_settings(key[7:])
            s.set_boolean('enabled', val)
        elif key == 'password':
            if 'username' in prefs:
                SecretService.set_account_password(None, prefs['username'], val, None)
        elif key == 'volume':
            settings.set_double(key, float(val))
        else:
            key = key.replace('_', '-')
            if isinstance(val, bool):
                settings.set_boolean(key, val)
            else:
                settings.set_string(key, val)

    os.remove(config_file)
    logging.debug('Migrated old config')
