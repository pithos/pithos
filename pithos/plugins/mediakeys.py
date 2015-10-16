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
import sys
import logging

APP_ID = 'Pithos'

class MediaKeyPlugin(PithosPlugin):
    preference = 'enable_mediakeys'
    description = 'Control playback with media keys'

    def bind_dbus(self):
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            DBusGMainLoop(set_as_default=True)
        except ImportError:
            return False

        try:
            bus = dbus.Bus(dbus.Bus.TYPE_SESSION)
        except dbus.DBusException:
            return False

        bound = False
        for de in ('gnome', 'mate'):
            try:
                mk = bus.get_object("org.%s.SettingsDaemon" %de, "/org/%s/SettingsDaemon/MediaKeys" %de)
                mk.GrabMediaPlayerKeys(APP_ID, 0, dbus_interface='org.%s.SettingsDaemon.MediaKeys' %de)
                mk.connect_to_signal("MediaPlayerKeyPressed", self.mediakey_pressed)
                bound = True
                logging.info("Bound media keys with DBUS (%s)" %de)
                break
            except dbus.DBusException as e:
                logging.debug(e)

        if bound:
            self.method = 'dbus'
            return True
            
    def mediakey_pressed(self, app, action):
       if app == APP_ID:
            if action == 'Play':
                self.window.playpause_notify()
            elif action == 'Next':
                self.window.next_song()
            elif action == 'Stop':
                self.window.user_pause()
            elif action == 'Previous':
                self.window.bring_to_top()
            
    def bind_keybinder(self):
        try:
            import gi
            gi.require_version('Keybinder', '3.0')
            # Gdk needed for Keybinder
            from gi.repository import Keybinder
            Keybinder.init()
        except:
            return False
        
        Keybinder.bind('XF86AudioPlay', self.window.playpause, None)
        Keybinder.bind('XF86AudioStop', self.window.user_pause, None)
        Keybinder.bind('XF86AudioNext', self.window.next_song, None)
        Keybinder.bind('XF86AudioPrev', self.window.bring_to_top, None)
        
        logging.info("Bound media keys with keybinder")
        self.method = 'keybinder'
        return True

    def kbevent(self, event):
        if event.KeyID == 179 or event.Key == 'Media_Play_Pause':
            self.window.playpause_notify()
        if event.KeyID == 176 or event.Key == 'Media_Next_Track':
            self.window.next_song()
        return True

    def bind_win32(self):
        try:
            import pyHook
        except ImportError:
            logging.warning('Please install PyHook: http://www.lfd.uci.edu/~gohlke/pythonlibs/#pyhook')
            return False
        self.hookman = pyHook.HookManager()
        self.hookman.KeyDown = self.kbevent
        self.hookman.HookKeyboard()
        return True

    def osx_playpause_handler(self):
        self.window.playpause_notify()
        return False # Don't let others get event

    def osx_skip_handler(self):
        self.window.next_song()
        return False

    def bind_osx(self):
        try:
            import osxmmkeys
        except ImportError:
            logging.warning('Please install osxmmkeys: https://github.com/pushrax/osxmmkeys')
            return False
        except RuntimeError as e:
            logging.warning('osxmmkeys failed to import: {}'.format(e))
            return False

        tap = osxmmkeys.Tap()
        tap.on('play_pause', self.osx_playpause_handler)
        tap.on('next_track', self.osx_skip_handler)
        tap.start()

        return True
        
    def on_enable(self):
        if sys.platform == 'win32':
            loaded = self.bind_win32()
        elif sys.platform == 'darwin':
            loaded = self.bind_osx()
        else:
            loaded = self.bind_dbus() or self.bind_keybinder()

        if not loaded:
            logging.error("Could not bind media keys")
        
    def on_disable(self):
        logging.error("Not implemented: Can't disable media keys")
