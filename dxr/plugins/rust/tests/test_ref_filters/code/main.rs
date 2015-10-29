#![crate_name="test"]

extern crate krate;
// The 'name' needle of internal crates like 'std' is an integer.
use std::io;

fn foo() {
    println!("Hello world");
}

fn main() {
    foo();
}
