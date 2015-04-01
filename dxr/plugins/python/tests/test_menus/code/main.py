from functions import foo
from functions import foo as foo2
from functions import foo as foo3


foo()  # Module-level call.


def bar():
    foo2()  # Call within function.


class Baz(object):
    def biff(self):
        foo3()  # Call within method.
