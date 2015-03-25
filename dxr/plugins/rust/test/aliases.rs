#[crate_id = "aliases"];

use my_sub2 = sub::sub2;
use my_st = sub::st;
use my_f = sub::f;
use my_g = sub::g;

mod sub {
    pub mod sub2 {
        pub static g: uint = 27;
    }
    pub struct st;
    pub fn f() {}
    pub static g: uint = 25;
}

fn main()
{
    let _ = my_sub2::g;
    let _ = my_st;
    let _ = my_f();
    let _ = my_g;
}
