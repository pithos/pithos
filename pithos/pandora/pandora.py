# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010 Kevin Mehall <km@kevinmehall.net>
# Copyright (C) 2012 Christopher Eby <kreed@kreed.org>
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

from pithos.pandora.blowfish import Blowfish
import json
import logging
import time
import urllib
import urllib2

# This is an implementation of the Pandora JSON API using Android partner
# credentials.
# See http://pan-do-ra-api.wikia.com/wiki/Json/5 for API documentation.

PROTOCOL_VERSION = '5'

CLIENTS = {'android-generic': {'deviceModel': 'android-generic',
                               'partner_username': 'android',
                               'partner_password': 'AC7IBG09A3DTSYM4R41UJWL07VLN8JI7',
                               'rpcUrl': '://tuner.pandora.com/services/json/?',
                               'encryptKey': '6#26FRL$ZWD',
                               'decryptKey': 'R=U!LH$O2B#',
                              },
           'pandora one': {'deviceModel': 'D01',
                           'partner_username': 'pandora one',
                           'partner_password': 'TVCKIBGS9AO9TSYLNNFUML0743LH82D',
                           'rpcUrl': '://internal-tuner.pandora.com/services/json/?',
                           'encryptKey': '2%3WCL*JU$MP]4',
                           'decryptKey': 'U#IO$RZPAB%VX2',
                          }
          }
DEFAULT_CLIENT = CLIENTS['android-generic']

HTTP_TIMEOUT = 30
USER_AGENT = 'pithos'

RATE_BAN = 'ban'
RATE_LOVE = 'love'
RATE_NONE = None

API_ERROR_API_VERSION_NOT_SUPPORTED = 11
API_ERROR_COUNTRY_NOT_SUPPORTED = 12
API_ERROR_INSUFFICIENT_CONNECTIVITY = 13
API_ERROR_READ_ONLY_MODE = 1000
API_ERROR_INVALID_AUTH_TOKEN = 1001
API_ERROR_INVALID_LOGIN = 1002
API_ERROR_LISTENER_NOT_AUTHORIZED = 1003
API_ERROR_PARTNER_NOT_AUTHORIZED = 1010

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


def pad(s, l):
    return s + "\0" * (l - len(s))


