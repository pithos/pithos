# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2015 Patrick Griffis <tingping@tingping.se>
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

import logging
from gi.repository import GLib, Gio, Gtk, Gdk, Pango
from .util import open_browser


class StationsPopover(Gtk.Popover):
    __gtype_name__ = "StationsPopover"

    def __init__(self):
        super().__init__()

        box2 = Gtk.Box()
        self.search = Gtk.SearchEntry(can_default=True,
                                      placeholder_text=_('Search stations…'))
        self.sorted = False
        self.sort = Gtk.ToggleButton.new()
        self.sort.get_accessible().props.accessible_description = _('sort button')
        self.sort.add(Gtk.Image.new_from_icon_name("view-sort-ascending-symbolic", Gtk.IconSize.BUTTON))
        self.sort.connect("toggled", self.sort_changed)
        box2.pack_start(self.search, True, True, 0)
        box2.add(self.sort)

        self.listbox = Gtk.ListBox()
        self.listbox.connect('button-press-event', self.on_button_press)
        self.listbox.connect('row-activated', self.on_row_activated)
        self.listbox.set_sort_func(self.listbox_sort)
        self.listbox.set_header_func(self.listbox_header)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(-1, 200)
        sw.add(self.listbox)

        self.search.connect("search-changed", self.search_changed)
        self.listbox.set_filter_func(self.listbox_filter, self.search)

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        box.props.margin = 3
        box.pack_start(box2, True, False, 3)
        box.pack_start(sw, True, True, 0)

        settings = Gio.Settings.new('io.github.Pithos')
        settings.bind('sort-stations', self.sort, 'active', Gio.SettingsBindFlags.DEFAULT)

        box.show_all()
        self.add(box)

    def on_button_press(self, widget, event):
        def open_info(item, station):
            open_browser(station.info_url, parent=self.get_toplevel(),
                         timestamp=event.time)

        if event.button != Gdk.BUTTON_SECONDARY:
            return False

        row = self.listbox.get_row_at_y(event.y)
        if not row:
            return False

        item = Gtk.MenuItem.new_with_label('Station Info…')
        item.connect('activate', open_info, row.station)
        item.show()
        menu = Gtk.Menu.new()
        menu.append(item)
        menu.attach_to_widget(widget)
        menu.popup(None, None, None, None, event.button, event.time)
        return True

    def on_row_activated(self, listbox, row):
        self.hide()
        self.search.set_text('')

    def sort_changed(self, widget):
        self.sorted = widget.get_active()
        self.listbox.invalidate_sort()

    def search_changed(self, entry):
        self.listbox.invalidate_filter()

    def listbox_header(self, row, before):
        if before and before.station.isQuickMix and not row.get_header():
            row.set_header(Gtk.Separator.new(Gtk.Orientation.HORIZONTAL))
        elif row.get_header():
            row.set_header(None)

    def listbox_filter(self, row, entry):
        search_text = entry.get_text().lower()
        if search_text == '':
            return True
        station_name = row.station.name.lower()
        if station_name.startswith(search_text):
            return True
        for word in station_name.split():
            if word.startswith(search_text):
                return True
        return False

    def listbox_sort(self, row1, row2):
        if row1.station.isQuickMix: # Always first
            return -1
        if not self.sorted: # This is the order Pandora lists it (aka create date)
            if row1.index < row2.index:
                return -1
            else:
                return 1
        else:
            return GLib.ascii_strcasecmp(row1.name, row2.name)

    def insert_row(self, model, path, iter):
        station, name, index = model.get(iter, 0, 1, 2)
        row = StationListBoxRow(station, name, index)
        row.show_all()
        self.listbox.add(row)

    def change_row(self, model, path, iter, data=None):
        station, name, index = model.get(iter, 0, 1, 2)
        for row in self.listbox.get_children():
            if row.station == station:
                row.name, row.index = name, index
                self.listbox.invalidate_sort()
                break
        else:
            logging.warning('Row changed on unknown station')

    def clear(self):
        for row in self.listbox.get_children():
            row.destroy()

    def set_model(self, model):
        model.connect('row-inserted', self.insert_row)
        model.connect('row-changed', self.change_row)

    def select_station(self, station):
        for row in self.listbox.get_children():
            if row.station == station:
                self.listbox.select_row(row)
                break

    def remove_station(self, station):
        for row in self.listbox.get_children():
            if row.station == station:
                self.listbox.remove(row)
                break


class StationListBoxRow(Gtk.ListBoxRow):

    def __init__(self, station, name, index):
        super().__init__()
        self.station = station
        self.index = index

        box = Gtk.Box()
        self.label = Gtk.Label()
        self.label.set_alignment(0, .5)
        self.label.set_ellipsize(Pango.EllipsizeMode.END)
        self.label.set_max_width_chars(15)
        self.label.set_text(name)
        box.pack_start(self.label, True, True, 0)

        # TODO: Modify quickmix from here
        self.add(box)

    @property
    def name(self):
        return self.label.get_text()

    @name.setter
    def name(self, name):
        self.label.set_text(name)
