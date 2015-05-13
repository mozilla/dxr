#![crate_name="test"]

trait Foo {
    fn foo(&self) {}
}
trait Bar: Foo {}

impl Foo for i32 {}
impl Bar for i32 {}

fn foo<X: Foo>(x: &X) {}

struct Baz;

impl Foo for Baz {}

fn main() {
    let x = 42i32;
    let _y: &Foo = &x;
    let _y: &Bar = &x;
}
