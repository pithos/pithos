# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
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

import contextlib
import html
import json
import logging
import math
import os
import re
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from gettext import gettext as _

import gi
gi.require_version('Gst', '1.0')
gi.require_version('GstPbutils', '1.0')
from gi.repository import Gst, GstPbutils, GObject, Gtk, Gdk, Pango, GdkPixbuf, Gio, GLib
from .gi_composites import GtkTemplate

if Gtk.get_major_version() < 3 or Gtk.get_minor_version() < 14:
    sys.exit('Gtk 3.14 is required')

from . import AboutPithosDialog, PreferencesPithosDialog, StationsDialog
from .StationsPopover import StationsPopover
from .gobject_worker import GObjectWorker
from .pandora import *
from .pandora.data import *
from .plugin import load_plugins
from .util import parse_proxy, open_browser, get_account_password

try:
    import pacparser
except ImportError:
    pacparser = None

ALBUM_ART_SIZE = 96
TEXT_X_PADDING = 12

class CellRendererAlbumArt(Gtk.CellRenderer):
    def __init__(self):
        super().__init__(height=ALBUM_ART_SIZE, width=ALBUM_ART_SIZE)
        self.icon = None
        self.pixbuf = None
        self.rate_bg = Gtk.IconTheme.get_default().load_icon('pithos-rate-bg', 32, 0)

    __gproperties__ = {
        'icon': (str, 'icon', 'icon', '', GObject.ParamFlags.READWRITE),
        'pixbuf': (GdkPixbuf.Pixbuf, 'pixmap', 'pixmap',  GObject.ParamFlags.READWRITE)
    }

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
    def do_get_property(self, pspec):
        return getattr(self, pspec.name)
    def do_render(self, ctx, widget, background_area, cell_area, flags):
        if self.pixbuf:
            Gdk.cairo_set_source_pixbuf(ctx, self.pixbuf, cell_area.x, cell_area.y)
            ctx.paint()
        if self.icon:
            x = cell_area.x + (cell_area.width - self.rate_bg.get_width()) # right
            y = cell_area.y + (cell_area.height - self.rate_bg.get_height()) # bottom
            Gdk.cairo_set_source_pixbuf(ctx, self.rate_bg, x, y)
            ctx.paint()

            pixbuf = Gtk.IconTheme.get_default().load_icon(self.icon, Gtk.IconSize.MENU, 0)
            x = cell_area.x + (cell_area.width - pixbuf.get_width()) - 5 # right
            y = cell_area.y + (cell_area.height - pixbuf.get_height()) - 5 # bottom
            Gdk.cairo_set_source_pixbuf(ctx, pixbuf, x, y)
            ctx.paint()

class PlayerStatus:
  def __init__(self):
    self.reset()

  def reset(self):
    self.began_buffering = None
    self.buffer_percent = 0


