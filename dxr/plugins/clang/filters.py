from jinja2 import Markup

from dxr.filters import NameFilterBase, negatable


class _CFilter(NameFilterBase):
    lang = 'c'


class _QualifiedNameFilter(_CFilter):
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


class MacroFilter(_CFilter):
    name = 'macro'
    description = 'Macro definition'


class MacroRefFilter(_CFilter):
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


class WarningFilter(_CFilter):
    name = 'warning'
    description = 'Compiler warning messages'


class WarningOptFilter(_CFilter):
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
