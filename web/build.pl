#!/usr/bin/perl -w
# This CGI script presents the results of the build_farm build
#
# Copyright (C) Andrew Tridgell <tridge@samba.org>     2001
# Copyright (C) Andrew Bartlett <abartlet@samba.org>   2001
# Copyright (C) Vance Lankhaar  <vance@samba.org>      2002-2005
# Copyright (C) Martin Pool <mbp@samba.org>            2001
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

# TODO: Allow filtering of the "Recent builds" list to show
# e.g. only broken builds or only builds that you care about.


my $BASEDIR = "/home/build/master";
my $CACHEDIR = "/home/build/master/cache";

use strict qw{vars};
use lib "$BASEDIR/web";
use util;
use history;
use POSIX;
use Data::Dumper;
use CGI;
use File::stat;

my $req = new CGI;

my $HEADCOLOR = "#a0a0e0";
my $OLDAGE = 60*60*4;
my $DEADAGE = 60*60*24*4;

##############################################
# this defines what it is possible to build 
# and what boxes. Should be in a config file
my $compilers = ['cc', 'gcc', 'gcc3', 'gcc-3.4', 'gcc-4.0', 'icc'];

my (%hosts) = ('sun1' => "Solaris 8 UltraSparc", 
	       'Isis' => "Solaris 8 i386",
	       'gc20' => "Solaris 2.6 Sparc",
#	       'sco1' => "SysV 3.2 i386", 
#	       'sco2' => "UnixWare 7.1.0 i386", 

	       'aix1' => "AIX 4.3 PPC",
	       'mungera' => "AIX 5.2 IBM POWER4+",
	       'oehmesrs6k' => "AIX 5.2",

	       'us4'  => "IRIX 6.5 MIPS", 
	       'au2'  => "IRIX 6.4 MIPS",

	       'wayne' => "RedHat 6.1 Sparc 10 (Kernel 2.2.18)",
	       'yowiee' => "RedHat 9.0 i386",
#	       'insure' => "RedHat 6.2 vmware (insure)",
	       'svamp' => "RedHat 7.0 i386",
	       'homer' => "RedHat RHEL 3 (WS)",

	       'rhonwyn'  => "Debian Linux unstable i686",
	       'boiccu'  => "Debian Linux testing/unstable IA64",
	       'yurok' => "Debian Linux 3.0 stable i386",
	       'sasoe_smb' => "Debian Linux 3.0 stable i386",
	       'samba-s390' => "Debian Linux 3.0 stable s390",

	       'fusberta' => "Debian Linux 3.0 Alpha",
	       'superego' => "Debian PPC/64 (Power3)",
	       'quango' => "Debian PPC/32 (Power3)",
	       'cl012' => "Debian Testing/Unstable i386",
	       'tux' => "Debian Linux sid/unstable HP PA-RISC",

	       'sparc-woody' => "Debian Linux 3.0 (woody) Sparc64",
	       'sparc-sarge' => "Debian Linux sarge/testing Sparc64",
	       'sparc-sid' => "Debian Linux sid/unstable Sparc64",

	       'flock'  => "OpenBSD 3.6 i386",
	       'flame'  => "OpenBSD 3.0 Sparc",
	       'pandemonium' => "OpenBSD-current Sparc64",

	       'kimchi'  => "NetBSD 1.5 i386",
	       'poseidon' => 'NetBSD 1.6.2 Sparc32',
	       'ares' => 'NetBSD 1.6.2 Sparc64',

	       'aretnap' => "FreeBSD 4.10-STABLE",

	       'gc8'  => "FreeBSD 3.3-RELEASE i386",
	       'gc4'  => "FreeBSD 4.3-STABLE i386",

	       'manhattan' => "FreeBSD 4.8-RELEASE i386",

	       'sbf' => "FreeBSD 5.2.1 i386",
	       'smartserv1' => 'FreeBSD 5.3-STABLE i386',

	       'woko'  => "Cray SV1 UNICOS 10.0.0.8",

	       'hpntc9I' => "HP-UX 11.11",
	       'gwen' => "HP-UX 11.11",

	       'g6usr30' => "RedHat 7.2 IBM s390 (Kernel 2.4.9)",

	       'belle' => "RedHat 8.0 i686",
	       'manjra' => "RedHat 8.0 i686",
	       'lacroix' => "RedHat 9.0 i686 SMP",
	       'delacruz'=> "RedHat 9.0 i686",

	       'berks' => "Fedora Core 1",
	       'tango-one-mars' => "Fedora Core 2 i386",

	       'suse71ppc' => "SuSE 7.1 ppc gcc2.95.2",
	       'metze01' => "SuSE 8.2 i386 (athlon)",
	       'metze02' => "SuSE 7.3 i386 (PIII)",

	       'l390vme1' => "SuSE SLES 8 (S/390)",

	       'opi' => "SuSE SLES 9 (x86_64)",
	       'PCS1' => "SuSE Linux 9.2 Professional (i586)",

	       'cyberone' => "Cygwin i686 (MS WinXP Pro)",

	       'trip' => "Mandrake 10.1 i386",

	       'm30' => "Stratus VOS HP PA-RISC",

	       'previn' => "Solaris 8 UltraSparc",
	       'mundroo' => "Solaris 8 i386",
	       'cat' => "Solaris 9 i386",
	       'fire1' => "Solaris 9 Sparc",
	       'opisol10' => "Solaris 10 b63 x86",

	       'packetstorm' => "Slackware Linux 9.0 i386",

	       'tardis' => "Gentoo i686",
	       'wetlizard' => "Gentoo UltraSparc",
	       'sol10' => "Solaris 10 x86",
	       'dev4-003' => "Debian Unstable x86"
	       );


