# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010 Kevin Mehall <km@kevinmehall.net>
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

import sys
import os
import gtk
import logging
import webbrowser

from pithos.pithosconfig import getdatapath
from pithos import SearchDialog

class StationsDialog(gtk.Dialog):
    __gtype_name__ = "StationsDialog"

    def __init__(self):
        """__init__ - This function is typically not called directly.
        Creation of a StationsDialog requires redeading the associated ui
        file and parsing the ui definition extrenally, 
        and then calling StationsDialog.finish_initializing().
    
        Use the convenience function NewStationsDialog to create 
        a StationsDialog object.
    
        """
        pass

    def finish_initializing(self, builder, pithos):
        """finish_initalizing should be called after parsing the ui definition
        and creating a StationsDialog object with it in order to finish
        initializing the start of the new StationsDialog instance.
    
        """
        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)
        
        self.pithos = pithos
        self.model = pithos.stations_model
        self.worker_run = pithos.worker_run
        self.quickmix_changed = False
        self.searchDialog = None
        
        self.modelfilter = self.model.filter_new()
        self.modelfilter.set_visible_func(lambda m, i: m.get_value(i, 0) and not  m.get_value(i, 0).isQuickMix)
        
        self.treeview = self.builder.get_object("treeview")
        self.treeview.set_model(self.modelfilter)
        self.treeview.connect('button_press_event', self.on_treeview_button_press_event)
        
        name_col   = gtk.TreeViewColumn()
        name_col.set_title("Name")
        render_text = gtk.CellRendererText()
        render_text.set_property('editable', True)
        render_text.connect("edited", self.station_renamed)
        name_col.pack_start(render_text, expand=True)
        name_col.add_attribute(render_text, "text", 1)
        name_col.set_expand(True)
        self.treeview.append_column(name_col)
        
        qm_col   = gtk.TreeViewColumn()
        qm_col.set_title("In QuickMix")
        render_toggle = gtk.CellRendererToggle()
        qm_col.pack_start(render_toggle, expand=True)
        def qm_datafunc(column, cell, model, iter):
            if model.get_value(iter,0).useQuickMix:
                cell.set_active(True)
            else:
                cell.set_active(False)
        qm_col.set_cell_data_func(render_toggle, qm_datafunc)
        render_toggle.connect("toggled", self.qm_toggled)
        self.treeview.append_column(qm_col)
        
        self.station_menu = builder.get_object("station_menu")
        
    def qm_toggled(self, renderer, path):
        station = self.modelfilter[path][0]
        station.useQuickMix = not station.useQuickMix
        self.quickmix_changed = True
        
    def station_renamed(self, cellrenderertext, path, new_text):
        station = self.modelfilter[path][0]
        self.worker_run(station.rename, (new_text,), context='net', message="Renaming Station...")
        self.model[self.modelfilter.convert_path_to_child_path(path)][1] = new_text
        
    def selected_station(self):
        sel = self.treeview.get_selection().get_selected()
        if sel:
            return self.treeview.get_model().get_value(sel[1], 0)
           
    def on_treeview_button_press_event(self, treeview, event):
        if event.button == 3:
            x = int(event.x)
            y = int(event.y)
            time = event.time
            pthinfo = treeview.get_path_at_pos(x, y)
            if pthinfo is not None:
                path, col, cellx, celly = pthinfo
                treeview.grab_focus()
                treeview.set_cursor( path, col, 0)
                self.station_menu.popup( None, None, None, event.button, time)
            return True
            
    def on_menuitem_listen(self, widget):
        list_model = self.pithos.stations_combo.get_model()
        for row in list_model:
            if row[1] == self.selected_station().name:
                self.pithos.stations_combo.set_active_iter(row.iter)
                break
        self.hide()
        
    def on_menuitem_info(self, widget):
        webbrowser.open(self.selected_station().info_url)
        
    def on_menuitem_rename(self, widget):
        sel = self.treeview.get_selection().get_selected()
        path = self.modelfilter.get_path(sel[1])
        self.treeview.set_cursor(path, self.treeview.get_column(0) ,True)
        
    def on_menuitem_delete(self, widget):
        sel = self.treeview.get_selection().get_selected()
        iter = self.modelfilter.convert_iter_to_child_iter(sel[1])
        station = self.model.get_value(iter, 0)
        
        dialog = self.builder.get_object("delete_confirm_dialog")
        dialog.set_property("text", "Are you sure you want to delete the station \"%s\"?"%(station.name))
        response = dialog.run()
        dialog.hide()
        
        if response:
            self.worker_run(station.delete, context='net', message="Deleting Station...")
            self.model.remove(iter)
            if self.pithos.current_station is station:
                self.pithos.station_changed(self.model[0][0])
                
    def add_station(self, widget):
        if self.searchDialog:
            self.searchDialog.present()
        else:
            self.searchDialog = SearchDialog.NewSearchDialog(self.worker_run)
            self.searchDialog.show_all()
            self.searchDialog.connect("response", self.add_station_cb)
        
    def add_station_cb(self, dialog, response):
        print "in add_station_cb", dialog.result, response
        if response == 1:
            self.worker_run("add_station_by_music_id", (dialog.result.musicId,), self.station_added, "Creating station...")
        dialog.hide()
        dialog.destroy()
        self.searchDialog = None
        
    def station_added(self, station):
        logging.debug("1 "+ repr(station))
        it = self.model.insert_after(self.model.get_iter(1), (station, station.name))
        logging.debug("2 "+ repr(it))
        self.pithos.station_changed(station)
        logging.debug("3 ")
        self.modelfilter.refilter()
        logging.debug("4")
        self.treeview.set_cursor(0)
        logging.debug("5 ")
        
    def on_close(self, widget, data=None):
        self.hide()
        
        if self.quickmix_changed:
            self.worker_run("save_quick_mix",  message="Saving QuickMix...")
            self.quickmix_changed = False
        
        logging.debug("closed dialog")
        return True

def NewStationsDialog(pithos):
    """NewStationsDialog - returns a fully instantiated
    Dialog object. Use this function rather than
    creating StationsDialog instance directly.
    
    """

    #look for the ui file that describes the ui
    ui_filename = os.path.join(getdatapath(), 'ui', 'StationsDialog.ui')
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = gtk.Builder()
    builder.add_from_file(ui_filename)    
    dialog = builder.get_object("stations_dialog")
    dialog.finish_initializing(builder, pithos)
    return dialog

if __name__ == "__main__":
    dialog = NewStationsDialog()
    dialog.show()
    gtk.main()

