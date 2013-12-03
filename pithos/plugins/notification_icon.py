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

import gtk
from pithos.pithosconfig import get_data_file
from pithos.plugin import PithosPlugin

# Check if appindicator is available on the system
try:
    import appindicator
    indicator_capable = True
except:
    indicator_capable = False

class PithosNotificationIcon(PithosPlugin):    
    preference = 'show_icon'
            
    def on_prepare(self):
        if indicator_capable:
            self.ind = appindicator.Indicator("pithos", \
                                  "pithos-mono", \
                                   appindicator.CATEGORY_APPLICATION_STATUS, \
                                   get_data_file('media'))
    
    def on_enable(self):
        self.visible = True
        self.delete_callback_handle = self.window.connect("delete-event", self.toggle_visible)
        self.state_callback_handle = self.window.connect("play-state-changed", self.play_state_changed)
        self.song_callback_handle = self.window.connect("song-changed", self.song_changed)
        
        if indicator_capable:
            self.ind.set_status(appindicator.STATUS_ACTIVE)      
        else:
            self.statusicon = gtk.status_icon_new_from_file(get_data_file('media', 'icon.png'))
            self.statusicon.connect('activate', self.toggle_visible)
        
        self.build_context_menu()

    def scroll(self, steps):
        if indicator_capable:
            down = steps
        else:
            down = steps.direction.value_nick == 'down'

        self.window.raise_volume(down=down)

    def build_context_menu(self):
        menu = gtk.Menu()
        
        def button(text, action, icon=None):
            if icon == 'check':
                item = gtk.CheckMenuItem(text)
                item.set_active(True)
            elif icon:
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
            self.visible_check = button("Show Pithos", self._toggle_visible, 'check')
        
        self.playpausebtn = button("Pause", self.window.playpause, gtk.STOCK_MEDIA_PAUSE)
        button("Skip",  self.window.next_song,                     gtk.STOCK_MEDIA_NEXT)
        button("Love",  (lambda *i: self.window.love_song()),      gtk.STOCK_ABOUT)
        button("Ban",   (lambda *i: self.window.ban_song()),       gtk.STOCK_CANCEL)
        button("Tired", (lambda *i: self.window.tired_song()),     gtk.STOCK_JUMP_TO)
        button("Quit",  self.window.quit,                          gtk.STOCK_QUIT )

        # connect our new menu to the statusicon or the appindicator
        if indicator_capable:
            self.ind.connect('scroll-event', lambda _x, _y, steps: self.scroll(steps))
            self.ind.set_menu(menu)
        else:
            self.statusicon.connect('popup-menu', self.context_menu, menu)
            self.statusicon.connect('scroll-event', lambda _, steps: self.scroll(steps))

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
        
    def _toggle_visible(self, *args):
        if self.visible:
            self.window.hide()
        else:
            self.window.bring_to_top()
        
        self.visible = not self.visible
        
    def toggle_visible(self, *args):
        if hasattr(self, 'visible_check'):
            self.visible_check.set_active(not self.visible)
        else:
            self._toggle_visible()
        
        return True

    def context_menu(self, widget, button, time, data=None): 
       if button == 3: 
           if data: 
               data.show_all() 
               data.popup(None, None, None, 3, time)
    
    def on_disable(self):
        if indicator_capable:
            self.ind.set_status(appindicator.STATUS_PASSIVE)
        else:
            self.statusicon.set_visible(False)
            
        self.window.disconnect(self.delete_callback_handle)
        self.window.disconnect(self.state_callback_handle)
        self.window.disconnect(self.song_callback_handle)
        
        # Pithos window needs to be reconnected to on_destro()
        self.window.connect('delete-event',self.window.on_destroy)

