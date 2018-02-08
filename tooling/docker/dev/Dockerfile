# A docker setup for DXR development
#
# This image has DXR and various compilers installed, so it can be used for
# indexing, serving web, and interactive debugging.
#
# This image should not be used as a base for production setups. Those would
# want separate images (and separate machines) for indexing. Also, we leave out
# some image size optimizations and introduce would-be security holes for the
# sake of a good dev experience.

# Ubuntu 14.04.3
FROM ubuntu:14.04
ENV DEBIAN_FRONTEND=noninteractive
LABEL MAINTAINER="Erik Rose <erik@mozilla.com>"



RUN apt-get -qq update \
    && apt-get -qqy install \
          npm \
          python-pip python-virtualenv python2.7-dev \
          mercurial git \
          llvm-3.8 libclang-3.8-dev clang-3.8 \
          curl apt-transport-https \
    && apt-get -yqq remove  nodejs \
    && curl -s https://deb.nodesource.com/gpgkey/nodesource.gpg.key | apt-key add - \
    && DISTRO=$(lsb_release -c -s) \
    && echo "deb https://deb.nodesource.com/node_6.x ${DISTRO} main" > /etc/apt/sources.list.d/nodesource.list \
    && echo "deb-src https://deb.nodesource.com/node_6.x ${DISTRO} main" >> /etc/apt/sources.list.d/nodesource.list \
    && apt-get -qq update \
    && apt-get -qqy install  nodejs \
    && update-alternatives --force --install /usr/local/bin/llvm-config llvm-config /usr/bin/llvm-config-3.8 0 \
    && update-alternatives --force --install /usr/local/bin/clang++ clang++ /usr/bin/clang++-3.8 0 \
    && update-alternatives --force --install /usr/local/bin/clang clang /usr/bin/clang-3.8 0 \
    && curl -s https://static.rust-lang.org/rustup.sh | sh -s -- --channel=nightly --date=2016-01-25 --yes \
    && echo "root:docker" | chpasswd \
    && apt-get -qqy install graphviz \
    && useradd --create-home --home-dir /home/dxr --shell /bin/bash --groups sudo --uid 1000 dxr \
    && echo "dxr:docker" | chpasswd

VOLUME /home/dxr/dxr
USER dxr

# Activate a virtualenv. make will make it later. Also, set SHELL so mach
# doesn't complain while building Firefox. Other things probably expect it as
# well.
ENV VIRTUAL_ENV=/venv PATH=/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin SHELL=/bin/bash

WORKDIR /home/dxr/dxr

EXPOSE 8000
