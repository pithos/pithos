### BEGIN LICENSE
# Copyright (C) 2016 Jason Gray <jasonlevigray3@gmail.com>
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

import logging
import json
import urllib.error
import urllib.parse
import urllib.request

from string import punctuation
from enum import Enum

from gi.repository import Gtk, GObject, GLib, Gdk
from pithos.gobject_worker import GObjectWorker
from pithos.gi_composites import GtkTemplate
from pithos.plugin import PithosPlugin
from pithos.util import open_browser

class LastfmErrorCode(Enum):
    INVALID_SERVICE = 2
    INVALID_METHOD = 3
    AUTH_FAILED = 4
    INVALID_FORMAT = 5
    INVALID_PARMAS = 6
    INVALID_RESOURCES = 7
    OPERATION_FAILED = 8
    INVALID_SESSION_KEY = 9
    INVALID_API_KEY = 10
    SERVICE_OFFLINE = 11
    INVALID_METHOD_SIG = 13
    TEMPORARY_ERROR = 16
    SUSPENDED_API_KEY = 26
    RATE_LIMIT_EXCEEDED = 29

    @property
    def message(self):
        value = self.value
        if value == 2:
            return 'This service does not exist'
        elif value == 3:
            return 'No method with that name in this package'
        elif value == 4:
            return 'You do not have permissions to access the service'
        elif value == 5:
            return 'This service doesn\'t exist in that format'
        elif value == 6:
            return 'Your request is missing a required parameter'
        elif value == 7:
            return 'Invalid resource specified'
        elif value == 8:
            return 'Something else went wrong'
        elif value == 9:
            return 'Please re-authenticate'
        elif value == 10:
            return 'You must be granted a valid key by last.fm'
        elif value == 11:
            return 'This service is temporarily offline. Try again later.'
        elif value == 13:
            return 'Invalid method signature supplied.'
        elif value == 16:
            return 'There was a temporary error processing your request. Please try again'
        elif value == 26:
            return 'Access for your account has been suspended, please contact Last.fm'
        elif value == 29:
            return 'Your IP has made too many requests in a short period'

class LastfmError(IOError):
    def __init__(self, message, status=None, submsg=None):
        self.status = status
        self.message = message
        self.submsg = submsg

class LastfmNetError(LastfmError): pass
class LastfmTimeout(LastfmError): pass

