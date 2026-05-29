# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2026 Pithos contributors
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

import html

from gi.repository import Gtk, Pango


class GenreStationsDialog(Gtk.Dialog):
    __gtype_name__ = "GenreStationsDialog"

    def __init__(self, pithos):
        super().__init__(
            title=_('Browse Genre Stations'),
            transient_for=pithos,
            modal=True,
            use_header_bar=1,
            default_width=640,
            default_height=480,
        )
        self.pithos = pithos
        self.worker_run = pithos.worker_run

        self.add_buttons('_Close', Gtk.ResponseType.CLOSE)
        self.connect('close-request', lambda *_: self.response(Gtk.ResponseType.CLOSE) or True)
        self.connect('response', self._on_response)

        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(12)

        paned = Gtk.Paned.new(Gtk.Orientation.HORIZONTAL)
        paned.set_position(220)
        paned.set_vexpand(True)
        paned.set_hexpand(True)
        content.append(paned)

        self.category_listbox = Gtk.ListBox()
        self.category_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.category_listbox.connect('row-selected', self._on_category_selected)
        cat_sw = Gtk.ScrolledWindow()
        cat_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        cat_sw.set_child(self.category_listbox)
        paned.set_start_child(cat_sw)
        paned.set_resize_start_child(False)

        right_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 6)

        self.station_listbox = Gtk.ListBox()
        self.station_listbox.set_selection_mode(Gtk.SelectionMode.SINGLE)
        self.station_listbox.connect('row-selected', self._on_station_selected)
        self.station_listbox.connect('row-activated', lambda *_: self._add_selected())
        sta_sw = Gtk.ScrolledWindow()
        sta_sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sta_sw.set_vexpand(True)
        sta_sw.set_child(self.station_listbox)
        right_box.append(sta_sw)

        self.add_button = Gtk.Button.new_with_mnemonic(_('_Add Station'))
        self.add_button.set_sensitive(False)
        self.add_button.set_halign(Gtk.Align.END)
        self.add_button.connect('clicked', lambda *_: self._add_selected())
        right_box.append(self.add_button)

        paned.set_end_child(right_box)

        self._loading_label = Gtk.Label(label=_('Loading genre stations…'))
        self._loading_label.set_margin_top(6)
        self._loading_label.set_margin_bottom(6)
        self.category_listbox.append(self._wrap_row(self._loading_label, selectable=False))

        self.worker_run(pithos.pandora.get_genre_stations, (), self._populate, 'Loading genre stations…')

    @staticmethod
    def _wrap_row(widget, selectable=True):
        row = Gtk.ListBoxRow()
        row.set_child(widget)
        if not selectable:
            row.set_selectable(False)
            row.set_activatable(False)
        return row

    def _clear_listbox(self, listbox):
        child = listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

    def _populate(self, categories):
        self._clear_listbox(self.category_listbox)
        if not categories:
            label = Gtk.Label(label=_('No genre stations available.'))
            self.category_listbox.append(self._wrap_row(label, selectable=False))
            return

        for category in categories:
            label = Gtk.Label(label=category.name)
            label.set_halign(Gtk.Align.START)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            label.set_margin_start(6)
            label.set_margin_end(6)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            row = self._wrap_row(label)
            row.category = category
            self.category_listbox.append(row)

        first = self.category_listbox.get_row_at_index(0)
        if first is not None:
            self.category_listbox.select_row(first)

    def _on_category_selected(self, listbox, row):
        self._clear_listbox(self.station_listbox)
        self.add_button.set_sensitive(False)
        if row is None or not hasattr(row, 'category'):
            return
        for station in row.category.stations:
            label = Gtk.Label(label=station.name)
            label.set_halign(Gtk.Align.START)
            label.set_margin_top(4)
            label.set_margin_bottom(4)
            label.set_margin_start(6)
            label.set_margin_end(6)
            label.set_ellipsize(Pango.EllipsizeMode.END)
            srow = self._wrap_row(label)
            srow.station = station
            self.station_listbox.append(srow)

    def _on_station_selected(self, listbox, row):
        self.add_button.set_sensitive(row is not None and hasattr(row, 'station'))

    def _add_selected(self):
        row = self.station_listbox.get_selected_row()
        if row is None or not hasattr(row, 'station'):
            return
        station = row.station
        user_data = 'genre', html.escape(station.name)
        self.worker_run(
            'add_station_by_music_id',
            (station.musicId,),
            self.pithos.station_added,
            'Creating station…',
            user_data=user_data,
        )
        self.set_visible(False)

    def _on_response(self, dialog, response):
        if response == Gtk.ResponseType.CLOSE:
            self.destroy()
