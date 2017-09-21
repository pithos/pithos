#
# Copyright (C) 2017 Jason Gray <jasonlevigray3@gmail.com>
#
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
# END LICENSE

import logging
import gi
import urllib.request
gi.require_version('Gst', '1.0')
gi.require_version('GstPbutils', '1.0')
from gi.repository import Gst, GstPbutils, GObject, GLib
from enum import IntEnum

from .util import parse_proxy

Gst.init(None)

PLAYER_SECOND = Gst.SECOND


class PseudoGst(IntEnum):
    '''Create aliases to Gst.State so that we can add our own BUFFERING Pseudo state'''
    PLAYING = 1
    PAUSED = 2
    BUFFERING = 3
    STOPPED = 4

    @property
    def state(self):
        value = self.value
        if value == 1:
            return Gst.State.PLAYING
        elif value == 2:
            return Gst.State.PAUSED
        elif value == 3:
            return Gst.State.PAUSED
        elif value == 4:
            return Gst.State.NULL


class GstPlayer(GObject.Object):
    __gtype_name__ = 'GstPlayer'

    __gsignals__ = {
        'eos': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'new-stream-duration': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'new-player-state': (GObject.SignalFlags.RUN_FIRST, None, ()),
        'buffering-finished': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'warning': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'error': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        'fatal-error': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    rg_limiter = GObject.Property(
        type=GObject.TYPE_BOOLEAN,
        default=False,
        nick='rg-limiter prop',
        blurb='enable ReplayGain limiter',
        flags=GObject.ParamFlags.READWRITE,
    )

    rg_fallback_gain = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-60.0,
        maximum=60.0,
        nick='rg-fallback-gain prop',
        blurb='ReplayGain fallback gain',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band0 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band0 prop',
        blurb='gain for the frequency band 29 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band1 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band1 prop',
        blurb='gain for the frequency band 59 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band2 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band2 prop',
        blurb='gain for the frequency band 119 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band3 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band3 prop',
        blurb='gain for the frequency band 237 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band4 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band4 prop',
        blurb='gain for the frequency band 474 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band5 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band5 prop',
        blurb='gain for the frequency band 947 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band6 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band6 prop',
        blurb='gain for the frequency band 1889 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band7 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band7 prop',
        blurb='gain for the frequency band 3770 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band8 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band8 prop',
        blurb='gain for the frequency band 7523 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    eq_band9 = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=0.0,
        minimum=-24.0,
        maximum=12.0,
        nick='eq-band9 prop',
        blurb='gain for the frequency band 15011 Hz',
        flags=GObject.ParamFlags.READWRITE,
    )

    volume = GObject.Property(
        type=GObject.TYPE_DOUBLE,
        default=1.0,
        minimum=0.0,
        maximum=1.0,
        nick='volume prop',
        blurb='volume factor',
        flags=GObject.ParamFlags.READWRITE,
    )

    __query_duration = Gst.Query.new_duration(Gst.Format.TIME)
    __query_position = Gst.Query.new_position(Gst.Format.TIME)
    __query_buffer = Gst.Query.new_buffering(Gst.Format.PERCENT)
    _desired_state = PseudoGst.STOPPED
    _actual_state = PseudoGst.STOPPED
    _buffering_timer_id = 0

    def __init__(self, settings):
        super().__init__()
        self._settings = settings
        self._player = Gst.ElementFactory.make('playbin', 'player')
        rgvolume = Gst.ElementFactory.make('rgvolume', 'rgvolume')
        rglimiter = Gst.ElementFactory.make('rglimiter', 'rglimiter')
        equalizer = Gst.ElementFactory.make('equalizer-10bands', 'equalizer')
        audiosink = Gst.ElementFactory.make('autoaudiosink', 'audiosink')
        sinkbin = Gst.Bin()

        sinkbin.add(rgvolume)
        sinkbin.add(rglimiter)
        sinkbin.add(equalizer)
        sinkbin.add(audiosink)

        rgvolume.link(rglimiter)
        rglimiter.link(equalizer)
        equalizer.link(audiosink)

        sinkbin.add_pad(Gst.GhostPad.new('sink', rgvolume.get_static_pad('sink')))

        rgvolume.props.album_mode = False
        rglimiter.props.enabled = False
        self._player.props.flags = (1 << 1) | (1 << 4)
        self._player.props.audio_sink = sinkbin

        self._player.bind_property(
            'volume',
            self,
            'volume',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        rglimiter.bind_property(
            'enabled',
            self,
            'rg-limiter',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        rgvolume.bind_property(
            'fallback-gain',
            self,
            'rg-fallback-gain',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        for i in range(10):
            equalizer.bind_property(
                'band{}'.format(i),
                self,
                'eq-band{}'.format(i),
                GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
            )

        bus = self._player.get_bus()
        bus.add_signal_watch()
        bus.connect('message::buffering', self._on_gst_buffering)
        bus.connect('message::element', self._on_gst_element)
        bus.connect(
            'message::eos',
            lambda *ignore: self.emit('eos'),
        )
        bus.connect(
            'message::error',
            lambda b, m: self.emit('warning', m.parse_error()),
        )
        bus.connect(
            'message::stream-start',
            lambda *ignore: self.emit('new-stream-duration', self._query_duration()),
        )
        self._player.connect('notify::source', self._on_gst_source)

    @GObject.Property(
        type=GObject.TYPE_BOOLEAN,
        default=True,
        nick='playing prop',
        blurb='simple boolean mostly for plugins',
        flags=GObject.ParamFlags.READABLE,
    )
    def playing(self):
        return self._desired_state is not PseudoGst.PAUSED

    @GObject.Property(
        type=GObject.TYPE_PYOBJECT,
        nick='actual-state prop',
        blurb='actual state of GstPlayer',
        flags=GObject.ParamFlags.READABLE,
    )
    def actual_state(self):
        return self._actual_state

    @GObject.Property(
        type=GObject.TYPE_PYOBJECT,
        nick='desired-state prop',
        blurb='desired state of GstPlayer',
        flags=GObject.ParamFlags.READABLE,
    )
    def desired_state(self):
        return self._desired_state

    def plugins_installation_in_progress(self):
        return GstPbutils.install_plugins_installation_in_progress()

    def query_position(self):
        if self._player.query(self.__query_position):
            return self.__query_position.parse_position()[1]
        else:
            return 0

    def start_stream(self, url):
        self._player.props.uri = url
        self._set_player_state(PseudoGst.BUFFERING)

    def play(self):
        self._set_player_state(PseudoGst.PLAYING)

    def pause(self):
        self._set_player_state(PseudoGst.PAUSED)

    def stop(self):
        self._set_player_state(PseudoGst.STOPPED, change_gst_state=True)

    def _query_duration(self):
        if self._player.query(self.__query_duration):
            return self.__query_duration.parse_duration()[1]

    def _query_buffer(self):
        if self._player.query(self.__query_buffer):
            return self.__query_buffer.parse_buffering_percent()[0]
        else:
            return True

    def _on_gst_plugin_installed(self, result, userdata):
        if result == GstPbutils.InstallPluginsReturn.SUCCESS:
            msg = (
                _('Codec installation successful'),
                _('The required codec was installed, please restart Pithos.'),
            )
            self.emit('fatal-error', msg)
        else:
            msg = (
                _('Codec installation failed'),
                None,
                _('The required codec failed to install.\nEither manually install it or try another quality setting.'),
            )
            self.emit('error', msg)

    def _on_gst_element(self, bus, message):
        if GstPbutils.is_missing_plugin_message(message):
            if GstPbutils.install_plugins_supported():
                details = GstPbutils.missing_plugin_message_get_installer_detail(message)
                GstPbutils.install_plugins_async([details], None, self._on_gst_plugin_installed, None)
            else:
                msg = (
                    _('Missing codec'),
                    None,
                    _('GStreamer is missing a plugin and it could not be automatically installed.'
                        '\nEither manually install it or try another quality setting.'),
                )
                self.emit('error', msg)

    def _on_gst_buffering(self, *ignore):
        # React to the buffer message immediately and also fire a short repeating timeout
        # to check the buffering state that cancels only if we're not buffering or there's a pending timeout.
        # This will insure we don't get stuck in a buffering state if we're really not buffering.

        self._react_to_buffering_mesage(False)

        if self._buffering_timer_id:
            GLib.source_remove(self._buffering_timer_id)
            self._buffering_timer_id = 0
        self._buffering_timer_id = GLib.timeout_add(200, self._react_to_buffering_mesage, True)

    def _react_to_buffering_mesage(self, from_timeout):
        # If the pipeline signals that it is buffering set the player to PseudoGst.BUFFERING
        # (which is an alias to Gst.State.PAUSED). During buffering if the user goes to Pause
        # or Play(an/or back again) go though all the motions but don't actaully change the
        # player's state to the desired state until buffering has completed. The player only
        # cares about the actual_state, the rest of Pithos only cares about our desired_state
        # state, the state we *wish* we were in.

        # Reset the timer_id only if called from the timeout
        # to avoid GLib.source_remove warnings.
        if from_timeout:
            self._buffering_timer_id = 0
        buffering = self._query_buffer()

        if buffering and self._actual_state is not PseudoGst.BUFFERING:
            logging.debug('Buffer underrun')
            if self._set_player_state(PseudoGst.BUFFERING):
                logging.debug('Pausing pipeline')
        elif not buffering and self._actual_state is PseudoGst.BUFFERING:
            logging.debug('Buffer overrun')
            if self._desired_state is PseudoGst.STOPPED:
                if self._set_player_state(PseudoGst.PLAYING, change_gst_state=True):
                    logging.debug('Song starting')
            elif self._desired_state is PseudoGst.PLAYING:
                if self._set_player_state(PseudoGst.PLAYING, change_gst_state=True):
                    logging.debug('Restarting pipeline')
            elif self._desired_state is PseudoGst.PAUSED:
                if self._set_player_state(PseudoGst.PAUSED, change_gst_state=True):
                    logging.debug('User paused')
            # Tell everyone to update their clocks after we're done buffering or
            # in case it takes a while after the song-changed signal for actual playback to begin.
            self.emit('buffering-finished', self.query_position())
        return buffering

    def _set_player_state(self, target, change_gst_state=False):
        change_gst_state = change_gst_state or self._actual_state is not PseudoGst.BUFFERING
        if change_gst_state:
            ret = self._player.set_state(target.state)
            if ret == Gst.StateChangeReturn.FAILURE:
                current_state = self._player.state_get_name(self._actual_state.state)
                target_state = self._player.state_get_name(target.state)
                logging.warning('Error changing player state from: {} to: {}'.format(current_state, target_state))
                return False
            self._actual_state = target
        if target is not PseudoGst.BUFFERING:
            self._desired_state = target
        self.emit('new-player-state')
        return True

    def _on_gst_source(self, player, params):
        soup = player.props.source.props
        props = {
            'iradio_mode': False,
            'user_agent': 'io.github.Pithos',
            'method': 'GET',
            'compress': True,
            'keep_alive': True,
            'proxy': None,
            'proxy_id': None,
            'proxy_pw': None,
        }

        proxy = self._settings['proxy'] or urllib.request.getproxies().get('http')
        if proxy:
            scheme, props['proxy_id'], props['proxy_pw'], props['proxy'] = parse_proxy(proxy)

        for prop, value, in props.items():
            if value is not None and hasattr(soup, prop):
                setattr(soup, prop, value)
