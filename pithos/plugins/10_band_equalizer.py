#
# Copyright (C) 2017 Jason Gray <jasonlevigray3@gmail.com>
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

from gi.repository import Gtk

from pithos.gi_composites import GtkTemplate
from pithos.plugin import PithosPlugin


class TenBandEqPlugin(PithosPlugin):
    preference = 'enable_10bandeq'
    description = '-24 to +12dB'

    def on_prepare(self):
        self.preferences_dialog = EqDialog(self)
        self.prepare_complete()


@GtkTemplate(ui='/io/github/Pithos/ui/EqDialog.ui')
class EqDialog(Gtk.Dialog):
    __gtype_name__ = 'EqDialog'

    band0 = GtkTemplate.Child()
    band1 = GtkTemplate.Child()
    band2 = GtkTemplate.Child()
    band3 = GtkTemplate.Child()
    band4 = GtkTemplate.Child()
    band5 = GtkTemplate.Child()
    band6 = GtkTemplate.Child()
    band7 = GtkTemplate.Child()
    band8 = GtkTemplate.Child()
    band9 = GtkTemplate.Child()

    def __init__(self, plugin):
        super().__init__(
            _('Logging Level'),
            plugin.window,
            0,
            ('_Reset', Gtk.ResponseType.CANCEL, '_Close', Gtk.ResponseType.CLOSE),
            use_header_bar=1,
        )
        self.init_template()
        self.set_title(_('10 Band Equalizer'))
        self.set_default_size(200, 200)
        self.set_resizable(False)
        self.connect('response', self.on_response)
        self.connect('delete-event', lambda *ignore: self.hide_on_delete())

        self.plugin = plugin
        self.plugin.connect('notify::enabled', self.on_enabled)

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.CLOSE:
            self.hide()
        elif response == Gtk.ResponseType.CANCEL:
            self.zero_eq()
            self.plugin.settings['data'] = self.get_eq_values()

    def on_enabled(self, *ignore):
        if self.plugin.enabled:
            if not self.plugin.settings['data']:
                self.plugin.settings['data'] = self.get_eq_values()
            else:
                self.load_eq_values()
        else:
            self.zero_eq()

    @GtkTemplate.Callback
    def on_scale_value_changed(self, scale):
        value = scale.get_value()
        name = scale.get_name()
        self.plugin.window.player.set_property('eq-' + name, value)
        self.plugin.settings['data'] = self.get_eq_values()

    def zero_eq(self):
        for i in range(10):
            self.set_eq_values(i)

    def get_eq_values(self):
        return ' '.join((str(self.plugin.window.player.get_property('eq-band{}'.format(i))) for i in range(10)))

    def load_eq_values(self, *ignore):
        values = self.plugin.settings['data'].split(' ')
        for i, v in enumerate(values):
            self.set_eq_values(i, float(v))

    def set_eq_values(self, index, value=0.0):
        name = 'band{}'.format(index)
        scale = getattr(self, name)
        scale.handler_block_by_func(self.on_scale_value_changed)
        scale.set_value(value)
        scale.handler_unblock_by_func(self.on_scale_value_changed)
        self.plugin.window.player.set_property('eq-' + name, value)
