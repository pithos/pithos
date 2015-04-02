#!/usr/bin/env python
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

import argparse
import cgi
import contextlib
import html
import json
import logging
import math
import os
import re
import signal
import sys
import time
import urllib.error
import urllib.parse
import urllib.request

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GstPbutils, GObject, Gtk, Gdk, Pango, GdkPixbuf, Gio, GLib
if sys.platform != 'win32':
    from dbus.mainloop.glib import DBusGMainLoop
    DBusGMainLoop(set_as_default=True)

# Check if we are working in the source tree or from the installed
# package and mangle the python path accordingly
realPath = os.path.realpath(sys.argv[0])  # If this file is run from a symlink, it needs to follow the symlink
if os.path.dirname(realPath) != ".":
    if realPath[0] == "/":
        fullPath = os.path.dirname(realPath)
    else:
        fullPath = os.getcwd() + "/" + os.path.dirname(realPath)
else:
    fullPath = os.getcwd()
sys.path.insert(0, os.path.dirname(fullPath))

from . import AboutPithosDialog, PreferencesPithosDialog, StationsDialog
from .gobject_worker import GObjectWorker
from .pandora import *
from .pandora.data import *
from .pithosconfig import get_ui_file, get_media_file, VERSION
from .pithosconfig import getdatapath, VERSION
from .plugin import load_plugins
from .plugin import load_plugins
from .util import parse_proxy
from .util import parse_proxy, open_browser
if sys.platform != 'win32':
    from .dbus_service import PithosDBusProxy
    from .mpris import PithosMprisService

pacparser_imported = False
try:
    import pacparser
    pacparser_imported = True
except ImportError:
    pass

def buttonMenu(button, menu):
    def cb(button):
        allocation = button.get_allocation()
        x, y = button.get_window().get_origin()[1:]
        x += allocation.x
        y += allocation.y + allocation.height
        menu.popup(None, None, (lambda *ignore: (x, y, True)), None, 1, Gtk.get_current_event_time())

    button.connect('clicked', cb)

ALBUM_ART_SIZE = 96
ALBUM_ART_X_PAD = 6

class CellRendererAlbumArt(Gtk.CellRenderer):
    def __init__(self):
        GObject.GObject.__init__(self)
        self.icon = None
        self.pixbuf = None
        self.rate_bg = GdkPixbuf.Pixbuf.new_from_file(get_media_file('rate'))

    __gproperties__ = {
        'icon': (str, 'icon', 'icon', '', GObject.PARAM_READWRITE),
        'pixbuf': (GdkPixbuf.Pixbuf, 'pixmap', 'pixmap',  GObject.PARAM_READWRITE)
    }

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
    def do_get_property(self, pspec):
        return getattr(self, pspec.name)
    def do_get_size(self, widget, cell_area):
        return (0, 0, ALBUM_ART_SIZE + ALBUM_ART_X_PAD, ALBUM_ART_SIZE)
    def do_render(self, ctx, widget, background_area, cell_area, flags):
        if self.pixbuf:
            Gdk.cairo_set_source_pixbuf(ctx, self.pixbuf, cell_area.x, cell_area.y)
            ctx.paint()
        if self.icon:
            x = cell_area.x+(cell_area.width-self.rate_bg.get_width()) - ALBUM_ART_X_PAD # right
            y = cell_area.y+(cell_area.height-self.rate_bg.get_height()) # bottom
            Gdk.cairo_set_source_pixbuf(ctx, self.rate_bg, x, y)
            ctx.paint()

            icon = widget.get_style_context().lookup_icon_set(self.icon)
            pixbuf = icon.render_icon_pixbuf(widget.get_style_context(), Gtk.IconSize.MENU)
            x = cell_area.x+(cell_area.width-pixbuf.get_width())-5 - ALBUM_ART_X_PAD # right
            y = cell_area.y+(cell_area.height-pixbuf.get_height())-5 # bottom
            Gdk.cairo_set_source_pixbuf(ctx, pixbuf, x, y)
            ctx.paint()

