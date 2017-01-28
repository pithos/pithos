# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
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
import logging

from gi.repository import Gtk, GObject

from .gi_composites import GtkTemplate
from .util import open_browser, popup_at_pointer
from . import SearchDialog


@GtkTemplate(ui='/io/github/Pithos/ui/StationsDialog.ui')
class StationsDialog(Gtk.Dialog):
    __gtype_name__ = "StationsDialog"
    __gsignals__ = {
        "station-renamed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "station-added": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "station-removed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    treeview = GtkTemplate.Child()
    delete_confirm_dialog = GtkTemplate.Child()
    station_menu = GtkTemplate.Child()

    def __init__(self, pithos, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_template()

        self.pithos = pithos
        self.model = pithos.stations_model
        self.worker_run = pithos.worker_run
        self.quickmix_changed = False
        self.searchDialog = None
        self.result = None

        self.modelfilter = self.model.filter_new()
        self.modelfilter.set_visible_func(lambda m, i, d: m.get_value(i, 0) and not m.get_value(i, 0).isQuickMix)

        self.modelsortable = Gtk.TreeModelSort.sort_new_with_model(self.modelfilter)
        """
        @todo Leaving it as sorting by date added by default.
        Probably should make a radio select in the window or an option in program options for user preference
        """
#        self.modelsortable.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        self.treeview.set_model(self.modelsortable)
        self.treeview.connect('button_press_event', self.on_treeview_button_press_event)

        name_col = Gtk.TreeViewColumn()
        name_col.set_title("Name")
        render_text = Gtk.CellRendererText()
        render_text.set_property('editable', True)
        render_text.connect("edited", self.station_renamed)
        name_col.pack_start(render_text, True)
        name_col.add_attribute(render_text, "text", 1)
        name_col.set_expand(True)
        name_col.set_sort_column_id(1)
        self.treeview.append_column(name_col)

        qm_col = Gtk.TreeViewColumn()
        qm_col.set_title("In QuickMix")
        render_toggle = Gtk.CellRendererToggle()
        qm_col.pack_start(render_toggle, True)

        def qm_datafunc(column, cell, model, _iter, data=None):
            if model.get_value(_iter, 0).useQuickMix:
                cell.set_active(True)
            else:
                cell.set_active(False)

        qm_col.set_cell_data_func(render_toggle, qm_datafunc)
        render_toggle.connect("toggled", self.qm_toggled)
        self.treeview.append_column(qm_col)

    def qm_toggled(self, renderer, path):
        station = self.modelfilter[path][0]
        station.useQuickMix = not station.useQuickMix
        self.quickmix_changed = True

    def station_renamed(self, cellrenderertext, path, new_text):
        station = self.modelfilter[path][0]
        self.worker_run(station.rename, (new_text,), context='net', message="Renaming Station...")
        self.model[self.modelfilter.convert_path_to_child_path(Gtk.TreePath(path))][1] = new_text
        self.emit('station-renamed', (station.id, new_text))

    def selected_station(self):
        sel = self.treeview.get_selection().get_selected()
        if sel:
            return self.treeview.get_model().get_value(sel[1], 0)

    @GtkTemplate.Callback
    def on_treeview_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor(path, col, 0)
                popup_at_pointer(self.station_menu, event)
            return True

    @GtkTemplate.Callback
    def on_menuitem_listen(self, widget):
        station = self.selected_station()
        self.pithos.station_changed(station)
        self.hide()

    @GtkTemplate.Callback
    def on_menuitem_info(self, widget):
        open_browser(self.selected_station().info_url, parent=self)

    @GtkTemplate.Callback
    def on_menuitem_rename(self, widget):
        sel = self.treeview.get_selection().get_selected()
        path = self.treeview.get_model().get_path(sel[1])
        self.treeview.set_cursor(path, self.treeview.get_column(0), True)

    @GtkTemplate.Callback
    def on_menuitem_delete(self, widget):
        station = self.selected_station()

        dialog = self.delete_confirm_dialog
        dialog.set_property('text', 'Are you sure you want to delete the station "{}"?'.format(station.name))
        response = dialog.run()
        dialog.hide()

        if response == Gtk.ResponseType.YES:
            self.worker_run(station.delete, context='net', message="Deleting Station...")
            self.pithos.remove_station(station)
            if self.pithos.current_station is station:
                self.pithos.station_changed(self.model[0][0])
            self.emit('station-removed', station)

    @GtkTemplate.Callback
    def add_station(self, widget):
        if self.searchDialog:
            self.searchDialog.present()
        else:
            self.searchDialog = SearchDialog.SearchDialog(worker=self.worker_run, transient_for=self)
            self.searchDialog.show_all()
            self.searchDialog.connect("response", self.add_station_cb)

    @GtkTemplate.Callback
    def refresh_stations(self, widget):
        self.pithos.refresh_stations(self.pithos)

    @GtkTemplate.Callback
    def add_station_cb(self, dialog, response):
        self.result = dialog.result
        logging.info("in add_station_cb {} {}".format(self.result, response))
        if response == Gtk.ResponseType.OK:
            self.worker_run("add_station_by_music_id", (self.result.musicId,),
                            self.station_added, "Creating station...")
        dialog.hide()
        dialog.destroy()
        self.searchDialog = None

    def station_already_exists(self, station):
        def on_response(dialog, response):
            if response == Gtk.ResponseType.YES:
                self.pithos.station_changed(station)
            dialog.destroy()

        sub_title = 'Pandora does not permit multiple stations with the same seed.\n'

        if self.result.resultType is 'song':
            seed = 'Song Seed: {} by {}'.format(html.escape(self.result.title), html.escape(self.result.artist))
        else:
            seed = 'Artist Seed: {}'.format(html.escape(self.result.name))

        self.result = None

        if station is self.pithos.current_station:
            button_type = Gtk.ButtonsType.OK
            message = (
                '{}"{}", the Station you are currently listening '
                'to already contains the {}.'.format(sub_title, station.name, seed)
            )

        else:
            button_type = Gtk.ButtonsType.YES_NO
            message = (
                '{}Your Station "{}" already contains the {}.\n'
                'Would you like to listen to it now?'.format(sub_title, station.name, seed)
            )

        dialog = Gtk.MessageDialog(
            parent=self,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=button_type,
            text='A New Station could not be created',
            secondary_text=message,
        )

        dialog.connect('response', on_response)
        dialog.show()

    def station_added(self, station):
        for existing_station in self.model:
            if existing_station[0].id == station.id:
                self.station_already_exists(existing_station[0])
                return
        self.result = None
        logging.debug("1 " + repr(station))
        it = self.model.insert_with_valuesv(0, (0, 1, 2), (station, station.name, 0))
        logging.debug("2 " + repr(it))
        self.pithos.station_changed(station)
        logging.debug("3 ")
        self.modelfilter.refilter()
        logging.debug("4")
        self.treeview.set_cursor(0)
        logging.debug("5 ")
        self.emit('station-added', station)

    @GtkTemplate.Callback
    def on_close(self, widget, data=None):
        self.hide()

        if self.quickmix_changed:
            self.worker_run("save_quick_mix", message="Saving QuickMix...")
            self.quickmix_changed = False

        logging.info("closed dialog")
        return True
