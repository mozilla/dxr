#!/usr/bin/env python2
import sqlite3
import re

# Returns tuples with [ path, basename ] for the given match string
def getFileMatches(conn, match_string):
  match_string = re.sub('["\']', '', match_string)
  for row in conn.execute('SELECT (SELECT path from files where ID = fts.rowid), fts.basename ' +
                          'FROM fts where fts.basename MATCH ?', ('"%s"' % match_string,)).fetchall():
    yield row

def filterByPath(query_str, args, path, col='file_id', ext=None):
  if ext is not None and path is not None:
    like_str = '%s/%%%s' % (path, ext)
  elif ext is not None:
    like_str = '%%%s' % (ext,)
  else:
    like_str = '%s/%%' % (path,)

  query_str += 'AND %s IN (SELECT ID FROM files WHERE path like ?)' % (col,)
  args.append(like_str)
  return query_str, args

# Returns tuples with [ path, lineno, linestr ] for the given match string
def getFTSMatches(conn, match_string, path=None, ext=None):
  match_string = re.sub('["\']', '', match_string)
  terms = match_string.strip().split(' ')

  if len(terms) > 1:
    str = '"%s"' % ('" NEAR "'.join(terms),)
  elif terms[0].find('-') != -1:
    str = '"%s"' % (terms[0],)
  else:
    str = '%s*' % (terms[0],)

  query_str = """SELECT (SELECT path from files where ID = fts.rowid), 
                 fts.content, offsets(fts) FROM fts where fts.content
                 MATCH ? """
  args = [str]

  if path is not None or ext is not None:
    query_str, args = filterByPath(query_str, args, path, "fts.rowid", ext)

  for row in conn.execute(query_str, args).fetchall():
    line_count = 0
    last_pos = 0

    content = row[1]
    offsets = row[2].split();
    offsets = [offsets[i:i+4] for i in xrange(0, len(offsets), 4)]

    for off in offsets:
      line_diff = content.count("\n", last_pos, int (off[2]))
      last_pos = int(off[2])
      if line_diff == 0:
        continue

      line_count += line_diff
      line_str = content [content.rfind ("\n", 0, int (off[2]) + 1) :
                          content.find ("\n", int (off[2]))]

      yield [row[0], line_count, line_str]

# Returns tuples with [ path, lineno, linestr ] for the given match string
def getRegexMatches(conn, match_string, path=None, ext=None):
  query_str = """SELECT (SELECT path from files where ID = fts.rowid),
                 fts.content FROM fts where fts.content REGEXP (?) """
  args = [match_string]

  if path is not None or ext is not None:
    query_str, args = filterByPath(query_str, args, path, "fts.rowid", ext)

  for row in conn.execute(query_str, args).fetchall():
    line_count = 0
    last_pos = 0
    content = row[1]

    for m in re.finditer (match_string, row[1]):
      offset = m.start ()

      line_diff = content.count("\n", last_pos, offset)
      last_pos = offset

      if line_diff == 0:
        continue

      line_count += line_diff
      line_str = content [content.rfind ("\n", 0, offset + 1) :
                          content.find ("\n", offset)]

      yield [row[0], line_count, line_str]

def getMacroMatches(conn, match_string):
  for row in conn.execute('SELECT macroname, file_line, (SELECT path FROM files where files.ID = macros.file_id) FROM macros WHERE macroname LIKE ?', ('%s%%' % match_string,)).fetchall():
    yield [row[0], row[2], row[1]]

def getFunctionMatches(conn, match_string):
  for row in conn.execute('SELECT fqualname, fargs, ftype, file_line, (SELECT path FROM files WHERE files.ID = functions.file_id) FROM functions WHERE fqualname LIKE ?', ('%%%s%%' % match_string,)).fetchall():
    yield [row[0], row[1], row[2], row[4], row[3]]

def getVariableMatches(conn, match_string):
  for row in conn.execute('SELECT vname, vtype, file_line, (SELECT path FROM files WHERE files.ID = variables.file_id) FROM variables WHERE vname LIKE ?', ('%%%s%%' % match_string,)).fetchall():
    yield [row[0], row[1], row[3], row[2]]

def getWarningMatches(conn, match_string):
  for row in conn.execute("SELECT wmsg, file_line, (SELECT path FROM files WHERE files.ID = warnings.file_id) FROM warnings WHERE wmsg LIKE ?", ('%%%s%%' % match_string,)).fetchall():
    yield [row[0], row[2], row[1]]

def getCallers(conn, match_string):
  for row in conn.execute("SELECT functions.fqualname, functions.file_line, " +
                          " (SELECT path FROM files WHERE files.ID = functions.file_id) " +
                          "FROM functions " +
                          "LEFT JOIN callers ON (callers.callerid = funcid) " +
                          "WHERE callers.targetid = (SELECT funcid FROM functions where fname = ?) " +
                          "UNION " +
                          "SELECT functions.fqualname, functions.file_line, " +
                          " (SELECT path FROM files WHERE files.ID = functions.file_id) " +
                          "FROM functions " +
                          "LEFT JOIN callers ON (callers.callerid = functions.funcid) " +
                          "LEFT JOIN targets USING (targetid) " +
                          "WHERE targets.funcid = (SELECT funcid FROM functions where fname = ?)",
                          (match_string, match_string)):
    yield [row[0], row[2], row[1]]
