#!/usr/bin/python
# Simple database query script for the buildfarm
#
# Copyright (C) Andrew Tridgell <tridge@samba.org>     2001-2005
# Copyright (C) Andrew Bartlett <abartlet@samba.org>   2001
# Copyright (C) Vance Lankhaar  <vance@samba.org>      2002-2005
# Copyright (C) Martin Pool <mbp@samba.org>            2001
# Copyright (C) Jelmer Vernooij <jelmer@samba.org>	   2007-2010
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

import bz2
from cStringIO import StringIO
import collections
import hashlib
import os
import re
from storm.locals import Int, RawStr
from storm.store import Store
from storm.expr import Desc
import time


def open_opt_compressed_file(path):
    try:
        return bz2.BZ2File(path+".bz2", 'r')
    except IOError:
        return open(path, 'r')


class Test(object):

    def __init__(self, name):
        self.name = name



class TestResult(object):

    def __init__(self, build, test, result):
        self.build = build
        self.test = test
        self.result = result


class BuildSummary(object):

    def __init__(self, host, tree, compiler, revision, status):
        self.host = host
        self.tree = tree
        self.compiler = compiler
        self.revision = revision
        self.status = status


BuildStageResult = collections.namedtuple("BuildStageResult", "name result")


class MissingRevisionInfo(Exception):
    """Revision info could not be found in the build log."""

    def __init__(self, build=None):
        self.build = build


class LogFileMissing(Exception):
    """Log file missing."""


class BuildStatus(object):

    def __init__(self, stages=None, other_failures=None):
        if stages is not None:
            self.stages = [BuildStageResult(n, r) for (n, r) in stages]
        else:
            self.stages = []
        if other_failures is not None:
            self.other_failures = other_failures
        else:
            self.other_failures = set()

    @property
    def failed(self):
        if self.other_failures:
            return True
        return not all([x.result == 0 for x in self.stages])

    def __serialize__(self):
        return repr(self)

    @classmethod
    def __deserialize__(cls, text):
        return eval(text)

    def __str__(self):
        if self.other_failures:
            return ",".join(self.other_failures)
        return "/".join([str(x.result) for x in self.stages])

    def broken_host(self):
        if "disk full" in self.other_failures:
            return True
        return False

    def regressed_since(self, older):
        """Check if this build has regressed since another build."""
        if "disk full" in self.other_failures:
            return False
        if ("timeout" in self.other_failures and
            "timeout" in older.other_failures):
            # When the timeout happens exactly can differ slightly, so it's
            # okay if the numbers are a bit different..
            return False
        if ("panic" in self.other_failures and
            not "panic" in older.other_failures):
            # If this build introduced panics, then that's always worse.
            return True
        if len(self.stages) < len(older.stages):
            # Less stages completed
            return True
        old_stages = dict(older.stages)
        new_stages = dict(self.stages)
        for name, new_result in new_stages.iteritems():
            try:
                old_result = old_stages[name]
            except KeyError:
                continue
            if new_result == old_result:
                continue
            if new_result < 0 and old_result >= 0:
                return True
            elif new_result >= 0 and old_result < 0:
                return False
            else:
                return (abs(new_result) > abs(old_result))
        return False

    def __cmp__(self, other):
        other_extra = other.other_failures - self.other_failures
        self_extra = self.other_failures - other.other_failures
        # Give more importance to other failures
        if other_extra:
            return 1
        if self_extra:
            return -1

        la = len(self.stages)
        lb = len(other.stages)
        if la > lb:
            return 1
        elif lb > la:
            return -1
        else:
            return cmp(other.stages, self.stages)

    def __repr__(self):
        return "%s(%r, %r)" % (self.__class__.__name__, self.stages, self.other_failures)


def check_dir_exists(kind, path):
    if not os.path.isdir(path):
        raise Exception("%s directory %s does not exist" % (kind, path))


def extract_phase_output(f):
    name = None
    output = None
    re_action = re.compile("^ACTION (PASSED|FAILED):\s+(.*)$")
    for l in f:
        if l.startswith("Running action "):
            name = l[len("Running action "):].strip()
            output = []
            continue
        m = re_action.match(l)
        if m:
            assert name == m.group(2).strip(), "%r != %r" % (name, m.group(2))
            yield name, output
            name = None
            output = []
        elif output is not None:
            output.append(l)


