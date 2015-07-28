from dxr.plugins.rust.tests import RustDxrInstanceTestCase
from nose import SkipTest

class FieldsTests(RustDxrInstanceTestCase):
    def test_qual_field(self):
        self.found_line_eq('+var:test::SomeFields::field1', "<b>field1</b>: i32,", 9)
        self.found_line_eq('+var:test::SomeFields::field2', "<b>field2</b>: NoFields,", 10)

    def test_qual_enum_field(self):
        self.found_line_eq('+var:test::EnumFields::Struct::field1', "Struct{ <b>field1</b>: i32,", 18)
        self.found_line_eq('+var:test::EnumFields::Struct::field2', "<b>field2</b>: NoFields },", 19)

    def test_field(self):
        # Note the apparent field refs here, these are actually new variables
        # being brought into scope.
        self.found_lines_eq('var:field1', [("<b>field1</b>: i32,", 9),
                                           ("Struct{ <b>field1</b>: i32,", 18),
                                           ("let SomeFields { <b>field1</b>, field2 } = b;", 30),
                                           ("let SFAlias { <b>field1</b>, field2 } = c;", 36),
                                           ("EnumFields::Struct{ <b>field1</b>, field2 } =&gt; {}", 42),
                                           ("EnumFields::Nested(SomeFields { <b>field1</b>, field2 }) =&gt; {}", 43)])
        self.found_lines_eq('var:field2', [("<b>field2</b>: NoFields,", 10),
                                           ("<b>field2</b>: NoFields },", 19),
                                           ("let SomeFields { field1, <b>field2</b> } = b;", 30),
                                           ("let SFAlias { field1, <b>field2</b> } = c;", 36),
                                           ("EnumFields::Struct{ field1, <b>field2</b> } =&gt; {}", 42),
                                           ("EnumFields::Nested(SomeFields { field1, <b>field2</b> }) =&gt; {}", 43)])

    def test_qual_field_ref(self):
        self.found_lines_eq('+var-ref:test::SomeFields::field1',
                            [("let b = SomeFields { <b>field1</b>: 42, field2: NoFields };", 26),
                             ("let _ = b.<b>field1</b>;", 27),
                             ("let SomeFields { <b>field1</b>: b1, field2: b2 } = b;", 29),
                             ("let SomeFields { <b>field1</b>, field2 } = b;", 30),
                             ("let c = SFAlias { <b>field1</b>: 42, field2: NoFields };", 32),
                             ("let _ = c.<b>field1</b>;", 33),
                             ("let SFAlias { <b>field1</b>: c1, field2: c2 } = c;", 35),
                             ("let SFAlias { <b>field1</b>, field2 } = c;", 36),
                             ("EnumFields::Nested(SomeFields { <b>field1</b>, field2 }) =&gt; {}", 43)])

        self.found_lines_eq('+var-ref:test::SomeFields::field2',
                            [("let b = SomeFields { field1: 42, <b>field2</b>: NoFields };", 26),
                             ("let _ = b.<b>field2</b>;", 28),
                             ("let SomeFields { field1: b1, <b>field2</b>: b2 } = b;", 29),
                             ("let SomeFields { field1, <b>field2</b> } = b;", 30),
                             ("let c = SFAlias { field1: 42, <b>field2</b>: NoFields };", 32),
                             ("let _ = c.<b>field2</b>;", 34),
                             ("let SFAlias { field1: c1, <b>field2</b>: c2 } = c;", 35),
                             ("let SFAlias { field1, <b>field2</b> } = c;", 36),
                             ("EnumFields::Nested(SomeFields { field1, <b>field2</b> }) =&gt; {}", 43)])

    def test_qual_enum_field_ref(self):
        self.found_line_eq('+var-ref:test::EnumFields::Struct::field1', "EnumFields::Struct{ <b>field1</b>, field2 } =&gt; {}", 42)
        self.found_line_eq('+var-ref:test::EnumFields::Struct::field2', "EnumFields::Struct{ field1, <b>field2</b> } =&gt; {}", 42)

    def test_field_ref(self):
        raise SkipTest('probably due to errors in rustc')
        self.found_lines_eq('var-ref:field1',
                            [("let b = SomeFields { <b>field1</b>: 42, field2: NoFields };", 26),
                             ("let _ = b.<b>field1</b>;", 27),
                             ("let SomeFields { <b>field1</b>: b1, field2: b2 } = b;", 29),
                             ("let SomeFields { <b>field1</b>, field2 } = b;", 30),
                             ("let c = SFAlias { <b>field1</b>: 42, field2: NoFields };", 32),
                             ("let _ = c.<b>field1</b>;", 33),
                             ("let SFAlias { <b>field1</b>: c1, field2: c2 } = c;", 35),
                             ("let SFAlias { <b>field1</b>, field2 } = c;", 36),
                             ("EnumFields::Struct{ <b>field1</b>, field2 } =&gt; {}", 42),
                             ("EnumFields::Nested(SomeFields { <b>field1</b>, field2 }) =&gt; {}", 43)])
        self.found_lines_eq('var-ref:field2',
                            [("let b = SomeFields { field1: 42, <b>field2</b>: NoFields };", 26),
                             ("let _ = b.<b>field2</b>;", 28),
                             ("let SomeFields { field1: b1, <b>field2</b>: b2 } = b;", 29),
                             ("let SomeFields { field1, <b>field2</b> } = b;", 30),
                             ("let c = SFAlias { field1: 42, <b>field2</b>: NoFields };", 32),
                             ("let _ = c.<b>field2</b>;", 34),
                             ("let SFAlias { field1: c1, <b>field2</b>: c2 } = c;", 35),
                             ("let SFAlias { field1, <b>field2</b> } = c;", 36),
                             ("EnumFields::Struct{ field1, <b>field2</b> } =&gt; {}", 42),
                             ("EnumFields::Nested(SomeFields { field1, <b>field2</b> }) =&gt; {}", 43)])

    # TODO case insensitive
    def test_qual_field_case_insensitive(self):
        self.found_line_eq('+var:@test::SomeFields::field1', "<b>field1</b>: i32,", 9)
        self.found_line_eq('+var:@test::SomeFields::field2', "<b>field2</b>: NoFields,", 10)

    def test_qual_enum_field_case_insensitive(self):
        self.found_line_eq('+var:@test::EnumFields::Struct::field1', "Struct{ <b>field1</b>: i32,", 18)
        self.found_line_eq('+var:@test::EnumFields::Struct::field2', "<b>field2</b>: NoFields },", 19)

    def test_field_case_insensitive(self):
        # Note the apparent field refs here, these are actually new variables
        # being brought into scope.
        self.found_lines_eq('var:field1', [("<b>field1</b>: i32,", 9),
                                           ("Struct{ <b>field1</b>: i32,", 18),
                                           ("let SomeFields { <b>field1</b>, field2 } = b;", 30),
                                           ("let SFAlias { <b>field1</b>, field2 } = c;", 36),
                                           ("EnumFields::Struct{ <b>field1</b>, field2 } =&gt; {}", 42),
                                           ("EnumFields::Nested(SomeFields { <b>field1</b>, field2 }) =&gt; {}", 43)])
        self.found_lines_eq('var:field2', [("<b>field2</b>: NoFields,", 10),
                                           ("<b>field2</b>: NoFields },", 19),
                                           ("let SomeFields { field1, <b>field2</b> } = b;", 30),
                                           ("let SFAlias { field1, <b>field2</b> } = c;", 36),
                                           ("EnumFields::Struct{ field1, <b>field2</b> } =&gt; {}", 42),
                                           ("EnumFields::Nested(SomeFields { field1, <b>field2</b> }) =&gt; {}", 43)])

    def test_qual_field_ref_case_insensitive(self):
        self.found_lines_eq('+var-ref:@test::SomeFields::field1',
                            [("let b = SomeFields { <b>field1</b>: 42, field2: NoFields };", 26),
                             ("let _ = b.<b>field1</b>;", 27),
                             ("let SomeFields { <b>field1</b>: b1, field2: b2 } = b;", 29),
                             ("let SomeFields { <b>field1</b>, field2 } = b;", 30),
                             ("let c = SFAlias { <b>field1</b>: 42, field2: NoFields };", 32),
                             ("let _ = c.<b>field1</b>;", 33),
                             ("let SFAlias { <b>field1</b>: c1, field2: c2 } = c;", 35),
                             ("let SFAlias { <b>field1</b>, field2 } = c;", 36),
                             ("EnumFields::Nested(SomeFields { <b>field1</b>, field2 }) =&gt; {}", 43)])

        self.found_lines_eq('+var-ref:@test::SomeFields::field2',
                            [("let b = SomeFields { field1: 42, <b>field2</b>: NoFields };", 26),
                             ("let _ = b.<b>field2</b>;", 28),
                             ("let SomeFields { field1: b1, <b>field2</b>: b2 } = b;", 29),
                             ("let SomeFields { field1, <b>field2</b> } = b;", 30),
                             ("let c = SFAlias { field1: 42, <b>field2</b>: NoFields };", 32),
                             ("let _ = c.<b>field2</b>;", 34),
                             ("let SFAlias { field1: c1, <b>field2</b>: c2 } = c;", 35),
                             ("let SFAlias { field1, <b>field2</b> } = c;", 36),
                             ("EnumFields::Nested(SomeFields { field1, <b>field2</b> }) =&gt; {}", 43)])

    def test_qual_enum_field_ref_case_insensitive(self):
        self.found_line_eq('+var-ref:@test::EnumFields::Struct::field1', "EnumFields::Struct{ <b>field1</b>, field2 } =&gt; {}", 42)
        self.found_line_eq('+var-ref:@test::EnumFields::Struct::field2', "EnumFields::Struct{ field1, <b>field2</b> } =&gt; {}", 42)

    def test_field_ref_case_insensitive(self):
        raise SkipTest('probably due to errors in rustc')
        self.found_lines_eq('var-ref:field1',
                            [("let b = SomeFields { <b>field1</b>: 42, field2: NoFields };", 26),
                             ("let _ = b.<b>field1</b>;", 27),
                             ("let SomeFields { <b>field1</b>: b1, field2: b2 } = b;", 29),
                             ("let SomeFields { <b>field1</b>, field2 } = b;", 30),
                             ("let c = SFAlias { <b>field1</b>: 42, field2: NoFields };", 32),
                             ("let _ = c.<b>field1</b>;", 33),
                             ("let SFAlias { <b>field1</b>: c1, field2: c2 } = c;", 35),
                             ("let SFAlias { <b>field1</b>, field2 } = c;", 36),
                             ("EnumFields::Struct{ <b>field1</b>, field2 } =&gt; {}", 42),
                             ("EnumFields::Nested(SomeFields { <b>field1</b>, field2 }) =&gt; {}", 43)])
        self.found_lines_eq('var-ref:field2',
                            [("let b = SomeFields { field1: 42, <b>field2</b>: NoFields };", 26),
                             ("let _ = b.<b>field2</b>;", 28),
                             ("let SomeFields { field1: b1, <b>field2</b>: b2 } = b;", 29),
                             ("let SomeFields { field1, <b>field2</b> } = b;", 30),
                             ("let c = SFAlias { field1: 42, <b>field2</b>: NoFields };", 32),
                             ("let _ = c.<b>field2</b>;", 34),
                             ("let SFAlias { field1: c1, <b>field2</b>: c2 } = c;", 35),
                             ("let SFAlias { field1, <b>field2</b> } = c;", 36),
                             ("EnumFields::Struct{ field1, <b>field2</b> } =&gt; {}", 42),
                             ("EnumFields::Nested(SomeFields { field1, <b>field2</b> }) =&gt; {}", 43)])