my @hosts = sort { $hosts{$a} cmp $hosts{$b} } keys %hosts;

my (%trees) = (
#'samba' => "",
	       'samba' => "",
	       'samba4' => "",
	       'samba-docs' => "",
	       'samba_3_0' => "SAMBA_3_0",
	       'rsync' => "",
	       'distcc' => "",
	       'ppp' => "",
	       'ccache' => "");

# these aren't really trees... they're just things we want in the menu.
# (for recent checkins)
my @pseudo_trees = ( "samba-web", "lorikeet", "samba_2_2", "samba_2_2_release", "samba_3_0_release" );
# this is automatically filled in
my (@deadhosts) = ();

###############################################
# work out a URL so I can refer to myself in links
my $myself = $req->self_url;
if ($myself =~ /(.*)[?].*/) {
    $myself = $1;
}
if ($myself =~ /http:\/\/.*\/(.*)/) {
    $myself = $1;
}

#$myself = "http://build.samba.org/";

################################################
# start CGI headers
sub cgi_headers() {
    print "Content-type: text/html\r\n";
    #print "Content-type: application/xhtml+xml\r\n";

    util::cgi_gzip();

    print util::FileLoad("$BASEDIR/web/header.html");
    print '<title>samba.org build farm</title>';
    print util::FileLoad("$BASEDIR/web/header2.html");
    main_menu();
    print util::FileLoad("$BASEDIR/web/header3.html");
}

################################################
# start CGI headers for diffs
sub cgi_headers_diff() {
    print "Content-type: application/x-diff\r\n";
    print "\n";
}

################################################
# start CGI headers for text output
sub cgi_headers_text() {
	print "Content-type: text/plain\r\n";
	print "\r\n";
}

################################################
# end CGI
sub cgi_footers() {
  print util::FileLoad("$BASEDIR/web/footer.html");
}

################################################
# print an error on fatal errors
sub fatal($) {
    my $msg=shift;
    print "ERROR: $msg<br />\n";
    cgi_footers();
    exit(0);
}

##############################################
# get the age of build from ctime
sub build_age($$$)
{
    my $host=shift;
    my $tree=shift;
    my $compiler=shift;
    my $file="build.$tree.$host.$compiler";
    my $age = -1;
    my $st;

    if ($st = stat("$file.log")) {
	$age = time() - $st->ctime;
    }

    return $age;
}

