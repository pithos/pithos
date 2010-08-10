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

import dbus.service

DBUS_BUS = "net.kevinmehall.Pithos"
DBUS_OBJECT_PATH = "/net/kevinmehall/Pithos"

def song_to_dict(song):
    d = {}
    if song:
        for i in ['artist', 'title', 'album', 'songDetailURL']:
            d[i] = getattr(song, i)
    return d
  
class PithosDBusProxy(dbus.service.Object):
    def __init__(self, window):
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(DBUS_BUS, bus=self.bus)
        dbus.service.Object.__init__(self, bus_name, DBUS_OBJECT_PATH)
        self.window = window
        self.window.connect("song-changed", self.songchange_handler)
        self.window.connect("play-state-changed", self.playstate_handler)
        
    def playstate_handler(self, window, state):
        self.PlayStateChanged(state)
        
    def songchange_handler(self, window, song):
        self.SongChanged(song_to_dict(song))
    
    @dbus.service.method(DBUS_BUS)
    def PlayPause(self):
        self.window.playpause()
    
    @dbus.service.method(DBUS_BUS)
    def SkipSong(self):
        self.window.next_song()
    
    @dbus.service.method(DBUS_BUS)
    def LoveCurrentSong(self):
        self.window.love_song()
    
    @dbus.service.method(DBUS_BUS)
    def BanCurrentSong(self):
        self.window.ban_song()
    
    @dbus.service.method(DBUS_BUS)
    def TiredCurrentSong(self):
        self.window.tired_song()
        
    @dbus.service.method(DBUS_BUS)
    def Present(self):
        self.window.present()
        
    @dbus.service.method(DBUS_BUS, out_signature='a{sv}')
    def GetCurrentSong(self):
        return song_to_dict(self.window.current_song)
        
    @dbus.service.method(DBUS_BUS, out_signature='b')
    def IsPlaying(self):
        return self.window.playing
        
    @dbus.service.signal(DBUS_BUS, signature='b')
    def PlayStateChanged(self, state):
        pass
        
    @dbus.service.signal(DBUS_BUS, signature='a{sv}')
    def SongChanged(self, songinfo):
        pass    


def try_to_raise():
    bus = dbus.SessionBus()
    try:
        proxy = bus.get_object(DBUS_BUS, DBUS_OBJECT_PATH)
        proxy.Present()
        return True
    except dbus.exceptions.DBusException as e:
        return False
