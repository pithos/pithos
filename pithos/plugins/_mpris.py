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
from xml.etree import ElementTree

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
        self.window.connect("song-art-changed", self.artchange_handler)
        self.window.connect("song-rating-changed", self.ratingchange_handler)
        self.window.connect("play-state-changed", self.playstate_handler)
        
    def playstate_handler(self, window, state):
        if state:
            self.signal_playing()
        else:
            self.signal_paused()
        
    def songchange_handler(self, window, song):
        self.song_changed([song.artist], song.album, song.title, song.artUrl,
                          song.rating)
        self.signal_playing()

    def artchange_handler(self, window, song):
        if song is self.window.current_song:
            self.__metadata['mpris:artUrl'] = song.artUrl or ''
            self.PropertiesChanged('org.mpris.MediaPlayer2.Player',
                        dbus.Dictionary({'Metadata': self.__metadata},
                        'sv',
                        variant_level=1),
                        [])

    def ratingchange_handler(self, window, song):
        """Handle rating changes and update MPRIS metadata accordingly"""
        # Pithos fires rating-changed signals for all songs, not just the
        # currently playing one, so we need ignore signals for irrelevant songs.
        if song is not self.window.current_song:
            return

        self.__metadata["pithos:rating"] = song.rating or ""
        self.PropertiesChanged("org.mpris.MediaPlayer2.Player",
                               dbus.Dictionary({"Metadata": self.__metadata},
                                               "sv",
                                               variant_level=1),
                               [])

    def song_changed(self, artists=None, album=None, title=None, artUrl='',
                     rating=None):
        """song_changed - sets the info for the current song.

        This method is not typically overriden. It should be called
        by implementations of this class when the player has changed
        songs.
            
        named arguments:
            artists - a list of strings representing the artists"
            album - a string for the name of the album
            title - a string for the title of the song

        """
        
        self.__metadata = dbus.Dictionary({
            "xesam:title": title or "Title Unknown",
            "xesam:artist": artists or ["Artist Unknown"],
            "xesam:album": album or "Album Unknown",
            "mpris:artUrl": artUrl or "",
            "pithos:rating": rating or "",
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
        return self.__metadata

    def _get_volume(self):
        return self.window.player.get_property("volume")

    def _set_volume(self, new_volume):
        self.window.player.set_property('volume', new_volume)

    def _get_position(self):
        return self.window.query_position() / 1000

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
            if property_name == 'Volume':
                self._set_volume(new_value)
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
        """Play previous song, not implemented"""

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
        """Stop is only used internally, mapping to pause instead"""
        self.window.pause()

    def signal_playing(self):
        """signal_playing - Tell the Sound Menu that the player has
        started playing.
        """
       
        self.__playback_status = "Playing"
        d = dbus.Dictionary({"PlaybackStatus":self.__playback_status, "Metadata":self.__metadata},
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

    # python-dbus does not have our properties for introspection, so we must manually add them
    @dbus.service.method(dbus.INTROSPECTABLE_IFACE, in_signature="", out_signature="s",
                         path_keyword="object_path", connection_keyword="connection")
    def Introspect(self, object_path, connection):
        data = dbus.service.Object.Introspect(self, object_path, connection)
        xml = ElementTree.fromstring(data)

        for iface in xml.findall("interface"):
            name = iface.attrib["name"]
            if name.startswith(self.MEDIA_PLAYER2_IFACE):
                for item, value in self.GetAll(name).items():
                    prop = {"name": item, "access": "read"}
                    if item == "Volume": # Hardcode the only writable property..
                        prop["access"] = "readwrite"

                    # Ugly mapping of types to signatures, is there a helper for this?
                    # KEEP IN SYNC!
                    if isinstance(value, str):
                        prop["type"] = "s"
                    elif isinstance(value, bool):
                        prop["type"] = "b"
                    elif isinstance(value, float):
                        prop["type"] = "d"
                    elif isinstance(value, int):
                        prop["type"] = "x"
                    elif isinstance(value, list):
                        prop["type"] = "as"
                    elif isinstance(value, dict):
                        prop["type"] = "a{sv}"
                    iface.append(ElementTree.Element("property", prop))
        return ElementTree.tostring(xml, encoding="UTF-8")