##############################################
# get the svn revision of build
sub build_revision($$$)
{
    my $host=shift;
    my $tree=shift;
    my $compiler=shift;
    my $file="build.$tree.$host.$compiler";
    my $log;
    my $rev = "unknown";

    my $st1 = stat("$file.log");
    my $st2 = stat("$CACHEDIR/$file.revision");

    if ($st1 && $st2 && $st1->ctime <= $st2->ctime) {
	    return util::FileLoad("$CACHEDIR/$file.revision");
    }

    $log = util::FileLoad("$file.log");

    if (! $log) { return 0; }

    if ($log =~ /BUILD REVISION:(.*)/) {
	$rev = $1;
    }

    util::FileSave("$CACHEDIR/$file.revision", "$rev");

    return $rev;
}

#############################################
# get the overall age of a host 
sub host_age($)
{
	my $host = shift;
	my $ret = -1;
	for my $compiler (@{$compilers}) {
		for my $tree (sort keys %trees) {
			my $age = build_age($host, $tree, $compiler);
			if ($age != -1 && ($age < $ret || $ret == -1)) {
				$ret = $age;
			}
		}
	}
	return $ret;
}

#############################################
# show an age as a string
sub red_age($)
{
	my $age = shift;
	
	if ($age > $OLDAGE) { 
		return sprintf("<span class=\"old\">%s</span>",  util::dhm_time($age));
	}
	return util::dhm_time($age);
}


##############################################
# get status of build
sub build_status($$$)
{
    my $host=shift;
    my $tree=shift;
    my $compiler=shift;
    my $file="build.$tree.$host.$compiler";
    my $cachefile="$CACHEDIR/build.$tree.$host.$compiler";
    my ($cstatus, $bstatus, $istatus, $tstatus, $sstatus);
    $cstatus = $bstatus = $istatus = $tstatus = $sstatus =
      "<span class=\"status unknown\">?</span>";

    my $log;
    my $ret;

    my $st1 = stat("$file.log");
    my $st2 = stat("$cachefile.status");

    if ($st1 && $st2 && $st1->ctime <= $st2->ctime) {
	return util::FileLoad("$cachefile.status");
    }

    $log = util::FileLoad("$file.log");

    unlink("$CACHEDIR/FAILED.test.$tree.$host.$compiler");
    if ($log =~ /TEST STATUS:(.*)/) {
	if ($1 == 0) {
	    $tstatus = "<span class=\"status passed\">ok</span>";
	} else {
	    $tstatus = "<span class=\"status failed\">$1</span>";
	    system("touch $CACHEDIR/FAILED.test.$tree.$host.$compiler");
	}
    }
    
    unlink("$CACHEDIR/FAILED.install.$tree.$host.$compiler");
    if ($log =~ /INSTALL STATUS:(.*)/) {
	if ($1 == 0) {
	    $istatus = "<span class=\"status passed\">ok</span>";
	} else {
	    $istatus = "<span class=\"status failed\">$1</span>";
	    system("touch $CACHEDIR/FAILED.install.$tree.$host.$compiler");
	}
    }
    
    unlink("$CACHEDIR/FAILED.build.$tree.$host.$compiler");
    if ($log =~ /BUILD STATUS:(.*)/) {
	if ($1 == 0) {
	    $bstatus = "<span class=\"status passed\">ok</span>";
	} else {
	    $bstatus = "<span class=\"status failed\">$1</span>";
	    system("touch $CACHEDIR/FAILED.build.$tree.$host.$compiler");
	}
    }

    unlink("$CACHEDIR/FAILED.configure.$tree.$host.$compiler");
    if ($log =~ /CONFIGURE STATUS:(.*)/) {
	if ($1 == 0) {
	    $cstatus = "<span class=\"status passed\">ok</span>";
	} else {
	    $cstatus = "<span class=\"status failed\">$1</span>";
	    system("touch $CACHEDIR/FAILED.configure.$tree.$host.$compiler");
	}
    }
    
    unlink("$CACHEDIR/FAILED.internalerror.$tree.$host.$compiler");
    if ($log =~ /INTERNAL ERROR:(.*)/ || $log =~ /PANIC:(.*)/) {
	$sstatus = "/<span class=\"status panic\">PANIC</span>";
	system("touch $CACHEDIR/FAILED.internalerror.$tree.$host.$compiler");
    } else {
	$sstatus = "";
    }
    
    $ret = "<a href=\"$myself?function=View+Build;host=$host;tree=$tree;compiler=$compiler\">$cstatus/$bstatus/$istatus/$tstatus$sstatus</a>";


    util::FileSave("$CACHEDIR/$file.status", $ret);

    return $ret;
}


