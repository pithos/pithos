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
import gi

from gi.repository import (
    GLib,
    Gio,
    Gtk
)

try:
    gi.require_versions({
        'DbusmenuGtk3': '0.4',
        'Dbusmenu': '0.4',
    })
    from gi.repository import Dbusmenu, DbusmenuGtk3
    have_dbusmenu = True
    logging.info('Imported Dbusmenu')
except (ValueError, ImportError) as e:
    logging.info('Failed to import Dbusmenu: {}'.format(e))
    have_dbusmenu = False

from .dbus_util.DBusServiceObject import (
    DBusServiceObject,
    dbus_method,
    dbus_property
)

from pithos.plugin import PithosPlugin


STATUS_NOTIFIER_WATCH_NAME = 'org.kde.StatusNotifierWatcher'
STATUS_NOTIFIER_WATCH_PATH = '/StatusNotifierWatcher'
STATUS_NOTIFIER_WATCH_IFACE = 'org.kde.StatusNotifierWatcher'

DBUS_MENU_PATH = '/io/github/Pithos/notification_icon/menu'

class PithosStatusNotifierItem(DBusServiceObject):
    STATUS_NOTIFIER_ITEM_IFACE = 'org.kde.StatusNotifierItem'
    STATUS_NOTIFIER_ITEM_PATH = '/StatusNotifierItem'

    def __init__(self, window, **kwargs):
        self.conn = kwargs.get('connection')
        self.icon = kwargs.pop('icon')
        super().__init__(object_path=self.STATUS_NOTIFIER_ITEM_PATH, **kwargs)
        self.window = window
        self.status = 'Passive'
        logging.info('PithosStatusNotifierItem created')

    def notify_property_change(self, prop):
        self.conn.emit_signal(
            STATUS_NOTIFIER_WATCH_NAME,
            self.STATUS_NOTIFIER_ITEM_PATH,
            self.STATUS_NOTIFIER_ITEM_IFACE,
            'New' + prop,
            GLib.Variant('(s)', (self.status, )) if prop == 'Status' else None
        )

    def set_active(self, active):
        self.status = 'Active' if active else 'Passive'
        self.notify_property_change('Status')

    def set_icon(self, icon):
        self.icon = icon
        self.notify_property_change('Icon')

    def toggle_visible(self, *args):
        if self.window.get_visible():
            self.window.hide()
        else:
            self.window.bring_to_top()

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 's')
    def Id(self):
        return 'pithos'

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 's')
    def Title(self):
        return 'Pithos'

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 's')
    def Category(self):
        return 'ApplicationStatus'

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 's')
    def Status(self):
        return self.status

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 'u')
    def Window(self):
        return 0  # Not available on Wayland?

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 's')
    def IconName(self):
        return self.icon

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 's')
    def OverlayIconName(self):
        return ''

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 's')
    def AttentionIconName(self):
        return ''

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 'b')
    def ItemIsMenu(self):
        return have_dbusmenu

    @dbus_property(STATUS_NOTIFIER_ITEM_IFACE, 'o')
    def Menu(self):
        return DBUS_MENU_PATH if have_dbusmenu else '/NO_DBUSMENU'

    @dbus_method(STATUS_NOTIFIER_ITEM_IFACE, 'ii')
    def Activate(self, x, y):
        self.toggle_visible()

    @dbus_method(STATUS_NOTIFIER_ITEM_IFACE, 'ii')
    def SecondaryActivate(self, x, y):
        self.toggle_visible()

    @dbus_method(STATUS_NOTIFIER_ITEM_IFACE, 'is')
    def Scroll(self, delta, orientation):
        if orientation == 'vertical':
            self.window.adjust_volume(-delta)


