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

from gi.repository import Gtk
import logging
from pithos.gobject_worker import GObjectWorker
from pithos.plugin import PithosPlugin
from pithos.util import open_browser

#getting an API account: http://www.last.fm/api/account
API_KEY = '997f635176130d5d6fe3a7387de601a8'
API_SECRET = '3243b876f6bf880b923a3c9fb955720c'

_worker = None
def get_worker():
    # so it can be shared between the plugin and the authorizer
    global _worker
    if not _worker:
        _worker = GObjectWorker()
    return _worker

class LastfmPlugin(PithosPlugin):
    preference = 'enable_lastfm'
    description = 'Scrobble tracks listened to on Last.fm'
    
    def on_prepare(self):
        try:
            import pylast
        except ImportError:
            logging.warning("pylast not found.")
            return "pylast not found"

        self.pylast = pylast
        self.worker = get_worker()
        self.is_really_enabled = False
        self.preferences_dialog = LastFmAuth(self.pylast, self.settings, 'data', self.window)
        self.preferences_dialog.connect('delete-event', self.auth_closed)

    def on_enable(self):
        if self.settings.get_string('data'):
            self._enable_real()

    def auth_closed(self, widget, event):
        if self.settings.get_string('data'):
            self._enable_real()
        else:
            self.settings.set_boolean('enabled', False)
        widget.hide()
        return True # Don't delete window

    def _enable_real(self):
        self.connect(self.settings.get_string('data'))
        self.song_ended_handle = self.window.connect('song-ended', self.song_ended)
        self.song_changed_handle = self.window.connect('song-changed', self.song_changed)
        self.is_really_enabled = True
        
    def on_disable(self):
        if self.is_really_enabled:
            self.window.disconnect(self.song_ended_handle)
            self.window.disconnect(self.song_changed_handle)
            self.is_really_enabled = False
        
    def song_ended(self, window, song):
        self.scrobble(song)
        
    def connect(self, session_key):
        self.network = self.pylast.get_lastfm_network(
            api_key=API_KEY, api_secret=API_SECRET,
            session_key = session_key
        )

    def song_changed(self, window, song):
        self.worker.send(self.network.update_now_playing, (song.artist, song.title, song.album))
        
    def send_rating(self, song, rating):
        if song.rating:
            track = self.network.get_track(song.artist, song.title)
            if rating == 'love':
                self.worker.send(track.love)
            elif rating == 'ban':
                self.worker.send(track.ban)
            logging.info("Sending song rating to last.fm")

    def scrobble(self, song):
        duration = song.get_duration_sec()
        position = song.get_position_sec()
        if not song.is_ad and duration > 30 and (position > 240 or position > duration/2):
            logging.info("Scrobbling song")
            self.worker.send(self.network.scrobble, (song.artist, song.title, int(song.start_time), song.album, \
                                                     None, None, int(duration)))


class LastFmAuth(Gtk.Dialog):
    def __init__(self, pylast, settings, key, parent):
        Gtk.Dialog.__init__(self)
        self.set_default_size(200, -1)

        self.settings = settings
        self.prefname = key
        self.pylast = pylast
        self.auth_url= False

        label = Gtk.Label.new('In order to use LastFM you must authorize this with your account')
        label.set_line_wrap(True)

        self.button = Gtk.Button()
        self.button.set_halign(Gtk.Align.CENTER)
        self.set_button_text()
        self.button.connect('clicked', self.clicked)

        self.get_content_area().add(label)
        self.get_content_area().show_all()
        self.get_action_area().add(self.button)
        self.get_action_area().set_layout(Gtk.ButtonBoxStyle.EXPAND)
    
    @property
    def enabled(self):
        return self.settings.get_string(self.prefname)
    
    def setkey(self, key):
        if not key:
            self.settings.reset(self.prefname)
        else:
            self.settings.set_string(self.prefname, key)
        self.set_button_text()
        
    def set_button_text(self):
        self.button.set_sensitive(True)
        if self.auth_url:
            self.button.set_label("Click once authorized on web site")
        elif self.enabled:
            self.button.set_label("Disable")
        else:
            self.button.set_label("Authorize")
            
    def clicked(self, *ignore):
        if self.auth_url:
            def err(e):
                logging.error(e)
                self.set_button_text()

            get_worker().send(self.sg.get_web_auth_session_key, (self.auth_url,), self.setkey, err) 
            self.button.set_label("Checking...")
            self.button.set_sensitive(False)
            self.auth_url = False
                
        elif self.enabled:
            self.setkey('')
        else:
            self.network = self.pylast.get_lastfm_network(api_key=API_KEY, api_secret=API_SECRET)
            self.sg = self.pylast.SessionKeyGenerator(self.network)
            
            def callback(url):
                self.auth_url = url
                self.set_button_text()
                open_browser(self.auth_url)
            
            get_worker().send(self.sg.get_web_auth_url, (), callback)
            self.button.set_label("Connecting...")
            self.button.set_sensitive(False)

