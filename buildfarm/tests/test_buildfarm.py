#!/usr/bin/python
# Copyright (C) Jelmer Vernooij <jelmer@samba.org> 2010
#
#   This program is free software; you can redistribute it and/or modify
#   it under the terms of the GNU General Public License as published by
#   the Free Software Foundation; either version 3 of the License, or
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

from buildfarm import (
    BuildFarm,
    CachingBuildFarm,
    data,
    read_trees_from_conf,
    )
from buildfarm.tests import BuildFarmTestCase

import os
from testtools import TestCase
import tempfile


class ReadTreesFromConfTests(TestCase):

    def create_file(self, contents):
        (fd, path) = tempfile.mkstemp()
        f = os.fdopen(fd, 'w')
        self.addCleanup(os.remove, path)
        try:
            f.write(contents)
        finally:
            f.close()
        return path

    def test_read_trees_from_conf_ko(self):
        name = self.create_file("""
[foo]
param1 = fooval1
param2 = fooval2
param3 = fooval3

[bar]
param1 = barval1
param2 = barval2
param3 = barval3
""")
        self.assertRaises(
            Exception, read_trees_from_conf, name, None)

    def test_read_trees_from_conf(self):
        name = self.create_file("""
[pidl]
scm = git
repo = samba.git
branch = master
subdir = pidl/

[rsync]
scm = git
repo = rsync.git
branch = HEAD
""")
        t = read_trees_from_conf(name)
        self.assertEquals(
            t["pidl"].scm,
            "git")


class BuildFarmTestBase(object):

    def setUp(self):
        self.write_compilers(["cc"])
        self.write_trees({"trivial": { "scm": "git", "repo": "git://foo", "branch": "master" }})

    def test_get_new_builds_empty(self):
        self.assertEquals([], list(self.x.get_new_builds()))

    def test_lcov_status_none(self):
        self.assertRaises(data.NoSuchBuildError, self.x.lcov_status, "trivial")

    def test_tree(self):
        self.assertEquals("trivial", self.x.trees["trivial"].name)
        tree = self.x.trees["trivial"]
        self.assertEquals("git", tree.scm)
        self.assertEquals("git://foo", tree.repo)
        self.assertEquals("master", tree.branch)

    def test_get_build_rev(self):
        path = self.create_mock_logfile("tdb", "charis", "cc", "12",
            contents="This is what a log file looks like.")
        build = self.x.get_build("tdb", "charis", "cc", "12")
        self.assertEquals("tdb", build.tree)
        self.assertEquals("charis", build.host)
        self.assertEquals("cc", build.compiler)
        self.assertEquals("12", build.rev)

    def test_get_build_no_rev(self):
        path = self.create_mock_logfile("tdb", "charis", "cc", 
            contents="This is what a log file looks like.")
        build = self.x.get_build("tdb", "charis", "cc")
        self.assertEquals("tdb", build.tree)
        self.assertEquals("charis", build.host)
        self.assertEquals("cc", build.compiler)
        self.assertIs(None, build.rev)


class BuildFarmTests(BuildFarmTestBase, BuildFarmTestCase):

    def setUp(self):
        BuildFarmTestCase.setUp(self)
        BuildFarmTestBase.setUp(self)
        self.x = BuildFarm(self.path)


class CachingBuildFarmTests(BuildFarmTestBase, BuildFarmTestCase):

    def setUp(self):
        BuildFarmTestCase.setUp(self)
        BuildFarmTestBase.setUp(self)
        self.x = CachingBuildFarm(self.path)