##############################################
# get status of build
sub err_count($$$)
{
    my $host=shift;
    my $tree=shift;
    my $compiler=shift;
    my $file="build.$tree.$host.$compiler";
    my $err;

    my $st1 = stat("$file.err");
    my $st2 = stat("$CACHEDIR/$file.errcount");

    if ($st1 && $st2 && $st1->ctime <= $st2->ctime) {
	    return util::FileLoad("$CACHEDIR/$file.errcount");
    }

    $err = util::FileLoad("$file.err");

    if (! $err) { return 0; }

    my $ret = util::count_lines($err);

    util::FileSave("$CACHEDIR/$file.errcount", "$ret");

    return $ret;
}



##############################################
# view build summary
sub view_summary($) {
    my $i = 0;
    my $list = `ls`;

    my $cols = 2;

    my $broken = 0;

    # either "text" or anything else.
    my $output_type = shift;

    # set up counters
    my %broken_count;
    my %panic_count;
    my %host_count;

    # zero broken and panic counters
    for my $tree (sort keys %trees) {
	$broken_count{$tree} = 0;
	$panic_count{$tree} = 0;
	$host_count{$tree} = 0;
    }

    #set up a variable to store the broken builds table's code, so we can output when we want
    my $broken_table = "";

    my $host_os;
    my $last_host = "";

    # for the text report, include the current time
    if ($output_type eq 'text') {
	    my $time = gmtime();
	    print "Build status as of $time\n\n";
    }

    for my $host (@hosts) {
	for my $compiler (@{$compilers}) {
	    for my $tree (sort keys %trees) {
		my $status = build_status($host, $tree, $compiler);
		my $age = build_age($host, $tree, $compiler);

		if ($age != -1 && $age < $DEADAGE) {
		    $host_count{$tree}++;
		}

		if ($age < $DEADAGE && $status =~ /status failed/) {
		    $broken_count{$tree}++;
		    if ($status =~ /PANIC/) {
			$panic_count{$tree}++;
		    }
		    my $warnings = err_count($host, $tree, $compiler);

		    $host_os = $hosts{$host};
		    if ($output_type eq "text") {
			    if (!$broken) {
				    $broken = 1;
				    $broken_table = "Currently broken builds:\n";
				    $broken_table .= sprintf "%-18s %-12s %-10s %-10s\n",
				    "Host", "Tree", "Compiler", "Status";

			    }
			    $broken_table .= sprintf "%-18s %-12s %-10s %-10s\n",
				    $host, $tree, $compiler, strip_html($status);
		    }
		    else {
			    if (!$broken) {
				    $broken = 1;
				    $broken_table = <<EOHEADER;

<div id="build-broken-summary" class="build-section">
<h2>Currently broken builds:</h2>
<table class="summary real">
  <thead>
    <tr>
      <th colspan="3">Target</th><th>Build&nbsp;Age</th><th>Status<br />config/build<br />install/test</th><th>Warnings</th>
    </tr>
  </thead>
  <tbody>
EOHEADER
			    }

			    $broken_table .= "    <tr>";

			    if ($host eq $last_host) {
				    $broken_table .= "<td colspan=\"2\" />";
			    } else {
				    $broken_table .= "<td>$host_os</td><td><a href=\"#$host\">$host</a></td>";
			    }
			    $broken_table .= "<td><span class=\"tree\">$tree</span>/$compiler</td><td class=\"age\">" . red_age($age) . "</td><td class=\"status\">$status</td><td>$warnings</td></tr>\n";
		    }

		    $last_host = $host;
		    
		}
	    }
	}
    }
    
    if ($broken && $output_type eq 'text') {
	    $broken_table .= "\n";
    }
    elsif ($broken) {
	    $broken_table .= "  </tbody>\n</table>\n</div>\n";
    }

    if ($output_type eq 'text') {
	    print "Build counts:\n";
	    printf "%-12s %-6s %-6s %-6s\n", "Tree", "Total", "Broken", "Panic";
    }
    else {
	    print <<EOHEADER;


<div id="build-counts" class="build-section">
<h2>Build counts:</h2>
<table class="real">
  <thead>
    <tr>
      <th>Tree</th><th>Total</th><th>Broken</th><th>Panic</th>
    </tr>
  </thead>
  <tbody>
EOHEADER
    }


    for my $tree (sort keys %trees) {
	    if ($output_type eq 'text') {
		    printf "%-12s %-6s %-6s %-6s\n", $tree, $host_count{$tree},
			    $broken_count{$tree}, $panic_count{$tree};
	    }
	    else {
		    print "    <tr><td>$tree</td><td>$host_count{$tree}</td><td>$broken_count{$tree}</td>";
		    my $panic = "";
		    if ($panic_count{$tree}) {
			    $panic = " class=\"panic\"";
		    }
		    print "<td$panic>$panic_count{$tree}</td></tr>\n";
	    }
    }

    if ($output_type eq 'text') {
	    print "\n";
    }
    else {
	    print "  </tbody>\n</table></div>\n";
    }


    print $broken_table;

    # for now, don't output individual build summaries in text report
    if ($output_type eq 'text') {
	    return;
    }

    if ($output_type eq 'text') {
	    print "Build summary:\n";
    }
    else {
	    print "<div class=\"build-section\" id=\"build-summary\">\n";
	    print "<h2>Build summary:</h2>\n";
    }

    for my $host (@hosts) {
	# make sure we have some data from it
	if (! ($list =~ /$host/)) {
		if ($output_type ne 'text') {
			print "<!-- skipping $host -->\n";
		}
	    next;
	}

	my $row = 0;

	for my $compiler (@{$compilers}) {
	    for my $tree (sort keys %trees) {
		my $age = build_age($host, $tree, $compiler);
		my $warnings = err_count($host, $tree, $compiler);
		if ($age != -1 && $age < $DEADAGE) {
		    my $status = build_status($host, $tree, $compiler);
		    if ($row == 0) {
			    if ($output_type eq 'text') {
				    printf "%-12s %-10s %-10s %-10s %-10s\n",
				    "Tree", "Compiler", "Build Age", "Status", "Warnings";
				    
			    }
			    else {
				    print <<EOHEADER;
<div class="host summary">
  <a id="$host" name="$host" />
  <h3>$host - $hosts{$host}</h3>
  <table class="real">
    <thead>
      <tr>
        <th>Target</th><th>Build&nbsp;Age</th><th>Status<br />config/build<br />install/test</th><th>Warnings</th>
      </tr>
    </thead>
    <tbody>
EOHEADER
			    }
		    }

		    if ($output_type eq 'text') {
			    printf "%-12s %-10s %-10s %-10s %-10s\n",
				    $tree, $compiler, util::dhm_time($age), 
					    strip_html($status), $warnings;
		    }
		    else {
			    print "    <tr><td><span class=\"tree\">$tree</span>/$compiler</td><td class=\"age\">" . red_age($age) . "</td><td class=\"status\">$status</td><td>$warnings</td></tr>\n";
		    }
		    $row++;
		}
	    }
	}
	if ($row != 0) {
		if ($output_type eq 'text') {
			print "\n";
		}
		else {
			print "  </tbody>\n</table></div>\n";
		}
	    $i++;
	} else {
	    push(@deadhosts, $host);
	}
    }

    if ($output_type ne 'text') {
	    print "</div>\n\n";
    }

    draw_dead_hosts($output_type, @deadhosts);
}

