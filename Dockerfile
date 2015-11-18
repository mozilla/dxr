# Ubuntu 14.04.3
FROM ubuntu@sha256:0ca448cb174259ddb2ae6e213ebebe7590862d522fe38971e1175faedf0b6823

MAINTAINER Erik Rose <erik@mozilla.com>

# Don't prompt for input:
ENV DEBIAN_FRONTEND noninteractive

# Install OS-level dependencies:
RUN apt-get -q update \
 && apt-get -q -y install \
        npm \
        python-pip python-virtualenv python2.7-dev \
        mercurial git \
        llvm-3.5 libclang-3.5-dev clang-3.5 \
        curl \
        graphviz \
 && apt-get clean \
 && rm -rf /var/lib/apt/lists/*
# TODO: graphviz is only for building docs. Install it only for dev.

# Alias some things:
#
# --force overrides any older-version LLVM alternative lying around. This was
# useful with vagrant, probably less so with ephemeral containers.
RUN update-alternatives --force --install /usr/local/bin/llvm-config llvm-config /usr/bin/llvm-config-3.5 0
# There is no clang++ until we do this:
RUN update-alternatives --force --install /usr/local/bin/clang++ clang++ /usr/bin/clang++-3.5 0
# And we might as well make a clang link so we can compile mozilla-central:
RUN update-alternatives --force --install /usr/local/bin/clang clang /usr/bin/clang-3.5 0
RUN ln -sf /usr/bin/nodejs /usr/local/bin/node

# Install Rust.
RUN curl -s https://static.rust-lang.org/rustup.sh | sh -s -- --channel=nightly --date=2015-06-14 --yes

# Do most of the rest as an unprivileged user:
RUN useradd --create-home --home-dir /home/dxr --shell /bin/bash dxr
USER dxr

# Make a virtualenv:
WORKDIR /home/dxr
ENV VIRTUAL_ENV=/home/dxr/venv
RUN virtualenv $VIRTUAL_ENV \
 && $VIRTUAL_ENV/bin/pip install pdbpp nose-progressive Sphinx==1.3.1
# TODO: Install pdbpp, nose, and Sphinx for dev only.


# Install and build DXR:
#
# TODO: Replace the COPY with a double mount (http://stackoverflow.com/a/27320731), or figure out some other easy way to build and exfiltrate the Sphinx docs from the container for viewing.
COPY . /home/dxr/dxr
USER root
RUN chown -R dxr /home/dxr/dxr
USER dxr
WORKDIR /home/dxr/dxr
RUN $VIRTUAL_ENV/bin/pip install --no-deps .
RUN make

EXPOSE 8000

# NEXT: See if this works. Then add a docker-compose thing, a make target to run tests, and more.