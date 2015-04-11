# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2011 Rick Spencer <rick.spencer@canonical.com>
# Copyright (C) 2011-2012 Kevin Mehall <km@kevinmehall.net>
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

import logging
from pithos.plugin import PithosPlugin

class MprisPlugin(PithosPlugin):
    preference = 'enable_mpris'
    description = 'Allows control with external programs'

    def on_prepare(self):
        try:
            from dbus.mainloop.glib import DBusGMainLoop
            DBusGMainLoop(set_as_default=True)
            from . import _mpris
            from . import _dbus_service
        except ImportError:
            return "python-dbus not found"

        self.PithosMprisService = _mpris.PithosMprisService
        self.PithosDBusProxy = _dbus_service.PithosDBusProxy
        self.was_enabled = False

    def on_enable(self):
        if not self.was_enabled:
            self.mpris = self.PithosMprisService(self.window)
            self.service = self.PithosDBusProxy(self.window)
            self.was_enabled = True

    def on_disable(self):
        logging.error("Not implemented: Can't disable mpris")
