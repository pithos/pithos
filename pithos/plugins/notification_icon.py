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

import gi
from gi.repository import Gtk
from pithos.plugin import PithosPlugin

# Use appindicator if installed
try:
    gi.require_version('AppIndicator3', '0.1')
    from gi.repository import AppIndicator3 as AppIndicator
    indicator_capable = True
except:
    indicator_capable = False

class PithosNotificationIcon(PithosPlugin):    
    preference = 'show_icon'
    description = 'Adds pithos icon to system tray'
            
    def on_prepare(self):
        if indicator_capable:
            self.ind = AppIndicator.Indicator.new("pithos-tray-icon", \
                                  "pithos-tray-icon", \
                                   AppIndicator.IndicatorCategory.APPLICATION_STATUS)

    def on_enable(self):
        self.delete_callback_handle = self.window.connect("delete-event", self.toggle_visible)
        self.state_callback_handle = self.window.connect("play-state-changed", self.play_state_changed)
        self.song_callback_handle = self.window.connect("song-changed", self.song_changed)
        
        if indicator_capable:
            self.ind.set_status(AppIndicator.IndicatorStatus.ACTIVE)
        else:
            self.statusicon = Gtk.StatusIcon.new_from_icon_name('pithos-tray-icon')
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

            # On middle-click
            self.ind.set_secondary_activate_target(self.visible_check)
        
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

