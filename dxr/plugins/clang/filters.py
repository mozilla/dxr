from funcy import identity
from jinja2 import Markup

from dxr.filters import Filter, negatable


class _SymbolFilter(Filter):
    """An exact-match filter for named symbols

    This filter assumes an object-shaped needle value with a 'name'
    subproperty (containing the symbol name), a 'name.lower' folded to
    lowercase, and 'qualname' and 'qualname.lower' (doing the same for
    fully-qualified name). Highlights are based on 'start' and 'end'
    subproperties, which contain column bounds.

    Derives the needle name from the ``name`` cls attribute.

    """
    lang = 'c'

    def __init__(self, term):
        """Expects ``self.lang`` to be a language identifier, to separate
        structural needles from those of other languages and allow for an
        eventual "lang:" metafilter.

        """
        super(_SymbolFilter, self).__init__(term)
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
            if self._term['case_sensitive']:
                name_filter = self._term_filter('name')
            else:
                # term filters have no query analysis phase. We must use a
                # match query, which is an analyzer pass + a term filter:
                name_filter = {
                    'query': {
                        'match': {
                            '{needle}.name.lower'.format(needle=self._needle):
                                self._term['arg']
                        }
                    }
                }
            return {'or': [name_filter,
                           self._term_filter('qualname')]}

    def highlight_content(self, result):
        # TODO: Update for case, qualified, etc.
        if self._term['not']:
            return []
        maybe_lower = (identity if self._term['case_sensitive'] else
                       unicode.lower)
        return ((entity['start'], entity['end'])
                for entity in result[self._needle]
                if maybe_lower(entity['name']) == maybe_lower(self._term['arg'])
                or entity['qualname'] == self._term['arg'])


class FunctionFilter(_SymbolFilter):
    name = 'function'
    description = Markup('Function or method definition: <code>function:foo</code>')


class FunctionRefFilter(_SymbolFilter):
    name = 'function-ref'
    description = 'Function or method references'


class FunctionDeclFilter(_SymbolFilter):
    name = 'function-decl'
    description = 'Function or method declaration'


class TypeRefFilter(_SymbolFilter):
    name = 'type-ref'
    description = 'Type or class references, uses, or instantiations'


class TypeDeclFilter(_SymbolFilter):
    name = 'type-decl'
    description = 'Type or class declaration'


class TypeFilter(_SymbolFilter):
    name = 'type'
    description = 'Type, function, or class definition: <code>type:Stack</code>'


class VariableFilter(_SymbolFilter):
    name = 'var'
    description = 'Variable definition'


class VariableRefFilter(_SymbolFilter):
    name = 'var-ref'
    description = 'Variable uses (lvalue, rvalue, dereference, etc.)'


class VarDeclFilter(_SymbolFilter):
    name = 'var-decl'
    description = 'Type or class declaration'


class MacroFilter(_SymbolFilter):
    name = 'macro'
    description = 'Macro definition'


class MacroRefFilter(_SymbolFilter):
    name = 'macro-ref'
    description = 'Macro uses'


class NamespaceFilter(_SymbolFilter):
    name = 'namespace'
    description = 'Namespace definition'


class NamespaceRefFilter(_SymbolFilter):
    name = 'namespace-ref'
    description = 'Namespace references'


class NamespaceAliasFilter(_SymbolFilter):
    name = 'namespace-alias'
    description = 'Namespace alias'


class NamespaceAliasRefFilter(_SymbolFilter):
    name = 'namespace-alias-ref'
    description = 'Namespace alias references'


class WarningFilter(_SymbolFilter):
    name = 'warning'
    description = 'Compiler warning messages'


class WarningOptFilter(_SymbolFilter):
    name = 'warning-opt'
    description = 'Warning messages brought on by a given compiler command-line option'


class CalleeFilter(_SymbolFilter):
    name = 'called-by'
    description = 'Functions or methods which are called by the given one'


class CallerFilter(_SymbolFilter):
    name = 'callers'
    description = Markup('Functions which call the given function or method: <code>callers:GetStringFromName</code>')


class ChildFilter(_SymbolFilter):
    name = 'bases'
    description = Markup('Superclasses of a class: <code>bases:SomeSubclass</code>')


class ParentFilter(_SymbolFilter):
    name = 'derived'
    description = Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>')


class MemberFilter(_SymbolFilter):
    name = 'member'
    description = Markup('Member variables, types, or methods of a class: <code>member:SomeClass</code>')


class OverridesFilter(_SymbolFilter):
    name = 'overrides'
    description = Markup('Methods which override the given one: <code>overrides:someMethod</code>')


class OverriddenFilter(_SymbolFilter):
    name = 'overridden'
    description = Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:Derived::foo()</code>.')
