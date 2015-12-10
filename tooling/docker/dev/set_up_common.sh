#!/bin/sh -e
# OS-agnostic machine setup steps for DXR. This is reusable for prod, as we
# don't do anything specific to development or CI.

# Install Rust.
curl -s https://static.rust-lang.org/rustup.sh | sh -s -- --channel=nightly --yes
