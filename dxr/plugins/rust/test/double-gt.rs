#[crate_id = "double-gt"];

use std::mem::size_of;
use std::raw::Vec;

fn main()
{
    let _ = size_of::<Vec<()>>();
    let _ = size_of::<Vec<()> >();
}
