import package.submodule
print package.DerivedFromInaccessibleClass

from package import submodule
print submodule

from package import test_import_name_collision
print test_import_name_collision

from package import Klass
print Klass
