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

import os
import sys
import ctypes
import logging
import gi
from gi.repository import (
    GLib,
    GObject,
    Gio,
    Gdk,
    Gtk
)

from pithos.plugin import PithosPlugin

# Use appindicator if installed
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as AppIndicator
    indicator_capable = True
except (ImportError, ValueError):
    indicator_capable = False


def get_local_icon_path():
    # This basically duplicates what is in bin/pithos.in
    srcdir = os.environ.get('MESON_SOURCE_ROOT')
    if srcdir:
        return os.path.join(srcdir, 'data', 'icons')


def get_system_tray_supported(screen):
    from gi.repository import GdkX11

    try:
        xlib = ctypes.CDLL('libX11.so.6')
    except OSError as e:
        logging.warning('Failed to load libX11: {}'.format(e))
        return False

    screen_num = screen.get_number()
    display = screen.get_display()
    xdisplay = ctypes.c_void_p(hash(display.get_xdisplay()))
    xatom = ctypes.c_int(GdkX11.x11_get_xatom_by_name_for_display(display,
                         '_NET_SYSTEM_TRAY_S{}'.format(screen_num)))

    display.grab()
    ret = bool(xlib.XGetSelectionOwner(xdisplay, xatom))
    display.ungrab()
    xlib.XFlush(xdisplay)

    return ret


class PithosNotificationIcon(PithosPlugin):
    preference = 'show_icon'
    description = 'Adds pithos icon to system tray'

    def on_prepare(self):
        if not self.settings['data']:
            self.settings['data'] = 'io.github.Pithos-tray'
        self.preferences_dialog = NotificationIconPluginPrefsDialog(self.window, self.settings)

        def prepare_legacy_tray():
            if sys.platform in ('win32', 'darwin'):
                # These platforms always support a tray
                self.prepare_complete()
                return

            display = self.window.props.screen.get_display()
            if not type(display).__name__.endswith('X11Display'):
                error_message = 'AppIndicator tray not found' if indicator_capable \
                                else 'AppIndicator is required for this platform'
                self.prepare_complete(error=error_message)
                return

            legacy_tray_supported = get_system_tray_supported(self.window.props.screen)
            if not legacy_tray_supported:
                self.prepare_complete(error='Your platform does not have a system tray')
                return

            if indicator_capable:
                # appindicator is capable of auto-upgrading if service appears
                self._create_appindicator()
                self.prepare_complete()
            else:
                self.prepare_complete()

        if self.bus is None:
            prepare_legacy_tray()
            return

        def on_has_name_owner(bus, result):
            try:
                is_owned = bus.call_finish(result)[0]
                logging.info('org.kde.StatusNotifierWatcher is owned: {}'.format(is_owned))
            except GLib.Error as e:
                logging.exception(e)
                prepare_legacy_tray()
                return

            if is_owned:
                if indicator_capable:
                    # Simple case, Use AppIndicator
                    self._create_appindicator()
                    self.prepare_complete()
                else:
                    # If you have the service, we assume you want to use it
                    self.prepare_complete(error='AppIndicator tray found but '
                                                'AppIndicator library not installed')
            else:
                prepare_legacy_tray()

        logging.info('Checking if org.kde.StatusNotifierWatcher is owned')
        self.bus.call('org.freedesktop.DBus', '/', 'org.freedesktop.DBus',
                      'NameHasOwner', GLib.Variant('(s)', ('org.kde.StatusNotifierWatcher',)),
                      GLib.VariantType('(b)'), Gio.DBusCallFlags.NONE, -1, None, on_has_name_owner)

    def on_enable(self):
        self.delete_callback_handle = self.window.connect("delete-event", self._toggle_visible)
        self.state_callback_handle = self.window.connect("play-state-changed", self.play_state_changed)
        self.song_callback_handle = self.window.connect("song-changed", self.song_changed)

        if indicator_capable:
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        else:
            self.statusicon = Gtk.StatusIcon.new_from_icon_name(self.settings['data'])
            self.settings.bind('data', self.statusicon, 'icon-name', Gio.SettingsBindFlags.GET)
            self.statusicon.connect('activate', self._toggle_visible)

        self.build_context_menu()

    def scroll(self, direction):
        if direction == Gdk.ScrollDirection.DOWN:
            self.window.adjust_volume(-1)
        elif direction == Gdk.ScrollDirection.UP:
            self.window.adjust_volume(+1)

    def _create_appindicator(self):
        self.ind = AppIndicator.Indicator.new("io.github.Pithos-tray",
                                              self.settings['data'],
                                              AppIndicator.IndicatorCategory.APPLICATION_STATUS)
        self.settings.bind('data', self.ind, 'icon-name', Gio.SettingsBindFlags.GET)
        local_icon_path = get_local_icon_path()
        if local_icon_path:
            self.ind.set_icon_theme_path(local_icon_path)

    def build_context_menu(self):
        menu = Gtk.Menu()

        def button(text, action, checked=False):
            if checked:
                item = Gtk.CheckMenuItem.new_with_label(text)
                item.set_active(True)
            else:
                item = Gtk.MenuItem.new_with_label(text)
            handler = item.connect('activate', action)
            item.show()
            menu.append(item)
            return item, handler

        if indicator_capable:
            # We have to add another entry for show / hide Pithos window
            self.visible_check, handler = button("Show Pithos", self._toggle_visible, True)

            def set_active(active):
                GObject.signal_handler_block(self.visible_check, handler)
                self.visible_check.set_active(active)
                GObject.signal_handler_unblock(self.visible_check, handler)

            # Ensure it is kept in sync
            self.window.connect("hide", lambda w: set_active(False))
            self.window.connect("show", lambda w: set_active(True))

            # On middle-click
            self.ind.set_secondary_activate_target(self.visible_check)

        self.playpausebtn = button("Pause", self.window.playpause)[0]
        button("Skip", self.window.next_song)
        button("Love", (lambda *i: self.window.love_song()))
        button("Ban", (lambda *i: self.window.ban_song()))
        button("Tired", (lambda *i: self.window.tired_song()))
        button("Quit", self.window.quit)

        # connect our new menu to the statusicon or the appindicator
        if indicator_capable:
            self.ind.set_menu(menu)
            self.ind.connect('scroll-event', lambda wid, steps, direction: self.scroll(direction))
        else:
            self.statusicon.connect('popup-menu', self.context_menu, menu)
            self.statusicon.connect('scroll-event', lambda wid, event: self.scroll(event.direction))

        self.menu = menu

    def play_state_changed(self, window, playing):
        """ play or pause and rotate the text """

        button = self.playpausebtn
        if not playing:
            button.set_label("Play")
        else:
            button.set_label("Pause")

        if indicator_capable: # menu needs to be reset to get updated icon
            self.ind.set_menu(self.menu)

    def song_changed(self, window, song):
        if not indicator_capable:
            self.statusicon.set_tooltip_text("{} by {}".format(song.title, song.artist))

    def _toggle_visible(self, *args):
        if self.window.get_visible():
            self.window.hide()
        else:
            self.window.bring_to_top()
        return True

    def context_menu(self, widget, button, time, data=None):
        if button == 3:
            if data:
                data.show_all()
                data.popup(None, None, None, None, 3, time)

    def on_disable(self):
        if indicator_capable:
            self.ind.set_status(AppIndicator.IndicatorStatus.PASSIVE)
        else:
            self.statusicon.set_visible(False)

        self.window.disconnect(self.delete_callback_handle)
        self.window.disconnect(self.state_callback_handle)
        self.window.disconnect(self.song_callback_handle)

        # Pithos window needs to be reconnected to on_destro()
        self.window.connect('delete-event', self.window.on_destroy)


