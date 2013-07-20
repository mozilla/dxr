import cgi
from itertools import groupby
import re
import struct
import time


# TODO
#   - Special argument files-only to just search for file names
#   - If no plugin returns an extents query, don't fetch content

#TODO _parameters should be extracted from filters (possible if filters are defined first)
# List of parameters to isolate in the search query, ie. path:mypath
_parameters = ["path", "ext",
"type", "type-ref", "type-decl",
"function", "function-ref", "function-decl",
"var", "var-ref", "var-decl",
"namespace", "namespace-ref",
"namespace-alias", "namespace-alias-ref",
"macro", "macro-ref", "callers", "called-by", "warning",
"warning-opt", "bases", "derived", "member"]

_parameters += ["-" + param for param in _parameters] + ["+" + param for param
    in _parameters] + ["-+" + param for param in _parameters] + ["+-" + param for param in _parameters]

#TODO Support negation of phrases, support phrases as args to params, ie. path:"my path", or warning:"..."


# Pattern recognizing a parameter and a argument, a phrase or a keyword
_pat = "(?:(?P<regpar>-?regexp):(?P<del>.)(?P<regarg>(?:(?!(?P=del)).)+)(?P=del))|"
_pat += "(?:(?P<param>%s):(?:\"(?P<qarg>[^\"]+)\"|(?P<arg>[^ ]+)))|"
_pat += "(?:\"(?P<phrase>[^\"]+)\")|"
_pat += "(?:-\"(?P<notphrase>[^\"]+)\")|"
_pat += "(?P<keyword>[^ \"]+)"
# Regexp for parsing regular expression
_pat = re.compile(_pat % "|".join([re.escape(p) for p in _parameters]))

# Pattern for recognizing if a word will be tokenized as a single term.
# Ideally we should reuse our custom sqlite tokenizer, but that'll just
# complicated things, anyways, if it's not a identifier, it must be a single
# token, in which we'll wrap it anyway :)
_single_term = re.compile("^[a-zA-Z]+[a-zA-Z0-9]*$")

