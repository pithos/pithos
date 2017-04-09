# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

from enum import Enum
import logging

from gi.repository import Gtk, GObject

from pithos.gobject_worker import GObjectWorker
from pithos.plugin import PithosPlugin
from pithos.util import open_browser

# getting an API account: http://www.last.fm/api/account
API_KEY = '997f635176130d5d6fe3a7387de601a8'
API_SECRET = '3243b876f6bf880b923a3c9fb955720c'


class LastfmPlugin(PithosPlugin):
    preference = 'enable_lastfm'
    description = _('Scrobble songs to Last.fm')

    is_really_enabled = False
    network = None

    def on_prepare(self):
        try:
            import pylast
        except ImportError:
            logging.warning('pylast not found.')
            return _('pylast not found')

        self.pylast = pylast
        self.worker = GObjectWorker()
        self.preferences_dialog = LastFmAuth(self.pylast, self.settings)
        self.preferences_dialog.connect('lastfm-authorized', self.on_lastfm_authorized)

    def on_enable(self):
        if self.settings['data']:
            self._enable_real()
        else:
            # Show the LastFmAuth dialog on enabling the plugin if we aren't aready authorized.
            dialog = self.preferences_dialog
            dialog.set_transient_for(self.window.prefs_dlg)
            dialog.set_destroy_with_parent(True)
            dialog.set_modal(True)
            dialog.show_all()


    def on_lastfm_authorized(self, prefs_dialog, auth_state):
        if auth_state is prefs_dialog.AuthState.AUTHORIZED:
            self._enable_real()

        elif auth_state is prefs_dialog.AuthState.NOT_AUTHORIZED:
            self.on_disable()

    def _enable_real(self):
        self._connect(self.settings['data'])
        self.is_really_enabled = True
        # Update Last.fm if plugin is enabled in the middle of a song.
        if self.window.current_song:
            self._on_song_changed(self.window, self.window.current_song)
        self._handlers = [
            self.window.connect('song-ended', self._on_song_ended),
            self.window.connect('song-changed', self._on_song_changed),
        ]
        logging.debug('Last.fm plugin fully enabled')
        
    def on_disable(self):
        if self.is_really_enabled:
            for handler in self._handlers:
                self.window.disconnect(handler)
        self.is_really_enabled = False
        self._handlers = []

    def _connect(self, session_key):
        # get_lastfm_network is deprecated. Use LastFMNetwork preferably.
        if hasattr(self.pylast, 'LastFMNetwork'):
            get_network = self.pylast.LastFMNetwork
        else:
            get_network = self.pylast.get_lastfm_network
        self.network = get_network(
            api_key=API_KEY, api_secret=API_SECRET,
            session_key=session_key
        )

    def _on_song_changed(self, window, song):
        def err(e):
            logging.error('Failed to update Last.fm now playing. Error: {}'.format(e))

        def success(*ignore):
            logging.debug('Updated Last.fm now playing. {} by {}'.format(song.title, song.artist))

        self.worker.send(self.network.update_now_playing, (song.artist, song.title, song.album), success, err)

    def _on_song_ended(self, window, song):
        def err(e):
            logging.error('Failed to Scrobble song at Last.fm. Error: {}'.format(e))

        def success(*ignore):
            logging.info('Scrobbled {} by {} to Last.fm'.format(song.title, song.artist))

        duration = song.get_duration_sec()
        position = song.get_position_sec()
        if not song.is_ad and duration > 30 and (position > 240 or position > duration / 2):
            args = (
                song.artist,
                song.title,
                int(song.start_time),
                song.album,
                None,
                None,
                int(duration),
            )

            self.worker.send(self.network.scrobble, args, success, err)


