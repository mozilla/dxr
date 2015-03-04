=============================================
Appendix A: Indexing mozilla-central With DXR
=============================================

As both a practical example and a specific reference, here is how to tweak the
included Vagrant box to build a DXR index of Firefox.

Increase Your RAM
=================

Increase the RAM on your VM. 6GB seems to suffice.

1. Copy :file:`vagrantconfig_local.yaml-dist` to a new file, calling it
   :file:`vagrantconfig_local.yaml`.
2. Put ``memory: 6000`` in it.

Embiggen Your Drive
===================

Make sure your drive is big: at least 80GB. The temp files are 15GB, and the ES index and generated HTML are also on that order.


1. Convert disk from VMDK to the resizable VDI::

    cd ~/VirtualBox VMs/DXR_VM
    VBoxManage clonehd box-disk1.vmdk box-disk1.vdi --format VDI
    VBoxManage modifyhd box-disk1.vdi --resize 100000

2. Attach it to the VM using the VirtualBox GUI. (This seems to suffice. We
   don't have to continue with creating new partitions, merging them, and
   extending the FS as at
   http://blog.lenss.nl/2012/09/resize-a-vagrant-vmdk-drive/.)

Configure The Source Tree
=========================

1. Put moz-central checkout in :file:`src`.
2. Have the compiler include the debug code so it can be analyzed, and enable
   standard C++ compatibility so we can build with clang. Put this in
   :file:`src/mozilla-central/.mozconfig`::

    ac_add_options --enable-debug
    ac_add_options --enable-stdcxx-compat

3. Get it ready to build::

    cd src/mozilla-central
    ./mach bootstrap``

4. Put this into a new :file:`dxr.config` file::

    [DXR]
    target_folder=target
    enabled_plugins=clang pygmentize

    [mozilla-central]
    source_folder=/home/vagrant/src/mozilla-central
    object_folder=/home/vagrant/src/mozilla-central/obj-x86_64-unknown-linux-gnu
    build_command=cd $source_folder && make -f client.mk build MOZ_OBJDIR=$object_folder MOZ_MAKE_FLAGS="-s -j$jobs"

5. Work around a build bug. This will probably not be necessary for very long.

   1. ``apt-get install libvpx-dev``
   2. Add ``ac_add_options --with-system-libvpx`` to your :file:`.mozconfig`.
   3. Maybe apply the ``AC_DEFINE(MOZ_NATIVE_LIBVPX)`` part from the patch
      linked from https://bugzilla.mozilla.org/show_bug.cgi?id=982693#c6. It
      may not be necessary.

Bump Up Elasticsearch's RAM
===========================

1. In :file:`/etc/init.d/elasticsearch`, set ``ES_HEAP_SIZE=2g``.
2. ``/etc/init.d/elasticsearch restart``

Kick Off The Build
==================

::

    dxr-build.py

This should result in a :file:`target` folder. You can run ``dxr-serve.py -a
target`` to spin up the web interface against it.

.. note::
    Between builds, do a ``mach clobber`` to make sure you build everything
    over again (and thus don't miss laying down CSVs).
