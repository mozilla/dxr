from jinja2 import Markup

from dxr.filters import QualifiedNameFilterBase


class _PyFilter(QualifiedNameFilterBase):
    lang = 'py'


class TypeFilter(_PyFilter):
    name = 'type'
    description = Markup("Class definition: <code>type:Stack</code>")


class FunctionFilter(_PyFilter):
    name = 'function'
    description = Markup("Function or method definition: <code>function:foo</code>")


class DerivedFilter(_PyFilter):
    name = 'derived'
    description = Markup("Subclasses of a class: <code>derived:SomeSuperclass</code>")


class BasesFilter(_PyFilter):
    name = 'bases'
    description = Markup("Superclasses of a class: <code>bases:SomeSubclass</code>")
