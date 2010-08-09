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

from .pandora import *
import gtk
import logging

class FakePandora(Pandora):
    def __init__(self):
        super(FakePandora, self).__init__()
        self.counter = 0
        self.show_fail_window()
        logging.info("Using test mode")
    
    def count(self):
        self.counter +=1
        return self.counter
        
    def show_fail_window(self):
        self.window = gtk.Window()
        self.window.set_size_request(200, 100)
        self.window.set_title("Pithos failure tester")
        self.window.set_opacity(0.7)
        self.auth_check = gtk.CheckButton("Authenticated")
        self.time_check = gtk.CheckButton("Be really slow")
        vbox = gtk.VBox()
        self.window.add(vbox)
        vbox.pack_start(self.auth_check)
        vbox.pack_start(self.time_check)
        self.window.show_all()

    def maybe_fail(self):
        if self.time_check.get_active():
            logging.info("fake: Going to sleep for 10s")
            time.sleep(10)
        if not self.auth_check.get_active():
            logging.info("fake: We're deauthenticated...")
            raise PandoraAuthTokenInvalid("AUTH_INVALID_TOKEN", "Auth token invalid")

    def set_authenticated(self):
        self.auth_check.set_active(True)
        
    def xmlrpc_call(self, method, args=[], url_args=True):
        print "fake xmlrpc"
        time.sleep(1)
        if method != 'listener.authenticateListener':
            self.maybe_fail()
            
        if method == 'listener.authenticateListener':
            self.set_authenticated()
            return {'webAuthToken': '123', 'listenerId':'456', 'authToken':'789'}
        
        elif method == 'station.getStations':
            return [
                {'stationId':'987', 'stationIdToken':'345434', 'isCreator':True, 'isQuickMix':False, 'stationName':"Test Station 1"},   
                {'stationId':'321', 'stationIdToken':'453544', 'isCreator':True, 'isQuickMix':True, 'stationName':"Fake's QuickMix",
                    'quickMixStationIds':['987', '343']},
                {'stationId':'432', 'stationIdToken':'345485', 'isCreator':True, 'isQuickMix':False, 'stationName':"Test Station 2"},
                {'stationId':'343', 'stationIdToken':'345435', 'isCreator':True, 'isQuickMix':False, 'stationName':"Test Station 3"},   
            ]
        elif method == 'playlist.getFragment':
            return [self.makeFakeSong(args) for i in range(4)]
        elif method == 'music.search':
            return {'artists': [
                        {'score':90, 'musicId':'988', 'artistName':"artistName"},
                    ],
                    'songs':[
                        {'score':80, 'musicId':'238', 'songTitle':"SongName", 'artistSummary':"ArtistName"},
                    ],
                   }
        elif method == 'station.createStation':
            return {'stationId':'999', 'stationIdToken':'345433', 'isCreator':True, 'isQuickMix':False, 'stationName':"Added Station"} 
        elif method in ('station.setQuickMix',
                        'station.addFeedback',
                        'station.transformShared', 
                        'station.setStationName',
                        'station.removeStation',
                        'listener.addTiredSong',
                        'station.createBookmark',
                        'station.createArtistBookmark',
                     ):
            return 1
        else:
            logging.error("Invalid method %s" % method)
            
    def makeFakeSong(self, args):
        c = self.count()
        return {
            'albumTitle':"AlbumName",
            'artistSummary':"ArtistName",
            'artistMusicId':'4324',
            'audioURL':'http://kevinmehall.net/p/pithos/testfile.aac?val='+'0'*48,
            'fileGain':0,
            'identity':'5908540384',
            'musicId':'4543',
            'rating': 1 if c%3 == 0 else 0,
            'stationId': args[0],
            'songTitle': 'Test song %i'%c,
            'userSeed': '54543',
            'songDetailURL': 'http://kevinmehall.net/p/pithos/',
            'albumDetailURL':'http://kevinmehall.net/p/pithos/',
            'artRadio':'http://i.imgur.com/H3Z8x.jpg',
            'songType':0,
        }
            
