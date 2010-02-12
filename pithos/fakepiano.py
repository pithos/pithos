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

import time
import logging

RATE_BAN = 0
RATE_LOVE = 1

counter = 0
def count():
    global counter
    counter +=1
    return counter

class PianoError(IOError): pass
class PianoAuthTokenInvalid(PianoError): pass
class PianoUserPasswordInvalid(PianoError): pass

class PianoPandora(object):
    def __init__(self):
        self.stations = [
            PianoStation("Fake 1"),
            PianoStation("Fake 2"),
            PianoStation("Fake 3"),
            PianoStation("Errors"),
            PianoStation("QuickMix", 1),
        ]
        self.authError = False
        
    def connect(self, user, password, proxy):
        logging.debug("fakepiano: logging in")
        if proxy:
            logging.debug("fakepiano: using proxy %s"%proxy)
        time.sleep(1)
        
    def get_playlist(self, station):
        if station.name=='Errors':
            if self.authError:
                self.authError=False
                raise PianoAuthTokenInvalid("Invalid Auth Token")
            else:
                self.authError = True
        r = [PianoSong("Test  &song %i"%count(), "Test Artist", "Album %s"%station.name, i%3-1) for i in range(4)]        
        time.sleep(1)
        return r
        
        
        

        
class PianoStation(object):
    def __init__(self, name, qm=False):
        self.id = str(hash(name))
        self.isCreator = True
        self.isQuickMix = qm
        self.name = name
        self.useQuickMix = True
        self.info_url = 'http://launchpad.net/pithos'
        
class PianoSong(object):
    def __init__(self, title, artist, album, rating):
        self.id=id(self)
        self.album = album
        self.artist = artist
        self.audioUrl = 'file:///home/km/Downloads/download'
        self.title = title
        self.rating = rating
        self.tired=False
        self.songDetailURL = 'http://launchpad.net/pithos'
        self.artRadio = 'http://i.imgur.com/H3Z8x.jpg'
        
    def rate(self, rating):
        time.sleep(1)
        print "rating song", self.title, rating
        self.rating = rating
            
    def set_tired(self):
        time.sleep(1)
        print "tired", self.title
        self.tired = True
        
        
        
    


