#![crate_name="test"]

fn foo() {
    println!("Hello world");
}

struct Baz;

impl Baz {
    fn baz(&self) {}

    fn bar() {}
}

trait Foo {
    fn qux(&self);
    fn norf(&self) {
        self.qux();
    }
}

impl Foo for Baz {
    fn qux(&self) {}
}

fn bar() {}

fn generic<T: Foo>(x: T) {
    x.qux();
    x.norf();
}

fn trait_object(x: &Foo) {
    x.qux();
    x.norf();    
}

fn main() {
    foo();

    let b = Baz;
    b.baz();

    b.qux();
    Foo::qux(&b);
    <Baz as Foo>::qux(&b);

    b.norf();
    Foo::norf(&b);
    <Baz as Foo>::norf(&b);
}