@GtkTemplate(ui='/io/github/Pithos/ui/PithosWindow.ui')
class PithosWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "PithosWindow"
    __gsignals__ = {
        "song-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "song-ended": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "play-state-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
        "user-changed-play-state": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
        "metadata-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "buffering-finished": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "no-art-url": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    volume = GtkTemplate.Child()
    playpause_image = GtkTemplate.Child()
    statusbar = GtkTemplate.Child()
    song_menu = GtkTemplate.Child()
    song_menu_love = GtkTemplate.Child()
    song_menu_unlove = GtkTemplate.Child()
    song_menu_ban = GtkTemplate.Child()
    song_menu_unban = GtkTemplate.Child()
    songs_treeview = GtkTemplate.Child()
    stations_button = GtkTemplate.Child()
    stations_label = GtkTemplate.Child()

    api_update_dialog_real = GtkTemplate.Child()
    error_dialog_real = GtkTemplate.Child()
    fatal_error_dialog_real = GtkTemplate.Child()

    def __init__(self, app, test_mode):
        super().__init__(application=app)
        self.init_template()
        self.version = app.version

        self.settings = Gio.Settings.new('io.github.Pithos')
        self.settings.connect('changed::audio-quality', self.set_audio_quality)
        self.settings.connect('changed::proxy', self.set_proxy)
        self.settings.connect('changed::control-proxy', self.set_proxy)
        self.settings.connect('changed::control-proxy-pac', self.set_proxy)
        self.settings.connect('changed::pandora-one', self.pandora_reconnect)

        self.prefs_dlg = PreferencesPithosDialog.PreferencesPithosDialog(transient_for=self)
        self.prefs_dlg.connect_after('response', self.on_prefs_response)
        self.prefs_dlg.connect('login-changed', self.pandora_reconnect)

        self.init_core()
        self.init_ui()
        self.init_actions(app)

        self.plugins = {}
        load_plugins(self)
        self.prefs_dlg.set_plugins(self.plugins)

        self.pandora = make_pandora(test_mode)
        self.set_proxy(reconnect=False)
        self.set_audio_quality()

        email = self.settings['email']
        try:
            password = get_account_password(email)
        except GLib.Error as e:
            if e.code == 2:
                self.fatal_error_dialog(e.message, _('You need to install a service such as gnome-keyring.'))
        else:
            if not email or not password:
                self.show()
                self.show_preferences()
            else:
                self.pandora_connect()

    def init_core(self):
        #                                Song object            display text  icon  album art
        self.songs_model = Gtk.ListStore(GObject.TYPE_PYOBJECT, str,          str,  GdkPixbuf.Pixbuf)
        #                                   Station object         station name  index
        self.stations_model = Gtk.ListStore(GObject.TYPE_PYOBJECT, str,          int)

        Gst.init(None)
        self._query_duration = Gst.Query.new_duration(Gst.Format.TIME)
        self._query_position = Gst.Query.new_position(Gst.Format.TIME)
        self.player = Gst.ElementFactory.make("playbin", "player")

        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message::stream-start", self.on_gst_stream_start)
        bus.connect("message::eos", self.on_gst_eos)
        bus.connect("message::buffering", self.on_gst_buffering)
        bus.connect("message::error", self.on_gst_error)
        bus.connect("message::element", self.on_gst_element)
        self.player.connect("notify::volume", self.on_gst_volume)
        self.player.connect("notify::source", self.on_gst_source)

        self.player_status = PlayerStatus()

        self.stations_dlg = None

        self.playing = None # None is a special "Waiting to play" state
        self.current_song_index = None
        self.current_station = None
        self.current_station_id = self.settings['last-station-id']

        self.filter_state = None
        self.auto_retrying_auth = False
        self.have_stations = False
        self.playcount = 0
        self.gstreamer_errorcount_1 = 0
        self.gstreamer_errorcount_2 = 0
        self.gstreamer_error = ''
        self.waiting_for_playlist = False
        self.start_new_playlist = False
        self.ui_loop_timer_id = 0
        self.worker = GObjectWorker()
        self.art_worker = GObjectWorker()

        theme = Gtk.IconTheme.get_default()
        aa = theme.load_icon('pithos-album-default', 128, 0)

        self.default_album_art = aa.scale_simple(ALBUM_ART_SIZE, ALBUM_ART_SIZE, GdkPixbuf.InterpType.BILINEAR)

        try:
            self.tempdir = tempfile.TemporaryDirectory(prefix='pithos-')
            logging.info("Created temporary directory %s" %self.tempdir.name)
        except IOError as e:
            self.tempdir = None
            logging.warning('Failed to create a temporary directory')

    def init_ui(self):
        GLib.set_application_name("Pithos")
        Gtk.Window.set_default_icon_name('pithos')
        os.environ['PULSE_PROP_media.role'] = 'music'

        self.volume.set_relief(Gtk.ReliefStyle.NORMAL)  # It ignores glade...
        self.settings.bind('volume', self.volume, 'value', Gio.SettingsBindFlags.DEFAULT)

        self.songs_treeview.set_model(self.songs_model)

        title_col   = Gtk.TreeViewColumn()

        render_icon = CellRendererAlbumArt()
        title_col.pack_start(render_icon, False)
        title_col.add_attribute(render_icon, "icon", 2)
        title_col.add_attribute(render_icon, "pixbuf", 3)

        render_text = Gtk.CellRendererText(xpad=TEXT_X_PADDING)
        render_text.props.ellipsize = Pango.EllipsizeMode.END
        title_col.pack_start(render_text, True)
        title_col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        title_col.add_attribute(render_text, "markup", 1)

        self.songs_treeview.append_column(title_col)

        self.songs_treeview.connect('button_press_event', self.on_treeview_button_press_event)

        self.stations_popover = StationsPopover()
        self.stations_popover.set_relative_to(self.stations_button)
        self.stations_popover.set_model(self.stations_model)
        self.stations_popover.listbox.connect('row-activated', self.active_station_changed)
        self.stations_button.set_popover(self.stations_popover)

        self.set_initial_pos()

    def init_actions(self, app):
        action = Gio.SimpleAction.new('playpause', None)
        self.add_action(action)
        app.add_accelerator('space', 'win.playpause', None)
        action.connect('activate', self.user_playpause)

        action = Gio.SimpleAction.new('playselected', None)
        self.add_action(action)
        app.add_accelerator('Return', 'win.playselected', None)
        action.connect('activate', self.start_selected_song)

        action = Gio.SimpleAction.new('songinfo', None)
        self.add_action(action)
        app.add_accelerator('<Primary>i', 'win.songinfo', None)
        action.connect('activate', self.info_song)

        action = Gio.SimpleAction.new('volumeup', None)
        self.add_action(action)
        app.add_accelerator('<Primary>Up', 'win.volumeup', None)
        action.connect('activate', self.volume_up)

        action = Gio.SimpleAction.new('volumedown', None)
        self.add_action(action)
        app.add_accelerator('<Primary>Down', 'win.volumedown', None)
        action.connect('activate', self.volume_down)

        action = Gio.SimpleAction.new('skip', None)
        self.add_action(action)
        app.add_accelerator('<Primary>Right', 'win.skip', None)
        action.connect('activate', self.next_song)

        action = Gio.SimpleAction.new('love', None)
        self.add_action(action)
        app.add_accelerator('<Primary>l', 'win.love', None)
        action.connect('activate', self.love_song)

        action = Gio.SimpleAction.new('ban', None)
        self.add_action(action)
        app.add_accelerator('<Primary>b', 'win.ban', None)
        action.connect('activate', self.ban_song)

        action = Gio.SimpleAction.new('tired', None)
        self.add_action(action)
        app.add_accelerator('<Primary>t', 'win.tired', None)
        action.connect('activate', self.tired_song)

        action = Gio.SimpleAction.new('unrate', None)
        self.add_action(action)
        app.add_accelerator('<Primary>u', 'win.unrate', None)
        action.connect('activate', self.unrate_song)

        action = Gio.SimpleAction.new('bookmark', None)
        self.add_action(action)
        app.add_accelerator('<Primary>d', 'win.bookmark', None)
        action.connect('activate', self.bookmark_song)

    def worker_run(self, fn, args=(), callback=None, message=None, context='net'):
        if context and message:
            self.statusbar.push(self.statusbar.get_context_id(context), message)

        if isinstance(fn,str):
            fn = getattr(self.pandora, fn)

        def cb(v):
            if context: self.statusbar.pop(self.statusbar.get_context_id(context))
            if callback: callback(v)

        def eb(e):
            if context and message:
                self.statusbar.pop(self.statusbar.get_context_id(context))

            def retry_cb():
                self.auto_retrying_auth = False
                if fn is not self.pandora.connect:
                    self.worker_run(fn, args, callback, message, context)

            if isinstance(e, PandoraAuthTokenInvalid) and not self.auto_retrying_auth:
                self.auto_retrying_auth = True
                logging.info("Automatic reconnect after invalid auth token")
                self.pandora_connect("Reconnecting...", retry_cb)
            elif isinstance(e, PandoraAPIVersionError):
                self.api_update_dialog()
            elif isinstance(e, PandoraError):
                self.error_dialog(e.message, retry_cb, submsg=e.submsg)
            else:
                logging.warning(e.traceback)

        self.worker.send(fn, args, cb, eb)

    def get_proxy(self):
        """ Get HTTP proxy, first trying preferences then system proxy """

        proxy = self.settings['proxy']
        if proxy:
            return proxy

        system_proxies = urllib.request.getproxies()
        if 'http' in system_proxies:
            return system_proxies['http']

        return None

    def on_explicit_content_filter_checkbox(self, *ignore):
        if self.pandora.connected:
            current_checkbox_state = self.prefs_dlg.explicit_content_filter_checkbutton.get_active()

            def set_content_filter(current_state):
                self.pandora.set_explicit_content_filter(current_state)

            def get_new_playlist(*ignore):
                if current_checkbox_state:
                    logging.info('Getting a new playlist.')
                    self.waiting_for_playlist = False
                    self.stop()
                    self.current_song_index = None
                    self.songs_model.clear()
                    self.get_playlist(start = True)

            if self.filter_state is not None and self.filter_state != current_checkbox_state:
                self.worker_run(set_content_filter, (current_checkbox_state, ), get_new_playlist)

    def set_proxy(self, *ignore, reconnect=True):
        # proxy preference is used for all Pithos HTTP traffic
        # control proxy preference is used only for Pandora traffic and
        # overrides proxy
        #
        # If neither option is set, urllib2.build_opener uses urllib.getproxies()
        # by default

        handlers = []
        global_proxy = self.settings['proxy']
        if global_proxy:
            handlers.append(urllib.request.ProxyHandler({'http': global_proxy, 'https': global_proxy}))
        global_opener = pandora.Pandora.build_opener(*handlers)
        urllib.request.install_opener(global_opener)

        control_opener = global_opener
        control_proxy = self.settings['control-proxy']
        control_proxy_pac = self.settings['control-proxy-pac']

        if not control_proxy and (control_proxy_pac and pacparser):
            pacparser.init()
            with urllib.request.urlopen(control_proxy_pac) as f:
                pacstring = f.read().decode('utf-8')
                try:
                    pacparser.parse_pac_string(pacstring)
                except pacparser._pacparser.error:
                    logging.warning('Failed to parse PAC.')
            try:
                proxies = pacparser.find_proxy("http://pandora.com", "pandora.com").split(";")
                for proxy in proxies:
                    match = re.search("PROXY (.*)", proxy)
                    if match:
                        control_proxy = match.group(1)
                        break
            except pacparser._pacparser.error:
                logging.warning('Failed to find proxy via PAC.')
            pacparser.cleanup()
        elif not control_proxy and (control_proxy_pac and not pacparser):
            logging.warning("Disabled proxy auto-config support because python-pacparser module was not found.")

        if control_proxy:
            control_opener = pandora.Pandora.build_opener(urllib.request.ProxyHandler({'http': control_proxy, 'https': control_proxy}))

        self.worker_run('set_url_opener', (control_opener,), self.pandora_connect if reconnect else None)

    def set_audio_quality(self, *ignore):
        self.worker_run('set_audio_quality', (self.settings['audio-quality'],))

    def pandora_connect(self, *ignore, message="Logging in...", callback=None):
        if self.settings['pandora-one']:
            client = client_keys[default_one_client_id]
        else:
            client = client_keys[default_client_id]

        # Allow user to override client settings
        force_client = self.settings['force-client']
        if force_client in client_keys:
            client = client_keys[force_client]
        elif force_client and force_client[0] == '{':
            try:
                client = json.loads(force_client)
            except json.JSONDecodeError:
                logging.error("Could not parse force_client json")


        email = self.settings['email']
        password = get_account_password(email)
        if not email or not password:
            # You probably shouldn't be able to reach here
            # with no credentials set
            logging.error('No email or no password set!')
            self.quit()

        args = (
            client,
            email,
            password,
        )

        def pandora_ready(*ignore):
            logging.info("Pandora connected")
            self.process_stations(self)
            if callback:
                callback()

        self.worker_run('connect', args, pandora_ready, message, 'login')

    def pandora_reconnect(self, *ignore):
        ''' Stop everything and reconnect '''
        self.stop()
        self.waiting_for_playlist = False
        self.current_song_index = None
        self.start_new_playlist = False
        self.current_station = None
        self.current_station_id = None
        self.have_stations = False
        self.playcount = 0
        self.songs_model.clear()
        self.pandora_connect()

    def sync_explicit_content_filter_setting(self, *ignore):
        #reset checkbox to default state
        self.prefs_dlg.explicit_content_filter_checkbutton.set_label(_('Explicit Content Filter'))
        self.prefs_dlg.explicit_content_filter_checkbutton.set_sensitive(False)
        self.prefs_dlg.explicit_content_filter_checkbutton.set_active(False)
        self.prefs_dlg.explicit_content_filter_checkbutton.set_inconsistent(True)
        self.filter_state = None

        if self.pandora.connected:
            def get_filter_and_pin_protected_state(*ignore):
                return self.pandora.explicit_content_filter_state

            def sync_checkbox(current_state):
                self.filter_state, pin_protected = current_state[0], current_state[1]
                self.prefs_dlg.explicit_content_filter_checkbutton.set_inconsistent(False)
                self.prefs_dlg.explicit_content_filter_checkbutton.set_active(self.filter_state)
                if pin_protected:
                    self.prefs_dlg.explicit_content_filter_checkbutton.set_label(_('Explicit Content Filter - PIN Protected'))
                else:
                    self.prefs_dlg.explicit_content_filter_checkbutton.set_sensitive(True)

            self.worker_run(get_filter_and_pin_protected_state, (), sync_checkbox)

    def process_stations(self, *ignore):
        self.stations_model.clear()
        self.stations_popover.clear()
        self.current_station = None
        selected = None

        for i, s in enumerate(self.pandora.stations):
            if s.isQuickMix and s.isCreator:
                self.stations_model.append((s, "QuickMix", i))
            else:
                self.stations_model.append((s, s.name, i))
            if s.id == self.current_station_id:
                logging.info("Restoring saved station: id = %s"%(s.id))
                selected = s
        if not selected and len(self.stations_model):
            selected=self.stations_model[0][0]
        if selected:
            self.station_changed(selected, reconnecting = self.have_stations)
            self.have_stations = True
        else:
            # User has no stations, open dialog
            self.show_stations()

    @property
    def current_song(self):
        if self.current_song_index is not None:
            return self.songs_model[self.current_song_index][0]

    def start_song(self, song_index):
        songs_remaining = len(self.songs_model) - song_index

        if songs_remaining <= 0:
            # We don't have this song yet. Get a new playlist.
            return self.get_playlist(start = True)
        elif songs_remaining == 1:
            # Preload next playlist so there's no delay
            self.get_playlist()

        prev = self.current_song

        self.stop()
        self.current_song_index = song_index

        if prev:
            self.update_song_row(prev)

        if not self.current_song.is_still_valid():
            self.current_song.message = "Playlist expired"
            self.update_song_row()
            return self.next_song()

        if self.current_song.tired or self.current_song.rating == RATE_BAN:
            return self.next_song()

        logging.info("Starting song: index = %i"%(song_index))
        self.player_status.reset()

        self.player.set_property("uri", self.current_song.audioUrl)
        self.player.set_state(Gst.State.PAUSED)
        self.playcount += 1

        self.current_song.start_time = time.time()
        self.songs_treeview.scroll_to_cell(song_index, use_align=True, row_align = 1.0)
        self.songs_treeview.set_cursor(song_index, None, 0)
        self.set_title("%s by %s - Pithos" % (self.current_song.title, self.current_song.artist))

        self.emit('song-changed', self.current_song)
        self.emit('metadata-changed', self.current_song)

    @GtkTemplate.Callback
    def next_song(self, *ignore):
        if self.current_song_index is not None:
            self.start_song(self.current_song_index + 1)

    def user_play(self, *ignore):
        self.play()
        self.emit('user-changed-play-state', True)

    def play(self):
        if not self.playing:
            self.playing = True
            self.create_ui_loop()
        self.player.set_state(Gst.State.PLAYING)
        self.playpause_image.set_from_icon_name('media-playback-pause-symbolic', Gtk.IconSize.SMALL_TOOLBAR)
        self.update_song_row()
        self.emit('play-state-changed', True)

    def user_pause(self, *ignore):
        self.pause()
        self.emit('user-changed-play-state', False)

    def pause(self):
        self.playing = False
        self.destroy_ui_loop()
        self.player.set_state(Gst.State.PAUSED)
        self.playpause_image.set_from_icon_name('media-playback-start-symbolic', Gtk.IconSize.SMALL_TOOLBAR)
        self.update_song_row()
        self.emit('play-state-changed', False)


    def stop(self):
        prev = self.current_song
        if prev and prev.start_time:
            prev.finished = True
            prev.position = self.query_position()
            self.emit("song-ended", prev)

        self.playing = None
        self.destroy_ui_loop()
        self.player.set_state(Gst.State.NULL)
        self.emit('play-state-changed', False)

    @GtkTemplate.Callback
    def user_playpause(self, *ignore):
        self.playpause_notify()

    def playpause(self, *ignore):
        logging.info("playpause")
        if self.playing:
            self.pause()
        else:
            self.play()

    def playpause_notify(self, *ignore):
        if self.playing:
            self.user_pause()
        else:
            self.user_play()

    def get_playlist(self, start = False):
        self.start_new_playlist = self.start_new_playlist or start
        if self.waiting_for_playlist: return

        if self.gstreamer_errorcount_1 >= self.playcount and self.gstreamer_errorcount_2 >=1:
            logging.warning("Too many gstreamer errors. Not retrying")
            self.waiting_for_playlist = 1
            self.error_dialog(self.gstreamer_error, self.get_playlist)
            return

        def get_album_art(url, tmpdir, *extra):
            try:
                with urllib.request.urlopen(url) as f:
                    image = f.read()
            except urllib.error.HTTPError:
                logging.warning('Invalid image url received')
                return (None, None,) + extra

            file_url = None
            if tmpdir:
                try:
                    with tempfile.NamedTemporaryFile(prefix='art-', dir=tmpdir.name, delete=False) as f:
                        f.write(image)
                        file_url = urllib.parse.urljoin('file://', urllib.parse.quote(f.name))
                except IOError:
                    logging.warning("Failed to write art tempfile")

            with contextlib.closing(GdkPixbuf.PixbufLoader()) as loader:
                loader.set_size(ALBUM_ART_SIZE, ALBUM_ART_SIZE)
                loader.write(image)
            return (loader.get_pixbuf(), file_url,) + extra

        def art_callback(t):
            pixbuf, file_url, song, index = t
            if index<len(self.songs_model) and self.songs_model[index][0] is song: # in case the playlist has been reset
                logging.info("Downloaded album art for %i"%song.index)
                song.art_pixbuf = pixbuf
                self.songs_model[index][3]=pixbuf
                if file_url:
                    song.artUrl = file_url
                    self.emit('metadata-changed', song)
                self.update_song_row(song)

        def callback(l):
            start_index = len(self.songs_model)
            for i in l:
                i.index = len(self.songs_model)
                self.songs_model.append((i, '', '', self.default_album_art))
                self.update_song_row(i)

                i.art_pixbuf = None
                i.artUrl = None
                if i.artRadio:
                    self.art_worker.send(get_album_art, (i.artRadio, self.tempdir, i, i.index), art_callback)
                else:
                    logging.info("No art url provided by Pandora for %i"%i.index)
                    self.emit('no-art-url', (get_album_art, i, art_callback))

            self.statusbar.pop(self.statusbar.get_context_id('net'))
            if self.start_new_playlist:
                self.start_song(start_index)

            self.gstreamer_errorcount_2 = self.gstreamer_errorcount_1
            self.gstreamer_errorcount_1 = 0
            self.playcount = 0
            self.waiting_for_playlist = False
            self.start_new_playlist = False

        self.waiting_for_playlist = True
        self.worker_run(self.current_station.get_playlist, (), callback, "Getting songs...")

    def error_dialog(self, message, retry_cb, submsg=None):
        dialog = self.error_dialog_real

        dialog.props.text = message
        dialog.props.secondary_text = submsg

        btn = dialog.get_widget_for_response(2)
        if retry_cb is None:
            btn.hide()
        else:
            btn.show()

        response = dialog.run()
        dialog.hide()

        if response == 2:
            self.gstreamer_errorcount_2 = 0
            logging.info("Manual retry")
            return retry_cb()
        elif response == 3:
            self.show_preferences()

    def fatal_error_dialog(self, message, submsg):
        dialog = self.fatal_error_dialog_real
        dialog.props.text = message
        dialog.props.secondary_text = submsg

        dialog.run()
        dialog.hide()

        self.quit()

    def api_update_dialog(self):
        dialog = self.api_update_dialog_real
        response = dialog.run()
        if response:
            open_browser("http://pithos.github.io/itbroke", self)
        self.quit()

    def station_changed(self, station, reconnecting=False):
        if station is self.current_station: return
        self.waiting_for_playlist = False
        if not reconnecting:
            self.stop()
            self.current_song_index = None
            self.songs_model.clear()
        logging.info("Selecting station %s; total = %i" % (station.id, len(self.stations_model)))
        self.current_station_id = station.id
        self.current_station = station
        self.settings.set_string('last-station-id', self.current_station_id)
        if not reconnecting:
            self.get_playlist(start = True)
        self.stations_label.set_text(station.name)
        self.stations_popover.select_station(station)

    def query_position(self):
      pos_stat = self.player.query(self._query_position)
      if pos_stat:
        _, position = self._query_position.parse_position()
        return position

    def query_duration(self):
      dur_stat = self.player.query(self._query_duration)
      if dur_stat:
        _, duration = self._query_duration.parse_duration()
        return duration

    def on_gst_stream_start(self, bus, message):
        # Fallback to using song.trackLength which is in seconds and converted to nanoseconds
        self.current_song.duration = self.query_duration() or self.current_song.trackLength * Gst.SECOND
        self.current_song.duration_message = self.format_time(self.current_song.duration)
        self.check_if_song_is_ad()
        self.emit('metadata-changed', self.current_song)

    def on_gst_eos(self, bus, message):
        logging.info("EOS")
        self.next_song()

    def on_gst_plugin_installed(self, result, userdata):
        if result == GstPbutils.InstallPluginsReturn.SUCCESS:
            self.fatal_error_dialog(_("Codec installation successful"),
                        submsg=_("The required codec was installed, please restart Pithos."))
        else:
            self.error_dialog(_("Codec installation failed"), None,
                        submsg=_("The required codec failed to install. Either manually install it or try another quality setting."))

    def on_gst_element(self, bus, message):
        if GstPbutils.is_missing_plugin_message(message):
            if GstPbutils.install_plugins_supported():
                details = GstPbutils.missing_plugin_message_get_installer_detail(message)
                GstPbutils.install_plugins_async([details,], None, self.on_gst_plugin_installed, None)
            else:
                self.error_dialog(_("Missing codec"), None,
                        submsg=_("GStreamer is missing a plugin and it could not be automatically installed. Either manually install it or try another quality setting."))

    def on_gst_error(self, bus, message):
        err, debug = message.parse_error()
        logging.error("Gstreamer error: %s, %s, %s" % (err, debug, err.code))
        if self.current_song:
            self.current_song.message = "Error: "+str(err)

        self.gstreamer_error = str(err)
        self.gstreamer_errorcount_1 += 1

        if not GstPbutils.install_plugins_installation_in_progress():
            self.next_song()

    def check_if_song_is_ad(self):
        if self.current_song.is_ad is None:
            if self.current_song.duration:
                if self.current_song.get_duration_sec() < 45:  # Less than 45 seconds we assume it's an ad
                    logging.info('Ad detected!')
                    self.current_song.is_ad = True
                    self.update_song_row()
                    self.set_title("Commercial Advertisement - Pithos")
                else:
                    logging.info('Not an Ad..')
                    self.current_song.is_ad = False
            else:
                logging.warning('dur_stat is False. The assumption that duration is available once the stream-start messages feeds is bad.')

    def on_gst_buffering(self, bus, message):
        # per GST documentation:
        # Note that applications should keep/set the pipeline in the PAUSED state when a BUFFERING
        # message is received with a buffer percent value < 100 and set the pipeline back to PLAYING
        # state when a BUFFERING message with a value of 100 percent is received.

        # 100% doesn't mean the entire song is downloaded, but it does mean that it's safe to play.
        # trying to play before 100% will cause stuttering.
        percent = message.parse_buffering()
        logging.debug("Buffering (%i%%)", percent)

        if percent < 100:
            # If our previous buffer was at 100, but now it's < 100,
            # then we should pause until the buffer is full.
            if self.player_status.buffer_percent == 100:
                logging.debug("Buffer underrun. Pausing pipeline")
                self.player.set_state(Gst.State.PAUSED)
                self.player_status.began_buffering = time.time()
        else:
            if self.playing is None: # Not playing but waiting to
                logging.debug("Buffer 100%. Song starting")
                self.play()
            elif self.playing:
                logging.debug("Buffer recovery. Restarting pipeline")
                self.player.set_state(Gst.State.PLAYING)
            else:
                logging.debug("Buffer recovery. User paused")
            # Tell everyone to update their clocks after we're done buffering or
            # in case it takes a while after the song-changed signal for actual playback to begin.
            self.emit('buffering-finished', self.query_position() or 0)
            self.player_status.began_buffering = None
        self.player_status.buffer_percent = percent
        self.update_song_row()

    def set_volume_cb(self, volume):
        # Convert to the cubic scale that the volume slider uses
        scaled_volume = math.pow(volume, 1.0/3.0)
        self.volume.handler_block_by_func(self.on_volume_change_event)
        self.volume.set_property("value", scaled_volume)
        self.volume.handler_unblock_by_func(self.on_volume_change_event)

    def on_gst_volume(self, player, volumespec):
        vol = self.player.get_property('volume')
        GLib.idle_add(self.set_volume_cb, vol)

    def on_gst_source(self, player, params):
        """ Setup httpsoupsrc to match Pithos proxy settings """
        soup = player.props.source.props
        proxy = self.get_proxy()
        if proxy and hasattr(soup, 'proxy'):
            scheme, user, password, hostport = parse_proxy(proxy)
            soup.proxy = hostport
            soup.proxy_id = user
            soup.proxy_pw = password

    def song_text(self, song):
        title = html.escape(song.title)
        artist = html.escape(song.artist)
        album = html.escape(song.album)
        msg = []
        if song is self.current_song:
            song.position = self.query_position()
            if not song.bitrate is None:
                msg.append("%skbit/s" % (song.bitrate))

            if song.position is not None and song.duration is not None:
                pos_str = self.format_time(song.position)
                msg.append("%s / %s" % (pos_str, song.duration_message))
                if self.playing == False:
                    msg.append("Paused")
            if self.player_status.buffer_percent < 100:
                msg.append("Buffering (%i%%)" % self.player_status.buffer_percent)
        if song.message:
            msg.append(song.message)
        msg = " - ".join(msg)
        if not msg:
            msg = " "

        if song.is_ad:
            description = "<b><big>Commercial Advertisement</big></b>\n<b>Pandora</b>"
        else:
            description = "<b><big>%s</big></b>\nby <b>%s</b>\n<small>from <i>%s</i></small>" % (title, artist, album)

        return "%s\n<small>%s</small>" % (description, msg)

    @staticmethod
    def song_icon(song):
        if song.tired:
            return 'go-jump'
        if song.rating == RATE_LOVE:
            return 'emblem-favorite'
        if song.rating == RATE_BAN:
            return 'dialog-error'

    def update_song_row(self, song = None):
        if song is None:
            song = self.current_song
        if song:
            self.songs_model[song.index][1] = self.song_text(song)
            self.songs_model[song.index][2] = self.song_icon(song) or ""
        return True

    def create_ui_loop(self):
        if not self.ui_loop_timer_id:
            self.ui_loop_timer_id = GLib.timeout_add_seconds(1, self.update_song_row)

    def destroy_ui_loop(self):
        if self.ui_loop_timer_id:
            GLib.source_remove(self.ui_loop_timer_id)
            self.ui_loop_timer_id = 0

    def active_station_changed(self, listbox, row):
        self.station_changed(row.station)

    @staticmethod
    def format_time(time_int):
        if time_int is None:
          return None

        time_int //= 1000000000
        s = time_int % 60
        time_int //= 60
        m = time_int % 60
        time_int //= 60
        h = time_int

        if h:
            return "%i:%02i:%02i"%(h,m,s)
        else:
            return "%i:%02i"%(m,s)

    def selected_song(self):
        sel = self.songs_treeview.get_selection().get_selected()
        if sel:
            return self.songs_treeview.get_model().get_value(sel[1], 0)

    def start_selected_song(self, *ignore):
        playable = self.selected_song().index > self.current_song_index
        if playable:
            self.start_song(self.selected_song().index)
        return playable

    def love_song(self, *ignore, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('metadata-changed', song)
        self.worker_run(song.rate, (RATE_LOVE,), callback, "Loving song...")


    def ban_song(self, *ignore, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('metadata-changed', song)
        self.worker_run(song.rate, (RATE_BAN,), callback, "Banning song...")
        if song is self.current_song:
            self.next_song()

    def unrate_song(self, *ignore, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('metadata-changed', song)
        self.worker_run(song.rate, (RATE_NONE,), callback, "Removing song rating...")

    def tired_song(self, *ignore, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('metadata-changed', song)
        self.worker_run(song.set_tired, (), callback, "Putting song on shelf...")
        if song is self.current_song:
            self.next_song()

    def bookmark_song(self, *ignore, song=None):
        song = song or self.current_song
        self.worker_run(song.bookmark, (), None, "Bookmarking...")

    def bookmark_song_artist(self, *ignore, song=None):
        song = song or self.current_song
        self.worker_run(song.bookmark_artist, (), None, "Bookmarking...")

    def info_song(self, *ignore, song=None):
        song = song or self.current_song
        open_browser(song.songDetailURL)

    @GtkTemplate.Callback
    def on_menuitem_love(self, widget):
        self.love_song(song=self.selected_song())

    @GtkTemplate.Callback
    def on_menuitem_ban(self, widget):
        self.ban_song(song=self.selected_song())

    @GtkTemplate.Callback
    def on_menuitem_unrate(self, widget):
        self.unrate_song(song=self.selected_song())

    @GtkTemplate.Callback
    def on_menuitem_tired(self, widget):
        self.tired_song(song=self.selected_song())

    @GtkTemplate.Callback
    def on_menuitem_info(self, widget):
        self.info_song(song=self.selected_song())

    @GtkTemplate.Callback
    def on_menuitem_bookmark_song(self, widget):
        self.bookmark_song(song=self.selected_song())

    @GtkTemplate.Callback
    def on_menuitem_bookmark_artist(self, widget):
        self.bookmark_song_artist(self.selected_song())

    def on_treeview_button_press_event(self, treeview, event):
        x = int(event.x)
        y = int(event.y)
        time = event.time
        pthinfo = treeview.get_path_at_pos(x, y)
        if pthinfo is not None:
            path, col, cellx, celly = pthinfo
            treeview.grab_focus()
            treeview.set_cursor( path, col, 0)

            if event.button == 3:
                rating = self.selected_song().rating
                self.song_menu_love.set_property("visible", rating != RATE_LOVE)
                self.song_menu_unlove.set_property("visible", rating == RATE_LOVE)
                self.song_menu_ban.set_property("visible", rating != RATE_BAN)
                self.song_menu_unban.set_property("visible", rating == RATE_BAN)

                self.song_menu.popup( None, None, None, None, event.button, time)
                return True

            if event.button == 1 and event.type == Gdk.EventType.DOUBLE_BUTTON_PRESS:
                logging.info("Double clicked on song %s", self.selected_song().index)
                return self.start_selected_song()

    def set_player_volume(self, value):
        # Use a cubic scale for volume. This matches what PulseAudio uses.
        volume = math.pow(value, 3)
        self.player.set_property("volume", volume)

    def adjust_volume(self, amount):
        old_volume = self.volume.get_property("value")
        new_volume = max(0.0, min(1.0, old_volume + 0.02 * amount))

        if new_volume != old_volume:
            self.volume.set_property("value", new_volume)

    def volume_up(self, *ignore):
        self.adjust_volume(+2)

    def volume_down(self, *ignore):
        self.adjust_volume(-2)

    @GtkTemplate.Callback
    def on_volume_change_event(self, volumebutton, value):
        self.set_player_volume(value)

    def show_about(self, version):
        """about - display the about box for pithos """
        about = AboutPithosDialog.AboutPithosDialog(transient_for=self)
        about.set_version(version)
        about.run()
        about.destroy()

    def on_prefs_response(self, widget, response):
        self.prefs_dlg.hide()

        if response == Gtk.ResponseType.APPLY:
            self.on_explicit_content_filter_checkbox()
        else:
            if not self.settings['email']:
                self.quit()

    def show_preferences(self):
        """preferences - display the preferences window for pithos """
        self.sync_explicit_content_filter_setting()
        self.prefs_dlg.show()

    def show_stations(self):
        if self.stations_dlg:
            self.stations_dlg.present()
        else:
            self.stations_dlg = StationsDialog.StationsDialog(self, transient_for=self)
            self.stations_dlg.show_all()

    def refresh_stations(self, *ignore):
        self.worker_run(self.pandora.get_stations, (), self.process_stations, "Refreshing stations...")

    def remove_station(self, station):
        def station_index(model, s):
            return [i[0] for i in model].index(s)
        del self.stations_model[station_index(self.stations_model, station)]
        self.stations_popover.remove_station(station)

    def set_initial_pos(self):
        """ Moves window to position stored in preferences """
        x, y = self.settings['win-pos']
        if not x is None and not y is None:
            self.move(int(x), int(y))

    def bring_to_top(self, *ignore):
        self.set_initial_pos()
        self.show()
        self.present()

    @GtkTemplate.Callback
    def on_configure_event(self, widget, event, data=None):
        self.settings.set_value('win-pos', GLib.Variant('(ii)', (event.x, event.y)))
        return False

    def quit(self, widget=None, data=None):
        """quit - signal handler for closing the PithosWindow"""
        Gio.Application.get_default().quit()

    @GtkTemplate.Callback
    def on_destroy(self, widget, data=None):
        """on_destroy - called when the PithosWindow is close. """
        self.stop()
        self.quit()

