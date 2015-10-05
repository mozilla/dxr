FROM quay.io/fubar/ubuntu-indexer
MAINTAINER Peter

# Install Rust.
RUN curl -s https://static.rust-lang.org/rustup.sh | sh -s -- --channel=nightly --date=2015-06-14 --yes
# It's okay Mercurial, you can trust staff group.
RUN echo [trusted] >> /home/jenkins/.hgrc && echo groups = staff >> /home/jenkins/.hgrc
# Replace the distributed dxr with the one from here (working copy).
ADD . /builds/dxr-build-env/dxr
# Run make.
RUN . venv/bin/activate && \
    dxr/peep.py install -r dxr/requirements.txt && \
    cd dxr && \
    python setup.py install && \
    make && \
    cd - && \
    deactivate
RUN pip install nose-progressive

WORKDIR /builds/dxr-build-env/dxr
