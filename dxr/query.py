import cgi
from itertools import chain, count, groupby
from operator import itemgetter
import re

from parsimonious import Grammar, NodeVisitor

from dxr.filters import LINE, FILE
from dxr.mime import icon
from dxr.utils import append_update, cached


@cached
def direct_searchers(plugins):
    """Return a list of all direct searchers, ordered by priority, then plugin
    name, then finally by function name.

    This is meant to at least yield a stable order if priorities are not
    unique.

    :arg plugins: An iterable of Plugins

    """
    sortables = []
    for plugin in plugins:
        for s in plugin.direct_searchers:
            sortables.append((s, (s.direct_search_priority, plugin.name, s.__name__)))
    sortables.sort(key=itemgetter(1))
    return [searcher for searcher, _ in sortables]


class Query(object):
    """Query object, constructor will parse any search query"""

    def __init__(self, es_search, querystr, enabled_plugins, is_case_sensitive=True):
        self.es_search = es_search
        self.is_case_sensitive = is_case_sensitive
        self.enabled_plugins = list(enabled_plugins)

        # A list of dicts describing query terms:
        grammar = query_grammar(self.enabled_plugins)
        self.terms = QueryVisitor(is_case_sensitive=is_case_sensitive).visit(grammar.parse(querystr))

    def single_term(self):
        """Return the single, non-negated textual term in the query.

        If there is more than one term in the query or if the single term is a
        non-textual one, return None.

        """
        if len(self.terms) == 1:
            term = self.terms[0]
            if term['name'] == 'text' and not term['not']:
                return term

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
        enabled_filters_by_name = filters_by_name(self.enabled_plugins)
        filters = [[f(term) for f in enabled_filters_by_name[term['name']]]
                   for term in self.terms]

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

        for searcher in direct_searchers(self.enabled_plugins):
            clause = searcher(term)
            if clause:
                results = self.es_search(
                    {
                        'query': {
                            'filtered': {
                                'query': {
                                    'match_all': {}
                                },
                                'filter': clause
                            }
                        },
                        'size': 2
                    },
                    doc_type=LINE)['hits']['hits']
                if len(results) == 1:
                    result = results[0]['_source']
                    # Everything is stored as arrays in ES. Pull it all out:
                    return result['path'][0], result['number'][0]
                elif len(results) > 1:
                    return None


@cached
def query_grammar(plugins):
    """Return a query-parsing grammar for some set of plugins.
    
    :arg plugins: An iterable of Plugins
    
    """
    return Grammar(ur'''
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
                             filters_by_name(plugins).iteritems() if
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


@cached
def filters_by_name(plugins):
    """Return a mapping of filter names to all filters with that name,
    regardless of whether they have descriptions

    :arg plugins: An iterable of plugins from which to get filters

    """
    return append_update(
        {},
        ((f.name, f) for f in
         chain.from_iterable(p.filters for p in plugins)))


def filter_menu_items(plugins):
    """Return the additional template variables needed to render filter.html.
    
    :arg plugins: An iterable of Plugins whose filters to put in the Filters
        menu
    
    """
    # TODO: Sort these in a stable order. But maybe common ones should be near
    # the top?
    return (dict(name=name, description=filters[0].description)
            for name, filters in filters_by_name(plugins).iteritems()
            if filters[0].description)


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
