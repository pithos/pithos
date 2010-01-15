# -*- coding: utf-8 -*-
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

import time

counter = 0
def count():
	global counter
	counter +=1
	return counter

class PianoPandora(object):
	def __init__(self):
		self.stations = [
			PianoStation("Fake 1"),
			PianoStation("Fake 2"),
			PianoStation("Fake 3"),
			PianoStation("QuickMix", 1),
		]
		
	def connect(self, user, password):
		print "logging in with", user, password
		time.sleep(1)

		
	def get_playlist(self, station):
		r = [PianoSong("Test  &song %i"%count(), "Test Artist", "Album %s"%station.name, i%3-1) for i in range(4)]		
		time.sleep(1)
		return r
		
		
		

		
class PianoStation(object):
	def __init__(self, name, qm=False):
		self.id = id(self)
		self.isCreator = True
		self.isQuickMix = qm
		self.name = name
		self.useQuickMix = True
		
class PianoSong(object):
	def __init__(self, title, artist, album, rating):
		self.id=id(self)
		self.album = album
		self.artist = artist
		self.audioUrl = 'file:///home/km/Downloads/download'
		self.title = title
		self.rating = rating
		self.tired=False
		
		
	


