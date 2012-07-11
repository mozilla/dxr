import utils

# Register filters by adding them to this list.
# A filter takes a query and yield triples of
#     (table list, conditions as string and list of arguments)
filters = []

# Register extents generators builders for results, by adding them to this list.
# An extents generators builder takes a query and yields extents generators.
# An extents generator takes a connection and a file-id and yields 4-tuples of
#     (extent_start, extent_end, markup, markdown)
# Where tuples are ordered by extent-start and never overlaps.
# These are used to highlight interesting keywords in the results.
#
# Remarks: Any extents generator should always highlight at least one extent for
# any results that matches the query it was created for.
# (This can be achieved by restricting the results with a filter)
extents_builders = []

# TODO
# Okay, to get perfect search results... We need for following:
#   - plugins should return one or more query for interesting extents of a file
#        (They should also be able to add links, etc.)
#   - if query["keywords"] is empty, don't add the MATCH clause it's not needed
#       (lookup for content is still necessary, but rowid is also indexed)
#   - if none of the plugins choses to return an extents query,
#       we can't show lines from the file, so we just show file names...
#   - Special argument files-only to just search for file names
#   - If no plugin returns an extents query, don't fetch content
#   - Method for merging extends from different sources
#      (this MUST be a reusable function)


# Fetch results using a query,
# See: queryparser.py for details in query specification
def fetch_results(conn, query,
                  limit = 100, offset = 0,
                  markup = "<b>", markdown = "</b>"):
  sql = "SELECT DISTINCT files.path, result.content, files.ID FROM %s WHERE %s LIMIT ? OFFSET ?"
  tables = ["fts AS result", "files"]
  conditions = " files.ID = result.rowid "
  arguments = []

  for f in filters:
    for tbls, conds, args in f(query):
      for tb in tbls:
        if tb not in tables:
          tables.append(tb)
      if conds:
        conditions += " AND " + conds
      arguments += args
  sql %= (" , ".join(tables), conditions)
  arguments += [limit, offset]

  extent_gens = []
  for builder in extents_builders:
    extent_gens += list(builder(query))
 
  utils.log(sql)
  utils.log(query)

  for path, content, fileid in conn.execute(sql, arguments):
    elist = [eg(conn, fileid) for eg in extent_gens]

    offsets = list(merge_extents(*elist))

    lines = []
    line_number = 1
    last_pos = 0

    for i in xrange(0, len(offsets)):
      offset, size, m1, m2 = offsets[i]
      size -= offset

      # Skip if we didn't get a new line
      line_diff = content.count("\n", last_pos, offset)
      if line_diff == 0 and last_pos > 0:
        continue 
      line_number += line_diff
      last_pos = offset

      # Find newline before and after offset
      end   = content.find ("\n", offset)
      start = max(content.rfind("\n", 0, end), 0)
      line  = content[start:end]

      # Add some markup to highlight hits
      fill = 0
      while content.count("\n", last_pos, offset) == 0:
        mstart = offset - start + fill
        mend   = mstart + size
        line = line[:mstart] + markup + line[mstart:mend] + markdown + line[mend:]
        fill += len(markup) + len(markdown)
        i += 1
        if i >= len(offsets):
          break
        offset, size, m1, m2 = offsets[i]
        size -= offset

      lines.append((line_number, line))
    # Return result
    yield path, lines

"""
  for path, content, offsets in conn.execute(sql, arguments):
    # Split offsets at spaces and find the lines for each of them
    offsets = offsets.split()
    offsets = [offsets[i:i+4] for i in xrange(0, len(offsets), 4)]

    lines = []
    line_number = 1
    last_pos = 0

    for i in xrange(0, len(offsets)):
      col, term, offset, size = offsets[i]
      offset = int(offset)
      size = int(size)

      # Skip if we didn't get a new line
      line_diff = content.count("\n", last_pos, offset)
      if line_diff == 0 and last_pos > 0:
        continue 
      line_number += line_diff
      last_pos = offset

      # Find newline before and after offset
      end   = content.find ("\n", offset)
      start = max(content.rfind("\n", 0, end), 0)
      line  = content[start:end]

      # Add some markup to highlight hits
      fill = 0
      while content.count("\n", last_pos, offset) == 0:
        mstart = offset - start + fill
        mend   = mstart + size
        line = line[:mstart] + markup + line[mstart:mend] + markdown + line[mend:]
        fill += len(markup) + len(markdown)
        i += 1
        if i >= len(offsets):
          break
        col, term, offset, size = offsets[i]
        offset = int(offset)
        size = int(size)

      lines.append((line_number, line))
    # Return result
    yield path, lines
"""




