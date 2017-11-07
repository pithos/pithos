# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010 Kevin Mehall <km@kevinmehall.net>
# Copyright (C) 2012 Christopher Eby <kreed@kreed.org>
# This program is free software: you can redistribute it and/or modify it
# under the terms of the GNU General Public License version 3, as published
# by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful, but
# WITHOUT ANY WARRANTY; without even the implied warranties of
# MERCHANTABILITY, SATISFACTORY QUALITY, or FITNESS FOR A PARTICULAR
# PURPOSE.  See the GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program.  If not, see <http://www.gnu.org/licenses/>.

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
import os
from enum import IntEnum
from socket import error as SocketError

from . import data

HTTP_TIMEOUT = 30
USER_AGENT = 'pithos'

RATE_BAN = 'ban'
RATE_LOVE = 'love'
RATE_NONE = None

class ApiError(IntEnum):
    INTERNAL_ERROR = 0
    MAINTENANCE_MODE = 1
    URL_PARAM_MISSING_METHOD = 2
    URL_PARAM_MISSING_AUTH_TOKEN = 3
    URL_PARAM_MISSING_PARTNER_ID = 4
    URL_PARAM_MISSING_USER_ID = 5
    SECURE_PROTOCOL_REQUIRED = 6
    CERTIFICATE_REQUIRED = 7
    PARAMETER_TYPE_MISMATCH = 8
    PARAMETER_MISSING = 9
    PARAMETER_VALUE_INVALID = 10
    API_VERSION_NOT_SUPPORTED = 11
    COUNTRY_NOT_SUPPORTED = 12
    INSUFFICIENT_CONNECTIVITY = 13
    UNKNOWN_METHOD_NAME = 14
    WRONG_PROTOCOL = 15
    READ_ONLY_MODE = 1000
    INVALID_AUTH_TOKEN = 1001
    INVALID_LOGIN = 1002
    LISTENER_NOT_AUTHORIZED = 1003
    USER_NOT_AUTHORIZED = 1004
    MAX_STATIONS_REACHED = 1005
    STATION_DOES_NOT_EXIST = 1006
    COMPLIMENTARY_PERIOD_ALREADY_IN_USE = 1007
    CALL_NOT_ALLOWED = 1008
    DEVICE_NOT_FOUND = 1009
    PARTNER_NOT_AUTHORIZED = 1010
    INVALID_USERNAME = 1011
    INVALID_PASSWORD = 1012
    USERNAME_ALREADY_EXISTS = 1013
    DEVICE_ALREADY_ASSOCIATED_TO_ACCOUNT = 1014
    UPGRADE_DEVICE_MODEL_INVALID = 1015
    EXPLICIT_PIN_INCORRECT = 1018
    EXPLICIT_PIN_MALFORMED = 1020
    DEVICE_MODEL_INVALID = 1023
    ZIP_CODE_INVALID = 1024
    BIRTH_YEAR_INVALID = 1025
    BIRTH_YEAR_TOO_YOUNG = 1026
    # FIXME: They can't both be 1027?
    # INVALID_COUNTRY_CODE = 1027
    # INVALID_GENDER = 1027
    DEVICE_DISABLED = 1034
    DAILY_TRIAL_LIMIT_REACHED = 1035
    INVALID_SPONSOR = 1036
    USER_ALREADY_USED_TRIAL = 1037
    PLAYLIST_EXCEEDED = 1039
    # Catch all for undocumented error codes
    UNKNOWN_ERROR = 100000

    @property
    def title(self):
        # Turns RANDOM_ERROR into Pandora Error: Random Error
        return 'Pandora Error: {}'.format(self.name.replace('_', ' ').title())

    @property
    def sub_message(self):
        value = self.value
        if value == 1:
            return 'Pandora is performing maintenance.\nTry again later.'
        elif value == 12:
            return ('Pandora is not available in your country.\n'
                    'If you wish to use Pandora you must configure your system or Pithos proxy accordingly.')
        elif value == 13:
            return ('Out of sync. Correct your system\'s clock.\n'
                    'If the problem persists, a Pithos update may be required.')
        if value == 1000:
            return 'Pandora is in read-only mode.\nTry again later.'
        elif value == 1002:
            return 'Invalid username or password.'
        elif value == 1003:
            return 'A Pandora One account is required to access this feature.\nUncheck "Pandora One" in Settings.'
        elif value == 1005:
            return ('You have reached the maximum number of stations.\n'
                    'To add a new station you must first delete an existing station.')
        elif value == 1010:
            return 'Invalid Pandora partner keys.\nA Pithos update may be required.'
        elif value == 1023:
            return 'Invalid Pandora device model.\nA Pithos update may be required.'
        elif value == 1039:
            return 'You have requested too many playlists.\nTry again later.'
        else:
            return None

