# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010 Kevin Mehall <km@kevinmehall.net>
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

from gi.repository import Gio, Gtk, GObject, Pango

from .Secrets import SecretService

try:
    import pacparser
except ImportError:
    pacparser = None
    logging.info("Could not import python-pacparser.")


class PithosPluginRow(Gtk.ListBoxRow):

    def __init__(self, plugin):
        super().__init__()

        self.plugin = plugin
        self._friendly_name = plugin.name.title().replace('_', ' ')

        box = Gtk.Box()
        label = Gtk.Label()
        label.set_markup('<b>{}</b>\n{}'.format(self._friendly_name, plugin.description))
        label.set_halign(Gtk.Align.START)
        label.set_ellipsize(Pango.EllipsizeMode.END)
        label.set_max_width_chars(30)
        label.set_line_wrap(True)
        label.set_lines(1)
        box.pack_start(label, True, True, 4)

        self.switch = Gtk.Switch()
        plugin.settings.bind('enabled', self.switch, 'active', Gio.SettingsBindFlags.DEFAULT)
        self.switch.connect('notify::active', self.on_activated)
        self.switch.set_valign(Gtk.Align.CENTER)
        box.pack_end(self.switch, False, False, 2)
        self.connect('grab-focus', self.set_prefs_btn)
        self.plugin.connect('notify::enabled', self.on_enabled)

        if plugin.prepared and plugin.error:
            self.set_sensitive(False)
            self.set_tooltip_text(plugin.error)

        self.add(box)

    def on_enabled(self, *ignore):
        if self.is_selected():
            self.set_prefs_btn()

    def set_prefs_btn(self, *ignore):
        prefs_btn = self.get_toplevel().preference_btn
        if self.plugin.enabled:
            sensitive = self.plugin.preferences_dialog is not None
        else:
            sensitive = False
        prefs_btn.set_sensitive(sensitive)
        if sensitive:
            tooltip = _('Click to change the {} plugin\'s settings.'.format(self._friendly_name))
        else:
            tooltip = _('This plugin either must be enabled or does not support preferences.')
        prefs_btn.set_tooltip_text(tooltip)

    def on_activated(self, obj, params):
        if not self.is_selected():
            self.get_parent().select_row(self)

        if self.switch.get_active():
            self.plugin.enable()
        else:
            self.plugin.disable()

        if self.plugin.prepared and self.plugin.error:
            self.get_parent().unselect_row(self)
            self.set_sensitive(False)
            self.set_tooltip_text(self.plugin.error)
        elif self.plugin.prepared:
            self.set_prefs_btn()


@Gtk.Template(resource_path='/io/github/Pithos/ui/PreferencesPithosDialog.ui')
class PreferencesPithosDialog(Gtk.Dialog):
    __gtype_name__ = "PreferencesPithosDialog"

    __gsignals__ = {
        'login-changed': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    preference_btn = Gtk.Template.Child()
    plugins_listbox = Gtk.Template.Child()
    email_entry = Gtk.Template.Child()
    password_entry = Gtk.Template.Child()
    audio_quality_combo = Gtk.Template.Child()
    proxy_entry = Gtk.Template.Child()
    control_proxy_entry = Gtk.Template.Child()
    control_proxy_pac_entry = Gtk.Template.Child()
    explicit_content_filter_checkbutton = Gtk.Template.Child()

    def __init__(self, *args, **kwargs):
        super().__init__(*args, use_header_bar=1, **kwargs)
        self.init_template()

        self.last_password = None
        self.settings = Gio.Settings.new('io.github.Pithos')

        if not pacparser:
            self.control_proxy_pac_entry.set_sensitive(False)
            self.control_proxy_pac_entry.set_tooltip_text("Please install python-pacparser")

        settings_mapping = {
            'email': (self.email_entry, 'text'),
            'proxy': (self.proxy_entry, 'text'),
            'control-proxy': (self.control_proxy_entry, 'text'),
            'control-proxy-pac': (self.control_proxy_pac_entry, 'text'),
            'audio-quality': (self.audio_quality_combo, 'active-id'),
        }

        for key, val in settings_mapping.items():
            self.settings.bind(key, val[0], val[1],
                               Gio.SettingsBindFlags.DEFAULT|Gio.SettingsBindFlags.NO_SENSITIVITY)

    def set_plugins(self, plugins):
        self.plugins_listbox.set_header_func(self.on_listbox_update_header)
        for plugin in plugins.values():
            row = PithosPluginRow(plugin)
            self.plugins_listbox.add(row)
        self.plugins_listbox.show_all()

    @Gtk.Template.Callback()
    def on_plugins_row_selected(self, box, row):
        if row:
            self.preference_btn.set_sensitive(row.plugin.preferences_dialog is not None)

    @Gtk.Template.Callback()
    def on_prefs_btn_clicked(self, btn):
        dialog = self.plugins_listbox.get_selected_rows()[0].plugin.preferences_dialog
        dialog.set_transient_for(self)
        dialog.set_destroy_with_parent(True)
        dialog.set_modal(True)
        dialog.show_all()

    @Gtk.Template.Callback()
    def on_account_changed(self, *ignore):
        if not self.email_entry.get_text() or not self.password_entry.get_text():
            self.set_response_sensitive(Gtk.ResponseType.APPLY, False)
        else:
            self.set_response_sensitive(Gtk.ResponseType.APPLY, True)

    def on_listbox_update_header(self, row, before, junk=None):
        if before and not row.get_header():
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

    @Gtk.Template.Callback()
    def on_show(self, widget):
        def cb(password):
            self.last_password = password
            self.password_entry.set_text(password)

        self.settings.delay()
        self.on_account_changed()

        self.last_email = self.settings['email']
        SecretService.get_account_password(self.last_email, cb)

    @Gtk.Template.Callback()
    def on_delete_event(self, *ignore):
        self.hide()
        self.settings.revert()
        return True

    def do_response(self, response_id):
        if response_id == Gtk.ResponseType.APPLY:
            def cb(success):
                if success:
                    self.settings.apply()
                    self.emit('login-changed', (email, password))
                else:
                    # Should never really ever happen...
                    # But just in case.
                    self.settings.revert()
                    self.show()
                    dialog = Gtk.MessageDialog(
                        parent=self,
                        flags=Gtk.DialogFlags.MODAL,
                        type=Gtk.MessageType.WARNING,
                        buttons=Gtk.ButtonsType.OK,
                        text=_('Failed to Store Your Pandora Credentials'),
                        secondary_text=_('Please re-enter your email and password.'),
                    )

                    dialog.connect('response', lambda *ignore: dialog.destroy())
                    dialog.show()

            email = self.email_entry.get_text()
            password = self.password_entry.get_text()

            if self.last_email != email or self.last_password != password:
                SecretService.set_account_password(self.last_email, email, password, cb)
            else:
                self.settings.apply()
        else:
            self.settings.revert()
