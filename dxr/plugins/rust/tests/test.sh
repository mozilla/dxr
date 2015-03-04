# TODO need to set these vars in the makefile or something

export RUSTC=/home/ncameron/rust3/x86_64-unknown-linux-gnu/stage1/bin/rustc
export LD_LIBRARY_PATH=/home/ncameron/rust3/x86_64-unknown-linux-gnu/stage1/lib
nosetests test_smoke/test_smoke.py
nosetests test_data/test_data_types.py
nosetests test_data/test_fields.py
nosetests test_fns/test_fns.py
nosetests test_traits/test_traits.py
nosetests test_traits/test_generics.py
nosetests test_vars/test_vars.py
nosetests test_mods/test_mods.py
nosetests test_mods/test_fns.py
