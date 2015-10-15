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

from gi.repository import Gtk, GdkPixbuf

from .gi_composites import GtkTemplate
from .pithosconfig import get_ui_file, get_media_file
from .util import open_browser

@GtkTemplate(ui=get_ui_file('about'))
class AboutPithosDialog(Gtk.AboutDialog):
    __gtype_name__ = "AboutPithosDialog"

    def __init__(self, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_template()

        self.set_logo(GdkPixbuf.Pixbuf.new_from_file_at_scale(get_media_file('icon'), -1, 96, True))

    @GtkTemplate.Callback
    def activate_link_cb(self, wid, uri):
        open_browser(uri)
        return True

