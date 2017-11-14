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
gi.require_version('GstAudio', '1.0')
gi.require_version('GstPbutils', '1.0')
from gi.repository import Gst, GstAudio, GstPbutils, GObject, GLib
from enum import IntEnum

from .util import parse_proxy

Gst.init(None)

PLAYER_SECOND = Gst.SECOND

# Older versions of Gstreamer may not have these constants
try:
    _NOISE_SHAPING_METHOD_HIGH = GstAudio.AudioNoiseShapingMethod.HIGH
    _DITHER_METHOD_TPDF_HF = GstAudio.AudioDitherMethod.TPDF_HF
    _RESAMPLER_QUALITY_MAX = GstAudio.AUDIO_RESAMPLER_QUALITY_MAX
    _RESAMPLER_FILTER_MODE_FULL = GstAudio.AudioResamplerFilterMode.FULL
except AttributeError:
    _NOISE_SHAPING_METHOD_HIGH = 4
    _DITHER_METHOD_TPDF_HF = 3
    _RESAMPLER_QUALITY_MAX = 10
    _RESAMPLER_FILTER_MODE_FULL = 1

# about 5 secs of compressed audio (125 * 5 * bitrate)
_BUFFER_SIZE_MULTIPLIER = 625

_AAC_EXT = '.mp4'
_AAC_CAPS = Gst.Caps.from_string('application/x-3gp, profile=(string)basic')

_MP3_EXT = '.mp3'
_MP3_CAPS = Gst.Caps.from_string('audio/mpeg, mpegversion=(int)1, layer=(int)3, parsed=(boolean)false')


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


