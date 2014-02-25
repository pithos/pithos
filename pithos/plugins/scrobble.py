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

import pylast
import logging
from pithos.gobject_worker import GObjectWorker
from pithos.plugin import PithosPlugin
from pithos.util import open_browser

#getting an API account: http://www.last.fm/api/account
API_KEY = '997f635176130d5d6fe3a7387de601a8'
API_SECRET = '3243b876f6bf880b923a3c9fb955720c'

#client id, client version info: http://www.last.fm/api/submissions#1.1
CLIENT_ID = 'pth'
CLIENT_VERSION = '1.0'

_worker = None
def get_worker():
    # so it can be shared between the plugin and the authorizer
    global _worker
    if not _worker:
        _worker = GObjectWorker()
    return _worker

class LastfmPlugin(PithosPlugin):
    preference='lastfm_key'
    
    def on_prepare(self):
        self.worker = get_worker()

    def on_enable(self):
        self.connect(self.window.preferences['lastfm_key'])
        self.song_ended_handle = self.window.connect('song-ended', self.song_ended)
        self.song_changed_handle = self.window.connect('song-changed', self.song_changed)
        
    def on_disable(self):
        self.window.disconnect(self.song_ended_handle)
        self.window.disconnect(self.song_rating_changed_handle)
        self.window.disconnect(self.song_changed_handle)
        
    def song_ended(self, window, song):
        self.scrobble(song)
        
    def connect(self, session_key):
        self.network = pylast.get_lastfm_network(
            api_key=API_KEY, api_secret=API_SECRET,
            session_key = session_key
        )
        self.scrobbler = self.network.get_scrobbler(CLIENT_ID, CLIENT_VERSION)
     
    def song_changed(self, window, song):
        self.worker.send(self.scrobbler.report_now_playing, (song.artist, song.title, song.album))
        
    def send_rating(self, song, rating):
        if song.rating:
            track = self.network.get_track(song.artist, song.title)
            if rating == 'love':
                self.worker.send(track.love)
            elif rating == 'ban':
                self.worker.send(track.ban)
            logging.info("Sending song rating to last.fm")

    def scrobble(self, song):
        if song.duration > 30 and (song.position > 240 or song.position > song.duration/2):
            logging.info("Scrobbling song")
            mode = pylast.SCROBBLE_MODE_PLAYED
            source = pylast.SCROBBLE_SOURCE_PERSONALIZED_BROADCAST
            self.worker.send(self.scrobbler.scrobble, (song.artist, song.title, int(song.start_time), source, mode, song.duration, song.album))            


class LastFmAuth:
    def __init__(self, d,  prefname, button):
        self.button = button
        self.dict = d
        self.prefname = prefname
        
        self.auth_url= False
        self.set_button_text()
        self.button.connect('clicked', self.clicked)
    
    @property
    def enabled(self):
        return self.dict[self.prefname]
    
    def setkey(self, key):
        self.dict[self.prefname] = key
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
            self.setkey(False)
        else:
            self.network = pylast.get_lastfm_network(api_key=API_KEY, api_secret=API_SECRET)
            self.sg = pylast.SessionKeyGenerator(self.network)
            
            def callback(url):
                self.auth_url = url
                self.set_button_text()
                open_browser(self.auth_url)
            
            get_worker().send(self.sg.get_web_auth_url, (), callback)
            self.button.set_label("Connecting...")
            self.button.set_sensitive(False)
            
            
            
        
