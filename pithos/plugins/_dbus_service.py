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

import logging
from gi.repository import GLib, Gio
from .dbus_util.DBusServiceObject import *

DBUS_BUS = "net.kevinmehall.Pithos"
DBUS_INTERFACE = "net.kevinmehall.Pithos"
DBUS_OBJECT_PATH = "/net/kevinmehall/Pithos"

class PithosDBusProxy(DBusServiceObject):
    def __init__(self, window, **kwargs):
        super().__init__(object_path=DBUS_OBJECT_PATH, **kwargs)
        self.window = window
        self.window.connect("song-changed",
                            lambda window, song: self.SongChanged(self.song_to_variant(song)))
        self.window.connect("play-state-changed",
                            lambda window, state: self.PlayStateChanged(state))

    def connect(self):
        def on_name_acquired(connection, name):
            logging.info('Got bus name: %s' %name)

        self.bus_id = Gio.bus_own_name_on_connection(self.connection, DBUS_BUS,
                            Gio.BusNameOwnerFlags.NONE, on_name_acquired, None)

    def disconnect(self):
        if self.bus_id:
            Gio.bus_unown_name(self.bus_id)
            self.bus_id = 0

    @staticmethod
    def song_to_variant(song):
        d = {}
        if song:
            for i in ['artist', 'title', 'album', 'songDetailURL']:
                d[i] = GLib.Variant('s', getattr(song, i))
        return d

    @dbus_method(interface=DBUS_INTERFACE)
    def PlayPause(self):
        self.window.playpause_notify()

    @dbus_method(interface=DBUS_INTERFACE)
    def SkipSong(self):
        self.window.next_song()

    @dbus_method(interface=DBUS_INTERFACE)
    def LoveCurrentSong(self):
        self.window.love_song()

    @dbus_method(interface=DBUS_INTERFACE)
    def BanCurrentSong(self):
        self.window.ban_song()

    @dbus_method(interface=DBUS_INTERFACE)
    def TiredCurrentSong(self):
        self.window.tired_song()

    @dbus_method(interface=DBUS_INTERFACE)
    def Present(self):
        self.window.bring_to_top()

    @dbus_method(interface=DBUS_INTERFACE, out_signature='a{sv}')
    def GetCurrentSong(self):
        return GLib.Variant('a{sv}', self.song_to_dict(self.window.current_song))

    @dbus_method(interface=DBUS_INTERFACE, out_signature='b')
    def IsPlaying(self):
        return self.window.playing

    @dbus_signal(interface=DBUS_INTERFACE, signature='b')
    def PlayStateChanged(self, state):
        pass

    @dbus_signal(interface=DBUS_INTERFACE, signature='a{sv}')
    def SongChanged(self, songinfo):
        pass
