from jinja2 import Markup

from dxr.filters import NameFilterBase, QualifiedNameFilterBase


class _CQualifiedNameFilter(QualifiedNameFilterBase):
    lang = 'c'


class _CNameFilter(NameFilterBase):
    lang = 'c'


class FunctionFilter(_CQualifiedNameFilter):
    name = 'function'
    is_identifier = True
    description = Markup('Function or method definition: <code>function:foo</code>')


class FunctionRefFilter(_CQualifiedNameFilter):
    name = 'function-ref'
    is_reference = True
    description = 'Function or method references'


class FunctionDeclFilter(_CQualifiedNameFilter):
    name = 'function-decl'
    description = 'Function or method declaration'


class TypeRefFilter(_CQualifiedNameFilter):
    name = 'type-ref'
    is_reference = True
    description = 'Type or class references, uses, or instantiations'


class TypeDeclFilter(_CQualifiedNameFilter):
    name = 'type-decl'
    description = 'Type or class declaration'


class TypeFilter(_CQualifiedNameFilter):
    name = 'type'
    is_identifier = True
    description = Markup('Type or class definition: <code>type:Stack</code>')


class VariableFilter(_CQualifiedNameFilter):
    name = 'var'
    is_identifier = True
    description = 'Variable definition'


class VariableRefFilter(_CQualifiedNameFilter):
    name = 'var-ref'
    is_reference = True
    description = 'Variable uses (lvalue, rvalue, dereference, etc.)'


class VarDeclFilter(_CQualifiedNameFilter):
    name = 'var-decl'
    description = 'Variable declaration'


class MacroFilter(_CNameFilter):
    name = 'macro'
    is_identifier = True
    description = 'Macro definition'


class MacroRefFilter(_CNameFilter):
    name = 'macro-ref'
    is_reference = True
    description = 'Macro uses'


class NamespaceFilter(_CQualifiedNameFilter):
    name = 'namespace'
    is_identifier = True
    description = 'Namespace definition'


class NamespaceRefFilter(_CQualifiedNameFilter):
    name = 'namespace-ref'
    is_reference = True
    description = 'Namespace references'


class NamespaceAliasFilter(_CQualifiedNameFilter):
    name = 'namespace-alias'
    is_identifier = True
    description = 'Namespace alias'


class NamespaceAliasRefFilter(_CQualifiedNameFilter):
    name = 'namespace-alias-ref'
    is_reference = True
    description = 'Namespace alias references'


class WarningFilter(_CNameFilter):
    name = 'warning'
    description = 'Compiler warning messages'


class WarningOptFilter(_CNameFilter):
    name = 'warning-opt'
    description = 'Warning messages brought on by a given compiler command-line option'


class CallerFilter(_CQualifiedNameFilter):
    name = 'callers'
    is_reference = True
    description = Markup('Calls to the given function or method: <code>callers:GetStringFromName</code>')

    def __init__(self, term, enabled_plugins):
        """Massage the needle name so we don't have to call our needle "callers"."""
        super(CallerFilter, self).__init__(term, enabled_plugins)
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
