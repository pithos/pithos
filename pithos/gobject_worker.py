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

import logging
import threading
from gi.repository import GLib
import traceback


class GObjectWorker:

    def send(self, command, args=(), callback=None, errorback=None):
        def run(data):
            command, args, callback, errorback = data
            try:
                result = command(*args)
                if callback:
                    GLib.idle_add(callback, result, priority=GLib.PRIORITY_DEFAULT)
            except Exception as e:
                e.traceback = traceback.format_exc()
                if errorback:
                    GLib.idle_add(errorback, e, priority=GLib.PRIORITY_DEFAULT)
        if errorback is None:
            errorback = self._default_errorback
        data = command, args, callback, errorback
        thread = threading.Thread(target=run, args=(data,))
        thread.daemon = True
        thread.start()

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
        return a * b

    def test_cb(result):
        logging.info("got result {}".format(result))

    logging.info("sending")
    worker.send(test_cmd, (3, 4), test_cb)
    worker.send(test_cmd, ((), ()), test_cb) # trigger exception in worker to test error handling

    Gtk.main()
