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

import pynotify
from pithos.plugin import PithosPlugin

class NotifyPlugin(PithosPlugin):
	def on_prepare(self):
		pynotify.init('pithos')
		self.notification = pynotify.Notification("Pithos","Pithos")
		
	def on_enable(self):
		self.song_callback_handle = self.window.connect("song-changed", self.song_changed)
		
	def song_changed(self, window,  song):
		if not self.window.is_active():
			msg = "by %s from %s"%(song.artist, song.album)
			self.notification.update(song.title, msg, "audio-x-generic")
			if song.art_pixbuf:
			    #logging.debug("has albumart", song.art_pixbuf, song.art_pixbuf.get_width())
			    self.notification.set_icon_from_pixbuf(song.art_pixbuf)
			self.notification.show()
		
	def on_disable(self):
		self.window.disconnect(self.song_callback_handle)
