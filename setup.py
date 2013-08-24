
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
    from setuptools import setup, find_packages
except ImportError:
    import ez_setup
    ez_setup.use_setuptools()
    from setuptools import setup, find_packages

import os

# Utility function to read the README file.
# Used for the long_description.  It's nice, because now 1) we have a top level
# README file and 2) it's easier to type in the README file than to put a raw
# string in below ...
def read(fname):
    return open(os.path.join(os.path.dirname(__file__), fname)).read()

data_files = [
    ('share/icons/hicolor/scalable/apps', [
         'data/icons/scalable/apps/pithos-mono.svg',
         'data/icons/scalable/apps/pithos.svg'
     ]),
    ('share/applications', ['pithos.desktop'])
]
for data_dir in ['data/ui', 'data/media']:
    data_files.append((
        data_dir,
        ['%s/%s' % (data_dir, f) for f in os.listdir(data_dir)]
    ))

setup(
    name='pithos',
    version='0.3',
    ext_modules=[],
    license='GPL-3',
    author='Kevin Mehall',
    author_email='km@kevinmehall.net',
    description='Pandora.com client for the GNOME desktop',
    long_description=read('README.md'),
    url='https://launchpad.net/pithos',
    classifiers=[
        'Development Status :: 4 - Beta',
        'Intended Audience :: End Users/Desktop',
        'Topic :: Media',
        'License :: OSI Approved :: GPL License',
        'Programming Language :: Python'
    ],
    data_files=data_files,
    package_data={
        'pithos': [
            'data/ui/*.ui',
            'data/ui/*.xml',
            'data/media/*.png',
            'data/media/*.svg',
            'data/icons/scalable/apps/*.svg'
        ]
    },
    packages=find_packages(),
    namespace_packages=['pithos', 'pithos.plugins', 'pithos.pandora'],
    entry_points={
        'gui_scripts': ['pithos = pithos.pithos:main']
    }
)
