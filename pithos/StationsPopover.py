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
from gi.repository import GLib, Gio, Gtk, Pango


class StationsPopover(Gtk.Popover):
    __gtype_name__ = "StationsPopover"

    def __init__(self):
        super().__init__()

        box2 = Gtk.Box()
        self.search = Gtk.SearchEntry(placeholder_text=_('Search stations…'))
        self.sorted = False
        self.sort = Gtk.ToggleButton.new()
        self.sort.set_child(Gtk.Image.new_from_icon_name("view-sort-ascending-symbolic"))
        self.sort.connect("toggled", self.sort_changed)
        self.search.set_hexpand(True)
        box2.append(self.search)
        box2.append(self.sort)

        self.listbox = Gtk.ListBox()
        # Phase 2: replace with GtkGestureClick (button-press-event removed in GTK4)
        self.listbox.connect('row-activated', self.on_row_activated)
        self.listbox.set_sort_func(self.listbox_sort)
        self.listbox.set_header_func(self.listbox_header)
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_size_request(-1, 200)
        sw.set_child(self.listbox)

        self.search.connect("search-changed", self.search_changed)
        self.listbox.set_filter_func(self.listbox_filter, self.search)

        box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        box.set_margin_top(3)
        box.set_margin_bottom(3)
        box.set_margin_start(3)
        box.set_margin_end(3)
        box2.set_margin_top(3)
        box2.set_margin_bottom(3)
        box.append(box2)
        sw.set_hexpand(True)
        sw.set_vexpand(True)
        box.append(sw)

        self.new_station_button = Gtk.Button.new_with_mnemonic(_('_New Station…'))
        self.new_station_button.set_action_name('app.new-station')
        self.new_station_button.set_margin_top(6)
        self.new_station_button.connect('clicked', lambda *_: self.set_visible(False))
        box.append(self.new_station_button)

        settings = Gio.Settings.new('io.github.Pithos')
        settings.bind('sort-stations', self.sort, 'active', Gio.SettingsBindFlags.DEFAULT)

        self.set_child(box)

    def on_button_press(self, widget, event):
        # Phase 2: GtkMenu and button-press-event removed in GTK4; replace with GtkGestureClick + GtkPopoverMenu
        pass

    def on_row_activated(self, listbox, row):
        self.set_visible(False)
        self.search.set_text('')

    def sort_changed(self, widget):
        self.sorted = widget.get_active()
        self.listbox.invalidate_sort()

    def search_changed(self, entry):
        self.listbox.invalidate_filter()

    def listbox_header(self, row, before):
        if before and before.station.isThumbprint and not row.get_header():
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
        if row1.station.isQuickMix or row1.station.isThumbprint: # Always first
            return -1
        if not self.sorted: # This is the order Pandora lists it (aka create date)
            if row1.index < row2.index:
                return -1
            else:
                return 1
        else:
            return GLib.ascii_strcasecmp(row1.name, row2.name)

    def _iter_rows(self):
        i = 0
        while True:
            row = self.listbox.get_row_at_index(i)
            if row is None:
                break
            yield row
            i += 1

    def insert_row(self, model, path, iter):
        station, name, index = model.get(iter, 0, 1, 2)
        row = StationListBoxRow(station, name, index)
        self.listbox.append(row)

    def change_row(self, model, path, iter, data=None):
        station, name, index = model.get(iter, 0, 1, 2)
        for row in self._iter_rows():
            if row.station == station:
                row.name, row.index = name, index
                self.listbox.invalidate_sort()
                break
        else:
            logging.warning('Row changed on unknown station')

    def clear(self):
        for row in list(self._iter_rows()):
            self.listbox.remove(row)

    def toggle_visibility(self, *ignore):
        self.set_visible(not self.get_visible())

    def set_model(self, model):
        model.connect('row-inserted', self.insert_row)
        model.connect('row-changed', self.change_row)

    def select_station(self, station):
        for row in self._iter_rows():
            if row.station == station:
                self.listbox.select_row(row)
                break

    def remove_station(self, station):
        for row in list(self._iter_rows()):
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
        self.label.set_halign(Gtk.Align.START)
        self.label.set_ellipsize(Pango.EllipsizeMode.END)
        self.label.set_max_width_chars(15)
        self.label.set_text(name)
        self.label.set_hexpand(True)
        box.append(self.label)

        # TODO: Modify quickmix from here
        self.set_child(box)

    @property
    def name(self):
        return self.label.get_text()

    @name.setter
    def name(self, name):
        self.label.set_text(name)
