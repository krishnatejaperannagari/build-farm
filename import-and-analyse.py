#!/usr/bin/python
# Write sqlite entries for test reports in the build farm
# Copyright (C) 2007-2010 Jelmer Vernooij <jelmer@samba.org>
# Copyright (C) 2007-2010 Andrew Bartlett <abartlet@samba.org>
# Published under the GNU GPL

"""Script to parse build farm log files from the data directory, import
them into the database, add links to the oldrevs/ directory and send
some mail chastising the possible culprits when the build fails, based
on recent commits.
"""

from buildfarm.build import (
    BuildDiff,
    MissingRevisionInfo,
    NoSuchBuildError,
    )
from buildfarm import BuildFarm
from buildfarm.web import (
    build_uri,
    )
from email.mime.text import MIMEText
import optparse
import resource
import smtplib

parser = optparse.OptionParser("import-and-analyse [options]")
parser.add_option("--dry-run", help="Will cause the script to send output to stdout instead of to sendmail.", action="store_true")
parser.add_option("--verbose", help="Be verbose", action="count")

(opts, args) = parser.parse_args()

resource.setrlimit(resource.RLIMIT_RSS, (300000, 300000))
resource.setrlimit(resource.RLIMIT_DATA, (300000, 300000))

buildfarm = BuildFarm(timeout=40.0)

smtp = smtplib.SMTP()
smtp.connect()


def broken_build_check(second_build, rev):

    original_build = second_build
    third_build = None
    first_build = None
    count = 1

    if second_build.tree is "waf":
        # no point sending emails, as the email addresses are invalid
        return None

    if second_build.tree is "samba_3_waf":
        # no emails for this until it stabilises a bit
        return None

    try:
        if opts.dry_run:
            # Perhaps this is a dry run and rev is not in the database yet so get build itself
            third_build = buildfarm.builds.get_latest_build(build.tree, build.host, build.compiler)
        else:
            third_build = buildfarm.builds.get_previous_build(build.tree, build.host, build.compiler, rev)
    except NoSuchBuildError:
        #cant send a nasty mail unless there are two builds
        return None

    #getting the first failed build in the sequence and send the mail to the commiters and authors of that build
    while(True):

        t = buildfarm.trees[second_build.tree]
        diff = BuildDiff(t, third_build, second_build)

        if not diff.is_regression():
            #checks if the builds have regressed else breaks the loop
            if opts.verbose >= 3:
                print "... hasn't regressed since %s: %s" % (diff.old_rev, diff.old_status)
            break

        count += 1
        first_build = second_build
        second_build = third_build
        third_build = None

        if opts.dry_run:
            break

        try:
            rev = second_build.revision_details()
        except MissingRevisionInfo:
            #no rev
            break

        try:
            #gets a previous build
            third_build = buildfarm.builds.get_previous_build(second_build.tree, second_build.host, second_build.compiler, rev)
        except NoSuchBuildError:
            break

    if count > 2:
        #three or more builds have failed consequtively
        return [first_build, second_build, original_build]
    elif count == 2:
        #two builds have regressed checks if the tree doesnt upload build logs frequently or dryrun
        #though there is regression we need to check as the previous mail would have been sent in third case 1 month ago only
        if int(first_build.upload_time - build.upload_time) > 2600000 or opts.dry_run:
            return [first_build, second_build, None]
        else:
            return None
    elif count == 1:
        #checks if the current build has failed and sends the mail  since there is no regression
        show = False
        for s in original_build.status().stages:
            if s.result != 0:
                show = True
        if show or "panic" in original_build.status().other_failures and not "disk full" in original_build.status().other_failures and not "timeout" in original_build.status().other_failures:
            return [second_build, third_build, None]
        else:
            return None


def send_mail(cur, old, original):

    t = buildfarm.trees[cur.tree]
    diff = BuildDiff(t, old, cur)

    recipients = set()
    change_log = ""

    for rev in diff.revisions():
        recipients.add(rev.author)
        recipients.add(rev.committer)
        change_log += """
revision: %s
author: %s
committer: %s
message:
    %s
""" % (rev.revision, rev.author, rev.committer, rev.message)

    body = """
Broken build for tree %(tree)s on host %(host)s with compiler %(compiler)s

Tree %(tree)s is %(scm)s branch %(branch)s.

Build status for new revision %(cur_rev)s is %(cur_status)s
Build status for old revision %(old_rev)s was %(old_status)s

See %(build_link)s

The build may have been broken by one of the following commits:

%(change_log)s
    """ % {
        "tree": cur.tree, "host": cur.host, "compiler": cur.compiler,
        "change_log": change_log,
        "scm": t.scm,
        "branch": t.branch,
        "cur_rev": diff.new_rev,
        "old_rev": diff.old_rev,
        "cur_status": diff.new_status,
        "old_status": diff.old_status,
        "build_link": build_uri("http://build.samba.org/build.cgi", cur)
        }

    if original:
        body += "The failures are continued till this build %s. ", build_uri("http://build.samba.org/build.cgi", original)

    msg = MIMEText(body)
    msg["Subject"] = "BUILD of %s:%s BROKEN on %s with %s AT REVISION %s" % (cur.tree, t.branch, cur.host, cur.compiler, diff.new_rev)
    msg["From"] = "\"Build Farm\" <build@samba.org>"
    msg["To"] = ",".join(recipients)

    if not opts.dry_run:
        smtp.sendmail(msg["From"], [msg["To"]], msg.as_string())
    else:
        print msg.as_string()



for build in buildfarm.get_new_builds():
    if build in buildfarm.builds:
        continue

    if not opts.dry_run:
        old_build = build
        try:
            build = buildfarm.builds.upload_build(old_build)
        except MissingRevisionInfo:
            print "No revision info in %r, skipping" % build
            continue
    try:
        rev = build.revision_details()
    except MissingRevisionInfo:
        #no point in sending mail as there is no rev and this is not added to database
        print "No revision info in %r, skipping" % build
        continue

    if opts.verbose >= 2:
        print "%s... " % build,
        print str(build.status())

    x = broken_build_check(build, rev)
    if x:
        send_mail(x[0], x[1], x[2])
    if not opts.dry_run:
        old_build.remove()
        buildfarm.commit()

smtp.quit()
