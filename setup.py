#!/usr/bin/env python
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

###################### DO NOT TOUCH THIS (HEAD TO THE SECOND PART) ######################

try:
    import DistUtilsExtra.auto
except ImportError:
    import sys
    print >> sys.stderr, 'To build pithos you need https://launchpad.net/python-distutils-extra'
    sys.exit(1)

assert DistUtilsExtra.auto.__version__ >= '2.10', 'needs DistUtilsExtra.auto >= 2.10'
import os


def update_data_path(prefix, oldvalue=None):

    try:
        fin = file('pithos/pithosconfig.py', 'r')
        fout = file(fin.name + '.new', 'w')

        for line in fin:            
            fields = line.split(' = ') # Separate variable from value
            if fields[0] == '__pithos_data_directory__':
                # update to prefix, store oldvalue
                if not oldvalue:
                    oldvalue = fields[1]
                    line = "%s = '%s'\n" % (fields[0], prefix)
                else: # restore oldvalue
                    line = "%s = %s" % (fields[0], oldvalue)
            fout.write(line)

        fout.flush()
        fout.close()
        fin.close()
        os.rename(fout.name, fin.name)
    except (OSError, IOError), e:
        print ("ERROR: Can't find pithos/pithosconfig.py")
        sys.exit(1)
    return oldvalue


def update_desktop_file(datadir):

    try:
        fin = file('pithos.desktop.in', 'r')
        fout = file(fin.name + '.new', 'w')

        for line in fin:            
            if 'Icon=' in line:
                line = "Icon=%s\n" % (datadir + 'media/icon.png')
            fout.write(line)
        fout.flush()
        fout.close()
        fin.close()
        os.rename(fout.name, fin.name)
    except (OSError, IOError), e:
        print ("ERROR: Can't find pithos.desktop.in")
        sys.exit(1)


class InstallAndUpdateDataDirectory(DistUtilsExtra.auto.install_auto):
    def run(self):
        if self.root or self.home:
            print "WARNING: You don't use a standard --prefix installation, take care that you eventually " \
            "need to update quickly/quicklyconfig.py file to adjust __quickly_data_directory__. You can " \
            "ignore this warning if you are packaging and uses --prefix."
        previous_value = update_data_path(self.prefix + '/share/pithos/')
        update_desktop_file(self.prefix + '/share/pithos/')
        DistUtilsExtra.auto.install_auto.run(self)
        update_data_path(self.prefix, previous_value)


        
##################################################################################
###################### YOU SHOULD MODIFY ONLY WHAT IS BELOW ######################
##################################################################################
from distutils.core import Extension

libpiano = Extension('pithos.libpiano._piano', [
	    	'pithos/libpiano/piano.i',
	    	'pithos/libpiano/piano.c',
	    	'pithos/libpiano/crypt.c',
	    	'pithos/libpiano/http.c',
	    	'pithos/libpiano/xml.c',
	    	'pithos/libpiano/ezxml.c',
	    	'pithos/libpiano/waitress.c'
    	],
        swig_opts=['-threads'],
        include_dirs=['pithos/libpiano/']
)

DistUtilsExtra.auto.setup(
    name='pithos',
    version='0.1-public6',
    ext_modules=[libpiano],
    license='GPL-3',
    author='Kevin Mehall',
    author_email='km@kevinmehall.net',
    description='Pandora.com client for the GNOME desktop',
    #long_description='Here a longer description',
    url='https://launchpad.net/pithos',
    cmdclass={'install': InstallAndUpdateDataDirectory}
    )

