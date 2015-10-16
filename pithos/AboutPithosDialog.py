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

from gi.repository import Gtk

from .gi_composites import GtkTemplate
from .util import open_browser

@GtkTemplate(ui='/io/github/Pithos/ui/AboutPithosDialog.ui')
class AboutPithosDialog(Gtk.AboutDialog):
    __gtype_name__ = "AboutPithosDialog"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_template()

        theme = Gtk.IconTheme.get_default()
        self.set_logo(theme.load_icon('pithos', 96, 0))

    @GtkTemplate.Callback
    def activate_link_cb(self, wid, uri):
        open_browser(uri)
        return True

