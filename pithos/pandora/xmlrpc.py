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

from cgi import escape

def xmlrpc_value(v):
    if isinstance(v, str):
        return "<value><string>%s</string></value>"%escape(v)
    elif v is True:
        return "<value><boolean>1</boolean></value>"
    elif v is False:
        return "<value><boolean>0</boolean></value>"
    elif isinstance(v, int) or isinstance(v, long):
        return "<value><int>%i</int></value>"%v
    elif isinstance(v, list):
        return "<value><array><data>%s</data></array></value>"%("".join([xmlrpc_value(i) for i in v]))
    else:
        raise ValueError("Can't encode %s of type %s to XMLRPC"%(v, type(v)))
        
def xmlrpc_make_call(method, args):
    args = "".join(["<param>%s</param>"%xmlrpc_value(i) for i in args])
    return "<?xml version=\"1.0\"?><methodCall><methodName>%s</methodName><params>%s</params></methodCall>"%(method, args)

def xmlrpc_parse_value(tree):
    b = tree.findtext('boolean')
    if b is not None:
        return bool(int(b))
    i = tree.findtext('int')
    if i is not None:
        return int(i)
    a = tree.find('array')
    if a is not None:
        return xmlrpc_parse_array(a)
    s = tree.find('struct')
    if s is not None:
        return xmlrpc_parse_struct(s)
    return tree.text
 
def xmlrpc_parse_struct(tree):
    d = {}
    for member in tree.findall('member'):
        name = member.findtext('name')
        d[name] = xmlrpc_parse_value(member.find('value'))
    return d
    
def xmlrpc_parse_array(tree):
    return [xmlrpc_parse_value(item) for item in tree.findall('data/value')]

def xmlrpc_parse(tree):
    return xmlrpc_parse_value(tree.find('params/param/value'))
