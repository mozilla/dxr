from jinja2 import Markup

from dxr.plugins.utils import ExactMatchExtentFilterBase


class _CFilter(ExactMatchExtentFilterBase):
    """Exact-match filter for structural entities in C or C++"""
    lang = 'c'


class FunctionFilter(_CFilter):
    name = 'function'
    description = Markup('Function or method definition: <code>function:foo</code>')


class FunctionRefFilter(_CFilter):
    name = 'function-ref'
    description = 'Function or method references'


class FunctionDeclFilter(_CFilter):
    name = 'function-decl'
    description = 'Function or method declaration'


class TypeRefFilter(_CFilter):
    name = 'type-ref'
    description = 'Type or class references, uses, or instantiations'


class TypeDeclFilter(_CFilter):
    name = 'type-decl'
    description = 'Type or class declaration'


class TypeFilter(_CFilter):
    name = 'type'
    description = 'Type, function, or class definition: <code>type:Stack</code>'


class VariableFilter(_CFilter):
    name = 'var'
    description = 'Variable definition'


class VariableRefFilter(_CFilter):
    name = 'var-ref'
    description = 'Variable uses (lvalue, rvalue, dereference, etc.)'


class VarDeclFilter(_CFilter):
    name = 'var-decl'
    description = 'Type or class declaration'


class MacroFilter(_CFilter):
    name = 'macro'
    description = 'Macro definition'


class MacroRefFilter(_CFilter):
    name = 'macro-ref'
    description = 'Macro uses'


class NamespaceFilter(_CFilter):
    name = 'namespace'
    description = 'Namespace definition'


class NamespaceRefFilter(_CFilter):
    name = 'namespace-ref'
    description = 'Namespace references'


class NamespaceAliasFilter(_CFilter):
    name = 'namespace-alias'
    description = 'Namespace alias'


class NamespaceAliasRefFilter(_CFilter):
    name = 'namespace-alias-ref'
    description = 'Namespace alias references'


class WarningFilter(_CFilter):
    name = 'warning'
    description = 'Compiler warning messages'


class WarningOptFilter(_CFilter):
    name = 'warning-opt'
    description = 'Warning messages brought on by a given compiler command-line option'


class CalleeFilter(_CFilter):
    name = 'called-by'
    description = 'Functions or methods which are called by the given one'


class CallerFilter(_CFilter):
    name = 'callers'
    description = Markup('Functions which call the given function or method: <code>callers:GetStringFromName</code>')


class ChildFilter(_CFilter):
    name = 'bases'
    description = Markup('Superclasses of a class: <code>bases:SomeSubclass</code>')


class ParentFilter(_CFilter):
    name = 'derived'
    description = Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>')


class MemberFilter(_CFilter):
    name = 'member'
    description = Markup('Member variables, types, or methods of a class: <code>member:SomeClass</code>')


class OverridesFilter(_CFilter):
    name = 'overrides'
    description = Markup('Methods which override the given one: <code>overrides:someMethod</code>')


class OverriddenFilter(_CFilter):
    name = 'overridden'
    description = Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:Derived::foo()</code>.')