class LastfmArtScraperPlugin(PithosPlugin):
    preference = 'enable_lastfm_art_scraper'
    description = 'Find missing covers with Last.fm'

    def on_prepare(self):
        self.check_and_reset_corrections_on_error()
        self.preferences_dialog = MissingCoversDialog()
        self.user_agent = '{}/{} ( {} )'.format('Pithos', self.window.version, 'https://pithos.github.io/')
        self.worker = GObjectWorker()

    def on_enable(self):
        corrections_model = self.preferences_dialog.corrections_model
        if not len(corrections_model):
            corrections = self.corrections
            pandora_names = corrections['pandora_names']
            lastfm_names = corrections['lastfm_names']
            pandora_albums = corrections['pandora_albums']
            lastfm_albums = corrections['lastfm_albums']
            artist_blacklist = corrections['artist_blacklist']
            album_blacklist = corrections['album_blacklist']
            album_image_urls = corrections['album_image_urls']
            artist_image_urls = corrections['artist_image_urls']
            for i, pandora_name in enumerate(pandora_names):
                corrections_model.append((pandora_name,
                                          lastfm_names[i],
                                          pandora_albums[i],
                                          lastfm_albums[i],
                                          artist_blacklist[i],
                                          album_blacklist[i],
                                          album_image_urls[i],
                                          artist_image_urls[i]))
     
        self.missing_art_handler = self.window.connect('no-art-url', self.get_lastfm_art)
        self.corrections_change_handler = corrections_model.connect('row-changed', self.sync_corrections_with_model)
        self.corrections_added_handler = corrections_model.connect('row-inserted', self.sync_corrections_with_model)

    def check_and_reset_corrections_on_error(self):
        corrections = self.corrections
        if corrections is None:
            self.corrections = {'pandora_names': [],
                                'lastfm_names': [],
                                'pandora_albums': [],
                                'lastfm_albums': [],
                                'artist_blacklist': [],
                                'album_blacklist': [],
                                'album_image_urls': [],
                                'artist_image_urls': [],
                               }
        else:
            try:
                pandora_names = corrections['pandora_names']
                lastfm_names = corrections['lastfm_names']
                pandora_albums = corrections['pandora_albums']
                lastfm_albums = corrections['lastfm_albums']
                artist_blacklist = corrections['artist_blacklist']
                album_blacklist = corrections['album_blacklist']
                album_image_urls = corrections['album_image_urls']
                artist_image_urls = corrections['artist_image_urls']

            except KeyError:
                self.corrections = {'pandora_names': [],
                                    'artist_blacklist': [],
                                    'lastfm_names': [],
                                    'pandora_albums': [],
                                    'album_blacklist': [],
                                    'lastfm_albums': [],
                                    'album_image_urls': [],
                                    'artist_image_urls': [],
                                   }

    def on_disable(self):
        self.window.disconnect(self.missing_art_handler)
        self.preferences_dialog.corrections_model.disconnect(self.corrections_change_handler)
        self.preferences_dialog.corrections_model.disconnect(self.corrections_added_handler)

    @property
    def corrections(self):
        data = self.settings['data']
        if data:
            return json.loads(data)
        return None

    @corrections.setter
    def corrections(self, corrections_dict):
        self.settings['data'] = json.dumps(corrections_dict)

    def sync_corrections_with_model(self, model, *ignore):
        self.corrections = {'pandora_names': [path[0] for path in model],
                            'lastfm_names': [path[1] for path in model],
                            'pandora_albums': [path[2] for path in model],
                            'lastfm_albums': [path[3] for path in model],
                            'artist_blacklist': [path[4] for path in model],
                            'album_blacklist': [path[5] for path in model],
                            'album_image_urls': [path[6] for path in model],
                            'artist_image_urls': [path[7] for path in model], 
        }

    def get_lastfm_art(self, window, data):
        def set_art(lastfm):
            art_url = lastfm.album_image_url or lastfm.artist_image_url
            blacklist_artist = lastfm.blacklist_artist
            blacklist_album = lastfm.blacklist_album
            if art_url:
                self.worker.send(get_album_art, (art_url, window.tempdir, song, song.index), art_callback)
            elif not art_url and not blacklist_artist and not blacklist_album:
                logging.info('No matching artist or album image found for {} {} at Last.fm'.format(pandora_artist, pandora_album))
            self.preferences_dialog.add_correction(pandora_artist,
                                                   lastfm.artist,
                                                   pandora_album,
                                                   lastfm.album,
                                                   blacklist_artist,
                                                   blacklist_album,
                                                   lastfm.album_image_url,
                                                   lastfm.artist_image_url)

        get_album_art, song, art_callback = data
        pandora_artist = song.artist.strip()
        pandora_album = song.album.strip()
        self.worker.send(LastFmArt, (self.user_agent, pandora_artist, pandora_album, self.corrections), set_art)