PLAYLIST_VALIDITY_TIME = 60*60

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
        self.isSubscriber = False

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
            with self.opener.open(req, timeout=HTTP_TIMEOUT) as response:
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
        except SocketError as e:
            try:
                error_string = os.strerror(e.errno)
            except (TypeError, ValueError):
                error_string = "Unknown Error"
            logging.error("Network Socket Error: %s", error_string)
            raise PandoraNetError("Network Socket Error", submsg=error_string)

        logging.debug(text)

        tree = json.loads(text)
        if tree['stat'] == 'fail':
            code = tree['code']
            msg = tree['message']

            try:
                error_enum = ApiError(code)
            except ValueError:
                error_enum = ApiError.UNKNOWN_ERROR

            logging.error('fault code: {} {} message: {}'.format(code, error_enum.name, msg))

            if error_enum is ApiError.INVALID_AUTH_TOKEN:
                raise PandoraAuthTokenInvalid(msg)
            elif error_enum is ApiError.API_VERSION_NOT_SUPPORTED:
                raise PandoraAPIVersionError(msg)
            elif error_enum is ApiError.UNKNOWN_ERROR:
                submsg = 'Undocumented Error Code: {}\n{}'.format(code, msg)
                raise PandoraError(error_enum.title, code, submsg)
            else:
                submsg = error_enum.sub_message or 'Error Code: {}\n{}'.format(code, msg)
                raise PandoraError(error_enum.title, code, submsg)

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
        auth_args = {'username': user, 'password': password, 'loginType': 'user', 'returnIsSubscriber': True}
        user = self.json_call('auth.userLogin', auth_args, https=True)
        self.userId = user['userId']
        self.userAuthToken = user['userAuthToken']

        self.connected = True
        self.isSubscriber = user['isSubscriber']

    @property
    def explicit_content_filter_state(self):
        """The User must already be authenticated before this is called.
           returns the state of Explicit Content Filter and if the Explicit Content Filter is PIN protected
        """
        get_filter_state = self.json_call('user.getSettings', https=True)
        filter_state = get_filter_state['isExplicitContentFilterEnabled']
        pin_protected = get_filter_state['isExplicitContentFilterPINProtected']
        logging.info('Explicit Content Filter state: %s' %filter_state)
        logging.info('PIN protected: %s' %pin_protected)
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
        results = self.json_call(
            'music.search',
            {'includeGenreStations': True, 'includeNearMatches': True, 'searchText': query},
        )

        l = [SearchResult('artist', i) for i in results['artists'] if i['score'] >= 80]
        l += [SearchResult('song', i) for i in results['songs'] if i['score'] >= 80]
        l += [SearchResult('genre', i) for i in results['genreStations']]
        l.sort(key=lambda i: i.score, reverse=True)

        return l

    def add_station_by_music_id(self, musicid):
        d = self.json_call('station.createStation', {'musicToken': musicid})
        station = Station(self, d)
        if not self.get_station_by_id(station.id):
            self.stations.append(station)
        return station

    def add_station_by_track_token(self, trackToken, musicType):
        d = self.json_call('station.createStation', {'trackToken': trackToken, 'musicType': musicType})
        station = Station(self, d)
        if not self.get_station_by_id(station.id):
            self.stations.append(station)
        return station

    def delete_station(self, station):
        if self.get_station_by_id(station.id):
            logging.info("pandora: Deleting Station")
            self.json_call('station.deleteStation', {'stationToken': station.idToken})
            self.stations.remove(station)

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
        self.isThumbprint = d.get('isThumbprint', False)
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
        # Set the playlist time to the time we requested a playlist.
        # It is better that a playlist be considered invalid a fraction
        # of a sec early than be considered valid any longer than it actually is.
        playlist_time = time.time()
        playlist = self.pandora.json_call('station.getPlaylist', {
                        'stationToken': self.idToken,
                        'includeTrackLength': True,
                        'additionalAudioUrl': 'HTTP_32_AACPLUS,HTTP_128_MP3',
                    }, https=True)['items']

        return [Song(self.pandora, i, playlist_time) for i in playlist if 'songName' in i] 

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
        self.pandora.delete_station(self)

    def __repr__(self):
        return '<{}.{} {} "{}">'.format(
            __name__,
            __class__.__name__,
            self.id,
            self.name,
        )

