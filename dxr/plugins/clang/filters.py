from funcy import identity
from jinja2 import Markup

from dxr.filters import Filter, negatable


class _NameFilter(Filter):
    """An exact-match filter for things exposing a single value to compare
    against

    This filter assumes an object-shaped needle value with a 'name'
    subproperty (containing the symbol name) and a 'name.lower' folded to
    lowercase. Highlights are based on 'start' and 'end' subproperties, which
    contain column bounds.

    Derives the needle name from the ``name`` cls attribute.

    """
    lang = 'c'

    def __init__(self, term):
        """Expects ``self.lang`` to be a language identifier, to separate
        structural needles from those of other languages and allow for an
        eventual "lang:" metafilter.

        """
        super(_NameFilter, self).__init__(term)
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
                for entity in result[self._needle] if
                self._should_be_highlit(entity))


class _QualifiedNameFilter(_NameFilter):
    """An exact-match filter for symbols having names and qualnames

    This filter assumes an object-shaped needle value with a 'name'
    subproperty (containing the symbol name), a 'name.lower' folded to
    lowercase, and 'qualname' and 'qualname.lower' (doing the same for
    fully-qualified name). Highlights are based on 'start' and 'end'
    subproperties, which contain column bounds.

    """
    @negatable
    def filter(self):
        """Find functions by their name or qualname.

        "+" searches look at just qualnames, but non-"+" searches look at both
        names and qualnames. All comparisons against qualnames are
        case-sensitive, because, if you're being that specific, that's
        probably what you want.

        """
        if self._term['qualified']:
            return self._term_filter('qualname')
        else:
            return {'or': [super(_QualifiedNameFilter, self)._positive_filter(),
                           self._term_filter('qualname')]}

    def _should_be_highlit(self, entity):
        """Return whether a structural entity should be highlit, according to
        names and qualnames.

        Compare short names and qualnames if this is a regular search. Compare
        just qualnames if it's a qualified search.

        """
        return ((not self._term['qualified'] and
                 super(_QualifiedNameFilter, self)._should_be_highlit(entity))
                or entity['qualname'] == self._term['arg'])


class FunctionFilter(_QualifiedNameFilter):
    name = 'function'
    description = Markup('Function or method definition: <code>function:foo</code>')


class FunctionRefFilter(_QualifiedNameFilter):
    name = 'function-ref'
    description = 'Function or method references'


class FunctionDeclFilter(_QualifiedNameFilter):
    name = 'function-decl'
    description = 'Function or method declaration'


class TypeRefFilter(_QualifiedNameFilter):
    name = 'type-ref'
    description = 'Type or class references, uses, or instantiations'


class TypeDeclFilter(_QualifiedNameFilter):
    name = 'type-decl'
    description = 'Type or class declaration'


class TypeFilter(_QualifiedNameFilter):
    name = 'type'
    description = Markup('Type, function, or class definition: <code>type:Stack</code>')


class VariableFilter(_QualifiedNameFilter):
    name = 'var'
    description = 'Variable definition'


class VariableRefFilter(_QualifiedNameFilter):
    name = 'var-ref'
    description = 'Variable uses (lvalue, rvalue, dereference, etc.)'


class VarDeclFilter(_QualifiedNameFilter):
    name = 'var-decl'
    description = 'Variable declaration'


class MacroFilter(_NameFilter):
    name = 'macro'
    description = 'Macro definition'


class MacroRefFilter(_NameFilter):
    name = 'macro-ref'
    description = 'Macro uses'


class NamespaceFilter(_QualifiedNameFilter):
    name = 'namespace'
    description = 'Namespace definition'


class NamespaceRefFilter(_QualifiedNameFilter):
    name = 'namespace-ref'
    description = 'Namespace references'


class NamespaceAliasFilter(_QualifiedNameFilter):
    name = 'namespace-alias'
    description = 'Namespace alias'


class NamespaceAliasRefFilter(_QualifiedNameFilter):
    name = 'namespace-alias-ref'
    description = 'Namespace alias references'


class WarningFilter(_NameFilter):
    name = 'warning'
    description = 'Compiler warning messages'


class WarningOptFilter(_NameFilter):
    name = 'warning-opt'
    description = 'Warning messages brought on by a given compiler command-line option'


class CallerFilter(_QualifiedNameFilter):
    name = 'callers'
    description = Markup('Functions which call the given function or method: <code>callers:GetStringFromName</code>')

    def __init__(self, term):
        """Massage the needle name so we don't have to call our needle "callers"."""
        super(CallerFilter, self).__init__(term)
        self._needle = '{0}_call'.format(self.lang)


class ChildFilter(_QualifiedNameFilter):
    name = 'bases'
    description = Markup('Superclasses of a class: <code>bases:SomeSubclass</code>')


class ParentFilter(_QualifiedNameFilter):
    name = 'derived'
    description = Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>')


class MemberFilter(_QualifiedNameFilter):
    name = 'member'
    description = Markup('Member variables, types, or methods of a class: <code>member:SomeClass</code>')


class OverridesFilter(_QualifiedNameFilter):
    name = 'overrides'
    description = Markup('Methods which override the given one: <code>overrides:someMethod</code>')


class OverriddenFilter(_QualifiedNameFilter):
    name = 'overridden'
    description = Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:Derived::foo()</code>.')
