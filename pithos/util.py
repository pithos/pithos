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
from urllib.parse import splittype, splituser, splitpasswd

import gi
gi.require_version('Secret', '1')
from gi.repository import (
    GLib,
    Secret,
    Gtk
)

_ACCOUNT_SCHEMA = Secret.Schema.new('io.github.Pithos.Account', Secret.SchemaFlags.NONE,
                                    {"email": Secret.SchemaAttributeType.STRING})

_current_collection = Secret.COLLECTION_DEFAULT


# TODO: Async
def unlock_keyring():
    service = Secret.Service.get_sync(
        Secret.ServiceFlags.NONE,
        None,
    )

    default_collection = Secret.Collection.for_alias_sync(
        service,
        Secret.COLLECTION_DEFAULT,
        Secret.CollectionFlags.NONE,
        None,
    )

    if default_collection is None:
        logging.warning(
            'Could not get the default Secret Collection.\n'
            'Attempting to use the session Collection.'
        )

        global _current_collection
        _current_collection = Secret.COLLECTION_SESSION
        return

    if not default_collection.get_locked():
        logging.debug('The default keyring is unlocked.')
    else:
        num_items, unlocked = service.unlock_sync(
            [default_collection],
            None,
        )

        if not num_items or default_collection not in unlocked:
            global _current_collection
            _current_collection = Secret.COLLECTION_SESSION
            logging.debug('The default keyring is locked. Using session collection.')
        else:
            logging.debug('The default keyring was unlocked.')

def get_account_password(email):
    return Secret.password_lookup_sync(_ACCOUNT_SCHEMA, {"email": email}, None) or ''


def _clear_account_password(email):
    return Secret.password_clear_sync(_ACCOUNT_SCHEMA, {"email": email}, None)


def set_account_password(email, password, previous_email=None):
    if previous_email and previous_email != email:
        if not _clear_account_password(previous_email):
            logging.warning('Failed to clear previous account')

    if not password:
        return _clear_account_password(email)

    attrs = {"email": email}
    if password == get_account_password(email):
        logging.debug('Password unchanged')
        return False

    Secret.password_store_sync(_ACCOUNT_SCHEMA, attrs, _current_collection,
                               "Pandora Account", password, None)
    return True


def parse_proxy(proxy):
    """ _parse_proxy from urllib """
    scheme, r_scheme = splittype(proxy)
    if not r_scheme.startswith("/"):
        # authority
        scheme = None
        authority = proxy
    else:
        # URL
        if not r_scheme.startswith("//"):
            raise ValueError("proxy URL with no authority: %r" % proxy)
        # We have an authority, so for RFC 3986-compliant URLs (by ss 3.
        # and 3.3.), path is empty or starts with '/'
        end = r_scheme.find("/", 2)
        if end == -1:
            end = None
        authority = r_scheme[2:end]
    userinfo, hostport = splituser(authority)
    if userinfo is not None:
        user, password = splitpasswd(userinfo)
    else:
        user = password = None
    return scheme, user, password, hostport


def open_browser(url, parent=None, timestamp=0):
    logging.info("Opening URL {}".format(url))
    if not timestamp:
        timestamp = Gtk.get_current_event_time()
    try:
        if hasattr(Gtk, 'show_uri_on_window'):
            Gtk.show_uri_on_window(parent, url, timestamp)
        else: # Gtk <= 3.20
            screen = None
            if parent:
                screen = parent.get_screen()
            Gtk.show_uri(screen, url, timestamp)
    except GLib.Error as e:
        logging.warning('Failed to open URL: {}'.format(e.message))

if hasattr(Gtk.Menu, 'popup_at_pointer'):
    popup_at_pointer = Gtk.Menu.popup_at_pointer
else:
    popup_at_pointer = lambda menu, event: menu.popup(None, None, None, None, event.button, event.time)

