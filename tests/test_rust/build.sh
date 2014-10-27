export RUSTC=/home/ncameron/rust3/x86_64-unknown-linux-gnu/stage1/bin/rustc
export LD_LIBRARY_PATH=/home/ncameron/rust3/x86_64-unknown-linux-gnu/stage1/lib:/home/ncameron/dxr/src2/tests/test_rust/code
#export RUST_LOG=info
../../bin/dxr-build.py dxr.config
