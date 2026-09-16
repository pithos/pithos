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
from .util import is_windows, is_flatpak
from gi.repository import GLib

_SERVICE_NAME = 'io.github.Pithos.Account'
_SERVICE_COMMENT = 'Pandora Account'


if is_windows():
    import pywintypes
    import win32cred
    from .gobject_worker import GObjectWorker


    class _SecretService:
        CRED_TYPE = win32cred.CRED_TYPE_GENERIC
        persist_type = win32cred.CRED_PERSIST_NONE

        def __init__(self):
            self.worker = GObjectWorker()

        def _validate_session(self):
            """This function should call `CredGetSessionTypes`, and validate around the data gathered from it.
            However, as of 6/16/2023, this function is not implemented in pywin32...

            Below is the proper code commented out, and a workaround, which is also denoted.
            https://github.com/mhammond/pywin32/issues/2067
            https://learn.microsoft.com/en-us/windows/win32/api/wincred/nf-wincred-credgetsessiontypes
            """
            if self.persist_type != win32cred.CRED_PERSIST_NONE:
                return

            """
            try:
                self.persist_type = win32cred.CredGetSessionTypes(self.CRED_TYPE)[self.CRED_TYPE]
            except pywintypes.error as e:
                if e.winerror == 1312 and e.funcname == 'CredGetSessionTypes':
                    logging.error('Error with session, {} failed with message: {}'.format(e.funcname, e.strerror)
                else:
                    logging.error('Unknown error while calling {}. [{}], {}'.format(e.funcname, e.winerror, e.strerror)
                raise e

            """

            """To get around this issue in the current state, we attempt to read/write a credential"""
            try:
                test = self._credential_lookup()
                self.persist_type = test['Persist']  # set the persist type to existing type
                self._credential_store(test['UserName'], test['CredentialBlob'].decode('utf-16'))

            except pywintypes.error as e:
                if e.winerror == 1168 and e.funcname == 'CredRead':
                    logging.info('No credential found for {}. {} failed with [{}], {}'
                                 .format(_SERVICE_NAME, e.funcname, e.winerror, e.strerror))
                else:
                    logging.error('Unknown error while calling {}. Failed with [{}], {}'
                                  .format(e.funcname, e.winerror, e.strerror))
                    raise e

            if self.persist_type == win32cred.CRED_PERSIST_NONE:
                persist_check = win32cred.CRED_PERSIST_ENTERPRISE  # largest documented value of 3
                while persist_check > win32cred.CRED_PERSIST_NONE and self.persist_type == win32cred.CRED_PERSIST_NONE:
                    try:
                        self.persist_type = persist_check
                        self._credential_store('', '')
                        self._credential_clear()

                    except pywintypes.error as e:
                        # MSDN doesn't document what occurs when attempting to call the write function when using a
                        # persist_type that has been disabled. Therefore, we brute-force calls here.
                        self.persist_type = win32cred.CRED_PERSIST_NONE
                        logging.debug('Persist value check with: {} failed.\
                                       {} failed with [{}], {}'.format(persist_check, e.funcname, e.winerror,
                                                                       e.strerror))
                        persist_check -= 1
            """End work-around"""

            if self.persist_type == win32cred.CRED_PERSIST_NONE:
                logging.error('Generic credential storing has been disabled by your administrator.\
                              Pithos requires this to run.')
                raise RuntimeError('Credential Persistence is CRED_PERSIST_NONE.')

            if self.persist_type == win32cred.CRED_PERSIST_SESSION:
                logging.warning('Generic credentials have been set to per session persistence via group policy.\
                                You will need to re-enter your login info each time pithos is launched')

            logging.info("Targeting persist: {}".format(self.persist_type))
            return

        def _credential_clear(self):
            win32cred.CredDelete(TargetName=_SERVICE_NAME,
                                 Type=win32cred.CRED_TYPE_GENERIC)
            return

        def _credential_lookup(self):
            credential = win32cred.CredRead(TargetName=_SERVICE_NAME,
                                            Type=win32cred.CRED_TYPE_GENERIC)
            return credential  # https://mhammond.github.io/pywin32/PyCREDENTIAL.html

        def _credential_store(self, new_email, password):
            credential = {'Type': win32cred.CRED_TYPE_GENERIC,
                          'TargetName': _SERVICE_NAME,
                          'Comment': _SERVICE_COMMENT,
                          'CredentialBlob': password,
                          'Persist': self.persist_type,
                          'UserName': new_email
                          }
            win32cred.CredWrite(credential, 0)
            return

        @staticmethod
        def _async_call_wrapper(command, *args):
            """Helper function to wrap win32 api functions to a Secrets-esque calling format"""
            try:
                result = command(*args)
            except Exception as e:
                result = e

            return result

        def unlock_keyring(self, callback):
            """Checks that the current logon session has a credential set, and that credentials can be stored"""
            def on_unlock_finish(result):
                if not isinstance(result, Exception):
                    result = None

                if callback:
                    callback(result)

            self.worker.send(self._async_call_wrapper, (self._validate_session,), on_unlock_finish)

        def get_account_password(self, email, callback):
            def on_password_lookup_finish(result):
                password = ''
                if not isinstance(result, Exception):
                    password = result['CredentialBlob'].decode('utf-16')

                if callback:
                    callback(password)

            self.worker.send(self._async_call_wrapper, (self._credential_lookup,), on_password_lookup_finish)

        def set_account_password(self, old_email, new_email, password, callback):
            def on_password_store_finish(result):
                success = not isinstance(result, Exception)
                if callback:
                    callback(success)

            self.worker.send(self._async_call_wrapper, (self._credential_store, new_email, password), on_password_store_finish)


else:
    import gi
    gi.require_version('Secret', '1')
    from gi.repository import Secret


    class _SecretService:

        _account_schema = Secret.Schema.new(
            _SERVICE_NAME,
            Secret.SchemaFlags.NONE,
            {'email': Secret.SchemaAttributeType.STRING},
        )

        def __init__(self):
            self._current_collection = Secret.COLLECTION_DEFAULT

        def unlock_keyring(self, callback):
            # Inside of flatpak we only have access to the simple API.
            if is_flatpak():
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
            if is_flatpak():
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
                        _SERVICE_COMMENT,
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
                    _SERVICE_COMMENT,
                    password,
                    None,
                    on_password_store_finish,
                    None,
                )

SecretService = _SecretService()
