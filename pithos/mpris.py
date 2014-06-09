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

class PithosMprisService(dbus.service.Object):
    MEDIA_PLAYER2_IFACE = 'org.mpris.MediaPlayer2'
    MEDIA_PLAYER2_PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'

    def __init__(self, window):
        """
        Creates a PithosSoundMenu object.

        Requires a dbus loop to be created before the gtk mainloop,
        typically by calling DBusGMainLoop(set_as_default=True).
        """

        bus_str = """org.mpris.MediaPlayer2.pithos"""
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

    # Properties
    def _get_playback_status(self):
        """Current status "Playing", "Paused", or "Stopped"."""
        if not self.window.current_song:
            return "Stopped"
        if self.window.playing:
            return "Playing"
        else:
            return "Paused"

    def _get_metadata(self):
        """The info for the current song."""
        return self.__meta_data

    def _get_volume(self):
        return self.window.player.get_property("volume")

    def _get_position(self):
        return self.window.player.query_position(self.window.time_format)[0] / 1000

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ss', out_signature='v')
    def Get(self, interface_name, property_name):
        try:
            return self.GetAll(interface_name)[property_name]
        except KeyError:
            raise dbus.exceptions.DBusException(
                interface_name, 'Property %s was not found.' %property_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='ssv')
    def Set(self, interface_name, property_name, new_value):
        if interface_name == self.MEDIA_PLAYER2_IFACE:
            pass
        elif interface_name == self.MEDIA_PLAYER2_PLAYER_IFACE:
            pass # TODO: volume
        else:
            raise dbus.exceptions.DBusException(
                'org.mpris.MediaPlayer2.pithos',
                'This object does not implement the %s interface'
                % interface_name)

    @dbus.service.method(dbus.PROPERTIES_IFACE, in_signature='s', out_signature='a{sv}')
    def GetAll(self, interface_name):
        if interface_name == self.MEDIA_PLAYER2_IFACE:
            return {
                'CanQuit': True,
                'CanRaise': True,
                'HasTrackList': False,
                'Identity': 'Pithos',
                'DesktopEntry': 'pithos',
                'SupportedUriSchemes': [''],
                'SupportedMimeTypes': [''],
            }
        elif interface_name == self.MEDIA_PLAYER2_PLAYER_IFACE:
            return {
                'PlaybackStatus': self._get_playback_status(),
                'LoopStatus': "None",
                'Rate': dbus.Double(1.0),
                'Shuffle': False,
                'Metadata': dbus.Dictionary(self._get_metadata(), signature='sv'),
                'Volume': dbus.Double(self._get_volume()),
                'Position': dbus.Int64(self._get_position()),
                'MinimumRate': dbus.Double(1.0),
                'MaximumRate': dbus.Double(1.0),
                'CanGoNext': self.window.waiting_for_playlist is not True,
                'CanGoPrevious': False,
                'CanPlay': self.window.current_song is not None,
                'CanPause': self.window.current_song is not None,
                'CanSeek': False,
                'CanControl': True,
            }
        else:
            raise dbus.exceptions.DBusException(
                'org.mpris.MediaPlayer2.pithos',
                'This object does not implement the %s interface'
                % interface_name)

    @dbus.service.method(MEDIA_PLAYER2_IFACE)
    def Raise(self):
        """Bring the media player to the front when selected by the sound menu"""

        self.window.bring_to_top()

    @dbus.service.method(MEDIA_PLAYER2_IFACE)
    def Quit(self):
        """Exit the player"""

        self.window.quit()

    @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Previous(self):
        """Play prvious song, not implemented"""

        pass

    @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Next(self):
        """Play next song"""

        self.window.next_song()

    @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE)
    def PlayPause(self):
        self.window.playpause()

    @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Play(self):
        self.window.play()

    @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Pause(self):
        self.window.pause()

    @dbus.service.method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Stop(self):
        self.window.stop()

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
