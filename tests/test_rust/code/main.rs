#![ crate_id = "test" ]
#![feature(struct_variant)]
#![feature(macro_rules)]

extern crate num;
// A simple rust project

//extern crate krate2;
extern crate myflate = "flate";

use num::bigint::BigInt;
use std::collections::hashmap::{HashMap,HashSet};
use std::cell::RefCell;

use msalias = sub::sub2;
use sub::sub2;
use sub_struct = sub::sub2::nested_struct;
use std::io::stdio::println;
use std::num::cast;
use std::num::{from_int,from_i8};

use std::mem::size_of;

static uni: &'static str = "Les Miséééééééérables";
static yy: uint = 25u;

static bob: Option<num::bigint::BigInt> = None;

// buglink test - see issue #1337.

fn test_aslias() {
    let s = sub_struct{ field2: 45u32, };
}

mod sub {
    pub mod sub2 {
        use std::io::stdio::println;
        pub mod sub3 {
            use std::io::stdio::println;
            pub fn hello() {
                println("hello from module 3");
            }          
        }
        pub fn hello() {
            println("hello from a module");
        }

        pub struct nested_struct {
            pub field2: u32,
        }

        pub enum nested_enum {
            Nest2 = 2,
            Nest3 = 3
        }
    }
}

pub mod SameDir;
pub mod SubDir;

#[path = "SameDir3.rs"]
pub mod SameDir2;

struct nofields;

#[deriving(Clone)]
struct some_fields {
    field1: u32,
}

trait SuperTrait {
}

trait SomeTrait : SuperTrait {
    fn Method(&self, x: u32) -> u32;

    fn prov(&self, x: u32) -> u32 {
        println(x.to_str().as_slice());
        42
    }  
    fn stat2(x: &Self) -> u32 {
        32
    }  
}

trait SubTrait: SomeTrait {
    fn provided_method(&self) -> u32 {
        42
    }
}

impl SomeTrait for some_fields {
    fn Method(&self, x: u32) -> u32 {
        println(x.to_str().as_slice());
        self.field1
    }  
}

impl SuperTrait for some_fields {
}

impl some_fields {
    fn stat(x: u32) -> u32 {
        println(x.to_str().as_slice());
        42
    }  
    fn stat2(x: &some_fields) -> u32 {
        42
    }  

    fn align_to<T>(&mut self) {
        
    }

    fn test(&mut self) {
        self.align_to::<bool>();
    }
}

impl SuperTrait for nofields {
}
impl SomeTrait for nofields {
    fn Method(&self, x: u32) -> u32 {
        self.Method(x);
        43
    }    
}

impl SubTrait for nofields {
    fn provided_method(&self) -> u32 {
        21
    }
}

impl SuperTrait for (Box<nofields>, Box<some_fields>) {}

type MyType = Box<some_fields>;

fn f_with_params<T: SomeTrait>(x: &T) {
    x.Method(41);
}

enum SomeEnum<'a> {
    Ints(int, int),
    Floats(f64, f64),
    Strings(&'a str, &'a str, &'a str),
    MyTypes(MyType, MyType)
}

enum SomeOtherEnum {
    SomeConst1,
    SomeConst2,
    SomeConst3
}