class LastFmArt:
    LASTFM_ALBUM_SEARCH = ('http://ws.audioscrobbler.com/2.0/'
                           '?method=album.search'
                           '&api_key=997f635176130d5d6fe3a7387de601a8'
                           '&album={}&limit=50&format=json')

    LASTFM_ARTIST_SEARCH = ('http://ws.audioscrobbler.com/2.0/'
                            '?method=artist.search'
                            '&api_key=997f635176130d5d6fe3a7387de601a8'
                            '&artist={}&limit=50&format=json')

    LASTFM_ALBUM_INFO = ('http://ws.audioscrobbler.com/2.0/'
                         '?method=album.getinfo'
                         '&api_key=997f635176130d5d6fe3a7387de601a8'
                         '&artist={}&album={}&autocorrect=1&format=json')

    LASTFM_ARTIST_INFO = ('http://ws.audioscrobbler.com/2.0/'
                          '?method=artist.getinfo'
                          '&api_key=997f635176130d5d6fe3a7387de601a8'
                          '&artist={}&autocorrect=1&format=json')

    def __init__(self, user_agent, artist, album, corrections):
        self.user_agent = user_agent
        self._artist = artist
        self._album = album
        self.corrections = corrections
        self.artist = ''
        self.album = ''
        self.artist_image_url = ''
        self.album_image_url = ''
        self.blacklist_artist = False
        self.blacklist_album = False
        self.variations = Variations()
        self.get_art()

    def get_art(self):
        self.get_cached_info()
        if self.album_image_url or self.blacklist_artist:
            return 
        self.get_remote_album_image_url()
        if self.album_image_url:
            return
        artist_variations = self.variations.generate(self.artist, self._artist)
        artist_variations = self.artist_search(artist_variations)
        if not self.blacklist_album:
            album_variations = self.variations.generate(self.album, self._album)
            self.album_search(artist_variations, album_variations)
        if self.album_image_url or self.artist_image_url:
            return
        self.get_remote_artist_image_url(artist_variations)

    def get_cached_info(self):
        corrections = self.corrections
        _artist = self._artist
        _album = self._album
        pandora_names = corrections['pandora_names']
        lastfm_names = corrections['lastfm_names']
        pandora_albums = corrections['pandora_albums']
        lastfm_albums = corrections['lastfm_albums']
        artist_blacklist = corrections['artist_blacklist']
        album_blacklist = corrections['album_blacklist']
        album_image_urls = corrections['album_image_urls']
        artist_image_urls = corrections['artist_image_urls']
        for i, pandora_name in enumerate(pandora_names):
            if _artist == pandora_name:
                self.blacklist_artist = artist_blacklist[i]
                if self.blacklist_artist:
                    logging.info('Artist is blacklisted: {}'.format(_artist))
                    return
                if _album == pandora_albums[i]:
                    self.artist = lastfm_names[i]
                    artist_url = artist_image_urls[i]
                    if self.image_url_is_still_valid(artist_url):
                        self.artist_image_url = artist_url
                        logging.info('Found cached artist image url for {}'.format(_artist))
                    self.blacklist_album = album_blacklist[i]
                    if self.blacklist_album:
                        logging.info('Album is blacklisted: {} {}'.format(_artist, _album))
                        return
                    self.album = lastfm_albums[i]
                    album_url = album_image_urls[i]
                    if self.image_url_is_still_valid(album_url):
                        self.album_image_url = album_url
                        logging.info('Found cached album cover url for {} {}'.format(_artist, _album))
                return 

    def artist_search(self, artist_variations):
        artist_names = []
        for artist_variation in artist_variations:
            lastfm_response = self.api_call(self.LASTFM_ARTIST_SEARCH.format(urllib.parse.quote_plus(artist_variation)))
            artists = lastfm_response.get('results', {}).get('artistmatches', {}).get('artist', [{}])
            for artist in artists:
                name = artist.get('name', '').strip()
                if name:
                    artist_names.append(name)
                    for artist_v in artist_variations:
                        if name == artist_v and not self.artist_image_url:
                            self.artist_image_url = self.get_image_url(artist.get('image', []))
                            if self.artist_image_url:
                                self.artist = name
                                logging.info('Found matching artist: {}'.format(name))

        artist_variations = self.variations.remove_dups(artist_variations + artist_names)
        return artist_variations

    def album_search(self, artist_variations, album_variations):
        for album_variation in album_variations:
            lastfm_response = self.api_call(self.LASTFM_ALBUM_SEARCH.format(urllib.parse.quote_plus(album_variation)))
            album_matches = lastfm_response.get('results', {}).get('albummatches', {}).get('album', [])
            for album in album_matches:
                artist_name = album.get('artist', '').strip()
                album_name = album.get('name', '').strip()
                for artist_v in artist_variations:
                    if artist_name == artist_v:
                        for album_v in album_variations:
                            if album_name == album_v:
                                self.album_image_url = self.get_image_url(album.get('image', []))
                                if self.album_image_url:
                                    self.artist = artist_name
                                    self.album = album_name
                                    logging.info('Best album match found: {} {}'.format(artist_name, album_name))
                                    return

    def get_remote_album_image_url(self):
        if not self.artist or not self.album:
            return ''
        artist = urllib.parse.quote_plus(self.artist)
        album = urllib.parse.quote_plus(self.album)
        lastfm_response = self.api_call(self.LASTFM_ALBUM_INFO.format(artist, album))
        self.album_image_url = self.get_image_url(lastfm_response.get('album', {}).get('image', []))

    def get_remote_artist_image_url(self, artist_variations):
        for artist_variation in artist_variations:
            lastfm_response = self.api_call(self.LASTFM_ARTIST_INFO.format(urllib.parse.quote_plus(artist_variation)))
            artist_name = lastfm_response.get('artist', {}).get('name', '').strip()
            if artist_name == artist_variation:
                self.artist_image_url = self.get_image_url(lastfm_response.get('artist', {}).get('image', []))
                if self.artist_image_url:
                    logging.info('Best artist match found: {}'.format(artist))
                    self.artist = artist_name
                    return

    def get_image_url(self, images):
        if not images:
            return ''
        images.reverse()
        for image in images:
            size = image['size']
            image_url = image['#text']
            if image_url and size in ('large', 'extralarge'):
                return image_url
        return ''

    def api_call(self, call):
        request = urllib.request.Request(call)
        request.add_header('User-Agent', self.user_agent)
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                lastfm_response = json.loads(response.read().decode('utf-8'))

            error = lastfm_response.get('error')
            if error is not None:
                error = LastfmErrorCode(int(error))
                message = lastfm_response.get('message', 'No Message')
                error_code_message = 'Error: {} ErrorCode Message: {}'.format(error, error.message)
                api_message = 'API Request: {} API Response: {}: '.format(call, message)
                logging.debug(error_code_message)
                logging.debug(api_message)
                return {}

            return lastfm_response

        except urllib.error.HTTPError as e:
            logging.error('HTTP error: {}'.format(e))
            raise LastfmNetError(str(e))
        except urllib.error.URLError as e:
            logging.error('Network error: {}'.format(e))
            if e.reason.strerror == 'timed out':
                raise LastfmTimeout('Network error', submsg='Timeout')
            else:
                raise LastfmNetError('Network error', submsg=e.reason.strerror)

        return {}

    def image_url_is_still_valid(self, url):
        if not url:
            return False
        request = urllib.request.Request(url)
        request.add_header('User-Agent', self.user_agent)
        request.get_method = lambda: 'HEAD'
        try:
            with urllib.request.urlopen(request, timeout=30) as response:
                validity_check = response
            status_code = validity_check.code
            maintype = validity_check.headers['Content-Type'].split(';')[0].lower()

            if status_code != 200:
                logging.debug('The status code did not indicate OK. Status code: {}'.format(status_code))
                return False
            elif maintype not in ('image/png', 'image/jpeg', 'image/gif'):
                logging.debug('The url content is of the wrong type. Content-Type: {}'.format(maintype))
                return False
            else:
                logging.debug('The Last.fm image Url is valid')
                return True

        except Exception as e:
            logging.debug('An Exception occurred while trying to validate the Last.fm image url: {}'.format(e))
            return False

