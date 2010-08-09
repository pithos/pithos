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
import time
import urllib2, urllib
import xml.etree.ElementTree as etree

from xmlrpc import *
from blowfish import Blowfish

PROTOCOL_VERSION = "27"
RPC_URL = "http://www.pandora.com/radio/xmlrpc/v"+PROTOCOL_VERSION+"?"
USER_AGENT = "Pithos/0.2"
HTTP_TIMEOUT = 30
AUDIO_FORMAT = 'aacplus'

RATE_BAN = 'ban'
RATE_LOVE = 'love'
RATE_NONE = None

class PandoraError(IOError):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        
class PandoraAuthTokenInvalid(PandoraError): pass

import pandora_keys

blowfish_encode = Blowfish(pandora_keys.out_key_p, pandora_keys.out_key_s)

def pad(s, l):
    return s + "\0" * (l - len(s))

def pandora_encrypt(s):
    return "".join([blowfish_encode.encrypt(pad(s[i:i+8], 8)).encode('hex') for i in xrange(0, len(s), 8)])
    
blowfish_decode = Blowfish(pandora_keys.in_key_p, pandora_keys.in_key_s)

def pandora_decrypt(s):
    return "".join([blowfish_decode.decrypt(pad(s[i:i+16].decode('hex'), 8)) for i in xrange(0, len(s), 16)]).rstrip('\x08')


def format_url_arg(v):
    if v is True:
        return 'true'
    elif v is False:
        return 'false'
    elif isinstance(v, list):
        return "%2C".join(v)
    else:
        return urllib.quote(str(v))

class Pandora(object):
    def __init__(self):
        self.rid = self.listenerId = self.authToken = None
        self.set_proxy(None)
        
    def xmlrpc_call(self, method, args=[], url_args=True):
        if url_args is True:
            url_args = args
            
        args = args[:]
        args.insert(0, int(time.time()))
        if self.authToken:
            args.insert(1, self.authToken)
            
        xml = xmlrpc_make_call(method, args)
        data = pandora_encrypt(xml)
        
        url_arg_strings = []
        if self.rid:
            url_arg_strings.append('rid=%s'%self.rid)
        if self.listenerId:
            url_arg_strings.append('lid=%s'%self.listenerId)
        method = method[method.find('.')+1:] # method in URL is only last component
        url_arg_strings.append('method=%s'%method)
        count = 1
        for i in url_args:
            url_arg_strings.append("arg%i=%s"%(count, format_url_arg(i)))
            count+=1
        
        url = RPC_URL + '&'.join(url_arg_strings)
        
        logging.debug(url)
        logging.debug(xml)
        
        req = urllib2.Request(url, data, {'User-agent': USER_AGENT, 'Content-type': 'text/xml'})
        response = self.opener.open(req, timeout=HTTP_TIMEOUT)
        text = response.read()
        logging.debug(text)
       
        tree = etree.fromstring(text)
        
        fault = tree.findtext('fault/value/struct/member/value')
        if fault:
            code, msg = fault.split('|')[2:]
            if code == 'AUTH_INVALID_TOKEN':
                raise PandoraAuthTokenInvalid(msg)
            else:
                raise PandoraError(code, msg)
        else:
            return xmlrpc_parse(tree)
     
    def set_proxy(self, proxy):
        if proxy:
            proxy_handler = urllib2.ProxyHandler({'http': proxy})
            self.opener = urllib2.build_opener(proxy_handler)  
        else:
            self.opener = urllib2.build_opener()     
        
    def connect(self, user, password):
        self.rid = "%07iP"%(int(time.time()) % 10000000)
            
        user = self.xmlrpc_call('listener.authenticateListener', [user, password], [])
        
        self.webAuthToken = user['webAuthToken']
        self.listenerId = user['listenerId']
        self.authToken = user['authToken']
        
        stations = self.xmlrpc_call('station.getStations')
        self.quickMixStationIds = None
        self.stations = [Station(self, i) for i in stations]
        
        if self.quickMixStationIds:
            for i in self.stations:
                if i.id in self.quickMixStationIds:
                    i.useQuickMix = True
                   
    def save_quick_mix(self):
        stationIds = []
        for i in self.stations:
            if i.useQuickMix:
                stationIds.append(i.id)
        self.xmlrpc_call('station.setQuickMix', ['RANDOM', stationIds])
         
    def search(self, query):
         results = self.xmlrpc_call('music.search', [query])
         
         l =  [SearchResult('artist', i) for i in results['artists']]
         l += [SearchResult('song',   i) for i in results['songs']]
         l.sort(key=lambda i: i.score, reverse=True)
         
         return l
         
    def create_station(self, reqType, id):
        assert(reqType == 'mi' or requestType == 'sh') # music id or shared station id
        d = self.xmlrpc_call('station.createStation', [reqType+id])
        station = Station(self, d)
        self.stations.append(station)
        return station
        
    def add_station_by_music_id(self, musicid):
         return self.create_station('mi', musicid)
         
    def add_feedback(self, stationId, musicId, rating, userSeed='', testStrategy='', songType=''):
        self.info("pandora: addFeedback")
        if rating == RATE_NONE:
            logging.error("Can't set rating to none")
            return
        rating_bool = True if rating == RATE_LOVE else False
        self.xmlrpc_call('station.addFeedback', [stationId, musicId, userSeed, testStrategy, rating_bool, False, songType])
        
    def get_station_by_id(self, id):
        for i in self.stations:
            if i.id == id:
                return i

        
