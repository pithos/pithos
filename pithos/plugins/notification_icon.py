# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
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

import os
from gi.repository import Gtk
from pithos.pithosconfig import get_data_file
from pithos.plugin import PithosPlugin

# Use appindicator if on Unity and installed
try:
    if os.environ['XDG_CURRENT_DESKTOP'] == 'Unity':
        from gi.repository import AppIndicator3 as AppIndicator
        indicator_capable = True
    else:
        indicator_capable = False
except:
    indicator_capable = False

class PithosNotificationIcon(PithosPlugin):    
    preference = 'show_icon'
            
    def on_prepare(self):
        if indicator_capable:
            self.ind = AppIndicator.Indicator.new_with_path("pithos-tray-icon", \
                                  "pithos-tray-icon", \
                                   AppIndicator.IndicatorCategory.APPLICATION_STATUS, \
                                   get_data_file('media'))
    
    def on_enable(self):
        self.delete_callback_handle = self.window.connect("delete-event", self.toggle_visible)
        self.state_callback_handle = self.window.connect("play-state-changed", self.play_state_changed)
        self.song_callback_handle = self.window.connect("song-changed", self.song_changed)
        
        if indicator_capable:
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        else:
            icon_info = Gtk.IconTheme.lookup_icon (Gtk.IconTheme.get_default(), 'pithos-tray-icon', 48, 0)
            if icon_info and Gtk.IconInfo.get_filename (icon_info):
                filename = Gtk.IconInfo.get_filename (icon_info)
            else:
                filename = get_data_file('media', 'pithos-tray-icon.png')

            self.statusicon = Gtk.StatusIcon.new ()
            self.statusicon.set_from_file (filename)
            self.statusicon.connect('activate', self.toggle_visible)
        
        self.build_context_menu()

    def scroll(self, steps):
        if indicator_capable:
            direction = steps.value_nick
        else:
            direction = steps.direction.value_nick

        if direction == 'down':
            self.window.adjust_volume(-1)
        elif direction == 'up':
            self.window.adjust_volume(+1)

    def build_context_menu(self):
        menu = Gtk.Menu()
        
        def button(text, action, checked=False):
            if checked:
                item = Gtk.CheckMenuItem(text)
                item.set_active(True)
            else:
                item = Gtk.MenuItem(text)
            item.connect('activate', action) 
            item.show()
            menu.append(item)
            return item
        
        if indicator_capable:
            # We have to add another entry for show / hide Pithos window
            self.visible_check = button("Show Pithos", self._toggle_visible, True)
        
        self.playpausebtn = button("Pause", self.window.playpause)
        button("Skip",  self.window.next_song)
        button("Love",  (lambda *i: self.window.love_song()))
        button("Ban",   (lambda *i: self.window.ban_song()))
        button("Tired", (lambda *i: self.window.tired_song()))
        button("Quit",  self.window.quit)

        # connect our new menu to the statusicon or the appindicator
        if indicator_capable:
            self.ind.set_menu(menu)
            # Disabled because of https://bugs.launchpad.net/variety/+bug/1071598
            #self.ind.connect('scroll-event', lambda _x, _y, steps: self.scroll(steps))
        else:
            self.statusicon.connect('popup-menu', self.context_menu, menu)
            self.statusicon.connect('scroll-event', lambda _, steps: self.scroll(steps))

        self.menu = menu


    def play_state_changed(self, window, playing):
        """ play or pause and rotate the text """
        
        button = self.playpausebtn
        if not playing:
            button.set_label("Play")
        else:
            button.set_label("Pause")
            
        if indicator_capable: # menu needs to be reset to get updated icon
            self.ind.set_menu(self.menu)

    def song_changed(self, window, song):
        if not indicator_capable:
            self.statusicon.set_tooltip_text("%s by %s"%(song.title, song.artist))
        
    def _toggle_visible(self, *args):
        self.window.set_visible(not self.window.get_visible())

        if self.window.get_visible(): # Ensure it's on top
            self.window.bring_to_top()
        
    def toggle_visible(self, *args):
        if hasattr(self, 'visible_check'):
            self.visible_check.set_active(not self.window.get_visible())
        else:
            self._toggle_visible()
        
        return True

    def context_menu(self, widget, button, time, data=None): 
       if button == 3: 
           if data: 
               data.show_all() 
               data.popup(None, None, None, None, 3, time)
    
    def on_disable(self):
        if indicator_capable:
            self.ind.set_status(AppIndicator.IndicatorStatus.PASSIVE)
        else:
            self.statusicon.set_visible(False)
            
        self.window.disconnect(self.delete_callback_handle)
        self.window.disconnect(self.state_callback_handle)
        self.window.disconnect(self.song_callback_handle)
        
        # Pithos window needs to be reconnected to on_destro()
        self.window.connect('delete-event',self.window.on_destroy)

