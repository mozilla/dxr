from jinja2 import Markup
from dxr.filters import NameFilterBase, QualifiedNameFilterBase
from dxr.plugins.xbl.refs import PLUGIN_NAME


class _NameFilter(NameFilterBase):
    lang = PLUGIN_NAME


class _QualifiedNameFilter(QualifiedNameFilterBase):
    lang = PLUGIN_NAME


class PropFilter(_QualifiedNameFilter):
    name = 'prop'
    is_identifier = True
    description = Markup('XBL property definition filter: <code>prop:foo</code>')


class TypeFilter(_NameFilter):
    name = 'type'
    is_identifier = True
    description = Markup('XBL interface implementation filter: <code>type:nsInterface</code>')
