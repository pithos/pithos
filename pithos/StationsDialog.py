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

from gi.repository import Gtk, Gdk, Gio, GObject

from .util import open_browser
from . import SearchDialog
from .StationSeedsDialog import StationSeedsDialog


@Gtk.Template(resource_path='/io/github/Pithos/ui/StationsDialog.ui')
class StationsDialog(Gtk.Dialog):
    __gtype_name__ = "StationsDialog"
    __gsignals__ = {
        "station-renamed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "station-added": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
        "station-removed": (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_PYOBJECT,)),
    }

    treeview = Gtk.Template.Child()
    delete_confirm_dialog = Gtk.Template.Child()

    def __init__(self, pithos, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.init_template()

        self.pithos = pithos
        self.model = pithos.stations_model
        self.worker_run = pithos.worker_run
        self.quickmix_changed = False
        self.searchDialog = None

        self.modelfilter = self.model.filter_new()

        def visible_func(m, i, d):
            return m.get_value(i, 0) and not (m.get_value(i, 0).isQuickMix or m.get_value(i, 0).isThumbprint)

        self.modelfilter.set_visible_func(visible_func)

        self.modelsortable = Gtk.TreeModelSort.new_with_model(self.modelfilter)
        """
        @todo Leaving it as sorting by date added by default.
        Probably should make a radio select in the window or an option in program options for user preference
        """
#        self.modelsortable.set_sort_column_id(1, Gtk.SortType.ASCENDING)

        self.treeview.set_model(self.modelsortable)

        # Station context menu (right-click on treeview)
        station_menu = Gio.Menu()
        station_menu.append(_("Listen to Station"), "ctx.station-listen")
        station_menu.append(_("Station Info"), "ctx.station-info")
        station_menu.append(_("Edit Seeds…"), "ctx.station-seeds")
        station_menu.append(_("Share Station…"), "ctx.station-share")
        station_menu.append(_("Rename Station"), "ctx.station-rename")
        station_menu.append(_("Delete Station"), "ctx.station-delete")

        self._station_menu_popover = Gtk.PopoverMenu.new_from_model(station_menu)
        self._station_menu_popover.set_parent(self.treeview)
        self._station_menu_popover.set_has_arrow(False)

        ctx_group = Gio.SimpleActionGroup()
        for name, handler in [
            ('station-listen', lambda *_: self.on_menuitem_listen(None)),
            ('station-info',   lambda *_: self.on_menuitem_info(None)),
            ('station-seeds',  lambda *_: self.on_menuitem_seeds(None)),
            ('station-share',  lambda *_: self.on_menuitem_share(None)),
            ('station-rename', lambda *_: self.on_menuitem_rename(None)),
            ('station-delete', lambda *_: self.on_menuitem_delete(None)),
        ]:
            a = Gio.SimpleAction.new(name, None)
            a.connect('activate', handler)
            ctx_group.add_action(a)
        self.insert_action_group('ctx', ctx_group)

        right_click = Gtk.GestureClick.new()
        right_click.set_button(3)
        right_click.connect('pressed', self._on_treeview_right_click)
        self.treeview.add_controller(right_click)

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
        old_station_name = station.name

        def errorback(e):
            self.pithos.statusbar.pop(self.pithos.statusbar.get_context_id('net'))
            if hasattr(e, 'status') and e.status == 1008:
                dialog = Gtk.MessageDialog(
                    transient_for=self,
                    modal=True,
                    message_type=Gtk.MessageType.WARNING,
                    buttons=Gtk.ButtonsType.OK,
                    text='Could Not Rename {}'.format(old_station_name),
                    secondary_text='Pandora does not permit renaming {}.'.format(old_station_name),
                )

                dialog.connect('response', lambda *ignore: dialog.destroy())
                dialog.present()

            elif hasattr(e, 'message') and hasattr(e, 'submsg'):
                self.window.error_dialog(e.message, None, submsg=e.submsg)

            else:
                logging.warning(e.traceback)

            self.model[self.modelfilter.convert_path_to_child_path(Gtk.TreePath(path))][1] = old_station_name

        def success(*ignore):
            self.emit('station-renamed', (station.id, new_text))

        self.worker_run(
            station.rename,
            (new_text,),
            callback=success,
            errorback=errorback,
            context='net',
            message="Renaming Station..."
        )

        self.model[self.modelfilter.convert_path_to_child_path(Gtk.TreePath(path))][1] = new_text

    def selected_station(self):
        sel = self.treeview.get_selection().get_selected()
        if sel:
            return self.treeview.get_model().get_value(sel[1], 0)

    def _on_treeview_right_click(self, gesture, n_press, x, y):
        pthinfo = self.treeview.get_path_at_pos(int(x), int(y))
        if pthinfo is None:
            return
        path, col, cellx, celly = pthinfo
        self.treeview.grab_focus()
        self.treeview.set_cursor(path, col, 0)
        rect = Gdk.Rectangle()
        rect.x, rect.y, rect.width, rect.height = int(x), int(y), 1, 1
        self._station_menu_popover.set_pointing_to(rect)
        self._station_menu_popover.popup()

    # Station context menu actions
    def on_menuitem_listen(self, widget):
        station = self.selected_station()
        self.pithos.station_changed(station)
        self.set_visible(False)

    def on_menuitem_info(self, widget):
        open_browser(self.selected_station().info_url, parent=self)

    def on_menuitem_seeds(self, widget):
        station = self.selected_station()
        if station is None:
            return
        dlg = StationSeedsDialog(self.pithos, station, parent=self)
        dlg.present()

    def on_menuitem_share(self, widget):
        station = self.selected_station()
        if station is None:
            return

        dialog = Gtk.Dialog(
            title=_('Share "{}"').format(station.name),
            transient_for=self,
            modal=True,
            use_header_bar=1,
            default_width=380,
        )
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

        def on_text_changed(e):
            dialog.set_response_sensitive(Gtk.ResponseType.APPLY, bool(e.get_text().strip()))
        entry.connect('changed', on_text_changed)
        entry.connect('activate', lambda *_: dialog.response(Gtk.ResponseType.APPLY))

        def on_response(dlg, response):
            if response == Gtk.ResponseType.APPLY:
                emails = [e.strip() for e in entry.get_text().split(',') if e.strip()]
                if emails:
                    self.worker_run(station.share, (emails,), None, _('Sharing station…'))
            dlg.destroy()

        dialog.connect('response', on_response)
        dialog.present()

    def on_menuitem_rename(self, widget):
        sel = self.treeview.get_selection().get_selected()
        path = self.treeview.get_model().get_path(sel[1])
        self.treeview.set_cursor(path, self.treeview.get_column(0), True)

    def on_menuitem_delete(self, widget):
        station = self.selected_station()

        dialog = self.delete_confirm_dialog
        dialog.set_property('text', 'Are you sure you want to delete the station "{}"?'.format(station.name))

        def on_response(dialog, response):
            dialog.disconnect_by_func(on_response)
            dialog.set_visible(False)
            if response == Gtk.ResponseType.YES:
                self.worker_run(station.delete, context='net', message="Deleting Station...")
                self.pithos.remove_station(station)
                if self.pithos.current_station is station:
                    self.pithos.station_changed(self.model[0][0])
                self.emit('station-removed', station)

        dialog.connect('response', on_response)
        dialog.present()

    @Gtk.Template.Callback()
    def add_station(self, widget):
        if self.searchDialog:
            self.searchDialog.present()
        else:
            self.searchDialog = SearchDialog.SearchDialog(worker=self.worker_run, transient_for=self)
            self.searchDialog.present()
            self.searchDialog.connect("response", self.add_station_cb)

    @Gtk.Template.Callback()
    def refresh_stations(self, widget):
        self.pithos.refresh_stations(self.pithos)

    def add_station_cb(self, dialog, response):
        result = dialog.result
        if result is not None:
            if result.resultType == 'song':
                description = '{} by {}'.format(html.escape(result.title), html.escape(result.artist))
            elif result.resultType == 'artist':
                description = html.escape(result.name)
            else:
                description = html.escape(result.stationName)
            user_data = result.resultType, description
            logging.info("in add_station_cb {} {}".format(result, response))
            if response == Gtk.ResponseType.OK:
                self.worker_run(
                    "add_station_by_music_id",
                    (result.musicId,),
                    self.station_added,
                    "Creating station...",
                    user_data=user_data,
                )

        dialog.destroy()
        self.searchDialog = None

    def station_added(self, station, user_data):
        music_type, description = user_data
        for existing_station in self.model:
            if existing_station[0].id == station.id:
                self.pithos.station_already_exists(existing_station[0], description, music_type, self)
                return
        logging.debug("1 " + repr(station))
        # We shouldn't actually add the station to the pandora stations list
        # until we know it's not a duplicate.
        self.pithos.pandora.stations.append(station)
        it = self.model.insert_with_valuesv(0, (0, 1, 2), (station, station.name, 0))
        logging.debug("2 " + repr(it))
        self.emit('station-added', station)
        self.pithos.station_changed(station)
        logging.debug("3 ")
        self.modelfilter.refilter()
        logging.debug("4")
        self.treeview.set_cursor(0)
        logging.debug("5 ")

    @Gtk.Template.Callback()
    def on_close(self, widget, data=None):
        self.set_visible(False)

        if self.quickmix_changed:
            self.worker_run("save_quick_mix", message="Saving QuickMix...")
            self.quickmix_changed = False

        logging.info("closed dialog")
        return True