class Variations:
    OPENING_BRACKETS = '([{'

    SUFFIXES = [' - EP', ' - ep', ' - Ep',' - LP', ' - lp', ' - Lp',
                ' EP', ' ep', ' Ep', ' LP', ' lp', ' Lp', ' (single)', ' (Single)']

    def __init__(self):
        pass

    def generate(self, corrected_item, item):
        # Generate a list of variations
        # to broaden our search net. Pandora artist names
        # and album titles don't always line up with
        # Last.fm artist names and album titles.
        # Any duplications will be removed.
        item = self.check_for_overrides(item)
        replaced_pipe = self.replace_pipe(item)
        stripped_pipe = self.strip_pipe(item)
        minus_suffixes = self.strip_suffixes(item)
        minus_punctuation = self.remove_punctuation(item)
        minus_suffixes_replaced_pipe = self.replace_pipe(minus_suffixes)
        minus_suffixes_stripped_pipe = self.strip_pipe(minus_suffixes)
        minus_suffixes_and_punctuation = self.remove_punctuation(minus_suffixes)
        cleaned = self.clean_text(item)
        cleaned_replaced_pipe = self.replace_pipe(cleaned)
        cleaned_stripped_pipe = self.strip_pipe(cleaned)
        cleaned_minus_punctuation = self.remove_punctuation(cleaned)

        variations = self.remove_dups([corrected_item,
                                       item,
                                       replaced_pipe,
                                       stripped_pipe,
                                       minus_punctuation,
                                       minus_suffixes,
                                       minus_suffixes_replaced_pipe,
                                       minus_suffixes_stripped_pipe,
                                       minus_suffixes_and_punctuation,
                                       cleaned,
                                       cleaned_replaced_pipe,
                                       cleaned_stripped_pipe,
                                       cleaned_minus_punctuation])

        return variations

    @staticmethod
    def remove_dups(old_list):
        return [item for index, item in enumerate(old_list) if item not in old_list[0:index] and item]

    def check_for_overrides(self, text):
        # Manual overrides.
        if text == 'Skrillex & Diplo':
            return 'Jack Ü'
        elif text == 'Pink':
            return 'P!nk'
        else:
            return text

    def strip_pipe(self, text):
        text = text.replace('|', '')
        text = text.replace('  ', ' ')
        return text.strip()

    def replace_pipe(self, text):
        return text.replace('|', '/').strip()

    def remove_punctuation(self, text):
        for mark in punctuation:
            text = text.replace(mark, '')
            text = text.replace('  ', ' ')
        return text.strip()

    def strip_suffixes(self, text):
        for suffix in self.SUFFIXES:                    
            if text.endswith(suffix):
                text = text[:len(text) - len(suffix)]
        return text.strip()

    def clean_text(self, text):
        for bracket in self.OPENING_BRACKETS:
            bracket = text.find(bracket)
            if bracket != -1:
                text = text[:bracket]
        return text.strip()

