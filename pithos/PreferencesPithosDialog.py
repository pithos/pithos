# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010 Kevin Mehall <km@kevinmehall.net>
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

from gi.repository import Gio, Gtk, GObject, Pango

from .gi_composites import GtkTemplate
from .util import get_account_password, set_account_password
from .pandora.data import valid_audio_formats

try:
    import pacparser
except ImportError:
    pacparser = None
    logging.info("Could not import python-pacparser.")


class PithosPluginRow(Gtk.ListBoxRow):

    def __init__(self, plugin):
        super().__init__()

        self.plugin = plugin

        box = Gtk.Box()
        label = Gtk.Label()
        label.set_markup('<b>{}</b>\n{}'.format(plugin.name.title().replace('_', ' '), plugin.description))
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

        if plugin.prepared and plugin.error:
            self.set_sensitive(False)
            self.set_tooltip_text(plugin.error)

        self.add(box)

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
            self.get_toplevel().preference_btn.set_sensitive(self.plugin.preferences_dialog is not None)


@GtkTemplate(ui='/io/github/Pithos/ui/PreferencesPithosDialog.ui')
class PreferencesPithosDialog(Gtk.Dialog):
    __gtype_name__ = "PreferencesPithosDialog"

    preference_btn = GtkTemplate.Child()
    plugins_listbox = GtkTemplate.Child()
    email_entry = GtkTemplate.Child()
    password_entry = GtkTemplate.Child()
    audio_quality_combo = GtkTemplate.Child()
    proxy_entry = GtkTemplate.Child()
    control_proxy_entry = GtkTemplate.Child()
    control_proxy_pac_entry = GtkTemplate.Child()
    pandora_one_checkbutton = GtkTemplate.Child()
    explicit_content_filter_checkbutton = GtkTemplate.Child()

    def __init__(self, settings, *args, **kwargs):
        super().__init__(*args, use_header_bar=1, **kwargs)
        self.init_template()

        self.settings = settings

        # initialize the "Audio Quality" combobox backing list
        fmt_store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        for audio_quality in valid_audio_formats:
            fmt_store.append(audio_quality)
        self.audio_quality_combo.set_model(fmt_store)
        render_text = Gtk.CellRendererText()
        self.audio_quality_combo.pack_start(render_text, True)
        self.audio_quality_combo.add_attribute(render_text, "text", 1)
        self.audio_quality_combo.set_id_column(0)

        if not pacparser:
            self.control_proxy_pac_entry.set_sensitive(False)
            self.control_proxy_pac_entry.set_tooltip_text("Please install python-pacparser")

        settings_mapping = {
            'email': (self.email_entry, 'text'),
            'pandora-one': (self.pandora_one_checkbutton, 'active'),
            'proxy': (self.proxy_entry, 'text'),
            'control-proxy': (self.control_proxy_entry, 'text'),
            'control-proxy-pac': (self.control_proxy_pac_entry, 'text'),
            'audio-quality': (self.audio_quality_combo, 'active-id'),
        }

        for key, val in settings_mapping.items():
            settings.bind(key, val[0], val[1],
                        Gio.SettingsBindFlags.DEFAULT|Gio.SettingsBindFlags.NO_SENSITIVITY)

        self.password_entry.set_text(get_account_password(self.settings.get_string('email')))

        self.on_account_changed(None)

    def set_plugins(self, plugins):
        self.plugins_listbox.set_header_func(self.on_listbox_update_header)
        for plugin in plugins.values():
            row = PithosPluginRow(plugin)
            self.plugins_listbox.add(row)
        self.plugins_listbox.show_all()

    @GtkTemplate.Callback
    def on_plugins_row_selected(self, box, row):
        if row:
            self.preference_btn.set_sensitive(row.plugin.preferences_dialog is not None)

    @GtkTemplate.Callback
    def on_prefs_btn_clicked(self, btn):
        dialog = self.plugins_listbox.get_selected_rows()[0].plugin.preferences_dialog
        dialog.set_transient_for(self)
        dialog.set_destroy_with_parent(True)
        dialog.set_modal(True)
        dialog.show_all()

    @GtkTemplate.Callback
    def on_account_changed(self, widget):
        if not self.email_entry.get_text() or not self.password_entry.get_text():
            self.set_response_sensitive(Gtk.ResponseType.APPLY, False)
        else:
            self.set_response_sensitive(Gtk.ResponseType.APPLY, True)

    def on_listbox_update_header(self, row, before, junk = None):
        if before and not row.get_header():
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

    def do_response(self, response_id):
        if response_id == Gtk.ResponseType.APPLY:
            set_account_password(self.email_entry.get_text(), self.password_entry.get_text())
            self.settings.apply()
        else:
            self.settings.revert()

