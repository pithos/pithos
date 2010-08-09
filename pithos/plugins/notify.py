#!/usr/bin/python
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

import pynotify, gtk
from pithos.plugin import PithosPlugin
from pithos.pithosconfig import get_data_file

class NotifyPlugin(PithosPlugin):
    def on_prepare(self):
        pynotify.init('pithos')
        self.notification = pynotify.Notification("Pithos","Pithos")
        
    def on_enable(self):
        self.song_callback_handle = self.window.connect("song-changed", self.song_changed)
        self.state_changed_handle = self.window.connect("user-changed-play-state", self.playstate_changed)
        
    def set_for_song(self, song):
        self.notification.clear_hints()
        msg = "by %s from %s"%(song.artist, song.album)
        self.notification.update(song.title, msg, 'audio-x-generic')
        
    def song_changed(self, window,  song):
        if not self.window.is_active():
            self.set_for_song(song)
            if song.art_pixbuf:
                #logging.debug("has albumart", song.art_pixbuf, song.art_pixbuf.get_width())
                self.notification.set_icon_from_pixbuf(song.art_pixbuf)
            else:
                self.notification.props.icon_name = get_data_file('media/pithos-mono.png')
            self.notification.show()
            
    def playstate_changed(self, window, state):
        if not self.window.is_active():
            self.set_for_song(window.current_song)
            if state:
                self.notification.props.icon_name = 'gtk-media-play-ltr'
            else:
                self.notification.props.icon_name = 'gtk-media-pause'
            
            self.notification.show()
            
        
    def on_disable(self):
        self.window.disconnect(self.song_callback_handle)
        self.window.disconnect(self.state_changed_handle)
