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

import threading
import Queue
import gobject
gobject.threads_init()

class GObjectWorker():
    def __init__(self):
        self.thread = threading.Thread(target=self._run)
        self.thread.daemon = True
        self.queue = Queue.Queue()
        self.thread.start()
        
    def _run(self):
        while True:
            command, args, callback, errorback = self.queue.get()
            try:
                result = command(*args)
                gobject.idle_add(callback, result)
            except Exception, e:
                gobject.idle_add(errorback, e)
                
    def send(self, command, args, callback, errorback=None):
        if errorback is None: errorback = self._default_errorback
        self.queue.put((command, args, callback, errorback))
        
    def _default_errorback(self, error):
        print "Unhandled exception in worker thread:", error
        
if __name__ == '__main__':
    worker = GObjectWorker()
    import time, gtk
    
    def test_cmd(a, b):
        print "running..."
        time.sleep(5)
        print "done"
        return a*b
        
    def test_cb(result):
        print "got result", result
        
    print "sending"
    worker.send(test_cmd, (3,4), test_cb)
    worker.send(test_cmd, ((), ()), test_cb) #trigger exception in worker to test error handling
    
    gtk.main()
        
                
