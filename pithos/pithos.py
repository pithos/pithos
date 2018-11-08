# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
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


import contextlib
import html
import json
import logging
import math
import re
import os
import sys
import time
import tempfile
import urllib.error
import urllib.parse
import urllib.request
from enum import Enum

import gi
from gi.repository import GObject, Gtk, Gdk, Pango, GdkPixbuf, Gio, GLib
from .gi_composites import GtkTemplate

if Gtk.get_major_version() < 3 or Gtk.get_minor_version() < 14:
    sys.exit('Gtk 3.14 is required')

from . import AboutPithosDialog, PreferencesPithosDialog, StationsDialog
from .StationsPopover import StationsPopover
from .gobject_worker import GObjectWorker
from .pandora import *
from .pandora.data import *
from .plugin import load_plugins
from .util import open_browser, SecretService, popup_at_pointer
from .migrate_settings import maybe_migrate_settings
from .GstPlayer import GstPlayer, PseudoGst, PLAYER_SECOND

try:
    import pacparser
except ImportError:
    pacparser = None

ALBUM_ART_SIZE = 96
TEXT_X_PADDING = 12

FALLBACK_BLACK = Gdk.RGBA(red=0.0, green=0.0, blue=0.0, alpha=1.0)
FALLBACK_WHITE = Gdk.RGBA(red=1.0, green=1.0, blue=1.0, alpha=1.0)

RATING_BG_SVG = '''
<svg height="20" width="20">
<g transform="translate(0,-1032.3622)">
<path d="m 12,1032.3622 a 12,12 0 0 0 -12,12 12,12 0 0 0 3.0742188,
8 l 16.9257812,0 0,-16.9277 a 12,12 0 0 0 -8,-3.0723 z"
style="fill:{bg}" /></g></svg>
'''

BACKGROUND_SVG = '''
<svg><rect y="0" x="0" height="{px}" width="{px}" style="fill:{fg}" /></svg>
'''


