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
import gtk

from pithos.pithosconfig import getdatapath
from pithos.plugins.scrobble import LastFmAuth

try:
    from xdg.BaseDirectory import xdg_config_home
    config_home = xdg_config_home
except ImportError:
    config_home = os.path.dirname(__file__)
    
configfilename = os.path.join(config_home, 'pithos.ini')

class PreferencesPithosDialog(gtk.Dialog):
    __gtype_name__ = "PreferencesPithosDialog"
    prefernces = {}

    def __init__(self):
        """__init__ - This function is typically not called directly.
        Creation of a PreferencesPithosDialog requires redeading the associated ui
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

        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)
        
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
            "show_icon": False,
            "lastfm_key": False,
        }
        
        try:
            f = open(configfilename)
        except IOError:
            return
        
        for line in f:
            sep = line.find('=')
            key = line[:sep]
            val = line[sep+1:].strip()
            if val == 'None': val=None
            elif val == 'False': val=False
            elif val == 'True': val=True
            self.__preferences[key]=val
        self.setup_fields()
        
    def save(self):
        f = open(configfilename, 'w')
        for key in self.__preferences:
            f.write('%s=%s\n'%(key, self.__preferences[key]))
        f.close()
    
    def setup_fields(self):
        self.builder.get_object('prefs_username').set_text(self.__preferences["username"])
        self.builder.get_object('prefs_password').set_text(self.__preferences["password"])
        self.builder.get_object('prefs_proxy').set_text(self.__preferences["proxy"])
        self.builder.get_object('checkbutton_notify').set_active(self.__preferences["notify"])
        self.builder.get_object('checkbutton_icon').set_active(self.__preferences["show_icon"])
        
        self.lastfm_auth = LastFmAuth(self.__preferences, "lastfm_key", self.builder.get_object('lastfm_btn'))
        
    def ok(self, widget, data=None):
        """ok - The user has elected to save the changes.
        Called before the dialog returns gtk.RESONSE_OK from run().
        """
        
        self.__preferences["username"] = self.builder.get_object('prefs_username').get_text()
        self.__preferences["password"] = self.builder.get_object('prefs_password').get_text()
        self.__preferences["proxy"] = self.builder.get_object('prefs_proxy').get_text()
        self.__preferences["notify"] = self.builder.get_object('checkbutton_notify').get_active()
        self.__preferences["show_icon"] = self.builder.get_object('checkbutton_icon').get_active()
        
        self.save()

    def cancel(self, widget, data=None):
        """cancel - The user has elected cancel changes.
        Called before the dialog returns gtk.RESPONSE_CANCEL for run()
        """

        #restore any changes to self.__preferences here
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

    builder = gtk.Builder()
    builder.add_from_file(ui_filename)
    dialog = builder.get_object("preferences_pithos_dialog")
    dialog.finish_initializing(builder)
    return dialog

if __name__ == "__main__":
    dialog = NewPreferencesPithosDialog()
    dialog.show()
    gtk.main()

