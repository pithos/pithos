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

from gi.repository import Gtk
from pithos.plugin import PithosPlugin


class AutoVolumeNormalization(PithosPlugin):
    preference = 'enable_autovolume'
    description = _('Normalize apparent volume')
    _song_change_handler = None

    def on_prepare(self):
        self.prepare_complete()

    def on_enable(self):
        self._song_change_handler = self.window.connect('song-changed', self._on_song_changed)
        self.window.rglimiter.set_property('enabled', True)
        if self.window.current_song is not None:
            self._on_song_changed(self.window, self.window.current_song)

    def on_disable(self):
        if self._song_change_handler is not None:
            self.window.disconnect(self._song_change_handler)
        self._song_change_handler = None
        self._volume_warning_dialog()

    def _on_song_changed(self, window, song):
        window.rgvolume.set_property('fallback-gain', song.trackGain)

    def _volume_warning_dialog(self):
        if self.window.playing:
            self.window.pause()
            text = _('Pithos Has Been Paused')
        else:
            text = _('Pithos Is Paused')

        self.window.rgvolume.set_property('fallback-gain', 0.0)
        self.window.rglimiter.set_property('enabled', False)

        dialog = Gtk.MessageDialog(
            parent=self.window.prefs_dlg,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.OK,
            text=text,
            secondary_text=_(
                'Please lower the volume before resuming playback,\n'
                'as you may notice a sudden volume increase upon disabling this plugin.'
            ),
        )

        dialog.connect('response', lambda d, r: d.destroy())
        dialog.show()
