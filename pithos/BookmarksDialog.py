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

from gi.repository import Gtk, Pango


class BookmarksDialog(Gtk.Dialog):
    __gtype_name__ = "BookmarksDialog"

    def __init__(self, pithos):
        super().__init__(
            title=_('Bookmarks'),
            transient_for=pithos,
            modal=True,
            use_header_bar=1,
        )
        self.set_default_size(520, 460)
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
        content.set_spacing(8)

        self.notebook = Gtk.Notebook()
        self.notebook.set_vexpand(True)
        content.append(self.notebook)

        self.songs_listbox = self._build_listbox()
        self.notebook.append_page(self._wrap_in_scroll(self.songs_listbox),
                                  Gtk.Label(label=_('Songs')))

        self.artists_listbox = self._build_listbox()
        self.notebook.append_page(self._wrap_in_scroll(self.artists_listbox),
                                  Gtk.Label(label=_('Artists')))

        self.songs_listbox.append(self._make_info_row(_('Loading bookmarks…')))
        self.artists_listbox.append(self._make_info_row(_('Loading bookmarks…')))

        self._reload()

    @staticmethod
    def _build_listbox():
        lb = Gtk.ListBox()
        lb.set_selection_mode(Gtk.SelectionMode.NONE)
        return lb

    @staticmethod
    def _wrap_in_scroll(child):
        sw = Gtk.ScrolledWindow()
        sw.set_policy(Gtk.PolicyType.NEVER, Gtk.PolicyType.AUTOMATIC)
        sw.set_child(child)
        return sw

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

    @staticmethod
    def _clear_listbox(listbox):
        child = listbox.get_first_child()
        while child is not None:
            nxt = child.get_next_sibling()
            listbox.remove(child)
            child = nxt

    def _reload(self):
        self.worker_run(self.pithos.pandora.get_bookmarks, (), self._populate, 'Loading bookmarks…')

    def _populate(self, result):
        songs, artists = result
        self._clear_listbox(self.songs_listbox)
        self._clear_listbox(self.artists_listbox)

        if not songs:
            self.songs_listbox.append(self._make_info_row(_('No bookmarked songs.')))
        else:
            for b in songs:
                self.songs_listbox.append(self._build_song_row(b))

        if not artists:
            self.artists_listbox.append(self._make_info_row(_('No bookmarked artists.')))
        else:
            for b in artists:
                self.artists_listbox.append(self._build_artist_row(b))

    def _build_song_row(self, bookmark):
        primary = bookmark.title or _('(unknown song)')
        secondary_parts = []
        if bookmark.artist:
            secondary_parts.append(_('by {}').format(bookmark.artist))
        if bookmark.album:
            secondary_parts.append(_('on {}').format(bookmark.album))
        secondary = '  •  '.join(secondary_parts)

        return self._build_row(primary, secondary,
                               lambda: self.pithos.pandora.delete_song_bookmark(bookmark.bookmarkToken))

    def _build_artist_row(self, bookmark):
        primary = bookmark.artist or _('(unknown artist)')
        return self._build_row(primary, '',
                               lambda: self.pithos.pandora.delete_artist_bookmark(bookmark.bookmarkToken))

    def _build_row(self, primary_text, secondary_text, delete_fn):
        row = Gtk.ListBoxRow()
        row.set_selectable(False)
        row.set_activatable(False)

        box = Gtk.Box.new(Gtk.Orientation.HORIZONTAL, 8)
        box.set_margin_top(4)
        box.set_margin_bottom(4)
        box.set_margin_start(8)
        box.set_margin_end(8)

        text_box = Gtk.Box.new(Gtk.Orientation.VERTICAL, 0)
        text_box.set_hexpand(True)

        primary = Gtk.Label(label=primary_text)
        primary.set_halign(Gtk.Align.START)
        primary.set_ellipsize(Pango.EllipsizeMode.END)
        text_box.append(primary)

        if secondary_text:
            secondary = Gtk.Label(label=secondary_text)
            secondary.set_halign(Gtk.Align.START)
            secondary.set_ellipsize(Pango.EllipsizeMode.END)
            secondary.add_css_class('dim-label')
            text_box.append(secondary)

        box.append(text_box)

        del_btn = Gtk.Button.new_from_icon_name('edit-delete-symbolic')
        del_btn.set_tooltip_text(_('Remove this bookmark'))
        del_btn.add_css_class('flat')
        del_btn.connect('clicked', lambda *_: self._delete(row, delete_fn))
        box.append(del_btn)

        row.set_child(box)
        return row

    def _delete(self, row, delete_fn):
        def done(*_ignore):
            parent = row.get_parent()
            if parent is not None:
                parent.remove(row)

        self.worker_run(delete_fn, (), done, 'Removing bookmark…')

    def _on_response(self, dialog, response):
        if response == Gtk.ResponseType.CLOSE:
            self.destroy()
