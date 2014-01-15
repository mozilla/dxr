import cgi
from itertools import chain, groupby
import re
import struct
import time

from parsimonious import Grammar
from parsimonious.nodes import NodeVisitor


# TODO: Some kind of UI feedback for bad regexes


# TODO
#   - Special argument files-only to just search for file names
#   - If no plugin returns an extents query, don't fetch content


# Pattern for matching a file and line number filename:n
_line_number = re.compile("^.*:[0-9]+$")

class Query(object):
    """Query object, constructor will parse any search query"""

    def __init__(self, conn, querystr, should_explain=False, is_case_sensitive=True):
        self.conn = conn
        self._should_explain = should_explain
        self._sql_profile = []
        self.is_case_sensitive = is_case_sensitive

        # A dict with a key for each filter type (like "regexp") in the query.
        # There is also a special "text" key where free text ends up.
        self.terms = QueryVisitor(is_case_sensitive=is_case_sensitive).visit(query_grammar.parse(querystr))

    def single_term(self):
        """Return the single textual term comprising the query.

        If there is more than one term in the query or if the single term is a
        non-textual one, return None.

        """
        if self.terms.keys() == ['text'] and len(self.terms['text']) == 1:
            return self.terms['text'][0]['arg']

    #TODO Use named place holders in filters, this would make the filters easier to write

    def execute_sql(self, sql, *parameters):
        if self._should_explain:
            self._sql_profile.append({
                "sql" : sql,
                "parameters" : parameters[0] if len(parameters) >= 1 else [],
                "explanation" : self.conn.execute("EXPLAIN QUERY PLAN " + sql, *parameters)
            })
            start_time = time.time()
        res = self.conn.execute(sql, *parameters)
        if self._should_explain:
            # fetch results eagerly so we can get an accurate time for the entire operation
            res = res.fetchall()
            self._sql_profile[-1]["elapsed_time"] = time.time() - start_time
            self._sql_profile[-1]["nrows"] = len(res)
        return res

    # Fetch results using a query,
    # See: queryparser.py for details in query specification
    def results(self,
                offset=0, limit=100,
                markup='<b>', markdown='</b>'):
        """Return search results as an iterable of these::

            (icon,
             path within tree,
             (line_number, highlighted_line_of_code)), ...

        """
        sql = """
            SELECT files.path, files.icon, files.encoding, trg_index.text, files.id,
            extents(trg_index.contents)
                FROM trg_index, files
              WHERE %s ORDER BY files.path LIMIT ? OFFSET ?
        """
        conditions = " files.id = trg_index.id "
        arguments = []

        # Give each registered filter an opportunity to contribute to the
        # query. This query narrows down the universe to a set of matching
        # files:
        has_extents = False
        for f in filters:
            for conds, args, exts in f.filter(self.terms):
                has_extents = exts or has_extents
                conditions += " AND " + conds
                arguments += args

        sql %= conditions
        arguments += [limit, offset]

        #TODO Actually do something with the has_extents, ie. don't fetch contents

        cursor = self.execute_sql(sql, arguments)

        # For each returned file (including, only in the case of the trilite
        # filter, a set of extents)...
        for path, icon, encoding, content, file_id, extents in cursor:
            elist = []

            # Special hack for TriLite extents
            if extents:
                matchExtents = []
                for i in xrange(0, len(extents), 8):
                    s, e = struct.unpack("II", extents[i:i+8])
                    matchExtents.append((s, e, []))
                elist.append(fix_extents_overlap(sorted(matchExtents)))

            # Let each filter do one or more additional queries to find the
            # extents to highlight:
            for f in filters:
                for e in f.extents(self.terms, self.execute_sql, file_id):
                    elist.append(e)
            offsets = list(merge_extents(*elist))

            if self._should_explain:
                continue

            # Yield the file, metadata, and iterable of highlighted offsets:
            yield icon, path, _highlit_lines(content, offsets, markup, markdown, encoding)


        # TODO: Decouple and lexically evacuate this profiling stuff from
        # results():
        def number_lines(arr):
            ret = []
            for i in range(len(arr)):
                if arr[i] == "":
                    ret.append((i, " "))  # empty lines cause the <div> to collapse and mess up the formatting
                else:
                    ret.append((i, arr[i]))
            return ret

        for i in range(len(self._sql_profile)):
            profile = self._sql_profile[i]
            yield ("",
                          "sql %d (%d row(s); %s seconds)" % (i, profile["nrows"], profile["elapsed_time"]),
                          number_lines(profile["sql"].split("\n")))
            yield ("",
                          "parameters %d" % i,
                          number_lines(map(lambda parm: repr(parm), profile["parameters"])));
            yield ("",
                          "explanation %d" % i,
                          number_lines(map(lambda row: row["detail"], profile["explanation"])))


    def direct_result(self):
        """Return a single search result that is an exact match for the query.

        If there is such a result, return a tuple of (path from root of tree,
        line number). Otherwise, return None.

        """
        term = self.single_term()
        if not term:
            return None
        cur = self.conn.cursor()

        line_number = -1
        if _line_number.match(term):
            parts = term.split(":")
            if len(parts) == 2:
                term = parts[0]
                line_number = int(parts[1])

        # See if we can find only one file match
        cur.execute("""
            SELECT path FROM files WHERE
                path = :term
                OR path LIKE :termPre 
            LIMIT 2
        """, {"term": term,
              "termPre": "%/" + term})

        rows = cur.fetchall()
        if rows and len(rows) == 1:
            if line_number >= 0:
                return (rows[0]['path'], line_number)
            return (rows[0]['path'], 1)

        # Case sensitive type matching
        cur.execute("""
            SELECT
                (SELECT path FROM files WHERE files.id = types.file_id) as path,
                types.file_line
              FROM types WHERE types.name = ? LIMIT 2
        """, (term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Case sensitive function names
        cur.execute("""
            SELECT
                    (SELECT path FROM files WHERE files.id = functions.file_id) as path,
                    functions.file_line
                FROM functions WHERE functions.name = ? LIMIT 2
        """, (term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Try fully qualified names
        if '::' in term:
            # Case insensitive type matching
            cur.execute("""
                SELECT
                      (SELECT path FROM files WHERE files.id = types.file_id) as path,
                      types.file_line
                    FROM types WHERE types.qualname LIKE ? LIMIT 2
            """, (term,))
            rows = cur.fetchall()
            if rows and len(rows) == 1:
                return (rows[0]['path'], rows[0]['file_line'])

            # Case insensitive function names
            cur.execute("""
            SELECT
                  (SELECT path FROM files WHERE files.id = functions.file_id) as path,
                  functions.file_line
                FROM functions WHERE functions.qualname LIKE ? LIMIT 2
            """, (term + '%',))  # Trailing % to eat "(int x)" etc.
            rows = cur.fetchall()
            if rows and len(rows) == 1:
                return (rows[0]['path'], rows[0]['file_line'])

        # Case insensitive type matching
        cur.execute("""
        SELECT
              (SELECT path FROM files WHERE files.id = types.file_id) as path,
              types.file_line
            FROM types WHERE types.name LIKE ? LIMIT 2
        """, (term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Case insensitive function names
        cur.execute("""
        SELECT
              (SELECT path FROM files WHERE files.id = functions.file_id) as path,
              functions.file_line
            FROM functions WHERE functions.name LIKE ? LIMIT 2
        """, (term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Okay we've got nothing
        return None


def _highlit_line(content, offsets, markup, markdown, encoding):
    """Return a line of string ``content`` with the given ``offsets`` prefixed
    by ``markup`` and suffixed by ``markdown``.

    We assume that none of the offsets split a multibyte character.

    """
    def chunks():
        try:
            # Start on the line the highlights are on:
            chars_before = content.rindex('\n', 0, offsets[0][0]) + 1
        except ValueError:
            chars_before = None
        for start, end in offsets:
            yield cgi.escape(content[chars_before:start].decode(encoding,
                                                                'replace'))
            yield markup
            yield cgi.escape(content[start:end].decode(encoding, 'replace'))
            yield markdown
            chars_before = end
        # Make sure to get the rest of the line after the last highlight:
        try:
            next_newline = content.index('\n', chars_before)
        except ValueError:  # eof
            next_newline = None
        yield cgi.escape(content[chars_before:next_newline].decode(encoding,
                                                                   'replace'))
    return ''.join(chunks())


def _highlit_lines(content, offsets, markup, markdown, encoding):
    """Return a list of (line number, highlit line) tuples.

    :arg content: The contents of the file against which the offsets are
        reported, as a bytestring. (We need to operate in terms of bytestrings,
        because those are the terms in which the C compiler gives us offsets.)
    :arg offsets: A sequence of non-overlapping (start offset, end offset,
        [keylist (presently unused)]) tuples describing each extent to
        highlight. The sequence must be in order by start offset.

    Assumes no newlines are highlit.

    """
    line_extents = []  # [(line_number, (start, end)), ...]
    lines_before = 1
    chars_before = 0
    for start, end, _ in offsets:
        # How many lines we've skipped since we last knew what line we were on:
        lines_since = content.count('\n', chars_before, start)

        # Figure out what line we're on, and throw this extent into its bucket:
        line = lines_before + lines_since
        line_extents.append((line, (start, end)))

        lines_before = line
        chars_before = end

    # Bucket highlit ranges by line, and build up the marked up strings:
    return [(line, _highlit_line(content,
                                 [extent for line, extent in lines_and_extents],
                                 markup,
                                 markdown,
                                 encoding)) for
            line, lines_and_extents in groupby(line_extents, lambda (l, e): l)]


def like_escape(val):
    """Escape for usage in as argument to the LIKE operator """
    return (val.replace("\\", "\\\\")
               .replace("_", "\\_")
               .replace("%", "\\%")
               .replace("?", "_")
               .replace("*", "%"))

class genWrap(object):
    """Auxiliary class for wrapping a generator and make it nicer"""
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
        Here we assume that each extent is a triple as follows:
            (start, end, keyset)

        Where keyset is a list of something that should be applied to the extent
        between start and end.
    """
    elist = [genWrap(e) for e in elist]
    elist = [e for e in elist if e.next()]
    while len(elist) > 0:
        start = min((e.value[0] for e in elist))
        end = min((e.value[1] for e in elist if e.value[0] == start))
        keylist = []
        for e in (e for e in elist if e.value[0] == start):
            for k in e.value[2]:
                if k not in keylist:
                    keylist.append(k)
            e.value = (end, e.value[1], e.value[2])
        yield start, end, keylist
        elist = [e for e in elist if e.value[0] < e.value[1] or e.next()]


def fix_extents_overlap(extents):
    """
        Take a sorted list of extents and yield the extents without overlapings.
        Assumes extents are of similar format as in merge_extents
    """
    # There must be two extents for there to be an overlap
    while len(extents) >= 2:
        # Take the two next extents
        start1, end1, keys1 = extents[0]
        start2, end2, keys2 = extents[1]
        # Check for overlap
        if end1 <= start2:
            # If no overlap, yield first extent
            yield start1, end1, keys1
            extents = extents[1:]
            continue
        # If overlap, yield extent from start1 to start2
        if start1 != start2:
            yield start1, start2, keys1
        extents[0] = (start2, end1, keys1 + keys2)
        extents[1] = (end1, end2, keys2)
    if len(extents) > 0:
        yield extents[0]


class SearchFilter(object):
    """Base class for all search filters, plugins subclasses this class and
            registers an instance of them calling register_filter
    """
    def filter(self, terms):
        """Yield tuples of SQL conditions, list of arguments, and True if this
        filter offers extents for results.

        SQL conditions must be string and condition on files.id.

        :arg terms: A dictionary with keys for each filter name I handle (as
            well as others, possibly, which should be ignored). Example::

                {'function': [{'arg': 'o hai',
                               'not': False,
                               'case_sensitive': False,
                               'qualified': False},
                               {'arg': 'what::next',
                                'not': True,
                                'case_sensitive': False,
                                'qualified': True}],
                  ...}

        """
        return []

    def extents(self, terms, execute_sql, file_id):
        """Return an ordered iterable of extents to highlight. Or an iterable
        of generators. It seems to vary.

        :arg execute_sql: A callable that takes some SQL and an iterable of
            params and executes it, returning the result
        :arg file_id: The ID of the file from which to return extents
        :arg kwargs: A dictionary with keys for each filter name I handle (as
            well as others, possibly), as in filter()

        """
        return []

    def names(self):
        """Return a list of filter names this filter handles.

        This smooths out the difference between the trilite filter (which
        handles 2 different params) and the other filters (which handle only 1).

        """
        return [self.param] if hasattr(self, 'param') else self.params


class TriLiteSearchFilter(SearchFilter):
    params = ['text', 'regexp']

    def filter(self, terms):
        not_conds = []
        not_args  = []
        for term in terms.get('text', []):
            if term['arg']:
                if term['not']:
                    not_conds.append("trg_index.contents MATCH ?")
                    not_args.append(('substr:' if term['case_sensitive']
                                               else 'isubstr:') +
                                    term['arg'])
                else:
                    yield ("trg_index.contents MATCH ?",
                           [('substr-extents:' if term['case_sensitive']
                                               else 'isubstr-extents:') +
                            term['arg']],
                           True)
        for term in terms.get('regexp', []):
            if term['arg']:
                if term['not']:
                    not_conds.append("trg_index.contents MATCH ?")
                    not_args.append("regexp:" + term['arg'])
                else:
                    yield ("trg_index.contents MATCH ?",
                           ["regexp-extents:" + term['arg']],
                           True)

        if not_conds:
            yield (""" files.id NOT IN (SELECT id FROM trg_index WHERE %s) """
                       % " AND ".join(not_conds),
                   not_args,
                   False)

    # Notice that extents is more efficiently handled in the search query
    # Sorry to break the pattern, but it's significantly faster.


class SimpleFilter(SearchFilter):
    """Search filter for limited results.
            This filter take 5 parameters, defined as follows:
                param           Search parameter from query
                filter_sql      Sql condition for limited using argument to param
                neg_filter_sql  Sql condition for limited using argument to param negated.
                ext_sql         Sql statement fetch an ordered list of extents, given
                                                file-id and argument to param as parameters.
                                                (None if not applicable)
                formatter       Function/lambda expression for formatting the argument
    """
    def __init__(self, param, filter_sql, neg_filter_sql, ext_sql, formatter):
        SearchFilter.__init__(self)
        self.param = param
        self.filter_sql = filter_sql
        self.neg_filter_sql = neg_filter_sql
        self.ext_sql = ext_sql
        self.formatter = formatter

    def filter(self, terms):
        for term in terms.get(self.param, []):
            arg = term['arg']
            if term['not']:
                yield self.neg_filter_sql, self.formatter(arg), False
            else:
                yield self.filter_sql, self.formatter(arg), self.ext_sql is not None

    def extents(self, terms, execute_sql, file_id):
        if self.ext_sql:
            for term in terms.get(self.param, []):
                for start, end in execute_sql(self.ext_sql,
                                              [file_id] + self.formatter(term['arg'])):
                    yield start, end, []


class ExistsLikeFilter(SearchFilter):
    """Search filter for asking of something LIKE this EXISTS,
            This filter takes 5 parameters, param is the search query parameter,
            "-" + param is a assumed to be the negated search filter.
            The filter_sql must be an (SELECT 1 FROM ... WHERE ... %s ...), sql condition on files.id,
            s.t. replacing %s with "qual_name = ?" or "like_name LIKE %?%" where ? is arg given to param
            in search query, and prefixing with EXISTS or NOT EXISTS will yield search
            results as desired :)
            (BTW, did I mention that 'as desired' is awesome way of writing correct specifications)
            ext_sql, must be an sql statement for a list of extent start and end,
            given arguments (file_id, %arg%), where arg is the argument given to
            param. Again %s will be replaced with " = ?" or "LIKE %?%" depending on
            whether or not param is prefixed +
    """
    def __init__(self, param, filter_sql, ext_sql, qual_name, like_name):
        super(ExistsLikeFilter, self).__init__()
        self.param = param
        self.filter_sql = filter_sql
        self.ext_sql = ext_sql
        self.qual_expr = " %s = ? " % qual_name
        self.like_expr = """ %s LIKE ? ESCAPE "\\" """ % like_name

    def filter(self, terms):
        for term in terms.get(self.param, []):
            is_qualified = term['qualified']
            arg = term['arg']
            filter_sql = (self.filter_sql % (self.qual_expr if is_qualified
                                             else self.like_expr))
            sql_params = [arg if is_qualified else like_escape(arg)]
            if term['not']:
                yield 'NOT EXISTS (%s)' % filter_sql, sql_params, False
            else:
                yield 'EXISTS (%s)' % filter_sql, sql_params, self.ext_sql is not None

    def extents(self, terms, execute_sql, file_id):
        def builder():
            for term in terms.get(self.param, []):
                arg = term['arg']
                escaped_arg, sql_expr = (
                    (arg, self.qual_expr) if term['qualified']
                    else (like_escape(arg), self.like_expr))
                for start, end in execute_sql(self.ext_sql % sql_expr,
                                              [file_id, escaped_arg]):
                    # Nones used to occur in the DB. Is this still true?
                    if start and end:
                        yield start, end, []
        if self.ext_sql:
            yield builder()

class UnionFilter(SearchFilter):
    """Provides a filter matching the union of the given filters.

            For when you want OR instead of AND.
    """
    def __init__(self, filters):
        super(UnionFilter, self).__init__()
        # For the moment, UnionFilter supports only single-param filters. There
        # is no reason this can't change.
        unique_params = set(f.param for f in filters)
        if len(unique_params) > 1:
            raise ValueError('All filters that make up a union filter must have the same name, but we got %s.' % ' and '.join(unique_params))
        self.param = unique_params.pop()  # for consistency with other
        self.filters = filters

    def filter(self, terms):
        for res in zip(*(filt.filter(terms) for filt in self.filters)):
            yield ('(' + ' OR '.join(conds for (conds, args, exts) in res) + ')',
                   [arg for (conds, args, exts) in res for arg in args],
                   any(exts for (conds, args, exts) in res))

    def extents(self, terms, execute_sql, file_id):
        def builder():
            for filt in self.filters:
                for hits in filt.extents(terms, execute_sql, file_id):
                    for hit in hits:
                        yield hit
        def sorter():
            for hits in groupby(sorted(builder())):
                yield hits[0]
        yield sorter()


# Register filters by adding them to this list:
filters = [
    TriLiteSearchFilter(),

    # path filter
    SimpleFilter(
        param             = "path",
        filter_sql        = """files.path LIKE ? ESCAPE "\\" """,
        neg_filter_sql    = """files.path NOT LIKE ? ESCAPE "\\" """,
        ext_sql           = None,
        formatter         = lambda arg: ['%' + like_escape(arg) + '%']
    ),

    # ext filter
    SimpleFilter(
        param             = "ext",
        filter_sql        = """files.path LIKE ? ESCAPE "\\" """,
        neg_filter_sql    = """files.path NOT LIKE ? ESCAPE "\\" """,
        ext_sql           = None,
        formatter         = lambda arg: ['%' +
            like_escape(arg if arg.startswith(".") else "." + arg)]
    ),


    # type filter
    UnionFilter([
      ExistsLikeFilter(
        param         = "type",
        filter_sql    = """SELECT 1 FROM types
                           WHERE %s
                             AND types.file_id = files.id
                        """,
        ext_sql       = """SELECT types.extent_start, types.extent_end FROM types
                           WHERE types.file_id = ?
                             AND %s
                           ORDER BY types.extent_start
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
      ),
      ExistsLikeFilter(
        param         = "type",
        filter_sql    = """SELECT 1 FROM typedefs
                           WHERE %s
                             AND typedefs.file_id = files.id
                        """,
        ext_sql       = """SELECT typedefs.extent_start, typedefs.extent_end FROM typedefs
                           WHERE typedefs.file_id = ?
                             AND %s
                           ORDER BY typedefs.extent_start
                        """,
        like_name     = "typedefs.name",
        qual_name     = "typedefs.qualname"
      ),
    ]),

    # type-ref filter
    UnionFilter([
      ExistsLikeFilter(
        param         = "type-ref",
        filter_sql    = """SELECT 1 FROM types, type_refs AS refs
                           WHERE %s
                             AND types.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM type_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM types
                                         WHERE %s
                                           AND types.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
      ),
      ExistsLikeFilter(
        param         = "type-ref",
        filter_sql    = """SELECT 1 FROM typedefs, typedef_refs AS refs
                           WHERE %s
                             AND typedefs.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM typedef_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM typedefs
                                         WHERE %s
                                           AND typedefs.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "typedefs.name",
        qual_name     = "typedefs.qualname"
      ),
    ]),

    # type-decl filter
    ExistsLikeFilter(
      param         = "type-decl",
      filter_sql    = """SELECT 1 FROM types, type_decldef AS decldef
                         WHERE %s
                           AND types.id = decldef.defid AND decldef.file_id = files.id
                      """,
      ext_sql       = """SELECT decldef.extent_start, decldef.extent_end FROM type_decldef AS decldef
                         WHERE decldef.file_id = ?
                           AND EXISTS (SELECT 1 FROM types
                                       WHERE %s
                                         AND types.id = decldef.defid)
                         ORDER BY decldef.extent_start
                      """,
      like_name     = "types.name",
      qual_name     = "types.qualname"
    ),

    # function filter
    ExistsLikeFilter(
        param         = "function",
        filter_sql    = """SELECT 1 FROM functions
                           WHERE %s
                             AND functions.file_id = files.id
                        """,
        ext_sql       = """SELECT functions.extent_start, functions.extent_end FROM functions
                           WHERE functions.file_id = ?
                             AND %s
                           ORDER BY functions.extent_start
                        """,
        like_name     = "functions.name",
        qual_name     = "functions.qualname"
    ),

    # function-ref filter
    ExistsLikeFilter(
        param         = "function-ref",
        filter_sql    = """SELECT 1 FROM functions, function_refs AS refs
                           WHERE %s
                             AND functions.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM function_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM functions
                                         WHERE %s
                                           AND functions.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "functions.name",
        qual_name     = "functions.qualname"
    ),

    # function-decl filter
    ExistsLikeFilter(
        param         = "function-decl",
        filter_sql    = """SELECT 1 FROM functions, function_decldef as decldef
                           WHERE %s
                             AND functions.id = decldef.defid AND decldef.file_id = files.id
                        """,
        ext_sql       = """SELECT decldef.extent_start, decldef.extent_end FROM function_decldef AS decldef
                           WHERE decldef.file_id = ?
                             AND EXISTS (SELECT 1 FROM functions
                                         WHERE %s
                                           AND functions.id = decldef.defid)
                           ORDER BY decldef.extent_start
                        """,
        like_name     = "functions.name",
        qual_name     = "functions.qualname"
    ),

    # var filter
    ExistsLikeFilter(
        param         = "var",
        filter_sql    = """SELECT 1 FROM variables
                           WHERE %s
                             AND variables.file_id = files.id
                        """,
        ext_sql       = """SELECT variables.extent_start, variables.extent_end FROM variables
                           WHERE variables.file_id = ?
                             AND %s
                           ORDER BY variables.extent_start
                        """,
        like_name     = "variables.name",
        qual_name     = "variables.qualname"
    ),

    # var-ref filter
    ExistsLikeFilter(
        param         = "var-ref",
        filter_sql    = """SELECT 1 FROM variables, variable_refs AS refs
                           WHERE %s
                             AND variables.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM variable_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM variables
                                         WHERE %s
                                           AND variables.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "variables.name",
        qual_name     = "variables.qualname"
    ),

    # var-decl filter
    ExistsLikeFilter(
        param         = "var-decl",
        filter_sql    = """SELECT 1 FROM variables, variable_decldef AS decldef
                           WHERE %s
                             AND variables.id = decldef.defid AND decldef.file_id = files.id
                        """,
        ext_sql       = """SELECT decldef.extent_start, decldef.extent_end FROM variable_decldef AS decldef
                           WHERE decldef.file_id = ?
                             AND EXISTS (SELECT 1 FROM variables
                                         WHERE %s
                                           AND variables.id = decldef.defid)
                           ORDER BY decldef.extent_start
                        """,
        like_name     = "variables.name",
        qual_name     = "variables.qualname"
    ),

    # namespace filter
    ExistsLikeFilter(
        param         = "namespace",
        filter_sql    = """SELECT 1 FROM namespaces
                           WHERE %s
                             AND namespaces.file_id = files.id
                        """,
        ext_sql       = """SELECT namespaces.extent_start, namespaces.extent_end FROM namespaces
                           WHERE namespaces.file_id = ?
                             AND %s
                           ORDER BY namespaces.extent_start
                        """,
        like_name     = "namespaces.name",
        qual_name     = "namespaces.qualname"
    ),

    # namespace-ref filter
    ExistsLikeFilter(
        param         = "namespace-ref",
        filter_sql    = """SELECT 1 FROM namespaces, namespace_refs AS refs
                           WHERE %s
                             AND namespaces.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM namespace_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM namespaces
                                         WHERE %s
                                           AND namespaces.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "namespaces.name",
        qual_name     = "namespaces.qualname"
    ),

    # namespace-alias filter
    ExistsLikeFilter(
        param         = "namespace-alias",
        filter_sql    = """SELECT 1 FROM namespace_aliases
                           WHERE %s
                             AND namespace_aliases.file_id = files.id
                        """,
        ext_sql       = """SELECT namespace_aliases.extent_start, namespace_aliases.extent_end FROM namespace_aliases
                           WHERE namespace_aliases.file_id = ?
                             AND %s
                           ORDER BY namespace_aliases.extent_start
                        """,
        like_name     = "namespace_aliases.name",
        qual_name     = "namespace_aliases.qualname"
    ),

    # namespace-alias-ref filter
    ExistsLikeFilter(
        param         = "namespace-alias-ref",
        filter_sql    = """SELECT 1 FROM namespace_aliases, namespace_alias_refs AS refs
                           WHERE %s
                             AND namespace_aliases.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM namespace_alias_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM namespace_aliases
                                         WHERE %s
                                           AND namespace_aliases.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "namespace_aliases.name",
        qual_name     = "namespace_aliases.qualname"
    ),

    # macro filter
    ExistsLikeFilter(
        param         = "macro",
        filter_sql    = """SELECT 1 FROM macros
                           WHERE %s
                             AND macros.file_id = files.id
                        """,
        ext_sql       = """SELECT macros.extent_start, macros.extent_end FROM macros
                           WHERE macros.file_id = ?
                             AND %s
                           ORDER BY macros.extent_start
                        """,
        like_name     = "macros.name",
        qual_name     = "macros.name"
    ),

    # macro-ref filter
    ExistsLikeFilter(
        param         = "macro-ref",
        filter_sql    = """SELECT 1 FROM macros, macro_refs AS refs
                           WHERE %s
                             AND macros.id = refs.refid AND refs.file_id = files.id
                        """,
        ext_sql       = """SELECT refs.extent_start, refs.extent_end FROM macro_refs AS refs
                           WHERE refs.file_id = ?
                             AND EXISTS (SELECT 1 FROM macros
                                         WHERE %s
                                           AND macros.id = refs.refid)
                           ORDER BY refs.extent_start
                        """,
        like_name     = "macros.name",
        qual_name     = "macros.name"
    ),

    UnionFilter([
      # callers filter (direct-calls)
      ExistsLikeFilter(
          param         = "callers",
          filter_sql    = """SELECT 1
                              FROM functions as caller, functions as target, callers
                             WHERE %s
                               AND callers.targetid = target.id
                               AND callers.callerid = caller.id
                               AND caller.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as target, callers
                                            WHERE %s
                                              AND callers.targetid = target.id
                                              AND callers.callerid = functions.id
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "target.name",
          qual_name     = "target.qualname"
      ),

      # callers filter (indirect-calls)
      ExistsLikeFilter(
          param         = "callers",
          filter_sql    = """SELECT 1
                              FROM functions as caller, functions as target, callers, targets
                             WHERE %s
                               AND targets.funcid = target.id
                               AND targets.targetid = callers.targetid
                               AND callers.callerid = caller.id
                               AND caller.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as target, callers, targets
                                            WHERE %s
                                              AND targets.funcid = target.id
                                              AND targets.targetid = callers.targetid
                                              AND callers.callerid = functions.id
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "target.name",
          qual_name     = "target.qualname"
      ),
    ]),

    UnionFilter([
      # called-by filter (direct calls)
      ExistsLikeFilter(
          param         = "called-by",
          filter_sql    = """SELECT 1
                               FROM functions as target, functions as caller, callers
                              WHERE %s
                                AND callers.callerid = caller.id
                                AND callers.targetid = target.id
                                AND target.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as caller, callers
                                            WHERE %s
                                              AND caller.id = callers.callerid
                                              AND callers.targetid = functions.id
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "caller.name",
          qual_name     = "caller.qualname"
      ),

      # called-by filter (indirect calls)
      ExistsLikeFilter(
          param         = "called-by",
          filter_sql    = """SELECT 1
                               FROM functions as target, functions as caller, callers, targets
                              WHERE %s
                                AND callers.callerid = caller.id
                                AND targets.funcid = target.id
                                AND targets.targetid = callers.targetid
                                AND target.file_id = files.id
                          """,
          ext_sql       = """SELECT functions.extent_start, functions.extent_end
                              FROM functions
                             WHERE functions.file_id = ?
                               AND EXISTS (SELECT 1 FROM functions as caller, callers, targets
                                            WHERE %s
                                              AND caller.id = callers.callerid
                                              AND targets.funcid = functions.id
                                              AND targets.targetid = callers.targetid
                                          )
                             ORDER BY functions.extent_start
                          """,
          like_name     = "caller.name",
          qual_name     = "caller.qualname"
      ),
    ]),

    # overridden filter
    ExistsLikeFilter(
        param         = "overridden",
        filter_sql    = """SELECT 1
                             FROM functions as base, functions as derived, targets
                            WHERE %s
                              AND base.id = -targets.targetid
                              AND derived.id = targets.funcid
                              AND base.id <> derived.id
                              AND base.file_id = files.id
                        """,
        ext_sql       = """SELECT functions.extent_start, functions.extent_end
                            FROM functions
                           WHERE functions.file_id = ?
                             AND EXISTS (SELECT 1 FROM functions as derived, targets
                                          WHERE %s
                                            AND functions.id = -targets.targetid
                                            AND derived.id = targets.funcid
                                            AND functions.id <> derived.id
                                        )
                           ORDER BY functions.extent_start
                        """,
        like_name     = "derived.name",
        qual_name     = "derived.qualname"
    ),

    # overrides filter
    ExistsLikeFilter(
        param         = "overrides",
        filter_sql    = """SELECT 1
                             FROM functions as base, functions as derived, targets
                            WHERE %s
                              AND base.id = -targets.targetid
                              AND derived.id = targets.funcid
                              AND base.id <> derived.id
                              AND derived.file_id = files.id
                        """,
        ext_sql       = """SELECT functions.extent_start, functions.extent_end
                            FROM functions
                           WHERE functions.file_id = ?
                             AND EXISTS (SELECT 1 FROM functions as base, targets
                                          WHERE %s
                                            AND base.id = -targets.targetid
                                            AND functions.id = targets.funcid
                                            AND base.id <> functions.id
                                        )
                           ORDER BY functions.extent_start
                        """,
        like_name     = "base.name",
        qual_name     = "base.qualname"
    ),

    #warning filter
    ExistsLikeFilter(
        param         = "warning",
        filter_sql    = """SELECT 1 FROM warnings
                            WHERE %s
                              AND warnings.file_id = files.id """,
        ext_sql       = """SELECT warnings.extent_start, warnings.extent_end
                             FROM warnings
                            WHERE warnings.file_id = ?
                              AND %s
                        """,
        like_name     = "warnings.msg",
        qual_name     = "warnings.msg"
    ),

    #warning-opt filter
    ExistsLikeFilter(
        param         = "warning-opt",
        filter_sql    = """SELECT 1 FROM warnings
                            WHERE %s
                              AND warnings.file_id = files.id """,
        ext_sql       = """SELECT warnings.extent_start, warnings.extent_end
                             FROM warnings
                            WHERE warnings.file_id = ?
                              AND %s
                        """,
        like_name     = "warnings.opt",
        qual_name     = "warnings.opt"
    ),

    # bases filter
    ExistsLikeFilter(
        param         = "bases",
        filter_sql    = """SELECT 1 FROM types as base, impl, types
                            WHERE %s
                              AND impl.tbase = base.id
                              AND impl.tderived = types.id
                              AND base.file_id = files.id""",
        ext_sql       = """SELECT base.extent_start, base.extent_end
                            FROM types as base
                           WHERE base.file_id = ?
                             AND EXISTS (SELECT 1 FROM impl, types
                                         WHERE impl.tbase = base.id
                                           AND impl.tderived = types.id
                                           AND %s
                                        )
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
    ),

    # derived filter
    ExistsLikeFilter(
        param         = "derived",
        filter_sql    = """SELECT 1 FROM types as sub, impl, types
                            WHERE %s
                              AND impl.tbase = types.id
                              AND impl.tderived = sub.id
                              AND sub.file_id = files.id""",
        ext_sql       = """SELECT sub.extent_start, sub.extent_end
                            FROM types as sub
                           WHERE sub.file_id = ?
                             AND EXISTS (SELECT 1 FROM impl, types
                                         WHERE impl.tbase = types.id
                                           AND impl.tderived = sub.id
                                           AND %s
                                        )
                        """,
        like_name     = "types.name",
        qual_name     = "types.qualname"
    ),

    UnionFilter([
      # member filter for functions
      ExistsLikeFilter(
        param         = "member",
        filter_sql    = """SELECT 1 FROM types as type, functions as mem
                            WHERE %s
                              AND mem.scopeid = type.id AND mem.file_id = files.id
                        """,
        ext_sql       = """ SELECT extent_start, extent_end
                              FROM functions as mem WHERE mem.file_id = ?
                                      AND EXISTS ( SELECT 1 FROM types as type
                                                    WHERE %s
                                                      AND type.id = mem.scopeid)
                           ORDER BY mem.extent_start
                        """,
        like_name     = "type.name",
        qual_name     = "type.qualname"
      ),
      # member filter for types
      ExistsLikeFilter(
        param         = "member",
        filter_sql    = """SELECT 1 FROM types as type, types as mem
                            WHERE %s
                              AND mem.scopeid = type.id AND mem.file_id = files.id
                        """,
        ext_sql       = """ SELECT extent_start, extent_end
                              FROM types as mem WHERE mem.file_id = ?
                                      AND EXISTS ( SELECT 1 FROM types as type
                                                    WHERE %s
                                                      AND type.id = mem.scopeid)
                           ORDER BY mem.extent_start
                        """,
        like_name     = "type.name",
        qual_name     = "type.qualname"
      ),
      # member filter for variables
      ExistsLikeFilter(
        param         = "member",
        filter_sql    = """SELECT 1 FROM types as type, variables as mem
                            WHERE %s
                              AND mem.scopeid = type.id AND mem.file_id = files.id
                        """,
        ext_sql       = """ SELECT extent_start, extent_end
                              FROM variables as mem WHERE mem.file_id = ?
                                      AND EXISTS ( SELECT 1 FROM types as type
                                                    WHERE %s
                                                      AND type.id = mem.scopeid)
                           ORDER BY mem.extent_start
                        """,
        like_name     = "type.name",
        qual_name     = "type.qualname"
      ),
    ])
]


query_grammar = Grammar(ur'''
    query = _ term*
    term = not_term / positive_term
    not_term = not positive_term
    positive_term = filtered_term / text

    # A term with a filter name prepended:
    filtered_term = maybe_plus filter ":" text

    # Bare or quoted text, possibly with spaces. Not empty.
    text = (double_quoted_text / single_quoted_text / bare_text) _

    filter = ~r"''' +
        # regexp, function, etc. No filter is a prefix of a later one. This
        # avoids premature matches.
        '|'.join(sorted(chain.from_iterable(map(re.escape, f.names()) for f in filters),
                        key=len,
                        reverse=True)) +
             ur'''"

    not = "-"

    # You can stick a plus in front of anything, and it'll parse, but it has
    # meaning only with the filters where it makes sense.
    maybe_plus = "+"?

    # Unquoted text until a space or EOL:
    bare_text = ~r"[^ ]+"

    # A string starting with a double quote and extending to {a double quote
    # followed by a space} or {a double quote followed by the end of line} or
    # {simply the end of line}, ignoring (that is, including) backslash-escaped
    # quotes. The intent is to take quoted strings like `"hi \there"woo"` and
    # take a good guess at what you mean even while you're still typing, before
    # you've closed the quote. The motivation for providing backslash-escaping
    # is so you can express trailing quote-space pairs without having the
    # scanner prematurely end.
    double_quoted_text = ~r'"(?P<content>(?:[^"\\]*(?:\\"|\\|"[^ ])*)*)(?:"(?= )|"$|$)'
    # A symmetric rule for single quotes:
    single_quoted_text = ~r"'(?P<content>(?:[^'\\]*(?:\\'|\\|'[^ ])*)*)(?:'(?= )|'$|$)"

    _ = ~r"[ \t]*"
    ''')


class QueryVisitor(NodeVisitor):
    visit_positive_term = NodeVisitor.lift_child

    def __init__(self, is_case_sensitive=False):
        """Construct.

        :arg is_case_sensitive: What "case_sensitive" value to set on every
            term. This is meant to be temporary, until we expose per-term case
            sensitivity to the user.

        """
        super(NodeVisitor, self).__init__()
        self.is_case_sensitive = is_case_sensitive

    def visit_query(self, query, (_, terms)):
        """Group terms into a dict of lists by filter type, and return it."""
        d = {}
        for filter_name, subdict in terms:
            d.setdefault(filter_name, []).append(subdict)
        return d

    def visit_term(self, term, ((filter_name, subdict),)):
        """Set the case-sensitive bit and, if not already set, a default not
        bit."""
        subdict['case_sensitive'] = self.is_case_sensitive
        subdict.setdefault('not', False)
        subdict.setdefault('qualified', False)
        return filter_name, subdict

    def visit_not_term(self, not_term, (not_, (filter_name, subdict))):
        """Add "not" bit to the subdict."""
        subdict['not'] = True
        return filter_name, subdict

    def visit_filtered_term(self, filtered_term, (plus, filter, colon, (text_type, subdict))):
        """Add fully-qualified indicator to the term subdict, and return it and
        the filter name."""
        subdict['qualified'] = plus.text == '+'
        return filter.text, subdict

    def visit_text(self, text, ((some_text,), _)):
        """Create the subdictionary that lives in Query.terms. Return it and
        'text', indicating that this is a bare or quoted run of text. If it is
        actually an argument to a filter, ``visit_filtered_term`` will
        overrule us later.

        """
        return 'text', {'arg': some_text}

    def visit_maybe_plus(self, plus, wtf):
        """Keep the plus from turning into a list half the time. That makes it
        awkward to compare against."""
        return plus

    def visit_bare_text(self, bare_text, visited_children):
        return bare_text.text

    def visit_double_quoted_text(self, quoted_text, visited_children):
        return quoted_text.match.group('content').replace(r'\"', '"')

    def visit_single_quoted_text(self, quoted_text, visited_children):
        return quoted_text.match.group('content').replace(r"\'", "'")

    def generic_visit(self, node, visited_children):
        """Replace childbearing nodes with a list of their children; keep
        others untouched.

        """
        return visited_children or node