##############################################
# Draw the "recent builds" view

sub view_recent_builds() {
    my $i = 0;
    my $list = `ls`;

    my $cols = 2;

    my $broken = 0;

    my $host_os;
    my $last_host = "";
    my @all_builds = ();
    my $tree=$req->param("tree");

    # Convert from the DataDumper tree form to an array that 
    # can be sorted by time.

    for my $host (@hosts) {
      for my $compiler (@{$compilers}) {
	  my $status = build_status($host, $tree, $compiler);
	  my $age = build_age($host, $tree, $compiler);
	  my $revision = build_revision($host, $tree, $compiler);
	  push @all_builds, [$age, $hosts{$host}, "<a href=\"$myself?function=Summary;host=$host;tree=$tree;compiler=$compiler#$host\">$host</a>", $compiler, $tree, $status, $revision]
	  	unless $age == -1 or $age >= $DEADAGE;
      }
  }

  @all_builds = sort {$$a[0] <=> $$b[0]} @all_builds;
  

    print <<EOHEADER;

    <div id="recent-builds" class="build-section">
    <h2>Recent builds of $tree</h2>
      <table class="real">
	<thead>
	  <tr>
            <th>Age</th><th>Revision</th><th colspan="4">Target</th><th>Status</th>
	  </tr>
	</thead>
        <tbody>
EOHEADER


    for my $build (@all_builds) {
	my $age = $$build[0];
	my $rev = $$build[6];
	print "    <tr>",
	  "<td>" . util::dhm_time($age). "</td>",
	  "<td>$rev</td><td>",
	  join("</td><td>", @$build[4, 1, 2, 3, 5]),
	  "</td></tr>\n";
    }
    print "  </tbody>\n</table>\n</div>\n";
}