enum SomeStructEnum {
    EnumStruct{a:int, b:int},
    EnumStruct2{f1:MyType, f2:MyType},
    EnumStruct3{f1:MyType, f2:MyType, f3:SomeEnum<'static>}
}

fn matchSomeEnum(val: SomeEnum) {
    match val {
        Ints(int1, int2) => { println((int1+int2).to_str().as_slice()); }
        Floats(float1, float2) => { println((float2*float1).to_str().as_slice()); }
        Strings(_, _, s3) => { println(s3); }
        MyTypes(mt1, mt2) => { println((mt1.field1 - mt2.field1).to_str().as_slice()); }
    }
}

fn matchSomeStructEnum(se: SomeStructEnum) {
    match se {
        EnumStruct{a:a, ..} => println(a.to_str().as_slice()),
        EnumStruct2{f1:f1, f2:f_2} => println(f_2.field1.to_str().as_slice()),
        EnumStruct3{f1, ..} => println(f1.field1.to_str().as_slice()),
    }
}
fn matchSomeStructEnum2(se: SomeStructEnum) {
    match se {
        EnumStruct{a: ref aaa, ..} => println(aaa.to_str().as_slice()),
        EnumStruct2{f1, f2: f2} => println(f1.field1.to_str().as_slice()),
        EnumStruct3{f1, f3: Ints(_, _), f2} => println(f1.field1.to_str().as_slice()),
        _ => {},
    }
}

fn matchSomeOtherEnum(val: SomeOtherEnum) {
    match val {
        SomeConst1 => { println("I'm const1."); }
        SomeConst2 | SomeConst3 => { println("I'm const2 or const3."); }
    }
}

fn hello<X: SomeTrait>((z, a) : (u32, String), ex: X) {
    SameDir2::hello(43);

    println(yy.to_str().as_slice());
    let (x, y): (u32, u32) = (5, 3);
    println(x.to_str().as_slice());
    println(z.to_str().as_slice());
    let x: u32 = x;
    println(x.to_str().as_slice());
    let x = "hello";
    println(x);

    let x = 32.0f32;
    let _ = (x + ((x * x) + 1.0).sqrt()).ln();

    let s: Box<SomeTrait> = box some_fields {field1: 43};
    let s2: Box<some_fields> =  box some_fields {field1: 43};
    let s3 = box nofields;

    s.Method(43);
    s3.Method(43);
    s2.Method(43);

    ex.prov(43);

    let y: u32 = 56;
    // static method on struct
    let r = some_fields::stat(y);
    // trait static method, calls override
    // TODO what is the syntax for this?
    let r = SomeTrait::stat2(s2);
    // trait static method, calls default
    let r = SomeTrait::stat2(s3);

    let s4 = s3 as Box<SubTrait>;
    s4.Method(43);

    s4.provided_method();
    s2.prov(45);

    let closure = |x: u32, s: &SomeTrait| {
        s.Method(23);
        return x + y;
    };

    let z = closure(10, s);
}

// test kind bounds on trait objects
fn kind_bounds(_: Box<SuperTrait>+Send, _: Box<SuperTrait>+'static) -> Box<SuperTrait> {
    fail!();
}

pub struct blah {
    used_link_args: RefCell<[&'static str, ..0]>,
}

fn main() {
    let s = box some_fields {field1: 43};
    hello((43, "a".to_owned()), *s);
    sub::sub2::hello();
    sub2::sub3::hello();

    let h = sub2::sub3::hello;
    h();

    // utf8 chars
    let ut = "Les Miséééééééérables";

    // For some reason, this pattern of macro_rules foiled our generated code
    // avoiding strategy.
    macro_rules! variable_str(($name:expr) => (
        some_fields {
            field1: $name,
        }
    ));
    let vs = variable_str!(32);

    let mut candidates: RefCell<HashMap<&'static str, &'static str>> = RefCell::new(HashMap::new());
    let _ = blah {
        used_link_args: RefCell::new([]),
    };
    let s1 = nofields;
    let s2 = some_fields{ field1: 55};
    let s3: some_fields = some_fields{ field1: 55};
    let s4: msalias::nested_struct = sub::sub2::nested_struct{ field2: 55};
    let s4: msalias::nested_struct = sub2::nested_struct{ field2: 55};
    println(s2.field1.to_str().as_slice());
    let s5: MyType = box some_fields{ field1: 55};
    let s = SameDir::SameStruct{name: "Bob".to_owned()};
    let s = SubDir::SubStruct{name:"Bob".to_owned()};
    let s6: SomeEnum = MyTypes(box s2, s5);
    let s7: SomeEnum = Strings("one", "two", "three");
    matchSomeEnum(s6);
    matchSomeEnum(s7);
    let s8: SomeOtherEnum = SomeConst2;
    matchSomeOtherEnum(s8);
    let s9: SomeStructEnum = EnumStruct2{f1: box some_fields{field1:10}, f2: box s2};
    matchSomeStructEnum(s9);
}

impl Iterator<(uint, uint)> for nofields {
    fn next(&mut self) -> Option<(uint, uint)> {
        fail!()
    }

    fn size_hint(&self) -> (uint, Option<uint>) {
        fail!()
    }
}
