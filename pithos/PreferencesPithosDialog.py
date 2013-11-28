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

from gi.repository import Gtk
from gi.repository import GObject

from .pithosconfig import *
from .pandora.data import *
from .plugins.scrobble import LastFmAuth

try:
    from xdg.BaseDirectory import xdg_config_home
    config_home = xdg_config_home
except ImportError:
    if 'XDG_CONFIG_HOME' in os.environ:
        config_home = os.environ['XDG_CONFIG_HOME']
    else:
        config_home = os.path.join(os.path.expanduser('~'), '.config')

configfilename = os.path.join(config_home, 'pithos.ini')

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

        # initialize the "Audio Quality" combobox backing list
        audio_quality_combo = self.builder.get_object('prefs_audio_quality')
        fmt_store = Gtk.ListStore(GObject.TYPE_STRING, GObject.TYPE_STRING)
        for audio_quality in valid_audio_formats:
            fmt_store.append(audio_quality)
        audio_quality_combo.set_model(fmt_store)
        render_text = Gtk.CellRendererText()
        audio_quality_combo.pack_start(render_text, True)
        audio_quality_combo.add_attribute(render_text, "text", 1)

        self.__load_preferences()


    def get_preferences(self):
        """get_preferences  - returns a dictionary object that contains
        preferences for pithos.
        """
        return self.__preferences

    def __load_preferences(self):
        #default preferences that will be overwritten if some are saved
        self.__preferences = {
            "username":'',
            "password":'',
            "notify":True,
            "last_station_id":None,
            "proxy":'',
            "control_proxy":'',
            "show_icon": False,
            "lastfm_key": False,
            "enable_mediakeys":True,
            "enable_screensaverpause":False,
            "volume": 1.0,
            # If set, allow insecure permissions. Implements CVE-2011-1500
            "unsafe_permissions": False,
            "audio_quality": default_audio_quality,
            "pandora_one": False,
            "force_client": None,
        }

        try:
            f = open(configfilename)
        except IOError:
            f = []

        for line in f:
            sep = line.find('=')
            key = line[:sep]
            val = line[sep+1:].strip()
            if val == 'None': val=None
            elif val == 'False': val=False
            elif val == 'True': val=True
            self.__preferences[key]=val

        if 'audio_format' in self.__preferences:
            # Pithos <= 0.3.17, replaced by audio_quality
            del self.__preferences['audio_format']

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
        f = open(configfilename, 'w')

        if not existed:
            # make the file owner-readable and writable only
            os.fchmod(f.fileno(), (stat.S_IRUSR | stat.S_IWUSR))

        for key in self.__preferences:
            f.write('%s=%s\n'%(key, self.__preferences[key]))
        f.close()

    def setup_fields(self):
        self.builder.get_object('prefs_username').set_text(self.__preferences["username"])
        self.builder.get_object('prefs_password').set_text(self.__preferences["password"])
        self.builder.get_object('checkbutton_pandora_one').set_active(self.__preferences["pandora_one"])
        self.builder.get_object('prefs_proxy').set_text(self.__preferences["proxy"])
        self.builder.get_object('prefs_control_proxy').set_text(self.__preferences["control_proxy"])

        audio_quality_combo = self.builder.get_object('prefs_audio_quality')
        for row in audio_quality_combo.get_model():
            if row[0] == self.__preferences["audio_quality"]:
                audio_quality_combo.set_active_iter(row.iter)
                break

        self.builder.get_object('checkbutton_notify').set_active(self.__preferences["notify"])
        self.builder.get_object('checkbutton_screensaverpause').set_active(self.__preferences["enable_screensaverpause"])
        self.builder.get_object('checkbutton_icon').set_active(self.__preferences["show_icon"])

        self.lastfm_auth = LastFmAuth(self.__preferences, "lastfm_key", self.builder.get_object('lastfm_btn'))

    def ok(self, widget, data=None):
        """ok - The user has elected to save the changes.
        Called before the dialog returns Gtk.RESONSE_OK from run().
        """

        self.__preferences["username"] = self.builder.get_object('prefs_username').get_text()
        self.__preferences["password"] = self.builder.get_object('prefs_password').get_text()
        self.__preferences["pandora_one"] = self.builder.get_object('checkbutton_pandora_one').get_active()
        self.__preferences["proxy"] = self.builder.get_object('prefs_proxy').get_text()
        self.__preferences["control_proxy"] = self.builder.get_object('prefs_control_proxy').get_text()
        self.__preferences["notify"] = self.builder.get_object('checkbutton_notify').get_active()
        self.__preferences["enable_screensaverpause"] = self.builder.get_object('checkbutton_screensaverpause').get_active()
        self.__preferences["show_icon"] = self.builder.get_object('checkbutton_icon').get_active()

        audio_quality = self.builder.get_object('prefs_audio_quality')
        active_idx = audio_quality.get_active()
        if active_idx != -1: # ignore unknown format
            self.__preferences["audio_quality"] = audio_quality.get_model()[active_idx][0]

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

    #look for the ui file that describes the ui
    ui_filename = os.path.join(getdatapath(), 'ui', 'PreferencesPithosDialog.ui')
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = Gtk.Builder()
    builder.add_from_file(ui_filename)
    dialog = builder.get_object("preferences_pithos_dialog")
    dialog.finish_initializing(builder)
    return dialog

if __name__ == "__main__":
    dialog = NewPreferencesPithosDialog()
    dialog.show()
    Gtk.main()

