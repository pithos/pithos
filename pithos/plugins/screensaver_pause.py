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

import logging
from gi.repository import (GLib, Gio)
from pithos.plugin import PithosPlugin

SCREENSAVERS = (
    # interface, path
    ('org.gnome.ScreenSaver', '/org/gnome/ScreenSaver'),
    ('org.cinnamon.ScreenSaver', '/org/cinnamon/ScreenSaver'),
    ('org.freedesktop.ScreenSaver', '/org/freedesktop/ScreenSaver'),
)

class ScreenSaverPausePlugin(PithosPlugin):
    preference = 'enable_screensaverpause'
    description = 'Pause playback when screensaver starts'

    bus = None
    cancel = None
    locked = 0
    wasplaying = False
    subs = []

    def on_enable(self):
        def on_got_bus(obj, result, userdata=None):
            self.cancel = None
            try:
                self.bus = Gio.bus_get_finish(result)
                logging.info('Got session bus')
            except Glib.Error as e:
                logging.warning(e)
                return

            self._connect_events()

        self.cancel = Gio.Cancellable()
        Gio.bus_get(Gio.BusType.SESSION, self.cancel, on_got_bus)

        # Since this async always succeed.
        return True

    def on_disable(self):
        if self.cancel:
            self.cancel.cancel()

        for sub in self.subs:
            self.bus.signal_unsubscribe(sub)

        self.subs = []
        self.bus = None
        self.cancel = None

    def _connect_events(self):
        def on_screensaver_active_changed(conn, sender, path,
                                   interface, sig, param, userdata=None):
            self._pause() if param[0] else self._play()

        def on_unity_session_changed(conn, sender, path,
                                   interface, sig, param, userdata=None):
            self._pause() if sig == 'Locked' else self._play()

        for ss in SCREENSAVERS:
            self.subs.append(self.bus.signal_subscribe (None, ss[0], 'ActiveChanged', ss[1],
                                       None, Gio.DBusSignalFlags.NONE,
                                       on_screensaver_active_changed, None))

        for sig in ('Locked', 'Unlocked'):
            self.subs.append(self.bus.signal_subscribe (None, 'com.canonical.Unity.Session',
                                        sig, '/com/canonical/Unity/Session',
                                        None, Gio.DBusSignalFlags.NONE,
                                        on_unity_session_changed, None))

    def _play(self):
        self.locked -= 1
        if self.locked < 0:
            self.locked = 0
        if not self.locked and self.wasplaying:
            self.window.user_play()

    def _pause(self):
        if not self.locked:
            self.wasplaying = self.window.playing
            self.window.pause()
        self.locked += 1

