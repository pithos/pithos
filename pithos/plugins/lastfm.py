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

from enum import Enum
from gi.repository import Gtk, GObject
import logging
from pithos.gi_composites import GtkTemplate
from pithos.gobject_worker import GObjectWorker
from pithos.plugin import PithosPlugin
from pithos.util import open_browser

#getting an API account: http://www.last.fm/api/account
API_KEY = '997f635176130d5d6fe3a7387de601a8'
API_SECRET = '3243b876f6bf880b923a3c9fb955720c'

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
        self.worker = GObjectWorker()
        self.is_really_enabled = False
        self.preferences_dialog = SettingsPreferenceDialog(self.pylast, self.settings, self.worker)
        self.preferences_dialog.connect('lastfm-authorized', self.on_lastfm_authorized)

    def on_enable(self):
        if self.settings['data']:
            self._enable_real()

    def on_lastfm_authorized(self, prefs_dialog, auth_state):
        if auth_state is prefs_dialog.AuthState.AUTHORIZED:
            self._enable_real()

        elif auth_state is prefs_dialog.AuthState.NOT_AUTHORIZED:
            self.on_disable()

    def _enable_real(self):
        self.connect(self.settings['data'])
        self.song_ended_handle = self.window.connect('song-ended', self.song_ended)
        self.song_changed_handle = self.window.connect('song-changed', self.song_changed)
        self.is_really_enabled = True
        # Update lastfm if plugin is enabled in the middle of a song
        self.song_changed(self.window, self.window.current_song)
        
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
        if song is not None:
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
        if not song.is_ad and duration > 30 and (position > 240 or position > duration / 2):
            logging.info("Scrobbling song")
            self.worker.send(self.network.scrobble, (song.artist, song.title, int(song.start_time), song.album,
                                                     None, None, int(duration)))

@GtkTemplate(ui='/io/github/Pithos/ui/SingleButtonSettingsBox.ui')
class SingleButtonSettingsBox(Gtk.Box):
    __gtype_name__ = 'SingleButtonSettingsBox'

    label = GtkTemplate.Child()
    btn = GtkTemplate.Child()

    def __init__(self):
        super().__init__()
        self.init_template()

@GtkTemplate(ui='/io/github/Pithos/ui/SettingsPreferenceDialog.ui')
class SettingsPreferenceDialog(Gtk.Dialog):
    __gtype_name__ = 'SettingsPreferenceDialog'

    __gsignals__ = {
        'lastfm-authorized': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    header_bar = GtkTemplate.Child()
    close_btn = GtkTemplate.Child()
    reset_btn = GtkTemplate.Child()
    v_box = GtkTemplate.Child()

    class AuthState(Enum):
        NOT_AUTHORIZED = 0
        BEGAN_AUTHORIZATION = 1
        AUTHORIZED = 2

    def __init__(self, pylast, settings, worker):
        super().__init__()
        self.init_template()

        self.pylast = pylast
        self.settings = settings
        self.worker = worker
        self.auth_url = ''

        if self.settings['data']:
            self.auth_state = self.AuthState.AUTHORIZED
        else:
            self.auth_state = self.AuthState.NOT_AUTHORIZED

        self.header_bar.set_title('Lastfm')
        self.header_bar.set_subtitle('Preferences')

        self.settings_box = SingleButtonSettingsBox()
        self.settings_box.btn.connect('clicked', self.on_settings_box_btn_clicked)
        self.set_widget_text()
        self.v_box.pack_start(self.settings_box, True, True, 0)

    @GtkTemplate.Callback
    def on_close_btn_clicked(self, *ignore):
        self.hide()
        # Don't let things be left in a half authorized state if the ui is closed and not fully authorized.
        if self.auth_state is self.AuthState.BEGAN_AUTHORIZATION:
            self.auth_state = self.AuthState.NOT_AUTHORIZED
            self.settings_box.btn.set_sensitive(True)
            self.set_widget_text()

    @GtkTemplate.Callback
    def on_reset_btn_clicked(self, *ignore):
       self.setkey('')

    def set_widget_text(self):
        if self.auth_state is self.AuthState.AUTHORIZED:
            self.settings_box.btn.set_label('Deauthorize')
            self.settings_box.label.set_markup('<b>Authorized</b>\n<small>Pithos is Authorized with Last.fm</small>')

        elif self.auth_state is self.AuthState.NOT_AUTHORIZED:
            self.settings_box.btn.set_label('Authorize')
            self.settings_box.label.set_markup('<b>Not Authorized</b>\n<small>Pithos is not Authorized with Last.fm</small>')

        elif self.auth_state is self.AuthState.BEGAN_AUTHORIZATION:
            self.settings_box.btn.set_label('Finish')
            self.settings_box.label.set_markup('<b>Finish Authorization</b>\n<small>Click Finish when Authorized with Last.fm</small>')
    
    def setkey(self, key):
        if not key:
            self.auth_state = self.AuthState.NOT_AUTHORIZED
            self.settings.reset('data')

        else:
            self.auth_state = self.AuthState.AUTHORIZED
            self.settings['data'] = key

        self.set_widget_text()
        self.settings_box.btn.set_sensitive(True)
        self.emit('lastfm-authorized', self.auth_state)

    def begin_authorization(self):
        def err(e):
            logging.error(e)
            self.setkey('')
            
        def callback(url):
            self.auth_url = url
            open_browser(self.auth_url)
            self.settings_box.btn.set_sensitive(True)

        self.auth_state = self.AuthState.BEGAN_AUTHORIZATION
        self.network = self.pylast.get_lastfm_network(api_key=API_KEY, api_secret=API_SECRET)
        self.sg = self.pylast.SessionKeyGenerator(self.network)

        self.set_widget_text()
        self.settings_box.btn.set_sensitive(False)           
        self.worker.send(self.sg.get_web_auth_url, (), callback, err)

    def finish_authorization(self):
        def err(e):
            logging.error(e)
            self.setkey('')

        self.settings_box.btn.set_sensitive(False)
        self.worker.send(self.sg.get_web_auth_session_key, (self.auth_url,), self.setkey, err)
            
    def on_settings_box_btn_clicked(self, *ignore):
        if self.auth_state is self.AuthState.NOT_AUTHORIZED:
            self.begin_authorization()

        elif self.auth_state is self.AuthState.BEGAN_AUTHORIZATION:
            self.finish_authorization()

        elif self.auth_state is self.AuthState.AUTHORIZED:
            self.setkey('')

