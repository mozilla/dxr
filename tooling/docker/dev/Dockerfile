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
FROM ubuntu@sha256:0ca448cb174259ddb2ae6e213ebebe7590862d522fe38971e1175faedf0b6823

MAINTAINER Erik Rose <erik@mozilla.com>

COPY set_up_ubuntu.sh /tmp/
RUN /tmp/set_up_ubuntu.sh

COPY set_up_common.sh /tmp/
RUN /tmp/set_up_common.sh

# Give root a known password so devs can become root:
RUN echo "root:docker" | chpasswd

# Install Graphviz, needed only for building docs.
# Not running apt-get clean, to keep dev experience snappy.
RUN apt-get -q -y install graphviz

RUN useradd --create-home --home-dir /home/dxr --shell /bin/bash --groups sudo --uid 1000 dxr
RUN mkdir -p /home/dxr/dxr
VOLUME /home/dxr/dxr
USER dxr

# Activate a virtualenv. make will make it later.
ENV VIRTUAL_ENV=/home/dxr/dxr/venv PATH=/home/dxr/dxr/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

WORKDIR /home/dxr/dxr

EXPOSE 8000
