# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2011 Rick Spencer <rick.spencer@canonical.com>
# Copyright (C) 2011-2012 Kevin Mehall <km@kevinmehall.net>
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

import dbus
import dbus.service

DESKTOP_NAME = 'pithos'

class PithosSoundMenu(dbus.service.Object):

    def __init__(self, window):
        """
        Creates a PithosSoundMenu object.

        Requires a dbus loop to be created before the gtk mainloop,
        typically by calling DBusGMainLoop(set_as_default=True).
        """

        bus_str = """org.mpris.MediaPlayer2.%s""" % DESKTOP_NAME
        bus_name = dbus.service.BusName(bus_str, bus=dbus.SessionBus())
        dbus.service.Object.__init__(self, bus_name, "/org/mpris/MediaPlayer2")
        self.window = window

        self.song_changed()
        
        self.window.connect("song-changed", self.songchange_handler)
        self.window.connect("play-state-changed", self.playstate_handler)
        
    def playstate_handler(self, window, state):
        if state:
        	self.signal_playing()
        else:
        	self.signal_paused()
        
    def songchange_handler(self, window, song):
        self.song_changed([song.artist], song.album, song.title, song.artRadio)
        self.signal_playing()

    def song_changed(self, artists = None, album = None, title = None, artUrl=''):
        """song_changed - sets the info for the current song.

        This method is not typically overriden. It should be called
        by implementations of this class when the player has changed
        songs.
            
        named arguments:
            artists - a list of strings representing the artists"
            album - a string for the name of the album
            title - a string for the title of the song

        """
        
        if artists is None:
            artists = ["Artist Unknown"]
        if album is None:
            album = "Album Unknown"
        if title is None:
            title = "Title Unknown"
        if artUrl is None:
            artUrl = ''
   
        self.__meta_data = dbus.Dictionary({"xesam:album":album,
                            "xesam:title":title,
                            "xesam:artist":artists,
                            "mpris:artUrl":artUrl,
                            }, "sv", variant_level=1)


    @dbus.service.method('org.mpris.MediaPlayer2')
    def Raise(self):
        """Bring the media player to the front when selected by the sound menu"""

        self.window.bring_to_top()

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface, prop):
        """Get

        A function necessary to implement dbus properties.

        This function is only called by the Sound Menu, and should not
        be overriden or called directly.

        """

        my_prop = self.__getattribute__(prop)
        return my_prop

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ssv')
    def Set(self, interface, prop, value):
        """Set

        A function necessary to implement dbus properties.

        This function is only called by the Sound Menu, and should not
        be overriden or called directly.

        """
        my_prop = self.__getattribute__(prop)
        my_prop = value

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface):
        """GetAll

        A function necessary to implement dbus properties.

        This function is only called by the Sound Menu, and should not
        be overriden or called directly.

        """

        return [DesktopEntry, PlaybackStatus, MetaData]

    @property
    def DesktopEntry(self):
        """DesktopEntry

        The name of the desktop file.

        This propert is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        return DESKTOP_NAME

    @property
    def PlaybackStatus(self):
        """PlaybackStatus

        Current status "Playing", "Paused", or "Stopped"

        This property is only used by the Sound Menu, and should not
        be overriden or called directly.

        """
        if not self.window.current_song:
            return "Stopped"
        if self.window.playing:
            return "Playing"
        else:
            return "Paused"

    @property
    def MetaData(self):
        """MetaData

        The info for the current song.

        This property is only used by the Sound Menu, and should not
        be overriden or called directly.

        """

        return self.__meta_data

    @dbus.service.method('org.mpris.MediaPlayer2.Player')
    def Next(self):
        """Next

        This function is called when the user has clicked
        the next button in the Sound Indicator.

        """

        self.window.next_song()


    @dbus.service.method('org.mpris.MediaPlayer2.Player')
    def Previous(self):
        """Previous

        This function is called when the user has clicked
        the previous button in the Sound Indicator.

        """

        pass

    @dbus.service.method('org.mpris.MediaPlayer2.Player')
    def PlayPause(self):
        
        self.window.playpause()


    def signal_playing(self):
        """signal_playing - Tell the Sound Menu that the player has
        started playing.
        """
       
        self.__playback_status = "Playing"
        d = dbus.Dictionary({"PlaybackStatus":self.__playback_status, "Metadata":self.__meta_data},
                                    "sv",variant_level=1)
        self.PropertiesChanged("org.mpris.MediaPlayer2.Player",d,[])

    def signal_paused(self):
        """signal_paused - Tell the Sound Menu that the player has
        been paused
        """

        self.__playback_status = "Paused"
        d = dbus.Dictionary({"PlaybackStatus":self.__playback_status},
                                    "sv",variant_level=1)
        self.PropertiesChanged("org.mpris.MediaPlayer2.Player",d,[])

    @dbus.service.signal(dbus.PROPERTIES_IFACE, signature='sa{sv}as')
    def PropertiesChanged(self, interface_name, changed_properties,
                          invalidated_properties):
        """PropertiesChanged

        A function necessary to implement dbus properties.

        Typically, this function is not overriden or called directly.

        """

        pass


