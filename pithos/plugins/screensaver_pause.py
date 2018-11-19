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

from gi.repository import Gio

from pithos.plugin import PithosPlugin


class ScreenSaverPausePlugin(PithosPlugin):
    preference = 'enable_screensaverpause'
    description = 'Pause playback on screensaver'

    _signal_handle = 0
    _app = None
    _wasplaying = False

    def on_prepare(self):
        self._app = Gio.Application.get_default()
        if not hasattr(self._app.props, 'screensaver_active'):
            self.prepare_complete(error='Gtk 3.24+ required')
        else:
            self.prepare_complete()

    def _on_screensaver_active(self, pspec, user_data=None):
        if self._app.props.screensaver_active:
            self._wasplaying = self.window.playing
            self.window.pause()
        elif self._wasplaying:
            self.window.user_play()

    def on_enable(self):
        self._signal_handle = self._app.connect('notify::screensaver-active',
                                                self._on_screensaver_active)

    def on_disable(self):
        if self._signal_handle:
            self._app.disconnect(self._signal_handle)
            self._signal_handle = 0
