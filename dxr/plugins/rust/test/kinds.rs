#[crate_id = "kinds"];

trait SuperTrait {}

fn kind_bounds(_: ~SuperTrait:Send, _: ~SuperTrait:'static) -> ~SuperTrait: {
    fail!();
}

fn main()
{
}
