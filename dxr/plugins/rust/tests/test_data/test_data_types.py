from dxr.plugins.rust.tests import RustDxrInstanceTestCase

class DataTypesTests(RustDxrInstanceTestCase):
    def test_struct_name(self):
        self.found_line_eq('type:NoFields', "struct <b>NoFields</b>;", 6)
        self.found_line_eq('type:SomeFields', "struct <b>SomeFields</b> {", 8)
        self.found_line_eq('type:SFAlias', "type <b>SFAlias</b> = SomeFields;", 13)
        self.found_line_eq('type:EnumFields', "enum <b>EnumFields</b> {", 15)

    def test_struct_qual_name(self):
        self.found_line_eq('+type:test::NoFields', "struct <b>NoFields</b>;", 6)
        self.found_line_eq('+type:test::SomeFields', "struct <b>SomeFields</b> {", 8)
        self.found_line_eq('+type:test::SFAlias', "type <b>SFAlias</b> = SomeFields;", 13)
        self.found_line_eq('+type:test::EnumFields', "enum <b>EnumFields</b> {", 15)

    def test_struct_ref(self):
        self.found_lines_eq('type-ref:NoFields',
                            [("field2: <b>NoFields</b>,", 10),
                             ("field2: <b>NoFields</b> },", 19),
                             ("let _a = <b>NoFields</b>;", 24),
                             ("let b = SomeFields { field1: 42, field2: <b>NoFields</b> };", 26),
                             ("let c = SFAlias { field1: 42, field2: <b>NoFields</b> };", 32)])
        self.found_lines_eq('type-ref:SomeFields',
                            [("type SFAlias = <b>SomeFields</b>;", 13),
                             ("Nested(<b>SomeFields</b>),", 20),
                             ("let b = <b>SomeFields</b> { field1: 42, field2: NoFields };", 26),
                             # TODO skipping struct refs in patterns
                             #("let <b>SomeFields</b> { field1: b1, field2: b2 } = b;", 29),
                             #("let <b>SomeFields</b> { field1, field2 } = b;", 30),
                             ("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
                             ("EnumFields::Nested(<b>SomeFields</b> { field1, field2 }) =&gt; {}", 43)])
        # TODO not handling aliases
        #self.found_lines_eq('type-ref:SFAlias',
        #                    [("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
        #                     ("let <b>SFAlias</b> { field1: c1, field2: c2 } = c;", 35),
        #                     ("let <b>SFAlias</b> { field1, field2 } = c;", 36)])
        # TODO not finding anything? Either in patterns or as a qualification
        # self.found_lines_eq('type-ref:EnumFields',
        #                     [("let d = <b>EnumFields</b>::None;", 38),
        #                      ("<b>EnumFields</b>::None => {}", 40),
        #                      ("<b>EnumFields</b>::Some(a, b) => {}", 41),
        #                      ("<b>EnumFields</b>::Struct{ field1, field2 } => {}", 42),
        #                      ("<b>EnumFields</b>::Nested(SomeFields { field1, field2 }) => {}", 43)])

    def test_struct_qual_ref(self):
        self.found_lines_eq('+type-ref:test::NoFields',
                            [("field2: <b>NoFields</b>,", 10),
                             ("field2: <b>NoFields</b> },", 19),
                             ("let _a = <b>NoFields</b>;", 24),
                             ("let b = SomeFields { field1: 42, field2: <b>NoFields</b> };", 26),
                             ("let c = SFAlias { field1: 42, field2: <b>NoFields</b> };", 32)])
        self.found_lines_eq('+type-ref:test::SomeFields',
                            [("type SFAlias = <b>SomeFields</b>;", 13),
                             ("Nested(<b>SomeFields</b>),", 20),
                             ("let b = <b>SomeFields</b> { field1: 42, field2: NoFields };", 26),
                             # TODO skipping struct refs in patterns
                             #("let <b>SomeFields</b> { field1: b1, field2: b2 } = b;", 29),
                             #("let <b>SomeFields</b> { field1, field2 } = b;", 30),
                             ("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
                             ("EnumFields::Nested(<b>SomeFields</b> { field1, field2 }) =&gt; {}", 43)])
        # TODO not handling aliases
        #self.found_lines_eq('+type-ref:test::SFAlias',
        #                    [("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
        #                     ("let <b>SFAlias</b> { field1: c1, field2: c2 } = c;", 35),
        #                     ("let <b>SFAlias</b> { field1, field2 } = c;", 36)])
        # TODO not finding anything? Either in patterns or as a qualification
        # self.found_lines_eq('+type-ref:test::EnumFields',
        #                     [("let d = <b>EnumFields</b>::None;", 38),
        #                      ("<b>EnumFields</b>::None => {}", 40),
        #                      ("<b>EnumFields</b>::Some(a, b) => {}", 41),
        #                      ("<b>EnumFields</b>::Struct{ field1, field2 } => {}", 42),
        #                      ("<b>EnumFields</b>::Nested(SomeFields { field1, field2 }) => {}", 43)])

    def test_struct_name_case_insensitive(self):
        self.found_line_eq('type:nofields', "struct <b>NoFields</b>;", 6)
        self.found_line_eq('type:somefields', "struct <b>SomeFields</b> {", 8)
        self.found_line_eq('type:sfalias', "type <b>SFAlias</b> = SomeFields;", 13)
        self.found_line_eq('type:enumfields', "enum <b>EnumFields</b> {", 15)

    # FIXME qualname/case insensitive
    def test_struct_qual_name_case_insensitive(self):
        pass
        #self.found_line_eq('+type:test::NOFIELDS', "struct <b>NoFields</b>;", 6)
        #self.found_line_eq('+type:TEST::somefieldS', "struct <b>SomeFields</b> {", 8)
        #self.found_line_eq('+type:test::sfalias', "type <b>SFAlias</b> = SomeFields;", 13)
        #self.found_line_eq('+type:tESt::enumFIELDS', "enum <b>EnumFields</b> {", 15)

    def test_struct_ref_case_insensitive(self):
        self.found_lines_eq('type-ref:nofields',
                            [("field2: <b>NoFields</b>,", 10),
                             ("field2: <b>NoFields</b> },", 19),
                             ("let _a = <b>NoFields</b>;", 24),
                             ("let b = SomeFields { field1: 42, field2: <b>NoFields</b> };", 26),
                             ("let c = SFAlias { field1: 42, field2: <b>NoFields</b> };", 32)])
        self.found_lines_eq('type-ref:somefields',
                            [("type SFAlias = <b>SomeFields</b>;", 13),
                             ("Nested(<b>SomeFields</b>),", 20),
                             ("let b = <b>SomeFields</b> { field1: 42, field2: NoFields };", 26),
                             # TODO skipping struct refs in patterns
                             #("let <b>SomeFields</b> { field1: b1, field2: b2 } = b;", 29),
                             #("let <b>SomeFields</b> { field1, field2 } = b;", 30),
                             ("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
                             ("EnumFields::Nested(<b>SomeFields</b> { field1, field2 }) =&gt; {}", 43)])
        # TODO not handling aliases
        #self.found_lines_eq('type-ref:SFAlias',
        #                    [("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
        #                     ("let <b>SFAlias</b> { field1: c1, field2: c2 } = c;", 35),
        #                     ("let <b>SFAlias</b> { field1, field2 } = c;", 36)])
        # TODO not finding anything? Either in patterns or as a qualification
        # self.found_lines_eq('type-ref:EnumFields',
        #                     [("let d = <b>EnumFields</b>::None;", 38),
        #                      ("<b>EnumFields</b>::None => {}", 40),
        #                      ("<b>EnumFields</b>::Some(a, b) => {}", 41),
        #                      ("<b>EnumFields</b>::Struct{ field1, field2 } => {}", 42),
        #                      ("<b>EnumFields</b>::Nested(SomeFields { field1, field2 }) => {}", 43)])

    # FIXME qualname/case insensitive
    def test_struct_qual_ref_case_insensitive(self):
        pass
        # self.found_lines_eq('+type-ref:TEST::NoFields',
        #                     [("field2: <b>NoFields</b>,", 10),
        #                      ("field2: <b>NoFields</b> },", 19),
        #                      ("let _a = <b>NoFields</b>;", 24),
        #                      ("let b = SomeFields { field1: 42, field2: <b>NoFields</b> };", 26),
        #                      ("let c = SFAlias { field1: 42, field2: <b>NoFields</b> };", 32)])
        # self.found_lines_eq('+type-ref:test::SOMEFIELDS',
        #                     [("type SFAlias = <b>SomeFields</b>;", 13),
        #                      ("Nested(<b>SomeFields</b>),", 20),
        #                      ("let b = <b>SomeFields</b> { field1: 42, field2: NoFields };", 26),
        #                      # TODO skipping struct refs in patterns
        #                      #("let <b>SomeFields</b> { field1: b1, field2: b2 } = b;", 29),
        #                      #("let <b>SomeFields</b> { field1, field2 } = b;", 30),
        #                      ("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
        #                      ("EnumFields::Nested(<b>SomeFields</b> { field1, field2 }) =&gt; {}", 43)])
        # TODO not handling aliases
        #self.found_lines_eq('+type-ref:test::SFAlias',
        #                    [("let c = <b>SFAlias</b> { field1: 42, field2: NoFields };", 32),
        #                     ("let <b>SFAlias</b> { field1: c1, field2: c2 } = c;", 35),
        #                     ("let <b>SFAlias</b> { field1, field2 } = c;", 36)])
        # TODO not finding anything? Either in patterns or as a qualification
        # self.found_lines_eq('+type-ref:Test::EnumFields',
        #                     [("let d = <b>EnumFields</b>::None;", 38),
        #                      ("<b>EnumFields</b>::None => {}", 40),
        #                      ("<b>EnumFields</b>::Some(a, b) => {}", 41),
        #                      ("<b>EnumFields</b>::Struct{ field1, field2 } => {}", 42),
        #                      ("<b>EnumFields</b>::Nested(SomeFields { field1, field2 }) => {}", 43)])

