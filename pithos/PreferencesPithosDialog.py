# -*- coding: utf-8 -*-
### BEGIN LICENSE
# This file is in the public domain
### END LICENSE

import sys
import os
import gtk

from pithos.pithosconfig import getdatapath

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
            "username":None,
            "password":None,
            "default_station_id":None,
        }
        
        try:
        	f = open(configfilename)
        except IOError:
        	return
        
        for line in f:
            sep = line.find('=')
            key = line[:sep]
            val = line[sep+1:].strip()
            self.__preferences[key]=val
        
    def __save_preferences(self):
        f = open(configfilename, 'w')
        for key in self.__preferences:
        	f.write('%s=%s\n'%(key, self.__preferences[key]))
        f.close()

    def ok(self, widget, data=None):
        """ok - The user has elected to save the changes.
        Called before the dialog returns gtk.RESONSE_OK from run().
        """
        
        self.__preferences["username"] = self.builder.get_object('prefs_username').get_text()
        self.__preferences["password"] = self.builder.get_object('prefs_password').get_text()
        
        
        self.__save_preferences()

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

