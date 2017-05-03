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

import logging

from gi.repository import GLib, Gdk, Gio

from pithos.plugin import PithosPlugin

APP_ID = 'io.github.Pithos'


class MediaKeyPlugin(PithosPlugin):
    preference = 'enable_mediakeys'
    description = 'Control playback with media keys'

    method = None

    def grab_media_keys(self):
        try:
            self.mediakeys.call_sync(
                'GrabMediaPlayerKeys',
                GLib.Variant('(su)', (APP_ID, 0)),
                Gio.DBusCallFlags.NONE, -1, None,
            )

            return True
        except GLib.Error as e:
            logging.debug(e)
            return False

    def release_media_keys(self):
        try:
            self.mediakeys.call_sync(
                'ReleaseMediaPlayerKeys',
                GLib.Variant('(s)', (APP_ID,)),
                Gio.DBusCallFlags.NONE, -1, None,
            )

        except GLib.Error as e:
            logging.debug(e)

    def update_focus_time(self, widget, event, userdata=None):
        if event.changed_mask & Gdk.WindowState.FOCUSED and \
           event.new_window_state & Gdk.WindowState.FOCUSED:
            self.grab_media_keys()

    def mediakey_signal(self, proxy, sender, signal, param, userdata=None):
        if signal != 'MediaPlayerKeyPressed':
            return

        app, action = param.unpack()
        if app == APP_ID:
            if action == 'Play':
                self.window.playpause_notify()
            elif action == 'Next':
                self.window.next_song()
            elif action == 'Stop':
                self.window.user_pause()
            elif action == 'Previous':
                self.window.bring_to_top()

    def on_prepare(self):
        if self.bus:
            de_busnames = {
                'gnome': ('org.gnome.SettingDaemon.MediaKeys', 'org.gnome.SettingsDaemon'),
                'mate': ('org.mate.SettingsDaemon', )
            }

            for de, bus_names in de_busnames.items():
                if not self.method:
                    for bus_name in bus_names:
                        try:
                            self.mediakeys = Gio.DBusProxy.new_sync(
                                self.bus,
                                Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                                None,
                                bus_name,
                                '/org/{}/SettingsDaemon/MediaKeys'.format(de),
                                'org.{}.SettingsDaemon.MediaKeys'.format(de),
                                None,
                            )

                            if self.grab_media_keys():
                                self.method = 'dbus'
                                break
                        except GLib.Error as e:
                            logging.warning(e)

        if self.method is None:
            display = self.window.props.screen.get_display()
            if not type(display).__name__.endswith('X11Display'):
                return 'DBus binding failed and Keybinder requires X11.'
            try:
                import gi
                gi.require_version('Keybinder', '3.0')
                from gi.repository import Keybinder
                self.keybinder = Keybinder
                self.keybinder.init()
                self.method = 'keybinder'
            except (ValueError, ImportError):
                return 'DBus binding failed and Keybinder not found.'

    def on_enable(self):
        if self.method == 'dbus':
            self.focus_hook = self.window.connect('window-state-event', self.update_focus_time)
            self.mediakey_hook = self.mediakeys.connect('g-signal', self.mediakey_signal)
            logging.info('Bound media keys with DBUS {}'.format(self.mediakeys.props.g_interface_name))
        elif self.method == 'keybinder':
            ret = self.keybinder.bind('XF86AudioPlay', self.window.playpause, None)
            if not ret:  # Presumably all bindings will fail
                logging.error('Failed to bind media keys with Keybinder')
                return
            self.keybinder.bind('XF86AudioStop', self.window.user_pause, None)
            self.keybinder.bind('XF86AudioNext', self.window.next_song, None)
            self.keybinder.bind('XF86AudioPrev', self.window.bring_to_top, None)
            logging.info('Bound media keys with Keybinder')

    def on_disable(self):
        if self.method == 'dbus':
            self.window.disconnect(self.focus_hook)
            self.mediakeys.disconnect(self.mediakey_hook)
            self.release_media_keys()
            logging.info('Disabled dbus mediakey bindings')
        elif self.method == 'keybinder':
            self.keybinder.unbind('XF86AudioPlay')
            self.keybinder.unbind('XF86AudioStop')
            self.keybinder.unbind('XF86AudioNext')
            self.keybinder.unbind('XF86AudioPrev')
            logging.info('Disabled keybinder mediakey bindings')
