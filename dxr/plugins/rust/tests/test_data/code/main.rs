// Test structs and fields.

#![crate_name="test"]

#[derive(Copy, Clone)]
struct NoFields;

struct SomeFields {
    field1: i32,
    field2: NoFields,
}

type SFAlias = SomeFields;

enum EnumFields {
    None,
    Some(i32, i64),
    Struct{ field1: i32,
            field2: NoFields },
    Nested(SomeFields),
}

fn main() {
    let _a = NoFields;

    let b = SomeFields { field1: 42, field2: NoFields };
    let _ = b.field1;
    let _ = b.field2;
    let SomeFields { field1: b1, field2: b2 } = b;
    let SomeFields { field1, field2 } = b;

    let c = SFAlias { field1: 42, field2: NoFields };
    let _ = c.field1;
    let _ = c.field2;
    let SFAlias { field1: c1, field2: c2 } = c;
    let SFAlias { field1, field2 } = c;

    let d = EnumFields::None;
    match d {
        EnumFields::None => {}
        EnumFields::Some(a, b) => {}
        EnumFields::Struct{ field1, field2 } => {}
        EnumFields::Nested(SomeFields { field1, field2 }) => {}
    }
}