class CellRendererAlbumArt(Gtk.CellRenderer):
    def __init__(self):
        super().__init__(height=ALBUM_ART_SIZE, width=ALBUM_ART_SIZE)
        self.icon = None
        self.pixbuf = None
        self.love_icon = None
        self.ban_icon = None
        self.tired_icon = None
        self.generic_audio_icon = None
        self.background = None
        self.rate_bg = None

    __gproperties__ = {
        'icon': (str, 'icon', 'icon', '', GObject.ParamFlags.READWRITE),
        'pixbuf': (GdkPixbuf.Pixbuf, 'pixmap', 'pixmap',  GObject.ParamFlags.READWRITE)
    }

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
    def do_get_property(self, pspec):
        return getattr(self, pspec.name)
    def do_render(self, ctx, widget, background_area, cell_area, flags):
        if self.pixbuf is not None:
            Gdk.cairo_set_source_pixbuf(ctx, self.pixbuf, cell_area.x, cell_area.y)
            ctx.paint()
        else:
            Gdk.cairo_set_source_pixbuf(ctx, self.background, cell_area.x, cell_area.y)
            ctx.paint()
            x = cell_area.x + (ALBUM_ART_SIZE - self.generic_audio_icon.get_width()) // 2
            y = cell_area.y + (ALBUM_ART_SIZE - self.generic_audio_icon.get_height()) // 2
            Gdk.cairo_set_source_pixbuf(ctx, self.generic_audio_icon, x, y)
            ctx.paint()

        if self.icon is not None:
            x = cell_area.x + (cell_area.width - self.rate_bg.get_width()) # right
            y = cell_area.y + (cell_area.height - self.rate_bg.get_height()) # bottom
            Gdk.cairo_set_source_pixbuf(ctx, self.rate_bg, x, y)
            ctx.paint()

            if self.icon == 'love':
                rating_icon = self.love_icon
            elif self.icon == 'tired':
                rating_icon = self.tired_icon
            elif self.icon == 'ban':
                rating_icon = self.ban_icon

            x = x + (rating_icon.get_width() // 2)
            y = y + (rating_icon.get_height() // 2)

            Gdk.cairo_set_source_pixbuf(ctx, rating_icon, x, y)
            ctx.paint()

    def update_icons(self, style_context):
        # Dynamically change the color of backgrounds and icons
        # to match the current theme at theme changes.
        # Attempt to look up the background and foreground colors
        # in the theme's CSS file. Otherwise if they aren't found
        # fallback to black and white. *Most* new themes use 'theme_bg_color' and 'theme_fg_color'.
        # Some(older) themes use 'bg_color' and 'fg_color'.(like Ubuntu light themes)
        for key in ('theme_bg_color', 'bg_color'):
            bg_bool, bg_color = style_context.lookup_color(key)
            if bg_bool:
                break
        if not bg_bool:
            bg_color = FALLBACK_BLACK
            logging.debug("Could not find theme's background color falling back to black.")

        for key in ('theme_fg_color', 'fg_color'):
            fg_bool, fg_color = style_context.lookup_color(key)
            if fg_bool:
                break
        if not fg_bool:
            fg_color = FALLBACK_WHITE
            logging.debug("Could not find theme's foreground color falling back to white.")

        fg_rgb = fg_color.to_string()
        bg_rgb = bg_color.to_string()

        # Use our color values to create strings representing valid SVG's
        # for backgound and rate_bg, then load them with PixbufLoader.
        background = BACKGROUND_SVG.format(px=ALBUM_ART_SIZE, fg=fg_rgb).encode()
        rating_bg = RATING_BG_SVG.format(bg=bg_rgb).encode()

        with contextlib.closing(GdkPixbuf.PixbufLoader()) as loader:
            loader.write(background)
        self.background = loader.get_pixbuf()

        with contextlib.closing(GdkPixbuf.PixbufLoader()) as loader:
            loader.write(rating_bg)
        self.rate_bg = loader.get_pixbuf()

        current_theme = Gtk.IconTheme.get_default()

        # Pithos requires an icon theme with symbolic icons.

        # Manually color audio-x-generic-symbolic 48px icon to be used as part of the "default cover".
        info = current_theme.lookup_icon('audio-x-generic-symbolic', 48, 0)
        self.generic_audio_icon, was_symbolic = info.load_symbolic(bg_color, bg_color, bg_color, bg_color)

        # We request 24px icons because what we really want is 12px icons,
        # and they doesn't exist in many(or any?) icon themes. We then manually color
        # and scale them down to 12px.
        info = current_theme.lookup_icon('emblem-favorite-symbolic', 24, 0)
        icon, was_symbolic = info.load_symbolic(fg_color, fg_color, fg_color, fg_color)
        self.love_icon = icon.scale_simple(12, 12, GdkPixbuf.InterpType.BILINEAR)

        info = current_theme.lookup_icon('dialog-error-symbolic', 24, 0)
        icon, was_symbolic = info.load_symbolic(fg_color, fg_color, fg_color, fg_color)
        self.ban_icon = icon.scale_simple(12, 12, GdkPixbuf.InterpType.BILINEAR)

        info = current_theme.lookup_icon('go-jump-symbolic', 24, 0)
        icon, was_symbolic = info.load_symbolic(fg_color, fg_color, fg_color, fg_color)
        self.tired_icon = icon.scale_simple(12, 12, GdkPixbuf.InterpType.BILINEAR)

@GtkTemplate(ui='/io/github/Pithos/ui/PithosWindow.ui')
class PithosWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "PithosWindow"
    __gsignals__ = {
        "song-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "song-ended": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "user-changed-play-state": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
        "metadata-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "station-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "stations-processed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "station-added": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "stations-dlg-ready": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
        "songs-added": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_INT,)),
    }

    volume = GtkTemplate.Child()
    playpause_image = GtkTemplate.Child()
    statusbar = GtkTemplate.Child()
    song_menu = GtkTemplate.Child()
    song_menu_love = GtkTemplate.Child()
    song_menu_unlove = GtkTemplate.Child()
    song_menu_ban = GtkTemplate.Child()
    song_menu_unban = GtkTemplate.Child()
    song_menu_create_station = GtkTemplate.Child()
    song_menu_create_song_station = GtkTemplate.Child()
    song_menu_create_artist_station = GtkTemplate.Child()
    songs_treeview = GtkTemplate.Child()
    stations_button = GtkTemplate.Child()
    stations_label = GtkTemplate.Child()

    api_update_dialog_real = GtkTemplate.Child()
    error_dialog_real = GtkTemplate.Child()
    fatal_error_dialog_real = GtkTemplate.Child()

    def __init__(self, app, test_mode):
        super().__init__(application=app)
        self.init_template()

        self.settings = Gio.Settings.new('io.github.Pithos')
        self.settings.connect('changed::audio-quality', self.set_audio_quality)
        self.settings.connect('changed::proxy', self.set_proxy)
        self.settings.connect('changed::control-proxy', self.set_proxy)
        self.settings.connect('changed::control-proxy-pac', self.set_proxy)

        self.prefs_dlg = PreferencesPithosDialog.PreferencesPithosDialog(transient_for=self)
        self.prefs_dlg.connect_after('response', self.on_prefs_response)
        self.prefs_dlg.connect('login-changed', self.pandora_reconnect)

        self.init_core()
        self.init_ui()
        self.init_actions(app)

        self.plugins = {}
        load_plugins(self)

        self.pandora = make_pandora(test_mode)
        self.set_proxy(reconnect=False)
        self.set_audio_quality()
        SecretService.unlock_keyring(self.on_keyring_unlocked)

    def on_keyring_unlocked(self, error):
        if error:
            logging.error('You need to install a service such as gnome-keyring. Error: {}'.format(error))
            self.fatal_error_dialog(
                error.message,
                _('You need to install a service such as gnome-keyring.'),
            )

        else:
            maybe_migrate_settings()
            self.pandora_connect()


    def init_core(self):
        #                                Song object            display text  icon  album art
        self.songs_model = Gtk.ListStore(GObject.TYPE_PYOBJECT, str,          str,  GdkPixbuf.Pixbuf)
        #                                   Station object         station name  index
        self.stations_model = Gtk.ListStore(GObject.TYPE_PYOBJECT, str,          int)

        self.player = GstPlayer(self.settings)

        self.player.connect('notify::volume', self.on_gst_volume)
        self.player.connect('eos', self.on_player_eos)
        self.player.connect('new-stream-duration', self.on_player_new_stream_duration)
        self.player.connect('new-player-state', self.on_player_new_player_state)
        self.player.connect('warning', self.on_player_warning)
        self.player.connect('error', lambda player, msg: self.error_dialog(msg[0], msg[1], msg[2]))
        self.player.connect('fatal-error', lambda player, msg: self.fatal_error_dialog(msg[0], msg[1]))

        self.stations_dlg = None

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
        self.playlist_update_timer_id = 0
        display = self.props.screen.get_display()
        self.not_in_x = not type(display).__name__.endswith('X11Display')
        self.worker = GObjectWorker()

        try:
            self.tempdir = tempfile.TemporaryDirectory(prefix='pithos-',
                                                       dir=GLib.get_user_cache_dir())
            logging.info("Created temporary directory %s" %self.tempdir.name)
        except IOError as e:
            self.tempdir = None
            logging.warning('Failed to create a temporary directory')

    def init_ui(self):
        GLib.set_application_name("Pithos")
        Gtk.Window.set_default_icon_name('pithos')

        self.volume.set_relief(Gtk.ReliefStyle.NORMAL)  # It ignores glade...
        self.settings.bind('volume', self.volume, 'value', Gio.SettingsBindFlags.DEFAULT)

        self.songs_treeview.set_model(self.songs_model)

        title_col   = Gtk.TreeViewColumn()

        render_cover_art = CellRendererAlbumArt()
        title_col.pack_start(render_cover_art, False)
        title_col.add_attribute(render_cover_art, "icon", 2)
        title_col.add_attribute(render_cover_art, "pixbuf", 3)

        render_text = Gtk.CellRendererText(xpad=TEXT_X_PADDING)
        render_text.props.ellipsize = Pango.EllipsizeMode.END
        title_col.pack_start(render_text, True)
        title_col.set_sizing(Gtk.TreeViewColumnSizing.FIXED)
        title_col.add_attribute(render_text, "markup", 1)

        self.songs_treeview.append_column(title_col)

        self.get_style_context().connect('changed', lambda sc: render_cover_art.update_icons(sc))

        self.songs_treeview.connect('button_press_event', self.on_treeview_button_press_event)

        self.stations_popover = StationsPopover()
        self.stations_popover.set_relative_to(self.stations_button)
        self.stations_popover.set_model(self.stations_model)
        self.stations_popover.listbox.connect('row-activated', self.active_station_changed)
        self.stations_button.set_popover(self.stations_popover)

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

    def worker_run(self, fn, args=(), callback=None, message=None, context='net', errorback=None, user_data=None):
        if context and message:
            self.statusbar.push(self.statusbar.get_context_id(context), message)

        if isinstance(fn,str):
            fn = getattr(self.pandora, fn)

        def cb(v):
            if context: self.statusbar.pop(self.statusbar.get_context_id(context))
            if callback:
                if user_data:
                    callback(v, user_data)
                else:
                    callback(v)

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
                self.pandora_connect(message="Reconnecting...", callback=retry_cb)
            elif isinstance(e, PandoraAPIVersionError):
                self.api_update_dialog()
            elif isinstance(e, PandoraError):
                self.error_dialog(e.message, retry_cb, submsg=e.submsg)
            else:
                logging.warning(e.traceback)

        err = errorback or eb

        self.worker.send(fn, args, cb, err)

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

        self.pandora.set_url_opener(control_opener)

        if reconnect:
            self.pandora_connect()

    def set_audio_quality(self, *ignore):
        # Don't change song quality on the fly if we're about to reload the playlist
        # because the explicit content filter has been set or the new song url is not valid.
        def player_stream_quailty_change():
            checkbox_state = self.prefs_dlg.explicit_content_filter_checkbutton.get_active()
            reload_playlist = self.filter_state is not None and self.filter_state != checkbox_state and checkbox_state
            song = self.current_song
            if not reload_playlist and song and song.is_still_valid():
                self.player.stream_quailty_change(song.audioUrl, int(song.bitrate))

        self.pandora.set_audio_quality(self.settings['audio-quality'])
        # Let the settings window close before we do anything.
        GLib.idle_add(player_stream_quailty_change)

    def pandora_connect(self, *ignore, message="Logging in...", callback=None):
        def cb(password):
            if not password:
                self.show_preferences()
            else:
                self._pandora_connect_real(message, callback, email, password)

        email = self.settings['email']
        if not email:
            self.show_preferences()
        else:
            SecretService.get_account_password(email, cb)

    def _pandora_connect_real(self, message, callback, email, password):
        pandora_one = self.settings['pandora-one']
        if pandora_one:
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

        args = (
            client,
            email,
            password,
        )

        def on_got_stations(*ignore):
            self.process_stations(self)
            if callback:
                callback()

        def pandora_ready(*ignore):
            logging.info("Pandora connected")
            if pandora_one != self.pandora.isSubscriber:
                self.settings['pandora-one'] = self.pandora.isSubscriber
                self._pandora_connect_real(message, callback, email, password)
            else:
                self.worker_run('get_stations', (), on_got_stations, 'Getting stations...', 'login')

        self.worker_run('connect', args, pandora_ready, message, 'login')

    def pandora_reconnect(self, prefs_dialog, email_password):
        ''' Stop everything and reconnect '''
        email, password = email_password
        self.stop()
        self.waiting_for_playlist = False
        self.current_song_index = None
        self.start_new_playlist = False
        self.current_station = None
        self.current_station_id = None
        self.have_stations = False
        self.playcount = 0
        self.songs_model.clear()
        self._pandora_connect_real("Logging in...", None, email, password)

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
        # Make sure that the Thumprint Radio Station is always 2nd.
        for i, s in enumerate(self.pandora.stations):
            if s.isThumbprint:
                self.pandora.stations.insert(1, self.pandora.stations.pop(i))
                break
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
            self.emit('stations-processed', self.pandora.stations)
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
            self.current_song.message = 'Song expired'
            self.update_song_row()
            return self.next_song()

        if self.current_song.tired or self.current_song.rating == RATE_BAN:
            return self.next_song()

        logging.info("Starting song: index = %i"%(song_index))
        song = self.current_song
        audioUrl = song.audioUrl
        os.environ['PULSE_PROP_media.title'] = song.title
        os.environ['PULSE_PROP_media.artist'] = song.artist
        os.environ['PULSE_PROP_media.name'] = '{}: {}'.format(song.artist, song.title)
        os.environ['PULSE_PROP_media.filename'] = audioUrl
        self.player.start_stream(audioUrl, int(song.bitrate))
        self.playcount += 1

        self.current_song.start_time = time.time()
        self.songs_treeview.scroll_to_cell(song_index, use_align=True, row_align = 1.0)
        self.songs_treeview.set_cursor(song_index, None, 0)
        self.set_title("%s by %s - Pithos" % (song.title, song.artist))

        self.update_song_row()

        self.emit('song-changed', song)
        self.emit('metadata-changed', song)

    @GtkTemplate.Callback
    def next_song(self, *ignore):
        if self.current_song_index is not None:
            self.start_song(self.current_song_index + 1)

    def user_play(self, *ignore):
        if self.play():
            self.emit('user-changed-play-state', True)

    def play(self):
        # Edge case. If we try to go to Play while we're reconnecting
        # to Pandora self.current_song will be None.
        if self.current_song is None:
            return False
        if not self.current_song.is_still_valid():
            self.current_song.message = 'Song expired'
            self.update_song_row()
            return self.next_song()

        self.player.play()
        return True

    def user_pause(self, *ignore):
        self.pause()
        self.emit('user-changed-play-state', False)

    def pause(self):
        self.player.pause()


    def stop(self):
        prev = self.current_song
        if prev and prev.start_time:
            prev.finished = True
            prev.position = self.player.query_position()
            self.emit("song-ended", prev)

        self.player.stop()

    @GtkTemplate.Callback
    def user_playpause(self, *ignore):
        self.playpause_notify()

    def playpause(self, *ignore):
        logging.info("playpause")
        if self.player.props.playing:
            self.pause()
        else:
            self.play()

    def playpause_notify(self, *ignore):
        if self.player.props.playing:
            self.user_pause()
        else:
            self.user_play()

    def get_playlist(self, start = False):
        if self.playlist_update_timer_id:
            GLib.source_remove(self.playlist_update_timer_id)
        self.playlist_update_timer_id = 0
        songs_left_to_process = 0
        song_count = 0
        self.start_new_playlist = self.start_new_playlist or start
        if self.waiting_for_playlist: return

        if self.gstreamer_errorcount_1 >= self.playcount and self.gstreamer_errorcount_2 >=1:
            logging.warning("Too many gstreamer errors. Not retrying")
            self.waiting_for_playlist = 1
            self.error_dialog(self.gstreamer_error, self.get_playlist)
            return

        def emit_songs_added(song_count):
            self.playlist_update_timer_id = 0
            self.emit('songs-added', song_count)
            return False

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
            nonlocal songs_left_to_process
            pixbuf, file_url, song, index = t
            songs_left_to_process -= 1
            if index<len(self.songs_model) and self.songs_model[index][0] is song: # in case the playlist has been reset
                logging.info("Downloaded album art for %i"%song.index)
                song.art_pixbuf = pixbuf
                self.songs_model[index][3]=pixbuf
                self.update_song_row(song)
                if file_url:
                    song.artUrl = file_url
                    # The song is either the current song or we got the cover after
                    # after the timeout has expired.
                    if song is self.current_song or not self.playlist_update_timer_id:
                        self.emit('metadata-changed', song)
                # We tried to get covers for all the songs in the playlist,
                # and the timeout is still live. Cancel it and emit
                # a 'songs-added' signal.
                if not songs_left_to_process and self.playlist_update_timer_id:
                    GLib.source_remove(self.playlist_update_timer_id)
                    emit_songs_added(song_count)

        def callback(l):
            nonlocal songs_left_to_process
            nonlocal song_count
            songs_left_to_process = song_count = len(l)
            start_index = len(self.songs_model)
            for i in l:
                i.index = len(self.songs_model)
                self.songs_model.append((i, '', None, None))
                self.update_song_row(i)
                i.art_pixbuf = None
                if i.artRadio:
                    self.worker_run(get_album_art, (i.artRadio, self.tempdir, i, i.index), art_callback)
                else:
                    songs_left_to_process -= 1
            # Give Pandora about 1 secs per song to return the playlist's cover art
            # after that emit a 'songs-added' Anyway. We can't wait forever after all.
            self.playlist_update_timer_id = GLib.timeout_add_seconds(song_count, emit_songs_added, song_count)

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
        self.emit('station-changed', station)

    def station_added(self, station, user_data):
        music_type, description = user_data
        for existing_station in self.stations_model:
            if existing_station[0].id == station.id:
                self.station_already_exists(existing_station[0], description, music_type, self)
                return
        # We shouldn't actually add the station to the pandora stations list
        # until we know it's not a duplicate.
        self.pandora.stations.append(station)
        self.stations_model.insert_with_valuesv(0, (0, 1, 2), (station, station.name, 0))
        self.emit('station-added', station)
        self.station_changed(station)

    def station_already_exists(self, station, description, music_type, parent):
        def on_response(dialog, response):
            if response == Gtk.ResponseType.YES:
                self.station_changed(station)
            dialog.destroy()

        sub_title = _('Pandora does not permit multiple stations with the same seed.')

        if music_type == 'song':
            seed = _('Song Seed:')
        elif music_type == 'artist':
            seed = _('Artist Seed:')
        else:
            seed = _('Genre Seed:')

        if station is self.current_station:
            button_type = Gtk.ButtonsType.OK
            message = _('{0}\n"{1}", the Station you are currently listening to already contains the {2} {3}.')
        else:
            button_type = Gtk.ButtonsType.YES_NO
            message = _('{0}\nYour Station "{1}" already contains the {2} {3}.\nWould you like to listen to it now?')

        message = message.format(sub_title, station.name, seed, description)

        dialog = Gtk.MessageDialog(
            parent=parent,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=button_type,
            text=_('A New Station could not be created'),
            secondary_text=message,
        )

        dialog.connect('response', on_response)
        dialog.show()

    def on_player_new_stream_duration(self, player, duration):
        # Edge case. We might get this singal while we're reconnecting to Pandora.
        # If so self.current_song will be None.
        if self.current_song is None:
            return
        # Fallback to using song.trackLength which is in seconds and converted to nanoseconds
        self.current_song.duration = duration or self.current_song.trackLength * PLAYER_SECOND
        self.current_song.duration_message = self.format_time(self.current_song.duration)
        self.update_song_row()
        # No point in checking if the song is an ad if the player doesn't return a valid duration
        # Pandora lies.
        if duration:
            self.check_if_song_is_ad()
        # We can't seek so duration in MPRIS is just for display purposes if it's not off by more than a sec it's OK.
        if self.current_song.get_duration_sec() != self.current_song.trackLength:
            self.emit('metadata-changed', self.current_song)

    def on_player_new_player_state(self, *ignore):
        self.update_song_row()
        if self.player.props.actual_state is PseudoGst.PLAYING:
            self.create_ui_loop()
        else:
            self.destroy_ui_loop()
        if self.player.props.desired_state is PseudoGst.PAUSED:
            self.playpause_image.set_from_icon_name('media-playback-start-symbolic', Gtk.IconSize.SMALL_TOOLBAR)
        else:
            self.playpause_image.set_from_icon_name('media-playback-pause-symbolic', Gtk.IconSize.SMALL_TOOLBAR)

    def on_player_eos(self, *ignore):
        logging.info("EOS")
        self.next_song()

    def on_player_warning(self, player, message):
        err, debug = message
        logging.error("Gstreamer error: %s, %s, %s" % (err, debug, err.code))
        if self.current_song:
            self.current_song.message = "Error: "+str(err)
            self.update_song_row()

        self.gstreamer_error = str(err)
        self.gstreamer_errorcount_1 += 1

        if not self.player.plugins_installation_in_progress():
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

    def set_volume_cb(self, volume):
        # Convert to the cubic scale that the volume slider uses
        scaled_volume = math.pow(volume, 1.0/3.0)
        self.volume.handler_block_by_func(self.on_volume_change_event)
        self.volume.set_property("value", scaled_volume)
        self.volume.handler_unblock_by_func(self.on_volume_change_event)

    def on_gst_volume(self, player, volumespec):
        vol = self.player.get_property('volume')
        GLib.idle_add(self.set_volume_cb, vol)

    def song_text(self, song):
        title = html.escape(song.title)
        artist = html.escape(song.artist)
        album = html.escape(song.album)
        msg = []
        if song is self.current_song:
            song.position = self.player.query_position()
            if not song.bitrate is None:
                msg.append("%skbit/s" % (song.bitrate))

            if song.position is not None and song.duration is not None:
                pos_str = self.format_time(song.position)
                msg.append("%s / %s" % (pos_str, song.duration_message))
            if self.player.props.desired_state is PseudoGst.PAUSED:
                msg.append("Paused")
            if self.player.props.actual_state is PseudoGst.BUFFERING:
                msg.append("Buffering…")
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
            return 'tired'
        if song.rating == RATE_LOVE:
            return 'love'
        if song.rating == RATE_BAN:
            return 'ban'
        return None

    def update_song_row(self, song = None):
        if song is None:
            song = self.current_song
        if song:
            self.songs_model[song.index][1] = self.song_text(song)
            self.songs_model[song.index][2] = self.song_icon(song)
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

    @GtkTemplate.Callback
    def on_menuitem_create_artist_station(self, widget):
        user_date = 'artist', html.escape(self.selected_song().artist)
        self.worker_run(
            'add_station_by_track_token',
            (self.selected_song().trackToken, 'artist'),
            self.station_added,
            user_data=user_date,
        )

    @GtkTemplate.Callback
    def on_menuitem_create_song_station(self, widget):
        title = html.escape(self.selected_song().title)
        artist = html.escape(self.selected_song().artist)
        user_date = 'song', '{} by {}'.format(title, artist)
        self.worker_run(
            'add_station_by_track_token',
            (self.selected_song().trackToken, 'song'),
            self.station_added,
            user_data=user_date,
        )

    def on_treeview_button_press_event(self, treeview, event):
        x = int(event.x)
        y = int(event.y)
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

                popup_at_pointer(self.song_menu, event)
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
            self.emit('stations-dlg-ready', True)

    def refresh_stations(self, *ignore):
        self.worker_run(self.pandora.get_stations, (), self.process_stations, "Refreshing stations...")

    def remove_station(self, station):
        def station_index(model, s):
            return [i[0] for i in model].index(s)
        del self.stations_model[station_index(self.stations_model, station)]
        self.stations_popover.remove_station(station)

    def restore_position(self):
        """ Moves window to position stored in preferences """
        # Getting and setting window position does not work in Wayland.
        if self.not_in_x:
            return
        x, y = self.settings['win-pos']
        self.handler_block_by_func(self.on_configure_event)
        self.move(x, y)
        self.handler_unblock_by_func(self.on_configure_event)

    def bring_to_top(self, *ignore):
        timestamp = Gtk.get_current_event_time()
        self.present_with_time(timestamp)

    def present_with_time(self, timestamp):
        self.restore_position()
        Gtk.Window.present_with_time(self, timestamp)

    def present(self):
        self.restore_position()
        Gtk.Window.present(self)

    @GtkTemplate.Callback
    def on_configure_event(self, *ignore):
        # Getting and setting window position does not work in Wayland.
        if self.not_in_x:
            return
        x, y = self.get_position() # This can return None
        self.settings.set_value('win-pos', GLib.Variant('(ii)', (x or 0, y or 0)))

    def quit(self, widget=None, data=None):
        """quit - signal handler for closing the PithosWindow"""
        Gio.Application.get_default().quit()

    @GtkTemplate.Callback
    def on_destroy(self, widget, data=None):
        """on_destroy - called when the PithosWindow is close. """
        self.stop()
        self.quit()
