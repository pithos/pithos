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

import sys
import os
import stat
import logging

from gi.repository import Gio, Gtk, GObject, GLib, Pango

from .util import get_account_password, set_account_password
from .pandora.data import *

pacparser_imported = False
try:
    import pacparser
    pacparser_imported = True
except ImportError:
    logging.info("Could not import python-pacparser.")


class PithosPluginRow(Gtk.ListBoxRow):

    def __init__(self, plugin):
        Gtk.ListBoxRow.__init__(self)

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
            self.get_toplevel().preference_btn.set_sensitive(self.plugin.preferences_dialog != None)

class PreferencesPithosDialog(Gtk.Dialog):
    __gtype_name__ = "PreferencesPithosDialog"

    def __init__(self):
        """__init__ - This function is typically not called directly.
        Creation of a PreferencesPithosDialog requires reading the associated ui
        file and parsing the ui definition extrenally,
        and then calling PreferencesPithosDialog.finish_initializing().

        Use the convenience function NewPreferencesPithosDialog to create
        NewAboutPithosDialog objects.
        """

        pass

    def finish_initializing(self, builder, settings):
        """finish_initalizing should be called after parsing the ui definition
        and creating a AboutPithosDialog object with it in order to finish
        initializing the start of the new AboutPithosDialog instance.
        """
        self.settings = settings

        # get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)
        self.preference_btn = self.builder.get_object('prefs_btn')
        self.listbox = self.builder.get_object('plugins_listbox')
        self.email = self.builder.get_object('prefs_username')
        self.password = self.builder.get_object('prefs_password')

        # initialize the "Audio Quality" combobox backing list
        audio_quality_combo = self.builder.get_object('prefs_audio_quality')
        fmt_store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        for audio_quality in valid_audio_formats:
            fmt_store.append(audio_quality)
        audio_quality_combo.set_model(fmt_store)
        render_text = Gtk.CellRendererText()
        audio_quality_combo.pack_start(render_text, True)
        audio_quality_combo.add_attribute(render_text, "text", 1)
        audio_quality_combo.set_id_column(0)

        if not pacparser_imported:
            self.builder.get_object('prefs_control_proxy_pac').set_sensitive(False)
            self.builder.get_object('prefs_control_proxy_pac').set_tooltip_text("Please install python-pacparser")

        settings_mapping = {
            'email': ('prefs_username', 'text'),
            'pandora-one': ('checkbutton_pandora_one', 'active'),
            'proxy': ('prefs_proxy', 'text'),
            'control-proxy': ('prefs_control_proxy', 'text'),
            'control-proxy-pac': ('prefs_control_proxy_pac', 'text'),
            'audio-quality': ('prefs_audio_quality', 'active-id'),
        }

        for key, val in settings_mapping.items():
            settings.bind(key, self.builder.get_object(val[0]), val[1],
                        Gio.SettingsBindFlags.DEFAULT|Gio.SettingsBindFlags.NO_SENSITIVITY)

        self.password.set_text(get_account_password(self.settings.get_string('email')))

        self.on_account_changed(None)

    def set_plugins(self, plugins):
        if len(self.listbox.set_header_func.get_arguments()) == 3:
            # pygobject3 3.10
            self.listbox.set_header_func(self.on_listbox_update_header, None)
        else:
            # pygobject3 3.12+
            self.listbox.set_header_func(self.on_listbox_update_header)
        for plugin in plugins.values():
            row = PithosPluginRow(plugin)
            self.listbox.add(row)
        self.listbox.show_all()

    def on_plugins_row_selected(self, box, row):
        if row:
            self.preference_btn.set_sensitive(row.plugin.preferences_dialog != None)

    def on_prefs_btn_clicked(self, btn):
        dialog = self.listbox.get_selected_rows()[0].plugin.preferences_dialog
        dialog.set_transient_for(self)
        dialog.set_destroy_with_parent(True)
        dialog.set_modal(True)
        dialog.show_all()

    def on_account_changed(self, widget):
        if not self.email.get_text() or not self.password.get_text():
            self.set_response_sensitive(Gtk.ResponseType.APPLY, False)
        else:
            self.set_response_sensitive(Gtk.ResponseType.APPLY, True)

    def on_listbox_update_header(self, row, before, junk = None):
        if before and not row.get_header():
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

    def do_response(self, response_id):
        if response_id == Gtk.ResponseType.APPLY:
            set_account_password(self.email.get_text(), self.password.get_text())
            self.settings.apply()
        else:
            self.settings.revert()


def NewPreferencesPithosDialog(settings):
    """NewPreferencesPithosDialog - returns a fully instantiated
    PreferencesPithosDialog object. Use this function rather than
    creating a PreferencesPithosDialog instance directly.
    """

    builder = Gtk.Builder.new_from_resource('/io/github/Pithos/ui/PreferencesPithosDialog.ui')
    dialog = builder.get_object("preferences_pithos_dialog")
    dialog.finish_initializing(builder, settings)
    return dialog

if __name__ == "__main__":
    dialog = NewPreferencesPithosDialog()
    dialog.show()
    Gtk.main()
