===============
Getting Started
===============

.. note::

    These instructions are for trying out DXR to see if you like it. If you
    plan to contribute code to DXR itself, please see :doc:`development`
    instead.

The easiest way to get DXR working on your own machine is...

1. Get the source code you want to index.
2. If it a language analyzed at build time (like C++ or Rust), tell DXR how to
   build it.
3. Run :program:`dxr index` to index your code.
4. Run :program:`dxr serve` to present a web-based search interface.

But first, we have some installation to do.


.. include:: download-boot-and-build.rst


Configuration
=============

Before DXR can index your code, it needs to know where it is and, if you want
to be able to do structural queries (like find-all-the-callers) for C, C++, or
Rust, how to kick off a build. (Analysis of more dynamic languages like Python
does not require a build step.) If you have a simple build process powered by
:command:`make`, a configuration like this might suffice. Place the following
in a file called :file:`dxr.config`. The location of the file doesn't matter,
but the usual place is adjacent to your source directory.

.. include:: example-configuration.rst

.. note::

   Be sure to replace the placeholder paths in the above config.  You'll need to
   move your code to be indexed into the VM, either by downloading it from
   within the VM, or by moving it into your DXR repository folder, where
   it will be visible from within the VM in the shared ``~/dxr`` folder. It's
   possible to index your code from a folder within ``~/dxr``, but, if you are
   using a non-Linux host machine, moving it to :file:`/code` will give you
   much faster IO by taking VirtualBox's shared-folder machinery out of the mix.

By building your project with clang and under the control of
:program:`dxr index`, DXR gets a chance to interpose a custom compiler
plugin that emits analysis data. It then processes that into an index.

If you have a non-C++ project and simply want to index it as text, the
``build_command`` can be set to blank::

    build_command =

Though you shouldn't need any of them yet, further config directives are
described in :doc:`configuration`.


Indexing
========

Now that you've told DXR about your codebase, it's time to build an
:term:`index`::

    dxr index --config dxr.config

.. note::

    If you have a large codebase, the VM might run out of RAM. If that happens,
    wipe out the VM using ``docker-machine rm default``, and then go back to
    the ``docker-machine create`` instruction and crank up the numbers. For
    example, this is plenty of space to build Firefox::

        docker-machine create --driver virtualbox --virtualbox-disk-size 50000 --virtualbox-cpu-count 4 --virtualbox-memory 8000 default

        # Reset your shell variables:
        eval "$(docker-machine env default)"

        # And drop back into the DXR container:
        make shell

.. note::

    If you have trouble getting your own code to index, step back and see if
    you can get one of the included test cases to work::

        cd ~/dxr/tests/test_basic
        dxr index

    If that works, it's just a matter of getting your configuration right. Pop
    into #static on irc.mozilla.org if you need a hand.


Serving Your Index
==================

Congratulations; your index is built! Now, spin up DXR's development server,
and see what you've wrought::

    dxr serve --all

If you're using ``docker-machine``, run ``docker-machine ip default`` to find
the address of your VM. Then surf to http://*that IP address*:8000/ from the
host machine, and poke around your fancy new searchable codebase.

If you're not using ``docker-machine``, your code should be accessible from
http://localhost:8000/.
