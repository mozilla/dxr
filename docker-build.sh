#!/bin/bash

set -e
set -x

cd dxr
docker build . && docker run -i -t -p 8000:8000 -v $PWD:/dxr $(docker images -q |head -n 1) /bin/bash /dxr/build.sh
