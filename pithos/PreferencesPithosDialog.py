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

from gi.repository import Gtk, GObject, GLib, Pango

from .pandora.data import *
from .pithosconfig import get_ui_file
from .player import get_players

pacparser_imported = False
try:
    import pacparser
    pacparser_imported = True
except ImportError:
    logging.info("Could not import python-pacparser.")

config_home = GLib.get_user_config_dir()
configfilename = os.path.join(config_home, 'pithos.ini')

class PithosPluginRow(Gtk.ListBoxRow):

    def __init__(self, plugin, enabled):
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
        self.switch.set_active(enabled)
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
    prefernces = {}

    def __init__(self):
        """__init__ - This function is typically not called directly.
        Creation of a PreferencesPithosDialog requires reading the associated ui
        file and parsing the ui definition extrenally,
        and then calling PreferencesPithosDialog.finish_initializing().

        Use the convenience function NewPreferencesPithosDialog to create
        NewAboutPithosDialog objects.
        """

        pass

    def finish_initializing(self, builder):
        """finish_initalizing should be called after parsing the ui definition
        and creating a AboutPithosDialog object with it in order to finish
        initializing the start of the new AboutPithosDialog instance.
        """

        # get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)
        self.preference_btn = self.builder.get_object('prefs_btn')
        self.listbox = self.builder.get_object('plugins_listbox')

        render_text = Gtk.CellRendererText()

        # initialize the "Audio Player" combobox backing list
        audio_player_combo = self.builder.get_object('prefs_audio_player')
        player_store = Gtk.ListStore(str, str)
        player_store.set_sort_column_id(1, Gtk.SortType.ASCENDING)
        for name, player in get_players().items():
            player_store.append((name, player.description))
        audio_player_combo.set_model(player_store)
        audio_player_combo.pack_start(render_text, True)
        audio_player_combo.add_attribute(render_text, "text", 1)

        # initialize the "Audio Quality" combobox backing list
        audio_quality_combo = self.builder.get_object('prefs_audio_quality')
        fmt_store = Gtk.ListStore(str, str)
        for audio_quality in valid_audio_formats:
            fmt_store.append(audio_quality)
        audio_quality_combo.set_model(fmt_store)
        audio_quality_combo.pack_start(render_text, True)
        audio_quality_combo.add_attribute(render_text, "text", 1)

        self.__load_preferences()

    def set_plugins(self, plugins):
        self.listbox.set_header_func(self.on_listbox_update_header)
        for plugin in plugins.values():
            row = PithosPluginRow(plugin, self.__preferences[plugin.preference])
            self.listbox.add(row)
        self.listbox.show_all()

    def get_preferences(self):
        """get_preferences  - returns a dictionary object that contains
        preferences for pithos.
        """
        return self.__preferences

    def on_plugins_row_selected(self, box, row):
        if row:
            self.preference_btn.set_sensitive(row.plugin.preferences_dialog != None)

    def on_prefs_btn_clicked(self, btn):
        dialog = self.listbox.get_selected_rows()[0].plugin.preferences_dialog
        dialog.set_transient_for(self)
        dialog.set_destroy_with_parent(True)
        dialog.set_modal(True)
        dialog.show_all()

    def on_listbox_update_header(self, row, before):
        if before and not row.get_header():
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))

    def __load_preferences(self):
        #default preferences that will be overwritten if some are saved
        self.__preferences = {
            "username": '',
            "password": '',
            "x_pos": None,
            "y_pos": None,
            "notify": True,
            "last_station_id": None,
            "proxy": '',
            "control_proxy": '',
            "control_proxy_pac": '',
            "show_icon": False,
            "lastfm_key": False,
            "enable_mediakeys": True,
            "enable_screensaverpause": False,
            "enable_lastfm": False,
            "enable_mpris": True,
            "volume": 1.0,
            # If set, allow insecure permissions. Implements CVE-2011-1500
            "unsafe_permissions": False,
            "audio_player": "GstPlayer",
            "audio_quality": default_audio_quality,
            "pandora_one": False,
            "force_client": None,
        }

        try:
            with open(configfilename) as f:
                for line in f:
                    sep = line.find('=')
                    key = line[:sep]
                    val = line[sep+1:].strip()
                    if val == 'None':
                        val = None
                    elif val == 'False':
                        val = False
                    elif val == 'True':
                        val = True
                    self.__preferences[key] = val
        except IOError:
            pass


        if 'audio_format' in self.__preferences:
            # Pithos <= 0.3.17, replaced by audio_quality
            del self.__preferences['audio_format']

        if not pacparser_imported and self.__preferences['control_proxy_pac'] != '':
            self.__preferences['control_proxy_pac'] = ''

        self.setup_fields()

    def fix_perms(self):
        """Apply new file permission rules, fixing CVE-2011-1500.
        If the file is 0644 and if "unsafe_permissions" is not True,
           chmod 0600
        If the file is world-readable (but not exactly 0644) and if
        "unsafe_permissions" is not True:
           chmod o-rw
        """
        def complain_unsafe():
            # Display this message iff permissions are unsafe, which is why
            #   we don't just check once and be done with it.
            logging.warning("Ignoring potentially unsafe permissions due to user override.")

        changed = False

        if os.path.exists(configfilename):
            # We've already written the file, get current permissions
            config_perms = stat.S_IMODE(os.stat(configfilename).st_mode)
            if config_perms == (stat.S_IRUSR | stat.S_IWUSR | stat.S_IRGRP | stat.S_IROTH):
                if self.__preferences["unsafe_permissions"]:
                    return complain_unsafe()
                # File is 0644, set to 0600
                logging.warning("Removing world- and group-readable permissions, to fix CVE-2011-1500 in older software versions. To force, set unsafe_permissions to True in pithos.ini.")
                os.chmod(configfilename, stat.S_IRUSR | stat.S_IWUSR)
                changed = True

            elif config_perms & stat.S_IROTH:
                if self.__preferences["unsafe_permissions"]:
                    return complain_unsafe()
                # File is o+r,
                logging.warning("Removing world-readable permissions, configuration should not be globally readable. To force, set unsafe_permissions to True in pithos.ini.")
                config_perms ^= stat.S_IROTH
                os.chmod(configfilename, config_perms)
                changed = True

            if config_perms & stat.S_IWOTH:
                if self.__preferences["unsafe_permissions"]:
                    return complain_unsafe()
                logging.warning("Removing world-writable permissions, configuration should not be globally writable. To force, set unsafe_permissions to True in pithos.ini.")
                config_perms ^= stat.S_IWOTH
                os.chmod(configfilename, config_perms)
                changed = True

        return changed

    def save(self):
        existed = os.path.exists(configfilename)
        with open(configfilename, 'w') as f:
            if not existed:
                # make the file owner-readable and writable only
                os.fchmod(f.fileno(), (stat.S_IRUSR | stat.S_IWUSR))

            for key in self.__preferences:
                f.write('%s=%s\n' % (key, self.__preferences[key]))

    def setup_fields(self):
        self.builder.get_object('prefs_username').set_text(self.__preferences["username"])
        self.builder.get_object('prefs_password').set_text(self.__preferences["password"])
        self.builder.get_object('checkbutton_pandora_one').set_active(self.__preferences["pandora_one"])
        self.builder.get_object('prefs_proxy').set_text(self.__preferences["proxy"])
        self.builder.get_object('prefs_control_proxy').set_text(self.__preferences["control_proxy"])
        self.builder.get_object('prefs_control_proxy_pac').set_text(self.__preferences["control_proxy_pac"])
        if not pacparser_imported:
            self.builder.get_object('prefs_control_proxy_pac').set_sensitive(False)
            self.builder.get_object('prefs_control_proxy_pac').set_tooltip_text("Please install python-pacparser")

        audio_player_combo = self.builder.get_object('prefs_audio_player')
        for row in audio_player_combo.get_model():
            if row[0] == self.__preferences["audio_player"]:
                audio_player_combo.set_active_iter(row.iter)
                break

        audio_quality_combo = self.builder.get_object('prefs_audio_quality')
        for row in audio_quality_combo.get_model():
            if row[0] == self.__preferences["audio_quality"]:
                audio_quality_combo.set_active_iter(row.iter)
                break

        for row in self.listbox.get_children():
            row.switch.set_active(self.__preferences[row.plugin.preference])

    def ok(self, widget, data=None):
        """ok - The user has elected to save the changes.
        Called before the dialog returns Gtk.RESONSE_OK from run().
        """

        self.__preferences["username"] = self.builder.get_object('prefs_username').get_text()
        self.__preferences["password"] = self.builder.get_object('prefs_password').get_text()
        self.__preferences["pandora_one"] = self.builder.get_object('checkbutton_pandora_one').get_active()
        self.__preferences["proxy"] = self.builder.get_object('prefs_proxy').get_text()
        self.__preferences["control_proxy"] = self.builder.get_object('prefs_control_proxy').get_text()
        self.__preferences["control_proxy_pac"] = self.builder.get_object('prefs_control_proxy_pac').get_text()

        audio_player = self.builder.get_object('prefs_audio_player')
        active_idx = audio_player.get_active()
        if active_idx != -1: # ignore unknown player
            self.__preferences["audio_player"] = audio_player.get_model()[active_idx][0]

        audio_quality = self.builder.get_object('prefs_audio_quality')
        active_idx = audio_quality.get_active()
        if active_idx != -1: # ignore unknown format
            self.__preferences["audio_quality"] = audio_quality.get_model()[active_idx][0]

        for row in self.listbox.get_children():
            self.__preferences[row.plugin.preference] = row.switch.get_active()

        self.save()

    def cancel(self, widget, data=None):
        """cancel - The user has elected cancel changes.
        Called before the dialog returns Gtk.ResponseType.CANCEL for run()
        """

        self.setup_fields() # restore fields to previous values
        pass


def NewPreferencesPithosDialog():
    """NewPreferencesPithosDialog - returns a fully instantiated
    PreferencesPithosDialog object. Use this function rather than
    creating a PreferencesPithosDialog instance directly.
    """

    builder = Gtk.Builder()
    builder.add_from_file(get_ui_file('preferences'))
    dialog = builder.get_object("preferences_pithos_dialog")
    dialog.finish_initializing(builder)
    return dialog

if __name__ == "__main__":
    dialog = NewPreferencesPithosDialog()
    dialog.show()
    Gtk.main()
