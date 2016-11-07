#
# Copyright (C) 2016 Jason Gray <jasonlevigray3@gmail.com>
#
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
from gettext import gettext as _
from pithos.plugin import PithosPlugin
import gi
from gi.repository import GLib, Gio, Gtk

class NotifyPlugin(PithosPlugin):
    preference = 'notify'
    description = 'Shows notifications on song change'

    def on_prepare(self):
        pass

    def on_enable(self):
        def on_DBusConnection_finish(cancelable, result):
            DBusConnection = Gio.bus_get_finish(result)
            Gio.DBusProxy.new(DBusConnection,
                              Gio.DBusCallFlags.NONE,
                              None,
                              'org.freedesktop.Notifications',
                              '/org/freedesktop/Notifications',
                              'org.freedesktop.Notifications',
                              None,
                              on_DBusProxy_finish,
            )

        def on_DBusProxy_finish(DBusProxy, result):
            self.NotificationsDBusProxy = DBusProxy.new_finish(result)
            self.NotificationsDBusProxy.call('GetCapabilities', None, Gio.DBusCallFlags.NONE, -1, None, on_GetCapabilities_finish)

        def on_GetCapabilities_finish(NotificationsDBusProxy, result):
            Capabilities = NotificationsDBusProxy.call_finish(result).unpack()[0]
            self.supports_actions = False
            self.escape_markup = False
            self.NotificationId = 0
            self.play_pause_identifier = ''
            self.skip_identifier = ''
            self.g_signal_handler = None
            self.actions = []
            self.hints = {'category': GLib.Variant.new_string('x-gnome.music'),
                          'desktop-entry': GLib.Variant.new_string('io.github.Pithos'),
            }

            if 'persistence' in Capabilities:
                logging.debug('Notification server supports persistence')

            if 'actions' in Capabilities:
                self.supports_actions = True
                self.g_signal_handler = self.NotificationsDBusProxy.connect('g-signal', self.on_g_signal)
                logging.debug('Notification server supports actions')

            if 'action-icons' in Capabilities:
                self.hints['action-icons'] = GLib.Variant.new_boolean(True)
                logging.debug('Notification server supports action icons')

            if 'body-markup' in Capabilities:
                self.escape_markup = True
                logging.debug('Notification server supports body markup')             

            self.song_change_handler = self.window.connect('song-changed', self.on_song_changed)
            self.state_change_handler = self.window.connect('user-changed-play-state', self.on_playstate_changed)

        Gio.bus_get(Gio.BusType.SESSION, None, on_DBusConnection_finish)

    def on_g_signal(self, proxy, sender_name, signal_name, parameters):
        id, action_key = parameters
        if id != self.NotificationId:
            return
        if signal_name == 'ActionInvoked':
            if action_key == self.play_pause_identifier:
                self.window.playpause_notify()
            elif action_key == self.skip_identifier:
                self.window.next_song()
            logging.debug('Notification Action Invoked: %s', action_key)

    def on_playstate_changed(self, window, playing):
        if self.window.is_active():
            return
        self.send_notification(window.current_song, playing)

    def on_song_changed(self, window, song):
        if self.window.is_active():
            return
        self.send_notification(song)

    def send_notification(self, song, playing=True):
        def on_NotificationsDBusProxy_call_finish(NotificationsDBusProxy, result):
            self.NotificationId = NotificationsDBusProxy.call_finish(result).unpack()[0]

        if self.supports_actions:
            self.set_actions(playing)

        summary = song.title
        body = '{} {} {} {}'.format(_('by'), song.artist, _('from'), song.album)
        if self.escape_markup:
            body = html.escape(body, quote=False)
        if song.artUrl:
            icon = song.artUrl
        else:
            icon = 'audio-x-generic'

        args = GLib.Variant('(susssasa{sv}i)', ('Pithos', self.NotificationId, icon, summary, body,
                                                self.actions, self.hints, -1))

        self.NotificationsDBusProxy.call('Notify', args, Gio.DBusCallFlags.NONE, -1, None, on_NotificationsDBusProxy_call_finish)

    def set_actions(self, playing):
        pause_identifier = 'media-playback-pause'
        play_identifier = 'media-playback-start'
        self.skip_identifier = 'media-skip-forward'

        if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
            play_identifier += '-rtl'
            self.skip_identifier += '-rtl'

        if playing:
            self.play_pause_identifier = pause_identifier
            play_pause_display_str = 'Pause'
        else:
            self.play_pause_identifier = play_identifier
            play_pause_display_str = 'Play'

        self.actions = [self.play_pause_identifier,
                        _(play_pause_display_str),
                        self.skip_identifier,
                        _('Skip'),
        ]

    def on_disable(self):
        self.window.disconnect(self.song_change_handler)
        self.window.disconnect(self.state_change_handler)
        if self.g_signal_handler is not None:
            self.NotificationsDBusProxy.disconnect(self.g_signal_handler)