def extract_test_output(f):
    for name, output in extract_phase_output(f):
        if name == "test":
            return output
    raise NoTestOutput()


def build_status_from_logs(log, err):
    """get status of build"""
    # FIXME: Perhaps also extract revision here?

    test_failures = 0
    test_successes = 0
    test_seen = 0
    ret = BuildStatus()

    stages = []
    re_status = re.compile("^([A-Z_]+) STATUS:(\s*\d+)$")
    re_action = re.compile("^ACTION (PASSED|FAILED):\s+test$")

    for l in log:
        if l.startswith("No space left on device"):
            ret.other_failures.add("disk full")
            continue
        if "Maximum time expired in timelimit" in l: # Ugh.
            ret.other_failures.add("timeout")
            continue
        if "maximum runtime exceeded" in l: # Ugh.
            ret.other_failures.add("timeout")
            continue
        if l.startswith("PANIC:") or l.startswith("INTERNAL ERROR:"):
            ret.other_failures.add("panic")
            continue
        if l.startswith("testsuite-failure: ") or l.startswith("testsuite-error: "):
            test_failures += 1
            continue
        if l.startswith("testsuite-success: "):
            test_successes += 1
            continue
        m = re_status.match(l)
        if m:
            stages.append(BuildStageResult(m.group(1), int(m.group(2).strip())))
            if m.group(1) == "TEST":
                test_seen = 1
            continue
        m = re_action.match(l)
        if m and not test_seen:
            if m.group(1) == "PASSED":
                stages.append(BuildStageResult("TEST", 0))
            else:
                stages.append(BuildStageResult("TEST", 1))
            continue

    # Scan err file for specific errors
    for l in err:
        if "No space left on device" in l:
            ret.other_failures.add("disk full")

    def map_stage(sr):
        if sr.name != "TEST":
            return sr
        # TEST is special
        if test_successes + test_failures == 0:
            # No granular test output
            return BuildStageResult("TEST", sr.result)
        if sr.result == 1 and test_failures == 0:
            ret.other_failures.add("inconsistent test result")
            return BuildStageResult("TEST", -1)
        return BuildStageResult("TEST", test_failures)

    ret.stages = map(map_stage, stages)
    return ret


def revision_from_log(log):
    revid = None
    for l in log:
        if l.startswith("BUILD COMMIT REVISION: "):
            revid = l.split(":", 1)[1].strip()
    if revid is None:
        raise MissingRevisionInfo()
    return revid


class NoSuchBuildError(Exception):
    """The build with the specified name does not exist."""

    def __init__(self, tree, host, compiler, rev=None):
        self.tree = tree
        self.host = host
        self.compiler = compiler
        self.rev = rev


class NoTestOutput(Exception):
    """The build did not have any associated test output."""


class Build(object):
    """A single build of a tree on a particular host using a particular compiler.
    """

    def __init__(self, basename, tree, host, compiler, rev=None):
        self.basename = basename
        self.tree = tree
        self.host = host
        self.compiler = compiler
        self.revision = rev

    def __cmp__(self, other):
        return cmp(
            (self.upload_time, self.revision, self.host, self.tree, self.compiler),
            (other.upload_time, other.revision, other.host, other.tree, other.compiler))

    def __eq__(self, other):
        return (isinstance(other, Build) and
                self.log_checksum() == other.log_checksum())

    def __repr__(self):
        if self.revision is not None:
            return "<%s: revision %s of %s on %s using %s>" % (self.__class__.__name__, self.revision, self.tree, self.host, self.compiler)
        else:
            return "<%s: %s on %s using %s>" % (self.__class__.__name__, self.tree, self.host, self.compiler)

    def remove_logs(self):
        # In general, basename.log should *always* exist.
        if os.path.exists(self.basename+".log"):
            os.unlink(self.basename + ".log")
        if os.path.exists(self.basename+".err"):
            os.unlink(self.basename+".err")

    def remove(self):
        self.remove_logs()

    @property
    def upload_time(self):
        """get timestamp of build"""
        st = os.stat("%s.log" % self.basename)
        return st.st_mtime

    @property
    def age(self):
        """get the age of build"""
        return time.time() - self.upload_time

    def read_subunit(self):
        """read the test output as subunit"""
        return StringIO("".join(extract_test_output(self.read_log())))

    def read_log(self):
        """read full log file"""
        try:
            return open_opt_compressed_file(self.basename+".log")
        except IOError:
            raise LogFileMissing()

    def has_log(self):
        try:
            f = self.read_log()
        except LogFileMissing:
            return False
        else:
            f.close()
            return True

    def read_err(self):
        """read full err file"""
        try:
            return open_opt_compressed_file(self.basename+".err")
        except IOError:
            # No such file
            return StringIO()

    def log_checksum(self):
        f = self.read_log()
        try:
            return hashlib.sha1(f.read()).hexdigest()
        finally:
            f.close()

    def summary(self):
        revid = self.revision_details()
        status = self.status()
        return BuildSummary(self.host, self.tree, self.compiler, revid, status)

    def revision_details(self):
        """get the revision of build

        :return: revision id
        """
        f = self.read_log()
        try:
            return revision_from_log(f)
        finally:
            f.close()

    def status(self):
        """get status of build

        :return: tuple with build status
        """
        log = self.read_log()
        try:
            err = self.read_err()
            try:
                return build_status_from_logs(log, err)
            finally:
                err.close()
        finally:
            log.close()

    def err_count(self):
        """get status of build"""
        file = self.read_err()
        return len(file.readlines())


