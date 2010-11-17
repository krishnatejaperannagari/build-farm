#!/usr/bin/python

# Samba.org buildfarm
# Copyright (C) 2008 Andrew Bartlett <abartlet@samba.org>
# Copyright (C) 2008-2010 Jelmer Vernooij <jelmer@samba.org>
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License as published by
# the Free Software Foundation; either version 3 of the License, or
# (at your option) any later version.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License
# along with this program.  If not, see <http://www.gnu.org/licenses/>.
#

import time


class HostAlreadyExists(Exception):
    """The specified host already exists."""

    def __init__(self, name):
        super(HostAlreadyExists, self).__init__()
        self.name = name


class NoSuchHost(Exception):
    """The specified host did not exist."""

    def __init__(self, name):
        super(NoSuchHost, self).__init__()
        self.name = name


class Host(object):
    """A host in the buildfarm."""

    def __init__(self, name, owner=None, owner_email=None, password=None, platform=None,
                 ssh_access=False, last_update=None, fqdn=None, join_time=None, permission=None):
        self.name = name
        if owner:
            self.owner = (owner, owner_email)
        else:
            self.owner = None
        if join_time is None:
            self.join_time = time.time()
        else:
            self.join_time = join_time
        self.permission = permission
        self.password = password
        self.platform = platform
        self.ssh_access = ssh_access
        self.last_update = last_update
        self.fqdn = fqdn
        self.last_dead_mail = None

    def __cmp__(self, other):
        return cmp(self.name, other.name)

    def dead_mail_sent(self):
        self.last_dead_mail = int(time.time())

    def update_platform(self, new_platform):
        self.platform = new_platform

    def update_owner(self, new_owner, new_owner_email):
        if new_owner is None:
            self.owner = None
            self.owner_email = None
        else:
            self.owner = (new_owner, new_owner_email)


class HostDatabase(object):
    """Host database."""

    def createhost(self, name, platform=None, owner=None, owner_email=None, password=None, permission=None):
        """Create a new host."""
        raise NotImplementedError(self.createhost)

    def deletehost(self, name):
        """Remove a host."""
        raise NotImplementedError(self.deletehost)

    def hosts(self):
        """Retrieve an iterable over all hosts."""
        raise NotImplementedError(self.hosts)

    def dead_hosts(self, age):
        dead_time = time.time() - age
        cursor = self.store.execute("SELECT host.name AS host, host.owner AS owner, host.owner_email AS owner_email, MAX(age) AS last_update FROM host LEFT JOIN build ON ( host.name == build.host) WHERE ifnull(last_dead_mail, 0) < %d AND ifnull(join_time, 0) < %d GROUP BY host.name having ifnull(MAX(age),0) < %d" % (dead_time, dead_time, dead_time))
        for row in cursor:
            yield Host(row[0], owner=row[1], owner_email=row[2], last_update=row[3])

    def host_ages(self):
        cursor = self.store.execute("SELECT host.name AS host, host.owner AS owner, host.owner_email AS owner_email, MAX(age) AS last_update FROM host LEFT JOIN build ON ( host.name == build.host) GROUP BY host.name ORDER BY age")
        for row in cursor:
            yield Host(row[0], owner=row[1], owner_email=row[2], last_update=row[3])

    def host(self, name):
        """Find a host by name."""
        raise NotImplementedError(self.host)

    def create_rsync_secrets(self):
        """Write out the rsyncd.secrets"""
        yield "# rsyncd.secrets file\n"
        yield "# automatically generated by textfiles.pl. DO NOT EDIT!\n\n"

        for host in self.hosts():
            if host.owner:
                yield "# %s, owner: %s <%s>\n" % (host.name, host.owner[0], host.owner[1])
            else:
                yield "# %s, owner unknown\n" % (host.name,);
            if host.password:
                yield "%s:%s\n\n" % (host.name, host.password)
            else:
                yield "# %s password is unknown\n\n" % host.name

    def create_hosts_list(self):
        """Write out the web/"""

        for host in self.hosts():
            yield "%s: %s\n" % (host.name, host.platform.encode("utf-8"))

    def commit(self):
        pass


class PlainTextHostDatabase(HostDatabase):

    def __init__(self, hosts):
        self._hosts = hosts

    @classmethod
    def from_file(cls, path):
        ret = {}
        f = open(path, 'r')
        try:
            for l in f:
                (host, platform) = l.split(":", 1)
                ret[host] = platform.strip().decode("utf-8")
        finally:
            f.close()
        return cls(ret)

    def hosts(self):
        for name, platform in self._hosts.iteritems():
            yield Host(name, platform=platform)

    def host(self, name):
        try:
            return Host(name=name, platform=self._hosts[name])
        except KeyError:
            raise NoSuchHost(name)
