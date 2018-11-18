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
import logging

from gi.repository import Gio

from pithos.plugin import PithosPlugin


class NotifyPlugin(PithosPlugin):
    preference = 'notify'
    description = 'Shows notifications on song change'

    _app = None
    _last_id = ''

    def on_prepare(self):
        # We prefer the behavior of the fdo backend to the gtk backend
        # as it doesn't force persistance which doesn't make sense for
        # this application.
        if not os.path.exists('/.flatpak-info'):
            os.environ['GNOTIFICATION_BACKEND'] = 'freedesktop'

        self._app = Gio.Application.get_default()
        self.prepare_complete()

    def on_enable(self):
        self.song_change_handler = self.window.connect('song-changed', self.send_notification)
        self.state_change_handler = self.window.connect('user-changed-play-state', self.send_notification)

    def send_notification(self, window, *ignore):
        if window.is_active():
            return

        song = window.current_song
        # This matches GNOME-Shell's format
        notification = Gio.Notification.new(song.artist)
        notification.set_body(song.title)
        if song.artUrl:
            notification.set_icon(Gio.FileIcon.new(Gio.File.new_for_uri(song.artUrl)))

        if window.playing:
            notification.add_button(_('Pause'), 'app.pause')
        else:
            notification.add_button(_('Play'), 'app.play')
        notification.add_button(_('Skip'), 'app.next-song')

        if self._last_id != song.trackToken:
            self._app.withdraw_notification(self._last_id)

        self._last_id = song.trackToken
        self._app.send_notification(song.trackToken, notification)

    def on_disable(self):
        if self._last_id:
            self._app.withdraw_notification(self._last_id)
            self._last_id = ''

        self.window.disconnect(self.song_change_handler)
        self.window.disconnect(self.state_change_handler)