def like_escape(val):
  """ Escape for usage in as argument to the LIKE operator """
  return val.replace("\\", "\\\\").replace("_", "\\_").replace("%", "\\%")


class genWrap:
  """ Auxiliary class for wrapping a generator and make it nicer """
  def __init__(self, gen):
    self.gen = gen
    self.value = None
  def next(self):
    try:
      self.value = self.gen.next()
      return True
    except StopIteration:
      self.value = None
      return False

def merge_extents(*elist):
  """
    Take a list of extents generators and merge them into one stream of extents
    overlapping extents will be split in two, this means that they will start
    and stop at same location.
    Here we assume that each extent is a tuple of five as follows:
      (start, end, markup, markdown, splitable)
    
    Markup/down are the markup used to signify beginning or end of extent.
    We assume that markup/down can be applied multiple times, if this extent
    overlaps another extent.
    For example:
      <b>keyword</b> works just as fine as <b>key</b><b><i>word</i></b>
      (In this case both keyword and word are highlighted up).
  """
  elist = [genWrap(e) for e in elist]
  elist = [e for e in elist if e.next()]
  while len(elist) > 0:
    start = min((e.value[0] for e in elist))
    end = min((e.value[1] for e in elist if e.value[0] == start))
    markup = ""
    markdown = ""
    for e in (e for e in elist if e.value[0] == start):
      markup = markup + e.value[2]
      markdown = e.value[3] + markdown
      e.value = (end, e.value[1], e.value[2], e.value[3])
    yield start, end, markup, markdown
    elist = [e for e in elist if e.value[0] < e.value[1] or e.next()]




def apply_extents(extents):
  pass


# Stupid builtin filters
# TODO Write these into the fetch_results method, matching twice just to get
# extents in a different function it not efficient

def filter_fts(query):
  """ Filter results using full text search """
  if query["fts_query"] and query["fts_query"] != "":
    yield ([], "result.content MATCH ?", [query["fts_query"]])
filters.append(filter_fts)

def extents_builder_fts(query):
  sql = """
    SELECT offsets(fts) FROM fts WHERE fts.content MATCH ? AND fts.rowid = ?
  """
  if query["fts_query"] and query["fts_query"] != "":
    def extents_fts(conn, fileid):
      offsets = conn.execute(sql, (query["fts_query"], fileid)).fetchone()
      offsets = offsets[0].split()
      offsets = [offsets[i:i+4] for i in xrange(0, len(offsets), 4)]
      for col, term, start, size in offsets:
        yield (int(start), int(start) + int(size), "<b>", "</b>")
    yield extents_fts
extents_builders.append(extents_builder_fts)

# Builtin filters

def filter_path(query):
  """ Filter results by the path argument """
  for path in query["parameters"].get("path") or []:
    yield ([], 'files.path LIKE ? ESCAPE "\\"', ['%' + like_escape(path) + '%'])
  for path in query["parameters"].get("-path") or []:
    yield ([], 'files.path NOT LIKE ? ESCAPE "\\"', ['%' + like_escape(path) + '%'])
filters.append(filter_path)

def filter_ext(query):
  """ Filter results by file extension """
  for ext in query["parameters"].get("ext") or []:
    yield ([], 'files.path LIKE ? ESCAPE "\\"', ['%' + like_escape(ext)])
  for ext in query["parameters"].get("-ext") or []:
    yield ([], 'files.path NOT LIKE ? ESCAPE "\\"', ['%' + like_escape(ext)])
filters.append(filter_ext)


def filter_type(query):
  """ Filter results to only type declarations """
  for tp in query["parameters"].get("type") or []:
    yield (
            ['types'],
            """
              types.tname LIKE ? ESCAPE "\\" AND
              types.file_id = files.ID
            """,
            ['%' + like_escape(tp) + '%']
          )
  for tp in query["parameters"].get("-type") or []:
    yield (
            [],
            """
              NOT EXISTS (
                SELECT 1 FROM types as mt WHERE
                  mt.tname LIKE ? ESCAPE "\\" AND
                  mt.file_id = files.ID
              )
            """,
            ['%' + like_escape(tp) + '%']
          )
filters.append(filter_type)


# Filters belonging to the cxx-lang plugin

