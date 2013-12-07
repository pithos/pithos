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

import logging
import html
from pithos.plugin import PithosPlugin
from pithos.pithosconfig import get_data_file
from gi.repository import (GLib, Gtk, Notify)

class NotifyPlugin(PithosPlugin):
    preference = 'notify'

    supports_actions = False
    
    def on_prepare(self):
        Notify.init('Pithos')
        self.notification = Notify.Notification()
        self.notification.set_category('x-gnome.music')
        self.notification.set_hint_string('desktop-icon', 'pithos')

        caps = Notify.get_server_caps()
        if 'actions' in caps:
            logging.info('Notify supports actions')
            self.supports_actions = True

        if 'action-icons' in caps:
            self.notification.set_hint('action-icons', GLib.Variant.new_boolean(True))

        # TODO: On gnome this can replace the tray icon, just need to add love/hate buttons
        #if 'persistence' in caps:
        #    self.notification.set_hint('resident', GLib.Variant.new_boolean(True))

    def on_enable(self):
        self.song_callback_handle = self.window.connect("song-changed", self.song_changed)
        self.state_changed_handle = self.window.connect("user-changed-play-state", self.playstate_changed)

    def set_actions(self, playing=True):
        self.notification.clear_actions()

        pause_action = 'media-playback-pause'
        play_action = 'media-playback-start'
        skip_action = 'media-skip-forward'

        if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
            play_action += '-rtl'
            skip_action += '-rtl'

        if playing:
            self.notification.add_action(pause_action, 'Pause',
                                         self.notification_playpause_cb, None, None)
        else:
            self.notification.add_action(play_action, 'Play',
                                         self.notification_playpause_cb, None, None)

        self.notification.add_action(skip_action, 'Skip',
                                     self.notification_skip_cb, None, None)

    def set_notification(self, song, playing=True):
        if self.supports_actions:
            self.set_actions(playing)

        if song.art_pixbuf:
            self.notification.set_image_from_pixbuf(song.art_pixbuf)
        else:
            self.notification.set_hint('image-data', None)

        msg = html.escape('by {} from {}'.format(song.artist, song.album))
        self.notification.update(song.title, msg, 'audio-x-generic')
        self.notification.show()

    def notification_playpause_cb(self, notification, action, data, ignore=None):
        self.window.playpause_notify()

    def notification_skip_cb(self, notification, action, data, ignore=None):
        self.window.next_song()
        
    def song_changed(self, window,  song):
        if not self.window.is_active():
            GLib.idle_add(self.set_notification, window.current_song)
            
    def playstate_changed(self, window, state):
        if not self.window.is_active():
            GLib.idle_add(self.set_notification, window.current_song, state)
        
    def on_disable(self):
        self.window.disconnect(self.song_callback_handle)
        self.window.disconnect(self.state_changed_handle)
