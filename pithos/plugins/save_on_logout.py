### BEGIN LICENSE
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
#
# Creator: Jeremiah Cunningham <jeremiah.w.cunningham@gmail.com> 10.12.2015
#
### END LICENSE

from pithos.plugin import PithosPlugin
import logging
import sys

APP_ID = 'Pithos'

class SaveOnLogoutPlugin(PithosPlugin):
    preference = 'enable_save_on_logout'
    description = 'Save preferences on Logout (linux)'

    def bind_dbus(self):
        try:
            import dbus
            from dbus.mainloop.glib import DBusGMainLoop
            DBusGMainLoop(set_as_default=True)
        except ImportError:
            return False
        try:
            bus = dbus.SessionBus()
            session_manager = bus.get_object("org.gnome.SessionManager", "/org/gnome/SessionManager")
            self.session_manager_interface = dbus.Interface(session_manager, dbus_interface="org.gnome.SessionManager")
            self.clientId = self.session_manager_interface.RegisterClient(APP_ID, "")
            session_client = bus.get_object("org.gnome.SessionManager", self.clientId)
            self.session_client_private_interface = dbus.Interface(session_client, dbus_interface="org.gnome.SessionManager.ClientPrivate")

            bus.add_signal_receiver(self.end_session_handler,
                signal_name = "EndSession",
                dbus_interface = "org.gnome.SessionManager.ClientPrivate",
                bus_name = "org.gnome.SessionManager")

            self.method = 'dbus'
            return True
        except dbus.DBusException:
            return False

    def end_session_handler(self, flags):
        self.window.prefs_dlg.save()
        self.window.destroy()
        self.session_client_private_interface.EndSessionResponse(True, "")

    def on_enable(self):
        if sys.platform in ['win32', 'darwin']:
            loggin.error("Cannot use this plugin with non-linux systems currently")
        else:
            self.bind_dbus()
