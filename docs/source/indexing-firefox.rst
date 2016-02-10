============================
Appendix A: Indexing Firefox
============================

As both a practical example and a specific reference, here is how to tweak the
included container to build a DXR index of mozilla-central, the repository
from which Firefox is built.

Increase Your RAM
=================

Stop your containers, and increase the RAM and disk on your docker-machine VM
(if using docker-machine). The compilation needs around 7GB. The temp files are
15GB, and the ES index and generated HTML are also on that order. It's also a
good idea to add more virtual CPUs, up to the limit of your physical ones. On
your host machine... ::

    make docker_stop
    docker-machine rm default
    docker-machine create --driver virtualbox --virtualbox-disk-size 80000 --virtualbox-cpu-count 4 --virtualbox-memory 8000 default

    # Reset your shell variables:
    eval "$(docker-machine env default)"

    # And drop back into the DXR container:
    make shell

Configure The Source Tree
=========================

1. Put a mozilla-central checkout in :file:`/code` on the VM. This is a
   special, blessed folder that will not evaporate when the docker container
   exits. (If you decide to put it somewhere else, be sure your choice is
   reflected in :file:`dxr.config` in Step 4.) You can use ``hg clone`` as
   documented at https://developer.mozilla.org/en-US/docs/Simple_Firefox_build.

.. note::

   If using docker-machine and VirtualBox, keep your source code out of
   :file:`/home/dxr/dxr`; VirtualBox's sharing of that folder between host and
   guest will kill your performance.

2. Have the compiler include the debug code so it can be analyzed. Put this in
   :file:`/code/mozilla-central/mozconfig`::

    ac_add_options --enable-debug
    ac_add_options --disable-optimize

3. Get it ready to build::

    cd /code/mozilla-central
    ./mach bootstrap
    ./mach mercurial-setup

4. Put this into a new :file:`dxr.config` file. It doesn't matter where it is,
   but it's a good idea to keep it outside the checkout. ::

    [DXR]
    enabled_plugins=clang pygmentize

    [mozilla-central]
    source_folder=/code/mozilla-central
    object_folder=/code/mozilla-central/obj-x86_64-unknown-linux-gnu
    build_command=cd $source_folder && ./mach clobber && make -f client.mk build MOZ_OBJDIR=$object_folder MOZ_MAKE_FLAGS="-s -j$jobs"

Bump Up Elasticsearch's RAM
===========================

1. In :file:`tooling/docker/docker-compose.yml`, add an ``environment`` stanza
   like this::

    es:
      build: ./es
      environment:
        ES_HEAP_SIZE: 2g
      ...

2. Run ``make docker_es``.

Kick Off The Build
==================

Within the Docker container (remember, ``make shell``), in the folder where you
put ``dxr.config``, run this::

    dxr index

This builds your source tree and indexes it into elasticsearch. You can then
run ``dxr serve -a`` to spin up the web interface against it.
