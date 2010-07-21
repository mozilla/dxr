#!/usr/bin/env python

"""
Modified from http://hg.mozilla.org/users/bsmedberg_mozilla.com/static-analysis-buildbot/file/19e7a98a8dc4/warning-parser.py

Assumes filenames in warnings use abs/real paths, see:
https://bugzilla.mozilla.org/show_bug.cgi?id=579203

Reads a build log on stdin. Parse warning messages (from GCC and elsewhere)
and store them in a sqlite database for later consumption.
"""

import sys, os, re

(srcdir, objdir, logfile) = sys.argv[1:]
srcdir = os.path.realpath(srcdir) + '/'
objdir = os.path.realpath(objdir) + '/'

# Remember current working dir so we can pick-out files missing full path later.
cwd = os.getcwd()

warningre = re.compile(r'(?P<file>[-/\.\w<>]+):((?P<line>\d+):)?(\d+:)? warning: (?P<msg>[^ ].*)$')

curid = -1

for line in open(logfile):
    line = line.strip()

    m = warningre.match(line)
    if m is None:
        continue

    curid += 1

    file, lineno, msg = m.group('file', 'line', 'msg')

    # Skip non-source loc warnings from configure and command line arg issues
    if file == 'configure' or file.endswith('<command-line>'):
        continue

    if lineno is not None:
        lineno = int(lineno)

    file = os.path.realpath(file)

    if file.startswith(srcdir):
        file = file[len(srcdir):]

    # Skip non-source loc warnings from objdir, and any files that 
    # now claim to be rooted in cwd, since this means we never had
    # an abs path, and just a filename.
    if not file.startswith(objdir) and not file.startswith(cwd):
        # fix-up gcc's quotes
        msg = msg.replace("\xe2\x80\x98", "'").replace("\xe2\x80\x99", "'")
        print "insert into warnings (wid,wfile,wloc,wmsg) values (%s,\"%s\",%s,\"%s\");" % (curid, file, lineno, msg.replace('"',"'")) 
