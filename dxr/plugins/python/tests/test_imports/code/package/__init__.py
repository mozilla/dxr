# Importing module 'package.submodule' into the scope of 'package' as variable
# 'submodule' shouldn't be problematic:
from package import submodule
class FirstDerivedFromSubmodule(submodule.MyClass):
    pass

# This allows us to refer to the same module by its full name:
import package.submodule
class SecondDerivedFromSubmodule(package.submodule.MyClass):
    pass

# This requires resolving `submodule` to `package.submodule` and doesn't work
# currently.
from submodule import MyClass as Klass
class ThirdDerivedFromSubmodule(Klass):
    pass

# This makes package.test_import_name_collision point to the function, not the module
# We should still be able to work with classes defined in `test_import_name_collision`,
# even though they can't be imported anymore as 'package.test_import_name_collision.MyClass'
from package.test_import_name_collision import test_import_name_collision, MyClass

# This is just to test that the import above worked.
class DerivedFromInaccessibleClass(MyClass):
    pass
test_import_name_collision()
