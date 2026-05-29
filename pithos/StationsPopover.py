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
from gi.repository import Gdk, GLib, Gio, Gtk, Pango

from .util import open_browser


class StationsPopover(Gtk.Popover):
    __gtype_name__ = "StationsPopover"

    def __init__(self, pithos=None):
        super().__init__()
        self.pithos = pithos

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

        self._setup_context_menu()

        self.set_child(box)

    def _setup_context_menu(self):
        if self.pithos is None:
            return

        ctx_menu = Gio.Menu()
        ctx_menu.append(_('Listen to Station'), 'ctx.listen')
        ctx_menu.append(_('Station Info'), 'ctx.info')
        ctx_menu.append(_('Edit Seeds…'), 'ctx.seeds')
        ctx_menu.append(_('Share Station…'), 'ctx.share')
        ctx_menu.append(_('Delete Station'), 'ctx.delete')

        # Nest the context popover inside the listbox so it appears at the
        # clicked row. To keep the outer stations popover from getting its
        # grab stuck open, the inner popover is set non-autohiding: it
        # doesn't take grab away from the outer. Dismissal of the inner is
        # handled in three ways: PopoverMenu auto-dismisses on action
        # activation; the outer's 'closed' signal forwards to it; and a
        # key controller closes it on Escape.
        self._ctx_popover = Gtk.PopoverMenu.new_from_model(ctx_menu)
        self._ctx_popover.set_parent(self.listbox)
        self._ctx_popover.set_has_arrow(False)
        self._ctx_popover.set_autohide(False)
        self._ctx_station = None

        ctx_group = Gio.SimpleActionGroup()
        for name, handler in [
            ('listen', self._ctx_listen),
            ('info',   self._ctx_info),
            ('seeds',  self._ctx_seeds),
            ('share',  self._ctx_share),
            ('delete', self._ctx_delete),
        ]:
            action = Gio.SimpleAction.new(name, None)
            action.connect('activate', handler)
            ctx_group.add_action(action)
        self.listbox.insert_action_group('ctx', ctx_group)

        # When the outer stations popover closes (autohide on outside click),
        # dismiss the inner context popover too.
        self.connect('closed', lambda *_: self._ctx_popover.popdown())

        # Escape closes the inner popover (it isn't autohide, so it won't
        # close on its own from key events).
        key_ctl = Gtk.EventControllerKey.new()
        key_ctl.connect('key-pressed', self._on_ctx_key_pressed)
        self._ctx_popover.add_controller(key_ctl)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect('pressed', self._on_right_click)
        self.listbox.add_controller(right_click)

    def _on_ctx_key_pressed(self, controller, keyval, keycode, state):
        if keyval == Gdk.KEY_Escape:
            self._ctx_popover.popdown()
            return True
        return False

    def _on_right_click(self, gesture, n_press, x, y):
        row = self.listbox.get_row_at_y(int(y))
        if row is None or not hasattr(row, 'station'):
            return
        station = row.station
        if station.isQuickMix or station.isThumbprint:
            return
        gesture.set_state(Gtk.EventSequenceState.CLAIMED)
        self._ctx_station = station
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self._ctx_popover.set_pointing_to(rect)
        self._ctx_popover.popup()

    def _ctx_listen(self, *_ignore):
        if self._ctx_station is None:
            return
        self.set_visible(False)
        self.pithos.station_changed(self._ctx_station)

    def _ctx_info(self, *_ignore):
        if self._ctx_station is None:
            return
        open_browser(self._ctx_station.info_url, parent=self.pithos)

    def _ctx_seeds(self, *_ignore):
        if self._ctx_station is None:
            return
        from .StationSeedsDialog import StationSeedsDialog
        StationSeedsDialog(self.pithos, self._ctx_station).present()

    def _ctx_share(self, *_ignore):
        if self._ctx_station is None:
            return
        station = self._ctx_station
        dialog = Gtk.Dialog(
            title=_('Share "{}"').format(station.name),
            transient_for=self.pithos,
            modal=True,
            use_header_bar=1,
        )
        dialog.set_default_size(380, -1)
        dialog.add_buttons('_Cancel', Gtk.ResponseType.CANCEL, '_Share', Gtk.ResponseType.APPLY)
        dialog.set_response_sensitive(Gtk.ResponseType.APPLY, False)

        content = dialog.get_content_area()
        content.set_margin_top(12)
        content.set_margin_bottom(12)
        content.set_margin_start(12)
        content.set_margin_end(12)
        content.set_spacing(8)

        prompt = Gtk.Label(label=_('Enter the email address of the person you want to share this station with. '
                                   'Separate multiple addresses with commas.'))
        prompt.set_wrap(True)
        prompt.set_xalign(0)
        content.append(prompt)

        entry = Gtk.Entry()
        entry.set_input_purpose(Gtk.InputPurpose.EMAIL)
        entry.set_placeholder_text('friend@example.com')
        content.append(entry)

        entry.connect('changed', lambda e: dialog.set_response_sensitive(
            Gtk.ResponseType.APPLY, bool(e.get_text().strip())))
        entry.connect('activate', lambda *_: dialog.response(Gtk.ResponseType.APPLY))

        def on_response(dlg, response):
            if response == Gtk.ResponseType.APPLY:
                emails = [e.strip() for e in entry.get_text().split(',') if e.strip()]
                if emails:
                    self.pithos.worker_run(station.share, (emails,), None, _('Sharing station…'))
            dlg.destroy()

        dialog.connect('response', on_response)
        dialog.present()

    def _ctx_delete(self, *_ignore):
        if self._ctx_station is None:
            return
        station = self._ctx_station

        def on_response(dialog, response):
            dialog.destroy()
            if response != Gtk.ResponseType.YES:
                return
            was_current = self.pithos.current_station is station
            self.pithos.worker_run(station.delete, (), None, _('Deleting station…'))
            self.pithos.remove_station(station)
            if was_current and len(self.pithos.stations_model):
                self.pithos.station_changed(self.pithos.stations_model[0][0])

        confirm = Gtk.MessageDialog(
            transient_for=self.pithos,
            modal=True,
            message_type=Gtk.MessageType.QUESTION,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Delete station "{}"?').format(station.name),
            secondary_text=_('This cannot be undone.'),
        )
        confirm.connect('response', on_response)
        confirm.present()

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
