#!/bin/sh

sqlite3 `dirname $0`/hostdb.sqlite 'VACUUM;'
cd `dirname $0` && exec ./mail-dead-hosts.pl

# delete old ones that are not used any more
find oldrevs -type f -mtime +4 -links 1 -print0 | xargs -i -0 rm -f \{\}

# delete any really old data
find . -type f -mtime +120  -print0 | xargs -i -0 rm -f \{\}

# delete old cache data
find ../cache -type f -name "build.*" -mtime +1 -print0 | xargs -i -0 rm -f \{\}

# delete partially uploaded files (crashed rsync)
find . -type f -mtime +2 -name ".build.*" -print0 | xargs -i -0 rm -f \{\}
