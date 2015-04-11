# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
#This program is free software: you can redistribute it and/or modify it
#under the terms of the GNU General Public License version 3, as published
#by the Free Software Foundation.
#
#This program is distributed in the hope that it will be useful, but
#WITHOUT ANY WARRANTY; without even the implied warranties of
#MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
#PURPOSE.  See the GNU General Public License for more details.
#
#You should have received a copy of the GNU General Public License along
#with this program.  If not, see <http://www.gnu.org/licenses/>.
### END LICENSE

from pithos.plugin import PithosPlugin
import logging

dbus = None
class ScreenSaverPausePlugin(PithosPlugin):
    preference = 'enable_screensaverpause'
    description = 'Pause playback when screensaver starts'

    session_bus = None

    def bind_session_bus(self):
        global dbus
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            DBusGMainLoop(set_as_default=True)
        except ImportError:
            return False

        try:
            self.session_bus = dbus.SessionBus()
            return True
        except dbus.DBusException:
            return False

    def on_enable(self):
        if not self.bind_session_bus():
            logging.error("Could not bind session bus")
            return
        self.connect_events() or logging.error("Could not connect events")

        self.locked = 0
        self.wasplaying = False

    def on_disable(self):
        if self.session_bus:
            self.disconnect_events()

        self.session_bus = None

    def connect_events(self):
        try:
            self.receivers = [
                self.session_bus.add_signal_receiver(*args)
                for args in ((self.playPause, 'ActiveChanged', 'org.gnome.ScreenSaver'),
                             (self.playPause, 'ActiveChanged', 'org.cinnamon.ScreenSaver'),
                             (self.playPause, 'ActiveChanged', 'org.freedesktop.ScreenSaver'),
                             (self.pause, 'Locked', 'com.canonical.Unity.Session'),
                             (self.play, 'Unlocked', 'com.canonical.Unity.Session'),
                            )
                ]

            return True
        except dbus.DBusException:
            logging.info("Enable failed")
            return False

    def disconnect_events(self):
        try:
            for r in self.receivers:
                r.remove()
            return True
        except dbus.DBusException:
            return False

    def play(self):
        self.locked -= 1
        if self.locked < 0:
            self.locked = 0
        if not self.locked and self.wasplaying:
            self.window.user_play()

    def pause(self):
        if not self.locked:
            self.wasplaying = self.window.playing
            self.window.pause()
        self.locked += 1

    def playPause(self, screensaver_on):
        if screensaver_on:
            self.pause()
        else:
            self.play()
