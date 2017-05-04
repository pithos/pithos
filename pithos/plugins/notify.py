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

import html
import logging

from gi.repository import (GLib, Gtk)

from pithos.plugin import PithosPlugin

from .dbus_util.GioNotify import GioNotify


class NotifyPlugin(PithosPlugin):
    preference = 'notify'
    description = 'Shows notifications on song change'

    notification = None
    supports_actions = False
    escape_markup = False

    def on_prepare(self):
        def on_notify_init_finish(notification, server_info, caps, error=None):
            if error:
                logging.warning('Notification server not found: {}'.format(error))
                self.prepare_complete(error='Notification server not found')
            else:
                self.notification = notification
                self.supports_actions = 'actions' in caps
                self.escape_markup = 'body-markup' in caps

                self.notification.set_hint('desktop-entry', GLib.Variant('s', 'io.github.Pithos'))
                self.notification.set_hint('category', GLib.Variant('s', 'x-gnome.music'))
                if 'action-icons' in caps:
                    self.notification.set_hint('action-icons', GLib.Variant('b', True))

                # GNOME Shell 3.20 or higher has bultin MPRIS functionality that makes
                # persistent song notifications redundant.
                has_built_in_mpris = False
                version = server_info['version'].split('.')
                if server_info['name'] == 'gnome-shell' and len(version) >= 2:
                    major_version, minor_version = (int(x) if x.isdigit() else 0 for x in version[0:2])
                    if major_version == 3 and minor_version >= 20:
                        has_built_in_mpris = True

                if 'persistence' in caps and has_built_in_mpris:
                    self.notification.set_hint('transient', GLib.Variant('b', True))

                server_info = '\n'.join(('{}: {}'.format(k, v) for k, v in server_info.items()))
                logging.debug('\nNotification Server Information:\n{}'.format(server_info))

                caps = '\n'.join((cap for cap in caps))
                logging.debug('\nNotification Server Capabilities:\n{}'.format(caps))
                self.prepare_complete()

        GioNotify.async_init('Pithos', on_notify_init_finish)

    def on_enable(self):
        self.song_change_handler = self.window.connect('song-changed', self.send_notification)
        self.state_change_handler = self.window.connect('user-changed-play-state', self.send_notification)
        self.closed_handler = self.notification.connect('closed', self.on_notification_closed)
        self.action_invoked_handler = self.notification.connect('action-invoked', self.on_notification_action_invoked)

    def on_notification_closed(self, notification, closed_reason):
        logging.debug(closed_reason.explanation)

    def on_notification_action_invoked(self, notification, action_id):
        logging.debug('Notification action invoked: {}'.format(action_id))

    def set_actions(self, playing):
        pause_action = 'media-playback-pause'
        play_action = 'media-playback-start'
        skip_action = 'media-skip-forward'
        if Gtk.Widget.get_default_direction() == Gtk.TextDirection.RTL:
            play_action += '-rtl'
            skip_action += '-rtl'
        if playing:
            self.notification.add_action(pause_action, 'Pause',
                                         self.window.playpause_notify)
        else:
            self.notification.add_action(play_action, 'Play',
                                         self.window.playpause_notify)

        self.notification.add_action(skip_action, 'Skip',
                                     self.window.next_song)

    def send_notification(self, window, *ignore):
        if window.is_active():
            return
        if self.supports_actions:
            self.notification.clear_actions()
            self.set_actions(window.playing is not False)
        song = window.current_song
        summary = song.title
        body = 'by {} from {}'.format(song.artist, song.album)
        if self.escape_markup:
            body = html.escape(body, quote=False)
        icon = song.artUrl or 'audio-x-generic'
        self.notification.show_new(summary, body, icon)

    def on_disable(self):
        if self.notification is None:
            return
        self.window.disconnect(self.song_change_handler)
        self.window.disconnect(self.state_change_handler)
        self.notification.disconnect(self.closed_handler)
        self.notification.disconnect(self.action_invoked_handler)