class Query(object):
    """Query object, constructor will parse any search query"""

    def __init__(self, conn, querystr, should_explain=False):
        self.conn = conn
        self._should_explain = should_explain
        self._sql_profile = []
        self.params = {}
        for param in _parameters:
            self.params[param] = []
        self.params["regexp"] = []
        self.params["-regexp"] = []
        self.notwords = []
        self.keywords = []
        self.phrases = []
        self.notphrases = []
        # We basically iterate over the set of matches left to right
        for token in (match.groupdict() for match in _pat.finditer(querystr)):
            if token["param"]:
                if token["arg"]:
                    self.params[token["param"]].append(token["arg"])
                elif token["qarg"]:
                    self.params[token["param"]].append(token["qarg"])
            if token["regpar"] and token["regarg"]:
                self.params[token["regpar"]].append(token["regarg"])
            if token["phrase"]:
                self.phrases.append(token["phrase"])
            if token["keyword"]:
                if token["keyword"].startswith("-"):
                    # If it's not a single term by the tokenizer
                    # we must wrap it as a phrase
                    if _single_term.match(token["keyword"][1:]):
                        self.notwords.append(token["keyword"][1:])
                    else:
                        self.phrases.append(token["keyword"][1:])
                else:
                    if _single_term.match(token["keyword"]):
                        self.keywords.append(token["keyword"])
                    else:
                        self.phrases.append(token["keyword"])
            if token["notphrase"]:
                self.notphrases.append(token["notphrase"])

    def single_term(self):
        """Returns the single term making up the query, None for complex queries"""
        count = 0
        term = None
        for param in _parameters:
            count += len(self.params[param])
        count += len(self.notwords)
        count += len(self.keywords)
        if len(self.keywords):
            term = self.keywords[0]
        count += len(self.phrases)
        if len(self.phrases):
            term = self.phrases[0]
        count += len(self.notphrases)
        if count > 1:
            return None
        return term

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
            SELECT files.path, files.icon, trg_index.text, files.id,
            extents(trg_index.contents)
                FROM trg_index, files
              WHERE %s LIMIT ? OFFSET ?
        """
        conditions = " files.id = trg_index.id "
        arguments = []

        # Give each registered filter an opportunity to contribute to the
        # query. This query narrows down the universe to a set of matching
        # files:
        has_extents = False
        for f in filters:
            for conds, args, exts in f.filter(self):
                has_extents = exts or has_extents
                conditions += " AND " + conds
                arguments += args

        sql %= conditions
        arguments += [limit, offset]

        #TODO Actually do something with the has_extents, ie. don't fetch contents

        cursor = self.execute_sql(sql, arguments)

        # For each returned file (including, only in the case of the trilite
        # filter, a set of extents)...
        for path, icon, content, fileid, extents in cursor:
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
                for e in f.extents(self.conn, self, fileid):
                    elist.append(e)
            offsets = list(merge_extents(*elist))

            if self._should_explain:
                continue

            # Yield the file, metadata, and iterable of highlighted offsets:
            yield icon, path, _highlit_lines(content, offsets, markup, markdown)


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

        # See if we can find only one file match
        cur.execute("SELECT path FROM files WHERE path LIKE ? LIMIT 2", ("%/" + term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
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


def _highlit_line(content, offsets, markup, markdown):
    """Return a line of string ``content`` with the given ``offsets`` prefixed
    by ``markup`` and suffixed by ``markdown``.

    We assume that none of the offsets split a Unicode code point. This
    assumption lets us run one big ``decode`` at the end.

    """
    def chunks():
        try:
            # Start on the line the highlights are on:
            chars_before = content.rindex('\n', 0, offsets[0][0]) + 1
        except ValueError:
            chars_before = None
        for start, end in offsets:
            # We can do the escapes before decoding, because all escaped chars
            # are the same in ASCII and utf-8:
            yield cgi.escape(content[chars_before:start])
            yield markup
            yield cgi.escape(content[start:end])
            yield markdown
            chars_before = end
        # Make sure to get the rest of the line after the last highlight:
        try:
            next_newline = content.index('\n', chars_before)
        except ValueError:  # eof
            next_newline = None
        yield cgi.escape(content[chars_before:next_newline])
    ret = ''.join(chunks())
    return ret.decode('utf-8', 'replace')


def _highlit_lines(content, offsets, markup, markdown):
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
                                 markdown)) for
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
    def __init__(self):
        """Initialize the filter, self.params is the keywords used by this filter,
                Fail to declare keywords and the query-parser will not parse them!
        """
        self.params = []

    def filter(self, query):
        """Given a query yield tuples of sql conditions, list of arguments and
                boolean True if this filter offer extents for results,
                Note the sql conditions must be string and condition on files.id
        """
        return []

    def extents(self, conn, query, fileid):
        """Given a connection, query and a file id yield a ordered lists of extents to highlight"""
        return []


class TriLiteSearchFilter(SearchFilter):
    """TriLite Search filter"""

    def filter(self, query):
        for term in query.keywords + query.phrases:
            yield "trg_index.contents MATCH ?", ["substr-extents:" + term], True
        for expr in query.params['regexp']:
            yield "trg_index.contents MATCH ?", ["regexp-extents:" + expr], True
        if (  len(query.notwords)
                + len(query.notphrases)
                + len(query.params['-regexp'])) > 0:
            conds = []
            args  = []
            for term in query.notwords + query.notphrases:
                conds.append("trg_index.contents MATCH ?")
                args.append("substr:" + term)
            for expr in query.params['-regexp']:
                conds.append("trg_index.contents MATCH ?")
                args.append("regexp:" + expr)
            yield (
                """ files.id NOT IN
                            (SELECT id FROM trg_index WHERE %s)
                """ % " AND ".join(conds),
                args, False)
    # Notice that extents is more efficiently handled in the search query
    # Sorry to break the pattern, but it's sagnificantly faster.


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
        self.params += (param, "-%s" % param)
        self.filter_sql = filter_sql
        self.neg_filter_sql = neg_filter_sql
        self.ext_sql = ext_sql
        self.formatter = formatter

    def filter(self, query):
        for arg in query.params[self.param]:
            yield self.filter_sql, self.formatter(arg), self.ext_sql is not None
        for arg in query.params["-%s" % self.param]:
            yield self.neg_filter_sql, self.formatter(arg), False

    def extents(self, conn, query, fileid):
        if self.ext_sql:
            for arg in query.params[self.param]:
                for start, end in query.execute_sql(self.ext_sql, [fileid] + self.formatter(arg)):
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
        SearchFilter.__init__(self)
        self.param = param
        self.params += (param, "+" + param, "-" + param, "+-" + param, "-+" + param)
        self.filter_sql = filter_sql
        self.ext_sql = ext_sql
        self.qual_expr = " %s = ? " % qual_name
        self.like_expr = """ %s LIKE ? ESCAPE "\\" """ % like_name

    def filter(self, query):
        for arg in query.params[self.param]:
            yield (
                            "EXISTS (%s)" % (self.filter_sql % self.like_expr),
                            [like_escape(arg)],
                            self.ext_sql is not None
                        )
        for arg in query.params["+" + self.param]:
            yield (
                            "EXISTS (%s)" % (self.filter_sql % self.qual_expr),
                            [arg],
                            self.ext_sql is not None
                        )
        for arg in query.params["+-" + self.param] + query.params["-+" + self.param]:
            yield (
                            "NOT EXISTS (%s)" % (self.filter_sql % self.qual_expr),
                            [arg],
                            False
                        )
        for arg in query.params["-" + self.param]:
            yield (
                            "NOT EXISTS (%s)" % (self.filter_sql % self.like_expr),
                            [like_escape(arg)],
                            False
                        )

    def extents(self, conn, query, fileid):
        if self.ext_sql:
            for arg in query.params[self.param]:
                params = [fileid, like_escape(arg)]
                def builder():
                    sql = self.ext_sql % self.like_expr
                    for start, end in query.execute_sql(sql, params):
                        # Apparently sometime, None can occur in the database
                        if start and end:
                            yield (start, end,[])
                yield builder()  # TODO: Can this be right? It seems like extents() will yield 2 iterables: one for each builder() proc. Huh?
            for arg in query.params["+" + self.param]:
                params = [fileid, arg]
                def builder():
                    sql = self.ext_sql % self.qual_expr
                    for start, end in query.execute_sql(sql, params):
                        # Apparently sometime, None can occur in the database
                        if start and end:
                            yield (start, end,[])
                yield builder()


class UnionFilter(SearchFilter):
    """Provides a filter matching the union of the given filters.

            For when you want OR instead of AND.
    """
    def __init__(self, filters):
        SearchFilter.__init__(self)
        self.filters = filters

    def filter(self, query):
        for res in zip(*(filt.filter(query) for filt in self.filters)):
            yield ('(' + ' OR '.join(conds for (conds, args, exts) in res) + ')',
                   [arg for (conds, args, exts) in res for arg in args],
                   any(exts for (conds, args, exts) in res))

    def extents(self, conn, query, fileid):
        def builder():
            for filt in self.filters:
                for hits in filt.extents(conn, query, fileid):
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
