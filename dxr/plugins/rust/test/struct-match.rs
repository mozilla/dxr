#[crate_id = "struct-match"];

use std::cell::RefCell;

pub struct blah {
    priv used_link_args: RefCell<~[~str]>,
}

fn main()
{
    let _ = blah {
        used_link_args: RefCell::new(~[]),
    };
}
