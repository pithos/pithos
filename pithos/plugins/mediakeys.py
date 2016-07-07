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

from pithos.plugin import PithosPlugin
import sys
import logging

from gi.repository import GLib, Gio, Gdk

APP_ID = 'io.github.Pithos'

class MediaKeyPlugin(PithosPlugin):
    preference = 'enable_mediakeys'
    description = 'Control playback with media keys'

    def bind_dbus(self):
        # FIXME: Make all dbus usage async
        def grab_media_keys():
            try:
                self.mediakeys.call_sync('GrabMediaPlayerKeys', GLib.Variant('(su)', (APP_ID, 0)),
                                    Gio.DBusCallFlags.NONE, -1, None)
                return True
            except GLib.Error as e:
                logging.debug(e)
                return False

        bound = hasattr(self, 'method') and self.method == 'dbus' # We may have bound it earlier
        if not bound:
            try:
                bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
                logging.info('Got session bus')
            except GLib.Error as e:
                logging.warning(e)
                return False

            for de in ('gnome', 'mate'):
                try:
                    self.mediakeys = Gio.DBusProxy.new_sync(bus, Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES, None,
                                                        'org.%s.SettingsDaemon' %de,
                                                        '/org/%s/SettingsDaemon/MediaKeys' %de,
                                                        'org.%s.SettingsDaemon.MediaKeys' %de,
                                                        None)
                    if grab_media_keys():
                        bound = True
                        break;
                except GLib.Error as e:
                    logging.warning(e)
                    return False
            else:
                return False

        def update_focus_time(widget, event, userdata=None):
            if event.changed_mask & Gdk.WindowState.FOCUSED and event.new_window_state & Gdk.WindowState.FOCUSED:
                grab_media_keys()
            return False

        def mediakey_signal(proxy, sender, signal, param, userdata=None):
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

        self.focus_hook = self.window.connect('window-state-event', update_focus_time)
        if not getattr(self, 'mediakey_hook', 0):
            self.mediakey_hook = self.mediakeys.connect('g-signal', mediakey_signal)
        else:
            grab_media_keys() # Was disabled previously
        logging.info("Bound media keys with DBUS (%s)" %self.mediakeys.props.g_interface_name)
        self.method = 'dbus'
        return True

    def bind_keybinder(self):
        try:
            import gi
            gi.require_version('Keybinder', '3.0')
            # Gdk needed for Keybinder
            from gi.repository import Keybinder
            Keybinder.init()
        except (ValueError, ImportError):
            return False
        
        Keybinder.bind('XF86AudioPlay', self.window.playpause, None)
        Keybinder.bind('XF86AudioStop', self.window.user_pause, None)
        Keybinder.bind('XF86AudioNext', self.window.next_song, None)
        Keybinder.bind('XF86AudioPrev', self.window.bring_to_top, None)
        
        logging.info("Bound media keys with keybinder")
        self.method = 'keybinder'
        return True

    def kbevent(self, event):
        if event.KeyID == 179 or event.Key == 'Media_Play_Pause':
            self.window.playpause_notify()
        if event.KeyID == 176 or event.Key == 'Media_Next_Track':
            self.window.next_song()
        return True

    def bind_win32(self):
        try:
            import pyHook
        except ImportError:
            logging.warning('Please install PyHook: http://www.lfd.uci.edu/~gohlke/pythonlibs/#pyhook')
            return False
        self.hookman = pyHook.HookManager()
        self.hookman.KeyDown = self.kbevent
        self.hookman.HookKeyboard()
        return True

    def osx_playpause_handler(self):
        self.window.playpause_notify()
        return False # Don't let others get event

    def osx_skip_handler(self):
        self.window.next_song()
        return False

    def bind_osx(self):
        try:
            import osxmmkeys
        except ImportError:
            logging.warning('Please install osxmmkeys: https://github.com/pushrax/osxmmkeys')
            return False
        except RuntimeError as e:
            logging.warning('osxmmkeys failed to import: {}'.format(e))
            return False

        tap = osxmmkeys.Tap()
        tap.on('play_pause', self.osx_playpause_handler)
        tap.on('next_track', self.osx_skip_handler)
        tap.start()

        return True
        
    def on_enable(self):
        if sys.platform == 'win32':
            loaded = self.bind_win32()
        elif sys.platform == 'darwin':
            loaded = self.bind_osx()
        else:
            loaded = self.bind_dbus() or self.bind_keybinder()

        if not loaded:
            logging.error("Could not bind media keys")
        
    def on_disable(self):
        if self.method == 'dbus':
            self.mediakeys.call_sync('ReleaseMediaPlayerKeys', GLib.Variant('(s)', (APP_ID,)),
                                     Gio.DBusCallFlags.NONE, -1, None)
            self.window.disconnect(self.focus_hook)
            self.focus_hook = 0
            logging.info("Disabled dbus mediakey bindings")
        else:
            logging.error("Not implemented: Can't disable media keys bound with %s", self.method)