class UploadBuildResultStore(object):

    def __init__(self, path):
        """Open the database.

        :param path: Build result base directory
        """
        self.path = path

    def get_all_builds(self):
        for name in os.listdir(self.path):
            try:
                (build, tree, host, compiler, extension) = name.split(".")
            except ValueError:
                continue
            if build != "build" or extension != "log":
                continue
            yield self.get_build(tree, host, compiler)

    def build_fname(self, tree, host, compiler):
        return os.path.join(self.path, "build.%s.%s.%s" % (tree, host, compiler))

    def has_host(self, host):
        for name in os.listdir(self.path):
            try:
                if name.split(".")[2] == host:
                    return True
            except IndexError:
                pass
        return False

    def get_build(self, tree, host, compiler):
        basename = self.build_fname(tree, host, compiler)
        logf = "%s.log" % basename
        if not os.path.exists(logf):
            raise NoSuchBuildError(tree, host, compiler)
        return Build(basename, tree, host, compiler)


class StormBuild(Build):
    __storm_table__ = "build"

    id = Int(primary=True)
    tree = RawStr()
    revision = RawStr()
    host = RawStr()
    compiler = RawStr()
    checksum = RawStr()
    upload_time = Int(name="age")
    status_str = RawStr(name="status")
    basename = RawStr()
    host_id = Int()
    tree_id = Int()
    compiler_id = Int()

    def status(self):
        return BuildStatus.__deserialize__(self.status_str)

    def revision_details(self):
        return self.revision

    def log_checksum(self):
        return self.checksum

    def remove(self):
        super(StormBuild, self).remove()
        Store.of(self).remove(self)

    def remove_logs(self):
        super(StormBuild, self).remove_logs()
        self.basename = None