class Station(object):
    def __init__(self, pandora, d):
        self.pandora = pandora
        
        self.id = d['stationId']
        self.idToken = d['stationIdToken']
        self.isCreator = d['isCreator']
        self.isQuickMix = d['isQuickMix']
        self.name = d['stationName']
        self.useQuickMix = False
        
        if self.isQuickMix:
            self.pandora.quickMixStationIds = d['quickMixStationIds']
         
    def transformIfShared(self):
        if not self.isCreator:
            logging.info("pandora: transforming station")
            self.pandora.xmlrpc_call('station.transformShared', [self.id])
            self.isCreator = True
            
    def get_playlist(self):
        logging.info("pandora: Get Playlist")
        playlist = self.pandora.xmlrpc_call('playlist.getFragment', [self.id, '0', '', '', AUDIO_FORMAT, '0', '0'])
        return [Song(self.pandora, i) for i in playlist]
                  
    @property
    def info_url(self):
        return 'http://www.pandora.com/stations/'+self.idToken
        
    def rename(self, new_name):
        if new_name != self.name:
            logging.info("pandora: Renaming station")
            self.pandora.xmlrpc_call('station.setStationName', [self.id, new_name])
            self.name = new_name
        
    def delete(self):
        logging.info("pandora: Deleting Station")
        self.pandora.xmlrpc_call('station.removeStation', [self.id])
        
class Song(object):
    def __init__(self, pandora, d):
        self.pandora = pandora
        
        self.album = d['albumTitle']
        self.artist = d['artistSummary']
        self.artistMusicId = d['artistMusicId']
        self.audioUrl = d['audioURL'][:-48] + pandora_decrypt(d['audioURL'][-48:])
        self.fileGain = d['fileGain']
        self.identity = d['identity']
        self.musicId = d['musicId']
        self.rating = RATE_LOVE if d['rating'] else RATE_NONE # banned songs won't play, so we don't care about them
        self.stationId = d['stationId']
        self.title = d['songTitle']
        self.userSeed = d['userSeed']
        self.songDetailURL = d['songDetailURL']
        self.albumDetailURL = d['albumDetailURL']
        self.artRadio = d['artRadio']
        self.songType = d['songType']
        
        self.tired=False
        self.message=''
        self.start_time = None
        
    @property
    def station(self):
        return self.pandora.get_station_by_id(self.stationId)
    
    def rate(self, rating):
        if self.rating != rating:
            self.station.transformIfShared()
            self.pandora.add_feedback(self.stationId, self.musicId, rating, self.userSeed, songType=self.songType)
            self.rating = rating
        
    def set_tired(self):
        if not self.tired:
            self.pandora.xmlrpc_call('listener.addTiredSong', [self.identity])
            self.tired = True
            
    def bookmark(self):
        self.pandora.xmlrpc_call('station.createBookmark', [self.stationId, self.musicId])
        
    def bookmark_artist(self):
        self.pandora.xmlrpc_call('station.createArtistBookmark', [self.artistMusicId])
            
    @property
    def rating_str(self):
        return self.rating
        
class SearchResult(object):
    def __init__(self, resultType, d):
        self.resultType = resultType
        self.score = d['score']
        self.musicId = d['musicId']
        
        if resultType == 'song':
            self.title = d['songTitle']
            self.artist = d['artistSummary']
        elif resultType == 'artist':
            self.name = d['artistName']
        
        
