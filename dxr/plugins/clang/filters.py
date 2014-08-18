from jinja2 import Markup
from functools import partial

from dxr.plugins.utils import needle_filter_factory


c_needle_filter_factory = partial(needle_filter_factory, 'c')


FunctionFilter = c_needle_filter_factory('function', Markup('Function or method definition: <code>function:foo</code>'))
FunctionRefFilter = c_needle_filter_factory('function-ref', 'Function or method references')
FunctionDeclFilter = c_needle_filter_factory('function-decl', 'Function or method declaration')
TypeRefFilter = c_needle_filter_factory('type-ref', 'Type or class references, uses, or instantiations')
TypeDeclFilter = c_needle_filter_factory('type-decl', 'Type or class declaration')
TypeFilter = c_needle_filter_factory('type', 'Type, function, or class definition: <code>type:Stack</code>')
VariableFilter = c_needle_filter_factory('variable', 'Variable definition')
VariableRefFilter = c_needle_filter_factory('variable', 'Variable uses (lvalue, rvalue, dereference, etc.)')
VarDeclFilter = c_needle_filter_factory('Variable declaration', 'Type or class declaration')
MacroFilter = c_needle_filter_factory('macro', 'Macro definition')
MacroRefFilter = c_needle_filter_factory('macro-ref', 'Macro uses')
NamespaceFilter = c_needle_filter_factory('namespace', 'Namespace definition')
NamespaceRefFilter = c_needle_filter_factory('namespace-ref', 'Namespace references')
NamespaceAliasFilter = c_needle_filter_factory('namespace-alias', 'Namespace alias')
NamespaceAliasRefFilter = c_needle_filter_factory('namespace-alias-ref', 'Namespace alias references')
WarningFilter = c_needle_filter_factory('warning', 'Compiler warning messages')
WarningOptFilter = c_needle_filter_factory('warning-opt', 'Warning messages brought on by a given compiler command-line option')
CalleeFilter = c_needle_filter_factory('callee', 'Functions or methods which are called by the given one')
CallerFilter = c_needle_filter_factory('caller', Markup('Functions which call the given function or method: <code>callers:GetStringFromName</code>'))
ChildFilter = c_needle_filter_factory('child', Markup('Superclasses of a class: <code>bases:SomeSubclass</code>'))
ParentFilter = c_needle_filter_factory('parent', Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>'))
MemberFilter = c_needle_filter_factory('member', Markup('Member variables, types, or methods of a class: <code>member:SomeClass</code>'))
OverridesFilter = c_needle_filter_factory('overrides', Markup('Methods which override the given one: <code>overrides:someMethod</code>'))
OverriddenFilter = c_needle_filter_factory('overridden', Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:Derived::foo()</code>.'))