class Song:
    def __init__(self, pandora, d, playlist_time):
        self.pandora = pandora
        self.playlist_time = playlist_time
        self.is_ad = None  # None = we haven't checked, otherwise True/False
        self.tired = False
        self.message = ''
        self.duration = None
        self.position = None
        self.bitrate = None
        self.start_time = None
        self.finished = False
        self.feedbackId = None
        self.bitrate = None
        self.artUrl = None
        self.album = d['albumName']
        self.artist = d['artistName']
        self.trackToken = d['trackToken']
        self.rating = RATE_LOVE if d['songRating'] == 1 else RATE_NONE # banned songs won't play, so we don't care about them
        self.stationId = d['stationId']
        self.songName = d['songName']
        self.songDetailURL = d['songDetailUrl']
        self.songExplorerUrl = d['songExplorerUrl']
        self.artRadio = d['albumArtUrl']
        self.trackLength = d['trackLength']
        self.trackGain = float(d.get('trackGain', '0.0'))
        self.audioUrlMap = d['audioUrlMap']

        # Optionally we requested more URLs
        if len(d.get('additionalAudioUrl', [])) == 2:
            if int(self.audioUrlMap['highQuality']['bitrate']) < 128:
                # We can use the higher quality mp3 stream for non-one users
                self.audioUrlMap['mediumQuality'] = self.audioUrlMap['highQuality']
                self.audioUrlMap['highQuality'] = {
                    'encoding': 'mp3',
                    'bitrate': '128',
                    'audioUrl': d['additionalAudioUrl'][1],
                }
            else:
                # And we can offer a lower bandwidth option for one users
                self.audioUrlMap['lowQuality'] = {
                    'encoding': 'aacplus',
                    'bitrate': '32',
                    'audioUrl': d['additionalAudioUrl'][0],
                }

        # the actual name of the track, minus any special characters (except dashes) is stored
        # as the last part of the songExplorerUrl, before the args.
        explorer_name = self.songExplorerUrl.split('?')[0].split('/')[-1]
        clean_expl_name = NAME_COMPARE_REGEX.sub('', explorer_name).lower()
        clean_name = NAME_COMPARE_REGEX.sub('', self.songName).lower()

        if clean_name == clean_expl_name:
            self.title = self.songName
        else:
            try:
                with urllib.request.urlopen(self.songExplorerUrl) as x, minidom.parseString(x.read()) as dom:
                    attr_value = dom.getElementsByTagName('songExplorer')[0].attributes['songTitle'].value

                # Pandora stores their titles for film scores and the like as 'Score name: song name'
                self.title = attr_value.replace('{0}: '.format(self.songName), '', 1)
            except:
                self.title = self.songName

    @property
    def audioUrl(self):
        quality = self.pandora.audio_quality
        try:
            q = self.audioUrlMap[quality]
            self.bitrate = q['bitrate']
            logging.info("Using audio quality %s: %s %s", quality, q['bitrate'], q['encoding'])
            return q['audioUrl']
        except KeyError:
            logging.warning("Unable to use audio format %s. Using %s",
                           quality, list(self.audioUrlMap.keys())[0])
            self.bitrate = list(self.audioUrlMap.values())[0]['bitrate']
            return list(self.audioUrlMap.values())[0]['audioUrl']

    @property
    def station(self):
        return self.pandora.get_station_by_id(self.stationId)

    def get_duration_sec(self):
        if self.duration is not None:
            return self.duration // 1000000000
        else:
            return self.trackLength

    def get_position_sec(self):
        if self.position is not None:
            return self.position // 1000000000
        else:
            return 0

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
        # Playlists are valid for 1 hour. A song is considered valid if there is enough time
        # to play the remaining duration of the song before the playlist expires.
        return ((time.time() + (self.get_duration_sec() - self.get_position_sec())) - self.playlist_time) < PLAYLIST_VALIDITY_TIME

    def __repr__(self):
        return '<{}.{} {} "{}" by "{}" from "{}">'.format(
            __name__,
            __class__.__name__,
            self.trackToken,
            self.title,
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
        elif resultType == 'genre':
            self.stationName = d['stationName']

