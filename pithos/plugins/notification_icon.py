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

from gi.repository import (
    GObject,
    GLib,
    Gtk,
    Gdk,
    Gio
)

from pithos.plugin import PithosPlugin


class PithosNotificationIcon(PithosPlugin):
    preference = 'show_icon'
    description = 'Adds pithos icon to system tray'

    appindicator = None

    def on_prepare(self):
        # 1st we check for AppIndicator3.
        # If it's not found we check to make sure we aren't running on KDE Plasma
        # because it doesn't support Gtk.StatusIcon. If we aren't we then
        # check to make sure we aren't running in Wayland because GNOME Shell doesn't support
        # tray icons in Wayland.
        # If AppIndicator3 is found we check for com.canonical.indicator.application
        # or if we have the appindicatorsupport GNOME Shell extension installed and enabled,
        # if not we check to see if we're running in KDE Plasma. If we aren't running in KDE Plasma,
        # have the indicator.application service or have the appindicatorsupport GNOME Shell extension
        # installed and enabled we have to check to see if we're on Wayland to see if we can use Gtk.StatusIcon.
        # It's all rather convoluted...
        def check_for_x():
            self.appindicator = None
            display = self.window.props.screen.get_display()
            if not type(display).__name__.endswith('X11Display'):
                logging.debug('Notification icon requires X11 or AppIndicator Support')
                self.prepare_complete(error='Notification icon requires X11 or AppIndicator Support')
            else:
                self.prepare_complete()

        def init_appindicator():
            self.ind = self.appindicator.Indicator.new(
                "pithos-tray-icon",
                "pithos-tray-icon",
                self.appindicator.IndicatorCategory.APPLICATION_STATUS,
            )

            self.prepare_complete()

        def has_appindicator_shell_ext():
            schema = Gio.SettingsSchemaSource.get_default()
            valid_schema = schema.lookup('org.gnome.shell', True)
            if valid_schema:
                gnome_shell = Gio.Settings.new('org.gnome.shell')
                enabled_extensions = gnome_shell.get_value('enabled-extensions')
                if 'appindicatorsupport@rgcjonas.gmail.com' in enabled_extensions:
                    return True
            return False

        def on_plasmashell_finish(source, result, data):
            try:
                plasmashell = Gio.DBusProxy.new_finish(result)
            except GLib.Error as e:
                logging.debug(e)
                check_for_x()
            else:
                bus_owned = plasmashell.get_name_owner()
                if bus_owned and self.appindicator:
                    init_appindicator()
                elif bus_owned and not self.appindicator:
                    logging.debug('Notification icon requires AppIndicator on Plasma')
                    self.prepare_complete(error='Notification icon requires AppIndicator on Plasma')
                else:
                    check_for_x()

        def on_indicator_finish(source, result, data):
            try:
                indicator_service = Gio.DBusProxy.new_finish(result)
            except GLib.Error as e:
                logging.debug(e)
                check_for_x()
            else:
                if indicator_service.get_name_owner() or has_appindicator_shell_ext():
                    init_appindicator()
                else:
                    check_for_plasma()

        def check_for_plasma():
            Gio.DBusProxy.new(
                self.bus,
                Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                None,
                'org.kde.plasmashell',
                '/org/kde/plasmashell',
                'org.kde.plasmashell',
                None,
                on_plasmashell_finish,
                None
            )

        try:
            import gi
            gi.require_version('AppIndicator3', '0.1')
            from gi.repository import AppIndicator3
            self.appindicator = AppIndicator3
        except (ImportError, ValueError):
            self.appindicator = None
            check_for_plasma()
        else:
            Gio.DBusProxy.new(
                self.bus,
                Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES,
                None,
                'com.canonical.indicator.application',
                '/com/canonical/indicator/application/service',
                'com.canonical.indicator.application.service',
                None,
                on_indicator_finish,
                None
            )

    def on_enable(self):
        if self.appindicator:
            self.ind.set_status(self.appindicator.IndicatorStatus.ACTIVE)
        else:
            self.statusicon = Gtk.StatusIcon.new_from_icon_name('io.github.Pithos-tray')
            self.statusicon.connect('activate', self._toggle_visible)

        self.build_context_menu()

        self.window_handlers = [
            self.window.connect("delete-event", self._toggle_visible),
            self.window.connect("play-state-changed", self.play_state_changed),
            self.window.connect("song-changed", self.song_changed)
        ]

    def scroll(self, direction):
        if direction == Gdk.ScrollDirection.DOWN:
            self.window.adjust_volume(-1)
        elif direction == Gdk.ScrollDirection.UP:
            self.window.adjust_volume(+1)

    def build_context_menu(self):
        menu = Gtk.Menu()

        def button(text, action, checked=False):
            if checked:
                item = Gtk.CheckMenuItem(text)
                item.set_active(True)
            else:
                item = Gtk.MenuItem(text)
            handler = item.connect('activate', action)
            item.show()
            menu.append(item)
            return item, handler

        if self.appindicator:
            # We have to add another entry for show / hide Pithos window
            self.visible_check, handler = button("Show Pithos", self._toggle_visible, True)

            def set_active(active):
                GObject.signal_handler_block(self.visible_check, handler)
                self.visible_check.set_active(active)
                GObject.signal_handler_unblock(self.visible_check, handler)
                return True

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
        if self.appindicator:
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

        if self.appindicator: # menu needs to be reset to get updated icon
            self.ind.set_menu(self.menu)

    def song_changed(self, window, song):
        if not self.appindicator:
            self.statusicon.set_tooltip_text("{} by {}".format(song.title, song.artist))

    def _toggle_visible(self, *args):
        self.window.set_visible(not self.window.get_visible())

        if self.window.get_visible(): # Ensure it's on top
            self.window.bring_to_top()

        return True

    def context_menu(self, widget, button, time, data=None):
        if button == 3:
            if data:
                data.show_all()
                data.popup(None, None, None, None, 3, time)

    def on_disable(self):
        if self.appindicator:
            self.ind.set_status(self.appindicator.IndicatorStatus.PASSIVE)
        else:
            self.statusicon.set_visible(False)

        for handler in self.window_handlers:
            self.window.disconnect(handler)

        # Pithos window needs to be reconnected to on_destro()
        self.window.connect('delete-event', self.window.on_destroy)