@GtkTemplate(ui='/io/github/Pithos/ui/MissingCoversDialog.ui')
class MissingCoversDialog(Gtk.Dialog):
    __gtype_name__ = 'MissingCoversDialog'

    treeview = GtkTemplate.Child()
    treeview_menu = GtkTemplate.Child()
    corrections_model = GtkTemplate.Child()
    model_filter = GtkTemplate.Child()
    model_sort = GtkTemplate.Child()
    lastfm_search_menu_item = GtkTemplate.Child()
    artist_album_search_entry = GtkTemplate.Child()
    lastfm_artist_name_column = GtkTemplate.Child()
    lastfm_album_title_column = GtkTemplate.Child()
    lastfm_artist_name_cellrender_text = GtkTemplate.Child()
    lastfm_album_title_cellrender_text = GtkTemplate.Child()

    LAST_FM_SEARCH = 'http://www.last.fm/search?q={}'
    LAST_FM_SEARCH_LABEL = 'Search Last.fm for {}'
 
    def __init__(self):
        super().__init__()
        self.init_template()
        self.clipboard = Gtk.Clipboard.get(Gdk.SELECTION_CLIPBOARD)
        self.lastfm_artist_name_column.set_cell_data_func(self.lastfm_artist_name_cellrender_text, self.lastfm_artist_cell_data_func)
        self.lastfm_album_title_column.set_cell_data_func(self.lastfm_album_title_cellrender_text, self.lastfm_album_cell_data_func)
        self.model_filter.set_visible_func(self.visible_cb)

    @GtkTemplate.Callback
    def on_close(self, *ignore):
        self.hide()
        self.artist_album_search_entry.set_text('')

    @GtkTemplate.Callback
    def on_artist_album_search_entry_search_changed(self, *ignore):
        self.model_filter.refilter() 

    @GtkTemplate.Callback
    def on_lastfm_artist_name_cellrender_text_edited(self, cellrenderertext, path, new_text):
        path = self.model_sort.convert_path_to_child_path(Gtk.TreePath(path))
        self.lastfm_artist_album_changed(path, new_text, 1, 7)

    @GtkTemplate.Callback
    def on_lastfm_album_title_cellrender_text_edited(self, cellrenderertext, path, new_text):
        path = self.model_sort.convert_path_to_child_path(Gtk.TreePath(path))
        self.lastfm_artist_album_changed(path, new_text, 3, 6)

    @GtkTemplate.Callback
    def on_lastfm_search_button_press_event(self, menu_item, event):
        if event.button == 1:
            url = self.LAST_FM_SEARCH.format(urllib.parse.quote_plus(self.get_selected_text()))
            open_browser(url, self, event.time)
        return True

    @GtkTemplate.Callback
    def on_artist_blacklist_toggled(self, cellrenderertext, path):
        filter_path = self.model_sort.convert_path_to_child_path(Gtk.TreePath(path))
        blacklist = not self.corrections_model[self.model_filter.convert_path_to_child_path(Gtk.TreePath(filter_path))][4]
        artist_name = self.corrections_model[self.model_filter.convert_path_to_child_path(Gtk.TreePath(filter_path))][0]
        for path in self.corrections_model:
            pandora_name = path[0]
            if artist_name == pandora_name:
                path[4] = blacklist 

    @GtkTemplate.Callback
    def on_album_blacklist_toggled(self, cellrenderertext, path):
        filter_path = self.model_sort.convert_path_to_child_path(Gtk.TreePath(path))
        blacklist = not self.corrections_model[self.model_filter.convert_path_to_child_path(Gtk.TreePath(filter_path))][5]
        self.corrections_model[self.model_filter.convert_path_to_child_path(Gtk.TreePath(filter_path))][5] = blacklist

    @GtkTemplate.Callback
    def on_copy_menu_item_button_press_event(self, menu_item, event):
        # Copy from both editable and uneditable cellrender_texts.
        if event.button == 1:
            self.clipboard.set_text(self.get_selected_text(), -1)
        return True
 
    @GtkTemplate.Callback
    def on_treeview_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor(path, col, False)
                if not self.is_blacklisted(path, col) and not col.get_sort_column_id() in (4, 5):
                    selected_text = self.get_selected_text()
                    if selected_text:    
                        self.lastfm_search_menu_item.set_property('label', self.LAST_FM_SEARCH_LABEL.format(selected_text)) 
                        self.treeview_menu.popup(None, None, None, None, event.button, time)
            return True

    def visible_cb(self, model, iter, data=None):
        search_query = self.artist_album_search_entry.get_text().lower()
        if search_query == '':
            return True
        path = model.get_path(iter)
        for col in range(self.treeview.get_n_columns()):
            if col in (4, 5):
                return False
            if self.is_blacklisted(path, col):
                return False
            value = model.get_value(iter, col).lower()
            if value.startswith(search_query):
                return True
            for word in value.split():
                if word.startswith(search_query):
                    return True
        return False

    def lastfm_artist_cell_data_func(self, column, cell, model, iter, Data=None):
        if model.get_value(iter, 4):
            cell.set_property('markup', '<b><i>Artist Blacklisted...</i></b>')
            cell.set_property('editable', False)
        else:
            cell.set_property('editable', True)

    def lastfm_album_cell_data_func(self, column, cell, model, iter, Data=None):
        if model.get_value(iter, 5):
            cell.set_property('markup', '<b><i>Album Blacklisted...</i></b>')
            cell.set_property('editable', False)
        else:
            cell.set_property('editable', True)

    def lastfm_artist_album_changed(self, path, new_text, text_col, url_col):
        self.corrections_model[self.model_filter.convert_path_to_child_path(Gtk.TreePath(path))][text_col] = new_text.strip()
        self.corrections_model[self.model_filter.convert_path_to_child_path(Gtk.TreePath(path))][url_col] = '' 

    def get_selected_text(self):
        path, col = self.treeview.get_cursor()
        column_id = col.get_sort_column_id()
        filter_path = self.model_sort.convert_path_to_child_path(Gtk.TreePath(path))
        return self.corrections_model[self.model_filter.convert_path_to_child_path(Gtk.TreePath(filter_path))][column_id]

    def is_blacklisted(self, path, col):
        if isinstance(col, int):
            column_id = col
        else:
            column_id = col.get_sort_column_id()
            path = self.model_sort.convert_path_to_child_path(Gtk.TreePath(path))
        if column_id in (1, 3):
            if column_id == 1:
                column_id = 4
            else:
                column_id = 5
            return self.corrections_model[path][column_id]
        return False

    def add_correction(self, pandora_artist, lastfm_artist, pandora_album, lastfm_album,
                       blacklist_artist, blacklist_album, lastfm_album_image_url, lastfm_artist_image_url):

        for path in self.corrections_model:
            cached_pandora_artist = path[0]
            cached_pandora_album = path[2]
            if cached_pandora_artist == pandora_artist:
                path[4] = blacklist_artist
                if cached_pandora_album == pandora_album:
                    path[1] = lastfm_artist 
                    path[5] = blacklist_album
                    path[3] = lastfm_album
                    path[6] = lastfm_album_image_url
                    path[7] = lastfm_artist_image_url
                    return

        self.corrections_model.append((pandora_artist,
                                       lastfm_artist,
                                       pandora_album,
                                       lastfm_album,
                                       blacklist_artist,
                                       blacklist_album,
                                       lastfm_album_image_url,
                                       lastfm_artist_image_url))
