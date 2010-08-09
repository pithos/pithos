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
import urllib2
import xml.etree.ElementTree as etree

from blowfish import pandora_encrypt, pandora_decrypt

PROTOCOL_VERSION = "27"
RPC_URL = "http://www.pandora.com/radio/xmlrpc/v"+PROTOCOL_VERSION+"?"
USER_AGENT = "Pithos/0.2"
HTTP_TIMEOUT = 30
AUDIO_FORMAT = 'aacplus'

RATE_BAN = 'ban'
RATE_LOVE = 'love'

def xmlrpc_value(v):
    if isinstance(v, str):
        return "<value><string>%s</string></value>"%v
    elif isinstance(v, int):
        return "<value><int>%i</int></value>"%v
    else:
        raise ValueError("Can't encode %s of type %s to XMLRPC"%(v, type(v)))

def xmlrpc_parse_value(tree):
    b = tree.findtext('boolean')
    if b:
        return bool(int(b))
    i = tree.findtext('int')
    if i:
        return int(i)
    a = tree.find('array')
    if a:
        return xmlrpc_parse_array(a)
    s = tree.find('struct')
    if s:
        return xmlrpc_parse_struct(s)
    return tree.text
 
def xmlrpc_parse_struct(tree):
    d = {}
    for member in tree.findall('member'):
        name = member.findtext('name')
        d[name] = xmlrpc_parse_value(member.find('value'))
    return d
    
def xmlrpc_parse_array(tree):
    return [xmlrpc_parse_value(item) for item in tree.findall('data/value')]

def xmlrpc_parse(tree):
    return xmlrpc_parse_value(tree.find('params/param/value'))
    
        

class PianoError(IOError):
    def __init__(self, status, message):
        self.status = status
        self.message = message
        
class PianoAuthTokenInvalid(PianoError): pass

class PianoPandora(object):
    def __init__(self):
        self.rid = self.listenerId = self.authToken = None
        self.proxy = None
        
    def xmlrpc_call(self, method, args=[], url_args=[]):
        args.insert(0, int(time.time()))
        if self.authToken:
            args.insert(1, self.authToken)
        args = "".join(["<param>%s</param>"%xmlrpc_value(i) for i in args])
        xml = "<?xml version=\"1.0\"?><methodCall><methodName>%s</methodName><params>%s</params></methodCall>"%(method, args)
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
            url_arg_strings.append("arg%i=%s"%(count, i))
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
            raise PianoError(code, msg)
        else:
            return xmlrpc_parse(tree)
            
        
    def connect(self, user, password, proxy):
        self.rid = "%07iP"%(int(time.time()) % 10000000)
        if proxy:
            proxy_handler = urllib2.ProxyHandler({'http': proxy})
            self.opener = urllib2.build_opener(proxy_handler)
        else:
            self.opener = urllib2.build_opener()
            
        user = self.xmlrpc_call('listener.authenticateListener', [user, password])
        
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
        notImplemented()
        
    def search(self, query):
         notImplemented()
         
    def add_station_by_music_id(self, musicid):
         notImplemented()

        
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
            logging.debug("libpiano: transforming station")
            notImplemented()
            self.isCreator = True
            
    def get_playlist(self):
        logging.debug("libpiano: Get Playlist")
        args = [self.id, '0', '', '', AUDIO_FORMAT, '0', '0']
        playlist = self.pandora.xmlrpc_call('playlist.getFragment', args, args)
        return [Song(self.pandora, i) for i in playlist]
        
            
    @property
    def info_url(self):
        return 'http://www.pandora.com/stations/'+self.idToken
        
    def rename(self, new_name):
        if new_name != self.name:
            logging.debug("libpiano: Renaming station")
            notImplemented()
            self.name = new_name
        
    def delete(self):
        logging.debug("libpiano: Deleting Station")
        notImplemented()
        
class Song(object):
    def __init__(self, pandora, d):
        self.pandora = pandora
        
        self.album = d['albumTitle']
        self.artist = d['artistSummary']
        self.audioUrl = d['audioURL'][:-48] + pandora_decrypt(d['audioURL'][-48:])
        self.fileGain = d['fileGain']
        self.identity = d['identity']
        self.musicId = d['musicId']
        self.rating = d['rating']
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
        return self.piano.stations_dict[self.stationId]
    
    def rate(self, rating):
        if self.rating != rating:
            self.station.transformIfShared()
            notImplemented()
            pianoCheck(piano.PianoAddFeedback(
                self.piano.p, self.stationId,
                self.musicId, self.matchingSeed, self.userSeed, self.focusTraitId, rating
            ))
            self.rating = rating
        
    def set_tired(self):
        if not self.tired:
            notImplemented()
            self.tired = True
            
    @property
    def rating_str(self):
        if self.rating == RATE_LOVE:
            return 'love'
        elif self.rating == RATE_BAN:
            return 'ban'
        else:
            return None
        
class PianoSongResult(object):
    resultType = "song"
    def __init__(self, c_obj):
        self.title = c_obj.title
        self.musicId = c_obj.musicId
        self.artist = c_obj.artist
        
        
class PianoArtistResult(object):
    resultType = "artist"
    def __init__(self, c_obj):
        self.name = c_obj.name
        self.musicId = c_obj.musicId
        self.score = c_obj.score