##############################################
# Draw the "dead hosts" table
sub draw_dead_hosts() {
    my $output_type = shift;
    my @deadhosts = @_;

    # don't output anything if there are no dead hosts
    if ($#deadhosts < 1) {
      return;
    }

    # don't include in text report
    if ($output_type eq 'text') {
	    return;
    }
	print <<EOHEADER;
<div class="build-section" id="dead-hosts">
<h2>Dead Hosts:</h2>
<table class="real">
<thead>
<tr><th>Host</th><th>OS</th><th>Min Age</th></tr>
</thead>
<tbody>
EOHEADER

    for my $host (@deadhosts) {
	my $age = host_age($host);
	print "    <tr><td>$host</td><td>$hosts{$host}</td><td>", util::dhm_time($age), "</td></tr>";
    }


    print "  </tbody>\n</table>\n</div>\n";
}


##############################################
# view one build in detail
sub view_build() {
    my $host=$req->param("host");
    my $tree=$req->param("tree");
    my $compiler=$req->param("compiler");
    my $file="build.$tree.$host.$compiler";
    my $log;
    my $err;
    my $uname="";
    my $cflags="";
    my $config="";
    my $age = build_age($host, $tree, $compiler);
    my $rev = build_revision($host, $tree, $compiler);
    my $status = build_status($host, $tree, $compiler);

    util::InArray($host, [keys %hosts]) || fatal("unknown host");
    util::InArray($compiler, $compilers) || fatal("unknown compiler");
    util::InArray($tree, [sort keys %trees]) || fatal("unknown tree");

    $log = util::FileLoad("$file.log");
    $err = util::FileLoad("$file.err");
    
    if ($log) {
	$log = util::cgi_escape($log);

	if ($log =~ /(.*)/) { $uname=$1; }
	if ($log =~ /CFLAGS=(.*)/) { $cflags=$1; }
	if ($log =~ /configure options: (.*)/) { $config=$1; }
    }

    if ($err) {
	$err = util::cgi_escape($err);
    }

    print "<h2>Host information:</h2>\n";

    print util::FileLoad("../web/$host.html");

    print "
<table class=\"real\">
<tr><td>Host:</td><td><a href=\"$myself?function=Summary;host=$host;tree=$tree;compiler=$compiler#$host\">$host</a> - $hosts{$host}</td></tr>
<tr><td>Uname:</td><td>$uname</td></tr>
<tr><td>Tree:</td><td>$tree</td></tr>
<tr><td>Build Revision:</td><td>" . $rev . "</td></tr>
<tr><td>Build age:</td><td class=\"age\">" . red_age($age) . "</td></tr>
<tr><td>Status:</td><td>$status</td></tr>
<tr><td>Compiler:</td><td>$compiler</td></tr>
<tr><td>CFLAGS:</td><td>$cflags</td></tr>
<tr><td>configure options:  </td><td>$config</td></tr>
</table>
";

    # check the head of the output for our magic string 
    my $plain_logs = (defined $req->param("plain") &&
		      $req->param("plain") =~ /^(yes|1|on|true|y)$/i);

    print "<div id=\"log\">\n";

    if (!$plain_logs) {

	    print "<p>Switch to the <a href=\"$myself?function=View+Build;host=$host;tree=$tree;compiler=$compiler;plain=true\" title=\"Switch to bland, non-javascript, unstyled view\">Plain View</a></p>";

	    print "<div id=\"actionList\">\n";
	    # These can be pretty wide -- perhaps we need to 
	    # allow them to wrap in some way?
	    if ($err eq "") {
		    print "<h2>No error log available</h2>\n";
	    } else {
		    print "<h2>Error log:</h2>\n";
		    print make_action_html("Error Output", "\n$err", "stderr-0");;
	    }

	    if ($log eq "") {
		    print "<h2>No build log available</h2>\n";
	    } else {
		    print "<h2>Build log:</h2>\n";
		    print_log_pretty($log);
	    }

	    print "<p><small>Some of the above icons derived from the <a href=\"http://www.gnome.org\">Gnome Project</a>'s stock icons.</p>";
	    print "</div>\n";
    }
    else {
	    print "<p>Switch to the <a href=\"$myself?function=View+Build;host=$host;tree=$tree;compiler=$compiler\" title=\"Switch to colourful, javascript-enabled, styled view \">Enhanced View</a></p>";
	    if ($err eq "") {
		    print "<h2>No error log available</h2>\n";
	    } else {
		    print "<h2>Error log:</h2>\n";
		    print "<div id=\"errorLog\"><pre>" . join('', $err) . "</pre></div>\n";
	    }
	    if ($log eq "") {
		    print "<h2>No build log available</h2>n";
	    }
	    else {
		    print "<h2>Build log:</h2>\n";
		    print "<div id=\"buildLog\"><pre>" . join('', $log) . "</pre></div>\n";
	    }
    }

    print "</div>\n";
}

