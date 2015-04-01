FROM ubuntu
MAINTAINER Jamon Camisso <jamon@jamon.ca>

# Don't prompt for input
ENV DEBIAN_FRONTEND noninteractive

# Update the base image
RUN apt-get update
RUN apt-get -y upgrade

# Install packages all at once so as not to create a bunch of extra docker checkpoints
RUN apt-get -q -y install python-pip npm sphinx-common libapache2-mod-wsgi apache2-dev apache2 libsqlite3-dev sqlite3 git mercurial llvm-3.3 libclang-3.3-dev clang-3.3 pkg-config

# Install old pip based packages using apt versions
RUN apt-get -q -y install python-virtualenv python-hglib python-nose

# Install pip packages using peep
ADD requirements.txt /tmp/requirements.txt
ADD peep.py /tmp/peep.py
RUN ["/usr/bin/python", "/tmp/peep.py", "install", "-r", "/tmp/requirements.txt"]
RUN ["/bin/rm", "/tmp/requirements.txt", "/tmp/peep.py"]

# Add docker build script
ADD dxr-docker-build.sh /usr/local/bin/dxr-docker-build.sh

# Install llvm-config alternative
RUN ["update-alternatives", "--install", "/usr/local/bin/llvm-config", "llvm-config", "/usr/bin/llvm-config-3.3", "0"]

# Make 'node' symlink
RUN ["/bin/ln", "-sf", "/usr/bin/nodejs", "/usr/local/bin/node"]

# Put dxr-build.py and dxr-serve.py symlinks in /usr/local/bin
RUN ["/bin/ln", "-sf", "/dxr/bin/dxr-serve.py", "/usr/local/bin/dxr-serve.py"]
RUN ["/bin/ln", "-sf", "/dxr/bin/dxr-build.py", "/usr/local/bin/dxr-build.py"]

# Set PYTHONPATH
ENV PYTHONPATH $PYTHONPATH:/dxr/dxr:/dxr

# Find libtrilite.so
ENV LD_LIBRARY_PATH $LD_LIBRARY_PATH:/dxr/trilite

# Expose the dxr-serve port
EXPOSE 8000