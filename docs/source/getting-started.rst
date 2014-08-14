===============
Getting Started
===============

.. note::

    These instructions are suited to trying out DXR to see if you like it. If
    you plan to contribute code to DXR itself, please see :doc:`development`
    instead.

The easiest way to get DXR working on your own machine is...

1. Get the source code you want to index.
2. Tell DXR how to build it.
3. Run :program:`dxr-index.py` to build and index your code.
4. Run :program:`dxr-serve.py` to present a web-based search interface.

But first, we have some installation to do.


.. include:: download-boot-and-build.rst


Configuration
=============

Before DXR can index your code, we need to tell it where it is and, if you want
to be able to do structural queries like find-all-the-callers, how to kick off
a build. (Currently, DXR supports structural queries only for C and C++.) If
you have a simple build process powered by :command:`make`, a configuration
like this might suffice. Place the following in a file called
:file:`dxr.config`. The location of the file doesn't matter; the usual
place is adjacent to your source directory.

.. include:: example-configuration.rst

.. note::

   Be sure to replace the placeholder paths in the above config.

By building your project with clang and under the control of
:program:`dxr-index.py`, DXR gets a chance to interpose a custom compiler
plugin that emits analysis data. It then processes that into an index.

If you have a non-C++ project and simply want to index it as text, the
``build_command`` can be set to :file:`/bin/true` or some other do-nothing
command.

Though you shouldn't need any of them yet, further config directives are
described in :doc:`configuration`.


Indexing
========

Now that you've told DXR about your codebase, it's time to build an
:term:`index` (sometimes also called an :term:`instance`)::

    dxr-build.py dxr.config

.. note::

    If you have a large codebase, the VM might run out of RAM. If that happens,
    make a copy of the
    :file:`vagrantconfig_local.yaml-dist` file in the top-level :file:`dxr`
    directory, rename it :file:`vagrantconfig_local.yaml`, and edit it to
    increase the VM's RAM::

        cp vagrantconfig_local.yaml-dist vagrantconfig_local.yaml
        vi vagrantconfig_local.yaml

    Then restart the VM. Within the VM... ::

        sudo shutdown -h now

    Then, from the host machine... ::

        vagrant up
        vagrant ssh

.. note::

    If you have trouble getting your own code to index, step back and see if
    you can get one of the included test cases to work::

        cd ~/dxr/tests/test_basic
        make

    If that works, it's just a matter of getting your configuration right. Pop
    into #static on irc.mozilla.org if you need a hand.


Serving Your Index
==================

Congratulations; your index is built! Now, spin up DXR's development server,
and see what you've wrought::

    dxr-serve.py --all /path/to/the/output

Surf to http://33.33.33.77:8000/ from the host machine, and poke around
your fancy new searchable codebase.

.. note::

    Seeing this error? ::

       Server Error
       Database error: no such module: trilite

    Run :command:`sudo ldconfig` inside the virtual machine to sort out the
    shared library linking problem. Then, re-run :program:`dxr-serve.py`, and
    all should work as expected.
