Downloading DXR
===============

Using git, clone the DXR repository::

   git clone --recursive https://github.com/mozilla/dxr.git

Remember the :option:`--recursive` option; DXR depends on the `TriLite SQLite
extension`_, which is included in the repository as a git submodule.


Booting And Building
====================


Vagrant Environment
-------------------

DXR runs only on Linux at the moment (and possibly other UNIX-like operating
systems). The easiest way to get things set up is to use the included,
preconfigured Vagrant_ VM. You'll need Vagrant and a virtualization provider
for it. We recommend VirtualBox.

Once you've installed VirtualBox and Vagrant, run these commands in DXR's
top-level directory::

   vagrant plugin install vagrant-vbguest
   vagrant up
   vagrant ssh

Then, run this inside the VM::

   cd ~/dxr
   make

.. note::

   The Vagrant image is built for VirtualBox 4.2.0 or newer.  If your version is older,
   the image might not work as expected.

   Your Vagrant version may require a specific vbguest plugin installation method.
   If you receive errors about the plugin visit the vbguest_ plugin page.

Docker environment
------------------

Stub Docker documentation once a build works

.. _TriLite SQLite extension: https://github.com/jonasfj/trilite

.. _Vagrant: http://www.vagrantup.com/

.. _vbguest: https://github.com/dotless-de/vagrant-vbguest
