# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
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

"""SecretService backed by the keyring package.

Used on platforms without a Secret Service provider, where keyring talks to
the native credential store: the Keychain on macOS and the Credential
Manager on Windows.
"""

import logging

import keyring

from .gobject_worker import GObjectWorker

_SERVICE = 'io.github.Pithos.Account'


class KeyringService:

    def __init__(self):
        self._worker = GObjectWorker()

    def unlock_keyring(self, callback):
        # The native stores are unlocked along with the user's session.
        callback(None)

    def get_account_password(self, email, callback):
        def on_finish(password):
            callback(password or '')

        def on_error(e):
            logging.error('Failed to lookup password, Error: {}'.format(e))
            callback('')

        self._worker.send(keyring.get_password, (_SERVICE, email), on_finish, on_error)

    def set_account_password(self, old_email, new_email, password, callback):
        def on_finish(success):
            if callback:
                callback(success)

        def on_error(e):
            logging.error('Failed to store password, Error: {}'.format(e))
            if callback:
                callback(False)

        self._worker.send(self._store, (old_email, new_email, password), on_finish, on_error)

    @staticmethod
    def _store(old_email, new_email, password):
        if old_email and old_email != new_email:
            try:
                keyring.delete_password(_SERVICE, old_email)
                logging.debug('Cleared password for: {}'.format(old_email))
            except keyring.errors.PasswordDeleteError:
                logging.debug('No password found to clear for: {}'.format(old_email))

        keyring.set_password(_SERVICE, new_email, password)
        return True
