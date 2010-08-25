# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010 Kevin Mehall <km@kevinmehall.net>
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


class MediaKeyPlugin(PithosPlugin):
    preference = 'enable_mediakeys'
    
    def bind_dbus(self):
        try:
            bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
            mk = bus.get_object("org.gnome.SettingsDaemon","/org/gnome/SettingsDaemon/MediaKeys")
            mk.connect_to_signal("MediaPlayerKeyPressed", self.mediakey_pressed)
            logging.info("Bound media keys with DBUS")
            self.method = 'dbus'
            return True
        except dbus.DBusException:
            return False
            
    def mediakey_pressed(self, *args):
        for i in args:
            if i == 'Play':
                self.window.playpause()
            elif i == 'Next':
                self.window.next_song()
            elif i == 'Stop':
                self.window.user_pause()
            elif i == 'Previous':
                self.window.bring_to_top()
            
    def bind_keybinder(self):
        try:
            import keybinder
        except:
            return False
        
        keybinder.bind('XF86AudioPlay', self.window.playpause, None)
        keybinder.bind('XF86AudioStop', self.window.user_pause, None)
        keybinder.bind('XF86AudioNext', self.window.next_song, None)
        keybinder.bind('XF86AudioPrev', self.window.bring_to_top, None)
        
        logging.info("Bound media keys with keybinder")
        self.method = 'keybinder'
        return True
        
    def on_enable(self):
        self.bind_dbus() or self.bind_keybinder() or logging.error("Could not bind media keys")     
        
    def on_disable(self):
        logging.error("Not implemented: Can't disable media keys")
