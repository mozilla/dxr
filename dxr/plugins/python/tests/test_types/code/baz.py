from . import main


class Baz(main.Bar):
    def __init__(self):
        print "Baz"

    def frobnicate(self):
        pass