class BuildResultStore(object):
    """The build farm build result database."""

    def __init__(self, basedir, store=None):
        from buildfarm.sqldb import memory_store
        if store is None:
            store = memory_store()

        self.store = store
        self.path = basedir

    def __contains__(self, build):
        try:
            self.get_by_checksum(build.log_checksum())
            return True
        except NoSuchBuildError:
            return False

    def get_build(self, tree, host, compiler, revision=None, checksum=None):
        from buildfarm.sqldb import Cast
        expr = [
            Cast(StormBuild.tree, "TEXT") == Cast(tree, "TEXT"),
            Cast(StormBuild.host, "TEXT") == Cast(host, "TEXT"),
            Cast(StormBuild.compiler, "TEXT") == Cast(compiler, "TEXT"),
            ]
        if revision is not None:
            expr.append(Cast(StormBuild.revision, "TEXT") == Cast(revision, "TEXT"))
        if checksum is not None:
            expr.append(Cast(StormBuild.checksum, "TEXT") == Cast(checksum, "TEXT"))
        result = self.store.find(StormBuild, *expr).order_by(Desc(StormBuild.upload_time))
        ret = result.first()
        if ret is None:
            raise NoSuchBuildError(tree, host, compiler, revision)
        return ret

    def build_fname(self, tree, host, compiler, rev):
        """get the name of the build file"""
        return os.path.join(self.path, "build.%s.%s.%s-%s" % (tree, host, compiler, rev))

    def get_all_builds(self):
        for l in os.listdir(self.path):
            m = re.match("^build\.([0-9A-Za-z]+)\.([0-9A-Za-z]+)\.([0-9A-Za-z]+)-([0-9A-Fa-f]+).log$", l)
            if not m:
                continue
            tree = m.group(1)
            host = m.group(2)
            compiler = m.group(3)
            rev = m.group(4)
            stat = os.stat(os.path.join(self.path, l))
            # skip the current build
            if stat.st_nlink == 2:
                continue
            yield self.get_build(tree, host, compiler, rev)

    def get_old_builds(self, tree, host, compiler):
        result = self.store.find(StormBuild,
            StormBuild.tree == tree,
            StormBuild.host == host,
            StormBuild.compiler == compiler)
        return result.order_by(Desc(StormBuild.upload_time))

    def upload_build(self, build):
        from buildfarm.sqldb import Cast, StormHost
        try:
            existing_build = self.get_by_checksum(build.log_checksum())
        except NoSuchBuildError:
            pass
        else:
            # Already present
            assert build.tree == existing_build.tree
            assert build.host == existing_build.host
            assert build.compiler == existing_build.compiler
            return existing_build
        rev = build.revision_details()

        new_basename = self.build_fname(build.tree, build.host, build.compiler, rev)
        for name in os.listdir(self.path):
            p = os.path.join(self.path, name)
            if p.startswith(new_basename+"."):
                os.remove(p)
        os.link(build.basename+".log", new_basename+".log")
        if os.path.exists(build.basename+".err"):
            os.link(build.basename+".err", new_basename+".err")
        new_build = StormBuild(new_basename, build.tree, build.host, build.compiler, rev)
        new_build.checksum = build.log_checksum()
        new_build.upload_time = build.upload_time
        new_build.status_str = build.status().__serialize__()
        new_build.basename = new_basename
        host = self.store.find(StormHost,
            Cast(StormHost.name, "TEXT") == Cast(build.host, "TEXT")).one()
        assert host is not None, "Unable to find host %r" % build.host
        new_build.host_id = host.id
        self.store.add(new_build)
        return new_build

    def get_by_checksum(self, checksum):
        from buildfarm.sqldb import Cast
        result = self.store.find(StormBuild,
            Cast(StormBuild.checksum, "TEXT") == Cast(checksum, "TEXT")).order_by(Desc(StormBuild.upload_time))
        ret = result.first()
        if ret is None:
            raise NoSuchBuildError(None, None, None, None)
        return ret

    def get_previous_build(self, tree, host, compiler, revision):
        from buildfarm.sqldb import Cast
        cur_build = self.get_build(tree, host, compiler, revision)

        result = self.store.find(StormBuild,
            Cast(StormBuild.tree, "TEXT") == Cast(tree, "TEXT"),
            Cast(StormBuild.host, "TEXT") == Cast(host, "TEXT"),
            Cast(StormBuild.compiler, "TEXT") == Cast(compiler, "TEXT"),
            Cast(StormBuild.revision, "TEXT") != Cast(revision, "TEXT"),
            StormBuild.id < cur_build.id)
        result = result.order_by(Desc(StormBuild.id))
        prev_build = result.first()
        if prev_build is None:
            raise NoSuchBuildError(tree, host, compiler, revision)
        return prev_build

    def get_latest_build(self, tree, host, compiler):
        result = self.store.find(StormBuild,
            StormBuild.tree == tree,
            StormBuild.host == host,
            StormBuild.compiler == compiler)
        result = result.order_by(Desc(StormBuild.id))
        build = result.first()
        if build is None:
            raise NoSuchBuildError(tree, host, compiler)
        return build


class BuildDiff(object):
    """Represents the difference between two builds."""

    def __init__(self, tree, old, new):
        self.tree = tree
        self.old = old
        self.new = new
        self.new_rev = new.revision_details()
        self.new_status = new.status()

        self.old_rev = old.revision_details()
        self.old_status = old.status()

    def is_regression(self):
        """Is there a regression in new build since old build?"""
        return self.new_status.regressed_since(self.old_status)

    def revisions(self):
        """Returns the revisions introduced since old in new."""
        branch = self.tree.get_branch()
        return branch.log(from_rev=self.new.revision, exclude_revs=set([self.old.revision]))
