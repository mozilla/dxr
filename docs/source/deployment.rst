==========
Deployment
==========

.. note::

    The best deployment story probably involves Docker and our setup scripts in
    :file:`tooling/docker/dev/`. However, we haven't got that quite figured out
    yet. Feel free to chip in! In the meantime, enjoy this page about manually
    installing DXR on bare metal.

Once you decide to put DXR into production for use by multiple people, it's
time to move beyond the :doc:`getting-started` instructions. You likely need
a real elasticsearch cluster, and you definitely need a robust web server like
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

You'll need to install several packages on both your build and web servers.
These are the Ubuntu package names, but they should be clear enough to map to
their equivalents on other distributions:

* make
* build-essential
* libclang-dev (clang dev headers). Version 3.5 is recommended, though we
  theoretically support back to 3.2.
* llvm-dev (LLVM dev headers, version 3.5 recommended)
* pkg-config
* npm; node 6.0.0 or higher
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
    :file:`tooling/docker/dev/set_up_ubuntu.sh` in the DXR source tree, which
    does the actual setup of the included container and is automatically
    tested.

Additional Installation
-----------------------

You'll need to install the JavaScript plugin for elasticsearch on your
elasticsearch server (regardless of what type of code you're indexing). The
plugin version you need depends on your version of elasticsearch (see
https://github.com/elastic/elasticsearch-lang-javascript). See
:file:`tooling/docker/es/Dockerfile` for the command currently being used to
install the plugin in our container, something like::

  sudo /usr/share/elasticsearch/bin/plugin --install elasticsearch/elasticsearch-lang-javascript/<version>

where you'll need to insert the appropriate ``<version>``.

(The JavaScript plugin can be uninstalled with ``sudo
/usr/share/elasticsearch/bin/plugin remove lang-javascript``.)

To get all of the DXR tests to pass, or if you're indexing rust code, you'll
also need to install rust.  Refer to
:file:`tooling/docker/dev/set_up_common.sh` for the currently recommended
install command, something like::

  curl -s https://static.rust-lang.org/rustup.sh | sh -s -- --channel=nightly --date=<date> --yes

.. note::

  The 2015-06-14 version of rust has a bug on Fedora-based systems - see
  https://github.com/rust-lang/rust/issues/15684 for a fix if you're
  seeing shared library errors during rust compiles.

(Rust can be uninstalled with ``sudo /usr/local/lib/rustlib/uninstall.sh``.)

Python Packages
---------------

You'll also need several third-party Python packages. In order to isolate the
specific versions we need from the rest of the system, use Virtualenv_::

   virtualenv dxr_venv  # Create a new virtual environment.
   source dxr_venv/bin/activate

You'll need to repeat that :command:`activate` command each time you want to
use DXR from a new shell.


Configuring Elasticsearch
=========================

Elasticsearch is the data store shared between the build and web servers.
Obviously, they both need network access to it. ES tuning is a complex art,
but these pointers should start you off with reasonable performance:

* Give ES its own server. It loves RAM and IO speed. If you want high
  availability or need more power than one machine can provide, set up a
  cluster.
* Configure the following in :file:`/etc/elasticsearch/elasticsearch.yml`:

  * Set ``bootstrap.mlockall`` to ``true``. You don't want any swapping.
  * Set ``script.disable_dynamic`` to ``false``. This enables DXR's use of the
    JavaScript plugin.
  * Whether you intend to set up a cluster or not, beware that ES makes friends
    all too easily. Be sure to change the ``cluster.name`` to something unusual
    and disable autodiscovery by setting
    ``discovery.zen.ping.multicast.enabled`` to ``false``, instead specifying
    your cluster members directly in ``discovery.zen.ping.unicast.hosts``.

* And set the following in :file:`/etc/default/elasticsearch` (for debian-based
  systems) or :file:`/etc/sysconfig/elasticsearch` (for RPM-based
  distributions):

  * Crank up your kernel's max file descriptors::

      MAX_OPEN_FILES=65535
      MAX_LOCKED_MEMORY=unlimited

  * Set :envvar:`ES_HEAP_SIZE` to half of your system RAM, not exceeding 32GB
    (because at that point the JVM can no longer use compressed
    pointers). Giving it one big chunk of RAM up front will avoid heap
    fragmentation and costly reallocations. The remaining memory will easily be
    filled by the OS's file cache as it tussles with Lucene indices.
  * If you have storage constraints, you may want to set :envvar:`DATA_DIR` and
    :envvar:`LOG_DIR` to control where elasticsearch puts its data and logs; the
    defaults are :file:`/var/lib/elasticsearch` and 
    :file:`/var/log/elasticsearch`. Elasticsearch doesn't require much log
    space...until things go wrong.

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

Then, activate the Python virtualenv you made above if you haven't already in
your current login session::

    source dxr_venv/bin/activate

Next, build DXR from its top-level directory::

    make

It will build :file:`libclang-index-plugin.so` in :file:`dxr/plugins/clang`,
compile the JavaScript-based templates, cache-bust the static assets, and
install the Python dependencies.


Installation and Tests
======================

Once you've built it, install DXR in the activated virtualenv::

    pip install --no-deps .

.. note::

    If you intend to develop DXR itself, run ``pip install --no-deps -e .``
    instead. Otherwise, pip will make a copy of the code, severing its
    relationship with the source checkout.

To ensure everything has built correctly and that elasticsearch and other
dependencies are installed and running correctly, you can run the tests. Make
sure elasticsearch is started first, of course. ::

    make test


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

    WSGIPythonHome /home/dxr/dxr/venv
    <VirtualHost *:80>
        # Serve static resources, like CSS and images, with plain Apache:
        Alias /static/ /home/dxr/dxr/dxr/static/

        # Tell DXR where its config file is:
        SetEnv DXR_CONFIG /home/dxr/dxr/tests/test_basic/dxr.config

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
   c. `Installation and Tests`_


.. _Virtualenv: https://virtualenv.pypa.io/en/latest/

.. _mod_wsgi: https://code.google.com/p/modwsgi/

.. _uWSGI: http://projects.unbit.it/uwsgi/

.. _WSGIScriptAlias: https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGIScriptAlias

.. _Because of the ways: http://stackoverflow.com/a/7856120/916968

.. _WSGIPythonHome: https://code.google.com/p/modwsgi/wiki/ConfigurationDirectives#WSGIPythonHome
