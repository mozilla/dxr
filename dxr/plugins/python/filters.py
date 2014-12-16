from jinja2 import Markup

from dxr.filters import NameFilterBase


class _PyFilter(NameFilterBase):
    lang = 'py'


class TypeFilter(_PyFilter):
    name = 'type'
    description = Markup("Class definition: <code>type:Stack</code>")


class FunctionFilter(_PyFilter):
    name = 'function'
    description = Markup("Function or method definition: <code>function:foo</code>")
