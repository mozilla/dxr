#![crate_name="test"]

mod mod1 {
    pub mod mod11 {
        pub mod mod111 {
            pub fn bar() {}
        }
    }

    pub mod mod12 {
        pub fn bar() {}

        pub mod mod3 {}
    }
}

mod mod2 {
    pub use mod1::mod12::bar;
    pub fn foo() {}

    pub mod mod3 {}
}

fn main() {
    ::mod1::mod11::mod111::bar();
    mod2::foo();
    mod2::bar();

    {
        use mod1::mod11::mod111;
        use mod1::mod11::mod111 as moda;

        mod111::bar();
        moda::bar();
    }

    {
        use mod1::mod12::*;

        bar();
    }

    {
        use mod1::{mod11, mod12};

        mod11::mod111::bar();
        mod12::bar();
    }

    {
        use mod1::mod12::bar;

        bar();
    }

    {
        use mod1::mod12::bar as baz;

        baz();
    }

    {
        use mod1::mod12::{self, bar};

        bar();
        mod12::bar();
    }
}
