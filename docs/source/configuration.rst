=============
Configuration
=============

DXR learns how to index and serve your source trees by means of an ini-formatted
configuration file:

.. include:: example-configuration.rst

When you invoke :program:`dxr index`, it defaults to reading :file:`dxr.config`
in the current directory::

    dxr index

Or you can pass in a config file explicitly::

    dxr index --config /some/place/dxr.config


Sections
========

The configuration file is divided into sections. The ``[DXR]`` section holds
global options; each other section describes a tree to be indexed.

You can use all the fancy interpolation features of Python's
`ConfigParser <http://docs.python.org/library/configparser.html>`__ class to
save repetition.

[DXR] Section
-------------

Here are the options that can live in the ``[DXR]`` section. For options
representing path names, relative paths are relative to the directory
containing the config file.

``disabled_plugins``
    Names of plugins to disable. Default: empty

``enabled_plugins``
    Names of plugins to enable. Default: ``*``

``es_alias``
    A ``format()``-style template for coming up with elasticsearch alias
    names. These live in the same namespace as indices, so don't pave over any
    index name you're already using. The variables ``{format}`` and ``{tree}``
    will be substituted, and their meanings are as in ``es_index``. Default:
    ``dxr_{format}_{tree}``.

``es_index``
    A ``format()``-style template for coming up with elasticsearch index
    names. The variable ``{tree}`` will be replaced with the tree name,
    ``{format}`` will be replaced with the format version, and ``{unique}``
    will be replaced with a unique ID to keep a tree's new index from
    colliding with the old one. The unique ID includes a random number and the
    build hosts's MAC address so errant concurrent builds on different hosts
    at least won't clobber each other. Default: ``dxr_{format}_{tree}_{unique}``

``es_catalog_replicas``
    The number of elasticsearch replicas to make of the :term:`catalog index`.
    This is read often and written only when an indexing run completes, so
    crank it up so there's a replica on every node for best performance. But
    remember that writes will hang if at least half of the attempted copies
    aren't available. Default: ``1``

``es_indexing_timeout``
    The number of seconds DXR should wait for elasticsearch responses during
    indexing. Default: 60

``es_refresh_interval``
    The number of seconds between elasticsearch's consolidation passes during
    indexing. Set to -1 to do no refreshes at all, except directly after an
    indexing run completes. Default: 60

``generated_date``
    The "generated on" date stamped at the bottom of every DXR web page, in
    RFC-822 (also known as RFC 2822) format. Default: the time the indexing run
    started

``log_folder``
    A ``format()``-style template for deciding where to store log files
    written while indexing. The token ``{tree}`` will be replaced with the name
    of the tree being indexed. Default: ``dxr-logs-{tree}`` (in the current
    working directory).

``skip_stages``
    Build/indexing stages to skip, for debugging: ``build``, ``index``, or
    both, whitespace-separated. Default: none

``temp_folder``
    A ``format()``-style template for deciding where to store temporary files
    used while indexing. The token ``{tree}`` will be replaced with the name
    of each tree you index. Default: ``dxr-temp-{tree}``. It's a good idea to
    keep this out of :file:`/tmp` if it's on a small partition, since it can
    grow to tens of gigabytes on a large codebase.

``workers``
    Number of concurrent processes to use for building and indexing projects.
    Default: the number of CPUs on the system. Set to 0 to use no worker
    processes and do everything in the master process. This is handy for
    debugging.

Web App Options That Need a Restart
```````````````````````````````````

These options are used by the DXR web app (though some are used at index time
as well). They are not frozen into the :term:`catalog index` but rather are
read when the web app starts up. Thus, the web app must be restarted to see
new values of these.

``default_tree``
    The tree to redirect to when you visit the root of the site. Default: the
    first tree in the config file

``es_hosts``
    A whitespace-delimited list of elasticsearch nodes to talk to. Be sure to
    include port numbers. Default: http://127.0.0.1:9200/. Remember that you
    can split whitespace-containing things across lines in an ini file by
    leading with spaces.

``es_catalog_index``
     The name to use for the :term:`catalog index`. You probably don't need to
     change this unless you want multiple otherwise-independent DXR
     deployments, with disjoint Switch Tree menus, sharing the same ES
     cluster. Default: ``dxr_catalog``.

``google_analytics_key``
    Google analytics key. If set, the analytics snippet will added
    automatically to every page.

``max_thumbnail_size``
    The file size in bytes at which images will not be used for their icon
    previews on folder browsing pages. Default: 20000.

``www_root``
    URL path prefix to the root of DXR's web app. Example: ``/smoo``. Default:
    empty.


Tree Sections
-------------

Any section not named ``[DXR]`` represents a tree to be indexed. Changes to
per-tree options take effect when the tree is next indexed.

``build_command``
    Command for building your source code. Default: ``make -j {workers}``.
    This is run within ``object_folder``. Note that ``{workers}`` will be
    replaced with ``workers`` from the ``[DXR]`` section (though 1 if
    ``workers`` is set to 0).

``clean_command``
    Command for deleting the build products of ``build_command``, restoring
    things to the pre-built state. Default: ``make clean``. This is run within
    ``object_folder``.

``disabled_plugins``
   Plugins disabled in this tree, in addition to ones already disabled in the
   ``[DXR]`` section. Default: ``*``

``enabled_plugins``
    Plugins enabled in this tree. Default: ``*``, which enables the same
    plugins enabled in the ``[DXR]`` section.

``ignore_patterns``
    Whitespace-separated list of Unix `shell-style
    <http://docs.python.org/library/fnmatch.html>`__ file names or paths to
    ignore. Paths start with a slash, and file names don't. Patterns
    containing whitespace can be expressed by enclosing them in double quotes:
    ``"Lovely readable name.human"``.

``object_folder``
    Folder where the ``build_command`` will be run. This is generally the
    folder where object files will be stored. Default: same as
    ``source_folder``

``source_folder``
    The folder containing the source code to index. **Required.**

``source_encoding``
    The Unicode encoding of the tree's source files. Default: ``utf-8``

``temp_folder``
    A ``format()``-style template for deciding where to store temporary files
    used while indexing. The token ``{tree}`` will be replaced with the name
    of each tree you index. Default: ``temp_folder`` setting from ``[DXR]``
    section. You generally don't need to set this.

``p4web_url``
    The URL to the root of a p4web installation. Default: ``http://p4web/``

Plugin Configuration
====================

Plugin-specific options go in ``[[double-bracketed]]`` sections under trees.
For example... ::

    [some-tree]

        [[buglink]]
        url = http://www.example.com/
        name = Example bug tracker

Currently, changes to plugin configuration take effect at index time or after
restarting the web app; none are picked up by the web app in realtime.

See :ref:`writing-plugins` for more details on plugin development.

[[buglink]]
-----------

``name``
    Name of the tree's bug tracker installation, e.g. ``Mozilla's Bugzilla``

``regex``
    Regex for finding bug references to link in the source code. Default:
    ``(?i)bug\s+#?([0-9]+)``, which catches things like "bug 123456"

``url``
    URL pattern for building links to tickets. ``%s`` will be replaced with the
    ticket number. The option should include the URL scheme.

[[python]]
----------

``python_path``
    Path to the folder from which the codebase imports Python modules
