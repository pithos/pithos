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
import util
from gi.repository import GLib

if util.is_msys2():
    import win32cred
else:
    import gi
    gi.require_version('Secret', '1')
    from gi.repository import Secret


class _DefaultSecretService:

    _account_schema = Secret.Schema.new(
        'io.github.Pithos.Account',
        Secret.SchemaFlags.NONE,
        {'email': Secret.SchemaAttributeType.STRING},
    )

    def __init__(self):
        self._current_collection = Secret.COLLECTION_DEFAULT

    def unlock_keyring(self, callback):
        # Inside of flatpak we only have access to the simple API.
        if util.is_flatpak():
            callback(None)
            return

        def on_unlock_finish(source, result, data):
            service, default_collection = data
            try:
                num_items, unlocked = service.unlock_finish(result)
            except GLib.Error as e:
                logging.error('Error on service.unlock, Error: {}'.format(e))
                callback(e)
            else:
                if not num_items or default_collection not in unlocked:
                    self._current_collection = Secret.COLLECTION_SESSION
                    logging.debug('The default keyring is still locked. Using session collection.')
                else:
                    logging.debug('The default keyring was unlocked.')
                callback(None)

        def on_for_alias_finish(source, result, service):
            try:
                default_collection = Secret.Collection.for_alias_finish(result)
            except GLib.Error as e:
                logging.error('Error getting Secret.COLLECTION_DEFAULT, Error: {}'.format(e))
                callback(e)
            else:
                if default_collection is None:
                    logging.warning(
                        'Could not get the default Secret Collection.\n'
                        'Attempting to use the session Collection.'
                    )

                    self._current_collection = Secret.COLLECTION_SESSION
                    callback(None)

                elif default_collection.get_locked():
                    logging.debug('The default keyring is locked.')
                    service.unlock(
                        [default_collection],
                        None,
                        on_unlock_finish,
                        (service, default_collection),
                    )

                else:
                    logging.debug('The default keyring is unlocked.')
                    callback(None)

        def on_get_finish(source, result, data):
            try:
                service = Secret.Service.get_finish(result)
            except GLib.Error as e:
                logging.error('Failed to get Secret.Service, Error: {}'.format(e))
                callback(e)
            else:
                Secret.Collection.for_alias(
                    service,
                    Secret.COLLECTION_DEFAULT,
                    Secret.CollectionFlags.NONE,
                    None,
                    on_for_alias_finish,
                    service,
                )

        Secret.Service.get(
            Secret.ServiceFlags.NONE,
            None,
            on_get_finish,
            None,
        )

    def get_account_password(self, email, callback):
        def on_password_lookup_finish(_, result):
            try:
                password = Secret.password_lookup_finish(result) or ''
                callback(password)
            except GLib.Error as e:
                logging.error('Failed to lookup password async, Error: {}'.format(e))
                callback('')

        # The async version of this hangs forever in flatpak and its been broken for years
        # so for now lets just use the sync version as it works.
        if util.is_flatpak():
            try:
                password = Secret.password_lookup_sync(
                    self._account_schema,
                    {'email': email},
                    None,
                ) or ''
                callback(password)
            except GLib.Error as e:
                logging.error('Failed to lookup password sync, Error: {}'.format(e))
                callback('')
            return

        Secret.password_lookup(
            self._account_schema,
            {'email': email},
            None,
            on_password_lookup_finish,
        )

    def set_account_password(self, old_email, new_email, password, callback):
        def on_password_store_finish(source, result, data):
            try:
                success = Secret.password_store_finish(result)
            except GLib.Error as e:
                logging.error('Failed to store password, Error: {}'.format(e))
                success = False
            if callback:
                callback(success)

        def on_password_clear_finish(source, result, data):
            try:
                password_removed = Secret.password_clear_finish(result)
                if password_removed:
                    logging.debug('Cleared password for: {}'.format(old_email))
                else:
                    logging.debug('No password found to clear for: {}'.format(old_email))
            except GLib.Error as e:
                logging.error('Failed to clear password for: {}, Error: {}'.format(old_email, e))
                if callback:
                    callback(False)
            else:
                Secret.password_store(
                    self._account_schema,
                    {'email': new_email},
                    self._current_collection,
                    'Pandora Account',
                    password,
                    None,
                    on_password_store_finish,
                    None,
                )

        if old_email and old_email != new_email:
            Secret.password_clear(
                self._account_schema,
                {'email': old_email},
                None,
                on_password_clear_finish,
                None,
            )

        else:
            Secret.password_store(
                self._account_schema,
                {'email': new_email},
                self._current_collection,
                'Pandora Account',
                password,
                None,
                on_password_store_finish,
                None,
            )


class _WindowsSecretService:
    _SERVICE_NAME = 'io.github.Pithos.Account'

    def __init__(self):
        ...

    def unlock_keyring(self, callback):
        ...

    def get_account_password(self, email, callback):
        ...

    def set_account_password(self, old_email, new_email, password, callback):
        ...


if util.is_msys2():
    SecretService = _WindowsSecretService()
else:
    SecretService = _DefaultSecretService()
