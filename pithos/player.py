"""Pithos music player plugin interface.

A new music player can be created by calling Player()
"""
import importlib
import logging
import pkgutil
import time

from pithos.util import find_subclasses

from gi.repository import GObject


class PlayerBase (GObject.Object):

    """Base class and interface for Pithos music players.

    Several different signals may be emitted by the player:
      song-ended:
        Called when the currently playing song ends.
      song-info-changed (song: pithos.pandora.Song):
        Called with the current song when some property of that song changes.
      volume-changed (volume: float):
        Called with the current volume (in the range [0,1]) when the player's
        volume has changed.
      error (msg: str, submsg: str, fatal: bool):
        Called when the player encounters an error. Errors where fatal is True
        indicate the player cannot continue to operate. Where fatal is False,
        the player will continue to operate and the message may be more
        informational in nature.
    """

    description = "Player Base Class"

    __gsignals__ = {
        "song-ended": (GObject.SignalFlags.RUN_FIRST, None, tuple()),
        "song-info-changed": (GObject.SignalFlags.RUN_FIRST, None,
                              (GObject.TYPE_PYOBJECT,)),
        "volume-changed": (GObject.SignalFlags.RUN_FIRST, None, (float,)),
        "error": (GObject.SignalFlags.RUN_FIRST, None, (str, str, bool,)),
    }

    def __init__(self, preferences, cmd_line_args=None):
        """Create a new Player."""
        super().__init__()

        self._preferences = preferences
        self._cmd_line_args = cmd_line_args
        self._current_song = None

        self._init()

    def _init(self):
        """Initialize implementation instance."""
        raise NotImplementedError("Abstract method _init")

    def dispose(self):
        """Dispose of this play and any resources it may have.

        This is an optional method.
        """

    @property
    def playing(self):
        """Flag if the player is in a "wants to play" state.

        This property should be based on the desired state of the player, even
        if the player isn't currently producing output (e.g. while paused for
        buffering.)
        """
        raise NotImplementedError("Abstract property playing")

    @property
    def buffer_percent(self):
        """The proportion of the buffer currently filled.

        When buffering, the value is in the range [0,1), otherwise it's None.
        """
        raise NotImplementedError("Abstract property buffer_percent")

    def play_song(self, song):
        """Start playing a specific song."""
        self._current_song = song
        self._current_song.start_time = time.time()

    @property
    def current_song(self):
        """The currently playing pithos.pandora.Song object."""
        return self._current_song

    @property
    def volume(self):
        """The player's current volume."""
        raise NotImplementedError("Abstract property getter volume")

    @volume.setter
    def volume(self, vol):
        """Set the player's current volume."""
        raise NotImplementedError("Abstract property setter volume")

    def play(self):
        """Set the player's desired state to "playing"."""
        raise NotImplementedError("Abstract method play")

    def pause(self):
        """Set the player's desired state to "paused"."""
        raise NotImplementedError("Abstract method pause")

    def stop(self):
        """Set the player's desired state to "stopped".

        A stopped player has no current_song.
        """
        raise NotImplementedError("Abstract method stop")

    def get_current_position(self):
        """Return the playback position of the current song."""
        raise NotImplementedError("Abstract method get_current_position")

    def get_current_duration(self):
        """Return the duration of the current song."""
        raise NotImplementedError("Abstract method get_current_duration")


class NoPlayerImplementationError (Exception):

    """No player implementation could be instantiated."""

    def __str__(self):
        return "Unable to create desired audio player: {}".format(self.args[0])


def get_players():
    return find_subclasses('pithos.players', PlayerBase)


def Player(preferences, cmd_line_args=None):
    """Create a new Pithos music player."""
    players = get_players()
    Impl = players.get(preferences['audio_player'])

    if Impl:
        try:
            return Impl(preferences, cmd_line_args)
        except Exception as e:
            logging.warning("Unable to instantiate player %s", Impl,
                            exc_info=True)

            msg = "Error creating player: {}: {}".format(type(e).__name__, e)
    else:
        msg = "Could not find player implementation."
    raise NoPlayerImplementationError(preferences['audio_player'], msg)
