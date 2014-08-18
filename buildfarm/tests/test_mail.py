#PYTHONPATH=. python -m unittest buildfarm.tests.test_suite

import testtools
import unittest

from buildfarm import BuildFarm
from buildfarm.build import (
    Build,
    BuildStatus,
    UploadBuildResultStore,
    build_status_from_logs,
    extract_test_output,
    )

from buildfarm.tests import BuildFarmTestCase
from import_and_analyse import broken_build_check


class BrokenBuildCheckTests(BuildFarmTestCase):

    def setUp(self):
        super(BrokenBuildCheckTests, self).setUp()
        self.buildfarm = BuildFarm(self.path)
        self.write_compilers(["cc", "gcc"])
        self.write_hosts({"somehost": "Some machine",
                          "anotherhost": "Another host"})
        self.write_trees({"trivial": {"scm": "git", "repo": "git://foo", "branch": "master"},
                          "tdb": {"scm": "git", "repo": "other.git", "branch": "HEAD"}})
        self.x = self.buildfarm.builds

    def test_broken_build_check(self):
        path = self.create_mock_logfile("tdb", "somehost", "cc",
            contents="BUILD COMMIT REVISION: 12\n", mtime=40)
        self.x.upload_build(Build(path[:-4],"tdb", "somehost", "cc"))
        path = self.create_mock_logfile("tdb", "somehost", "cc",
            contents="BUILD COMMIT REVISION: 11\nINTERNAL ERROR:\n", mtime=2605000)
        uploadedbuild = self.x.upload_build(Build(path[:-4],"tdb", "somehost", "cc"))
        result = broken_build_check(self.x, uploadedbuild, 11)
        self.assertEquals(2605000, result[0].upload_time)
        self.assertEquals(40, result[1].upload_time)
        self.assertEquals(None, result[2])

        path = self.create_mock_logfile("tdb", "anotherhost", "gcc",
            contents="BUILD COMMIT REVISION: 10\nINTERNAL ERROR:\n", mtime=60)
        self.x.upload_build(Build(path[:-4],"tdb", "anotherhost", "gcc"))
        path = self.create_mock_logfile("tdb", "anotherhost", "gcc",
            contents="BUILD COMMIT REVISION: 9\nINTERNAL ERROR:\nBuild STATUS: FAILED", mtime=70)
        uploadedbuild = self.x.upload_build(Build(path[:-4],"tdb", "anotherhost", "gcc"))
        result = broken_build_check(self.x, uploadedbuild, 9)
        self.assertEquals(70, result[0].upload_time)
        self.assertEquals(60, result[1].upload_time)
        self.assertEquals(None, result[2])