class Pandora(object):
    def pandora_encrypt(self, s):
        return "".join([self.blowfish_encode.encrypt(pad(s[i:i+8], 8)).encode('hex') for i in xrange(0, len(s), 8)])

    def pandora_decrypt(self, s):
        return "".join([self.blowfish_decode.decrypt(pad(s[i:i+16].decode('hex'), 8)) for i in xrange(0, len(s), 16)]).rstrip('\x08')

    def json_call(self, method, args={}, https=False, blowfish=True):
        url_arg_strings = []
        if self.partnerId:
            url_arg_strings.append('partner_id=%s'%self.partnerId)
        if self.userId:
            url_arg_strings.append('user_id=%s'%self.userId)
        if self.userAuthToken:
            url_arg_strings.append('auth_token=%s'%urllib.quote_plus(self.userAuthToken))
        elif self.partnerAuthToken:
            url_arg_strings.append('auth_token=%s'%urllib.quote_plus(self.partnerAuthToken))

        url_arg_strings.append('method=%s'%method)
        protocol = 'https' if https else 'http'
        url = protocol + self.rpc_url + '&'.join(url_arg_strings)

        if self.time_offset:
            args['syncTime'] = int(time.time()+self.time_offset)
        if self.userAuthToken:
            args['userAuthToken'] = self.userAuthToken
        elif self.partnerAuthToken:
            args['partnerAuthToken'] = self.partnerAuthToken
        data = json.dumps(args)

        logging.debug(url)
        logging.debug(data)

        if blowfish:
            data = self.pandora_encrypt(data)

        try:
            req = urllib2.Request(url, data, {'User-agent': USER_AGENT, 'Content-type': 'text/plain'})
            response = self.opener.open(req, timeout=HTTP_TIMEOUT)
            text = response.read()
        except urllib2.HTTPError as e:
            logging.error("HTTP error: %s", e)
            raise PandoraNetError(str(e))
        except urllib2.URLError as e:
            logging.error("Network error: %s", e)
            if e.reason[0] == 'timed out':
                raise PandoraTimeout("Network error", submsg="Timeout")
            else:
                raise PandoraNetError("Network error", submsg=e.reason[1])

        logging.debug(text)

        tree = json.loads(text)

        if tree['stat'] == 'fail':
            code = tree['code']
            msg = tree['message']
            logging.error('fault code: ' + str(code) + ' message: ' + msg)

            if code == API_ERROR_INVALID_AUTH_TOKEN:
                raise PandoraAuthTokenInvalid(msg)
            elif code == API_ERROR_COUNTRY_NOT_SUPPORTED:
                 raise PandoraError("Pandora not available", code,
                    submsg="Pandora is not available outside the United States.")
            elif code == API_ERROR_API_VERSION_NOT_SUPPORTED:
                raise PandoraAPIVersionError(msg)
            elif code == API_ERROR_INSUFFICIENT_CONNECTIVITY:
                raise PandoraError("Out of sync", code,
                    submsg="Correct your system's clock. If the problem persists, a Pithos update may be required")
            elif code == API_ERROR_READ_ONLY_MODE:
                raise PandoraError("Pandora maintenance", code,
                    submsg="Pandora is in read-only mode as it is performing maintenance. Try again later.")
            elif code == API_ERROR_INVALID_LOGIN:
                raise PandoraError("Login Error", code, submsg="Invalid username or password")
            elif code == API_ERROR_LISTENER_NOT_AUTHORIZED:
                raise PandoraError("Login Error", code, submsg='User is not a Pandora One subscriber.\nPlease uncheck "Pandora One Subscriber" in preferences.')
            elif code == API_ERROR_PARTNER_NOT_AUTHORIZED:
                raise PandoraError("Login Error", code,
                    submsg="Invalid Pandora partner keys. A Pithos update may be required.")
            else:
                raise PandoraError("Pandora returned an error", code, "%s (code %d)"%(msg, code))

        if 'result' in tree:
            return tree['result']

    def set_audio_quality(self, fmt):
        self.audio_quality = fmt

    def set_proxy(self, proxy):
        if proxy:
            proxy_handler = urllib2.ProxyHandler({'http': proxy})
            self.opener = urllib2.build_opener(proxy_handler)
        else:
            self.opener = urllib2.build_opener()

    def connect(self, prefs):
        client = DEFAULT_CLIENT
        if prefs['pandora_one']:
          client = CLIENTS['pandora one']
        self.partner_username = prefs.get('partner_username', client['partner_username'])
        self.partner_password = prefs.get('partner_password', client['partner_password'])
        self.device_model = prefs.get('device_model', client['deviceModel'])
        self.blowfish_encode = Blowfish(prefs.get('encrypt_key', client['encryptKey']))
        self.blowfish_decode = Blowfish(prefs.get('decrypt_key', client['decryptKey']))
        self.rpc_url = prefs.get('rpc_url', client['rpcUrl'])

        self.partnerId = self.userId = self.partnerAuthToken = self.userAuthToken = self.time_offset = None

        partner = self.json_call('auth.partnerLogin', {'deviceModel': self.device_model,
                                                       'username': self.partner_username,
                                                       'password': self.partner_password,
                                                       'version': PROTOCOL_VERSION},
                                 https=True, blowfish=False)
        self.partnerId = partner['partnerId']
        self.partnerAuthToken = partner['partnerAuthToken']

        pandora_time = int(self.pandora_decrypt(partner['syncTime'])[4:14])
        self.time_offset = pandora_time - time.time()
        logging.info("Time offset is %s", self.time_offset)

        user = self.json_call('auth.userLogin', {'username': prefs['username'],
                                                 'password': prefs['password'], 'loginType': 'user'},
                              https=True)
        self.userId = user['userId']
        self.userAuthToken = user['userAuthToken']

        self.get_stations(self)

    def get_stations(self, *ignore):
        stations = self.json_call('user.getStationList')['stations']
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
        self.json_call('user.setQuickMix', {'quickMixStationIds': stationIds})

    def search(self, query):
        results = self.json_call('music.search', {'searchText': query})

        l =  [SearchResult('artist', i) for i in results['artists']]
        l += [SearchResult('song',   i) for i in results['songs']]
        l.sort(key=lambda i: i.score, reverse=True)

        return l

    def add_station_by_music_id(self, musicid):
        d = self.json_call('station.createStation', {'musicToken': musicid})
        station = Station(self, d)
        self.stations.append(station)
        return station

    def get_station_by_id(self, id):
        for i in self.stations:
            if i.id == id:
                return i

    def add_feedback(self, trackToken, rating):
        logging.info("pandora: addFeedback")
        rating_bool = True if rating == RATE_LOVE else False
        feedback = self.json_call('station.addFeedback', {'trackToken': trackToken, 'isPositive': rating_bool})
        return feedback['feedbackId']

    def delete_feedback(self, stationToken, feedbackId):
        self.json_call('station.deleteFeedback', {'feedbackId': feedbackId, 'stationToken': stationToken})

