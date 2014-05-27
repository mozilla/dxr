Deployment of DXR
=================

*This document describes how to build DXR and publish a source code
index on the web.*

DXR is designed to generate a :term:`source code index` for one or
more source trees offline, preferably on a dedicated build server.
The generated index is then uploaded to a web server for hosting.

Generating and publishing an index roughly involves the following
steps:

1. Build DXR and associated plugins
2. Configure it
3. Generate a source code index
4. Publish the index on a web server


Build DXR and Associated Plugins
--------------------------------

Building DXR means installing some build dependencies including a C++
compiler and running :command:`make` in DXR's top-level directory.
Alternatively you can use Vagrant_ run DXR inside a preconfigured
virtual machine.

Either way, first clone the DXR repository with the :option:`git clone
--recursive` option.  DXR depends on the `TriLite SQLite extension`_
which is included in the repository as a Git submodule.  The
:option:`git clone --recursive` option is needed to download the
submodule along with DXR.

::

   $ git clone --recursive https://github.com/mozilla/dxr.git


Without Vagrant
^^^^^^^^^^^^^^^

Here are examples of some packages you might need to install to
satisfy DXR's build dependencies, depending on your system:

*  make
*  build-essential
*  libclang-dev
*  llvm-dev
*  pkg-config
*  mercurial
*  libsqlite3-dev
*  npm

.. note::

   On some systems (for example Debian and Ubuntu) the Node.js interpreter is
   named nodejs but DXR depends on it and expects it to be named node.
   One simple solution is to add a symlink on your system::

      $ sudo ln -s /usr/bin/nodejs /usr/bin/node

Build DXR using the Makefile in DXR's top-level directory.  Simply
type :command:`make` and you should be good to go.

It will build the libtrilite.so library in the trilite directory and
the libclang-index-plugin.so library in the dxr/plugins/clang
directory.  You might need to edit the Makefile in the
dxr/plugins/clang directory to specify the correct locations of
:program:`llvm-config`, :program:`clang`, and :program:`clang++`.

.. note::

   The TriLite SQLite extension is under active development and far
   from stable.  If you have any problems with it, try a different
   revision and file a bug report.  DXR depends on it for accelerated
   substring and regular expression matching.

Notice that the Makefile in DXR's top-level directory also features a
:command:`make check` target for running automated tests.  See the
:doc:`tests` document for details.

You can optionally install DXR onto your system using the setup.py
script.  Virtualenv_ can be used to install DXR into a self-contained
directory instead of installing it system-wide.

::

   $ python setup.py install


Virtualenv
^^^^^^^^^^

If you're going to install DXR, using Virtualenv_ is the recommended
way.  Using Virtualenv doesn't require root privileges.

::

   $ virtualenv DEST_DIR
   $ source DEST_DIR/bin/activate

You'll need to repeat that activate command each time you want to use
DXR from a new shell.

::

   $ python setup.py install

Magic :envvar:`PATH` munging by the activate script makes this command
operate inside the new Virtualenv environment.


With Vagrant
^^^^^^^^^^^^

You can use Vagrant_ to run DXR inside a preconfigured virtual
machine.

If you want to customize the virtual machine configuration, for
example if you want to turn off NFS, make a copy of the
:file:`vagrantconfig_local.yaml-dist` file named
:file:`vagrantconfig_local.yaml` and edit it::

   $ cp vagrantconfig_local.yaml-dist vagrantconfig_local.yaml

First run the following commands in DXR's top-level directory::

   $ vagrant up
   $ vagrant ssh

Then run the following commands inside the Vagrant virtual machine::

   $ cd ~/dxr
   $ make

.. note::

   The Vagrant image is built for VirtualBox version 4.2.0.  If your
   version is older, the image might not work as expected.


Configure DXR to Generate an Index
----------------------------------

Some minimal configuration is needed before DXR will index any source
code.  It is described in the :doc:`configuration` document.

By default, the :program:`dxr-build.py` script looks for a
:file:`dxr.config` file in the current working directory.

A sample configuration is shipped along with a sample source tree in
the tests/test_basic directory.


Generate a Source Code Index
----------------------------

The :program:`dxr-build.py` script is used to generate a source code
index.  For the best results, it will build your source code with the
`Clang compiler`_ and use Clang's output to generate cross-references.


Without Vagrant
^^^^^^^^^^^^^^^

:program:`dxr-build.py` has a number of runtime dependencies, mostly
Python packages, which are listed in the :file:`requirements.txt`
file.  Again, Virtualenv_ can be used to install these packages in a
self-contained directory instead of installing them system-wide.
Using Virtualenv doesn't require root privileges.

For example, the following command will install
:program:`dxr-build.py`'s runtime dependencies, if you're using
Virtualenv and assuming you've already run it's activate command::

   $ pip install -r requirements.txt

Either pass an :envvar:`LD_LIBRARY_PATH` environment variable to
:program:`dxr-build.py` as follows, or install the libtrilite.so
library onto your system::

   $ LD_LIBRARY_PATH=dxr/trilite dxr-build.py

Otherwise :program:`dxr-build.py` will complain that it can't find the
TriLite SQLite extension.  To install the libtrilite.so library on
Linux, copy it to your /usr/local/lib directory and run
:command:`ldconfig`.

To run :program:`dxr-build.py` from the DXR source tree, without
installing it, pass it a :envvar:`PYTHONPATH` environment variable::

   $ PYTHONPATH=dxr dxr-build.py

