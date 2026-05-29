#
# Copyright (C) 2016 Jason Gray <jasonlevigray3@gmail.com>
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
# END LICENSE

import logging

from gi.repository import GObject, Gtk

from pithos.plugin import PithosPlugin

LOG_LEVELS = {
    'debug': logging.DEBUG,
    'verbose': logging.INFO,
    'warning': logging.WARN,
}


class JournalLoggingPlugin(PithosPlugin):
    preference = 'journald-logging'
    description = _('Store logs with the journald service')

    _logging_changed_handler = None

    def on_prepare(self):
        try:
            from systemd.journal import JournalHandler
            self._journal = JournalHandler(SYSLOG_IDENTIFIER='io.github.Pithos')
            self._journal.setFormatter(logging.Formatter())
            self._logger = logging.getLogger()
            self.preferences_dialog = LoggingPluginPrefsDialog(self.window, self.settings)
        except ImportError:
            self.prepare_complete(error=_('Systemd Python module not found'))
        else:
            self.prepare_complete()

    def on_enable(self):
        self._on_logging_changed(None, self.settings['data'] or 'verbose')
        self._logger.addHandler(self._journal)
        self._logging_changed_handler = self.preferences_dialog.connect('logging-changed', self._on_logging_changed)

    def _on_logging_changed(self, prefs_dialog, level):
        self.settings['data'] = level
        self._journal.setLevel(LOG_LEVELS[level])
        logging.info('setting journald logging level to: {}'.format(level))

    def on_disable(self):
        if self._logging_changed_handler:
            self.preferences_dialog.disconnect(self._logging_changed_handler)
        self._logger.removeHandler(self._journal)


class LoggingPluginPrefsDialog(Gtk.Dialog):
    __gtype_name__ = 'LoggingPluginPrefsDialog'
    __gsignals__ = {
        'logging-changed': (GObject.SignalFlags.RUN_FIRST, None, (GObject.TYPE_STRING,)),
    }

    def __init__(self, parent, settings):
        super().__init__(
            title=_('Logging Level'),
            transient_for=parent,
            use_header_bar=1,
            resizable=False,
            default_width=300,
        )
        self.add_buttons('_Cancel', Gtk.ResponseType.CANCEL, '_Apply', Gtk.ResponseType.APPLY)
        self.pithos_window = parent
        self.settings = settings

        self.connect('close-request', lambda *ignore: self.response(Gtk.ResponseType.CANCEL) or True)

        sub_title = Gtk.Label.new(_('Set the journald logging level for Pithos'))
        sub_title.set_halign(Gtk.Align.CENTER)

        self._level_ids = ['debug', 'verbose', 'warning']
        level_labels = ['High - debug', 'Default - verbose', 'Low - warning']
        self.log_level_combo = Gtk.DropDown.new(Gtk.StringList.new(level_labels), None)

        self._reset_combo()
        content_area = self.get_content_area()
        content_area.set_spacing(12)
        content_area.set_margin_top(12)
        content_area.set_margin_bottom(12)
        content_area.set_margin_start(12)
        content_area.set_margin_end(12)

        content_area.append(sub_title)
        content_area.append(self.log_level_combo)

    def _reset_combo(self):
        try:
            idx = self._level_ids.index(self.settings['data'] or 'verbose')
        except ValueError:
            idx = self._level_ids.index('verbose')
        self.log_level_combo.set_selected(idx)

    def _active_id(self):
        idx = self.log_level_combo.get_selected()
        if 0 <= idx < len(self._level_ids):
            return self._level_ids[idx]
        return None

    def do_response(self, response):
        if response != Gtk.ResponseType.APPLY:
            self.set_visible(False)
            self._reset_combo()
            return

        setting = self.settings['data']
        active_id = self._active_id()

        if setting == active_id:
            self.set_visible(False)
            return

        if active_id != 'debug':
            self.set_visible(False)
            self.emit('logging-changed', active_id)
            return

        def on_dialog_response(dialog, response):
            if response == Gtk.ResponseType.YES:
                self.set_visible(False)
                self.emit('logging-changed', active_id)
            dialog.destroy()

        message = (_(
            'The debug logging level is not '
            'recommended unless you are actually debugging an issue, '
            'as it generates very large logs.\n\nAre you sure you want to set logging to debug?',
        ))

        dialog = Gtk.MessageDialog(
            transient_for=self.pithos_window.prefs_dlg,
            modal=True,
            message_type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Debug Logging Level'),
            secondary_text=message,
        )

        dialog.connect('response', on_dialog_response)
        dialog.present()
