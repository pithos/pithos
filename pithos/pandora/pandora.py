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

"""Pandora JSON v5 API

See http://6xq.net/playground/pandora-apidoc/json/ for API documentation.
"""

from .blowfish import Blowfish
# from Crypto.Cipher import Blowfish
from xml.dom import minidom
import re
import json
import logging
import time
import urllib.request, urllib.parse, urllib.error
import codecs
import ssl

from . import data

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
API_ERROR_PLAYLIST_EXCEEDED = 1039

PLAYLIST_VALIDITY_TIME = 60*60*3

NAME_COMPARE_REGEX = re.compile(r'[^A-Za-z0-9]')

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
    return s + b'\0' * (l - len(s))

class Pandora:
    """Access the Pandora API

    To use the Pandora class, make sure to call :py:meth:`set_audio_quality`
    and :py:meth:`connect` methods.

    Get information from Pandora using:

    - :py:meth:`get_stations` which populates the :py:attr:`stations` attribute
    - :py:meth:`search` to find songs to add to stations or create a new station with
    - :py:meth:`json_call` call into the JSON API directly
    """
    def __init__(self):
        self.opener = self.build_opener()
        self.connected = False

    def pandora_encrypt(self, s):
        return b''.join([codecs.encode(self.blowfish_encode.encrypt(pad(s[i:i+8], 8)), 'hex_codec') for i in range(0, len(s), 8)])

    def pandora_decrypt(self, s):
        return b''.join([self.blowfish_decode.decrypt(pad(codecs.decode(s[i:i+16], 'hex_codec'), 8)) for i in range(0, len(s), 16)]).rstrip(b'\x08')

    def json_call(self, method, args=None, https=False, blowfish=True):
        if not args:
            args = {}
        url_arg_strings = []
        if self.partnerId:
            url_arg_strings.append('partner_id=%s'%self.partnerId)
        if self.userId:
            url_arg_strings.append('user_id=%s'%self.userId)
        if self.userAuthToken:
            url_arg_strings.append('auth_token=%s'%urllib.parse.quote_plus(self.userAuthToken))
        elif self.partnerAuthToken:
            url_arg_strings.append('auth_token=%s'%urllib.parse.quote_plus(self.partnerAuthToken))

        url_arg_strings.append('method=%s'%method)
        protocol = 'https' if https else 'http'
        url = protocol + self.rpcUrl + '&'.join(url_arg_strings)

        if self.time_offset:
            args['syncTime'] = int(time.time()+self.time_offset)
        if self.userAuthToken:
            args['userAuthToken'] = self.userAuthToken
        elif self.partnerAuthToken:
            args['partnerAuthToken'] = self.partnerAuthToken
        data = json.dumps(args).encode('utf-8')

        logging.debug(url)
        logging.debug(data)

        if blowfish:
            data = self.pandora_encrypt(data)

        try:
            req = urllib.request.Request(url, data, {'User-agent': USER_AGENT, 'Content-type': 'text/plain'})
            response = self.opener.open(req, timeout=HTTP_TIMEOUT)
            text = response.read().decode('utf-8')
        except urllib.error.HTTPError as e:
            logging.error("HTTP error: %s", e)
            raise PandoraNetError(str(e))
        except urllib.error.URLError as e:
            logging.error("Network error: %s", e)
            if e.reason.strerror == 'timed out':
                raise PandoraTimeout("Network error", submsg="Timeout")
            else:
                raise PandoraNetError("Network error", submsg=e.reason.strerror)

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
                    submsg="Pandora is not available in your country.")
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
                raise PandoraError("Pandora Error", code,
                    submsg="A Pandora One account is required to access this feature. Uncheck 'Pandora One' in Settings.")
            elif code == API_ERROR_PARTNER_NOT_AUTHORIZED:
                raise PandoraError("Login Error", code,
                    submsg="Invalid Pandora partner keys. A Pithos update may be required.")
            elif code == API_ERROR_PLAYLIST_EXCEEDED:
                raise PandoraError("Playlist Error", code,
                    submsg="You have requested too many playlists. Try again later.")
            else:
                raise PandoraError("Pandora returned an error", code, "%s (code %d)"%(msg, code))

        if 'result' in tree:
            return tree['result']

    def set_audio_quality(self, fmt):
        """Set the desired audio quality

        Used by the :py:attr:`Song.audioUrl` property.

        :param fmt: An audio quality format from :py:data:`pithos.pandora.data.valid_audio_formats`
        """
        self.audio_quality = fmt

    @staticmethod
    def build_opener(*handlers):
        """Creates a new opener

        Wrapper around urllib.request.build_opener() that adds
        a custom ssl.SSLContext for use with internal-tuner.pandora.com
        """
        ctx = ssl.create_default_context()
        ctx.load_verify_locations(cadata=data.internal_cert)
        https = urllib.request.HTTPSHandler(context=ctx)
        return urllib.request.build_opener(https, *handlers)

    def set_url_opener(self, opener):
        self.opener = opener

    def connect(self, client, user, password):
        """Connect to the Pandora API and log the user in

        :param client:   The client ID from :py:data:`pithos.pandora.data.client_keys`
        :param user:     The user's login email
        :param password: The user's login password
        """
        self.connected = False
        self.partnerId = self.userId = self.partnerAuthToken = None
        self.userAuthToken = self.time_offset = None

        self.rpcUrl = client['rpcUrl']
        self.blowfish_encode = Blowfish(client['encryptKey'].encode('utf-8'))
        self.blowfish_decode = Blowfish(client['decryptKey'].encode('utf-8'))

        partner = self.json_call('auth.partnerLogin', {
            'deviceModel': client['deviceModel'],
            'username': client['username'], # partner username
            'password': client['password'], # partner password
            'version': client['version']
            },https=True, blowfish=False)

        self.partnerId = partner['partnerId']
        self.partnerAuthToken = partner['partnerAuthToken']

        pandora_time = int(self.pandora_decrypt(partner['syncTime'].encode('utf-8'))[4:14])
        self.time_offset = pandora_time - time.time()
        logging.info("Time offset is %s", self.time_offset)

        user = self.json_call('auth.userLogin', {'username': user, 'password': password, 'loginType': 'user'}, https=True)
        self.userId = user['userId']
        self.userAuthToken = user['userAuthToken']

        self.connected = True
        self.get_stations(self)

    @property
    def explicit_content_filter_state(self):
        """The User must already be authenticated before this is called.
           returns the state of Explicit Content Filter and if the Explicit Content Filter is PIN protected
        """
        get_filter_state = self.json_call('user.getSettings', https=True)
        filter_state = get_filter_state['isExplicitContentFilterEnabled']
        pin_protected = get_filter_state['isExplicitContentFilterPINProtected']
        logging.info('Explicit Content Filter state: %s', filter_state)
        logging.info('PIN protected: %s', pin_protected)
        return filter_state, pin_protected

    def set_explicit_content_filter(self, state):
        """The User must already be authenticated before this is called.
           Does not take effect until the next playlist.
           Valid desired states are True to enable and False to disable the Explicit Content Filter.
        """
        self.json_call('user.setExplicitContentFilter', {'isExplicitContentFilterEnabled': state})
        logging.info('Explicit Content Filter set to: %s' %(state))

    def get_stations(self, *ignore):
        stations = self.json_call('user.getStationList')['stations']
        self.quickMixStationIds = None
        self.stations = [Station(self, i) for i in stations]

        if self.quickMixStationIds:
            for i in self.stations:
                if i.id in self.quickMixStationIds:
                    i.useQuickMix = True

        return self.stations

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

