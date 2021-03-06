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

from buildfarm.build import Build
from buildfarm.sqldb import setup_schema
import os
from storm import database
from storm.store import Store
from testtools import TestCase
import shutil
import tempfile
import unittest


class BuildFarmTestCase(TestCase):
    """Test case class that provides a build farm data directory and convenience methods.
    """

    def upload_mock_logfile(self, store, tree, host, compiler,
            stdout_contents="", stderr_contents=None, mtime=None):
        log_path = self.create_mock_logfile(tree, host, compiler, contents=stdout_contents, mtime=mtime)
        if stderr_contents is not None:
            err_path = self.create_mock_logfile(tree, host, compiler, kind="stderr", contents=stderr_contents, mtime=mtime)
        build = Build(log_path[:-4], tree, host, compiler)
        store.upload_build(build)
        return log_path

    def create_mock_logfile(self, tree, host, compiler, rev=None,
            kind="stdout", contents="FOO", mtime=None):
        basename = "build.%s.%s.%s" % (tree, host, compiler)
        if rev is not None:
            basename += "-%s" % rev
            path = os.path.join(self.path, "data", "oldrevs", basename)
        else:
            path = os.path.join(self.path, "data", "upload", basename)
        if kind == "stdout":
            path += ".log"
        elif kind == "stderr":
            path += ".err"
        else:
            raise ValueError("Unknown log kind %r" % kind)
        f = open(path, 'w+')
        try:
            f.write(contents)
        finally:
            f.close()
        if mtime is not None:
            os.utime(path, (mtime, mtime))
        return path

    def write_compilers(self, compilers):
        f = open(os.path.join(self.path, "web", "compilers.list"), "w")
        try:
            for compiler in compilers:
                f.write("%s\n" % compiler)
        finally:
            f.close()

    def write_hosts(self, hosts):
        for host in hosts:
            self.buildfarm.hostdb.createhost(host)

    def write_trees(self, trees):
        f = open(os.path.join(self.path, "web", "trees.conf"), "w")
        try:
            for t in trees:
                f.write("[%s]\n" % t)
                for k, v in trees[t].iteritems():
                    f.write("%s = %s\n" % (k, v))
                f.write("\n")
        finally:
            f.close()

    def setUp(self):
        super(BuildFarmTestCase, self).setUp()
        self.path = tempfile.mkdtemp()

        for subdir in ["data", "data/upload", "data/oldrevs", "db", "web", "lcov", "lcov/data"]:
            os.mkdir(os.path.join(self.path, subdir))

        self.db_url = "sqlite:"+os.path.join(self.path, "db", "hostdb.sqlite")
        db = database.create_database(self.db_url)
        store = Store(db)
        setup_schema(store)
        store.commit()
        self.write_compilers([])
        self.write_hosts({})

    def tearDown(self):
        shutil.rmtree(self.path)
        super(BuildFarmTestCase, self).tearDown()


def test_suite():
    names = [
        '__init__',
        'test_build',
        'test_buildfarm',
        'test_history',
        'test_hostdb',
        'test_sqldb',
        'test_util',
        'test_mail',
        ]
    module_names = ['buildfarm.tests.' + name for name in names]
    result = unittest.TestSuite()
    loader = unittest.TestLoader()
    suite = loader.loadTestsFromNames(module_names)
    result.addTests(suite)
    return result
