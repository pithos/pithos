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
import logging
import math
import codecs
from xml.etree import ElementTree
from gi.repository import (
    GLib,
    Gio,
    Gtk
)
from .dbus_util.DBusServiceObject import *

class PithosMprisService(DBusServiceObject):
    MEDIA_PLAYER2_IFACE = 'org.mpris.MediaPlayer2'
    MEDIA_PLAYER2_PLAYER_IFACE = 'org.mpris.MediaPlayer2.Player'

    def __init__(self, window, **kwargs):
        """
        Creates a PithosMprisService object.
        """
        super().__init__(object_path='/org/mpris/MediaPlayer2', **kwargs)
        self.window = window
        self._volume = math.pow(self.window.player.props.volume, 1.0/3.0)
        self._metadata = {}
        self._playback_status = 'Stopped'

        self.window.connect("metadata-changed", self._metadatachange_handler)
        self.window.connect("play-state-changed", self._playstate_handler)
        self.window.player.connect("notify::volume", self._volumechange_handler)
        self.window.connect("buffering-finished", lambda window, position: self.Seeked(position // 1000))

        # Updates everything if mpris is enabled in the middle of a song
        if self.window.current_song:
            self._metadatachange_handler(self.window, self.window.current_song)
            self._playstate_handler(self.window, self.window.playing)

    def connect(self):
        def on_name_acquired(connection, name):
            logging.info('Got bus name: %s' %name)

        self.bus_id = Gio.bus_own_name_on_connection(self.connection, 'org.mpris.MediaPlayer2.pithos',
                            Gio.BusNameOwnerFlags.NONE, on_name_acquired, None)

    def disconnect(self):
        if self.bus_id:
            Gio.bus_unown_name(self.bus_id)
            self.bus_id = 0

    def _playstate_handler(self, window, state):
        """Updates the playstate in the Sound Menu"""

        play_state = 'Playing' if state else 'Paused'

        if self._playback_status != play_state: # stops unneeded updates
            self._playback_status = play_state
            self.PropertiesChanged(self.MEDIA_PLAYER2_PLAYER_IFACE, {
                    "PlaybackStatus": GLib.Variant('s', self._playback_status)
                }, [])

    def _volumechange_handler(self, player, spec):
        """Updates the volume in the Sound Menu"""
        volume = math.pow(player.props.volume, 1.0/3.0)

        if self._volume != volume: # stops unneeded updates
            self._volume = volume
            self.PropertiesChanged(self.MEDIA_PLAYER2_PLAYER_IFACE, {
                    "Volume": GLib.Variant('d', self._volume)
                }, [])

    def _metadatachange_handler(self, window, song):
        """Updates the song info in the Sound Menu"""

        if song is self.window.current_song: # we only care about the current song
            self.PropertiesChanged(self.MEDIA_PLAYER2_PLAYER_IFACE, {
                    'Metadata': GLib.Variant('a{sv}', self._update_metadata(song)),
                }, [])

    def _update_metadata(self, song):
        """
        metadata changed - sets the info for the current song.

        This method is not typically overriden. It should be called
        by implementations of this class when the player has changed
        songs.

        named arguments:
            artists - a list of strings representing the artists"
            album - a string for the name of the album
            title - a string for the title of the song

        """
        # Map pithos ratings to something MPRIS understands
        if song.rating == 'love':
            userRating = 5
        else:
            userRating = 0

        # Try to use the generic audio MIME type icon from the user's current theme
        # for the cover image if we don't get one from Pandora
        # Workaround for:
        # https://github.com/eonpatapon/gnome-shell-extensions-mediaplayer/issues/248

        if song.artUrl is not None:
            artUrl = song.artUrl
        else:
            icon_sizes = Gtk.IconTheme.get_icon_sizes(Gtk.IconTheme.get_default(), 'audio-x-generic')
            if -1 in icon_sizes: # -1 is a scalable icon(svg)
                best_icon = -1
            else:
                icon_sizes = sorted(icon_sizes, key=int, reverse=True)
                best_icon = icon_sizes[0] 
            icon_info = Gtk.IconTheme.get_default().lookup_icon('audio-x-generic', best_icon, 0)
            artUrl = "file://%s" %icon_info.get_filename()

        # Ensure is a valid dbus path by converting to hex
        track_id = codecs.encode(bytes(song.trackToken, 'ascii'), 'hex').decode('ascii')
        self._metadata = {
            "mpris:trackid": GLib.Variant('o', '/io/github/Pithos/TrackId/' + track_id),
            "xesam:title": GLib.Variant('s', song.title or "Title Unknown"),
            "xesam:artist": GLib.Variant('as', [song.artist] or ["Artist Unknown"]),
            "xesam:album": GLib.Variant('s', song.album or "Album Unknown"),
            "xesam:userRating": GLib.Variant('i', userRating),
            "mpris:artUrl": GLib.Variant('s', artUrl),
            "xesam:url": GLib.Variant('s', song.audioUrl),
            "mpris:length": GLib.Variant('x', self._duration),
            "pithos:rating": GLib.Variant('s', song.rating or ""),
        }

        return self._metadata

    @property
    def _duration(self):
        # use the duration provided by Pandora
        # if Gstreamer hasn't figured out the duration yet
        if self.window.query_duration() is not None:
            return self.window.query_duration() // 1000
        else:
            return self.window.current_song.trackLength * 1000000

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def CanQuit(self):
        return True

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def CanRaise(self):
        return True

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='b')
    def HasTrackList(self):
        return False

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='s')
    def Identity(self):
        return 'Pithos'

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='s')
    def DesktopEntry(self):
        return 'io.github.Pithos'

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='as')
    def SupportedUriScheme(self):
        return ['',]

    @dbus_property(MEDIA_PLAYER2_IFACE, signature='as')
    def SupportedMimeTypes(self):
        return ['',]

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='s')
    def PlaybackStatus(self):
        """Current status "Playing", "Paused", or "Stopped"."""
        if not self.window.current_song:
            return "Stopped"
        if self.window.playing:
            return "Playing"
        else:
            return "Paused"

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='s')
    def LoopStatus(self):
        return 'None'

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def Shuffle(self):
        return False

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def Rate(self):
        return 1.0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='a{sv}')
    def Metadata(self):
        """The info for the current song."""
        if self._metadata:
            return self._metadata
        else:
            return {"mpris:trackid": GLib.Variant('o', '/org/mpris/MediaPlayer2/TrackList/NoTrack'),
                    # Workaround for https://github.com/eonpatapon/gnome-shell-extensions-mediaplayer/issues/247
                    "xesam:url": GLib.Variant('s', '')}

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def Volume(self):
        volume = self.window.player.get_property("volume")
        scaled_volume = math.pow(volume, 1.0/3.0)
        return scaled_volume

    @Volume.setter
    def Volume(self, new_volume):
        scaled_vol = math.pow(new_volume, 3.0/1.0)
        self.window.player.set_property('volume', scaled_vol)

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='x')
    def Position(self):
        if self.window.query_position() is not None:
            return self.window.query_position() // 1000
        else:
            return 0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def MinimumRate(self):
        return 1.0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='d')
    def MaximumRate(self):
        return 1.0

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanGoNext(self):
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanGoPrevious(self):
        return False

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanPlay(self):
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanPause(self):
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanSeek(self):
        # This a lie because some sound applets depend upon
        # this to show song position/duration info
        return True

    @dbus_property(MEDIA_PLAYER2_PLAYER_IFACE, signature='b')
    def CanControl(self):
        return True

    @dbus_method(MEDIA_PLAYER2_IFACE)
    def Raise(self):
        """Bring the media player to the front when selected by the sound menu"""

        self.window.bring_to_top()

    @dbus_method(MEDIA_PLAYER2_IFACE)
    def Quit(self):
        """Exit the player"""
        self.window.quit()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Previous(self):
        """Play previous song, not implemented"""
        pass

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Next(self):
        """Play next song"""
        if not self.window.waiting_for_playlist:
            self.window.next_song()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def PlayPause(self):
        if self.window.current_song:
            self.window.playpause()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Play(self):
        if self.window.current_song:
            self.window.play()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Pause(self):
        if self.window.current_song:
            self.window.pause()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE)
    def Stop(self):
        """Stop is only used internally, mapping to pause instead"""
        self.window.pause()

    @dbus_method(MEDIA_PLAYER2_PLAYER_IFACE, in_signature='ox')
    def SetPosition(self, trackid, position):
        """
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
        """

        self.Seeked(self.Position)

    @dbus_signal(MEDIA_PLAYER2_PLAYER_IFACE, signature='x')
    def Seeked(self, position):
        '''Unsupported but some applets depend on this'''
        pass

    def PropertiesChanged(self, interface, changed, invalidated):
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