##############################################
# prints the log in a visually appealing manner
sub print_log_pretty() {
  my $log = shift;


  # do some pretty printing for the actions
  my $id = 1;
  $log =~ s{   Running\ action\s+([\w\-]+)
	       (.*?)
	       ACTION\ (PASSED|FAILED):\ ([\w\-]+)
	     }{make_action_html($1, $2, $id++, $3)}exgs;
  
  $log =~ s{
	      --==--==--==--==--==--==--==--==--==--==--.*?
	      Running\ test\ ([\w-]+)\ \(level\ (\d+)\ (\w+)\).*?
	      --==--==--==--==--==--==--==--==--==--==--
              (.*?)
	      ==========================================.*?
	      TEST\ (FAILED|PASSED):(\ \(status\ (\d+)\))?.*?
	      ==========================================\s+
	     }{make_test_html($1, $4, $id++, $5)}exgs;


	print "<tt><pre>" .join('', $log) . "</pre></tt><p>\n";
}

##############################################
# generate html for a test section
sub make_test_html {
  my $name = shift;
  my $output = shift;
  my $id = shift;
  my $status = shift;

  my $return =  "</pre>" . # don't want the pre openned by action affecting us
               "<div class=\"test unit \L$status\E\" id=\"test-$id\">" .
                "<a href=\"javascript:handle('$id');\">" .
                 "<img id=\"img-$id\" name=\"img-$id\" src=\"";
  if (defined $status && $status eq "PASSED") {
    $return .= "icon_unhide_16.png";
  }
  else {
    $return .= "icon_hide_16.png";
  }
  $return .= "\" /> " .
                 "<div class=\"test name\">$name</div> " .
                "</a> " .
               "<div class=\"test status \L$status\E\">$status</div>" .
               "<div class=\"test output\" id=\"output-$id\">" .
                "<pre>$output</pre>" .
               "</div>" .
              "</div>" .
              "<pre>";    # open the pre back up
              
  return $return;
}

