#
# Copyright (C) 2017 Jason Gray <jasonlevigray3@gmail.com>
#
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
# END LICENSE

from gi.repository import (
    Gtk,
    Gio
)

from pithos.plugin import PithosPlugin


class InhibitScreensaverPlugin(PithosPlugin):
    preference = 'enable_inhibitscreensaver'
    description = 'Prevent Session from going idle'
    _cookie = 0
    _status_handler_id = None
    _playing = None
    _pithos_app = None

    def on_prepare(self):
        self._pithos_app = Gio.Application.get_default()
        self.prepare_complete()

    def on_enable(self):
        self._on_status_changed()

        if self._status_handler_id is None:
            self._status_handler_id = self.window.connect(
                'play-state-changed',
                self._on_status_changed,
            )

    def on_disable(self):
        if self._status_handler_id is not None:
            self.window.disconnect(self._status_handler_id)
            self._status_handler_id = None

        self._uninhibit()

    def _on_status_changed(self, *ignore):
        playing = self.window.playing

        if self._playing != playing:
            self._playing = playing

            if self._playing:
                self._inhibit()
            else:
                self._uninhibit()

    def _inhibit(self):
        suspend = Gtk.ApplicationInhibitFlags.SUSPEND
        idle = Gtk.ApplicationInhibitFlags.IDLE

        self._cookie = self._pithos_app.inhibit(
            self.window,
            suspend | idle,
            'Inhibit Screensaver plugin enabled',
        )

    def _uninhibit(self):
        if self._cookie != 0:
            self._pithos_app.uninhibit(self._cookie)

        self._cookie = 0
        self._playing = None
