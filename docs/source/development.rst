===========
Development
===========

Here's the quickest way to start hacking on DXR.

.. include:: download-boot-and-build.rst

Making And Serving An Example Index
===================================

The folder-based test cases make decent scratch deployments when developing,
suitable for manually playing with your changes. ``test_basic`` is a good one
to start with. To get it running... ::

    cd ~/dxr/tests/test_basic
    make
    dxr-serve.py -a target

You can then surf to http://33.33.33.77:8000/ from the host machine and play around.

After Making Changes
====================

After you make changes to the code, you may have to rebuild various bits of the system:

``make`` (at the root level of the project)
    Rebuild the C-based compiler plugins, TriLite, and the JS templates.

``make templates``
    Just recompile the JS the template files used on the client side. Run this
    after changing any of the templates listed in :file:`Gruntfile.js`. You can
    also leave ``grunt watch`` running, and it will take care of this for you.

``make`` inside :file:`tests/test_basic`
    Re-render the HTML and regenerate the SQLite DB in :file:`test_basic`. Run 

architecture
tests
plugins




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


Icons
-----

DXR uses third-party icons from a variety of sources: :doc:`icons`.

If your plugin needs an icon not already present in the :file:`icons` folder,
please add it, and document its origin in this document. Feel free to use
existing icons, but keep in mind that they use semantic naming. So don't use
the ``search`` icon for zoom, because we may later change the search icon from
a magnifying glass to binoculars.


Troubleshooting
===============

Why is my copy of DXR acting errating, failing at searches, making requests for JS templates that shouldn't exist, and just generally not appearing to be in sync with my changes?
    Have you run ``python setup.py install`` for DXR at some point? Never, ever do that in development; use ``python setup.py develop`` instead. Otherwise, you will confuse yourself.  ever under any circumstances do ``python setup.py install`` when developing.

format version
