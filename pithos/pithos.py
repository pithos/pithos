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

import sys
import os, time
import gtk, gobject, pango

import gst
import cgi
import math
import webbrowser
import os
import urllib2
import dbus
import json
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
from .util import *
from .pithosconfig import get_data_file, getdatapath, VERSION
from .gobject_worker import GObjectWorker
from .plugin import load_plugins
from .dbus_service import PithosDBusProxy, try_to_raise
from .sound_menu import PithosSoundMenu
from .pandora import *
from .pandora.data import *


def openBrowser(url):
    print "Opening %s"%url
    webbrowser.open(url)
    try:
        os.wait() # workaround for http://bugs.python.org/issue5993
    except:
        pass

def buttonMenu(button, menu):
    def cb(button):
        allocation = button.get_allocation()
        x, y = button.window.get_origin()
        x += allocation.x
        y += allocation.y + allocation.height
        menu.popup(None, None, (lambda *ignore: (x, y, True)), 1, gtk.get_current_event_time())

    button.connect('clicked', cb)

ALBUM_ART_SIZE = 96
ALBUM_ART_X_PAD = 6

class CellRendererAlbumArt(gtk.GenericCellRenderer):
    def __init__(self):
        self.__gobject_init__()
        self.icon = None
        self.pixbuf = None
        self.rate_bg = gtk.gdk.pixbuf_new_from_file(os.path.join(getdatapath(), 'media', 'rate_bg.png'))

    __gproperties__ = {
        'icon': (str, 'icon', 'icon', '', gobject.PARAM_READWRITE),
        'pixbuf': (gtk.gdk.Pixbuf, 'pixmap', 'pixmap',  gobject.PARAM_READWRITE)
    }

    def do_set_property(self, pspec, value):
        setattr(self, pspec.name, value)
    def do_get_property(self, pspec):
        return getattr(self, pspec.name)
    def on_get_size(self, widget, cell_area):
        return (0, 0, ALBUM_ART_SIZE + ALBUM_ART_X_PAD, ALBUM_ART_SIZE)
    def on_render(self, window, widget, background_area, cell_area, expose_area, flags):
        if self.pixbuf:
            window.draw_pixbuf(None, self.pixbuf, 0, 0, cell_area.x, cell_area.y, width=-1, height=-1, dither=gtk.gdk.RGB_DITHER_NORMAL, x_dither=0, y_dither=0)
        if self.icon:
            x = cell_area.x+(cell_area.width-self.rate_bg.get_width()) - ALBUM_ART_X_PAD # right
            y = cell_area.y+(cell_area.height-self.rate_bg.get_height()) # bottom
            window.draw_pixbuf(None, self.rate_bg, 0, 0, x, y, width=-1, height=-1, dither=gtk.gdk.RGB_DITHER_NORMAL, x_dither=0, y_dither=0)

            icon = widget.style.lookup_icon_set(self.icon)
            pixbuf = icon.render_icon(widget.style, widget.get_direction(), gtk.STATE_ACTIVE, gtk.ICON_SIZE_MENU, widget, detail=None)
            x = cell_area.x+(cell_area.width-pixbuf.get_width())-5 - ALBUM_ART_X_PAD # right
            y = cell_area.y+(cell_area.height-pixbuf.get_height())-5 # bottom
            window.draw_pixbuf(None, pixbuf, 0, 0, x, y, width=-1, height=-1, dither=gtk.gdk.RGB_DITHER_NORMAL, x_dither=0, y_dither=0)

def get_album_art(url, *extra):
     content = urllib2.urlopen(url).read()
     l = gtk.gdk.PixbufLoader()
     l.set_size(ALBUM_ART_SIZE, ALBUM_ART_SIZE)
     l.write(content)
     l.close()
     return (l.get_pixbuf(),) + extra


