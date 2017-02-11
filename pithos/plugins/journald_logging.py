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
            return _('Systemd Python module not found')

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

    def __init__(self, parent, settings, *args, **kwargs):
        super().__init__(
            _('Logging Level'),
            parent,
            0,
            ('_Cancel', Gtk.ResponseType.CANCEL, '_Apply', Gtk.ResponseType.APPLY),
            *args,
            use_header_bar=1,
            **kwargs,
        )
        self.set_default_size(300, -1)
        self.pithos_window = parent
        self.settings = settings
        self.set_resizable(False)
        self.connect('response', self._on_response)

        sub_title = Gtk.Label.new(_('Set the journald logging level for Pithos'))
        sub_title.set_halign(Gtk.Align.CENTER)
        self.log_level_combo = Gtk.ComboBoxText.new()

        logging_levels = [
            ('debug', 'High - debug'),
            ('verbose', 'Default - verbose'),
            ('warning', 'Low - warning'),
        ]

        for level in logging_levels:
            self.log_level_combo.append(level[0], level[1])

        self._reset_combo()
        content_area = self.get_content_area()

        content_area.add(sub_title)
        content_area.add(self.log_level_combo)
        content_area.show_all()

    def _reset_combo(self):
        self.log_level_combo.set_active_id(self.settings['data'] or 'verbose')

    def _on_response(self, dialog, response):
        if response != Gtk.ResponseType.APPLY:
            self.hide()
            self._reset_combo()
            return

        setting = self.settings['data']
        active_id = self.log_level_combo.get_active_id()

        if setting == active_id:
            self.hide()
            return

        if active_id != 'debug':
            self.hide()
            self.emit('logging-changed', active_id)
            return

        def on_dialog_response(dialog, response):
            if response == Gtk.ResponseType.YES:
                self.hide()
                self.emit('logging-changed', active_id)
            dialog.destroy()

        message = (_(
            'The debug logging level is not '
            'recommended unless you are actually debugging an issue, '
            'as it generates very large logs.\n\nAre you sure you want to set logging to debug?',
        ))

        dialog = Gtk.MessageDialog(
            parent=self.pithos_window.prefs_dlg,
            flags=Gtk.DialogFlags.MODAL,
            type=Gtk.MessageType.WARNING,
            buttons=Gtk.ButtonsType.YES_NO,
            text=_('Debug Logging Level'),
            secondary_text=message,
        )

        dialog.connect('response', on_dialog_response)
        dialog.show()
