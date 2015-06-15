from jinja2 import Markup

from dxr.filters import NameFilterBase, QualifiedNameFilterBase


class _CQualifiedNameFilter(QualifiedNameFilterBase):
    lang = 'c'


class _CNameFilter(NameFilterBase):
    lang = 'c'


class FunctionFilter(_CQualifiedNameFilter):
    name = 'function'
    description = Markup('Function or method definition: <code>function:foo</code>')


class FunctionRefFilter(_CQualifiedNameFilter):
    name = 'function-ref'
    description = 'Function or method references'


class FunctionDeclFilter(_CQualifiedNameFilter):
    name = 'function-decl'
    description = 'Function or method declaration'


class TypeRefFilter(_CQualifiedNameFilter):
    name = 'type-ref'
    description = 'Type or class references, uses, or instantiations'


class TypeDeclFilter(_CQualifiedNameFilter):
    name = 'type-decl'
    description = 'Type or class declaration'


class TypeFilter(_CQualifiedNameFilter):
    name = 'type'
    description = Markup('Type or class definition: <code>type:Stack</code>')


class VariableFilter(_CQualifiedNameFilter):
    name = 'var'
    description = 'Variable definition'


class VariableRefFilter(_CQualifiedNameFilter):
    name = 'var-ref'
    description = 'Variable uses (lvalue, rvalue, dereference, etc.)'


class VarDeclFilter(_CQualifiedNameFilter):
    name = 'var-decl'
    description = 'Variable declaration'


class MacroFilter(_CNameFilter):
    name = 'macro'
    description = 'Macro definition'


class MacroRefFilter(_CNameFilter):
    name = 'macro-ref'
    description = 'Macro uses'


class NamespaceFilter(_CQualifiedNameFilter):
    name = 'namespace'
    description = 'Namespace definition'


class NamespaceRefFilter(_CQualifiedNameFilter):
    name = 'namespace-ref'
    description = 'Namespace references'


class NamespaceAliasFilter(_CQualifiedNameFilter):
    name = 'namespace-alias'
    description = 'Namespace alias'


class NamespaceAliasRefFilter(_CQualifiedNameFilter):
    name = 'namespace-alias-ref'
    description = 'Namespace alias references'


class WarningFilter(_CNameFilter):
    name = 'warning'
    description = 'Compiler warning messages'


class WarningOptFilter(_CNameFilter):
    name = 'warning-opt'
    description = 'Warning messages brought on by a given compiler command-line option'


class CallerFilter(_CQualifiedNameFilter):
    name = 'callers'
    description = Markup('Calls to the given function or method: <code>callers:GetStringFromName</code>')

    def __init__(self, term):
        """Massage the needle name so we don't have to call our needle "callers"."""
        super(CallerFilter, self).__init__(term)
        self._needle = '{0}_call'.format(self.lang)


class ParentFilter(_CQualifiedNameFilter):
    name = 'bases'
    description = Markup('Superclasses of a class: <code>bases:SomeSubclass</code>')


class ChildFilter(_CQualifiedNameFilter):
    name = 'derived'
    description = Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>')


class MemberFilter(_CQualifiedNameFilter):
    name = 'member'
    description = Markup('Member variables, types, or methods of a class: <code>member:SomeClass</code>')


class OverridesFilter(_CQualifiedNameFilter):
    name = 'overrides'
    description = Markup('Methods which override the given one: <code>overrides:someMethod</code>')


class OverriddenFilter(_CQualifiedNameFilter):
    name = 'overridden'
    description = Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:Derived::foo()</code>.')
