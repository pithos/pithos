# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2011 Rick Spencer <rick.spencer@canonical.com>
# Copyright (C) 2011-2012 Kevin Mehall <km@kevinmehall.net>
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

import logging

from gi.repository import Gio, GLib

from pithos.plugin import PithosPlugin


class MprisPlugin(PithosPlugin):
    preference = 'enable_mpris'
    description = 'Allows control with external programs'

    def on_prepare(self):
        from . import _mpris
        self.PithosMprisService = _mpris.PithosMprisService
        self.mpris = None
        try:
            self.bus = Gio.bus_get_sync(Gio.BusType.SESSION, None)
        except GLib.Error as e:
            logging.warning('Failed to connect to session bus: {}'.format(e))
            return 'Failed to connect to DBus'

        try:
            self.mpris = self.PithosMprisService(self.window, connection=self.bus)
        except Exception as e:
            logging.warning('Failed to create DBus services: {}'.format(e))
            return 'Failed to create DBus services'

    def on_enable(self):
        self.mpris.connect()

    def on_disable(self):
        self.mpris.disconnect()
