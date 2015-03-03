from jinja2 import Markup

from dxr.filters import NameFilterBase, QualifiedNameFilterBase


class _QualifiedPyFilter(QualifiedNameFilterBase):
    lang = 'py'


class _PyFilter(NameFilterBase):
    lang = 'py'


class TypeFilter(_PyFilter):
    name = 'type'
    description = Markup("Class definition: <code>type:Stack</code>")


class FunctionFilter(_PyFilter):
    name = 'function'
    description = Markup("Function or method definition: <code>function:foo</code>")


class DerivedFilter(_QualifiedPyFilter):
    name = 'derived'
    description = Markup("Subclasses of a class: <code>derived:SomeSuperclass</code>")


class BasesFilter(_QualifiedPyFilter):
    name = 'bases'
    description = Markup("Superclasses of a class: <code>bases:SomeSubclass</code>")


class CallersFilter(_PyFilter):
    name = 'callers'
    description = Markup("Functions which call the given function: <code>callers:some_function</code>")
