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
import os, os.path


def update_data_path(build_dir, prefix, oldvalue=None):

    try:
        fin = file(os.path.join(build_dir, 'pithos/pithosconfig.py'), 'r')
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


class InstallAndUpdateDataDirectory(DistUtilsExtra.auto.install_auto):
    def initialize_options(self):
        self.build_base = None
        self.build_lib = None
        DistUtilsExtra.auto.install_auto.initialize_options(self)

    def finalize_options(self):
        self.set_undefined_options('build',
            ('build_lib', 'build_lib'))
        DistUtilsExtra.auto.install_auto.finalize_options(self)

    def run(self):
        if self.root or self.home:
            print "WARNING: You don't use a standard --prefix installation, take care that you eventually " \
            "need to update quickly/quicklyconfig.py file to adjust __quickly_data_directory__. You can " \
            "ignore this warning if you are packaging and uses --prefix."
        previous_value = update_data_path(self.build_lib, self.prefix + '/share/pithos/')
        DistUtilsExtra.auto.install_auto.run(self)
        update_data_path(self.build_lib, self.prefix, previous_value)

from distutils.cmd import Command    
class OverrideI18NCommand(Command):
	def initialize_options(self): pass
	def finalize_options(self): pass
	def run(self):
		self.distribution.data_files.append(('share/applications', ['pithos.desktop']))

from DistUtilsExtra.command.build_extra import build_extra
from DistUtilsExtra.command.build_icons import build_icons

DistUtilsExtra.auto.setup(
    name='pithos',
    version='0.3',
    ext_modules=[],
    license='GPL-3',
    author='Kevin Mehall',
    author_email='km@kevinmehall.net',
    description='Pandora.com client for the GNOME desktop',
    #long_description='Here a longer description',
    url='https://launchpad.net/pithos',
    cmdclass={'install': InstallAndUpdateDataDirectory, 'build_icons':build_icons, 'build':build_extra, 'build_i18n':OverrideI18NCommand}
    )

