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
import logging

RATE_BAN = piano.PIANO_RATE_BAN
RATE_LOVE = piano.PIANO_RATE_LOVE

def linkedList(head):
	out = []
	while head:
		out.append(head)
		head=head.next
	return out

class PianoError(IOError): pass
class PianoAuthTokenInvalid(PianoError): pass
class PianoUserPasswordInvalid(PianoError): pass

def pianoCheck(status):
	ret = None
	if type(status) == tuple:
		ret = status[1]
		status = status[0]
	if status!=0:
		s=piano.PianoErrorToStr(status)
		logging.error("libpiano: error: %s"%(s))
		if status == piano.PIANO_RET_AUTH_TOKEN_INVALID:
			raise PianoAuthTokenInvalid(s)
		elif status == piano.PIANO_RET_AUTH_USER_PASSWORD_INVALID:
			raise PianoUserPasswordInvalid(s)
		else:
			raise PianoError(s)
	return ret

class PianoPandora(object):
	def connect(self, user, password):
		self.p = piano.PianoHandle_t()
		piano.PianoInit(self.p)
		logging.debug("libpiano: Connecting")
		pianoCheck(piano.PianoConnect(self.p, user, password))
		logging.debug("libpiano: Get Stations")
		pianoCheck(piano.PianoGetStations(self.p))
		self.stations = [PianoStation(self, x) for x in linkedList(self.p.stations)]
		logging.debug("libpiano: found %i stations"%(len(self.stations)))
		self.stations_dict = {}
		for i in self.stations:
			self.stations_dict[i.id] = i
		
	def get_playlist(self, station):
		logging.debug("libpiano: Get Playlist")
		l = pianoCheck(piano.PianoGetPlaylist(self.p, station.id, piano.PIANO_AF_AACPLUS))
		r = [PianoSong(self, x) for x in linkedList(l)]
		return r
		
		

		
class PianoStation(object):
	def __init__(self, piano, c_obj):
		self._c_obj = c_obj
		self.piano = piano
		
		self.id = c_obj.id
		self.idToken = c_obj.idToken
		self.isCreator = c_obj.isCreator
		self.isQuickMix = c_obj.isQuickMix
		self.name = c_obj.name
		self.useQuickMix = c_obj.useQuickMix
	
	def transformIfShared(self):
		if not self.isCreator:
			logging.debug("libpiano: transforming station")
			pianoCheck(piano.PianoTransformShared(self.piano.p, self._c_obj))
			self.isCreator = True
			
	@property
	def info_url(self):
		return 'http://www.pandora.com/stations/'+self.idToken
		
class PianoSong(object):
	def __init__(self, piano, c_obj):
		self._c_obj = c_obj
		self.piano = piano
		
		self.album = c_obj.album
		self.artist = c_obj.artist
		self.audioFormat = c_obj.audioFormat
		self.audioUrl = c_obj.audioUrl
		self.fileGain = c_obj.fileGain
		self.focusTraiId = c_obj.focusTraitId
		self.identity = c_obj.identity
		self.matchingSeed = c_obj.matchingSeed
		self.musicId = c_obj.musicId
		self.rating = c_obj.rating
		self.stationId = c_obj.stationId
		self.title = c_obj.title
		self.userSeed = c_obj.userSeed
		self.songDetailURL = c_obj.songDetailURL
		self.artRadio = c_obj.artRadio
		self.tired=False
		
	@property
	def station(self):
		return self.piano.stations_dict[self.stationId]
	
	def rate(self, rating):
		if self.rating != rating:
			self.station.transformIfShared()
			pianoCheck(piano.PianoRateTrack(self.piano.p, self._c_obj, rating))
			self.rating = rating
		
	def set_tired(self):
		if not self.tired:
			pianoCheck(piano.PianoSongTired(self.piano.p, self._c_obj))
			self.tired = True
		
		
	


