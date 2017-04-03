# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2011 Rick Spencer <rick.spencer@canonical.com>
# Copyright (C) 2011-2012 Kevin Mehall <km@kevinmehall.net>
# Copyright (C) 2017 Jason Gray <jasonlevigray3@gmail.com>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.
#
# See <https://specifications.freedesktop.org/mpris-spec/latest/interfaces.html>
# for documentation.

import codecs
import logging
import math

from gi.repository import (
    GLib,
    Gio
)
from .dbus_util.DBusServiceObject import (
    DBusServiceObject,
    dbus_method,
    dbus_signal,
    dbus_property
)


class PithosMprisService(DBusServiceObject):
    MEDIA_PLAYER2_IFACE = 'org.mpris.MediaPlayer2'
    MEDIA_PLAYER2_PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'
    MEDIA_PLAYER2_PLAYLISTS_IFACE = 'org.mpris.MediaPlayer2.Playlists'
    MEDIA_PLAYER2_TRACKLIST_IFACE = 'org.mpris.MediaPlayer2.TrackList'

    # As per https://lists.freedesktop.org/archives/mpris/2012q4/000054.html
    # Secondary mpris interfaces to allow for options not allowed within the
    # confines of the mrpis spec are a completely valid use case.
    # This interface allows clients to love, ban, set tired and unrate songs.
    MEDIA_PLAYER2_RATINGS_IFACE = 'org.mpris.MediaPlayer2.ExtensionPithosRatings'

    TRACK_OBJ_PATH = '/io/github/Pithos/TrackId/'
    NO_TRACK_OBJ_PATH = '/org/mpris/MediaPlayer2/TrackList/NoTrack'
    PLAYLIST_OBJ_PATH = '/io/github/Pithos/PlaylistId/'

    NO_TRACK_METADATA = {
        'mpris:trackid': GLib.Variant('o', NO_TRACK_OBJ_PATH),
    }

    def __init__(self, window, **kwargs):
        '''Creates a PithosMprisService object.'''
        super().__init__(object_path='/org/mpris/MediaPlayer2', **kwargs)
        self.window = window

    def _reset(self):
        '''Resets state to default.'''
        self._volume = math.pow(self.window.player.props.volume, 1.0 / 3.0)
        self._metadata = self.NO_TRACK_METADATA
        self._metadata_list = [self.NO_TRACK_METADATA]
        self._tracks = [self.NO_TRACK_OBJ_PATH]
        self._playback_status = 'Stopped'
        self._playlists = [('/', '', '')]
        self._current_playlist = False, ('/', '', '')
        self._orderings = ['CreationDate']
        self._stations_dlg_handlers = []
        self._window_handlers = []
        self._stations_dlg_handlers = []
        self._volumechange_handler_id = None
        self._sort_order_handler_id = None

    def connect(self):
        '''Take ownership of the Pithos mpris Interfaces.'''
        self._reset()

        def on_name_acquired(connection, name):
            logging.info('Got bus name: {}'.format(name))
            self._update_handlers()
            self._connect_handlers()

        self.bus_id = Gio.bus_own_name_on_connection(
            self.connection,
            'org.mpris.MediaPlayer2.pithos',
            Gio.BusNameOwnerFlags.NONE,
            on_name_acquired,
            None,
        )

    def disconnect(self):
        '''Disown the Pithos mpris Interfaces.'''
        self._disconnect_handlers()
        if self.bus_id:
            Gio.bus_unown_name(self.bus_id)
            self.bus_id = 0

    def _update_handlers(self):
        '''Updates signal handlers.'''
        # Update some of our dynamic props if mpris
        # was enabled after a song has already started.
        window = self.window
        station = self.window.current_station
        song = self.window.current_song

        if station:
            self._current_playlist_handler(
                window,
                station,
            )

            self._update_playlists_handler(
                window,
                window.pandora.stations,
            )

        if song:
            songs_model = window.songs_model
            stop = len(songs_model)
            start = max(0, stop - 5)
            songs = [songs_model[i][0] for i in range(start, stop)]

            self._songs_added_handler(
                window,
                songs,
            )

            self._metadatachange_handler(
                window,
                song,
            )

            self._playstate_handler(
                window,
                window.playing,
            )

        self._sort_order_handler()

    def _connect_handlers(self):
        '''Connects signal handlers.'''
        window = self.window
        self._window_handlers = [
            window.connect(
                'metadata-changed',
                self._metadatachange_handler,
            ),

            window.connect(
                'play-state-changed',
                self._playstate_handler,
            ),

            window.connect(
                'buffering-finished',
                lambda window, position: self.Seeked(position // 1000),
            ),

            window.connect(
                'station-changed',
                self._current_playlist_handler,
            ),

            window.connect(
                'stations-processed',
                self._update_playlists_handler,
            ),

            window.connect(
                'stations-dlg-ready',
                self._stations_dlg_ready_handler,
            ),

            window.connect(
                'songs-added',
                self._songs_added_handler,
            ),
        ]

        if window.stations_dlg:
            # If stations_dlg exsists already
            # we missed the ready signal and
            # we should connect our handlers.
            self._stations_dlg_ready_handler()

        self._volumechange_handler_id = window.player.connect(
            'notify::volume',
            self._volumechange_handler,
        )

        self._sort_order_handler_id = window.settings.connect(
            'changed::sort-stations',
            self._sort_order_handler,
        )

    def _disconnect_handlers(self):
        '''Disconnects signal handlers.'''
        window = self.window
        stations_dlg = self.window.stations_dlg

        if self._window_handlers:
            for handler in self._window_handlers:
                window.disconnect(handler)

        if stations_dlg and self._stations_dlg_handlers:
            for handler in self._stations_dlg_handlers:
                stations_dlg.disconnect(handler)

        if self._volumechange_handler_id:
            window.player.disconnect(self._volumechange_handler_id)

        if self._sort_order_handler_id:
            window.settings.disconnect(self._sort_order_handler_id)

    def _stations_dlg_ready_handler(self, *ignore):
        '''Connects stations dialog handlers.'''
        stations_dlg = self.window.stations_dlg
        self._stations_dlg_handlers = [
            stations_dlg.connect(
                'station-renamed',
                self._rename_playlist_handler,
            ),

            stations_dlg.connect(
                'station-added',
                self._add_playlist_handler,
            ),

            stations_dlg.connect(
                'station-removed',
                self._remove_playlist_handler,
            ),
        ]

    def _sort_order_handler(self, *ignore):
        '''Changes the Playlist Orderings Property based on the station popover sort order.'''
        if self.window.settings['sort-stations']:
            new_orderings = ['Alphabetical']
        else:
            new_orderings = ['CreationDate']
        if self._orderings != new_orderings:
            self._orderings = new_orderings
            self.PropertiesChanged(
                self.MEDIA_PLAYER2_PLAYLISTS_IFACE,
                {'Orderings': GLib.Variant('as', self._orderings)},
                [],
            )

    def _update_playlists_handler(self, window, stations):
        '''Updates the Playlist Interface when stations are loaded/refreshed.'''
        self._playlists = [(self.PLAYLIST_OBJ_PATH + station.id, station.name, '') for station in stations]
        self.PropertiesChanged(
            self.MEDIA_PLAYER2_PLAYLISTS_IFACE,
            {'PlaylistCount': GLib.Variant('u', len(self._playlists))},
            [],
        )

    def _remove_playlist_handler(self, window, station):
        '''Removes a deleted station from the Playlist Interface.'''
        for index, playlist in enumerate(self._playlists[:]):
            if playlist[0].strip(self.PLAYLIST_OBJ_PATH) == station.id:
                del self._playlists[index]
                self.PropertiesChanged(
                    self.MEDIA_PLAYER2_PLAYLISTS_IFACE,
                    {'PlaylistCount': GLib.Variant('u', len(self._playlists))},
                    [],
                )
                break

    def _rename_playlist_handler(self, stations_dlg, data):
        '''Renames the corresponding Playlist when a station is renamed.'''
        station_id, new_name = data
        for index, playlist in enumerate(self._playlists):
            if playlist[0].strip(self.PLAYLIST_OBJ_PATH) == station_id:
                self._playlists[index] = (self.PLAYLIST_OBJ_PATH + station_id, new_name, '')
                self.PlaylistChanged(self._playlists[index])
                break

    def _add_playlist_handler(self, window, station):
        '''Adds a new station to the Playlist Interface when it is created.'''
        new_playlist = (self.PLAYLIST_OBJ_PATH + station.id, station.name, '')
        if new_playlist not in self._playlists:
            self._playlists.append(new_playlist)
            self.PropertiesChanged(
                self.MEDIA_PLAYER2_PLAYLISTS_IFACE,
                {'PlaylistCount': GLib.Variant('u', len(self._playlists))},
                [],
            )

    def _current_playlist_handler(self, window, station):
        '''Sets the ActivePlaylist Property to the current station.'''
        new_current_playlist = (self.PLAYLIST_OBJ_PATH + station.id, station.name, '')
        if self._current_playlist != (True, new_current_playlist):
            self._current_playlist = (True, new_current_playlist)
            self.PropertiesChanged(
                self.MEDIA_PLAYER2_PLAYLISTS_IFACE,
                {'ActivePlaylist': GLib.Variant('(b(oss))', self._current_playlist)},
                [],
            )

    def _playstate_handler(self, window, state):
        '''Updates the mpris PlaybackStatus Property.'''
        play_state = 'Playing' if state else 'Paused'

        if self._playback_status != play_state: # stops unneeded updates
            self._playback_status = play_state
            self.PropertiesChanged(
                self.MEDIA_PLAYER2_PLAYER_IFACE,
                {'PlaybackStatus': GLib.Variant('s', self._playback_status)},
                [],
            )

    def _volumechange_handler(self, player, spec):
        '''Updates the mpris Volume Property.'''
        volume = math.pow(player.props.volume, 1.0 / 3.0)

        if self._volume != volume: # stops unneeded updates
            self._volume = volume
            self.PropertiesChanged(
                self.MEDIA_PLAYER2_PLAYER_IFACE,
                {'Volume': GLib.Variant('d', self._volume)},
                [],
            )

    def _songs_added_handler(self, window, songs):
        '''Adds songs to the TrackList Interface.'''
        # Replace the old playlist with the new one but make sure to include the current song.
        self._tracks = [self._track_id_from_song(song) for song in songs]
        self._metadata_list = [self._get_metadata(window, song) for song in songs]
        if window.current_song and window.current_song not in songs:
            self._tracks.insert(0, self._track_id_from_song(window.current_song))
            self._metadata_list.insert(0, self._get_metadata(window, window.current_song))
        self.TrackListReplaced(self._tracks, self._tracks[0])

    def _metadatachange_handler(self, window, song):
        '''Updates the metadata for the Player and TrackList Interfaces.'''
        # Ignore songs that have no chance of being in our Tracks list.
        if song.index < max(0, len(window.songs_model) - 5):
            return
        metadata = self._get_metadata(window, song)
        trackId = self._track_id_from_song(song)
        if trackId in self._tracks:
            for index, track_id in enumerate(self._tracks):
                if track_id == trackId:
                    self._metadata_list[index] = metadata
                    self.TrackMetadataChanged(trackId, metadata)
                    break
        # No need to update the current metadata if the current song has been banned
        # or set tired as it will be skipped anyway very shortly.
        if song is window.current_song and not (song.tired or song.rating == 'ban'):
            self._metadata = metadata
            self.PropertiesChanged(
                self.MEDIA_PLAYER2_PLAYER_IFACE,
                {'Metadata': GLib.Variant('a{sv}', self._metadata)},
                [],
            )

    def _get_metadata(self, window, song):
        '''Generates metadata for a song.'''
        # Map pithos ratings to something MPRIS understands
        userRating = 1.0 if song.rating == 'love' else 0.0
        duration = self._duration if song is window.current_song else song.trackLength * 1000000
        pithos_rating = window.song_icon(song) or ''
        trackid = self._track_id_from_song(song)

        metadata = {
            'mpris:trackid': GLib.Variant('o', trackid),
            'xesam:title': GLib.Variant('s', song.title or 'Title Unknown'),
            'xesam:artist': GLib.Variant('as', [song.artist] or ['Artist Unknown']),
            'xesam:album': GLib.Variant('s', song.album or 'Album Unknown'),
            'xesam:userRating': GLib.Variant('d', userRating),
            'xesam:url': GLib.Variant('s', song.audioUrl),
            'mpris:length': GLib.Variant('x', duration),
            'pithos:rating': GLib.Variant('s', pithos_rating),
        }

        # If we don't have an artUrl the best thing we can
        # do is not even have 'mpris:artUrl' in the metadata,
        # and let the applet decide what to do.
        if song.artUrl is not None:
            metadata['mpris:artUrl'] = GLib.Variant('s', song.artUrl)

        return metadata

    def _song_from_track_id(self, TrackId):
        '''Convenience method that takes a TrackId and returns the corresponding song object.'''
        if TrackId not in self._tracks:
            return
        if self.window.current_song_index is None:
            return
        songs_model = self.window.songs_model
        stop = len(songs_model)
        start = max(0, stop - 5)
        for i in range(start, stop):
            song = songs_model[i][0]
            if TrackId == self._track_id_from_song(song):
                return song

    def _track_id_from_song(self, song):
        '''Convenience method that generates a TrackId based on a song.'''
        return self.TRACK_OBJ_PATH + codecs.encode(bytes(song.trackToken, 'ascii'), 'hex').decode('ascii')

    @property
    def _duration(self):
        '''The current song's Duration.'''
        # use the duration provided by Pandora
        # if Gstreamer hasn't figured out the duration yet
        duration = self.window.query_duration()
        if duration is not None:
            return duration // 1000
        else:
            return self.window.current_song.trackLength * 1000000

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def CanQuit(self):
        '''b Read only Interface MediaPlayer2'''
        return True

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def Fullscreen(self):
        '''b Read/Write (optional) Interface MediaPlayer2'''
        return False

    @Fullscreen.setter
    def Fullscreen(self, Fullscreen):
        '''Not Implemented'''
        # Spec says the Fullscreen property should be read/write so we
        # include this dummy setter for applets that might wrongly ignore
        # the CanSetFullscreen property and try to set the Fullscreen
        # property anyway.
        pass

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def CanSetFullscreen(self):
        '''b Read only (optional) Interface MediaPlayer2'''
        return False

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def CanRaise(self):
        '''b Read only Interface MediaPlayer2'''
        return True

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def HasTrackList(self):
        '''b Read only Interface MediaPlayer2'''
        return True

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='s')
    def Identity(self):
        '''s Read only Interface MediaPlayer2'''
        return 'Pithos'

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='s')
    def DesktopEntry(self):
        '''s Read only (optional) Interface MediaPlayer2'''
        return 'io.github.Pithos'

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='as')
    def SupportedUriScheme(self):
        '''as Read only Interface MediaPlayer2'''
        return ['', ]

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='as')
    def SupportedMimeTypes(self):
        '''as Read only Interface MediaPlayer2'''
        return ['', ]

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='s')
    def PlaybackStatus(self):
        '''s Read only Interface MediaPlayer2.Player'''
        return self._playback_status

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='s')
    def LoopStatus(self):
        '''s Read only (optional) Interface MediaPlayer2.Player'''
        return 'None'

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def Shuffle(self):
        '''b Read only (optional) Interface MediaPlayer2.Player'''
        return False

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def Rate(self):
        '''d Read only (optional) Interface MediaPlayer2.Player'''
        return 1.0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='a{sv}')
    def Metadata(self):
        '''a{sv} Read only Interface MediaPlayer2.Player'''
        return self._metadata

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def Volume(self):
        '''d Read/Write Interface MediaPlayer2.Player'''
        volume = self.window.player.get_property('volume')
        scaled_volume = math.pow(volume, 1.0 / 3.0)
        return scaled_volume

    @Volume.setter
    def Volume(self, new_volume):
        scaled_vol = math.pow(new_volume, 3.0 / 1.0)
        self.window.player.set_property('volume', scaled_vol)

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='x')
    def Position(self):
        '''x Read only Interface MediaPlayer2.Player'''
        position = self.window.query_position()
        if position is not None:
            return position // 1000
        else:
            return 0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def MinimumRate(self):
        '''d Read only Interface MediaPlayer2.Player'''
        return 1.0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def MaximumRate(self):
        '''d Read only Interface MediaPlayer2.Player'''
        return 1.0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanGoNext(self):
        '''b Read only Interface MediaPlayer2.Player'''
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanGoPrevious(self):
        '''b Read only Interface MediaPlayer2.Player'''
        return False

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanPlay(self):
        '''b Read only Interface MediaPlayer2.Player'''
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanPause(self):
        '''b Read only Interface MediaPlayer2.Player'''
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanSeek(self):
        '''b Read only Interface MediaPlayer2.Player'''
        # This a lie because some sound applets depend upon
        # this to show song position/duration info
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanControl(self):
        '''b Read only Interface MediaPlayer2.Player'''
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYLISTS_IFACE, signature='(b(oss))')
    def ActivePlaylist(self):
        '''(b(oss)) Read only Interface MediaPlayer2.Playlists'''
        return self._current_playlist

    @dbus_property(MEDIA_PLAYER2_PLAYLISTS_IFACE, signature='u')
    def PlaylistCount(self):
        '''u Read only Interface MediaPlayer2.Playlists'''
        return len(self._playlists)

    @dbus_property(MEDIA_PLAYER2_PLAYLISTS_IFACE, signature='as')
    def Orderings(self):
        '''as Read only Interface MediaPlayer2.Playlists'''
        return self._orderings

    @dbus_property(MEDIA_PLAYER2_TRACKLIST_IFACE, signature='ao')
    def Tracks(self):
        '''ao Read only Interface MediaPlayer2.TrackList'''
        return self._tracks

    @dbus_property(MEDIA_PLAYER2_TRACKLIST_IFACE, signature='b')
    def CanEditTracks(self):
        '''b Read only Interface MediaPlayer2.TrackList'''
        return False

    @dbus_property(MEDIA_PLAYER2_RATINGS_IFACE, signature='b')
    def CanRate(self):
        '''b Read only Interface MediaPlayer2.ExtensionPithosRatings'''
        # This property exists so that applets can check it to make sure
        # the MediaPlayer2.ExtensionPithosRatings interface actually exists.
        # It's much more convenient for them then wrapping all their
        # ratings code in the equivalent of a try except block.
        # Not all versions of Pithos will have this interface.
        # It serves a similar function as HasTrackList.
        return True

    @dbus_method(MEDIA_PLAYER2_IFACE)
    def Raise(self):
        '''() -> nothing Interface MediaPlayer2'''
        self.window.bring_to_top()

    @dbus_method(MEDIA_PLAYER2_IFACE)
    def Quit(self):
        '''() -> nothing Interface MediaPlayer2'''
        self.window.quit()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Previous(self):
        '''Not Implemented'''
        pass

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Next(self):
        '''() -> nothing Interface MediaPlayer2.Player'''
        if not self.window.waiting_for_playlist:
            self.window.next_song()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def PlayPause(self):
        '''() -> nothing Interface MediaPlayer2.Player'''
        if self.window.current_song:
            self.window.playpause()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Play(self):
        '''() -> nothing Interface MediaPlayer2.Player'''
        if self.window.current_song:
            self.window.play()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Pause(self):
        '''() -> nothing Interface MediaPlayer2.Player'''
        if self.window.current_song:
            self.window.pause()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Stop(self):
        '''Stop is only used internally, mapping to pause instead.'''
        if self.window.current_song:
            self.window.pause()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='x')
    def Seek(self, Offset):
        '''Not Implemented'''
        self.Seeked(self.Position)

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='s')
    def OpenUri(self, Uri):
        '''Not Implemented'''
        pass

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='ox')
    def SetPosition(self, TrackId, Position):
        '''
        We can't actually seek, we lie so gnome-shell-extensions-mediaplayer[1] will show the
        position slider. We send a Seeked signal with the current position to make sure applets
        update their postion.

        Under normal circumstances SetPosition would tell the player where to seek to and any
        seeking caused by either the MPRIS client or the player would cause a Seeked signal to
        be fired with current track position after the seek.

        (The MPRIS client tells the player that it wants to seek to a position >>>
         the player seeks to the disired position >>>
         the player tells the MPRIS client were it actually seeked too.)

        We're skipping the middleman(Pithos) because we can't seek. Some players do not send
        a Seeked signal and some clients workaround that[2] so this may not be necessary for
        all clients.

        [1] https://github.com/eonpatapon/gnome-shell-extensions-mediaplayer/issues/246
        [2] https://github.com/eonpatapon/gnome-shell-extensions-mediaplayer#known-bugs
        '''

        self.Seeked(self.Position)

    @dbus_method(MEDIA_PLAYER2_PLAYLISTS_IFACE, in_signature='uusb', out_signature='a(oss)')
    def GetPlaylists(self, Index, MaxCount, Order, ReverseOrder):
        '''(uusb) -> a(oss) Interface MediaPlayer2.Playlists'''
        playlists = self._playlists[:]
        quick_mix = playlists.pop(0)

        if Order not in ('CreationDate', 'Alphabetical') or Order == 'Alphabetical':
            playlists = sorted(playlists, key=lambda playlists: playlists[1])
        if ReverseOrder:
            playlists.reverse()
        playlists = playlists[Index:MaxCount - 1]
        playlists.insert(0, quick_mix)
        return playlists

    @dbus_method(MEDIA_PLAYER2_PLAYLISTS_IFACE, in_signature='o')
    def ActivatePlaylist(self, PlaylistId):
        '''(o) -> nothing Interface MediaPlayer2.Playlists'''
        stations = self.window.pandora.stations
        station_id = PlaylistId.strip(self.PLAYLIST_OBJ_PATH)
        for station in stations:
            if station.id == station_id:
                self.window.station_changed(station)
                break

    @dbus_method(MEDIA_PLAYER2_TRACKLIST_IFACE, in_signature='ao', out_signature='aa{sv}')
    def GetTracksMetadata(self, TrackIds):
        '''(ao) -> aa{sv} Interface MediaPlayer2.TrackList'''
        return [self._metadata_list[self._tracks.index(TrackId)] for TrackId in TrackIds if TrackId in self._tracks]

    @dbus_method(MEDIA_PLAYER2_TRACKLIST_IFACE, in_signature='sob')
    def AddTrack(self, Uri, AfterTrack, SetAsCurrent):
        '''Not Implemented'''
        pass

    @dbus_method(MEDIA_PLAYER2_TRACKLIST_IFACE, in_signature='o')
    def RemoveTrack(self, TrackId):
        '''Not Implemented'''
        pass

    @dbus_method(MEDIA_PLAYER2_TRACKLIST_IFACE, in_signature='o')
    def GoTo(self, TrackId):
        '''(o) -> nothing Interface MediaPlayer2.TrackList'''
        song = self._song_from_track_id(TrackId)
        if song and song.index > self.window.current_song_index:
            self.window.start_song(song.index)

    @dbus_method(MEDIA_PLAYER2_RATINGS_IFACE, in_signature='o')
    def LoveSong(self, TrackId):
        '''(o) -> nothing Interface MediaPlayer2.ExtensionPithosRatings'''
        song = self._song_from_track_id(TrackId)
        if song:
            self.window.love_song(song=song)

    @dbus_method(MEDIA_PLAYER2_RATINGS_IFACE, in_signature='o')
    def BanSong(self, TrackId):
        '''(o) -> nothing Interface MediaPlayer2.ExtensionPithosRatings'''
        song = self._song_from_track_id(TrackId)
        if song:
            self.window.ban_song(song=song)

    @dbus_method(MEDIA_PLAYER2_RATINGS_IFACE, in_signature='o')
    def TiredSong(self, TrackId):
        '''(o) -> nothing Interface MediaPlayer2.ExtensionPithosRatings'''
        song = self._song_from_track_id(TrackId)
        if song:
            self.window.tired_song(song=song)

    @dbus_method(MEDIA_PLAYER2_RATINGS_IFACE, in_signature='o')
    def UnRateSong(self, TrackId):
        '''(o) -> nothing Interface MediaPlayer2.ExtensionPithosRatings'''
        song = self._song_from_track_id(TrackId)
        if song:
            self.window.unrate_song(song=song)

    @dbus_signal(MEDIA_PLAYER2_PLAYER_IFACE, signature='x')
    def Seeked(self, Position):
        '''x Interface MediaPlayer2.Player'''
        # Unsupported, but some applets depend on this.
        pass

    @dbus_signal(MEDIA_PLAYER2_PLAYLISTS_IFACE, signature='(oss)')
    def PlaylistChanged(self, Playlist):
        '''(oss) Interface MediaPlayer2.Playlists'''
        pass

    @dbus_signal(MEDIA_PLAYER2_TRACKLIST_IFACE, signature='aoo')
    def TrackListReplaced(self, Tracks, CurrentTrack):
        '''aoo Interface MediaPlayer2.TrackList'''
        pass

    @dbus_signal(MEDIA_PLAYER2_TRACKLIST_IFACE, signature='a{sv}o')
    def TrackAdded(self, Metadata, AfterTrack):
        '''a{sv}o Interface MediaPlayer2.TrackList'''
        pass

    @dbus_signal(MEDIA_PLAYER2_TRACKLIST_IFACE, signature='o')
    def TrackRemoved(self, TrackId):
        '''o Interface MediaPlayer2.TrackList'''
        pass

    @dbus_signal(MEDIA_PLAYER2_TRACKLIST_IFACE, signature='oa{sv}')
    def TrackMetadataChanged(self, TrackId, Metadata):
        '''oa{sv} Interface MediaPlayer2.TrackList'''
        pass

    def PropertiesChanged(self, interface, changed, invalidated):
        '''Emit mpris Property changes.'''
        try:
            self.connection.emit_signal(None, '/org/mpris/MediaPlayer2',
                                        'org.freedesktop.DBus.Properties',
                                        'PropertiesChanged',
                                        GLib.Variant.new_tuple(
                                            GLib.Variant('s', interface),
                                            GLib.Variant('a{sv}', changed),
                                            GLib.Variant('as', invalidated)
                                        ))
        except GLib.Error as e:
            logging.warning(e)