class PithosWindow(gtk.Window):
    __gtype_name__ = "PithosWindow"
    __gsignals__ = {
        "song-changed": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        "song-ended": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        "song-rating-changed": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_PYOBJECT,)),
        "play-state-changed": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
        "user-changed-play-state": (gobject.SIGNAL_RUN_FIRST, gobject.TYPE_NONE, (gobject.TYPE_BOOLEAN,)),
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
        self.cmdopts = cmdopts

        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)

        self.prefs_dlg = PreferencesPithosDialog.NewPreferencesPithosDialog()
        self.preferences = self.prefs_dlg.get_preferences()

        if self.prefs_dlg.fix_perms():
            # Changes were made, save new config variable
            self.prefs_dlg.save()
        self.init_core()
        self.init_ui()

        self.plugins = {}
        load_plugins(self)

        self.dbus_service = PithosDBusProxy(self)
        self.sound_menu = PithosSoundMenu(self)

        if not self.preferences['username']:
            self.show_preferences(is_startup=True)

        self.pandora = make_pandora(self.cmdopts.test)
        self.set_proxy()
        self.set_audio_quality()
        self.pandora_connect()

    def init_core(self):
        #                                Song object            display text  icon  album art
        self.songs_model = gtk.ListStore(gobject.TYPE_PYOBJECT, str,          str,  gtk.gdk.Pixbuf)
        #                                   Station object         station name
        self.stations_model = gtk.ListStore(gobject.TYPE_PYOBJECT, str)

        self.player = gst.element_factory_make("playbin2", "player")
        self.player.props.flags |= (1 << 7) # enable progressive download (GST_PLAY_FLAG_DOWNLOAD)
        bus = self.player.get_bus()
        bus.add_signal_watch()
        bus.connect("message::eos", self.on_gst_eos)
        bus.connect("message::buffering", self.on_gst_buffering)
        bus.connect("message::error", self.on_gst_error)
        self.player.connect("notify::volume", self.on_gst_volume)
        self.player.connect("notify::source", self.on_gst_source)
        self.time_format = gst.Format(gst.FORMAT_TIME)

        self.stations_dlg = None

        self.playing = False
        self.current_song_index = None
        self.current_station = None
        self.current_station_id = self.preferences.get('last_station_id')

        self.buffer_percent = 100
        self.auto_retrying_auth = False
        self.have_stations = False
        self.playcount = 0
        self.gstreamer_errorcount_1 = 0
        self.gstreamer_errorcount_2 = 0
        self.gstreamer_error = ''
        self.waiting_for_playlist = False
        self.start_new_playlist = False

        self.worker = GObjectWorker()
        self.art_worker = GObjectWorker()

        aa = gtk.gdk.pixbuf_new_from_file(os.path.join(getdatapath(), 'media', 'album_default.png'))
        self.default_album_art = aa.scale_simple(ALBUM_ART_SIZE, ALBUM_ART_SIZE, gtk.gdk.INTERP_BILINEAR)

    def init_ui(self):
        gobject.set_application_name("Pithos")
        gtk.window_set_default_icon_name('pithos')
        os.environ['PULSE_PROP_media.role'] = 'music'

        self.playpause_button = self.builder.get_object('playpause_button')

        self.volume = self.builder.get_object('volume')
        self.volume.set_property("value", math.pow(float(self.preferences['volume']), 1.0/3.0))

        self.statusbar = self.builder.get_object('statusbar1')

        self.song_menu = self.builder.get_object('song_menu')
        self.song_menu_love = self.builder.get_object('menuitem_love')
        self.song_menu_unlove = self.builder.get_object('menuitem_unlove')
        self.song_menu_ban = self.builder.get_object('menuitem_ban')
        self.song_menu_unban = self.builder.get_object('menuitem_unban')

        self.songs_treeview = self.builder.get_object('songs_treeview')
        self.songs_treeview.set_model(self.songs_model)

        title_col   = gtk.TreeViewColumn()

        def bgcolor_data_func(column, cell, model, iter):
            if model.get_value(iter, 0) is self.current_song:
                bgcolor = column.get_tree_view().get_style().mid[gtk.STATE_NORMAL]
            else:
                bgcolor = column.get_tree_view().get_style().base[gtk.STATE_NORMAL]
            cell.set_property("cell-background-gdk", bgcolor)

        render_icon = CellRendererAlbumArt()
        title_col.pack_start(render_icon, expand=False)
        title_col.add_attribute(render_icon, "icon", 2)
        title_col.add_attribute(render_icon, "pixbuf", 3)
        title_col.set_cell_data_func(render_icon, bgcolor_data_func)

        render_text = gtk.CellRendererText()
        render_text.props.ellipsize = pango.ELLIPSIZE_END
        title_col.pack_start(render_text, expand=True)
        title_col.add_attribute(render_text, "markup", 1)
        title_col.set_cell_data_func(render_text, bgcolor_data_func)

        self.songs_treeview.append_column(title_col)

        self.songs_treeview.connect('button_press_event', self.on_treeview_button_press_event)

        self.stations_combo = self.builder.get_object('stations')
        self.stations_combo.set_model(self.stations_model)
        render_text = gtk.CellRendererText()
        self.stations_combo.pack_start(render_text, expand=True)
        self.stations_combo.add_attribute(render_text, "text", 1)
        self.stations_combo.set_row_separator_func(lambda model, iter: model.get_value(iter, 0) is None)

        buttonMenu(self.builder.get_object("toolbutton_options"), self.builder.get_object("menu_options"))

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

        system_proxies = urllib.getproxies()
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
            handlers.append(urllib2.ProxyHandler({'http': global_proxy, 'https': global_proxy}))
        global_opener = urllib2.build_opener(*handlers)
        urllib2.install_opener(global_opener)

        control_opener = global_opener
        control_proxy = self.preferences['control_proxy']
        if control_proxy:
            control_opener = urllib2.build_opener(urllib2.ProxyHandler({'http': control_proxy, 'https': control_proxy}))
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
        self.buffer_percent = 100
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
            self.player.set_state(gst.STATE_PLAYING)
            gobject.timeout_add_seconds(1, self.update_song_row)
        self.playpause_button.set_stock_id(gtk.STOCK_MEDIA_PAUSE)
        self.update_song_row()
        self.emit('play-state-changed', True)

    def user_pause(self, *ignore):
        self.pause()
        self.emit('user-changed-play-state', False)

    def pause(self):
        self.playing = False
        self.player.set_state(gst.STATE_PAUSED)
        self.playpause_button.set_stock_id(gtk.STOCK_MEDIA_PLAY)
        self.update_song_row()
        self.emit('play-state-changed', False)


    def stop(self):
        prev = self.current_song
        if prev and prev.start_time:
            prev.finished = True
            try:
                prev.duration = self.player.query_duration(self.time_format, None)[0] / 1000000000
                prev.position = self.player.query_position(self.time_format, None)[0] / 1000000000
            except gst.QueryError:
                prev.duration = prev.position = None
            self.emit("song-ended", prev)

        self.playing = False
        self.player.set_state(gst.STATE_NULL)
        self.emit('play-state-changed', False)

    def playpause(self, *ignore):
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

        response = dialog.run()
        dialog.hide()

        self.quit()

    def api_update_dialog(self):
        dialog = self.builder.get_object("api_update_dialog")
        response = dialog.run()
        if response:
            openBrowser("http://kevinmehall.net/p/pithos/itbroke?utm_source=pithos&utm_medium=app&utm_campaign=%s"%VERSION)
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

    def on_gst_eos(self, bus, message):
        logging.info("EOS")
        self.next_song()

    def on_gst_error(self, bus, message):
        err, debug = message.parse_error()
        logging.error("Gstreamer error: %s, %s, %s" % (err, debug, err.code))
        if self.current_song:
            self.current_song.message = "Error: "+str(err)

        #if err.code is int(gst.CORE_ERROR_MISSING_PLUGIN):
        #    self.fatal_error_dialog("Missing codec", submsg="GStreamer is missing a plugin")
        #    return

        self.gstreamer_error = str(err)
        self.gstreamer_errorcount_1 += 1
        self.next_song()

    def on_gst_buffering(self, bus, message):
        percent = message.parse_buffering()
        self.buffer_percent = percent
        #if percent < 100:
            #self.player.set_state(gst.STATE_PAUSED)
        #elif self.playing:
            #self.player.set_state(gst.STATE_PLAYING)
        self.update_song_row()

    def set_volume_cb(self, volume):
        # Convert to the cubic scale that the volume slider uses
        scaled_volume = math.pow(volume, 1.0/3.0)
        self.volume.handler_block_by_func(self.on_volume_change_event)
        self.volume.set_property("value", scaled_volume)
        self.volume.handler_unblock_by_func(self.on_volume_change_event)
        self.preferences['volume'] = volume

    def on_gst_volume(self, player, volumespec):
        vol = self.player.get_property('volume')
        gobject.idle_add(self.set_volume_cb, vol)

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
        title = cgi.escape(song.title)
        artist = cgi.escape(song.artist)
        album = cgi.escape(song.album)
        msg = []
        if song is self.current_song:
            try:
                dur_int = self.player.query_duration(self.time_format, None)[0]
                dur_str = self.format_time(dur_int)
                pos_int = self.player.query_position(self.time_format, None)[0]
                pos_str = self.format_time(pos_int)
                msg.append("%s / %s" %(pos_str, dur_str))
                if not self.playing:
                    msg.append("Paused")
            except gst.QueryError:
                pass
            if self.buffer_percent < 100:
                msg.append("Buffering (%i%%)"%self.buffer_percent)
        if song.message:
            msg.append(song.message)
        msg = " - ".join(msg)
        if not msg:
            msg = " "
        return "<b><big>%s</big></b>\nby <b>%s</b>\n<small>from <i>%s</i></small>\n<small>%s</small>"%(title, artist, album, msg)

    def song_icon(self, song):
        if song.tired:
            return gtk.STOCK_JUMP_TO
        if song.rating == RATE_LOVE:
            return gtk.STOCK_ABOUT
        if song.rating == RATE_BAN:
            return gtk.STOCK_CANCEL

    def update_song_row(self, song = None):
        if song is None:
            song = self.current_song
        if song:
            self.songs_model[song.index][1] = self.song_text(song)
            self.songs_model[song.index][2] = self.song_icon(song)
        return self.playing

    def stations_combo_changed(self, widget):
        index = widget.get_active()
        if index>=0:
            self.station_changed(self.stations_model[index][0])

    def format_time(self, time_int):
        time_int = time_int / 1000000000
        s = time_int % 60
        time_int /= 60
        m = time_int % 60
        time_int /= 60
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
        openBrowser(song.songDetailURL)

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

                self.song_menu.popup( None, None, None, event.button, time)
                return True

            if event.button == 1 and event.type == gtk.gdk._2BUTTON_PRESS:
                logging.info("Double clicked on song %s", self.selected_song().index)
                if self.selected_song().index <= self.current_song_index:
                    return False
                self.start_song(self.selected_song().index)

    def set_player_volume(self, value):
        logging.info('%.3f' % value)
        # Use a cubic scale for volume. This matches what PulseAudio uses.
        volume = math.pow(value, 3)
        self.player.set_property("volume", volume)
        self.preferences['volume'] = value

    def raise_volume(self, down=False):
        old_volume = self.volume.get_property("value")
        new_volume = max(0.0, min(1.0, old_volume + 0.02 * (-1.0 if down else 1.0)))

        if new_volume != old_volume:
            self.volume.set_property("value", new_volume)

    def on_volume_change_event(self, volumebutton, value):
        self.set_player_volume(value)

    def station_properties(self, *ignore):
        openBrowser(self.current_station.info_url)

    def open_web_site(self, *ignore):
        openBrowser("http://kevinmehall.net/p/pithos?utm_source=pithos&utm_medium=app&utm_campaign=%s"%VERSION)

    def report_bug(self, *ignore):
        openBrowser("https://bugs.launchpad.net/pithos")

    def about(self, widget, data=None):
        """about - display the about box for pithos """
        about = AboutPithosDialog.NewAboutPithosDialog()
        about.set_version(VERSION)
        response = about.run()
        about.destroy()

    def show_preferences(self, widget=None, data=None, is_startup=False):
        """preferences - display the preferences window for pithos """
        old_prefs = dict(self.preferences)
        response = self.prefs_dlg.run()
        self.prefs_dlg.hide()

        if response == gtk.RESPONSE_OK:
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
            load_plugins(self)

    def stations_dialog(self, *ignore):
        if self.stations_dlg:
            self.stations_dlg.present()
        else:
            self.stations_dlg = StationsDialog.NewStationsDialog(self)
            self.stations_dlg.show_all()

    def refresh_stations(self, *ignore):
        self.worker_run(self.pandora.get_stations, (), self.process_stations, "Refreshing stations...")

    def bring_to_top(self, *ignore):
        self.show()
        self.present()

    def on_kb_playpause(self, widget=None, data=None):
        if not isinstance(widget.get_focus(), gtk.Button) and data.keyval == 32:
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
        gtk.main_quit()

