# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
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

from gi.repository import Gio, Gtk

from pithos.plugin import PithosPlugin
from pithos.util import is_flatpak


class NotifyPlugin(PithosPlugin):
    preference = 'notify'
    description = 'Shows notifications on song change'

    _app = None
    _app_id = None
    _fallback_icon = None

    def on_prepare(self):
        # We prefer the behavior of the fdo backend to the gtk backend
        # as it doesn't force persistence which doesn't make sense for
        # this application.
        if not is_flatpak():
            os.environ['GNOTIFICATION_BACKEND'] = 'freedesktop'

        self._app = Gio.Application.get_default()
        self._app_id = self._app.get_application_id()
        self._fallback_icon = Gio.ThemedIcon.new('audio-x-generic')
        self.preferences_dialog = NotifyPluginPrefsWindow(self.window, self.settings)
        self.prepare_complete()

    def on_enable(self):
        self._song_change_handler = self.window.connect('song-changed', self.send_notification)
        self._shutdown_handler = self._app.connect('shutdown', lambda app: app.withdraw_notification(self._app_id))

    def send_notification(self, window, *ignore):
        if window.is_active():
            # GNOME-Shell will auto dismiss notifications
            # when the window becomes "active" but other DE's may not (KDE for example).
            # If we're not going to replace a previous notification
            # we should withdraw said stale previous notification.
            self._app.withdraw_notification(self._app_id)
        else:
            song = window.current_song
            album = '\n' + song.album if song.album and self.preferences_dialog.show_album else ''
            # This matches GNOME-Shell's format
            notification = Gio.Notification.new(song.artist)
            # GNOME focuses the application by default, we want to match that behavior elsewhere such as on KDE.
            notification.set_default_action('app.activate')
            notification.set_body(song.title + album)

            if song.artUrl:
                icon = Gio.FileIcon.new(Gio.File.new_for_uri(song.artUrl))
            else:
                icon = self._fallback_icon
            notification.set_icon(icon)

            notification.add_button(_('Skip'), 'app.next-song')

            self._app.send_notification(self._app_id, notification)

    def on_disable(self):
        self._app.withdraw_notification(self._app_id)
        if self._song_change_handler:
            self.window.disconnect(self._song_change_handler)
            self._song_change_handler = 0
        if self._shutdown_handler:
            self._app.disconnect(self._shutdown_handler)
            self._shutdown_handler = 0


class NotifyPluginPrefsWindow(Gtk.Window):
    __gtype_name__ = 'NotifyPluginPrefsWindow'

    def __init__(self, window, settings):
        super().__init__(title='Notification Preferences', resizable=False,
                         default_height=-1, default_width=300)
        self.connect('delete-event', self.on_close)

        self.pithos = window
        self.settings = settings
        self.show_album = self.settings['data'] == 'True' if self.settings['data'] else False

        box = Gtk.Box(spacing=6)
        label = Gtk.Label()
        label.set_markup('\n<b>{}</b>\n'.format(_('Show Album Info')))
        label.set_halign(Gtk.Align.START)
        label.set_valign(Gtk.Align.CENTER)
        box.pack_start(label, True, True, 4)

        self.switch = Gtk.Switch()
        self.switch.connect('notify::active', self.toggle_album_info)
        self.switch.set_active(self.show_album)
        self.settings.connect('changed::enabled', self._on_album_info_plugin_enabled)
        self.switch.set_halign(Gtk.Align.END)
        self.switch.set_valign(Gtk.Align.CENTER)
        box.pack_end(self.switch, False, False, 2)

        self.add(box)

    def on_close(self, window, event):
        window.hide()
        return True

    def toggle_album_info(self, *ignore):
        self.show_album = bool(self.switch.get_active())
        self.settings['data'] = str(self.show_album)

    def _on_album_info_plugin_enabled(self, *ignore):
        self.switch.set_active(self.show_album)
