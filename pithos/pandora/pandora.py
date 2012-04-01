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

from pithos.pandora.xmlrpc import *
from pithos.pandora.blowfish import Blowfish

PROTOCOL_VERSION = "33"
RPC_URL = "www.pandora.com/radio/xmlrpc/v"+PROTOCOL_VERSION+"?"
USER_AGENT = "Mozilla/5.0 (X11; U; Linux i586; de; rv:5.0) Gecko/20100101 Firefox/5.0 (compatible; Pithos/0.3)"
HTTP_TIMEOUT = 30
AUDIO_FORMAT = 'aacplus'

RATE_BAN = 'ban'
RATE_LOVE = 'love'
RATE_NONE = None

PLAYLIST_VALIDITY_TIME = 60*60*3

class PandoraError(IOError):
    def __init__(self, message, status=None, submsg=None):
        self.status = status
        self.message = message
        self.submsg = submsg
        
class PandoraAuthTokenInvalid(PandoraError): pass
class PandoraNetError(PandoraError): pass
class PandoraAPIVersionError(PandoraError): pass
class PandoraTimeout(PandoraNetError): pass

from pithos.pandora import pandora_keys

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
        self.set_audio_format(AUDIO_FORMAT)
        
    def xmlrpc_call(self, method, args=[], url_args=True, secure=False, includeTime=True):
        if url_args is True:
            url_args = args
            
        args = args[:]
        
        if includeTime:
            args.insert(0, int(time.time()+self.time_offset))
            
        if self.authToken:
            args.insert(1, self.authToken)
            
        xml = xmlrpc_make_call(method, args)
        data = pandora_encrypt(xml)
        
        url_arg_strings = []
        
        if self.rid and includeTime:
            url_arg_strings.append('rid=%s'%self.rid)
        if self.listenerId:
            url_arg_strings.append('lid=%s'%self.listenerId)
        method = method[method.find('.')+1:] # method in URL is only last component
        url_arg_strings.append('method=%s'%method)
        count = 1
        for i in url_args:
            url_arg_strings.append("arg%i=%s"%(count, format_url_arg(i)))
            count+=1
        
        if secure:
            proto = 'https://'
        else:
            proto = 'http://'
        
        url = proto + RPC_URL + '&'.join(url_arg_strings)
        
        logging.debug(url)
        logging.debug(xml)
        
        try:
            req = urllib2.Request(url, data, {'User-agent': USER_AGENT, 'Content-type': 'text/xml'})
            response = self.opener.open(req, timeout=HTTP_TIMEOUT)
            text = response.read()
        except urllib2.URLError as e:
            logging.error("Network error: %s", e)
            if e.reason[0] == 'timed out':
                raise PandoraTimeout("Network error", submsg="Timeout")
            else:
                raise PandoraNetError("Network error", submsg=e.reason[1])
            
        logging.debug(text)
       
        tree = etree.fromstring(text)
        
        fault = tree.findtext('fault/value/struct/member/value')
        if fault:
            logging.error('fault: ' +  fault)
            
            try:
                code, msg = fault.split('|')[2:]
            except:
                raise PandoraError("Pandora returned a malformed error: %s" % (fault))
                
            if code == 'AUTH_INVALID_TOKEN':
                raise PandoraAuthTokenInvalid(msg)
            elif code == 'INCOMPATIBLE_VERSION':
                raise PandoraAPIVersionError(msg)
            elif code == 'OUT_OF_SYNC':
                raise PandoraError("Out of sync", code,
                    submsg="Correct your system's clock. If the problem persists, a Pithos update may be required")
            elif code == 'AUTH_INVALID_USERNAME_PASSWORD':
                raise PandoraError("Login Error", code, submsg="Invalid username or password")
            else:
                raise PandoraError("Pandora returned an error", code, "%s: %s"%(code, msg))
        else:
            return xmlrpc_parse(tree)

    def set_audio_format(self, fmt):
        self.audio_format = fmt
     
    def set_proxy(self, proxy):
        if proxy:
            proxy_handler = urllib2.ProxyHandler({'http': proxy})
            self.opener = urllib2.build_opener(proxy_handler)  
        else:
            self.opener = urllib2.build_opener()     
        
    def connect(self, user, password):
        self.rid = "%07iP"%(int(time.time()) % 10000000)
        self.listenerId = self.authToken = None
        
        pandora_time = self.xmlrpc_call('misc.sync', [], [], secure=True, includeTime=False)
        logging.info("Pandora sync reply is %s", pandora_decrypt(pandora_time))
        pandora_time = int(pandora_decrypt(pandora_time)[4:14])
        self.time_offset =  pandora_time - time.time()
        logging.info("Time offset is %s", self.time_offset)
            
        user = self.xmlrpc_call('listener.authenticateListener', [user, password], [], secure=True)
        
        self.webAuthToken = user['webAuthToken']
        self.listenerId = user['listenerId']
        self.authToken = user['authToken']
        
        self.get_stations(self)
        
    def get_stations(self, *ignore):
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
        d = self.xmlrpc_call('station.createStation', [reqType+id, ''])
        station = Station(self, d)
        self.stations.append(station)
        return station
        
    def add_station_by_music_id(self, musicid):
         return self.create_station('mi', musicid)
         
    def add_feedback(self, stationId, trackToken, rating):
        logging.info("pandora: addFeedback")
        if rating == RATE_NONE:
            logging.error("Can't set rating to none")
            return
        rating_bool = True if rating == RATE_LOVE else False
        self.xmlrpc_call('station.addFeedback', [stationId, trackToken, rating_bool])
        
    def get_station_by_id(self, id):
        for i in self.stations:
            if i.id == id:
                return i

    def get_feedback_id(self, stationId, musicId):
        station = self.xmlrpc_call('station.getStation', [stationId])
        feedback = station['feedback']
        for i in feedback:
            if musicId == i['musicId']:
                return i['feedbackId']

    def delete_feedback(self, feedbackId):
        self.xmlrpc_call('station.deleteFeedback', [feedbackId])
        
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
            self.pandora.quickMixStationIds = d.get('quickMixStationIds', [])
         
    def transformIfShared(self):
        if not self.isCreator:
            logging.info("pandora: transforming station")
            self.pandora.xmlrpc_call('station.transformShared', [self.id])
            self.isCreator = True
            
    def get_playlist(self):
        logging.info("pandora: Get Playlist")
        playlist = self.pandora.xmlrpc_call('playlist.getFragment', [self.id, '0', '', '', self.pandora.audio_format, '0', '0'])
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
        self.trackToken = d['trackToken']
        self.rating = RATE_LOVE if d['rating'] else RATE_NONE # banned songs won't play, so we don't care about them
        self.stationId = d['stationId']
        self.title = d['songTitle']
        self.userSeed = d['userSeed']
        self.songDetailURL = d['songDetailURL']
        self.albumDetailURL = d['albumDetailURL']
        self.artRadio = d['artRadio']
        
        self.tired=False
        self.message=''
        self.start_time = None
        self.finished = False
        self.playlist_time = time.time()
        
    @property
    def station(self):
        return self.pandora.get_station_by_id(self.stationId)
    
    @property
    def feedbackId(self):
        return self.pandora.get_feedback_id(self.stationId, self.musicId)

    def rate(self, rating):
        if self.rating != rating:
            self.station.transformIfShared()
            if rating == RATE_NONE:
                self.pandora.delete_feedback(self.feedbackId)
            else:
                self.pandora.add_feedback(self.stationId, self.trackToken, rating)
            self.rating = rating
        
    def set_tired(self):
        if not self.tired:
            self.pandora.xmlrpc_call('listener.addTiredSong', [self.musicId, self.userSeed, self.stationId])
            self.tired = True
            
    def bookmark(self):
        self.pandora.xmlrpc_call('station.createBookmark', [self.stationId, self.musicId])
        
    def bookmark_artist(self):
        self.pandora.xmlrpc_call('station.createArtistBookmark', [self.artistMusicId])
            
    @property
    def rating_str(self):
        return self.rating
        
    def is_still_valid(self):
        return (time.time() - self.playlist_time) < PLAYLIST_VALIDITY_TIME
        
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
        
        