class LastFmAuth(Gtk.Dialog):
    __gtype_name__ = 'LastFmAuth'
    __gsignals__ = {
        'lastfm-authorized': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    class AuthState(Enum):
        NOT_AUTHORIZED = 0
        BEGAN_AUTHORIZATION = 1
        AUTHORIZED = 2

    def __init__(self, pylast, settings):
        super().__init__(use_header_bar=1)
        self.set_title('Last.fm')
        self.set_default_size(300, -1)
        self.set_resizable(False)
        self.connect('delete-event', self.on_close)

        self.worker = GObjectWorker()
        self.settings = settings
        self.pylast = pylast
        self.auth_url = ''

        if self.settings['data']:
            self.auth_state = self.AuthState.AUTHORIZED
        else:
            self.auth_state = self.AuthState.NOT_AUTHORIZED

        self.label = Gtk.Label.new('')
        self.label.set_halign(Gtk.Align.CENTER)
        self.button = Gtk.Button()
        self.button.set_halign(Gtk.Align.CENTER)
        self.set_widget_text()
        self.button.connect('clicked', self.on_clicked)

        content_area = self.get_content_area()
        content_area.add(self.label)
        content_area.add(self.button)
        content_area.show_all()

    def on_close(self, *ignore):
        self.hide()
        # Don't let things be left in a half authorized state if the dialog is closed and not fully authorized.
        # Also disable the plugin if it's not fully authorized so there's no confusion.
        if self.auth_state is not self.AuthState.AUTHORIZED:
            self.auth_state = self.AuthState.NOT_AUTHORIZED
            self.settings.reset('enabled')
            self.button.set_sensitive(True)
            self.set_widget_text()
        return True

    def set_widget_text(self):
        if self.auth_state is self.AuthState.AUTHORIZED:
            self.button.set_label(_('Deauthorize'))
            self.label.set_text(_('Pithos is Authorized with Last.fm'))

        elif self.auth_state is self.AuthState.NOT_AUTHORIZED:
            self.button.set_label(_('Authorize'))
            self.label.set_text(_('Pithos is not Authorized with Last.fm'))

        elif self.auth_state is self.AuthState.BEGAN_AUTHORIZATION:
            self.button.set_label(_('Finish'))
            self.label.set_text(_('Click Finish when Authorized with Last.fm'))
    
    def setkey(self, key):
        if not key:
            self.auth_state = self.AuthState.NOT_AUTHORIZED
            self.settings.reset('data')
            logging.debug('Last.fm Auth Key cleared')

        else:
            self.auth_state = self.AuthState.AUTHORIZED
            self.settings['data'] = key
            logging.debug('Got Last.fm Auth Key: {}'.format(key))

        self.set_widget_text()
        self.button.set_sensitive(True)
        self.emit('lastfm-authorized', self.auth_state)

    def begin_authorization(self):
        def err(e):
            logging.error('Failed to begin Last.fm authorization. Error: {}'.format(e))
            self.setkey('')
            
        def callback(url):
            self.auth_url = url
            logging.debug('Opening Last.fm Auth url: {}'.format(self.auth_url))
            open_browser(self.auth_url)
            self.button.set_sensitive(True)

        self.auth_state = self.AuthState.BEGAN_AUTHORIZATION
        # get_lastfm_network is deprecated. Use LastFMNetwork preferably.
        if hasattr(self.pylast, 'LastFMNetwork'):
            get_network = self.pylast.LastFMNetwork
        else:
            get_network = self.pylast.get_lastfm_network
        self.sg = self.pylast.SessionKeyGenerator(get_network(api_key=API_KEY, api_secret=API_SECRET))

        self.set_widget_text()
        self.button.set_sensitive(False)           
        self.worker.send(self.sg.get_web_auth_url, (), callback, err)

    def finish_authorization(self):
        def err(e):
            logging.error('Failed to finish Last.fm authorization. Error: {}'.format(e))
            self.setkey('')

        self.button.set_sensitive(False)
        self.worker.send(self.sg.get_web_auth_session_key, (self.auth_url,), self.setkey, err)
            
    def on_clicked(self, *ignore):
        if self.auth_state is self.AuthState.NOT_AUTHORIZED:
            self.begin_authorization()

        elif self.auth_state is self.AuthState.BEGAN_AUTHORIZATION:
            self.finish_authorization()

        elif self.auth_state is self.AuthState.AUTHORIZED:
            self.setkey('')
