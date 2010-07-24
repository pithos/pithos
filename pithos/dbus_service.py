import dbus.service

DBUS_BUS = "net.kevinmehall.Pithos"
DBUS_OBJECT_PATH = "/net/kevinmehall/Pithos"
  
class PithosDBusProxy(dbus.service.Object):
    def __init__(self, window):
        self.bus = dbus.SessionBus()
        bus_name = dbus.service.BusName(DBUS_BUS, bus=self.bus)
        dbus.service.Object.__init__(self, bus_name, DBUS_OBJECT_PATH)
        self.window = window
        self.window.connect("song-changed", self.songchange_handler)
        self.window.connect("play-state-changed", self.playstate_handler)
        
    def playstate_handler(self, window, state):
    	self.PlayStateChanged(state)
    	
    def songchange_handler(self, window, song):
    	d = {}
    	for i in ['artist', 'title', 'album', 'songDetailURL']:
    		d[i] = getattr(song, i)
    	self.SongChanged(d)
    
    @dbus.service.method(DBUS_BUS)
    def PlayPause(self):
        self.window.playpause()
    
    @dbus.service.method(DBUS_BUS)
    def SkipSong(self):
        self.window.next_song()
    
    @dbus.service.method(DBUS_BUS)
    def LoveCurrentSong(self):
        self.window.love_song()
    
    @dbus.service.method(DBUS_BUS)
    def BanCurrentSong(self):
        self.window.ban_song()
    
    @dbus.service.method(DBUS_BUS)
    def TiredCurrentSong(self):
        self.window.tired_song()
        
    @dbus.service.signal(DBUS_BUS, signature='b')
    def PlayStateChanged(self, state):
    	pass
    	
    @dbus.service.signal(DBUS_BUS, signature='a{sv}')
    def SongChanged(self, songinfo):
    	pass	
   	
