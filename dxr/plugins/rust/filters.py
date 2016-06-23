from jinja2 import Markup
from dxr.filters import QualifiedNameFilterBase


class _QualifiedNameFilter(QualifiedNameFilterBase):
    lang = "rust"

class FunctionFilter(_QualifiedNameFilter):
    name = 'function'
    is_identifier = True
    description = Markup('Function or method definition: <code>function:foo</code>')

class FunctionRefFilter(_QualifiedNameFilter):
    name = 'function-ref'
    is_reference = True
    description = 'Function or method references'

class CallersFilter(_QualifiedNameFilter):
    name = 'callers'
    is_reference = True
    description = 'Function callers'

class FnImplsFilter(_QualifiedNameFilter):
    name = 'fn-impls'
    is_identifier = True
    description = 'Function implementations'

class DerivedFilter(_QualifiedNameFilter):
    name = 'derived'
    description = 'Sub-traits'

class BasesFilter(_QualifiedNameFilter):
    name = 'bases'
    description = 'Super-traits'

class ImplFilter(_QualifiedNameFilter):
    name = 'impl'
    is_reference = True
    description = 'Implementations'

class ModuleFilter(_QualifiedNameFilter):
    name = 'module'
    is_identifier = True
    description = 'Module defintions'

class ModuleUseFilter(_QualifiedNameFilter):
    name = 'module-use'
    is_reference = True
    description = 'Module imports'

class VarFilter(_QualifiedNameFilter):
    name = 'var'
    is_identifier = True
    description = 'Variable definitions'

class VarRefFilter(_QualifiedNameFilter):
    name = 'var-ref'
    is_reference = True
    description = 'Variable references'

class TypeFilter(_QualifiedNameFilter):
    name = 'type'
    is_identifier = True
    description = 'Type (struct, enum, type, trait) definition'

class TypeRefFilter(_QualifiedNameFilter):
    name = 'type-ref'
    is_reference = True
    description = 'Type references'

class ModuleRefFilter(_QualifiedNameFilter):
    name = 'module-ref'
    is_reference = True
    description = 'Module references'

class ModuleAliasRefFilter(_QualifiedNameFilter):
    name = 'module-alias-ref'
    description = 'Module alias references'
    is_reference = True

class ExternRefFilter(_QualifiedNameFilter):
    name = 'extern-ref'
    is_reference = True
    description = 'References to items in external crate'

