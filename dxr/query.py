import cgi
from itertools import chain, groupby
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

    def __init__(self, es_search, querystr, enabled_plugins):
        self.es_search = es_search
        self.enabled_plugins = list(enabled_plugins)

        # A list of dicts describing query terms:
        grammar = query_grammar(self.enabled_plugins)
        self.terms = QueryVisitor().visit(grammar.parse(querystr))

    def single_term(self):
        """Return the single, non-negated textual term in the query.

        If there is more than one term in the query or if the single term is a
        non-textual one, return None.

        """
        if len(self.terms) == 1:
            term = self.terms[0]
            if term['name'] == 'text' and not term['not']:
                return term

    def _line_query_results(self, filters, results, path_highlighters):
        """Return an iterable of results of a LINE-domain query."""
        content_highlighters = [f.highlight_content for f in chain.from_iterable(filters)
                                if hasattr(f, 'highlight_content')]

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
                     highlight(line['content'][0].rstrip('\n\r'),
                               chain.from_iterable(h(line) for h in
                                                   content_highlighters)))
                    for line in lines])

    def _file_query_results(self, results, path_highlighters):
        """Return an iterable of results of a FILE-domain query."""
        for file in results:
            yield (icon(file['path'][0], file.get('is_binary', False)),
                   highlight(file['path'][0],
                             chain.from_iterable(
                                 h(file) for h in path_highlighters)),
                   [])

    def results(self, offset=0, limit=100):
        """Return a count of search results and, as an iterable, the results
        themselves::

            {'result_count': 12,
             'results': [(icon,
                          path within tree,
                          [(line_number, highlighted_line_of_code), ...]),
                         ...]}

        """
        enabled_filters_by_name = filters_by_name(self.enabled_plugins)

        def group_filters_by_term(predicate):
            """Return an iterable of lists of ES filters for each term, filtered on
            predicate(Filter)."""

            return ([f(term, self.enabled_plugins) for f in enabled_filters_by_name[term['name']]
                     if predicate(f)] for term in self.terms)

        def group_filters_by_name(predicate):
            """Return an iterable of a list of ES filters for each unique filter name, filtered on
            predicate(Filter)."""

            d = {}
            for term in self.terms:
                for f in enabled_filters_by_name[term['name']]:
                    if predicate(f):
                        d.setdefault(term['name'], []).append(f(term, self.enabled_plugins))
            return d.itervalues()

        # Instantiate applicable filters, yielding a list of lists, each inner
        # list representing the filters of the name of the parallel term. We
        # will OR the elements of the inner lists and then AND those OR balls
        # together.
        # Some filters, such as ExtFilter, do not make sense to be AND'ed together, so we move
        # them all to their own lists at the end of the regular filters list, such that they
        # will be joined by OR instead.
        filters = list(chain(group_filters_by_term(lambda f: not f.union_only),
                             group_filters_by_name(lambda f: f.union_only)))
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
            # Filter out all FILE docs who are links.
            ors.append({'not': {'exists': {'field': 'link'}}})

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
            doc_type=LINE if is_line_query else FILE)['hits']
        result_count = results['total']
        results = [r['_source'] for r in results['hits']]

        path_highlighters = [f.highlight_path for f in chain.from_iterable(filters)
                             if hasattr(f, 'highlight_path')]
        return {'result_count': result_count,
                'results': self._line_query_results(filters, results, path_highlighters)
                           if is_line_query
                           else self._file_query_results(results, path_highlighters)}

        # Test: If var-ref (or any structural query) returns 2 refs on one line, they should both get highlit.

    def direct_result(self):
        """Return a single search result that is an exact match for the query.

        If there is such a result, return a tuple of (path from root of tree,
        line number). Line number may be None to indicate the entire file
        rather than any specific line. If no result is found, return just None.

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
                    doc_type=searcher.domain)['hits']['hits']
                if len(results) == 1:
                    result = results[0]['_source']
                    # Everything is stored as arrays in ES. Pull it all out:
                    return (result['path'][0],
                            result['number'][0] if searcher.domain == LINE else None)
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
        positive_term = filtered_term / cased_text / text

        # A term with a filter name prepended:
        filtered_term = maybe_plus filter ":" (cased_text / text)

        # Bare or quoted text, possibly with spaces. Not empty.
        cased_text = case text
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
        # Stick an @ in front of text to negate the case-sensitivity guess.
        case = "@"

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
          'not': False}]

    """
    visit_positive_term = NodeVisitor.lift_child

    def __init__(self):
        """Construct.
        """
        super(NodeVisitor, self).__init__()

    def visit_query(self, query, (_, terms)):
        """Return a list of query term term_dicts."""
        return terms

    def visit_terms(self, terms, the_terms):
        return the_terms

    def visit_term(self, term, (term_dict,)):
        """Set the case-sensitive bit and, if not already set, a default not
        bit."""
        term_dict.setdefault('not', False)
        term_dict.setdefault('qualified', False)
        return term_dict

    def visit_not_term(self, not_term, (not_, term_dict)):
        """Add "not" bit to the term_dict."""
        term_dict['not'] = True
        return term_dict

    def visit_filtered_term(self, filtered_term, (plus, filter, colon, (term_dict,))):
        """Add fully-qualified indicator and the filter name to the term_dict."""
        term_dict['qualified'] = plus.text == '+'
        term_dict['name'] = filter.text
        return term_dict

    def visit_cased_text(self, cased_text, (at_, term_dict)):
        """Force case_sensitive to True in the term_dict."""
        term_dict['case_sensitive'] = True
        return term_dict

    def visit_text(self, text, ((some_text,), _)):
        """Create the dictionary that lives in Query.terms. Return it with a
        filter name of 'text', indicating that this is a bare or quoted run of
        text. If it is actually an argument to a filter,
        ``visit_filtered_term`` will overrule us later.

        """
        # Case-sensitive if there's any uppercase characters in the term.
        case_sensitive = any((c.isupper() for c in some_text))
        return {'name': 'text', 'arg': some_text, 'case_sensitive': case_sensitive}

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


