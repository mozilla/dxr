==========
Deployment
==========

Once you decide to put DXR into production for use by multiple people, it's
time to move beyond the :doc:`getting-started` instructions. You likely need
real machines—not Vagrant VMs—and you definitely need a robust web server like
Apache. This chapter helps you deploy DXR on the Linux machines [#]_ of your
choice and configure them to handle multi-user traffic volumes.

DXR generates an elasticsearch-dwelling :term:`index` for one or more source
trees as a batch process. This is well suited to a dedicated build server. One
or more web servers then serve pages based on it.

.. [#] DXR might also work with other UNIX-like operating systems, but we make no promises.

Dependencies
============

OS Packages
-----------

Since you're no longer using the Vagrant VM, you'll need to install several
packages on both your build and web servers. These are the Ubuntu package
names, but they should be clear enough to map to their equivalents on other
distributions:

* make
* build-essential
* libclang-dev (clang dev headers). Version 3.5 is recommended, though we
  theoretically support back to 3.2.
* llvm-dev (LLVM dev headers, version 3.5 recommended)
* pkg-config
* npm (Node.js and its package manager)
* openjdk-7-jdk
* elasticsearch 1.1 or higher. The elasticsearch corporation maintains its own
  packages; they aren't often found in distros. Newer is better, though I tend
  to avoid x.0 releases.

Technically, you could probably do without most of these on the web server,
though you'd then need to build DXR itself on a different machine and transfer
it over.

.. note::

   On some systems (for example Debian and Ubuntu) the Node.js interpreter is
   named :program:`nodejs`, but DXR expects it to be named :program:`node`. One
   simple solution is to add a symlink::

      sudo ln -s /usr/bin/nodejs /usr/bin/node

.. note::

    The list of packages above is maintained by hand and might fall behind,
    despite our best efforts. If you suspect something is missing, look at
    :file:`vagrant_provision.sh` in the DXR source tree, which does the actual
    setup of the VM and is automatically tested.

Python Packages
---------------

You'll also need several third-party Python packages. In order to isolate the
specific versions we need from the rest of the system, use
Virtualenv_::

   virtualenv dxr_venv  # Create a new virtual environment.
   source dxr_venv/bin/activate

You'll need to repeat that :command:`activate` command each time you want to
use DXR from a new shell.

Now, with your new virtualenv active, you can install the requisite packages::

    cd dxr
    ./peep.py install -r requirements.txt


Configuring Elasticsearch
=========================

Elasticsearch is the data store shared between the build and web servers.
Obviously, they both need network access to it. ES tuning is a complex art,
but these pointers should start you off with reasonable performance:

* Give ES its own server. It loves RAM and IO speed. If you want high
  availability or need more power than one machine can provide, set up a
  cluster.
* Whether you intend to set up a cluster or not, beware that ES makes friends
  all too easily. Be sure to change the ``cluster.name`` to something unusual
  and disable autodiscovery by setting ``discovery.zen.ping.multicast.enabled``
  to ``false``, instead specifying your cluster members directly in
  ``discovery.zen.ping.unicast.hosts``.
* Crank up your kernel's max file descriptors. Put this in the init script that
  launches ES::

    ulimit -n 65535
    ulimit -l unlimited

  Doing the equivalent in :file:`/etc/security/limits.conf` tends not to work.

* Set :envvar:`ES_HEAP_SIZE` to half of your system RAM, not exceeding 32GB,
  because then the JVM can no longer use compressed pointers. Giving it one
  big chunk of RAM up front will avoid heap fragmentation and costly
  reallocations. The remaining memory will easily be filled by the OS's file
  cache as it tussles with Lucene indices.
* Set ``bootstrap.mlockall`` to ``true``. You don't want any swapping.
* It is often recommended to use Oracle's JVM, but OpenJDK works fine.

DXR will create one index per indexed tree per :term:`format version`.
Reindexing a tree automatically replaces the old index with the new one as its
last step. This happens atomically. Be sure there's enough space on the
cluster to hold both the old and new indices at once during indexing.


Building
========

First, arrange for the correct versions of :command:`llvm-config`,
:command:`clang`, and :command:`clang++` to be available under those names,
whether by a mechanism like Debian's alternatives system or with symlinks.

Then, build DXR from its top-level directory::

    make

It will build :file:`libclang-index-plugin.so` in :file:`dxr/plugins/clang`
and compile the JavaScript-based templates.

To ensure everything has built correctly, you can run the tests::

    make test


Installation
============

Once you've built it, install DXR in the activated virtualenv::

    python setup.py install

.. note::

    If you intend to develop DXR itself, don't ever run ``install``, which
    makes a copy of the code, severing its relationship with the source
    checkout. Do ``python setup.py develop`` instead.


Indexing
========

Now that we've got DXR installed on both the build and web machines, let's talk
about just the build server for a moment.

As in :doc:`getting-started`, copy your projects' source trees to the build
server, and create a config file. (See :doc:`configuration` for details.) Then,
kick off the indexing process::

    dxr index --config dxr.config

.. note::

    You can also append one or more tree names to index just those trees. This
    is useful for parallelization across multiple build servers.

Generally, you use something like cron or Jenkins to repeat indexing on a
schedule or in response to source-tree changes.


Serving Your Index
==================

Now let's set up the web server. Here we have some alternatives.

dxr serve
---------

:program:`dxr serve` runs a tiny web server for publishing an index. Though it
is underpowered for production use, it can come in handy for testing that the
index was built properly and DXR's dependencies are installed::

    dxr serve

Then visit http://localhost:8000/.

Apache and mod_wsgi
-------------------

DXR is also a WSGI application and can be deployed on Apache with mod_wsgi_, on
uWSGI_, or on any other web server that supports the WSGI protocol.

The main mod_wsgi directive is WSGIScriptAlias_, and the DXR WSGI application
is defined in :file:`dxr/wsgi.py`, so an example Apache directive might look
something like this::

   WSGIScriptAlias / /path/to/dxr/dxr/wsgi.py

You must also specify the path to the config file. This is done with the
:envvar:`DXR_CONFIG` environment variable. For example, add this to your Apache
configuration::

   SetEnv DXR_CONFIG /path/to/dxr.config

Because we used virtualenv to install DXR's runtime dependencies, add the path
to the virtualenv to your Apache configuration as well::

   WSGIPythonHome /path/to/dxr_venv

Note that the WSGIPythonHome_ directive is allowed only in the server config
context, not in the virtual host context. It's analogous to running
virtualenv's :program:`activate` command.

Finally, make sure mod_wsgi is installed and enabled. Then, restart Apache::

    sudo service apache2 stop
    sudo service apache2 start


.. note::

    Changes to :file:`/etc/apache2/envvars` don't take effect if you run only
    :command:`sudo service apache2 restart`.

Additional configuration might be required, depending on your version
of Apache, your other Apache configuration, and where DXR is
installed. For example, if you can't access your DXR index and your
Apache error log contains lines like ``client denied by server
configuration: /path/to/dxr/dxr/wsgi.py``, try adding this to your
Apache configuration::

   <Directory /path/to/dxr/dxr>
      Require all granted
   </Directory>

Here is a complete example config, for reference::

    WSGIPythonHome /home/vagrant/dxr_venv
    <VirtualHost *:80>
        # Serve static resources, like CSS and images, with plain Apache:
        Alias /static/ /home/vagrant/dxr/dxr/static/

        # We used to make special efforts to also serve the static pages of
        # HTML-formatted source code from the tree via plain Apache, but that
        # tangle of RewriteRules saved us only about 20ms per request. You can do
        # it if you're on a woefully underpowered machine, but I'm not maintaining
        # it.

        # Tell DXR where its config file is:
        SetEnv DXR_CONFIG /home/vagrant/dxr/tests/test_basic/dxr.config

        WSGIScriptAlias / /usr/local/lib/python2.7/site-packages/dxr/dxr.wsgi
    </VirtualHost>

uWSGI
-----

uWSGI_ is the new hotness and well worth considering. The first person to
deploy DXR under uWSGI should document it here.


Upgrading
=========

To update to a new version of DXR...

1. Update your DXR clone::

    git pull origin master

2. Delete your old virtual env::

    rm -rf /path/to/dxr_venv

3. Repeat these parts of the installation:

   a. `Python Packages`_
   b. `Building`_
   c. `Installation`_


.. _Virtualenv: https://virtualenv.pypa.io/en/latest/

.. _mod_wsgi: https://code.google.com/p/modwsgi/

.. _uWSGI: http://projects.unbit.it/uwsgi/

.. _WSGIScriptAlias: https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGIScriptAlias

.. _Because of the ways: http://stackoverflow.com/a/7856120/916968

.. _WSGIPythonHome: https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGIPythonHome
