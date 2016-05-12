#!/bin/sh -e
# OS-agnostic machine setup steps for DXR. This is reusable for prod, as we
# don't do anything specific to development or CI.

# Install Rust.
curl -s https://static.rust-lang.org/rustup.sh | sh -s -- --channel=nightly --date=2016-01-25 --yes
# Install newer node.
apt-get remove -y nodejs
curl -sL https://deb.nodesource.com/setup_6.x | bash -
apt-get install -y nodejs