def some_filters(plugins, condition):
    """Return a list of filters of the given plugins for which condition(filter) is True.

    :arg plugins: An iterable of plugins
    :arg condition: A function which takes a filter and returns True or False

    """
    return filter(condition, chain.from_iterable(p.filters for p in plugins))


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


@cached
def lang_badge_colors(plugins):
    """Return a mapping of filter languages to their badge colors as defined by
    provided plugins.

    :arg plugins: An iterable of plugins from which to get badge colors

    """
    badges = {}
    for p in plugins:
        if p.badge_colors:
            badges.update(p.badge_colors)
    return badges


def filter_menu_items(plugins):
    """Return the additional template variables needed to render filter.html.

    :arg plugins: An iterable of Plugins whose filters to put in the Filters
        menu

    Language-agnostic filters come first (as they happen to be among the most
    useful ones and are relatively few), then the rest, alphabetically.

    """
    # Concretize to iterate over it more than once.
    plugins = list(plugins)
    sorted_filters_by_name = sorted(
        ((name, filters) for name, filters in filters_by_name(plugins).iteritems()),
        key=lambda (name, filters): (hasattr(filters[0], 'lang'), name))
    badge_colors = lang_badge_colors(plugins)
    return (dict(name=name,
                 description=filters[0].description,
                 badges=sorted((f.lang, badge_colors.get(f.lang)) for f in filters if hasattr(f, 'lang')))
            for name, filters in sorted_filters_by_name
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
    """Return a sorted iterable of extents whose effect is to highlight the
    same characters the passed-in ones did but without overlapping each other.

    :arg extents: A sorted iterable of (start, end) extent tuples

    """
    cur = init = -1, -1
    for nex in extents:
        if cur[0] <= nex[0] <= cur[1]:
            # nex overlaps cur or comes directly after it. Combine them.
            cur = cur[0], nex[1]
        else:  # nex and cur are disjoint
            if cur is not init:
                yield cur
            cur = nex
    if cur is not init:
        yield cur
