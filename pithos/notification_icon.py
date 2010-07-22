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
                                   pithosconfig.getmediapath())
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
			self.statusicon.connect('activate', self.statusicon_clicked )
		
		self.build_context_menu()
	   
	def build_context_menu(self):
		""" build context menu for the right click menu on the status icon 
			of for the appindicator """

		def icon(image):
			""" create an icon from a stock image """
			return gtk.image_new_from_stock(image, gtk.ICON_SIZE_MENU)

		buttons = ( # text	 click action		 image icon [optional]
				   ("Pause", self.window.playpause,			icon(gtk.STOCK_MEDIA_PAUSE)),
				   ("Skip",  self.window.next_song,			icon(gtk.STOCK_MEDIA_NEXT)),
				   ("Love",  self.window.on_menuitem_love,  icon(gtk.STOCK_ABOUT)),
				   ("Ban",   self.window.on_menuitem_ban,   icon(gtk.STOCK_CANCEL)),
				   ("Tired", self.window.on_menuitem_tired, icon(gtk.STOCK_JUMP_TO)),
				   (gtk.STOCK_QUIT, self.window.quit )
				 )   

		# build out the menu
		menu = gtk.Menu()
		self.buttons = {}
		for button in buttons:
			item = gtk.ImageMenuItem(button[0])
			item.connect('activate', button[1])
			if len(button) > 2:
				item.set_image(button[2])
			item.show()
			menu.append(item)
			self.buttons[button[0]] = item

		# connect our new menu to the statusicon or the appindicator
		if indicator_capable:
			# We have to add another entry for show / hide Pithos window
			item = gtk.ImageMenuItem("Show/Hide Pithos");
			item.connect('activate',self.statusicon_clicked); # since self.statusicon_clicked shows and hides
			item.show()
			menu.append(item)
			self.buttons["Show/Hide Pithos"] = item
			self.ind.set_menu(menu)
		else:
			self.statusicon.connect('popup-menu', self.context_menu, menu)


	def play_state_changed(self, window, playing):
		""" play or pause and rotate the text """
		
        button = self.buttons['Pause']
		if not playing:
			button.set_label("Play")
			button.set_image(gtk.image_new_from_stock(gtk.STOCK_MEDIA_PLAY, gtk.ICON_SIZE_MENU))

		else:
			button.set_label("Pause")
			button.set_image(gtk.image_new_from_stock(gtk.STOCK_MEDIA_PAUSE, gtk.ICON_SIZE_MENU))

    def song_changed(self, window, song):
		if not indicator_capable:
			self.statusicon.set_tooltip("%s by %s"%(song.title, song.artist))
        
	def statusicon_clicked(self, status):
		""" hide/unhide the window 
		@param status: the statusicon

		"""

		if self.window.is_active():
			self.window.hide()
		else:
			self.window.show_all()

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

