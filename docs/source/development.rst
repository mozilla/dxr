DXR Development
===============

*This document details how to get started with DXR development.*

Using Vagrant and Puppet you can quickly get started with DXR
development in a VM. The config files and puppet manifests in ./puppet/
may also be a useful reference for setting up DXR on your own server.

To begin, you will need Vagrant and Virtual box. More about that (on
Vagrant's website)[https://www.virtualbox.org/wiki/Downloads]. Once both
of those are installed you're ready to begin. Make sure you have the
necessary submodules by running ``git submodule update --init`` and
execute the following:

::

    # from the dxr root
    vagrant up # requires password for setting up shared folders
    vagrant ssh

    # now you're inside the VM

    cd dxr/
    make
    cd tests/test_basic/
    make

    # run the server
    ../../bin/dxr-serve.py --all target
    # Server should be running on 33.33.33.77:8000.

    # all done? ctrl+c to interrupt the server
    exit

    # back on the host; shut it down
    vagrant halt

The repository on your host machine is mirrored over to the VM via
Shared Folders. Changes you make outside the VM will be instantly
available inside the VM and vice-versa, so you can edit locally with
whatever you are used to using and run the code inside inside the VM.

Customization
-------------

You may find it convenient to edit your local ``/etc/hosts`` file and
add a line to alias the VMs IP to something more memorable, like
``33.33.33.77  dxr``.

If you need to modify the Vagrant configuration, tear off the local
vagrant config file in the project root:
``cp vagrantconfig_local.yaml-dest vagrantconfig_local.yaml`` and edit
as necessary. The .gitignore file will safely keep your changes out of
version control. This is particularly useful for boosting the amount of
RAM allocated to the virtual machine or debugging puppet changes.
