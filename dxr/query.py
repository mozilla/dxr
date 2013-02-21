import utils, cgi, codecs, struct
import time


# Register filters by adding them to this list.
filters = []

# TODO
#   - Special argument files-only to just search for file names
#   - If no plugin returns an extents query, don't fetch content


import re

#TODO _parameters should be extracted from filters (possible if filters are defined first)
# List of parameters to isolate in the search query, ie. path:mypath
_parameters = ["path", "ext", "type", "type-ref", "function", "function-ref",
"var", "var-ref", "macro", "macro-ref", "callers", "called-by", "warning",
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

class Query:
    """ Query object, constructor will parse any search query """
    def __init__(self, querystr):
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
        """ Returns the single term making up the query, None for complex queries """
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

_explain = False
_sql_profile = []
def _execute_sql(conn, sql, *parameters):
    if _explain:
        _sql_profile.append({
            "sql" : sql,
            "parameters" : parameters[0] if len(parameters) >= 1 else [],
            "explanation" : conn.execute("EXPLAIN QUERY PLAN " + sql, *parameters)
        })
        start_time = time.time()
    res = conn.execute(sql, *parameters)
    if _explain:
        # fetch results eagerly so we can get an accurate time for the entire operation
        res = res.fetchall()
        _sql_profile[-1]["elapsed_time"] = time.time() - start_time
        _sql_profile[-1]["nrows"] = len(res)
    return res

# Fetch results using a query,
# See: queryparser.py for details in query specification
def fetch_results(conn, query,
                                    offset = 0, limit = 100,
                                    explain = False,
                                    markup = "<b>", markdown = "</b>"):
    global _explain
    _explain = explain
    sql = """
        SELECT files.path, files.icon, trg_index.text, files.id,
        extents(trg_index.contents)
            FROM trg_index, files
          WHERE %s LIMIT ? OFFSET ?
    """
    conditions = " files.id = trg_index.id "
    arguments = []

    has_extents = False
    for f in filters:
        for conds, args, exts in f.filter(query):
            has_extents = exts or has_extents
            conditions += " AND " + conds
            arguments += args

    sql %= conditions
    arguments += [limit, offset]

    #TODO Actually do something with the has_extents, ie. don't fetch contents

    #utils.log(sql)
    #utils.log(arguments)

    # Make a simple decoder for decoding unicode
    # Note that we need to operate in ascii inorder to handle
    # compiler offsets
    decoder = codecs.getdecoder("utf-8")
    def d(string):
        return decoder(string, errors="replace")[0]

    cursor = _execute_sql(conn, sql, arguments)

    for path, icon, content, fileid, extents in cursor:
        elist = []

        # Special hack for TriLite extents
        if extents:
            matchExtents = []
            for i in xrange(0, len(extents), 8):
                s, e = struct.unpack("II", extents[i:i+8])
                matchExtents.append((s, e, []))
            elist.append(fix_extents_overlap(sorted(matchExtents)))

        for f in filters:
            for e in f.extents(conn, query, fileid):
                elist.append(e)
        offsets = list(merge_extents(*elist))
        if _explain:
            continue

        lines = []
        line_number = 1
        last_pos = 0

        for i in xrange(0, len(offsets)):
            # TODO keylist should infact have information about which extent of the
            # search query caused this hit, we should highlight this extent
            # (Note. Query object still doesn't provide support for offering this
            #  extent, and this needs to be supported and used in filters).
            estart, eend, keylist = offsets[i]

            # Count the newlines from the top of the file to get the line
            # number. Maybe we could optimize this by storing the line number
            # in the index with the extent.
            line_diff = content.count("\n", last_pos, estart)
            # Skip if we didn't get a new line
            if line_diff == 0 and last_pos > 0:
                continue 
            line_number += line_diff
            last_pos = estart

            # Find newline before and after offset
            end       = content.find("\n", estart)
            if end == -1:
                end = len(content)
            start     = content.rfind("\n", 0, end) + 1
            src_line  = content[start:end]

            # Build line
            out_line = ""
            mend = 0      # Invariant: Offset where last write ended

            # Add some markup to highlight hits
            while content.count("\n", last_pos, estart) == 0:
                last_end = mend
                mstart = estart - start
                mend   = eend - start
                # Output line segment from last_end to markup start
                out_line += cgi.escape(d(src_line[last_end:mstart]))
                # Output markup and line segment
                out_line += markup + cgi.escape(d(src_line[mstart:mend])) + markdown
                i += 1
                if i >= len(offsets):
                    break
                estart, eend, keylist = offsets[i]

            # Output the rest of the line when theres no more offsets
            # Notice that the while loop always goes atleast once
            out_line += cgi.escape(d(src_line[mend:]))

            lines.append((line_number, out_line))
        # Return result
        yield icon, path, lines

    def number_lines(arr):
        ret = []
        for i in range(len(arr)):
            if arr[i] == "":
                ret.append((i, " "))  # empty lines cause the <div> to collapse and mess up the formatting
            else:
                ret.append((i, arr[i]))
        return ret

    for i in range(len(_sql_profile)):
        profile = _sql_profile[i]
        yield ("",
                      "sql %d (%d row(s); %s seconds)" % (i, profile["nrows"], profile["elapsed_time"]),
                      number_lines(profile["sql"].split("\n")))
        yield ("",
                      "parameters %d" % i,
                      number_lines(map(lambda parm: repr(parm), profile["parameters"])));
        yield ("",
                      "explanation %d" % i,
                      number_lines(map(lambda row: row["detail"], profile["explanation"])))


def direct_result(conn, query):
    """ Get a direct result as tuple of (path, line) or None if not direct result
            for query, ie. complex query
    """
    term = query.single_term()
    if not term:
        return None
    cur = conn.cursor()
    
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
    if "::" in term:
        # Case insensitive type matching
        cur.execute("""
            SELECT
                  (SELECT path FROM files WHERE files.id = types.file_id) as path,
                  types.file_line
                FROM types WHERE types.qualname LIKE ? LIMIT 2
        """, ("%" + term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Case insensitive function names
        cur.execute("""
        SELECT
              (SELECT path FROM files WHERE files.id = functions.file_id) as path,
              functions.file_line
            FROM functions WHERE functions.qualname LIKE ? LIMIT 2
        """, ("%" + term,))
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


def like_escape(val):
    """ Escape for usage in as argument to the LIKE operator """
    return (val.replace("\\", "\\\\")
               .replace("_", "\\_")
               .replace("%", "\\%")
               .replace("?", "_")
               .replace("*", "%"))


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


class SearchFilter:
    """ Base class for all search filters, plugins subclasses this class and
            registers an instance of them calling register_filter
    """
    def __init__(self):
        """ Initialize the filter, self.params is the keywords used by this filter,
                Fail to declare keywords and the query-parser will not parse them!
        """
        self.params = []
    def filter(self, query):
        """ Given a query yield tuples of sql conditions, list of arguments and
                boolean True if this filter offer extents for results,
                Note the sql conditions must be string and condition on files.id
        """
        return []
    def extents(self, conn, query, fileid):
        """ Given a connection, query and a file id yield a ordered lists of extents to highlight """
        return []

class TriLiteSearchFilter(SearchFilter):
    """ TriLite Search filter """
    def __init__(self):
        SearchFilter.__init__(self)
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
    """ Search filter for limited results.
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
                for start, end in _execute_sql(conn, self.ext_sql, [fileid] + self.formatter(arg)):
                    yield start, end, []

class ExistsLikeFilter(SearchFilter):
    """ Search filter for asking of something LIKE this EXISTS,
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
                    for start, end in _execute_sql(conn, sql, params):
                        # Apparently sometime, None can occur in the database
                        if start and end:
                            yield (start, end,[])
                yield builder()
            for arg in query.params["+" + self.param]:
                params = [fileid, arg]
                def builder():
                    sql = self.ext_sql % self.qual_expr
                    for start, end in _execute_sql(conn, sql, params):
                        # Apparently sometime, None can occur in the database
                        if start and end:
                            yield (start, end,[])
                yield builder()


class UnionFilter(SearchFilter):
    """ Provides a filter matching the union of the given filters.

            For when you want OR instead of AND.
    """
    def __init__(self, filters):
        SearchFilter.__init__(self)
        self.filters = filters

    def filter(self, query):
        sql = []
        args = []
        has_ext = True
        for filt in self.filters:
            for hit in filt.filter(query):
                sql.append(hit[0])
                args.extend(hit[1])
                has_ext = has_ext or hit[2]
        if len(sql) == 0:
            return []
        return [('(' + ' OR '.join(sql) + ')',
                          args,
                          has_ext)]

    def extents(self, conn, query, fileid):
        def builder():
            for filt in self.filters:
                for hits in filt.extents(conn, query, fileid):
                    for hit in hits:
                        yield hit
        yield builder()


# TriLite Search filter
filters.append(TriLiteSearchFilter())

# path filter
filters.append(SimpleFilter(
    param             = "path",
    filter_sql        = """files.path LIKE ? ESCAPE "\\" """,
    neg_filter_sql    = """files.path NOT LIKE ? ESCAPE "\\" """,
    ext_sql           = None,
    formatter         = lambda arg: ['%' + like_escape(arg) + '%']
))

# ext filter
filters.append(SimpleFilter(
    param             = "ext",
    filter_sql        = """files.path LIKE ? ESCAPE "\\" """,
    neg_filter_sql    = """files.path NOT LIKE ? ESCAPE "\\" """,
    ext_sql           = None,
    formatter         = lambda arg: ['%' + like_escape(arg)]
))


# type filter
filters.append(UnionFilter([
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
]))


# type-ref filter
filters.append(UnionFilter([
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
]))

# function filter
filters.append(ExistsLikeFilter(
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
))


# function-ref filter
filters.append(ExistsLikeFilter(
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
))


# var filter
filters.append(ExistsLikeFilter(
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
))


# var-ref filter
filters.append(ExistsLikeFilter(
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
))


# macro filter
filters.append(ExistsLikeFilter(
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
))


# macro-ref filter
filters.append(ExistsLikeFilter(
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
))


filters.append(UnionFilter([
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
                          FROM functions as caller, functions as target, callers
                         WHERE %s
                           AND  EXISTS ( SELECT 1 FROM targets
                                          WHERE targets.funcid = target.id
                                            AND targets.targetid = callers.targetid
                                       )
                           AND callers.callerid = caller.id
                           AND caller.file_id = files.id
                      """,
      ext_sql       = """SELECT functions.extent_start, functions.extent_end
                          FROM functions
                         WHERE functions.file_id = ?
                           AND EXISTS (SELECT 1 FROM functions as target, callers
                                        WHERE %s
                                          AND EXISTS (
                                     SELECT 1 FROM targets
                                      WHERE targets.funcid = target.id
                                        AND targets.targetid = callers.targetid
                                        AND callers.callerid = target.id
                                              )
                                          AND callers.callerid = functions.id
                                      )
                         ORDER BY functions.extent_start
                      """,
      like_name     = "target.name",
      qual_name     = "target.qualname"
  ),
]))

filters.append(UnionFilter([
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
                           FROM functions as target, functions as caller, callers
                          WHERE %s
                            AND callers.callerid = caller.id
                            AND ( EXISTS (SELECT 1 FROM targets
                                           WHERE targets.funcid = target.id
                                             AND targets.targetid = callers.targetid
                                         )
                                )
                            AND target.file_id = files.id
                      """,
      ext_sql       = """SELECT functions.extent_start, functions.extent_end
                          FROM functions
                         WHERE functions.file_id = ?
                           AND EXISTS (SELECT 1 FROM functions as caller, callers
                                        WHERE %s
                                          AND caller.id = callers.callerid
                                          AND EXISTS (
                                      SELECT 1 FROM targets
                                       WHERE targets.funcid = functions.id
                                         AND targets.targetid = callers.targetid
                                              )
                                      )
                         ORDER BY functions.extent_start
                      """,
      like_name     = "caller.name",
      qual_name     = "caller.qualname"
  ),
]))

#warning filter
filters.append(ExistsLikeFilter(
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
))


#warning-opt filter
filters.append(ExistsLikeFilter(
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
))


# bases filter
filters.append(ExistsLikeFilter(
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
))


# derived filter
filters.append(ExistsLikeFilter(
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
))


filters.append(UnionFilter([
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
]))
