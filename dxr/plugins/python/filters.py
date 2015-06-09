from jinja2 import Markup

from dxr.filters import FILE, NameFilterBase, QualifiedNameFilterBase


class _QualifiedPyFilter(QualifiedNameFilterBase):
    lang = 'py'


class _PyFilter(NameFilterBase):
    lang = 'py'


class ModuleFilter(_QualifiedPyFilter):
    name = 'module'
    domain = FILE
    is_identifier = True
    description = Markup("Module definition: <code>module:module.name</code>")


class TypeFilter(_PyFilter):
    name = 'type'
    is_identifier = True
    description = Markup('Class definition: <code>type:Stack</code>')


class FunctionFilter(_PyFilter):
    name = 'function'
    is_identifier = True
    description = Markup('Function or method definition: <code>function:foo</code>')


class DerivedFilter(_QualifiedPyFilter):
    name = 'derived'
    description = Markup('Subclasses of a class: <code>derived:SomeSuperclass</code>')


class BasesFilter(_QualifiedPyFilter):
    name = 'bases'
    description = Markup('Superclasses of a class: <code>bases:SomeSubclass</code>')


class CallersFilter(_PyFilter):
    name = 'callers'
    is_reference = True
    description = Markup('Calls to the given function: <code>callers:some_function</code>')


class OverridesFilter(_QualifiedPyFilter):
    name = 'overrides'
    description = Markup('Methods which override the given one: <code>overrides:some_method</code>')


class OverriddenFilter(_QualifiedPyFilter):
    name = 'overridden'
    description = Markup('Methods which are overridden by the given one. Useful mostly with fully qualified methods, like <code>+overridden:foo.bar.some_method</code>.')
