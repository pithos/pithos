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


import sys
import signal
import logging

import gi
gi.require_version('Gtk', '3.0')
from gi.repository import GLib, Gio, Gtk

from .pithos import PithosWindow
from .migrate_settings import maybe_migrate_settings

class PithosApplication(Gtk.Application):
    __gtype_name__ = 'PithosApplication'

    def __init__(self, version=''):
        super().__init__(application_id='io.github.Pithos',
                                flags=Gio.ApplicationFlags.HANDLES_COMMAND_LINE)
        self.window = None
        self.test_mode = False
        self.version = version

        self.add_main_option('verbose', ord('v'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Show info messages'), None)
        self.add_main_option('debug', ord('d'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Show debug messages'), None)
        self.add_main_option('test', ord('t'), GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Use a mock service instead of connecting to the real Pandora server'), None)
        self.add_main_option('version', 0, GLib.OptionFlags.NONE, GLib.OptionArg.NONE,
                             _('Show the version'), None)

    def do_startup(self):
        Gtk.Application.do_startup(self)
        signal.signal(signal.SIGINT, signal.SIG_DFL)

        action = Gio.SimpleAction.new("stations", None)
        action.connect("activate", self.stations_cb)
        self.add_action(action)

        action = Gio.SimpleAction.new("preferences", None)
        action.connect("activate", self.prefs_cb)
        self.add_action(action)

        action = Gio.SimpleAction.new("about", None)
        action.connect("activate", self.about_cb)
        self.add_action(action)

        action = Gio.SimpleAction.new("quit", None)
        action.connect("activate", self.quit_cb)
        self.add_action(action)

        if Gtk.get_major_version() > 3 or Gtk.get_minor_version() >= 20:
            menu = self.get_app_menu()
            it = menu.iterate_item_links(menu.get_n_items() - 1)
            assert(it.next())
            last_section = it.get_value()
            shortcuts_item = Gio.MenuItem.new(_('Keyboard Shortcuts'), 'win.show-help-overlay')
            last_section.prepend_item(shortcuts_item)

    def do_command_line(self, command_line):
        options = command_line.get_options_dict()

        # First, get rid of existing logging handlers due to call in header as per
        # http://stackoverflow.com/questions/1943747/python-logging-before-you-run-logging-basicconfig
        logging.root.handlers = []

        # Show the version on local instance and exit
        if options.contains('version'):
            # Broken bindings...
            type(command_line).do_print_literal(command_line, "Pithos {}\n".format(self.version))
            return 0

        handlers = []
        try:
            from systemd.journal import JournalHandler

            journal = JournalHandler(SYSLOG_IDENTIFIER=self.props.application_id)

            # We can be more verbose with the journal and filter it later
            # and don't need fancy formatting as its part of the structure
            journal.setLevel(logging.INFO)
            journal.setFormatter(logging.Formatter())

            handlers.append(journal)
        except ImportError:
            pass

        # Set the logging level to show debug messages
        if options.contains('debug'):
            log_level = logging.DEBUG
        elif options.contains('verbose'):
            log_level = logging.INFO
        else:
            log_level = logging.WARN

        stream = logging.StreamHandler()
        stream.setLevel(log_level)
        stream.setFormatter(logging.Formatter(fmt='%(levelname)s - %(module)s:%(funcName)s:%(lineno)d - %(message)s'))
        handlers.append(stream)

        logging.basicConfig(level=logging.NOTSET, handlers=handlers)

        self.test_mode = options.lookup_value('test')

        self.do_activate()

        return 0

    def do_activate(self):
        if not self.window:
            maybe_migrate_settings()
            logging.info("Pithos %s" %self.version)
            self.window = PithosWindow(self, self.test_mode)

        self.window.present()

    def do_shutdown(self):
        Gtk.Application.do_shutdown(self)
        if self.window:
            self.window.destroy()

    def stations_cb(self, action, param):
        self.window.show_stations()

    def prefs_cb(self, action, param):
        self.window.show_preferences()

    def about_cb(self, action, param):
        self.window.show_about(self.version)

    def quit_cb(self, action, param):
        self.window.destroy()

def main(version=''):
    app = PithosApplication(version=version)
    exit_status = app.run(sys.argv)
    sys.exit(exit_status)

if __name__ == '__main__':
    main()
