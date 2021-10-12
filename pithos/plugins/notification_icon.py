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
    GLib,
    Gio,
    Gtk
)
from .dbus_util.DBusServiceObject import (
    DBusServiceObject,
    dbus_method,
    dbus_property
)

from pithos.plugin import PithosPlugin


class PithosStatusNotifierItem(DBusServiceObject):
    STATUS_NOTIFIER_ITEM_IFACE = 'org.kde.StatusNotifierItem'
    STATUS_NOTIFIER_ITEM_PATH = '/StatusNotifierItem'

    def __init__(self, window, **kwargs):
        self.conn = kwargs.get('connection')
        super().__init__(object_path=self.STATUS_NOTIFIER_ITEM_PATH, **kwargs)
        self.window = window
        self.status = 'Passive'
        self.icon = 'io.github.Pithos-tray-symbolic'
        logging.info('PithosStatusNotifierItem created')

    def notify_property_change(self, prop):
        self.conn.emit_signal(
            'org.kde.StatusNotifierWatcher',
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
        return False  # DBusMenu is an insane spec...

    @dbus_method(STATUS_NOTIFIER_ITEM_IFACE, 'ii')
    def Activate(self, x, y):
        if self.window.get_visible():
            self.window.hide()
        else:
            self.window.bring_to_top()

    @dbus_method(STATUS_NOTIFIER_ITEM_IFACE, 'ii')
    def SecondaryActivate(self, x, y):
        self.Activate(x, y)

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

        def on_settings_changed(settings, key):
            if key == 'data' and self.statusnotifieritem:
                self.statusnotifieritem.set_icon_name(settings[key])

        self.settings.connect('changed', on_settings_changed)

        # Connect to watcher
        def on_proxy_ready(obj, result, user_data=None):
            try:
                self.proxy = obj.new_finish(result)
            except GLib.Error as e:
                self.prepare_complete(error='Failed to connect to StatusNotifierWatcher {}'.format(e))
            else:
                logging.info('Connected to StatusNotifierWatcher')
                self.statusnotifieritem = PithosStatusNotifierItem(self.window, connection=self.proxy.get_connection())
                self.prepare_complete()

        # FIXME: We need to watch for this bus name coming and going
        Gio.DBusProxy.new(
            self.bus,
            Gio.DBusProxyFlags.DO_NOT_LOAD_PROPERTIES | Gio.DBusProxyFlags.DO_NOT_CONNECT_SIGNALS,
            None,
            'org.kde.StatusNotifierWatcher',
            '/StatusNotifierWatcher',
            'org.kde.StatusNotifierWatcher',
            None,
            on_proxy_ready,
            None
        )

    def on_enable(self):
        def on_register_failure(proxy, exception, user_data):
            logging.warning('Failed to call RegisterStatusNotifierItem: {}'.format(exception))

        def after_register(proxy, result, user_data):
            logging.info('Called RegisterStatusNotifierItem successfully')
            self.statusnotifieritem.set_icon(self.settings['data'])
            self.statusnotifieritem.set_active(True)

        bus_id = self.proxy.get_connection().get_unique_name()
        assert bus_id
        logging.info('Registering StatusNotifierItem on connection {}'.format(bus_id))
        # NOTE: We don't actually track registration but in testing it seems harmless
        #       to repeatedly call this. We could print nicer logs though.
        self.proxy.RegisterStatusNotifierItem('(s)', bus_id,
                                              result_handler=after_register,
                                              error_handler=on_register_failure)

    def on_disable(self):
        if self.statusnotifieritem:
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
