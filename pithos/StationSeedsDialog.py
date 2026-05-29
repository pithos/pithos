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

import logging

from gi.repository import Gtk, Pango

from . import SearchDialog


class StationSeedsDialog(Gtk.Dialog):
    __gtype_name__ = "StationSeedsDialog"

    def __init__(self, pithos, station, parent=None):
        super().__init__(
            title=_('Seeds for "{}"').format(station.name),
            transient_for=parent or pithos,
            modal=True,
            use_header_bar=1,
            default_width=480,
            default_height=420,
        )
        self.pithos = pithos
        self.station = station
        self.worker_run = pithos.worker_run

        self.add_buttons('_Close', Gtk.ResponseType.CLOSE)
        self.connect('close-request', lambda *_: self.response(Gtk.ResponseType.CLOSE) or True)
        self.connect('response', self._on_response)

        content = self.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(8)

        header = Gtk.Label(label=_('Songs, artists, and genres used to pick tracks for this station.'))
        header.set_halign(Gtk.Align.START)
        header.set_wrap(True)
        content.append(header)

        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_vexpand(True)
        content.append(sw)

        self.listbox = Gtk.ListBox()
        self.listbox.set_selection_mode(Gtk.SelectionMode.NONE)
        sw.set_child(self.listbox)

        self._loading_row = self._make_info_row(_('Loading seeds…'))
        self.listbox.append(self._loading_row)

        button_row = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 6)
        button_row.set_halign(Gtk.Align.END)
        add_btn = Gtk.Button.new_with_mnemonic(_('_Add Seed…'))
        add_btn.connect('clicked', lambda *_: self._add_seed())
        button_row.append(add_btn)
        content.append(button_row)

        self._search_dlg = None
        self._reload()

    @staticmethod
    def _make_info_row(text):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)
        label = Gtk.Label(label=text)
        label.set_halign(Gtk.Align.START)
        label.set_margin_top(8)
        label.set_margin_bottom(8)
        label.set_margin_start(8)
        label.set_margin_end(8)
        row.set_child(label)
        return row

    def _clear_listbox(self):
        child = self.listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            self.listbox.remove(child)
            child = nxt

    def _reload(self):
        self._clear_listbox()
        self.listbox.append(self._make_info_row(_('Loading seeds…')))
        self.worker_run(self.station.get_details, (), self._populate, 'Loading seeds…')

    def _populate(self, seeds):
        self._clear_listbox()
        if not seeds:
            self.listbox.append(self._make_info_row(_('No seeds returned by Pandora.')))
            return
        for seed in seeds:
            self.listbox.append(self._build_seed_row(seed))

    def _build_seed_row(self, seed):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(8)
        box.set_margin_end(8)

        type_label = Gtk.Label(label=self._type_label(seed.seedType))
        type_label.set_xalign(0)
        type_label.set_width_chars(8)
        type_label.add_css_class('dim-label')
        box.append(type_label)

        desc = Gtk.Label(label=seed.description or _('(unnamed)'))
        desc.set_halign(Gtk.Align.START)
        desc.set_ellipsize(Pango.EllipsizeMode.END)
        desc.set_hexpand(True)
        box.append(desc)

        del_btn = Gtk.Button.new_from_icon_name('edit-delete-symbolic')
        del_btn.set_tooltip_text(_('Delete this seed'))
        del_btn.add_css_class('flat')
        del_btn.connect('clicked', lambda *_: self._delete_seed(seed))
        box.append(del_btn)

        row.set_child(box)
        return row

    @staticmethod
    def _type_label(seed_type):
        return {'song': _('Song'), 'artist': _('Artist'), 'genre': _('Genre')}.get(seed_type, seed_type)

    def _delete_seed(self, seed):
        def on_response(dialog, response):
            dialog.destroy()
            if response != Gtk.ResponseType.YES:
                return
            self.worker_run(self.station.delete_music, (seed.seedId,),
                            lambda *_: self._reload(),
                            'Removing seed…')

        confirm = Gtk.MessageDialog(
            transient_for=self,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Remove seed?'),
            secondary_text=_('Are you sure you want to remove the {} seed "{}" from this station?').format(
                self._type_label(seed.seedType), seed.description,
            ),
        )
        confirm.connect('response', on_response)
        confirm.present()

    def _add_seed(self):
        if self._search_dlg is not None:
            self._search_dlg.present()
            return

        self._search_dlg = SearchDialog.SearchDialog(worker=self.worker_run, transient_for=self)
        self._search_dlg.set_response_sensitive(Gtk.ResponseType.OK, False)

        def on_response(dialog, response):
            result = dialog.result
            dialog.destroy()
            self._search_dlg = None
            if response == Gtk.ResponseType.OK and result is not None and result.musicId:
                self.worker_run(self.station.add_music, (result.musicId,),
                                lambda *_: self._reload(),
                                'Adding seed…')

        self._search_dlg.connect('response', on_response)
        self._search_dlg.present()

    def _on_response(self, dialog, response):
        if response == Gtk.ResponseType.CLOSE:
            self.destroy()