class Station:
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
        playlist = self.pandora.json_call('station.getPlaylist', {'stationToken': self.idToken}, https=True)
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

    def __repr__(self):
        return '<{}.{} {} "{}">'.format(
            __name__,
            __class__.__name__,
            self.id,
            self.name,
        )

class Song:
    def __init__(self, pandora, d):
        self.pandora = pandora

        self.album = d['albumName']
        self.artist = d['artistName']
        self.audioUrlMap = d['audioUrlMap']
        self.trackToken = d['trackToken']
        self.rating = RATE_LOVE if d['songRating'] == 1 else RATE_NONE # banned songs won't play, so we don't care about them
        self.stationId = d['stationId']
        self.songName = d['songName']
        self.songDetailURL = d['songDetailUrl']
        self.songExplorerUrl = d['songExplorerUrl']
        self.artRadio = d['albumArtUrl']

        self.bitrate = None
        self.is_ad = None  # None = we haven't checked, otherwise True/False
        self.tired=False
        self.message=''
        self.duration = None
        self.position = None
        self.start_time = None
        self.finished = False
        self.playlist_time = time.time()
        self.feedbackId = None
        self._title = ''

    @property
    def title(self):
        if not self._title:
            # the actual name of the track, minus any special characters (except dashes) is stored
            # as the last part of the songExplorerUrl, before the args.
            explorer_name = self.songExplorerUrl.split('?')[0].split('/')[-1]
            clean_expl_name = NAME_COMPARE_REGEX.sub('', explorer_name).lower()
            clean_name = NAME_COMPARE_REGEX.sub('', self.songName).lower()

            if clean_name == clean_expl_name:
                self._title = self.songName
            else:
                try:
                    xml_data = urllib.request.urlopen(self.songExplorerUrl)
                    dom = minidom.parseString(xml_data.read())
                    attr_value = dom.getElementsByTagName('songExplorer')[0].attributes['songTitle'].value

                    # Pandora stores their titles for film scores and the like as 'Score name: song name'
                    self._title = attr_value.replace('{0}: '.format(self.songName), '', 1)
                except:
                    self._title = self.songName
        return self._title

    @property
    def audioUrl(self):
        quality = self.pandora.audio_quality
        try:
            q = self.audioUrlMap[quality]
            logging.info("Using audio quality %s: %s %s", quality, q['bitrate'], q['encoding'])
            return q['audioUrl']
        except KeyError:
            logging.warning("Unable to use audio format %s. Using %s",
                           quality, list(self.audioUrlMap.keys())[0])
            return list(self.audioUrlMap.values())[0]['audioUrl']

    @property
    def station(self):
        return self.pandora.get_station_by_id(self.stationId)

    def get_duration_sec (self):
      if self.duration is not None:
        return self.duration / 1000000000

    def get_position_sec (self):
      if self.position is not None:
        return self.position / 1000000000

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

    def __repr__(self):
        return '<{}.{} {} "{}" by "{}" from "{}">'.format(
            __name__,
            __class__.__name__,
            self.trackToken,
            self.songName,
            self.artist,
            self.album,
        )


class SearchResult:
    def __init__(self, resultType, d):
        self.resultType = resultType
        self.score = d['score']
        self.musicId = d['musicToken']

        if resultType == 'song':
            self.title = d['songName']
            self.artist = d['artistName']
        elif resultType == 'artist':
            self.name = d['artistName']

