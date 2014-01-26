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

APP_ID = 'Pithos'

class MediaKeyPlugin(PithosPlugin):
    preference = 'enable_mediakeys'
    
    def bind_dbus(self):
        try:
            bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
            mk = bus.get_object("org.gnome.SettingsDaemon","/org/gnome/SettingsDaemon/MediaKeys")
            mk.GrabMediaPlayerKeys(APP_ID, 0, dbus_interface='org.gnome.SettingsDaemon.MediaKeys')
            mk.connect_to_signal("MediaPlayerKeyPressed", self.mediakey_pressed)
            logging.info("Bound media keys with DBUS")
            self.method = 'dbus'
            return True
        except dbus.DBusException:
            return False
            
    def mediakey_pressed(self, app, action):
       if app == APP_ID:
            if action == 'Play':
                self.window.playpause_notify()
            elif action == 'Next':
                self.window.next_song()
            elif action == 'Stop':
                self.window.user_pause()
            elif action == 'Previous':
                self.window.prev_song()
            
    def bind_keybinder(self):
        try:
            import gi
            gi.require_version('Keybinder', '3.0')
            # Gdk needed for Keybinder
            from gi.repository import Keybinder, Gdk
            Keybinder.init()
        except:
            return False
        
        Keybinder.bind('XF86AudioPlay', self.window.playpause, None)
        Keybinder.bind('XF86AudioStop', self.window.user_pause, None)
        Keybinder.bind('XF86AudioNext', self.window.next_song, None)
        Keybinder.bind('XF86AudioPrev', self.window.prev_song, None)
        
        logging.info("Bound media keys with keybinder")
        self.method = 'keybinder'
        return True
        
    def on_enable(self):
        self.bind_dbus() or self.bind_keybinder() or logging.error("Could not bind media keys")     
        
    def on_disable(self):
        logging.error("Not implemented: Can't disable media keys")
