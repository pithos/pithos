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
import time

try:
    from gi.repository import Gdk    
    from gi.repository import Gtk
    from gi.repository import Gio

    from gi.repository import Dee
    _m = dir(Dee.SequenceModel)

    from gi.repository import Unity
    UNITY = True
except ImportError:
    UNITY = False

if UNITY:
    try:
        from gi.repository import Dbusmenu
        UNITY_QUICKLIST = True
    except ImportError:
        UNITY_QUICKLIST = False 


if not UNITY:
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


        def load_stations(self):
            stations = self.window.pandora.stations
            s = stations[0]
            #print s.id, s.idToken, s.isCreator, s.isQuickMix, s.name

            for station in stations:
                playlist = Unity.Playlist.new(station.id)
                playlist.props.name = station.name
                playlist.props.icon = Gio.ThemedIcon.new("media-playlist-shuffle" if station.isQuickMix else "stock_smart_playlist")
                self.player.add_playlist(playlist)
            
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
            return self.window.player.query_position(self.window.time_format, None)[0] / 1000

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
            """Play previous song"""

            self.window.prev_song()

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

        def station_changed(*args):
            pass

else:
    # Use Unity Sound Menu API, with playlists/stations support
    class PithosMprisService(object):
        def __init__(self, window):
            self.window = window
            self.stations = []

            self.window.connect("song-changed", self.songchange_handler)
            self.window.connect("play-state-changed", self.playstate_handler)

            self.sound_menu_settings = Gio.Settings.new('com.canonical.indicator.sound')
            self.blacklisted_players = self.sound_menu_settings.get_strv('blacklisted-media-players')
            if 'pithos' in self.blacklisted_players:
                self.sound_menu_settings.set_strv('blacklisted-media-players', [p for p in self.blacklisted_players if p != 'pithos'])

            self.player = Unity.MusicPlayer.new('pithos.desktop')
            self.player.props.title = 'Pithos'

            self.player.connect('play_pause', self.play_pause)
            self.player.connect('previous', self.previous)
            self.player.connect('next', self.next)

            self.player.export()

            if UNITY_QUICKLIST:
                self.launcher = Unity.LauncherEntry.get_for_desktop_id("pithos.desktop")

            self.song_changed()

        def build_quicklist(self):
            self.quicklist = Dbusmenu.Menuitem.new()

            self.ql_playpause = Dbusmenu.Menuitem.new()
            self.ql_playpause.property_set(Dbusmenu.MENUITEM_PROP_LABEL, "Play")
            self.ql_playpause.property_set(Dbusmenu.MENUITEM_PROP_TOGGLE_TYPE, Dbusmenu.MENUITEM_TOGGLE_CHECK)
            self.ql_playpause.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, Dbusmenu.MENUITEM_TOGGLE_STATE_UNCHECKED)
            self.ql_playpause.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
            self.ql_playpause.connect('item_activated', self.play_pause, None)
            self.quicklist.child_append(self.ql_playpause)

            self.ql_next = Dbusmenu.Menuitem.new()
            self.ql_next.property_set(Dbusmenu.MENUITEM_PROP_LABEL, "Next")
            self.ql_next.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
            self.ql_next.connect('item_activated', self.next, None)
            self.quicklist.child_append(self.ql_next)

            self.ql_previous = Dbusmenu.Menuitem.new()
            self.ql_previous.property_set(Dbusmenu.MENUITEM_PROP_LABEL, "Previous")
            self.ql_previous.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
            self.ql_previous.connect('item_activated', self.previous_ql, None)
            self.quicklist.child_append(self.ql_previous)

            self.ql_stations = {}

            if len(self.stations) > 0:
                separator = Dbusmenu.Menuitem.new()
                separator.property_set(Dbusmenu.MENUITEM_PROP_TYPE, Dbusmenu.CLIENT_TYPES_SEPARATOR)
                separator.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
                self.quicklist.child_append(separator)

                for station in self.stations:
                    radio = Dbusmenu.Menuitem.new()
                    radio.property_set(Dbusmenu.MENUITEM_PROP_LABEL, station.name)
                    radio.property_set(Dbusmenu.MENUITEM_PROP_TOGGLE_TYPE, Dbusmenu.MENUITEM_TOGGLE_RADIO)
                    radio.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, Dbusmenu.MENUITEM_TOGGLE_STATE_UNCHECKED)
                    radio.property_set_bool(Dbusmenu.MENUITEM_PROP_VISIBLE, True)
                    radio.connect(Dbusmenu.MENUITEM_SIGNAL_ITEM_ACTIVATED, self.change_station_ql, station)
                    self.quicklist.child_append(radio)

                    self.ql_stations[station.id] = radio


            self.launcher.set_property("quicklist", self.quicklist)

        def load_stations(self):
            self.stations = self.window.pandora.stations

            for station in self.stations:
                playlist = Unity.Playlist.new(station.id)
                playlist.props.name = station.name
                #playlist.props.icon = Gio.ThemedIcon.new("media-playlist-shuffle" if station.isQuickMix else "stock_smart_playlist")
                self.player.add_playlist(playlist)

            if UNITY_QUICKLIST:
                print "building"
                self.build_quicklist()
                self.station_changed(self.window.current_station)
            
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
            
            try:
                del self.data
            except:
                pass

            if artists is None:
                artists = ["Unknown artist"]
            if album is None:
                album = "Unknown album"
            if title is None:
                title = "Unknown"

       
            self.data = Unity.TrackMetadata.new()

            self.data.props.title = title
            self.data.props.artist = repr_seq(artists)
            self.data.props.album = album

            if artUrl is not None:
                self.data.props.art_location = Gio.File.new_for_uri(artUrl)

            self.player.props.current_track = self.data

        def station_changed(self, station):
            try:
                if UNITY_QUICKLIST:
                    for i in self.ql_stations:
                        if i != station.id:
                            self.ql_stations[i].property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, Dbusmenu.MENUITEM_TOGGLE_STATE_UNCHECKED)
                        else:
                            self.ql_stations[i].property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, Dbusmenu.MENUITEM_TOGGLE_STATE_CHECKED)
            except AttributeError:
                pass

        def change_station_ql(self, menu_item, obj, station):
            self.window.station_changed(station)

        def change_station_sm(self, *args):
            pass

        def previous_ql(self, *ignore):
            # Reset start time so that it immediately changes song instead of restarting it
            self.window.current_song.start_time = time.time()
            self.window.prev_song()

        def previous(self, *ignore):
            self.window.prev_song()

        def next(self, *ignore):
            self.window.next_song()

        def play_pause(self, *ignore):
            self.window.playpause()

        def signal_playing(self):
            """signal_playing - Tell the Sound Menu that the player has
            started playing.
            """
            self.player.props.playback_state = Unity.PlaybackState.PLAYING
            try:
                if UNITY_QUICKLIST:
                    self.ql_playpause.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, Dbusmenu.MENUITEM_TOGGLE_STATE_CHECKED)
            except AttributeError:
                pass

        def signal_paused(self):
            """signal_paused - Tell the Sound Menu that the player has
            been paused
            """
            self.player.props.playback_state = Unity.PlaybackState.PAUSED
            try:
                if UNITY_QUICKLIST:
                    self.ql_playpause.property_set_int(Dbusmenu.MENUITEM_PROP_TOGGLE_STATE, Dbusmenu.MENUITEM_TOGGLE_STATE_UNCHECKED)
            except AttributeError:
                pass

        def PropertiesChanged(self, interface_name, changed_properties,
                              invalidated_properties):
            pass


def repr_seq(seq):
    string = ""
    for i in seq:
        string += str(i)
        string += ", "
    string = string[:-2]
    return string