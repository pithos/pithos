import datetime
import logging
import time
import urllib

import gi
gi.require_version('Gst', '1.0')
from gi.repository import Gst, GstPbutils

from pithos.player import PlayerBase
from pithos.util import parse_proxy, PeriodicCallback


_initialized = False
def _init_gst(args):
    global _initialized

    if not _initialized:
        if args:
            args = [''] + args
        Gst.init(args)
        _initialized = True

_zero = datetime.timedelta(0)
_one_second = datetime.timedelta(seconds=1)
_desired_buffer = datetime.timedelta(seconds=10)


class GstPlayer (PlayerBase):
    description = Gst.version_string()
    def _init(self):
        _init_gst(self._cmd_line_args)

        self.gstplayer = Gst.ElementFactory.make("playbin", "gstplayer")
        self.gstplayer.props.flags = ( 1<<1   # GST_PLAY_FLAG_AUDIO
                                     | 1<<4   # GST_PLAY_FLAG_SOFT_VOLUME
                                     | 1<<7   # GST_PLAY_FLAG_DOWNLOAD
                                     )

        self.bus = self.gstplayer.get_bus()
        self.bus.add_signal_watch()
        self.bus.connect("message::async-done", self._async_done)
        self.bus.connect("message::duration-changed", self._duration_changed)
        self.bus.connect("message::eos", self._on_end_of_song)
        self.bus.connect("message::error", self._on_gst_error)
        self.bus.connect("message::element", self._on_element)
        self.bus.connect("message::tag", self._on_tag_info)

        self.gstplayer.connect("notify::volume", self._on_notify_volume)
        self.gstplayer.connect("source-setup", self._on_source_setup)

        # self.gstplayer.connect("about-to-finish", self._on_about_to_finish)

        self._duration_query = Gst.Query.new_duration(Gst.Format.TIME)
        self._position_query = Gst.Query.new_position(Gst.Format.TIME)
        self._buffering_query = Gst.Query.new_buffering(Gst.Format.PERCENT)

        self._explicit_volume_change = False
        self._volume = 1

        self._next_songs = None
        self._current_state = None
        self._buffer_timer = PeriodicCallback("DownloadCheck",
                                              self._buffering, 250,
                                              use_glib=True)
        self._target_state = Gst.State.READY
        self._buffering_handler_id = None
        self._reset()

    def dispose(self):
        self._reset()
        self.gstplayer.set_state(Gst.State.NULL)

    @property
    def playing(self):
        return self._target_state == Gst.State.PLAYING

    @property
    def buffer_percent(self):
        if (self._target_state == Gst.State.PLAYING and
            self._current_state == Gst.State.PAUSED):
            return self._buffer_percent
        return None

    @property
    def volume(self):
        return self._volume

    @volume.setter
    def volume(self, vol):
        vol = round(vol, 3)
        if vol != self._volume:
            self._volume = vol
            self.gstplayer.props.volume = vol

    def play_song(self, song):
        self._set_state(None, Gst.State.READY)

        super().play_song(song)
        self.gstplayer.props.uri = song.audioUrl

        # Player should start in PLAYING state. If you start in PAUSED, (as
        # recommended in the Gst docs,) the position isn't reset from the
        # previous song, and it messes up the buffering calculations.
        self._set_state(Gst.State.PLAYING, Gst.State.PLAYING)

    def play(self):
        self._set_state(Gst.State.PLAYING)

    def pause(self):
        self._set_state(Gst.State.PAUSED)

    def stop(self):
        self._reset()

    def get_current_position(self):
        pos_stat = self.gstplayer.query(self._position_query)
        if pos_stat:
            _, position = self._position_query.parse_position()
            self.current_song.position = position
            return position

    def get_current_duration(self):
        return self._current_song.duration

    ### Private implementation:

    def _reset(self):
        self._began_buffering = None
        self._buffer_timer.stop()
        if self._buffering_handler_id:
            self.bus.disconnect(self._buffering_handler_id)
            self._buffering_handler_id = None
        self._current_song = None
        self._download_percent = 0
        self._is_async_done = False
        self._set_state(Gst.State.READY, Gst.State.READY)
        self._buffer_percent = 0

    def _set_state(self, target_state, real_state=None):
        if (target_state == self._target_state and
            (real_state is None or real_state == self._current_state)):
            return

        old_target = self._target_state
        if target_state is not None:
            self._target_state = target_state
        if real_state is None:
            if old_target == self._current_state:
                real_state = target_state
            else:
                return

        if real_state != self._current_state:
            ret = self.gstplayer.set_state(real_state)
            if ret == Gst.StateChangeReturn.FAILURE:
                raise Exception("Error changing player state: " + str(ret))
            self._current_state = real_state
            return ret

    def _react_to_buffering(self, hard_limit=True):
        if self._buffer_percent >= 1:
            if self._began_buffering is not None:
                logging.debug("Buffered for %.3fs before starting playback.",
                              time.time() - self._began_buffering)
            prev_state = self._current_state
            ret = self._set_state(None, self._target_state)
            if ret and ret != Gst.StateChangeReturn.SUCCESS:
                self._current_state = prev_state
                return True
            self._began_buffering = None
        elif hard_limit:
            # We've drained the buffer, let it fill up
            self._set_state(None, Gst.State.PAUSED)
            if self._began_buffering is None:
                self._began_buffering = time.time()
            return True

        return False

    def _stream_buffering(self, bus=None, message=None):
        if message:
            percent = message.parse_buffering()
        else:
            # This is the manual call, let's listen for future bus events.
            if not self._buffering_handler_id:
                self._buffering_handler_id = self.bus.connect(
                    "message::buffering", self._stream_buffering)

            _, percent = self._buffering_query.parse_buffering_percent()

        self._buffer_percent = percent/100
        self._react_to_buffering()

    def _download_buffering(self, first=False):
        _, start, stop, _ = self._buffering_query.parse_buffering_range()

        download_percent = stop / Gst.FORMAT_PERCENT_MAX

        if download_percent is None or self._current_song.duration is None:
            return True

        position = self.get_current_position() / 1e6
        duration = self._current_song.duration / 1e6
        remaining_playback_time = datetime.timedelta(
            milliseconds=(duration * download_percent) - position)
        song_remaining = datetime.timedelta(milliseconds=duration - position)

        if remaining_playback_time < _zero:
            # Position is probably borked... just hope it's better next time.
            return True
        self._buffer_percent = remaining_playback_time / _desired_buffer
        if remaining_playback_time >= song_remaining:
            self._buffer_percent = 1

        self._react_to_buffering(
            hard_limit=first or remaining_playback_time < _one_second)

        if download_percent >= 1:
            return False
        # Don't call back until we're close to running out of buffer
        if self._current_state == Gst.State.PLAYING:
            return int((remaining_playback_time.total_seconds() - 1) * 1000)
        return 250

    def _buffering(self, first=False):
        buf_stat = self.gstplayer.query(self._buffering_query)
        if buf_stat:
            mode, *_ = self._buffering_query.parse_buffering_stats()

            if mode == Gst.BufferingMode.STREAM:
                self._stream_buffering()
            elif mode == Gst.BufferingMode.DOWNLOAD:
                return self._download_buffering(first)
            else:
                logging.warning("Unexpected buffering mode: %s", mode)
        else:
            return True

    def _async_done(self, bus, message):
        self._is_async_done = True

        self._duration_changed()

        if self._buffering(first=True):
            self._buffer_timer.start()

    def _duration_changed(self, *_):
        if self._is_async_done:
            dur_stat = self.gstplayer.query(self._duration_query)
            if dur_stat:
                _, self._current_song.duration = self._duration_query.parse_duration()
                self.emit("song-info-changed", self._current_song)
            else:
                logging.warning("Async complete, "
                                "but unable to get song duration.")

    def _on_notify_volume(self, playbin, volume_propspec):
        player_vol = round(self.gstplayer.props.volume, 3)
        if player_vol != self._volume:
            self._volume = player_vol
            # Volume change must have happened from an outside source
            self.emit("volume-changed", self._volume)

    def _on_end_of_song(self, bus, message):
        self.emit("song-ended")

    def _on_source_setup(self, playbin, source):
        """Setup httpsoupsrc to match Pithos proxy settings."""
        soup = source.props

        proxy = None
        if self._preferences['proxy']:
            proxy = self.preferences['proxy']

        system_proxies = urllib.request.getproxies()
        if 'http' in system_proxies:
            proxy = system_proxies['http']

        if proxy and hasattr(soup, 'proxy'):
            scheme, user, password, hostport = parse_proxy(proxy)
            soup.proxy = hostport
            soup.proxy_id = user
            soup.proxy_pw = password

    def _plugin_installation_complete(self, result, userdata):
        if result == GstPbutils.InstallPluginsReturn.SUCCESS:
            self.emit("error", "Codec installation successful",
                      "The required codec was installed, "
                      "please restart Pithos.",
                      True)
        else:
            self.emit("error", "Codec installation failed",
                      "The required codec failed to install. Either manually "
                      "install it or try another quality setting.",
                      False)

    def _on_element(self, bus, message):
        if GstPbutils.is_missing_plugin_message(message):
            if GstPbutils.install_plugins_supported():
                details = (
                    GstPbutils.missing_plugin_message_get_installer_detail(
                        message))
                GstPbutils.install_plugins_async(
                    [details], None, self._plugin_installation_complete, None)
            else:
                self.emit("error", "Missing codec",
                          "GStreamer is missing a plugin and it could not be "
                          "automatically installed. Either manually install "
                          "it or try another quality setting.",
                          False)

    def _on_gst_error(self, bus, message):
        err, debug = message.parse_error()
        logging.error("Gstreamer error from %s: %s, %s, %s",
                      message.src, err, debug, err.code)

        if err.matches(Gst.ResourceError.quark(),
                       Gst.ResourceError.NOT_AUTHORIZED):
            err = 'Playlist entry expired'

        if self._current_song:
            self._current_song.message = "Error: " + str(err)

        if not GstPbutils.install_plugins_installation_in_progress():
            self.emit("song-ended")

    def _on_tag_info(self, bus, message):
        tag_info = message.parse_tag()
        tag_info.foreach(self._tag_handler)

    def _tag_handler(self, taglist, tag):
        # An exhaustive list of tags is available at
        # https://developer.gnome.org/gstreamer/stable/gstreamer-GstTagList.html
        # but Pandora seems to only use these
        if tag == 'datetime':
            _, datetime = taglist.get_date_time(tag)
            value = datetime.to_iso8601_string()
        elif tag in ('container-format', 'audio-codec'):
            _, value = taglist.get_string(tag)
        elif 'bitrate' in tag:
            _, value = taglist.get_uint(tag)
        else:
            value = "Don't know the type of this"

        if tag == 'bitrate' and self._current_song.bitrate != value:
            self._current_song.bitrate = value
            self.emit("song-info-changed", self._current_song)
