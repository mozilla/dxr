"""Base classes and convenience functions for writing filters"""

from functools import wraps
from funcy import identity


# Domain constants:
FILE = 'file'
LINE = 'line'
IMAGE = 'image'


class Filter(object):
    """A provider of search strategy and highlighting

    Filter classes, which roughly correspond to the items in the Filters
    dropdown menu, tell DXR how to query the data stored in elasticsearch by
    :meth:`~dxr.plugins.FileToIndex.needles` and
    :meth:`~dxr.plugins.FileToIndex.needles_by_line`. An instance is created
    for each query term whose :attr:`name` matches and persists through the
    querying and highlighting phases.

    This is an optional base class that saves code on many filters. It also
    serves to document the filter API.

    :ivar name: The string prefix used in a query term to activate this
        filter. For example, if this were "path", this filter would be
        activated for the query term "path:foo". Multiple filters can be
        registered against a single name; they are ORed together. For example,
        it is good practice for a language plugin to query against a language
        specific needle (like "js-function") but register against the more
        generic "function" here. (This allows us to do language-specific
        queries.)
    :ivar domain: Either LINE or FILE. LINE means this filter returns results
        that point to specific lines of files; FILE means they point to files
        as a whole. Default: LINE.
    :ivar description: A description of this filter for the Filters menu:
        unicode or Markup (in case you want to wrap examples in ``<code>``
        tags). Of filters having the same name, the description of the first
        one encountered will be used. An empty description will hide a filter
        from the menu. This should probably be used only internally, by the
        TextFilter.

    """
    domain = LINE
    description = u''

    def __init__(self, term):
        """This is a good place to parse the term's arg (if it requires further
        parsing) and stash it away on the instance.

        Raise :class:`~dxr.exceptions.BadTerm` to complain to the user: for
        instance, about an unparseable term.

        """
        self._term = term

    def filter(self):
        """Return the ES filter clause that applies my restrictions to the
        found set of lines (or files and folders, if :attr:`domain` is FILES).

        To quietly do no filtration, return None. This would be suitable for
        ``path:*``, for example.

        To do no filtration and complain to the user about it, raise
        :class:`~dxr.exceptions.BadTerm`.

        We might even make this return a list of filter clauses, for things
        like the RegexFilter which want a bunch of match_phrases and a script.

        """
        raise NotImplementedError

    def highlight_path(self, result):
        """Return an unsorted iterable of extents that should be highlighted in
        the ``path`` field of a search result.

        :arg result: A mapping representing properties from a search result,
            whether a file or a line. With access to all the data, you can,
            for example, use the extents from a 'c-function' needle to inform
            the highlighting of the 'content' field.

        """
        return []

    def highlight_content(self, result):
        """Return an unsorted iterable of extents that should be highlighted in
        the ``content`` field of a search result.

        :arg result: A mapping representing properties from a search result,
            whether a file or a line. With access to all the data, you can,
            for example, use the extents from a 'c-function' needle to inform
            the highlighting of the 'content' field.

        """
        return []

    # A filter can eventually grow a "kind" attr that says "structural" or
    # "text" or whatever, and we can vary the highlight color or whatever based
    # on that to make identifiers easy to pick out visually.


def negatable(filter_method):
    """Decorator to wrap an ES "not" around a ``Filter.filter()`` method iff
    the term is negated.

    """
    @wraps(filter_method)
    def maybe_negate(self):
        positive = filter_method(self)
        return {'not': positive} if positive and self._term['not'] else positive
    return maybe_negate


class NameFilterBase(Filter):
    """An exact-match filter for things exposing a single value to compare
    against

    This filter assumes an object-shaped needle value with a 'name'
    subproperty (containing the symbol name) and a 'name.lower' folded to
    lowercase. Highlights are based on 'start' and 'end' subproperties, which
    contain column bounds.

    Derives the needle name from the ``name`` cls attribute.

    """
    def __init__(self, term):
        """Expects ``self.lang`` to be a language identifier, to separate
        structural needles from those of other languages and allow for an
        eventual "lang:" metafilter.

        """
        super(NameFilterBase, self).__init__(term)
        self._needle = '{0}_{1}'.format(self.lang, self.name.replace('-', '_'))

    def _term_filter(self, field):
        """Return a term filter clause that does a case-sensitive match
        against the given field.

        """
        return {
            'term': {'{needle}.{field}'.format(
                        needle=self._needle,
                        field=field):
                     self._term['arg']}
        }

    def _positive_filter(self):
        """Non-negated filter recipe, broken out for subclassing"""
        if self._term['case_sensitive']:
            return self._term_filter('name')
        else:
            # term filters have no query analysis phase. We must use a
            # match query, which is an analyzer pass + a term filter:
            return {
                'query': {
                    'match': {
                        '{needle}.name.lower'.format(needle=self._needle):
                            self._term['arg']
                    }
                }
            }

    @negatable
    def filter(self):
        """Find things by their "name" properties, case-sensitive or not.

        Ignore the term's "qualified" property.

        """
        return self._positive_filter()

    def _should_be_highlit(self, entity):
        """Return whether some entity should be highlit in the search results,
        based on its "name" property.

        :arg entity: A map, the value of a needle from a found line

        """
        maybe_lower = (identity if self._term['case_sensitive'] else
                       unicode.lower)
        return maybe_lower(entity['name']) == maybe_lower(self._term['arg'])

    def highlight_content(self, result):
        """Highlight any structural entity whose name matches the term.

        Compare short names and qualnames if this isn't a fully-qualified
        search. Otherwise, compare just qualnames.

        """
        if self._term['not']:
            return []
        return ((entity['start'], entity['end'])
                for entity in result.get(self._needle, ()) if
                self._should_be_highlit(entity))
