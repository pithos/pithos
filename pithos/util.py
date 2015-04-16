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

from functools import wraps
from gi.repository import GLib, Gdk
from urllib.parse import splittype, splituser, splitpasswd
import importlib
import logging
import os
import pkgutil
import webbrowser

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
            os.wait()  # workaround for http://bugs.python.org/issue5993
        except:
            pass


class PeriodicCallback:
    def __init__(self, name, cb_func, period, seconds_ok=False,
                 use_glib=False):
        self._name = name
        self._cb_func = cb_func
        self._period = period
        self._current_period = period
        self._seconds_ok = seconds_ok
        self._use_glib = use_glib

        self._pcb_id = None
        self._running = False

    def _schedule(self):
        seconds = self._current_period % 1000 == 0 and self._seconds_ok

        if self._use_glib:
            if seconds:
                self._pcb_id = GLib.timeout_add_seconds(
                    self._current_period//1000, self._pcb_func)
            else:
                self._pcb_id = GLib.timeout_add(
                    self._current_period, self._pcb_func)
        else:
            if seconds:
                self._pcb_id = Gdk.threads_add_timeout_seconds(
                    GLib.PRIORITY_DEFAULT, self._current_period//1000,
                    self._pcb_func)
            else:
                self._pcb_id = Gdk.threads_add_timeout(
                    GLib.PRIORITY_DEFAULT, self._current_period,
                    self._pcb_func)

    def _cancel_pcb(self):
        if self._pcb_id is not None:
            ret = GLib.source_remove(self._pcb_id)
            self._log("Removing existing callback ID: %s, returned %s",
                      self._pcb_id, ret)
            self._pcb_id = None
        else:
            self._log("No existing callback to cancel...")

    def start(self):
        if self._running:
            self._log("Callback already running, doing nothing.")
            return True
        self._running = True
        self._cancel_pcb()
        self._current_period = self._period
        self._schedule()
        self._log("Started new callback ID: %s", self._pcb_id)

    def stop(self):
        self._cancel_pcb()
        self._running = False

    def _pcb_func(self):
        if self._running:
            cb_ret = self._cb_func()
            self._running = bool(cb_ret)

        if type(cb_ret) is int and cb_ret != self._current_period:
            self._log("Callback wants to be rescheduled with a period of %s "
                      "(previous period was %s)", cb_ret, self._current_period)
            self._current_period = cb_ret
            self._schedule()
            self._log("Added callback ID: %s", self._pcb_id)
            # Autoremove ourselves
            return False

        if not self._running:
            self._log("Callback returned False, callbacks will be stopped.")
            # GLib will remove the callback when we return False
            self._pcb_id = None

        return self._running

    def _log(self, msg, *args):
        logging.debug("PeriodicCallback %s<%s>: {}".format(msg),
                      self._name, self._pcb_id, *args)


def ignore_source(fn):
    """Wraps a function with one that ignores the first argument.

    This is useful when connecting to signals with existing functions that do
    not expect and argument for the event source.
    """
    @wraps(fn)
    def source_remover(src, *args, **kwargs):
        return fn(*args, **kwargs)
    return source_remover


def import_all (pkg):
    if isinstance(pkg, str):
        pkg = importlib.import_module(pkg)
    logging.debug("Importing all modules in package %s", pkg.__name__)
    modules = []
    for _, name, _ in pkgutil.iter_modules(pkg.__path__, pkg.__name__ + '.'):
        logging.debug("Found module: %s", name)
        try:
            modules.append(importlib.import_module(name))
        except Exception:
            logging.debug("Unable to import module %s", name,
                          exc_info=True)
    return modules


def find_subclasses (pkg, BaseClass):
    import_all(pkg)
    return {Subclass.__qualname__: Subclass
            for Subclass in BaseClass.__subclasses__()}
