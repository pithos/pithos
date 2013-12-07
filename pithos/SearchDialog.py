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

import sys
import os
import html
from gi.repository import Gtk
from gi.repository import GObject

from .pithosconfig import getdatapath

class SearchDialog(Gtk.Dialog):
    __gtype_name__ = "SearchDialog"

    def __init__(self):
        """__init__ - This function is typically not called directly.
        Creation of a SearchDialog requires redeading the associated ui
        file and parsing the ui definition extrenally, 
        and then calling SearchDialog.finish_initializing().
    
        Use the convenience function NewSearchDialog to create 
        a SearchDialog object.
    
        """
        pass

    def finish_initializing(self, builder, worker_run):
        """finish_initalizing should be called after parsing the ui definition
        and creating a SearchDialog object with it in order to finish
        initializing the start of the new SearchDialog instance.
    
        """
        #get a reference to the builder and set up the signals
        self.builder = builder
        self.builder.connect_signals(self)
        
        self.entry = self.builder.get_object('entry')
        self.treeview = self.builder.get_object('treeview')
        self.okbtn = self.builder.get_object('okbtn')
        self.searchbtn = self.builder.get_object('searchbtn')
        self.model = Gtk.ListStore(GObject.TYPE_PYOBJECT, str)
        self.treeview.set_model(self.model)
        
        self.worker_run = worker_run
        
        self.result = None


    def ok(self, widget, data=None):
        """ok - The user has elected to save the changes.
        Called before the dialog returns Gtk.RESONSE_OK from run().

        """
        

    def cancel(self, widget, data=None):
        """cancel - The user has elected cancel changes.
        Called before the dialog returns Gtk.ResponseType.CANCEL for run()

        """         
        pass
        
    def search_clicked(self, widget):
        self.search(self.entry.get_text())
        
    def search(self, query):
        if not query: return
        def callback(results):
            self.model.clear()
            for i in results:
                if i.resultType is 'song':
                    mk = "<b>%s</b> by %s"%(html.escape(i.title), html.escape(i.artist))
                elif i.resultType is 'artist':
                    mk = "<b>%s</b> (artist)"%(html.escape(i.name))
                self.model.append((i, mk))
            self.treeview.show()
            self.searchbtn.set_sensitive(True)
            self.searchbtn.set_label("Search")
        self.worker_run('search', (query,), callback, "Searching...")
        self.searchbtn.set_sensitive(False)
        self.searchbtn.set_label("Searching...")
        
    def get_selected(self):
        sel = self.treeview.get_selection().get_selected()
        if sel[1]:
            return self.treeview.get_model().get_value(sel[1], 0)
            
    def cursor_changed(self, *ignore):
        self.result = self.get_selected()
        self.okbtn.set_sensitive(not not self.result)
        

def NewSearchDialog(worker_run):
    """NewSearchDialog - returns a fully instantiated
    dialog-camel_case_nameDialog object. Use this function rather than
    creating SearchDialog instance directly.
    
    """

    #look for the ui file that describes the ui
    ui_filename = os.path.join(getdatapath(), 'ui', 'SearchDialog.ui')
    if not os.path.exists(ui_filename):
        ui_filename = None

    builder = Gtk.Builder()
    builder.add_from_file(ui_filename)    
    dialog = builder.get_object("search_dialog")
    dialog.finish_initializing(builder, worker_run)
    return dialog

if __name__ == "__main__":
    dialog = NewSearchDialog()
    dialog.show()
    Gtk.main()

