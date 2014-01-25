// sub-module in a sub-directory

use msalias = sub::sub2;
use sub::sub2;
use std::io::stdio::println;

static yy: uint = 25u;

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
            field2: u32,
        }
    }
}

pub struct SubStruct {
    name: ~str
}
