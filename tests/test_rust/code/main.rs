#[ crate_id = "test" ];

// A simple rust project

//extern mod crate2;
extern mod myextra = "extra";
//TODO doesn't work right now in rust
//extern mod core = "github.com/thestinger/rust-core/tree/master/core";

use msalias = sub::sub2;
use sub::sub2;
use myextra::arc;

static yy: uint = 25u;

static bob: Option<myextra::bigint::BigInt> = None;


mod sub {
    pub mod sub2 {
        pub mod sub3 {
          pub fn hello() {
              println("hello from module 3");
          }          
        }
        pub fn hello() {
            println("hello from a module");
        }

        pub struct nested_struct {
            field2: u32,
        }
    }

}

pub mod SameDir;
pub mod SubDir;

#[path = "SameDir3.rs"]
pub mod SameDir2;

struct nofields;
struct some_fields {
    field1: u32,
}

trait SuperTrait {

}

trait SomeTrait : SuperTrait {
    fn Method(&self, x: u32) -> u32;
}

trait SubTrait: SomeTrait {

}

impl SomeTrait for some_fields {
    fn Method(&self, x: u32) -> u32 {
        self.field1
    }  
}

impl SuperTrait for some_fields {

}

impl some_fields {

}

type MyType = ~some_fields;

fn hello((z, a) : (u32, ~str)) {
    SameDir2::hello(43);

    println(yy.to_str());
    let (x, y): (u32, u32) = (5, 3);
    println(x.to_str());
    println(z.to_str());
    let x: u32 = x;
    println(x.to_str());
    let x = ~"hello";
    println(x);

    let s: ~SomeTrait = ~some_fields {field1: 43};
}

fn main() {
    hello((43, ~"a"));
    sub::sub2::hello();
    sub2::sub3::hello();

    let h = sub2::sub3::hello;
    h();

    let s1 = nofields;
    let s2 = some_fields{ field1: 55};
    let s3: some_fields = some_fields{ field1: 55};
    let s4: msalias::nested_struct = sub::sub2::nested_struct{ field2: 55};
    let s4: msalias::nested_struct = sub2::nested_struct{ field2: 55};
    println(s2.field1.to_str());
    let s5: MyType = ~some_fields{ field1: 55};

    let s = SameDir::SameStruct{name:~"Bob"};
    let s = SubDir::SubStruct{name:~"Bob"};
}
