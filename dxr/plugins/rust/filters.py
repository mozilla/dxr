from funcy import identity
from jinja2 import Markup
from dxr.filters import QualifiedNameFilterBase, Filter, negatable

class _QualifiedNameFilter(QualifiedNameFilterBase):
    lang = "rust"

class FunctionFilter(_QualifiedNameFilter):
    name = 'function'
    description = Markup('Function or method definition: <code>function:foo</code>')

class FunctionRefFilter(_QualifiedNameFilter):
    name = 'function-ref'
    description = 'Function or method references'

class CallersFilter(_QualifiedNameFilter):
    name = 'callers'
    description = 'Function callers'

class CalledByFilter(_QualifiedNameFilter):
    name = 'called-by'
    description = 'Functions called by this function'

class FnImplsFilter(_QualifiedNameFilter):
    name = 'fn-impls'
    description = 'Function implementations'

class DerivedFilter(_QualifiedNameFilter):
    name = 'derived'
    description = 'Sub-traits'

class BasesFilter(_QualifiedNameFilter):
    name = 'bases'
    description = 'Super-traits'

class ImplFilter(_QualifiedNameFilter):
    name = 'impl'
    description = 'Implementations'

class ModuleFilter(_QualifiedNameFilter):
    name = 'module'
    description = 'Module defintions'

class ModuleUseFilter(_QualifiedNameFilter):
    name = 'module-use'
    description = 'Module imports'

class VarFilter(_QualifiedNameFilter):
    name = 'var'
    description = 'Variable definitions'

class VarRefFilter(_QualifiedNameFilter):
    name = 'var-ref'
    description = 'Variable references'

class TypeFilter(_QualifiedNameFilter):
    name = 'type'
    description = 'Type (struct, enum, type, trait) definition'

class TypeRefFilter(_QualifiedNameFilter):
    name = 'type-ref'
    description = 'Type references'

class ModuleRefFilter(_QualifiedNameFilter):
    name = 'module-ref'
    description = 'Module references'

class ModuleAliasRefFilter(_QualifiedNameFilter):
    name = 'module-alias-ref'
    description = 'Module alias references'

class ExternRefFilter(_QualifiedNameFilter):
    name = 'extern-ref'
    description = 'References to items in external crate'

