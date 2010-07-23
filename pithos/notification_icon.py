#!/usr/bin/python
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

import gtk
import pithosconfig

# Check if appindicator is available on the system
try:
    import appindicator
    indicator_capable = True
except:
    indicator_capable = False

class PithosNotificationIcon:
    class Borg:
        """Application indicator can be instantiated only
           once. The plugin api, when toggling the activation
           state of a plugin, instantiates different instances
           of the plugin class. Therefore, we need to keep
           a reference to the indicator object. This class does that."""
        __shared_state = {}
        def __init__(self):
            self.__dict__ = self.__shared_state
            if not hasattr(self, "indicator"):
                self.indicator = appindicator.Indicator("pithos", \
                                  "pithos-mono", \
                                   appindicator.CATEGORY_APPLICATION_STATUS, \
                                   pithosconfig.get_data_file('media'))
                self.indicator.set_status(appindicator.STATUS_ACTIVE)

        def get_indicator(self):
            return self.indicator    
    
    def __init__(self, window):
        
        self.window = window
        
        self.delete_callback_handle = self.window.connect("delete-event", self.window.hide_on_delete)
        self.state_callback_handle = self.window.connect("play-state-changed", self.play_state_changed)
        self.song_callback_handle = self.window.connect("song-changed", self.song_changed)
        
        if indicator_capable:
            self.ind = self.Borg().get_indicator()        
        else:
            self.statusicon = gtk.status_icon_new_from_file(pithosconfig.get_data_file('media', 'icon.png'))
            self.statusicon.connect('activate', self.toggle_visible)
        
        self.build_context_menu()
       
    def build_context_menu(self):
        menu = gtk.Menu()
        
        def button(text, action, icon=None):
            if icon:
                item = gtk.ImageMenuItem(text)
                item.set_image(gtk.image_new_from_stock(icon, gtk.ICON_SIZE_MENU))
            else:
                item = gtk.MenuItem(text)
            item.connect('activate', action) 
            item.show()
            menu.append(item)
            return item
        
        if indicator_capable:
            # We have to add another entry for show / hide Pithos window
            button("Show/Hide Pithos", self.toggle_visible)
        
        self.playpausebtn = button("Pause", self.window.playpause, gtk.STOCK_MEDIA_PAUSE)
        button("Skip",  self.window.next_song,                     gtk.STOCK_MEDIA_NEXT)
        button("Love",  (lambda *i: self.window.love_song()),      gtk.STOCK_ABOUT)
        button("Ban",   (lambda *i: self.window.ban_song()),       gtk.STOCK_CANCEL)
        button("Tired", (lambda *i: self.window.tired_song()),     gtk.STOCK_JUMP_TO)
        button("Quit",  self.window.quit,                          gtk.STOCK_QUIT )

        # connect our new menu to the statusicon or the appindicator
        if indicator_capable:
            self.ind.set_menu(menu)
        else:
            self.statusicon.connect('popup-menu', self.context_menu, menu)
            
        self.menu = menu


    def play_state_changed(self, window, playing):
        """ play or pause and rotate the text """
        
        button = self.playpausebtn
        if not playing:
            button.set_label("Play")
            button.set_image(gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU))

        else:
            button.set_label("Pause")
            button.set_image(gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE, gtk.ICON_SIZE_MENU))
            
        if indicator_capable: # menu needs to be reset to get updated icon
            self.ind.set_menu(self.menu)

    def song_changed(self, window, song):
        if not indicator_capable:
            self.statusicon.set_tooltip("%s by %s"%(song.title, song.artist))
        
    def toggle_visible(self, status):
        """ hide/unhide the window 
        @param status: the statusicon

        """

        if self.window.is_active():
            self.window.hide()
        else:
            self.window.show_all()
            self.window.present()

    def context_menu(self, widget, button, time, data=None): 
       if button == 3: 
           if data: 
               data.show_all() 
               data.popup(None, None, None, 3, time)
    
    def remove(self):
        if indicator_capable:
            self.ind.set_status(appindicator.STATUS_PASSIVE)
        else:
            self.statusicon.set_visible(False)
            
        self.window.disconnect(self.delete_callback_handle)
        self.window.disconnect(self.state_callback_handle)
        self.window.disconnect(self.song_callback_handle)
        
        # Pithos window needs to be reconnected to on_destro()
        self.window.connect('delete-event',self.window.on_destroy)

