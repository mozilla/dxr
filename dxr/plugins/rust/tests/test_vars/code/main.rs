#![crate_name="test"]

fn foo(x: u8) -> u8 {
    if false {
        return x;
    }

    {
        let x = 2u8;
    }

    let x = 5 + x;
    x
}

fn test_match(y: u32) {
    match y {
        z => {
            foo(z as u8);
        }
    }

    match y {
        w @ _ => {
            let _ = w;
        }
    }
}

fn main() {
    let a = 32i32;
    let _ = a + 10;
}
