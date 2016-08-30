#!/bin/sh -e
# Do the Ubuntu-specific setup necessary to run DXR on any Ubuntu box for any
# purpose. This is reusable for prod, as we don't do anything specific to
# development or CI.

# Install OS-level dependencies:
apt-get -q update \
 && apt-get -q -y install \
        npm \
        python-pip python-virtualenv python2.7-dev \
        mercurial git \
        llvm-3.8 libclang-3.8-dev clang-3.8 \
        curl apt-transport-https

# Install newer node.
apt-get remove -y nodejs
curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add -
DISTRO=$(lsb_release -c -s)
echo "deb https://deb.nodesource.com/node_6.x ${DISTRO} main" > /etc/apt/sources.list.d/nodesource.list
echo "deb-src https://deb.nodesource.com/node_6.x ${DISTRO} main" >> /etc/apt/sources.list.d/nodesource.list
apt-get update
apt-get install -y nodejs

# Alias some things:
#
# --force overrides any older-version LLVM alternative lying around. This was
# useful with vagrant, probably less so with ephemeral containers.
update-alternatives --force --install /usr/local/bin/llvm-config llvm-config /usr/bin/llvm-config-3.8 0
# There is no clang++ until we do this:
update-alternatives --force --install /usr/local/bin/clang++ clang++ /usr/bin/clang++-3.8 0
# And we might as well make a clang link so we can compile mozilla-central:
update-alternatives --force --install /usr/local/bin/clang clang /usr/bin/clang-3.8 0
