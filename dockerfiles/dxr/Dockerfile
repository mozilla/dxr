FROM ubuntu
MAINTAINER Jamon Camisso <jamon@jamon.ca>

# Don't prompt for input
ENV DEBIAN_FRONTEND noninteractive

# Install packages all at once so as not to create a bunch of extra docker checkpoints
RUN apt-get -q update && apt-get -q -y install python-pip npm sphinx-common libsqlite3-dev sqlite3 git mercurial llvm-3.5 libclang-3.5-dev clang-3.5 pkg-config && apt-get clean

# Install old pip based packages using apt versions
RUN apt-get -q -y install python-virtualenv python-hglib python-nose && apt-get clean

RUN apt-get -q -y install python-dev && apt-get clean

# Install llvm-config alternative
RUN update-alternatives --force --install /usr/local/bin/llvm-config llvm-config /usr/bin/llvm-config-3.5 0
# There is no clang++ until we do this:
RUN update-alternatives --force --install /usr/local/bin/clang++ clang++ /usr/bin/clang++-3.5 0
# And we might as well make a clang link so we can compile mozilla-central:
RUN update-alternatives --force --install /usr/local/bin/clang clang /usr/bin/clang-3.5 0

# Make 'node' symlink
RUN ["/bin/ln", "-sf", "/usr/bin/nodejs", "/usr/local/bin/node"]

COPY setup_dxr.sh /usr/local/bin/setup_dxr

RUN useradd -u 1000 --create-home --home-dir /home/dxr dxr
USER dxr
WORKDIR /home/dxr

ENV VIRTUAL_ENV /home/dxr/venv
ENV PATH /home/dxr/venv/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin:/sbin:/bin

# Expose the dxr-serve port
EXPOSE 8000