Run the :program:`dxr-build.py` script with no options, or run
:command:`dxr-build.py CONFIG_FILE` to specify the configuration
file.  Use the :option:`dxr-build.py --tree TREE` or
:option:`dxr-build.py -t TREE` option to generate the index for just
the named source tree.  This is useful, for example, for building each
source tree on its own server.

The index is generated in the *target_folder* directory.  It contains a
minimal configuration file, an SQLite database for searching the
index, and static HTML versions of all of the files in the source
trees.


With Vagrant
^^^^^^^^^^^^

Run the following commands inside the Vagrant virtual machine to index
a sample source tree::

   $ cd ~/dxr/tests/test_basic
   $ make


Publish the Index on a Web Server
---------------------------------

The :program:`dxr-serve.py` script is a tiny web server for publishing
a generated index.  DXR is also a WSGI application and can be deployed
on Apache with mod_wsgi_ or on uWSGI_ or any other web server that
supports WSGI.

If you're building and hosting your index on separate servers, which
is preferable, you'll need to build at least the TriLite SQLite
extension on the web server as well.  There are also a number of
runtime dependencies, mostly Python packages, which you'll need to
install whether you're using the :program:`dxr-serve.py` script or
WSGI.  Again, Virtualenv_ can be used to install these packages in a
self-contained directory instead of installing them system-wide.
Using Virtualenv doesn't require root privileges.


dxr-serve.py
^^^^^^^^^^^^

Run :command:`dxr-serve.py target` to start the web server and then
surf to http://localhost:8000/.

As with :program:`dxr-build.py` above, either pass an
:envvar:`LD_LIBRARY_PATH` environment variable to
:program:`dxr-serve.py` or install the libtrilite.so library onto your
system::

   $ LD_LIBRARY_PATH=dxr/trilite dxr-serve.py target

To run :program:`dxr-serve.py` from the DXR source tree, without
installing it, pass it a :envvar:`PYTHONPATH` environment variable::

   $ PYTHONPATH=dxr dxr-serve.py target


mod_wsgi
^^^^^^^^

The main mod_wsgi directive is WSGIScriptAlias_ and the DXR WSGI
application is defined in the :file:`dxr/wsgi.py` file, so for
example, add the following to your Apache configuration::

   WSGIScriptAlias / /home/ubuntu/dxr/dxr/wsgi.py

You must also specify the path to the generated index.  This is
accomplished with a :envvar:`DXR_FOLDER` environment variable, so for
example, add to your Apache configuration::

   SetEnv DXR_FOLDER /home/ubuntu/target

As with :program:`dxr-build.py` and :program:`dxr-serve.py` above,
either pass an :envvar:`LD_LIBRARY_PATH` environment variable to
mod_wsgi or install the libtrilite.so library onto your system.
`Because of the ways`_ :envvar:`LD_LIBRARY_PATH` and mod_wsgi work,
adding it to your regular Apache configuration has no effect.  Instead
add the following to your :file:`/etc/apache2/envvars` file::

   export LD_LIBRARY_PATH=/home/ubuntu/dxr/trilite

If you used Virtualenv to install DXR's runtime dependencies, add the
path to the Virtualenv environment to your Apache configuration::

   WSGIPythonHome /home/ubuntu/DEST_DIR

The WSGIPythonHome_ directive is allowed only in the server config
context, not in the virtual host context.  It's analogous to running
Virtualenv's activate command.

To run DXR from its source tree, without installing it, use the
WSGIPythonPath_ directive, which is analogous to the
:envvar:`PYTHONPATH` environment variable::

   WSGIPythonPath /home/ubuntu/dxr

It's also allowed  only in the server config context.

Finally make sure mod_wsgi is installed and enabled and run
:command:`sudo apache2ctl stop; sudo apache2ctl start`.  Changes to
:file:`/etc/apache2/envvars` don't take effect if you only run
:command:`sudo apache2ctl restart`.

Additional configuration might be required, depending on your version
of Apache, your other Apache configuration, and where DXR is
installed.  For example, if you can't access your DXR index and your
Apache error.log contains lines like ``client denied by server
configuration: /home/ubuntu/dxr/dxr/wsgi.py``, try adding to your
Apache configuration::

   <Directory /home/ubuntu/dxr/dxr>
      Require all granted
   </Directory>


uWSGI
^^^^^

.. todo::


With Vagrant
^^^^^^^^^^^^

Run the following commands inside the Vagrant virtual machine to
publish a sample source tree::

   $ cd ~/dxr/tests/test_basic
   $ dxr-serve.py --all target

The :option:`dxr-serve.py --all` option is needed to bind the web
server to all interfaces, otherwise you won't be able to surf the web
server inside the virtual machine from the host machine.

Surf to http://33.33.33.77:8000/ from the host machine and poke around
to your heart's content.  You might need to substitute the address of
your Vagrant virtual machine.

If you see the following error, run :command:`ldconfig` inside the
virtual machine to sort out the shared library linking problem.  Then
restart the :program:`dxr-serve.py` script and all should work as
expected.

::

   Server Error
   Database error: no such module: trilite


.. _Vagrant: http://www.vagrantup.com/

.. _TriLite SQLite extension: https://github.com/jonasfj/trilite

.. _Virtualenv: https://virtualenv.pypa.io/en/latest/

.. _Clang compiler: http://clang.llvm.org/

.. _mod_wsgi: https://code.google.com/p/modwsgi/

.. _uWSGI: http://projects.unbit.it/uwsgi/

.. _WSGIScriptAlias: https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGIScriptAlias

.. _Because of the ways: http://stackoverflow.com/a/7856120/916968

.. _WSGIPythonHome: https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGIPythonHome

.. _WSGIPythonPath: https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGIPythonPath
