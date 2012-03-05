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

def getMacroMatches(conn, match_string):
  for row in conn.execute('SELECT macroname, macroloc FROM macros WHERE macroname LIKE ?', ('%s%%' % match_string,)).fetchall():
    loc = row[1].split(':')
    yield [row[0], loc[0], int(loc[1])]

def getFunctionMatches(conn, match_string):
  for row in conn.execute('SELECT fqualname, fargs, ftype, floc FROM functions WHERE fqualname LIKE ?', ('%%%s%%' % match_string,)).fetchall():
    loc = row[3].split(':')
    yield [row[0], row[1], row[2], loc[0], int(loc[1])]

def getVariableMatches(conn, match_string):
  for row in conn.execute('SELECT vname, vtype, vloc FROM variables WHERE vname LIKE ?', ('%%%s%%' % match_string,)).fetchall():
    loc = row[2].split(':')
    yield [row[0], row[1], loc[0], int(loc[1])]

def getWarningMatches(conn, match_string):
  for row in conn.execute("SELECT wmsg, wloc FROM warnings WHERE wmsg LIKE ?", ('%%%s%%' % match_string,)).fetchall():
    loc = row[1].split(':')
    yield [row[0], loc[0], int(loc[1])]

def getCallers(conn, match_string):
  for row in conn.execute("SELECT functions.fqualname, functions.floc FROM functions " +
                          "LEFT JOIN callers ON (callers.callerid = funcid) " +
                          "WHERE callers.targetid = (SELECT funcid FROM functions where fname = ?) " +
                          "UNION " +
                          "SELECT functions.fqualname, functions.floc FROM functions " +
                          "LEFT JOIN callers ON (callers.callerid = functions.funcid) " +
                          "LEFT JOIN targets USING (targetid) " +
                          "WHERE targets.funcid = (SELECT funcid FROM functions where fname = ?)",
                          (match_string, match_string)):
    loc = row[1].split(':')
    yield [row[0], loc[0], int(loc[1])]