def get_album_art(url, *extra):
    try:
        with urllib.request.urlopen(url) as f:
            image = f.read()
    except urllib.error.HTTPError:
        logging.warn('Invalid image url received')
        return (None,) + extra

    with contextlib.closing(GdkPixbuf.PixbufLoader()) as loader:
        loader.set_size(ALBUM_ART_SIZE, ALBUM_ART_SIZE)
        loader.write(image)
        return (loader.get_pixbuf(),) + extra

class PlayerStatus (object):
  def __init__(self):
    self.reset()

  def reset(self):
    self.async_done = False
    self.began_buffering = None
    self.buffer_percent = 100
    self.pending_duration_query = False


class PithosWindow(Gtk.ApplicationWindow):
    __gtype_name__ = "PithosWindow"
    __gsignals__ = {
        "song-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "song-ended": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "song-rating-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "play-state-changed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
        "user-changed-play-state": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_BOOLEAN,)),
    }

    def __init__(self):
        """__init__ - This function is typically not called directly.
        Creation a PithosWindow requires redeading the associated ui
        file and parsing the ui definition extrenally,
        and then calling PithosWindow.finish_initializing().

        Use the convenience function NewPithosWindow to create
        PithosWindow object.

        """
        pass

    def finish_initializing(self, builder, cmdopts):
        """finish_initalizing should be called after parsing the ui definition
        and creating a PithosWindow object with it in order to finish
        initializing the start of the new PithosWindow instance.

        """
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        self.cmdopts = cmdopts

        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)

        self.prefs_dlg = PreferencesPithosDialog.NewPreferencesPithosDialog()
        self.prefs_dlg.set_transient_for(self)
        self.preferences = self.prefs_dlg.get_preferences()

        if self.prefs_dlg.fix_perms():
            # Changes were made, save new config variable
            self.prefs_dlg.save()

        self.init_core()
        self.init_ui()

        self.plugins = {}
        load_plugins(self)

        if sys.platform != 'win32':
            self.dbus_service = PithosDBusProxy(self)
            self.mpris = PithosMprisService(self)

        if not self.preferences['username']:
            self.show_preferences(is_startup=True)

        self.pandora = make_pandora(self.cmdopts.test)
        self.set_proxy()
        self.set_audio_quality()
        self.pandora_connect()

    def init_core(self):
        #                                Song object            display text  icon  album art
        self.songs_model = Gtk.ListStore(GObject.TYPE_PYOBJECT, str,          str,  GdkPixbuf.Pixbuf)
        #                                   Station object         station name
        self.stations_model = Gtk.ListStore(GObject.TYPE_PYOBJECT, str)

        Gst.init(None)
        self._query_duration = Gst.Query.new_duration(Gst.Format.TIME)
        self._query_position = Gst.Query.new_position(Gst.Format.TIME)
        self.player = Gst.ElementFactory.make("playbin", "player");
        self.player.props.flags |= (1 << 7) # enable progressive download (GST_PLAY_FLAG_DOWNLOAD)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message::async-done", self.on_gst_async_done)
        bus.connect("message::duration-changed", self.on_gst_duration_changed)
        bus.connect("message::eos", self.on_gst_eos)
        bus.connect("message::buffering", self.on_gst_buffering)
        bus.connect("message::error", self.on_gst_error)
        bus.connect("message::element", self.on_gst_element)
        bus.connect("message::tag", self.on_gst_tag)
        self.player.connect("notify::volume", self.on_gst_volume)
        self.player.connect("notify::source", self.on_gst_source)

        self.player_status = PlayerStatus()

        self.stations_dlg = None

        self.playing = False
        self.current_song_index = None
        self.current_station = None
        self.current_station_id = self.preferences.get('last_station_id')

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

        aa = GdkPixbuf.Pixbuf.new_from_file(get_media_file('album'))

        self.default_album_art = aa.scale_simple(ALBUM_ART_SIZE, ALBUM_ART_SIZE, GdkPixbuf.InterpType.BILINEAR)

    def init_ui(self):
        GLib.set_application_name("Pithos")
        Gtk.Window.set_default_icon_name('pithos')
        os.environ['PULSE_PROP_media.role'] = 'music'

        self.playpause_image = self.builder.get_object('playpause_image')

        self.volume = self.builder.get_object('volume')
        self.volume.set_relief(Gtk.ReliefStyle.NORMAL)  # It ignores glade...
        self.volume.set_property("value", math.pow(float(self.preferences['volume']), 1.0/3.0))

        self.statusbar = self.builder.get_object('statusbar1')

        self.song_menu = self.builder.get_object('song_menu')
        self.song_menu_love = self.builder.get_object('menuitem_love')
        self.song_menu_unlove = self.builder.get_object('menuitem_unlove')
        self.song_menu_ban = self.builder.get_object('menuitem_ban')
        self.song_menu_unban = self.builder.get_object('menuitem_unban')

        self.songs_treeview = self.builder.get_object('songs_treeview')
        self.songs_treeview.set_model(self.songs_model)

        title_col   = Gtk.TreeViewColumn()

        def bgcolor_data_func(column, cell, model, iter, data=None):
            if model.get_value(iter, 0) is self.current_song:
                bgcolor = column.get_tree_view().get_style_context().get_background_color(Gtk.StateFlags.ACTIVE)
            else:
                bgcolor = column.get_tree_view().get_style_context().get_background_color(Gtk.StateFlags.NORMAL)
            cell.set_property("cell-background-rgba", bgcolor)

        render_icon = CellRendererAlbumArt()
        title_col.pack_start(render_icon, False)
        title_col.add_attribute(render_icon, "icon", 2)
        title_col.add_attribute(render_icon, "pixbuf", 3)
        title_col.set_cell_data_func(render_icon, bgcolor_data_func)

        render_text = Gtk.CellRendererText()
        render_text.props.ellipsize = Pango.EllipsizeMode.END
        title_col.pack_start(render_text, True)
        title_col.add_attribute(render_text, "markup", 1)
        title_col.set_cell_data_func(render_text, bgcolor_data_func)

        self.songs_treeview.append_column(title_col)

        self.songs_treeview.connect('button_press_event', self.on_treeview_button_press_event)

        self.stations_combo = self.builder.get_object('stations')
        self.stations_combo.set_model(self.stations_model)
        render_text = Gtk.CellRendererText()
        self.stations_combo.pack_start(render_text, True)
        self.stations_combo.add_attribute(render_text, "text", 1)
        self.stations_combo.set_row_separator_func(lambda model, iter, data=None: model.get_value(iter, 0) is None, None)

        self.set_initial_pos()

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
                logging.warn(e.traceback)

        self.worker.send(fn, args, cb, eb)

    def get_proxy(self):
        """ Get HTTP proxy, first trying preferences then system proxy """

        if self.preferences['proxy']:
            return self.preferences['proxy']

        system_proxies = urllib.request.getproxies()
        if 'http' in system_proxies:
            return system_proxies['http']

        return None

    def set_proxy(self):
        # proxy preference is used for all Pithos HTTP traffic
        # control proxy preference is used only for Pandora traffic and
        # overrides proxy
        #
        # If neither option is set, urllib2.build_opener uses urllib.getproxies()
        # by default

        handlers = []
        global_proxy = self.preferences['proxy']
        if global_proxy:
            handlers.append(urllib.request.ProxyHandler({'http': global_proxy, 'https': global_proxy}))
        global_opener = urllib.request.build_opener(*handlers)
        urllib.request.install_opener(global_opener)

        control_opener = global_opener
        control_proxy = self.preferences['control_proxy']
        control_proxy_pac = self.preferences['control_proxy_pac']

        if control_proxy:
            control_opener = urllib.request.build_opener(urllib.request.ProxyHandler({'http': control_proxy, 'https': control_proxy}))

        elif control_proxy_pac and pacparser_imported:
            pacparser.init()
            with urllib.request.urlopen(control_proxy_pac) as f:
                pacstring = f.read().decode('utf-8')
                try:
                    pacparser.parse_pac_string(pacstring)
                except:
                    logging.warning('Failed to parse PAC.')
            try:
                proxies = pacparser.find_proxy("http://pandora.com", "pandora.com").split(";")
                for proxy in proxies:
                    match = re.search("PROXY (.*)", proxy)
                    if match:
                        control_proxy = match.group(1)
                        break
            except:
                logging.warning('Failed to find proxy via PAC.')
            pacparser.cleanup()
        elif control_proxy_pac and not pacparser_imported:
            logging.warning("Disabled proxy auto-config support because python-pacparser module was not found.")

        self.worker_run('set_url_opener', (control_opener,))

    def set_audio_quality(self):
        self.worker_run('set_audio_quality', (self.preferences['audio_quality'],))

    def pandora_connect(self, message="Logging in...", callback=None):
        if self.preferences['pandora_one']:
            client = client_keys[default_one_client_id]
        else:
            client = client_keys[default_client_id]

        # Allow user to override client settings
        force_client = self.preferences['force_client']
        if force_client in client_keys:
            client = client_keys[force_client]
        elif force_client and force_client[0] == '{':
            try:
                client = json.loads(force_client)
            except:
                logging.error("Could not parse force_client json")

        args = (
            client,
            self.preferences['username'],
            self.preferences['password'],
        )

        def pandora_ready(*ignore):
            logging.info("Pandora connected")
            self.process_stations(self)
            if callback:
                callback()

        self.worker_run('connect', args, pandora_ready, message, 'login')

    def process_stations(self, *ignore):
        self.stations_model.clear()
        self.current_station = None
        selected = None

        for i in self.pandora.stations:
            if i.isQuickMix and i.isCreator:
                self.stations_model.append((i, "QuickMix"))
        self.stations_model.append((None, 'sep'))
        for i in self.pandora.stations:
            if not (i.isQuickMix and i.isCreator):
                self.stations_model.append((i, i.name))
            if i.id == self.current_station_id:
                logging.info("Restoring saved station: id = %s"%(i.id))
                selected = i
        if not selected:
            selected=self.stations_model[0][0]
        self.station_changed(selected, reconnecting = self.have_stations)
        self.have_stations = True

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
        self.play()
        self.playcount += 1

        self.current_song.start_time = time.time()

        self.songs_treeview.scroll_to_cell(song_index, use_align=True, row_align = 1.0)
        self.songs_treeview.set_cursor(song_index, None, 0)
        self.set_title("Pithos - %s by %s" % (self.current_song.title, self.current_song.artist))

        self.emit('song-changed', self.current_song)

    def next_song(self, *ignore):
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

        self.playing = False
        self.destroy_ui_loop()
        self.player.set_state(Gst.State.NULL)
        self.emit('play-state-changed', False)

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
            logging.warn("Too many gstreamer errors. Not retrying")
            self.waiting_for_playlist = 1
            self.error_dialog(self.gstreamer_error, self.get_playlist)
            return

        def art_callback(t):
            pixbuf, song, index = t
            if index<len(self.songs_model) and self.songs_model[index][0] is song: # in case the playlist has been reset
                logging.info("Downloaded album art for %i"%song.index)
                song.art_pixbuf = pixbuf
                self.songs_model[index][3]=pixbuf
                self.update_song_row(song)

        def callback(l):
            start_index = len(self.songs_model)
            for i in l:
                i.index = len(self.songs_model)
                self.songs_model.append((i, '', '', self.default_album_art))
                self.update_song_row(i)

                i.art_pixbuf = None
                if i.artRadio:
                    self.art_worker.send(get_album_art, (i.artRadio, i, i.index), art_callback)

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
        dialog = self.builder.get_object("error_dialog")

        dialog.props.text = message
        dialog.props.secondary_text = submsg
        dialog.set_default_response(3)

        if retry_cb is None:
            btn = self.builder.get_object("button2")
            btn.hide()

        response = dialog.run()
        dialog.hide()

        if response == 2:
            self.gstreamer_errorcount_2 = 0
            logging.info("Manual retry")
            return retry_cb()
        elif response == 3:
            self.show_preferences()

    def fatal_error_dialog(self, message, submsg):
        dialog = self.builder.get_object("fatal_error_dialog")
        dialog.props.text = message
        dialog.props.secondary_text = submsg
        dialog.set_default_response(1)

        dialog.run()
        dialog.hide()

        self.quit()

    def api_update_dialog(self):
        dialog = self.builder.get_object("api_update_dialog")
        dialog.set_default_response(0)
        response = dialog.run()
        if response:
            open_browser("http://pithos.github.io/itbroke?utm_source=pithos&utm_medium=app&utm_campaign=%s"%VERSION)
        self.quit()

    def station_index(self, station):
        return [i[0] for i in self.stations_model].index(station)

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
        if not reconnecting:
            self.get_playlist(start = True)
        self.stations_combo.set_active(self.station_index(station))

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

    def on_gst_async_done(self, bus, message):
      self.player_status.async_done = True
      if self.player_status.pending_duration_query:
        self.current_song.duration = self.query_duration()
        self.current_song.duration_message = self.format_time(self.current_song.duration)        
        self.check_if_song_is_ad()
        self.player_status.pending_duration_query = False

    def on_gst_duration_changed(self, bus, message):
      if self.player_status.async_done:
        self.current_song.duration = self.query_duration()
        self.current_song.duration_message = self.format_time(self.current_song.duration)
        self.check_if_song_is_ad()
      else:
        self.player_status.pending_duration_query = True

    def on_gst_eos(self, bus, message):
        logging.info("EOS")
        self.next_song()

    def on_gst_plugin_installed(self, result, userdata):
        if result == GstPbutils.InstallPluginsReturn.SUCCESS:
            self.fatal_error_dialog("Codec installation successful",
                        submsg="The required codec was installed, please restart Pithos.")
        else:
            self.error_dialog("Codec installation failed", None,
                        submsg="The required codec failed to install. Either manually install it or try another quality setting.")

    def on_gst_element(self, bus, message):
        if GstPbutils.is_missing_plugin_message(message):
            if GstPbutils.install_plugins_supported():
                details = GstPbutils.missing_plugin_message_get_installer_detail(message)
                GstPbutils.install_plugins_async([details,], None, self.on_gst_plugin_installed, None)
            else:
                self.error_dialog("Missing codec", None,
                        submsg="GStreamer is missing a plugin and it could not be automatically installed. Either manually install it or try another quality setting.")

    def on_gst_error(self, bus, message):
        err, debug = message.parse_error()
        logging.error("Gstreamer error: %s, %s, %s" % (err, debug, err.code))
        if self.current_song:
            self.current_song.message = "Error: "+str(err)

        self.gstreamer_error = str(err)
        self.gstreamer_errorcount_1 += 1

        if not GstPbutils.install_plugins_installation_in_progress():
            self.next_song()

    def gst_tag_handler(self, tag_info):
        def handler(_x, tag, _y):
            # An exhaustive list of tags is available at
            # https://developer.gnome.org/gstreamer/stable/gstreamer-GstTagList.html
            # but Pandora seems to only use those
            if tag == 'datetime':
                _, datetime = tag_info.get_date_time(tag)
                value = datetime.to_iso8601_string()
            elif tag in ('container-format', 'audio-codec'):
                _, value = tag_info.get_string(tag)
            elif tag in ('bitrate', 'maximum-bitrate', 'minimum-bitrate'):
                _, value = tag_info.get_uint(tag)
            else:
                value = 'Don\'t know the type of this'

            logging.debug('Found tag "%s" in stream: "%s" (type: %s)' % (tag, value, type(value)))

            if tag == 'bitrate':
                self.current_song.bitrate = value / 1000
                self.update_song_row()

        return handler

    def check_if_song_is_ad(self):
        if self.current_song.is_ad is None:
            if self.current_song.duration:
                if self.current_song.get_duration_sec() < 45:  # Less than 45 seconds we assume it's an ad
                    logging.info('Ad detected!')
                    self.current_song.is_ad = True
                    self.update_song_row()
                else:
                    logging.info('Not an Ad..')
                    self.current_song.is_ad = False
            else:
                logging.warning('dur_stat is False. The assumption that duration is available once the audio-codec messages feeds is bad.')

    def on_gst_tag(self, bus, message):
        tag_info = message.parse_tag()
        tag_handler = self.gst_tag_handler(tag_info)
        tag_info.foreach(tag_handler, None)

    def on_gst_buffering(self, bus, message):
        # per GST documentation:
        # Note that applications should keep/set the pipeline in the PAUSED state when a BUFFERING
        # message is received with a buffer percent value < 100 and set the pipeline back to PLAYING
        # state when a BUFFERING message with a value of 100 percent is received.

        # 100% doesn't mean the entire song is downloaded, but it does mean that it's safe to play.
        # trying to play before 100% will cause stuttering.
        percent = message.parse_buffering()
        if self.playing:
            if percent < 100:
                # If our previous buffer was at 100, but now it's < 100,
                # then we should pause until the buffer is full.
                if self.player_status.buffer_percent == 100:
                  self.player.set_state(Gst.State.PAUSED)
                  self.player_status.began_buffering = time.time()
            else:
                self.player.set_state(Gst.State.PLAYING)
                logging.debug("Took %.3f to buffer", time.time() - self.player_status.began_buffering)
                self.player_status.began_buffering = None
        self.player_status.buffer_percent = percent
        self.update_song_row()
        logging.debug("Buffering (%i%%)", self.player_status.buffer_percent)

    def set_volume_cb(self, volume):
        # Convert to the cubic scale that the volume slider uses
        scaled_volume = math.pow(volume, 1.0/3.0)
        self.volume.handler_block_by_func(self.on_volume_change_event)
        self.volume.set_property("value", scaled_volume)
        self.volume.handler_unblock_by_func(self.on_volume_change_event)
        self.preferences['volume'] = volume

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
                msg.append("%0dkbit/s" % (song.bitrate))

            if song.position is not None and song.duration is not None:
                pos_str = self.format_time(song.position)
                msg.append("%s / %s" % (pos_str, song.duration_message))
                if not self.playing:
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

    def song_icon(self, song):
        if song.tired:
            return Gtk.STOCK_JUMP_TO
        if song.rating == RATE_LOVE:
            return Gtk.STOCK_ABOUT
        if song.rating == RATE_BAN:
            return Gtk.STOCK_CANCEL

    def update_song_row(self, song = None):
        if song is None:
            song = self.current_song
        if song:
            self.songs_model[song.index][1] = self.song_text(song)
            self.songs_model[song.index][2] = self.song_icon(song) or ""
        return self.playing

    def create_ui_loop(self):
        if not self.ui_loop_timer_id:
            self.ui_loop_timer_id = GLib.timeout_add_seconds(1, self.update_song_row)

    def destroy_ui_loop(self):
        if self.ui_loop_timer_id:
            GLib.source_remove(self.ui_loop_timer_id)
            self.ui_loop_timer_id = 0

    def stations_combo_changed(self, widget):
        index = widget.get_active()
        if index>=0:
            self.station_changed(self.stations_model[index][0])

    def format_time(self, time_int):
        if time_int is None:
          return None

        time_int = time_int // 1000000000
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

    def love_song(self, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('song-rating-changed', song)
        self.worker_run(song.rate, (RATE_LOVE,), callback, "Loving song...")


    def ban_song(self, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('song-rating-changed', song)
        self.worker_run(song.rate, (RATE_BAN,), callback, "Banning song...")
        if song is self.current_song:
            self.next_song()

    def unrate_song(self, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('song-rating-changed', song)
        self.worker_run(song.rate, (RATE_NONE,), callback, "Removing song rating...")

    def tired_song(self, song=None):
        song = song or self.current_song
        def callback(l):
            self.update_song_row(song)
            self.emit('song-rating-changed', song)
        self.worker_run(song.set_tired, (), callback, "Putting song on shelf...")
        if song is self.current_song:
            self.next_song()

    def bookmark_song(self, song=None):
        song = song or self.current_song
        self.worker_run(song.bookmark, (), None, "Bookmarking...")

    def bookmark_song_artist(self, song=None):
        song = song or self.current_song
        self.worker_run(song.bookmark_artist, (), None, "Bookmarking...")

    def on_menuitem_love(self, widget):
        self.love_song(self.selected_song())

    def on_menuitem_ban(self, widget):
        self.ban_song(self.selected_song())

    def on_menuitem_unrate(self, widget):
        self.unrate_song(self.selected_song())

    def on_menuitem_tired(self, widget):
        self.tired_song(self.selected_song())

    def on_menuitem_info(self, widget):
        song = self.selected_song()
        open_browser(song.songDetailURL)

    def on_menuitem_bookmark_song(self, widget):
        self.bookmark_song(self.selected_song())

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
                self.song_menu_love.set_property("visible", rating != RATE_LOVE);
                self.song_menu_unlove.set_property("visible", rating == RATE_LOVE);
                self.song_menu_ban.set_property("visible", rating != RATE_BAN);
                self.song_menu_unban.set_property("visible", rating == RATE_BAN);

                self.song_menu.popup( None, None, None, None, event.button, time)
                return True

            if event.button == 1 and event.type == Gdk.EventType._2BUTTON_PRESS:
                logging.info("Double clicked on song %s", self.selected_song().index)
                if self.selected_song().index <= self.current_song_index:
                    return False
                self.start_song(self.selected_song().index)

    def set_player_volume(self, value):
        logging.info('%.3f' % value)
        # Use a cubic scale for volume. This matches what PulseAudio uses.
        volume = math.pow(value, 3)
        self.player.set_property("volume", volume)
        self.preferences['volume'] = volume

    def adjust_volume(self, amount):
        old_volume = self.volume.get_property("value")
        new_volume = max(0.0, min(1.0, old_volume + 0.02 * amount))

        if new_volume != old_volume:
            self.volume.set_property("value", new_volume)

    def on_volume_change_event(self, volumebutton, value):
        self.set_player_volume(value)

    def station_properties(self, *ignore):
        open_browser(self.current_station.info_url)

    def show_about(self):
        """about - display the about box for pithos """
        about = AboutPithosDialog.NewAboutPithosDialog()
        about.set_transient_for(self)
        about.set_version(VERSION)
        about.run()
        about.destroy()

    def show_preferences(self, is_startup=False):
        """preferences - display the preferences window for pithos """
        if is_startup:
            self.prefs_dlg.set_type_hint(Gdk.WindowTypeHint.NORMAL)

        old_prefs = dict(self.preferences)
        response = self.prefs_dlg.run()
        self.prefs_dlg.hide()

        if response == Gtk.ResponseType.OK:
            self.preferences = self.prefs_dlg.get_preferences()
            if not is_startup:
                if (   self.preferences['proxy'] != old_prefs['proxy']
                    or self.preferences['control_proxy'] != old_prefs['control_proxy']):
                    self.set_proxy()
                if self.preferences['audio_quality'] != old_prefs['audio_quality']:
                    self.set_audio_quality()
                if (   self.preferences['username'] != old_prefs['username']
                    or self.preferences['password'] != old_prefs['password']
                    or self.preferences['pandora_one'] != old_prefs['pandora_one']):
                        self.pandora_connect()
            else:
                self.prefs_dlg.set_type_hint(Gdk.WindowTypeHint.DIALOG)
            load_plugins(self)

    def show_stations(self):
        if self.stations_dlg:
            self.stations_dlg.present()
        else:
            self.stations_dlg = StationsDialog.NewStationsDialog(self)
            self.stations_dlg.set_transient_for(self)
            self.stations_dlg.show_all()

    def refresh_stations(self, *ignore):
        self.worker_run(self.pandora.get_stations, (), self.process_stations, "Refreshing stations...")

    def set_initial_pos(self):
        """ Moves window to position stored in preferences """
        x, y = self.preferences['x_pos'], self.preferences['y_pos']
        if not x is None and not y is None:
            self.move(int(x), int(y))

    def bring_to_top(self, *ignore):
        self.set_initial_pos()
        self.show()
        self.present()

    def on_configure_event(self, widget, event):
        self.preferences['x_pos'], self.preferences['y_pos'] = event.x, event.y

    def on_kb_playpause(self, widget=None, data=None):
        if not isinstance(widget.get_focus(), Gtk.Button) and data.keyval == 32:
            self.playpause()
            return True

    def quit(self, widget=None, data=None):
        """quit - signal handler for closing the PithosWindow"""
        self.destroy()

    def on_destroy(self, widget, data=None):
        """on_destroy - called when the PithosWindow is close. """
        self.stop()
        self.preferences['last_station_id'] = self.current_station_id
        self.prefs_dlg.save()
        self.quit()

def NewPithosWindow(app, options):
    """NewPithosWindow - returns a fully instantiated
    PithosWindow object. Use this function rather than
    creating a PithosWindow directly.
    """

    builder = Gtk.Builder()
    builder.add_from_file(get_ui_file('main'))
    window = builder.get_object("pithos_window")
    window.set_application(app)
    window.finish_initializing(builder, options)
    return window

class PithosApplication(Gtk.Application):
    def __init__(self):
        # Use org.gnome to avoid conflict with existing dbus interface net.kevinmehall
        Gtk.Application.__init__(self, application_id='org.gnome.pithos',
                                flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.options = None

    def do_startup(self):
        Gtk.Application.do_startup(self)

        # Setup appmenu
        builder = Gtk.Builder()
        builder.add_from_file(get_ui_file('menu'))
        menu = builder.get_object("app-menu")
        self.set_app_menu(menu)

        action = Gio.SimpleAction.new("stations", None)
        action.connect("activate", self.stations_cb)
        self.add_action(action)

        action = Gio.SimpleAction.new("preferences", None)
        action.connect("activate", self.prefs_cb)
        self.add_action(action)

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.about_cb)
        self.add_action(action)

        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.quit_cb)
        self.add_action(action)

    # FIXME: do_local_command_line() segfaults?
    def do_command_line(self, args):
        Gtk.Application.do_command_line(self, args)

        parser = argparse.ArgumentParser()
        parser.add_argument("-v", "--verbose", action="count", default=0, dest="verbose", help="Show debug messages")
        parser.add_argument("-t", "--test", action="store_true", dest="test", help="Use a mock web interface instead of connecting to the real Pandora server")
        self.options = parser.parse_args(args.get_arguments()[1:])

        # First, get rid of existing logging handlers due to call in header as per
        # http://stackoverflow.com/questions/1943747/python-logging-before-you-run-logging-basicconfig
        logging.root.handlers = []

        #set the logging level to show debug messages
        if self.options.verbose > 1:
            log_level = logging.DEBUG
        elif self.options.verbose == 1:
            log_level = logging.INFO
        else:
            log_level = logging.WARN

        logging.basicConfig(level=log_level, format='%(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s')

        self.do_activate()

        return 0

    def do_activate(self):
        if not self.window:
            logging.info("Pithos %s" %VERSION)
            self.window = NewPithosWindow(self, self.options)

        self.window.present()

    def do_shutdown(self):
        Gtk.Application.do_shutdown(self)
        self.window.destroy()

    def stations_cb(self, action, param):
        self.window.show_stations()

    def prefs_cb(self, action, param):
        self.window.show_preferences()

    def about_cb(self, action, param):
        self.window.show_about()

    def quit_cb(self, action, param):
        self.window.destroy()

def main():
    app = PithosApplication()
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

if __name__ == '__main__':
    main()