class Station(object):
    def __init__(self, pandora, d):
        self.pandora = pandora

        self.id = d['stationId']
        self.idToken = d['stationToken']
        self.isCreator = not d['isShared']
        self.isQuickMix = d['isQuickMix']
        self.name = d['stationName']
        self.useQuickMix = False

        if self.isQuickMix:
            self.pandora.quickMixStationIds = d.get('quickMixStationIds', [])

    def transformIfShared(self):
        if not self.isCreator:
            logging.info("pandora: transforming station")
            self.pandora.json_call('station.transformSharedStation', {'stationToken': self.idToken})
            self.isCreator = True

    def get_playlist(self):
        logging.info("pandora: Get Playlist")
        playlist = self.pandora.json_call('station.getPlaylist',
                                          {'stationToken': self.idToken}, https=True)
        songs = []
        for i in playlist['items']:
            if 'songName' in i: # check for ads
                songs.append(Song(self.pandora, i))
        return songs

    @property
    def info_url(self):
        return 'http://www.pandora.com/stations/'+self.idToken

    def rename(self, new_name):
        if new_name != self.name:
            self.transformIfShared()
            logging.info("pandora: Renaming station")
            self.pandora.json_call('station.renameStation', {'stationToken': self.idToken, 'stationName': new_name})
            self.name = new_name

    def delete(self):
        logging.info("pandora: Deleting Station")
        self.pandora.json_call('station.deleteStation', {'stationToken': self.idToken})

class Song(object):
    def __init__(self, pandora, d):
        self.pandora = pandora

        self.album = d['albumName']
        self.artist = d['artistName']
        if self.pandora.audio_quality in d['audioUrlMap']:
          self.audioUrl = d['audioUrlMap'][self.pandora.audio_quality]['audioUrl']
        else:
          # Just pick the first one
          self.audioUrl = d['audioUrlMap'].values()[0]['audioUrl']
        self.trackToken = d['trackToken']
        self.rating = RATE_LOVE if d['songRating'] == 1 else RATE_NONE # banned songs won't play, so we don't care about them
        self.stationId = d['stationId']
        self.title = d['songName']
        self.songDetailURL = d['songDetailUrl']
        self.artRadio = d['albumArtUrl']

        self.tired=False
        self.message=''
        self.start_time = None
        self.finished = False
        self.playlist_time = time.time()
        self.feedbackId = None

    @property
    def station(self):
        return self.pandora.get_station_by_id(self.stationId)

    def rate(self, rating):
        if self.rating != rating:
            self.station.transformIfShared()
            if rating == RATE_NONE:
                if not self.feedbackId:
                    # We need a feedbackId, get one by re-rating the song. We
                    # could also get one by calling station.getStation, but
                    # that requires transferring a lot of data (all feedback,
                    # seeds, etc for the station).
                    opposite = RATE_BAN if self.rating == RATE_LOVE else RATE_LOVE
                    self.feedbackId = self.pandora.add_feedback(self.trackToken, opposite)
                self.pandora.delete_feedback(self.station.idToken, self.feedbackId)
            else:
                self.feedbackId = self.pandora.add_feedback(self.trackToken, rating)
            self.rating = rating

    def set_tired(self):
        if not self.tired:
            self.pandora.json_call('user.sleepSong', {'trackToken': self.trackToken})
            self.tired = True

    def bookmark(self):
        self.pandora.json_call('bookmark.addSongBookmark', {'trackToken': self.trackToken})

    def bookmark_artist(self):
        self.pandora.json_call('bookmark.addArtistBookmark', {'trackToken': self.trackToken})

    @property
    def rating_str(self):
        return self.rating

    def is_still_valid(self):
        return (time.time() - self.playlist_time) < PLAYLIST_VALIDITY_TIME

class SearchResult(object):
    def __init__(self, resultType, d):
        self.resultType = resultType
        self.score = d['score']
        self.musicId = d['musicToken']

        if resultType == 'song':
            self.title = d['songName']
            self.artist = d['artistName']
        elif resultType == 'artist':
            self.name = d['artistName']

