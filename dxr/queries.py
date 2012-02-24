#!/usr/bin/env python2
import sqlite3
import re

# Returns tuples with [ path, basename ] for the given match string
def getFileMatches(conn, match_string):
  for row in conn.execute('SELECT (SELECT path from files where ID = fts.rowid), fts.basename ' +
                          'FROM fts where fts.basename MATCH \'%s\'' % match_string).fetchall():
    yield row

# Returns tuples with [ path, lineno, linestr ] for the given match string
def getFTSMatches(conn, match_string):
  for row in conn.execute('SELECT (SELECT path from files where ID = fts.rowid), ' +
                          ' fts.content, offsets(fts) FROM fts where fts.content ' +
                          'MATCH \'%s\'' % match_string).fetchall():
    line_count = 0
    last_pos = 0

    content = row[1]
    offsets = row[2].split();
    offsets = [offsets[i:i+4] for i in xrange(0, len(offsets), 4)]

    for off in offsets:
      line_count += content.count ("\n", last_pos, int (off[2]))
      last_pos = int (off[2])

      line_str = content [content.rfind ("\n", 0, int (off[2]) + 1) :
                          content.find ("\n", int (off[2]))]

      yield [row[0], line_count, line_str]

# Returns tuples with [ path, lineno, linestr ] for the given match string
def getRegexMatches(conn, match_string):
  for row in conn.execute('SELECT (SELECT path from files where ID = fts.rowid),' +
                          'fts.content FROM fts where fts.content REGEXP (\'%s\')' % match_string).fetchall():
    line_count = 0
    last_pos = 0
    content = row[1]

    for m in re.finditer (match_string, row[1]):
      offset = m.start ()

      line_count += content.count ("\n", last_pos, offset)
      last_pos = offset

      line_str = content [content.rfind ("\n", 0, offset + 1) :
                          content.find ("\n", offset)]

      yield [row[0], line_count, line_str]