class GstPlayer(Gst.Pipeline):
    '''A custom mostly static Gst.Pipeline for playing MP3 and AAC network streams'''
    __gtype_name__ = 'GstPlayer'

    # signals
    # player, *signal value
    __gsignals__ = {
        # no signal value
        'eos': (GObject.SignalFlags.RUN_FIRST, None, ()),
        # None or int time in nanoseconds
        'new-stream-duration': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        # no signal value
        'new-player-state': (GObject.SignalFlags.RUN_FIRST, None, ()),
        # None or int time in nanoseconds
        'buffering-finished': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        # tuple (GLib.Error, str) err, debug
        'warning': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        # str error message
        'error': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        # str fatal-error message
        'fatal-error': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    # public read-write properties
    location = GObject.Property(
        type=str,
        default='',
        nick='location prop',
        blurb='the URI to play next',
        flags=GObject.ParamFlags.READWRITE,
    )

    proxy = GObject.Property(
        type=str,
        default='',
        nick='proxy prop',
        blurb='HTTP proxy server URI',
        flags=GObject.ParamFlags.READWRITE,
    )

    proxy_id = GObject.Property(
        type=str,
        default='',
        nick='proxy-id prop',
        blurb='HTTP proxy URI user id for authentication',
        flags=GObject.ParamFlags.READWRITE,
    )

    proxy_pw = GObject.Property(
        type=str,
        default='',
        nick='proxy-pw prop',
        blurb='HTTP proxy URI user password for authentication',
        flags=GObject.ParamFlags.READWRITE,
    )

    max_size_bytes = GObject.Property(
        type=GObject.TYPE_UINT,
        default=0,
        minimum=0,
        maximum=GLib.MAXUINT,
        nick='max-size-bytes prop',
        blurb='Max. amount of data in the buffer',
        flags=GObject.ParamFlags.READWRITE,
    )

    decodebin_sink_caps = GObject.Property(
        type=Gst.Caps,
        nick='decodebin-sink-caps prop',
        blurb='force caps without doing a typefind',
        flags=GObject.ParamFlags.READWRITE,
    )

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

    def __init__(self, settings):
        super().__init__()

        self._desired_state = PseudoGst.STOPPED
        self._actual_state = PseudoGst.STOPPED
        self._prerolled = False
        self._got_duration = False
        self._buffering_timer_id = 0
        self._current_bitrate = 0
        self._seek_time = None

        # create and add elements to the Pipeline
        souphttpsrc = Gst.ElementFactory.make('souphttpsrc', None)
        souphttpsrc.props.iradio_mode = False
        souphttpsrc.props.user_agent = 'io.github.Pithos'
        souphttpsrc.props.method = 'GET'
        souphttpsrc.props.compress = True
        souphttpsrc.props.keep_alive = True
        souphttpsrc.props.http_log_level = 0

        self.add(souphttpsrc)

        queue2 = Gst.ElementFactory.make('queue2', None)
        queue2.props.use_buffering = True
        queue2.props.max_size_buffers = 0
        queue2.props.max_size_time = 0

        self.add(queue2)

        decodebin = Gst.ElementFactory.make('decodebin', None)
        decodebin.props.expose_all_streams = False
        decodebin.props.caps = Gst.Caps.from_string('audio/x-raw')

        self.add(decodebin)

        audioconvert = Gst.ElementFactory.make('audioconvert', None)
        audioconvert.props.dithering = _DITHER_METHOD_TPDF_HF
        audioconvert.props.noise_shaping = _NOISE_SHAPING_METHOD_HIGH

        self.add(audioconvert)

        audioresample = Gst.ElementFactory.make('audioresample', None)
        audioresample.props.quality = _RESAMPLER_QUALITY_MAX
        audioresample.props.sinc_filter_mode = _RESAMPLER_FILTER_MODE_FULL

        self.add(audioresample)

        rgvolume = Gst.ElementFactory.make('rgvolume', None)
        rgvolume.props.album_mode = False

        self.add(rgvolume)

        rglimiter = Gst.ElementFactory.make('rglimiter', None)
        rglimiter.props.enabled = False

        self.add(rglimiter)

        equalizer = Gst.ElementFactory.make('equalizer-10bands', None)

        self.add(equalizer)

        # If PulseAudio is running use pulsesink and it's PulseAudio friendly volume,
        # otherwise use a seperate volume element and autoaudiosink.
        volume = self._get_pulse_sink()
        if volume:
            self.add(volume)
            logging.debug('using pulsesink')
        else:
            volume = Gst.ElementFactory.make('volume', None)
            self.add(volume)

            sink = Gst.ElementFactory.make('autoaudiosink', None)
            self.add(sink)

            volume.link_pads_full('src', sink, 'sink', Gst.PadLinkCheck.NOTHING)
            logging.debug('using autoaudiosink')

        # link the rest of our elements in the Pipeline except decodebin >> audioconvert
        souphttpsrc.link_pads_full('src', queue2, 'sink', Gst.PadLinkCheck.NOTHING)
        queue2.link_pads_full('src', decodebin, 'sink', Gst.PadLinkCheck.NOTHING)
        audioconvert.link_pads_full('src', audioresample, 'sink', Gst.PadLinkCheck.NOTHING)
        audioresample.link_pads_full('src', rgvolume, 'sink', Gst.PadLinkCheck.NOTHING)
        rgvolume.link_pads_full('src', rglimiter, 'sink', Gst.PadLinkCheck.NOTHING)
        rglimiter.link_pads_full('src', equalizer, 'sink', Gst.PadLinkCheck.NOTHING)
        equalizer.link_pads_full('src', volume, 'sink', Gst.PadLinkCheck.NOTHING)

        # decodebin >> audioconvert must be linked on the fly.
        sink_pad = audioconvert.get_static_pad('sink')
        decodebin.connect('pad-added', lambda e, p: p.link_full(sink_pad, Gst.PadLinkCheck.NOTHING))
        decodebin.connect('autoplug-query', self._on_decodebin_autoplug_query, sink_pad.query_caps(None))
        decodebin.connect('autoplug-factories', self._on_decodebin_autoplug_factories, self._get_cached_factories())

        # Bind all of our intresting properties so from the outside
        # our player appears as a single player/element.
        souphttpsrc.bind_property(
            'location',
            self,
            'location',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        souphttpsrc.bind_property(
            'proxy',
            self,
            'proxy',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        souphttpsrc.bind_property(
            'proxy-id',
            self,
            'proxy-id',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        souphttpsrc.bind_property(
            'proxy-pw',
            self,
            'proxy-pw',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        queue2.bind_property(
            'max-size-bytes',
            self,
            'max-size-bytes',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        decodebin.bind_property(
            'sink-caps',
            self,
            'decodebin-sink-caps',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        rgvolume.bind_property(
            'fallback-gain',
            self,
            'rg-fallback-gain',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        rglimiter.bind_property(
            'enabled',
            self,
            'rg-limiter',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        for i in range(10):
            equalizer.bind_property(
                'band{}'.format(i),
                self,
                'eq-band{}'.format(i),
                GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
            )

        volume.bind_property(
            'volume',
            self,
            'volume',
            GObject.BindingFlags.BIDIRECTIONAL | GObject.BindingFlags.SYNC_CREATE,
        )

        # Bus message handlers
        self.bus.add_signal_watch()
        self.bus.connect('message::buffering', self._on_gst_buffering)
        self.bus.connect('message::element', self._on_gst_element)
        self.bus.connect('message::clock-lost', self._on_gst_clock_lost)
        self.bus.connect('message::async-done', self._on_gst_async_done)
        self.bus.connect('message::stream-start', self._get_duration)
        self.bus.connect('message::duration-changed', self._get_duration)
        self.bus.connect('message::eos', lambda *ignore: self.emit('eos'))
        self.bus.connect('message::error', lambda b, m: self.emit('warning', m.parse_error()))
        self.bus.connect('message::warning', lambda b, m: self.emit('warning', m.parse_warning()))

        # set the proxy and connect the proxy changed handler
        self._on_proxy_setting_changed(settings, 'proxy')
        settings.connect_after('changed::proxy', self._on_proxy_setting_changed)

    # public read-only properties
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
        blurb='actual state of GstPlayer PseudoGst Enum',
        flags=GObject.ParamFlags.READABLE,
    )
    def actual_state(self):
        return self._actual_state

    @GObject.Property(
        type=GObject.TYPE_PYOBJECT,
        nick='desired-state prop',
        blurb='desired state of GstPlayer PseudoGst Enum',
        flags=GObject.ParamFlags.READABLE,
    )
    def desired_state(self):
        return self._desired_state

    # public methods/functions
    def plugins_installation_in_progress(self):
        return GstPbutils.install_plugins_installation_in_progress()

    def query_position(self):
        if self.query(self.__query_position):
            return self.__query_position.parse_position()[1]
        else:
            # Comming off an on the fly stream quailty
            # change we may not be able to get a position
            # so we just return the seek time otherwise.
            return self._seek_time or 0

    def start_stream(self, url, bitrate):
        if self._current_bitrate != bitrate:
            self._current_bitrate = bitrate
            self.props.max_size_bytes = bitrate * _BUFFER_SIZE_MULTIPLIER
            self.props.decodebin_sink_caps = self._caps_for_url(url)
        self.props.location = url
        self._set_player_state(PseudoGst.BUFFERING)

    def stream_quailty_change(self, url, bitrate):
        self.set_state(Gst.State.PAUSED)
        seek_time = self.query_position()
        self.stop()
        self._seek_time = seek_time
        self.start_stream(url, bitrate)

    def play(self):
        self._set_player_state(PseudoGst.PLAYING)

    def pause(self):
        self._set_player_state(PseudoGst.PAUSED)

    def stop(self):
        self._prerolled = False
        self._got_duration = False
        self._disk_cached = False
        self._seek_time = None
        self._set_player_state(PseudoGst.STOPPED, change_gst_state=True)

    # private methods/functions/signal handlers
    def _caps_for_url(self, url):
        # Skip typefinding if we can and speed up prerolling.
        # In the case of mp3 streams it also allows us to skip adding
        # the id3demux element to decodebin. typefind reports the caps
        # of mp3 streams as 'application/x-id3' more often than not leading
        # to the addition of id3demux to the pipeline. As Pandora streams
        # contain no useful tags there's no point in adding it.
        if _MP3_EXT in url:
            return _MP3_CAPS
        elif _AAC_EXT in url:
            return _AAC_CAPS
        else:
            return None

    def _get_pulse_sink(self):
        # If we have a pulsesink we can get the server presence through
        # setting the ready state. If PulseAudio is running return the pulsesink.
        pulsesink = Gst.ElementFactory.make('pulsesink', None)
        if pulsesink is not None:
            pulsesink.set_state(Gst.State.READY)
            res = pulsesink.get_state(0)[0]
            pulsesink.set_state(Gst.State.NULL)
            if res != Gst.StateChangeReturn.FAILURE:
                return pulsesink

    def _get_cached_factories(self):
        # return a list of Gst.ElementFactory's sorted by rank containing a AAC demuxer, MP3 parser,
        # and hopefully a AAC decoder and MP3 decoder if they exist.
        demuxed_aac_caps = Gst.Caps.from_string('audio/mpeg, mpegversion=(int)4, '
                                                'framed=(boolean)true, '
                                                'stream-format=(string)raw')

        parsed_mp3_caps = Gst.Caps.from_string('audio/mpeg, mpegversion=(int)1, '
                                               'layer=(int)3, parsed=(boolean)true')

        # Rank priority: resource useage, speed, sound quality.
        # libav decoders use noticeably more resources compared to other decoders.
        decoder_rank_map = {
            'mad': 100,
            'avdec_mp3': 150,
            'avdec_mp3float': 200,
            'flump3dec': 250,
            'mpg123audiodec': 300,
            'avdec_aac_fixed': 200,
            'avdec_aac': 250,
            'faad': 300,
        }

        def factories_for_caps_and_type(caps, factory_type):
            factories = Gst.ElementFactory.list_get_elements(factory_type, Gst.Rank.MARGINAL)
            return Gst.ElementFactory.list_filter(factories, caps, Gst.PadDirection.SINK, False)

        def rank_decoder(factory):
            # Not all decoders are created equal.
            # Their ranks by Gstreamer are not necessarily a reflection
            # of their speed, sound quality and resource useage, so we re-rank them.
            new_rank = decoder_rank_map.get(factory.get_name())
            if new_rank:
                factory.set_rank(new_rank)
            return factory

        def factories_gen():
            factories = factories_for_caps_and_type(parsed_mp3_caps, Gst.ELEMENT_FACTORY_TYPE_DECODER)
            if factories:
                factory = sorted(map(rank_decoder, factories), key=lambda f: f.get_rank(), reverse=True)[0]
                logging.debug('MP3 decoder: {}'.format(factory.get_name()))
                yield factory
            else:
                logging.debug('no MP3 decoder found')
            factories = factories_for_caps_and_type(demuxed_aac_caps, Gst.ELEMENT_FACTORY_TYPE_DECODER)
            if factories:
                factory = sorted(map(rank_decoder, factories), key=lambda f: f.get_rank(), reverse=True)[0]
                logging.debug('AAC decoder: {}'.format(factory.get_name()))
                yield factory
            else:
                logging.debug('no AAC decoder found')
            factories = factories_for_caps_and_type(_MP3_CAPS, Gst.ELEMENT_FACTORY_TYPE_PARSER)
            if factories:
                factory = factories[0]
                logging.debug('MP3 parser: {}'.format(factory.get_name()))
                yield factory
            else:
                logging.debug('no MP3 parser found')
            factories = factories_for_caps_and_type(_AAC_CAPS, Gst.ELEMENT_FACTORY_TYPE_DEMUXER)
            if factories:
                factory = factories[0]
                logging.debug('AAC demuxer: {}'.format(factory.get_name()))
                yield factory
            else:
                logging.debug('no AAC demuxer found')

        return sorted(factories_gen(), key=lambda f: f.get_rank(), reverse=True)

    def _query_buffer(self):
        if self.query(self.__query_buffer):
            # If we have a seek_time always return True to help prevent buffer flutter when doing
            # an on the fly stream quality change.
            return self.__query_buffer.parse_buffering_percent()[0] or self._seek_time is not None
        else:
            return True

    def _query_duration(self):
        if self.query(self.__query_duration):
            return self.__query_duration.parse_duration()[1]

    def _set_player_state(self, target, change_gst_state=False):
        change_gst_state = change_gst_state or self._actual_state is not PseudoGst.BUFFERING
        if change_gst_state:
            ret = self.set_state(target.state)
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

    def _on_gst_clock_lost(self, *ignore):
        # Not sure why this isn't just done automatically?
        # Below is exactly what you should do per the docs.
        if self.get_state(Gst.CLOCK_TIME_NONE)[1] == Gst.State.PLAYING:
            logging.debug('Gst clock lost, resetting the pipeline to get a new clock')
            self.set_state(Gst.State.PAUSED)
            self.set_state(Gst.State.PLAYING)

    def _on_gst_async_done(self, *ignore):
        # The 1st async-done message going from STOPPED to BUFFERING
        # means our pipeline is prerolled. As per the docs we should
        # check to see if we're buffering. (we more than likely still are)
        if not self._prerolled:
            # If we're comming off a on the fly quality change
            # we have to wait to be prerolled before we can seek
            # to the previous stream time.
            if self._seek_time:
                self.seek_simple(
                    Gst.Format.TIME,
                    Gst.SeekFlags.FLUSH | Gst.SeekFlags.ACCURATE,
                    self._seek_time,
                )
            self._prerolled = True
            self._get_duration()
            self._on_gst_buffering()
            self._seek_time = None

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
                _('The required codec failed to install.'
                    '\nEither manually install it or try another quality setting.'),
            )
            self.emit('error', msg)

    def _on_gst_buffering(self, *ignore):
        # React to the buffer message immediately and also fire a short repeating timeout
        # to check the buffering state that cancels only if we're not buffering or there's a pending timeout.
        # This will insure we don't get stuck in a buffering state if we're really not buffering.

        # Ignore buffering messages if the pipeline is not yet prerolled.
        if not self._prerolled:
            return

        self._react_to_buffering_mesage(False)

        if self._buffering_timer_id:
            GLib.source_remove(self._buffering_timer_id)
            self._buffering_timer_id = 0
        self._buffering_timer_id = GLib.timeout_add(500, self._react_to_buffering_mesage, True)

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
                logging.debug('pipeline buffering')
        elif not buffering and self._actual_state is PseudoGst.BUFFERING:
            logging.debug('Buffer overrun')
            if self._desired_state is PseudoGst.STOPPED:
                self._get_duration(final=True)
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

    def _get_duration(self, *ignore, final=False):
        # Do our very best to get a duration
        # before buffering completes.
        if self._got_duration:
            return
        duration = self._query_duration()
        if duration or final:
            self._got_duration = True
            self.emit('new-stream-duration', duration)

    def _on_decodebin_autoplug_query(self, decodebin, pad, child, query, sink_pad_caps):
        # As per docs answer yet to be linked audio decoder caps queries with the sink caps of the audioconvert element.
        if query.type == Gst.QueryType.CAPS and child.get_factory().list_is_type(Gst.ELEMENT_FACTORY_TYPE_DECODER):
            query.set_caps_result(sink_pad_caps)
            return True
        return False

    def _on_decodebin_autoplug_factories(self, decodebin, pad, caps, cached_factories):
        # This speeds up the autoplug process(and thus prerolling),
        # and stops aacparse from being added to decodebin for aac's unnecessary.
        factories = Gst.ElementFactory.list_filter(cached_factories, caps, Gst.PadDirection.SINK, caps.is_fixed())
        if not factories:
            factories = Gst.ElementFactory.list_get_elements(Gst.ELEMENT_FACTORY_TYPE_DECODABLE, Gst.Rank.SECONDARY)
            factories = Gst.ElementFactory.list_filter(factories, caps, Gst.PadDirection.SINK, caps.is_fixed())
        return factories

    def _on_proxy_setting_changed(self, settings, key):
        scheme = user = password = hostport = None
        proxy = settings[key] or urllib.request.getproxies().get('http')
        if proxy:
            scheme, user, password, hostport = parse_proxy(proxy)
        self.props.proxy = hostport
        self.props.proxy_id = user
        self.props.proxy_pw = password
        logging.debug(
            'souphttpsrc proxy set - proxy: {}, proxy-id: {}, proxy-pw: {}'.format(hostport, user, password),
        )
