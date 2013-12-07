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

import logging
import threading
import queue
from gi.repository import GObject, GLib
import traceback
GObject.threads_init()

class GObjectWorker():
    def __init__(self):
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.queue = queue.Queue()
        self.thread.start()
        
    def _run(self):
        while True:
            command, args, callback, errorback = self.queue.get()
            try:
                result = command(*args)
                if callback:
                    GLib.idle_add(callback, result)
            except Exception as e:
                e.traceback = traceback.format_exc()
                if errorback:
                    GLib.idle_add(errorback, e)
                
    def send(self, command, args=(), callback=None, errorback=None):
        if errorback is None: errorback = self._default_errorback
        self.queue.put((command, args, callback, errorback))
        
    def _default_errorback(self, error):
        logging.error("Unhandled exception in worker thread:\n{}".format(error.traceback))
        
if __name__ == '__main__':
    worker = GObjectWorker()
    import time
    from gi.repository import Gtk
    
    def test_cmd(a, b):
        logging.info("running...")
        time.sleep(5)
        logging.info("done")
        return a*b
        
    def test_cb(result):
        logging.info("got result {}".format(result))
        
    logging.info("sending")
    worker.send(test_cmd, (3,4), test_cb)
    worker.send(test_cmd, ((), ()), test_cb) #trigger exception in worker to test error handling
    
    Gtk.main()
        
                