def NewPithosWindow(options):
    """NewPithosWindow - returns a fully instantiated
    PithosWindow object. Use this function rather than
    creating a PithosWindow directly.
    """

    #look for the ui file that describes the ui
    ui_filename = os.path.join(getdatapath(), 'ui', 'PithosWindow.ui')
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = gtk.Builder()
    builder.add_from_file(ui_filename)
    window = builder.get_object("pithos_window")
    window.finish_initializing(builder, options)
    return window


def main():
    import logging, optparse
    parser = optparse.OptionParser(version="Pithos %s"%(VERSION))
    parser.add_option("-v", "--verbose", action="store_true", dest="verbose", help="Show debug messages")
    parser.add_option("-t", "--test", action="store_true", dest="test", help="Use a mock web interface instead of connecting to the real Pandora server")
    (options, args) = parser.parse_args()

    if not options.test and try_to_raise():
        print "Raised existing Pithos instance"
    else:

        #set the logging level to show debug messages
        if options.verbose:
            logging.basicConfig(level=logging.INFO, format='%(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s')
        else:
            logging.basicConfig(level=logging.WARNING)

        logging.info("Pithos %s"%VERSION)

        window = NewPithosWindow(options)
        window.show()
        gtk.main()


if __name__ == '__main__':
    main()

