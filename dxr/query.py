from itertools import chain, count, groupby
import re
import time

from parsimonious import Grammar
from parsimonious.nodes import NodeVisitor

from dxr.extents import flatten_extents, highlight_line
from dxr.filters import filters

# TODO: Some kind of UI feedback for bad regexes
# TODO: Special argument files-only to just search for file names


# Pattern for matching a file and line number filename:n
_line_number = re.compile("^.*:[0-9]+$")


class Query(object):
    """Query object, constructor will parse any search query"""

    def __init__(self, conn, querystr, should_explain=False, is_case_sensitive=True):
        self.conn = conn
        self._should_explain = should_explain
        self._sql_profile = []
        self.is_case_sensitive = is_case_sensitive

        # A list of dicts describing query terms:
        self.terms = QueryVisitor(is_case_sensitive=is_case_sensitive).visit(query_grammar.parse(querystr))

    def single_term(self):
        """Return the single textual term comprising the query.

        If there is more than one term in the query or if the single term is a
        non-textual one, return None.

        """
        if len(self.terms) == 1 and self.terms[0]['type'] == ['text']:
            return self.terms[0]['arg']

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

    def _sql_report(self):
        """Yield a report on how long the SQL I've run has taken."""
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

    def results(self,
                offset=0, limit=100,
                markup='<b>', markdown='</b>'):
        """Return search results as an iterable of these::

            (icon,
             path within tree,
             [(line_number, highlighted_line_of_code), ...])

        """
        sql = ('SELECT %s '
               'FROM %s '
               '%s '
               '%s '
               'ORDER BY %s LIMIT ? OFFSET ?')
        # Filters can add additional fields, in pairs of {extent_start,
        # extent_end}, to be used for highlighting.
        fields = ['files.path', 'files.icon']  # TODO: move extents() to TriliteSearchFilter
        tables = ['files']
        conditions, arguments, joins = [], [], []
        orderings = ['files.path']
        has_lines = False

        # Give each registered filter an opportunity to contribute to the
        # query, narrowing it down to the set of matching lines:
        aliases = alias_counter()
        for term in self.terms:
            filter = filters[term['type']]
            flds, tbls, cond, jns, args = filter.filter(term, aliases)
            if not has_lines and filter.has_lines:
                has_lines = True
                # 2 types of query are possible: ones that return just
                # files and involve no other tables, and ones which join
                # the lines and trg_index tables and return lines and
                # extents. This switches from the former to the latter.
                #
                # The first time we hit a line-having filter, glom on the
                # line-based fields. That way, they're always at the
                # beginning (non-line-having filters never return fields),
                # so we can use our clever slicing later on to find the
                # extents fields.
                fields.extend(['files.encoding', 'files.id as file_id',
                               'lines.id as line_id', 'lines.number',
                               'trg_index.text', 'extents(trg_index.contents)'])
                tables.extend(['lines', 'trg_index'])
                conditions.extend(['files.id=lines.file_id', 'lines.id=trg_index.id'])
                orderings.append('lines.number')

            # We fetch the extents for structural filters without doing
            # separate queries, by adding columns to the master search
            # query. Since we're only talking about a line at a time, it is
            # unlikely that there will be multiple highlit extents per
            # filter per line, so any cartesian product of rows can
            # reasonably be absorbed and merged in the app.
            fields.extend(flds)

            tables.extend(tbls)
            joins.extend(jns)
            conditions.append(cond)
            arguments.extend(args)

        sql %= (', '.join(fields),
                ', '.join(tables),
                ' '.join(joins),
                ('WHERE ' + ' AND '.join(conditions)) if conditions else '',
                ', '.join(orderings))
        arguments.extend([limit, offset])
        cursor = self.execute_sql(sql, arguments)

        if self._should_explain:
            for r in self._sql_report():
                yield r

        if has_lines:
            # Group lines into files:
            for file_id, fields_and_extents_for_lines in \
                    groupby(flatten_extents(cursor),
                            lambda (fields, extents): fields['file_id']):
                # fields_and_extents_for_lines is [(fields, extents) for one line,
                #                                   ...] for a single file.
                fields_and_extents_for_lines = list(fields_and_extents_for_lines)
                shared_fields = fields_and_extents_for_lines[0][0]  # same for each line in the file

                yield (shared_fields['icon'],
                       shared_fields['path'],
                       [(fields['number'],
                         highlight_line(
                                fields['text'],
                                extents,
                                markup,
                                markdown,
                                shared_fields['encoding']))
                        for fields, extents in fields_and_extents_for_lines])
        else:
            for result in cursor:
                yield (result['icon'],
                       result['path'],
                       [])

        # Boy, as I see what this is doing, I think how good a fit ES is: you fetch a line document, and everything you'd need to highlight is right there. # If var-ref returns 2 extents on one line, it'll just duplicate a line, and we'll merge stuff after the fact. Hey, does that mean I should gather and merge everything before I try to homogenize the extents?
        # Test: If var-ref (or any structural query) returns 2 refs on one line, they should both get highlit.

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
        '|'.join(sorted((re.escape(filter_type) for
                                filter_type, filter in
                                filters.iteritems() if
                                filter.description),
                        key=len,
                        reverse=True)) + ur'''"

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
        """Return a list of query term term_dicts."""
        return terms

    def visit_term(self, term, (term_dict,)):
        """Set the case-sensitive bit and, if not already set, a default not
        bit."""
        term_dict['case_sensitive'] = self.is_case_sensitive
        term_dict.setdefault('not', False)
        term_dict.setdefault('qualified', False)
        return term_dict

    def visit_not_term(self, not_term, (not_, term_dict)):
        """Add "not" bit to the term_dict."""
        term_dict['not'] = True
        return term_dict

    def visit_filtered_term(self, filtered_term, (plus, filter, colon, term_dict)):
        """Add fully-qualified indicator and the filter name to the term_dict."""
        term_dict['qualified'] = plus.text == '+'
        term_dict['type'] = filter.text
        return term_dict

    def visit_text(self, text, ((some_text,), _)):
        """Create the dictionary that lives in Query.terms. Return it with a
        filter type of 'text', indicating that this is a bare or quoted run of
        text. If it is actually an argument to a filter,
        ``visit_filtered_term`` will overrule us later.

        """
        return {'type': 'text', 'arg': some_text}

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


def filter_menu_items():
    """Return the additional template variables needed to render filter.html."""
    return (dict(name=type, description=filter.description) for type, filter in
            filters.iteritems() if filter.description)


def alias_counter():
    """Return an infinite iterable of unique, valid SQL alias names."""
    return ('t%s' % num for num in count())
