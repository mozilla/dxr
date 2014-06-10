Downloading DXR
===============

Using git, clone the DXR repository::

   git clone --recursive https://github.com/mozilla/dxr.git

Remember the :option:`--recursive` option; DXR depends on the `TriLite SQLite
extension`_, which is included in the repository as a git submodule.


Booting And Building
====================

DXR runs only on Linux at the moment (and possibly other UNIX-like operating
systems). The easiest way to get things set up is to use the included,
preconfigured Vagrant_ VM. You'll need Vagrant and a virtualization provider
for it. We recommend VirtualBox.

Once you've installed VirtualBox and Vagrant, run these commands in DXR's
top-level directory::

   vagrant up
   vagrant ssh

Then, run this inside the VM::

   cd ~/dxr
   make

.. note::

   The Vagrant image is built for VirtualBox 4.2.0.  If your version is older,
   the image might not work as expected.


.. _TriLite SQLite extension: https://github.com/jonasfj/trilite

.. _Vagrant: http://www.vagrantup.com/