##############################################
# generate html for an action section
sub make_action_html {

  my $name = shift;
  my $output = shift;
  my $id = shift;
  my $status = shift;
  my $return = "<div class=\"action unit \L$status\E\" id=\"action-$id\">" .
                "<a href=\"javascript:handle('$id');\">" .
                 "<img id=\"img-$id\" name=\"img-$id\" src=\"";

  if (defined $status && ($status =~ /failed/i)) {
    $return .= 'icon_hide_24.png';
  }
  else {
    $return .= 'icon_unhide_24.png';
  }

  $return .= "\" /> " .
                  "<div class=\"action name\">$name</div>" .
                "</a> ";

  if (defined $status) {
    $return .= "<div class=\"action status \L$status\E\">$status</div>";
  }

  $return .= "<div class=\"action output\" id=\"output-$id\">" .
                 "<pre>Running action $name$output ACTION $status: $name</pre>" .
                "</div>".
               "</div>";

  return $return
}

##############################################
# simple html markup stripper
sub strip_html($) {
	my $string = shift;

	# get rid of comments
	$string =~ s/<!\-\-(.*?)\-\->/$2/g;

	# and remove tags.
	while ($string =~ s&<(\w+).*?>(.*?)</\1>&$2&) {
		;
	}

	return $string;
}


##############################################
# main page
sub main_menu() {
    print $req->startform("GET");
    print "<div id=\"build-menu\">\n";
    print $req->popup_menu(-name=>'host',
			   -values=>\@hosts,
			   -labels=>\%hosts) . "\n";
    print $req->popup_menu("tree", [sort (keys %trees, @pseudo_trees)]) . "\n";
    print $req->popup_menu("compiler", $compilers) . "\n";
    print "<br />\n";
    print $req->submit('function', 'View Build') . "\n";
    print $req->submit('function', 'Recent Checkins') . "\n";
    print $req->submit('function', 'Summary') . "\n";
    print $req->submit('function', 'Recent Builds') . "\n";
    print "</div>\n";
    print $req->endform() . "\n";
}


###############################################
# display top of page
sub page_top() {
    cgi_headers();
    chdir("$BASEDIR/data") || fatal("can't change to data directory");
}


###############################################
# main program
my $fn_name = (defined $req->param('function')) ? $req->param('function') : '';

if ($fn_name eq 'text_diff') {
  cgi_headers_diff();
  chdir("$BASEDIR/data") || fatal("can't change to data directory");
  history::diff($req->param('author'),
		$req->param('date'),
		$req->param('tree'),
		$req->param('revision'),
		"text");
}
elsif ($fn_name eq 'Text_Summary') {
	cgi_headers_text();
	chdir("$BASEDIR/data") || fatal("can't change to data directory");
	view_summary('text');
}
else {
  page_top();

  if    ($fn_name eq "View Build") {
    view_build();
  }
  elsif ($fn_name eq "Recent Builds") {
    view_recent_builds();
  }
  elsif ($fn_name eq "Recent Checkins") {
    history::history($req->param('tree'));
  }
  elsif ($fn_name eq "diff") {
    history::diff($req->param('author'),
		  $req->param('date'),
		  $req->param('tree'),
		  $req->param('revision'),
		  "html");
  }
  else {
    view_summary('html');
  }
  cgi_footers();
}

