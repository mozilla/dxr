// sub-module in a sub-directory

use sub::sub2 as msalias;
use sub::sub2;
use std::io::Write;

static yy: usize = 25;

mod sub {
    pub mod sub2 {
        use std::io::Write;
        pub mod sub3 {
            use std::io::Write;
            pub fn hello() {
                ::std::io::stdout().write_all(b"hello from module 3");
            }          
        }
        pub fn hello() {
            ::std::io::stdout().write_all(b"hello from a module");
        }

        pub struct nested_struct {
            pub field2: u32,
        }
    }
}

pub struct SubStruct {
    pub name: String
}
