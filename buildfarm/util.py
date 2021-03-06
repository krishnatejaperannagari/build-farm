#!/usr/bin/python
# utility functions to support the build farm
# Copyright (C) tridge@samba.org, 2001
# Copyright (C) Jelmer Vernooij <jelmer@samba.org> 2010
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 2 of the License, or
#   (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU General Public License for more details.
#
#   You should have received a copy of the GNU General Public License
#   along with this program; if not, write to the Free Software
#   Foundation, Inc., 675 Mass Ave, Cambridge, MA 02139, USA.

import re
import os

def load_list(fname):
    """load a list from a file, using : to separate"""
    ret = []
    f = open(fname, 'r')
    try:
        for l in f.readlines():
            if l[0] != "#":
                l = l.strip('\r\n')
                if len(l) > 0:
                    ret.append(l)
    finally:
        f.close()
    return ret


def FileLoad(filename):
    """read a file into a string"""
    f = open(filename, 'r')
    try:
        return f.read()
    finally:
        f.close()

def SambaWebFileLoad(webdir, filename):
    """loads file and changes the links to suit buildfarm"""
    try:
        f = open(os.path.join(webdir, filename), 'r')
        text = f.read()
    except IOError:
        return ''
    else:
        f.close()
    def add_virtual_headers(m):
        try:
            f = open(os.path.join(webdir, m.group(1)), 'r')
            text = f.read()
        except:
            return ''
        else:
            f.close()
            return text
    text = re.sub('<!--#include virtual="/samba/(.*)" -->',add_virtual_headers , text)
    text = re.sub('href="/samba', 'href="http://www.samba.org/samba', text)
    return text

def dhm_time(sec):
    """display a time as days, hours, minutes"""
    days = int(sec / (60*60*24));
    hour = int(sec / (60*60)) % 24;
    min = int(sec / 60) % 60;

    if sec < 0:
        return "-"

    if days != 0:
        return "%dd %dh %dm" % (days, hour, min)
    if hour != 0:
        return "%dh %dm" % (hour, min)
    if min != 0:
        return "%dm" % min
    return "%ds" % sec
