#!/bin/sh
# Shell script to provision the vagrant box

set -e
set -x

# clean out redundant packages from vagrant base image
apt-get autoremove -y

apt-get purge -y juju*:*

# Docker
apt-get update
apt-get install -y docker.io
