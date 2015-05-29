============================
Appendix A: Indexing Firefox
============================

As both a practical example and a specific reference, here is how to tweak the
included Vagrant box to build a DXR index of mozilla-central, the repository
from which Firefox is built.

Increase Your RAM
=================

Increase the RAM on your VM. 7GB seems to suffice.

1. Copy :file:`vagrantconfig_local.yaml-dist` to a new file, calling it
   :file:`vagrantconfig_local.yaml`.
2. Put ``memory: 7000`` in it.

Embiggen Your Drive
===================

Make sure your drive is big: at least 80GB. The temp files are 15GB, and the ES index and generated HTML are also on that order.


1. Convert disk from VMDK to the resizable VDI::

    cd ~/VirtualBox\ VMs/DXR_VM
    VBoxManage clonehd box-disk1.vmdk box-disk1.vdi --format VDI
    VBoxManage modifyhd box-disk1.vdi --resize 100000

2. Attach the new VDI to the VM using the VirtualBox GUI. (This seems to
   suffice. We don't have to continue with creating new partitions, merging
   them, and extending the FS as at
   http://blog.lenss.nl/2012/09/resize-a-vagrant-vmdk-drive/.)

3. Delete the old VMDK file if you want.

4. Fire up the VM to make sure it still works::

    vagrant up && vagrant ssh

Add More CPUs
=============

Use the VirtualBox GUI to crank up the number of processors on your VM to the
number on your physical host.

Configure The Source Tree
=========================

1. Put moz-central checkout in a folder somewhere. Let's call it :file:`src`.
   You can use ``hg clone`` as documented at
   https://developer.mozilla.org/en-US/docs/Simple_Firefox_build.

2. Have the compiler include the debug code so it can be analyzed, and enable
   standard C++ compatibility so we can build with clang. Put this in
   :file:`src/mozilla-central/.mozconfig`::

    ac_add_options --enable-debug
    ac_add_options --enable-stdcxx-compat

3. Get it ready to build::

    cd src/mozilla-central
    ./mach bootstrap``

4. Put this into a new :file:`dxr.config` file. It doesn't matter where it is,
   but it's a good idea to keep it outside the checkout. ::

    [DXR]
    enabled_plugins=clang pygmentize

    [mozilla-central]
    source_folder=/home/vagrant/src/mozilla-central
    object_folder=/home/vagrant/src/mozilla-central/obj-x86_64-unknown-linux-gnu
    build_command=cd $source_folder && ./mach clobber && make -f client.mk build MOZ_OBJDIR=$object_folder MOZ_MAKE_FLAGS="-s -j$jobs"

Bump Up Elasticsearch's RAM
===========================

1. In :file:`/etc/init.d/elasticsearch`, set ``ES_HEAP_SIZE=2g``.
2. ``/etc/init.d/elasticsearch restart``

Kick Off The Build
==================

In the folder where you put ``dxr.config``, run this::

    dxr index

This builds your source tree and indexes it into elasticsearch. You can then
run ``dxr serve -a`` to spin up the web interface against it.
