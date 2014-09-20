#!/bin/bash

# use a bash script to allow running docker builds via vagrant on jenkins (temporarily)
cd /dxr
make clean && make test
