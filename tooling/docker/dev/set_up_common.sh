#!/bin/sh -e
# OS-agnostic machine setup steps for DXR. This is reusable for prod, as we
# don't do anything specific to development or CI.

# Install Rust.
curl -sSf https://sh.rustup.rs | sh -s -- --default-toolchain nightly-2016-01-25 -y
