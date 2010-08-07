#!/usr/bin/python
# -*- coding: utf-8; tab-width: 4; indent-tabs-mode: nil; -*-
### BEGIN LICENSE
# Copyright (C) 2010 Kevin Mehall <km@kevinmehall.net>
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

import logging

class PithosPlugin(object):
    _PITHOS_PLUGIN = True # used to find the plugin class in a module
	def __init__(self, name, window):
	    self.name = name
		self.window = window
		self.prepared = False
		self.enabled = False
		
	def enable(self):
		if not self.prepared:
			self.error = self.on_prepare()
			self.prepared = True
		if not self.error and not self.enabled:
		    logging.debug("Enabling module %s"%(self.name))
			self.on_enable()
			self.enabled = True
			
	def disable(self):
		if self.enabled:
		    logging.debug("Disabling module %s"%(self.name))
			self.on_disable()
			self.enabled = False
		
	def on_prepare(self):
		pass
		
	def on_enable(self):
		pass
		
	def on_disable(self):
		pass

class ErrorPlugin(PithosPlugin):
	def __init__(self, name, error):
		logging.error("Error loading plugin %s: %s"%(name, error))
		self.prepared = True
		self.error = error
		self.name = name
		self.enabled = False
		
def load_plugin(name, window):
	try:
		module = __import__('pithos.'+name)
		module = getattr(module, name)
		
	except ImportError as e:
		return ErrorPlugin(name, e.message)
		
	# find the class object for the actual plugin
	for key, item in module.__dict__.iteritems():
		if hasattr(item, '_PITHOS_PLUGIN'):
			plugin_class = item
			break
	else:
		return ErrorPlugin(name, "Could not find module class")
		
	return plugin_class(name, window)

def load_plugins(window, definedPlugins):
    plugins = window.plugins
    prefs = window.preferences
	for name in definedPlugins:
		if not name in plugins:
			plugin = plugins[name] = load_plugin(name, window)
	    else:
	        plugin = plugins[name]

		if prefs[definedPlugins[name]]:
			plugin.enable()
		else:
			plugin.disable()
		
