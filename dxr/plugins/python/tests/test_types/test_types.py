from dxr.testing import DxrInstanceTestCase


class TypeDefTests(DxrInstanceTestCase):
    def test_simple_class_defs(self):
        self.found_line_eq('type:Foo', "class <b>Foo</b>(object):", 2)
        self.found_line_eq('type:Bar', "class <b>Bar</b>(Foo):", 7)
        self.found_line_eq('type:Baz', "class <b>Baz</b>(main.Bar):", 4)

    def test_undefined_class(self):
        self.found_nothing('type:object')

    def test_methods_are_not_classes(self):
        self.found_nothing('type:__init__')

    def test_two_classes(self):
        self.found_nothing('type:*Foo* type:*Bar*')
