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
from sys import platform
from pithos.plugin import PithosPlugin

import gi
gi.require_version('Notify', '0.7')
from gi.repository import (GLib, Gtk)

class NotifyPlugin(PithosPlugin):
    preference = 'notify'
    description = 'Shows notifications on song change'

    has_notifications = False
    supports_actions = False
    escape_markup = False

    def on_prepare(self):
        if platform == 'darwin':
            return self.prepare_osx()
        else:
            return self.prepare_notify()

    def prepare_osx(self):
        try:
            from pync import Notifier
            self.has_notifications = True
        except ImportError:
            logging.warning("pync not found.")
            return "pync not found"

        self.notifier = Notifier

    def prepare_notify(self):
        try:
            from gi.repository import Notify
            self.has_notifications = True
        except ImportError:
            logging.warning ("libnotify not found.")
            return "libnotify not found"

        # Work-around Ubuntu's incompatible workaround for Gnome's API breaking mistake.
        # https://bugzilla.gnome.org/show_bug.cgi?id=702390
        old_add_action = Notify.Notification.add_action
        def new_add_action(*args):
            try:
                old_add_action(*args)
            except TypeError:
                old_add_action(*(args + (None,)))
        Notify.Notification.add_action = new_add_action

        Notify.init('pithos')
        self.notification = Notify.Notification()
        self.notification.set_category('x-gnome.music')
        self.notification.set_hint('desktop-entry', GLib.Variant.new_string('pithos'))

        caps = Notify.get_server_caps()
        if 'actions' in caps:
            logging.info('Notify supports actions')
            self.supports_actions = True

        if 'body-markup' in caps:
            self.escape_markup = True

        if 'action-icons' in caps:
            self.notification.set_hint('action-icons', GLib.Variant.new_boolean(True))

        # TODO: On gnome this can replace the tray icon, just need to add love/hate buttons
        #if 'persistence' in caps:
        #    self.notification.set_hint('resident', GLib.Variant.new_boolean(True))

    def on_enable(self):
        if self.has_notifications:
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
                                         self.notification_playpause_cb, None)
        else:
            self.notification.add_action(play_action, 'Play',
                                         self.notification_playpause_cb, None)

        self.notification.add_action(skip_action, 'Skip',
                                     self.notification_skip_cb, None)

    def set_notification_notify(self, song, playing):
        if self.supports_actions:
            self.set_actions(playing)

        if song.art_pixbuf:
            self.notification.set_image_from_pixbuf(song.art_pixbuf)
        else:
            self.notification.set_hint('image-data', None)

        msg = 'by {} from {}'.format(song.artist, song.album)
        if self.escape_markup:
            msg = html.escape(msg, quote=False)
        self.notification.update(song.title, msg, 'audio-x-generic' if not song.art_pixbuf else None)
        self.notification.show()

    def set_notification_osx(self, song, playing):
        # TODO: Icons (buttons not possible?)
        if playing:
            self.notifier.notify('by {} from {}'.format(song.artist, song.album),
                                title=song.title)

    def set_notification(self, song, playing=True):
        if platform == 'darwin':
            self.set_notification_osx(song, playing)
        else:
            self.set_notification_notify(song, playing)

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
        if self.has_notifications:
            self.window.disconnect(self.song_callback_handle)
            self.window.disconnect(self.state_changed_handle)
