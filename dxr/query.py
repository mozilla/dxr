import cgi
from itertools import chain, count, groupby
import re

from parsimonious import Grammar, NodeVisitor

from dxr.mime import icon
from dxr.plugins import all_plugins, LINE, FILE
from dxr.utils import append_update

# TODO: Some kind of UI feedback for bad regexes
# TODO: Special argument files-only to just search for file names


# Pattern for matching a file and line number filename:n
_line_number = re.compile("^.*:[0-9]+$")


# A dict mapping a filter name to a list of all filters having that name,
# across all plugins
FILTERS_NAMED = append_update(
    {},
    ((f.name, f) for f in
     chain.from_iterable(p.filters for p in all_plugins().itervalues())))


class Query(object):
    """Query object, constructor will parse any search query"""

    def __init__(self, es_search, querystr, is_case_sensitive=True):
        self.es_search = es_search
        self.is_case_sensitive = is_case_sensitive

        # A list of dicts describing query terms:
        self.terms = QueryVisitor(is_case_sensitive=is_case_sensitive).visit(query_grammar.parse(querystr))

    def single_term(self):
        """Return the single textual term comprising the query.

        If there is more than one term in the query or if the single term is a
        non-textual one, return None.

        """
        if len(self.terms) == 1 and self.terms[0]['name'] == 'text':
            return self.terms[0]['arg']

    def results(self, offset=0, limit=100):
        """Return search results as an iterable of these::

            (icon,
             path within tree,
             [(line_number, highlighted_line_of_code), ...])

        """
        # Instantiate applicable filters, yielding a list of lists, each inner
        # list representing the filters of the name of the parallel term. We
        # will OR the elements of the inner lists and then AND those OR balls
        # together.
        filters = [[f(term) for f in FILTERS_NAMED[term['name']]] for term in
                   self.terms]

        # See if we're returning lines or just files-and-folders:
        is_line_query = any(f.domain == LINE for f in
                            chain.from_iterable(filters))

        # An ORed-together ball for each term's filters, omitting filters that
        # punt by returning {} and ors that contain nothing but punts:
        ors = filter(None, [filter(None, (f.filter() for f in term))
                            for term in filters])
        ors = [{'or': x} for x in ors]

        if not is_line_query:
            # Don't show folders yet in search results. I don't think the JS
            # is able to handle them.
            ors.append({'term': {'is_folder': False}})

        if ors:
            query = {
                'filtered': {
                    'query': {
                        'match_all': {}
                    },
                    'filter': {
                        'and': ors
                    }
                }
            }
        else:
            query = {
                'match_all': {}
            }

        results = self.es_search(
            {'query': query,
             'sort': ['path', 'number'] if is_line_query else ['path'],
             'from': offset,
             'size': limit},
            doc_type=LINE if is_line_query else FILE)['hits']['hits']
        results = [r['_source'] for r in results]

        path_highlighters = [f.highlight_path for f in chain.from_iterable(filters)
                             if hasattr(f, 'highlight_path')]
        content_highlighters = [f.highlight_content for f in chain.from_iterable(filters)
                                if hasattr(f, 'highlight_content')]
        if is_line_query:
            # Group lines into files:
            for path, lines in groupby(results, lambda r: r['path'][0]):
                lines = list(lines)
                highlit_path = highlight(
                    path,
                    chain.from_iterable((h(lines[0]) for h in
                                         path_highlighters)))
                icon_for_path = icon(path)
                yield (icon_for_path,
                       highlit_path,
                       [(line['number'][0],
                         highlight(line['content'][0],
                                   chain.from_iterable(h(line) for h in
                                                       content_highlighters)))
                        for line in lines])
        else:
            for file in results:
                yield (icon(file['path'][0]),
                       highlight(file['path'][0],
                                 chain.from_iterable(
                                     h(file) for h in path_highlighters)),
                       [])

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

        # Case sensitive macro names
        cur.execute("""
            SELECT
                 (SELECT path FROM files WHERE files.id = macros.file_id) as path,
                 macros.file_line
              FROM macros WHERE macros.name = ? LIMIT 2
        """, (term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Case sensitive typedef names
        cur.execute("""
            SELECT
                 (SELECT path FROM files WHERE files.id = typedefs.file_id) as path,
                 typedefs.file_line
              FROM typedefs WHERE typedefs.name = ? LIMIT 2
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

        # Case insensitive macro names
        cur.execute("""
        SELECT
              (SELECT path FROM files WHERE files.id = macros.file_id) as path,
              macros.file_line
            FROM macros WHERE macros.name LIKE ? LIMIT 2
        """, (term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Case insensitive typedef names
        cur.execute("""
        SELECT
              (SELECT path FROM files WHERE files.id = typedefs.file_id) as path,
              typedefs.file_line
            FROM typedefs WHERE typedefs.name LIKE ? LIMIT 2
        """, (term,))
        rows = cur.fetchall()
        if rows and len(rows) == 1:
            return (rows[0]['path'], rows[0]['file_line'])

        # Okay we've got nothing
        return None


query_grammar = Grammar(ur'''
    query = _ terms
    terms = term*
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
        '|'.join(sorted((re.escape(filter_name) for
                                filter_name, filters in
                                FILTERS_NAMED.iteritems() if
                                filters[0].description),
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
    """Visitor that turns a parsed query into a list of dicts, one for each
    term.

    'path:ns*.cpp', for example, might become this::

        [{'name': 'path',
          'arg': 'ns*.cpp',
          'qualified': False,
          'not': False,
          'case_sensitive': False}]

    """
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

    def visit_terms(self, terms, the_terms):
        return the_terms

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
        term_dict['name'] = filter.text
        return term_dict

    def visit_text(self, text, ((some_text,), _)):
        """Create the dictionary that lives in Query.terms. Return it with a
        filter name of 'text', indicating that this is a bare or quoted run of
        text. If it is actually an argument to a filter,
        ``visit_filtered_term`` will overrule us later.

        """
        return {'name': 'text', 'arg': some_text}

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
    # TODO: Take a 'tree' arg, and return only filters registered by plugins
    # enabled on that tree. For this, we'll have to either add enabled plugins
    # per tree to the request-time config file or unify configs at last.
    return (dict(name=name, description=filters[0].description) for
            name, filters in
            FILTERS_NAMED.iteritems() if filters[0].description)


def highlight(content, extents):
    """Return ``content`` with the union of all ``extents`` highlighted.

    Put ``<b>`` before the beginning of each highlight and ``</b>`` at the
    end. Combine overlapping highlights.

    :arg content: The unicode string against which the extents are reported
    :arg extents: An iterable of unsorted, possibly overlapping (start offset,
        end offset) tuples describing each extent to highlight.

    Leading whitespace is stripped.

    """
    def chunks():
        chars_before = None
        for start, end in fix_extents_overlap(sorted(extents)):
            if start > end:
                raise ValueError('Extent start was after its end.')
            yield cgi.escape(content[chars_before:start])
            yield u'<b>'
            yield cgi.escape(content[start:end])
            yield u'</b>'
            chars_before = end
        # Make sure to get the rest of the line after the last highlight:
        yield cgi.escape(content[chars_before:])
    return ''.join(chunks()).lstrip()


def fix_extents_overlap(extents):
    """Take a sorted list of extents and yield the extents without overlaps."""
    # There must be two extents for there to be an overlap
    while len(extents) >= 2:
        # Take the two next extents
        start1, end1 = extents[0]
        start2, end2 = extents[1]
        # Check for overlap
        if end1 <= start2:
            # If no overlap, yield first extent
            yield start1, end1
            extents = extents[1:]  # This has got to be slow as death.
            continue
        # If overlap, yield extent from start1 to start2
        if start1 != start2:
            yield start1, start2
        extents[0] = start2, end1
        extents[1] = end1, end2
    if extents:
        yield extents[0]
