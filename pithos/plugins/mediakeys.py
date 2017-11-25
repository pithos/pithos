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

    mediakeys = None
    keybinder = None
    de_busnames = [
        ('gnome', 'org.gnome.SettingsDaemon.MediaKeys'),
        ('gnome', 'org.gnome.SettingsDaemon'),
        ('mate', 'org.mate.SettingsDaemon'),
    ]

    def grab_media_keys(self):
        self.mediakeys.call(
            'GrabMediaPlayerKeys',
            GLib.Variant('(su)', (APP_ID, 0)),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
            None,
        )

    def release_media_keys(self):
        self.mediakeys.call(
            'ReleaseMediaPlayerKeys',
            GLib.Variant('(s)', (APP_ID,)),
            Gio.DBusCallFlags.NONE,
            -1,
            None,
            None,
        )

    def update_focus_time(self, widget, event, userdata=None):
        if event.changed_mask & Gdk.WindowState.FOCUSED and \
           event.new_window_state & Gdk.WindowState.FOCUSED:
            self.grab_media_keys()

    def update_active(self, *ignore):
        if self.window.is_active():
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
            elif action == 'Previous':
                self.window.bring_to_top()
            elif action in ('Stop', 'Pause'):
                self.window.user_pause()

    def on_prepare(self):
        def prepare_keybinder():
            display = self.window.props.screen.get_display()
            if not type(display).__name__.endswith('X11Display'):
                self.prepare_complete(error='DBus binding failed and Keybinder requires X11.')
            else:
                try:
                    import gi
                    gi.require_version('Keybinder', '3.0')
                    from gi.repository import Keybinder
                    self.keybinder = Keybinder
                    self.keybinder.init()
                except (ValueError, ImportError):
                    self.keybinder = None
                    self.prepare_complete(error='DBus binding failed and Keybinder not found.')
                else:
                    self.prepare_complete()

        def on_new_finish(source, result, data):
            try:
                mediakeys = Gio.DBusProxy.new_finish(result)
            except GLib.Error as e:
                logging.warning(e)
                prepare_keybinder()
            else:
                if mediakeys.get_name_owner():
                    self.mediakeys = mediakeys
                    self.prepare_complete()
                elif self.de_busnames:
                    de, busname = self.de_busnames.pop(0)
                    get_bus(de, busname)
                else:
                    logging.debug('DBus binding failed')
                    prepare_keybinder()

        def get_bus(de, bus_name):
            Gio.DBusProxy.new(
                self.bus,
                Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                None,
                bus_name,
                '/org/{}/SettingsDaemon/MediaKeys'.format(de),
                'org.{}.SettingsDaemon.MediaKeys'.format(de),
                None,
                on_new_finish,
                None
            )

        if self.bus:
            de, busname = self.de_busnames.pop(0)
            get_bus(de, busname)
        else:
            prepare_keybinder()

    def on_enable(self):
        if self.mediakeys:
            iface_name = self.mediakeys.props.g_interface_name
            if 'mate' in iface_name:
                # Workaround for MATE not updating it's window state properly.
                self.focus_hook = self.window.connect('notify::is-active', self.update_active)
                self.grab_media_keys()
            else:
                self.focus_hook = self.window.connect('window-state-event', self.update_focus_time)
            self.mediakey_hook = self.mediakeys.connect('g-signal', self.mediakey_signal)
            logging.info('Bound media keys with DBUS {}'.format(iface_name))
        elif self.keybinder:
            ret = self.keybinder.bind('XF86AudioPlay', self.window.playpause, None)
            if not ret:  # Presumably all bindings will fail
                self.keybinder = None # We don't need to unbind any keys
                logging.error('Failed to bind media keys with Keybinder')
                self.on_error('Failed to bind media keys with Keybinder')
                return
            self.keybinder.bind('XF86AudioStop', self.window.user_pause, None)
            self.keybinder.bind('XF86AudioPause', self.window.user_pause, None)
            self.keybinder.bind('XF86AudioNext', self.window.next_song, None)
            self.keybinder.bind('XF86AudioPrev', self.window.bring_to_top, None)
            logging.info('Bound media keys with Keybinder')

    def on_disable(self):
        if self.mediakeys:
            self.window.disconnect(self.focus_hook)
            self.mediakeys.disconnect(self.mediakey_hook)
            self.release_media_keys()
            logging.info('Disabled dbus mediakey bindings')
        elif self.keybinder:
            self.keybinder.unbind('XF86AudioPlay')
            self.keybinder.unbind('XF86AudioStop')
            self.keybinder.unbind('XF86AudioPause')
            self.keybinder.unbind('XF86AudioNext')
            self.keybinder.unbind('XF86AudioPrev')
            logging.info('Disabled keybinder mediakey bindings')