class NotificationIconPluginPrefsDialog(Gtk.Dialog):

    def __init__(self, parent, settings):
        super().__init__(
            title=_('Icon Type'),
            transient_for=parent,
            use_header_bar=1,
            resizable=False,
            default_width=300
        )
        self.settings = settings

        self.add_buttons('_Cancel', Gtk.ResponseType.CANCEL, '_Apply', Gtk.ResponseType.APPLY)

        self.connect('delete-event', lambda *ignore: self.response(Gtk.ResponseType.CANCEL) or True)

        sub_title = Gtk.Label.new(_('Set the Notification Icon Type'))
        sub_title.set_halign(Gtk.Align.CENTER)
        self.icons_combo = Gtk.ComboBoxText.new()

        icons = (
            ('io.github.Pithos-tray', _('Full Color')),
            ('io.github.Pithos-symbolic', _('Symbolic')),
        )

        for icon in icons:
            self.icons_combo.append(icon[0], icon[1])
        self._reset_combo()

        content_area = self.get_content_area()
        content_area.add(sub_title)
        content_area.add(self.icons_combo)
        content_area.show_all()

    def _reset_combo(self):
        self.icons_combo.set_active_id(self.settings['data'])

    def do_response(self, response):
        if response == Gtk.ResponseType.APPLY:
            self.settings['data'] = self.icons_combo.get_active_id()
        else:
            self._reset_combo()
        self.hide()