class PithosNotificationIcon(PithosPlugin):
    preference = 'show_icon'
    description = 'Adds Pithos StatusNotifier to tray'

    def on_prepare(self):
        # Preferences for icon type
        if not self.settings['data']:
            self.settings['data'] = 'io.github.Pithos-tray-symbolic'
        self.preferences_dialog = NotificationIconPluginPrefsDialog(self.window, self.settings)

        def on_icon_theme_changed(settings, key):
            if self.statusnotifieritem:
                self.statusnotifieritem.set_icon(settings[key])

        self.settings.connect('changed::data', on_icon_theme_changed)

        self.registered = False

        def on_registered_signal(conn, sender, path, iface, signal, params, user_data):
            bus_id = params.get_child_value(0).get_string()
            if bus_id.startswith(self.bus_id):
                logging.info('StatusNotifierItemRegistered')
                self.registered = True

        def on_unregistered_signal(conn, sender, path, iface, signal, params, user_data):
            bus_id = params.get_child_value(0).get_string()
            if bus_id.startswith(self.bus_id):
                logging.info('StatusNotifierItemUnregistered')
                self.registered = False
                self._show_window()

        def on_watcher_appeared(conn, name, name_owner, user_data=None):
            self.registered_signal_handler = conn.signal_subscribe(
                STATUS_NOTIFIER_WATCH_NAME,
                STATUS_NOTIFIER_WATCH_IFACE,
                'StatusNotifierItemRegistered',
                STATUS_NOTIFIER_WATCH_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                on_registered_signal,
                None
            )
            self.unregistered_signal_handler = conn.signal_subscribe(
                STATUS_NOTIFIER_WATCH_NAME,
                STATUS_NOTIFIER_WATCH_IFACE,
                'StatusNotifierItemUnregistered',
                STATUS_NOTIFIER_WATCH_PATH,
                None,
                Gio.DBusSignalFlags.NONE,
                on_unregistered_signal,
                None
            )

            self.bus_id = conn.get_unique_name()
            logging.info('Calling RegisterStatusNotifierItem("{}")'.format(self.bus_id))
            conn.call(
                STATUS_NOTIFIER_WATCH_NAME,
                STATUS_NOTIFIER_WATCH_PATH,
                STATUS_NOTIFIER_WATCH_IFACE,
                'RegisterStatusNotifierItem',
                GLib.Variant('(s)', (self.bus_id, )),
                None,
                Gio.DBusCallFlags.NONE,
                -1,
                None,
                None
            )

        def on_watcher_disappear(conn, name, user_data=None):
            logging.info('StatusNotifierWatcher disappeared')
            if hasattr(self, 'registered_signal_handler'):
                conn.signal_unsubscribe(self.registered_signal_handler)
                del self.registered_signal_handler
            if hasattr(self, 'unregistered_signal_handler'):
                conn.signal_unsubscribe(self.unregistered_signal_handler)
                del self.unregistered_signal_handler
            self.registered = False
            self._show_window()

        Gio.bus_watch_name_on_connection(
            self.bus,
            STATUS_NOTIFIER_WATCH_NAME,
            Gio.BusNameWatcherFlags.AUTO_START,
            on_watcher_appeared,
            on_watcher_disappear
        )

        self._setup_dbusmenu()
        self.statusnotifieritem = PithosStatusNotifierItem(self.window, connection=self.bus, icon=self.settings['data'])
        self.prepare_complete()

    def _play_state_changed(self, window, playing):
        self.playpausebtn.set_label("Pause" if playing else "Play")

    def _build_context_menu(self):
        menu = Gtk.Menu()

        def button(text, action):
            item = Gtk.MenuItem(text)
            item.connect('activate', action)
            item.show()
            menu.append(item)
            return item

        self.playpausebtn = button("Pause", self.window.playpause)
        button("Skip",  self.window.next_song)
        button("Love",  (lambda *i: self.window.love_song()))
        button("Ban",   (lambda *i: self.window.ban_song()))
        button("Tired", (lambda *i: self.window.tired_song()))
        button("Quit",  self.window.quit)

        self.menu = menu

    def _setup_dbusmenu(self):
        if not have_dbusmenu:
            return

        self._build_context_menu()
        self.dbusmenuservice = Dbusmenu.Server.new(DBUS_MENU_PATH)
        self.dbusmenuservice.set_root(DbusmenuGtk3.gtk_parse_menu_structure(self.menu))

    def _show_window(self):
        if not self.window.get_visible():
            self.window.show()

    def _toggle_visible(self, *args):
        if self.registered:
            self.statusnotifieritem.toggle_visible()
            return True

    def on_enable(self):
        self.delete_callback_handle = self.window.connect('delete-event', self._toggle_visible)
        self.state_callback_handle = self.window.connect('play-state-changed', self._play_state_changed)
        self.statusnotifieritem.set_active(True)

    def on_disable(self):
        self.window.disconnect(self.delete_callback_handle)
        self.window.disconnect(self.state_callback_handle)
        self.statusnotifieritem.set_active(False)


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
