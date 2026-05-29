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

from pithos.plugin import PithosPlugin


class TenBandEqPlugin(PithosPlugin):
    preference = 'enable_10bandeq'
    description = '-24 to +12dB'

    def on_prepare(self):
        self.preferences_dialog = EqDialog(self)
        self.prepare_complete()


@Gtk.Template(resource_path='/io/github/Pithos/ui/EqDialog.ui')
class EqDialog(Gtk.Dialog):
    __gtype_name__ = 'EqDialog'

    band0 = Gtk.Template.Child()
    band1 = Gtk.Template.Child()
    band2 = Gtk.Template.Child()
    band3 = Gtk.Template.Child()
    band4 = Gtk.Template.Child()
    band5 = Gtk.Template.Child()
    band6 = Gtk.Template.Child()
    band7 = Gtk.Template.Child()
    band8 = Gtk.Template.Child()
    band9 = Gtk.Template.Child()

    def __init__(self, plugin):
        super().__init__(
            title=_('10 Band Equalizer'),
            transient_for=plugin.window,
            use_header_bar=1,
            resizable=False,
            default_width=200,
            default_height=200,
        )
        self.add_buttons('_Reset', Gtk.ResponseType.CANCEL, '_Close', Gtk.ResponseType.CLOSE)
        self.init_template()
        self.connect('response', self.on_response)
        self.connect('close-request', lambda *ignore: self.set_visible(False) or True)

        self._scale_handler_ids = {}
        for i in range(10):
            scale = getattr(self, 'band{}'.format(i))
            self._scale_handler_ids[i] = scale.connect('value-changed', self.on_scale_value_changed)

        self.plugin = plugin
        self.plugin.window.connect('player-ready', self.on_enabled)
        self.plugin.connect('notify::enabled', self.on_enabled)

    def on_response(self, dialog, response):
        if response == Gtk.ResponseType.CLOSE:
            self.set_visible(False)
        elif response == Gtk.ResponseType.CANCEL:
            self.zero_eq()
            self.plugin.settings['data'] = self.get_eq_values()

    def on_enabled(self, *ignore):
        if not hasattr(self.plugin.window, 'player'):
            return
        if self.plugin.enabled:
            if not self.plugin.settings['data']:
                self.plugin.settings['data'] = self.get_eq_values()
            else:
                self.load_eq_values()
        else:
            self.zero_eq()

    def on_scale_value_changed(self, scale):
        value = scale.get_value()
        name = scale.get_name()
        self.plugin.window.equalizer.set_property(name, value)
        self.plugin.settings['data'] = self.get_eq_values()

    def zero_eq(self):
        for i in range(10):
            self.set_eq_values(i)

    def get_eq_values(self):
        return ' '.join([str(self.plugin.window.equalizer.get_property('band{}'.format(i))) for i in range(10)])

    def load_eq_values(self, *ignore):
        values = self.plugin.settings['data'].split(' ')
        for i, v in enumerate(values):
            self.set_eq_values(i, float(v))

    def set_eq_values(self, index, value=0.0):
        name = 'band{}'.format(index)
        scale = getattr(self, name)
        scale.handler_block(self._scale_handler_ids[index])
        scale.set_value(value)
        scale.handler_unblock(self._scale_handler_ids[index])
        self.plugin.window.equalizer.set_property(name, value)
