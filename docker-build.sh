#!/bin/bash

set -e
set -x

cd /home/vagrant/dxr
docker build . && docker run -i -t -p 8000:8000 -v /home/vagrant/dxr:/dxr $(docker images -q |head -n 1) /bin/bash /tmp/dxr-docker-build.sh
