==========
Deployment
==========

Once you decide to put DXR into production for use by multiple people, it's
time to move beyond the :doc:`getting-started` instructions. You likely need
real machines—not Vagrant VMs—and you definitely need a robust web server like
Apache. This chapter helps you deploy DXR on the Linux machines [#]_ of your
choice and configure them to handle multi-user traffic volumes.

DXR generates an :term:`index` for one or more source trees offline. This is
well suited to a dedicated build server. The generated index is then
transferred to one or more web servers for hosting.

.. [#] DXR might also work with other UNIX-like operating systems, but we make no promises.

Dependencies
============

OS Packages
-----------

Since you're no longer using the Vagrant VM, you'll need to install several
packages on both your build and web servers. These are the Ubuntu package
names, but they should be clear enough to map to their equivalents on other
distributions:

*  make
*  build-essential
*  libclang-dev (clang dev headers 3.3 or 3.4)
*  llvm-dev (LLVM dev headers 3.3 or 3.4)
*  pkg-config
*  mercurial (to check out re2)
*  libsqlite3-dev
*  npm (Node.js and its package manager)

Technically, you could probably do without most of these on the web server,
though you'd then need to build DXR on a different machine and transfer it over.

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


Building
========

First, if you cannot arrange for the correct versions of :command:`llvm-config`,
:command:`clang`, and :command:`clang++` to be available under those names,
whether by a mechanism like Debian's alternatives system or with symlinks,  you
will need to edit the makefile in :file:`dxr/plugins/clang` to specify complete
paths to the right ones.

Then, build DXR from its top-level directory::

    make

It will build the :file:`libtrilite.so` library in the :file:`trilite`
directory and
:file:`libclang-index-plugin.so` in :file:`dxr/plugins/clang` as well as
compiling the JavaScript-based templates.

To assure yourself that everything has built correctly, you can run the tests::

    make test


Installation
============

Once you've built it, install DXR in the activated virtualenv. This is an
optional step, but it lets you call the :program:`dxr-index.py` and
:program:`dxr-build.py` commands without specifying their full paths, as long as
the env is activated. ::

    python setup.py install

It's also convenient to install the TriLite library globally. Otherwise,
:program:`dxr-build.py` will complain that it can't find the TriLite SQLite
extension unless you prepend ``LD_LIBRARY_PATH=dxr/trilite`` at every
invocation. It's also a challenge to get a web server to see the lib, since you
don't have a ready opportunity to interpose an environment variable. To install
TriLite... ::

    cp dxr/trilite/libtrilite.so /usr/local/lib/
    sudo ldconfig


Indexing
========

Now that we've got DXR installed on both the build and web machines, let's talk
about just the build server for a moment.

As in :doc:`getting-started`, copy your projects' source trees to the build
server, and create a config file. (See :doc:`configuration` for details.) Then,
kick off the indexing process::

    dxr-build.py dxr.config

.. note::

    You can also pass the :option:`--tree TREE` option to generate the index
    for just one source tree. This is useful for building each tree on a
    different machine, though it does leave you with the task of stitching the
    resulting single-tree indexes together, a matter of moving some directories
    around and tweaking the generated :file:`config.py` file.

The index is generated in the directory specified by the ``target_folder``
directive. It contains a minimal configuration file, a SQLite database to
support search, and static HTML versions of all of the files in the source
trees.

Generally, you use something like cron to repeat indexing on a schedule or in
response to source tree changes. After an indexing run, the index has to be
made available to the web servers. One approach is to share it on a common NFS
volume (and use an atomic :command:`mv` to swap the new one into place).
Alternatively, you can simply copy the index to the web server (in which case
an atomic :command:`mv` remains advisable, of course).


Serving Your Index
==================

Now let's set up the web server. Here we have some alternatives.

dxr-serve.py
------------

The :program:`dxr-serve.py` script is a tiny web server for publishing an
index. Though it is underpowered for production use, it can come in handy for
testing that the index arrived undamaged and DXR's dependencies are installed::

    dxr-serve.py target

Then visit http://localhost:8000/.

As with :program:`dxr-build.py` above, you can pass an
:envvar:`LD_LIBRARY_PATH` environment variable to :program:`dxr-serve.py` if you
are unable to install the TriLite library globally on your system::

    LD_LIBRARY_PATH=dxr/trilite dxr-serve.py target

Apache and mod_wsgi
-------------------

DXR is also a WSGI application and can be deployed on Apache with mod_wsgi_, on
uWSGI_, or on any other web server that supports the WSGI protocol.

The main mod_wsgi directive is WSGIScriptAlias_, and the DXR WSGI application
is defined in :file:`dxr/wsgi.py`, so an example Apache directive might look
something like this::

   WSGIScriptAlias / /path/to/dxr/dxr/wsgi.py

You must also specify the path to the generated index. This is done with a
:envvar:`DXR_FOLDER` environment variable. For example, add this to your Apache
configuration::

   SetEnv DXR_FOLDER /path/to/target

As with :program:`dxr-build.py` and :program:`dxr-serve.py` above, either pass
an :envvar:`LD_LIBRARY_PATH` environment variable to mod_wsgi, or install the
:file:`libtrilite.so` library onto your system globally. `Because of the ways`_
:envvar:`LD_LIBRARY_PATH` and mod_wsgi work, adding it to your regular Apache
configuration has no effect. Instead, add the following to
:file:`/etc/apache2/envvars`::

   export LD_LIBRARY_PATH=/path/to/dxr/trilite

Because we used virtualenv to install DXR's runtime dependencies, add the path
to the virtualenv to your Apache configuration::

   WSGIPythonHome /path/to/dxr_venv

Note that the WSGIPythonHome_ directive is allowed only in the server config
context, not in the virtual host context. It's analogous to running virtualenv's
:program:`activate` command.

Finally, make sure mod_wsgi is installed and enabled. Then, restart Apache::

    sudo apache2ctl stop
    sudo apache2ctl start


.. note::

    Changes to :file:`/etc/apache2/envvars` don't take effect if you run only
    :command:`sudo apache2ctl restart`.

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

        # Tell this instance of DXR where its target folder is:
        SetEnv DXR_FOLDER /home/vagrant/dxr/tests/test_basic/target/

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
    git submodule update

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
