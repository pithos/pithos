# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010-2012 Kevin Mehall <km@kevinmehall.net>
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
### END LICENSE

import os
import logging
import webbrowser
from urllib.parse import splittype, splituser, splitpasswd

import gi
gi.require_version('Secret', '1')
from gi.repository import Secret

_ACCOUNT_SCHEMA = Secret.Schema.new('io.github.Pithos.Account', Secret.SchemaFlags.NONE, 
                                    {"email": Secret.SchemaAttributeType.STRING})

# TODO: Async
def get_account_password(email):
    return Secret.password_lookup_sync(_ACCOUNT_SCHEMA, {"email": email}, None) or ''

def set_account_password(email, password):
    attrs = {"email": email}
    if password:
        Secret.password_store_sync(_ACCOUNT_SCHEMA, attrs, Secret.COLLECTION_DEFAULT,
                                    "Pandora Account", password, None)
    else:
        Secret.password_clear_sync(_ACCOUNT_SCHEMA, attrs, None)

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

def open_browser(url):
    logging.info("Opening URL {}".format(url))
    webbrowser.open(url)
    if isinstance(webbrowser.get(), webbrowser.BackgroundBrowser):
        try:
            os.wait() # workaround for http://bugs.python.org/issue5993
        except os.ChildProcessError:
            pass
