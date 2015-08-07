from jinja2 import Markup

from dxr.filters import NameFilterBase

PLUGIN_NAME = 'xpidl'


class _XpidlFilter(NameFilterBase):
    lang = 'xpidl'


class TypeFilter(_XpidlFilter):
    name = 'type-decl'
    is_identifier = True
    description = Markup('Interface definition: <code>type-decl:IStack</code>')


class MethodFilter(_XpidlFilter):
    name = 'function-decl'
    is_identifier = True
    description = Markup('Interface method declaration: <code>function-decl:getTarget</code>')


class VarFilter(_XpidlFilter):
    name = 'var-decl'
    is_identifier = True
    description = Markup('Interface variable declaration: <code>var-decl:EVENT_SHOW</code>')


class DerivedFilter(_XpidlFilter):
    name = 'derived'
    description = Markup('Derived interface: <code>derived:ParentInterface</code>')
