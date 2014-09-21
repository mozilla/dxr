#!/bin/bash

# use a bash script to allow running docker builds via vagrant on jenkins (temporarily)

cd /dxr

if [ ! -d /dxr/.git ]; then
    git clone --bare https://github.com/mozilla/dxr.git .git
    git checkout master
fi

make clean && make test
