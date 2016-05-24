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
        llvm-3.5 libclang-3.5-dev clang-3.5 \
        curl

# Install newer node.
apt-get remove -y nodejs
curl -sL https://deb.nodesource.com/setup_6.x | bash -
apt-get install -y nodejs

# Alias some things:
#
# --force overrides any older-version LLVM alternative lying around. This was
# useful with vagrant, probably less so with ephemeral containers.
update-alternatives --force --install /usr/local/bin/llvm-config llvm-config /usr/bin/llvm-config-3.5 0
# There is no clang++ until we do this:
update-alternatives --force --install /usr/local/bin/clang++ clang++ /usr/bin/clang++-3.5 0
# And we might as well make a clang link so we can compile mozilla-central:
update-alternatives --force --install /usr/local/bin/clang clang /usr/bin/clang-3.5 0
