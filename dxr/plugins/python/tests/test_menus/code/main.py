from classes import BarClass
from functions import foo
from functions import foo as foo_func
from functions import foo as foo_method


foo()  # Module-level call.


def bar():
    foo_func()  # Call within function.


class Baz(object):
    def biff(self):
        foo_method()  # Call within method.


instance = BarClass()  # Class constructors should work too!
