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
import dbus
import logging


class ScreenSaverPausePlugin(PithosPlugin):
    preference = 'enable_screensaverpause'
    
    def bind_session_bus(self):
        try:
            self.session_bus = dbus.SessionBus()
            return True
        except dbus.DBusException:
            return False
        
    def on_enable(self):
        self.bind_session_bus() or logging.error("Could not bind session bus")
        self.connect_events() or logging.error("Could not connect events")

    def on_disable(self):
        self.disconnect_events()
        self.session_bus = None

    def connect_events(self):
        try:
            self.session_bus.add_signal_receiver(self.playPause, 'ActiveChanged', 'org.gnome.ScreenSaver')
            self.session_bus.add_signal_receiver(self.playPause, 'ActiveChanged', 'org.cinnamon.ScreenSaver')
            self.session_bus.add_signal_receiver(self.playPause, 'ActiveChanged', 'org.freedesktop.ScreenSaver')
            return True
        except dbus.DBusException:
            logging.info("Enable failed")
            return False

    def disconnect_events(self):
        try:
            self.session_bus.remove_signal_receiver(self.playPause, 'ActiveChanged', 'org.gnome.ScreenSaver')
            self.session_bus.remove_signal_receiver(self.playPause, 'ActiveChanged', 'org.cinnamon.ScreenSaver')
            self.session_bus.remove_signal_receiver(self.playPause, 'ActiveChanged', 'org.freedesktop.ScreenSaver')
            return True
        except dbus.DBusException:
            return False
            
    
    def playPause(self,state):
        if not state:
            if self.wasplaying:
                self.window.user_play()
        else:
            self.wasplaying = self.window.playing
            self.window.pause()
