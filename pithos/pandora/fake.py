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

from pithos.pandora.pandora import *
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
            raise PandoraAuthTokenInvalid("Auth token invalid", "AUTH_INVALID_TOKEN")

    def set_authenticated(self):
        self.auth_check.set_active(True)

    def json_call(self, method, args={}, https=False, blowfish=True):
        time.sleep(1)
        self.maybe_fail()

        if method == 'user.getStationList':
            return {'stations': [
                {'stationId':'987', 'stationToken':'345434', 'isShared':False, 'isQuickMix':False, 'stationName':"Test Station 1"},
                {'stationId':'321', 'stationToken':'453544', 'isShared':False, 'isQuickMix':True, 'stationName':"Fake's QuickMix",
                    'quickMixStationIds':['987', '343']},
                {'stationId':'432', 'stationToken':'345485', 'isShared':False, 'isQuickMix':False, 'stationName':"Test Station 2"},
                {'stationId':'254', 'stationToken':'345415', 'isShared':False, 'isQuickMix':False, 'stationName':"Test Station 4 - Out of Order"},
                {'stationId':'343', 'stationToken':'345435', 'isShared':False, 'isQuickMix':False, 'stationName':"Test Station 3"},
            ]}
        elif method == 'station.getPlaylist':
            stationId = self.get_station_by_token(args['stationToken']).id
            return {'items': [self.makeFakeSong(stationId) for i in range(4)]}
        elif method == 'music.search':
            return {'artists': [
                        {'score':90, 'musicToken':'988', 'artistName':"artistName"},
                    ],
                    'songs':[
                        {'score':80, 'musicToken':'238', 'songName':"SongName", 'artistName':"ArtistName"},
                    ],
                   }
        elif method == 'station.createStation':
            return {'stationId':'999', 'stationToken':'345433', 'isShared':False, 'isQuickMix':False, 'stationName':"Added Station"}
        elif method == 'station.addFeedback':
            return {'feedbackId': '1234'}
        elif method in ('user.setQuickMix',
                        'station.deleteFeedback',
                        'station.transformSharedStation',
                        'station.renameStation',
                        'station.deleteStation',
                        'user.sleepSong',
                        'bookmark.addSongBookmark',
                        'bookmark.addArtistBookmark',
                     ):
            return 1
        else:
            logging.error("Invalid method %s" % method)

    def connect(self, user, password):
        self.set_authenticated()
        self.get_stations()

    def get_station_by_token(self, token):
        for i in self.stations:
            if i.idToken == token:
                return i

    def makeFakeSong(self, stationId):
        c = self.count()
        return {
            'albumName':"AlbumName",
            'artistName':"ArtistName",
            'additionalAudioUrl':'http://kevinmehall.net/p/pithos/testfile.aac?val='+'0'*48,
            'trackGain':0,
            'trackToken':'5908540384',
            'songRating': 1 if c%3 == 0 else 0,
            'stationId': stationId,
            'songName': 'Test song %i'%c,
            'songDetailUrl': 'http://kevinmehall.net/p/pithos/',
            'albumDetailUrl':'http://kevinmehall.net/p/pithos/',
            'albumArtUrl':'http://i.imgur.com/H4Z8x.jpg',
        }

