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

import piano

def linkedList(head):
	out = []
	while head:
		out.append(head)
		head=head.next
	return out

def pianoCheck(status):
	ret = None
	if type(status) == tuple:
		ret = status[1]
		status = status[0]
	if status!=0:
		raise IOError(piano.PianoErrorToStr(status))
	return ret

class PianoPandora(object):
	def connect(self, user, password):
		self.p = piano.PianoHandle_t()
		piano.PianoInit(self.p)
		pianoCheck(piano.PianoConnect(self.p, user, password))
		pianoCheck(piano.PianoGetStations(self.p))
		self.stations = [PianoStation(x) for x in linkedList(self.p.stations)]
		

		
	def get_playlist(self, station):
		l = pianoCheck(piano.PianoGetPlaylist(self.p, station.id, piano.PIANO_AF_AACPLUS))
		r = [PianoSong(x) for x in linkedList(l)]
		print [i.title for i in r]
		#piano.PianoDestroyPlaylist(l)
		return r
		
		

		
class PianoStation(object):
	def __init__(self, proxy):
		self.id = proxy.id
		self.isCreator = proxy.isCreator
		self.isQuickMix = proxy.isQuickMix
		self.name = proxy.name
		self.useQuickMix = proxy.useQuickMix
		
class PianoSong(object):
	def __init__(self, proxy):
		self.album = proxy.album
		self.artist = proxy.artist
		self.audioFormat = proxy.audioFormat
		self.audioUrl = proxy.audioUrl
		self.fileGain = proxy.fileGain
		self.focusTraiId = proxy.focusTraitId
		self.identity = proxy.identity
		self.matchingSeed = proxy.matchingSeed
		self.musicId = proxy.musicId
		self.rating = proxy.rating
		self.stationId = proxy.stationId
		self.title = proxy.title
		self.userSeed = proxy.userSeed
		
		
	