def filter_typeref(query):
  """ Filter results by type references """
  for tp in query["parameters"].get("type-ref") or []:
    yield (
              ['types', 'refs'],
              """
                types.tname LIKE ? ESCAPE "\\" AND
                types.tid = refs.refid AND
                refs.file_id = files.ID
              """,
              ['%' + like_escape(tp) + '%']
           )
  for tp in query["parameters"].get("-type-ref") or []:
    yield (
              [],
              """
                NOT EXISTS (
                  SELECT 1 FROM types as mt, refs WHERE
                    mt.tname LIKE ? ESCAPE "\\" AND
                    mt.tid = refs.refid AND
                    refs.file_id = files.ID
                )
              """,
              ['%' + like_escape(tp) + '%']
           )

filters.append(filter_typeref)

def extents_builder_typeref(query):
  """ Returns an extents generators for type references """
  sql = """
        SELECT DISTINCT refs.extent_start, refs.extent_end
        FROM refs, files, types
        WHERE types.tname LIKE ? ESCAPE "\\"
          AND types.tid = refs.refid
          AND refs.file_id = ?
  """
  for tp in query["parameters"].get("type-ref") or []:
    def extents_typeref(conn, fileid):
      for start, end in conn.execute(sql, ('%' + like_escape(tp) + '%', fileid)):
        yield (start, end, "<b>", "</b>")
    yield extents_typeref
extents_builders.append(extents_builder_typeref)


def filter_funcref(query):
  """ Filter results by function references """
  # Lets allow for a few different aliases
  for fref in query["parameters"].get("function-ref") or []:
    yield (
              ['functions', 'refs'],
              """
                functions.fname LIKE ? ESCAPE "\\" AND
                functions.funcid = refs.refid AND
                refs.file_id = files.ID
              """,
              ['%' + like_escape(fref) + '%']
           )
  for fref in query["parameters"].get("-function-ref") or []:
    yield (
              [],
              """
                NOT EXISTS (
                  SELECT 1 FROM functions, refs WHERE
                    functions.fname LIKE ? ESCAPE "\\" AND
                    functions.funcid = refs.refid AND
                    refs.file_id = files.ID
                )
              """,
              ['%' + like_escape(fref) + '%']
           )
filters.append(filter_funcref)

def extents_builder_funcref(query):
  """ Returns extents generators for function references """
  sql = """
        SELECT DISTINCT refs.extent_start, refs.extent_end
        FROM refs, files, functions
        WHERE functions.fname LIKE ? ESCAPE "\\"
          AND functions.funcid = refs.refid
          AND refs.file_id = ?
  """
  for fref in query["parameters"].get("function-ref") or []:
    def extents_funcref(conn, fileid):
      for start, end in conn.execute(sql, ('%' + like_escape(fref) + '%', fileid)):
        yield (start, end, "<b>", "</b>")
    yield extents_funcref
extents_builders.append(extents_builder_funcref)


def filter_macroref(query):
  """ Filter results by macro references """
  # Lets allow for a few different aliases
  for mref in query["parameters"].get("macro-ref") or []:
    yield (
              ['macros', 'refs'],
              """
                macros.macroname LIKE ? ESCAPE "\\" AND
                macros.macroid = refs.refid AND
                refs.file_id = files.ID
              """,
              ['%' + like_escape(mref) + '%']
           )
  for mref in query["parameters"].get("-macro-ref") or []:
    yield (
              [],
              """
                NOT EXISTS (
                  SELECT 1 FROM macros, refs WHERE
                    macros.macroname LIKE ? ESCAPE "\\" AND
                    macros.macroid = refs.refid AND
                    refs.file_id = files.ID
                )
              """,
              ['%' + like_escape(mref) + '%']
           )
filters.append(filter_macroref)

def extents_builder_macroref(query):
  """ Returns extents generators for macro references """
  sql = """
        SELECT DISTINCT refs.extent_start, refs.extent_end
        FROM refs, files, macros
        WHERE macros.macroname LIKE ? ESCAPE "\\"
          AND macros.macroid = refs.refid
          AND refs.file_id = ?
  """
  for mref in query["parameters"].get("macro-ref") or []:
    def extents_macroref(conn, fileid):
      for start, end in conn.execute(sql, ('%' + like_escape(mref) + '%', fileid)):
        yield (start, end, "<b>", "</b>")
    yield extents_macroref
extents_builders.append(extents_builder_macroref)


