import parent
import parent as blarent
from . import parent as carent
from parent import ParentClass
from parent import ParentClass as PClass


class FromImportChildClass(ParentClass):
    pass


class ImportChildClass(parent.ParentClass):
    pass


class FromImportAsChildClass(PClass):
    pass


class ImportAsChildClass(blarent.ParentClass):
    pass


class RelativeImportChildClass(carent.ParentClass):
    pass
