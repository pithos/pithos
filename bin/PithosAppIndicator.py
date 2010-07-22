import appindicator
import os
import sys
import gtk

# Check if we are working in the source tree or from the installed 
# package and mangle the python path accordingly
if os.path.dirname(sys.argv[0]) != ".":
    if sys.argv[0][0] == "/":
        fullPath = os.path.dirname(sys.argv[0])
    else:
        fullPath = os.getcwd() + "/" + os.path.dirname(sys.argv[0])
else:
    fullPath = os.getcwd()
sys.path.insert(0, os.path.dirname(fullPath))

from pithos import AboutPithosDialog, PreferencesPithosDialog, StationsDialog
from pithos.pithosconfig import getdatapath, getmediapath
from pithos.gobject_worker import GObjectWorker

class PithosAppIndicator:
	def __init__(self,window):
		# App Indicator
		self.ind = appindicator.Indicator("example-simple-client","pithos-mono",appindicator.CATEGORY_APPLICATION_STATUS,getmediapath())
		self.ind.set_status (appindicator.STATUS_ACTIVE)

		# create a menu
		menu = gtk.Menu()

		# Play/Pause menu item
		PlayPauseMenuItem = gtk.ImageMenuItem("Play/Pause")
		PlayPauseMenuItem.connect("activate",window.playpause)
		PlayPauseMenuItem.show()

		skipMenuItem = gtk.MenuItem("Skip")
		skipMenuItem.connect("activate",window.next_song)
		skipMenuItem.show();

		showhideMenuItem = gtk.MenuItem("Show/Hide")
		showhideMenuItem.connect("activate",window.showhide)
		showhideMenuItem.show();

		quitMenuItem = gtk.MenuItem("Quit")
		quitMenuItem.connect("activate",window.quit)
		quitMenuItem.show()
		
		menu.append(PlayPauseMenuItem)
		menu.append(skipMenuItem)
		menu.append(showhideMenuItem)
		menu.append(quitMenuItem)

		# this is where you would connect your menu item up with a function:
		
		# menu_items.connect("activate", self.menuitem_response, buf)

		# show the items
		
		self.ind.set_menu(menu)
