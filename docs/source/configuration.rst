=============
Configuration
=============

DXR learns how to index your source trees by means of an ini-formatted
configuration file:

.. include:: example-configuration.rst

It gets passed to :program:`dxr-build.py` at indexing time::

    dxr-build.py my_config_file.config

Sections
========

The configuration file is divided into sections. The ``[DXR]`` section holds
global options; other sections describe trees to be indexed.

You can use all the fancy interpolation features of Python's
`ConfigParser <http://docs.python.org/library/configparser.html>`__ class to
save repetition.

[DXR] Section
-------------

Here are the options that can live in the ``[DXR]`` section:

``target_folder``
    Where to put the built :term:`index`. **Required.**

``temp_folder``
    The default container for individual tree-specific temp folders. Default:
    ``/tmp/dxr-temp``. **Recommended** to avoid exceeding the size of the
    :file:`/tmp` volume and to avoid collisions between concurrent indexing
    runs

``default_tree``
    The tree to redirect to when you visit the root of the site. Default: the
    first tree in the config file

``disabled_plugins``
    Names of plugins to disable. Default: empty

``disable_workers``
    If non-empty, do not use a worker pool for building the static HTML.
    Default: empty

``enabled_plugins``
    Names of plugins to enable. Default: ``*``

``generated_date``
    The "generated on" date stamped at the bottom of every DXR web page, in
    RFC-822 (also known as RFC 2822) format. Default: the time the indexing run
    started

``log_folder``
    The default container for individual tree-specific log folders. Default:
    ``<temp_folder>/logs``.

``workers``
    Number of concurrent processes to use for building and indexing projects.
    Default: the number of CPUs on the system. Set to 0 to use no worker
    processes and do everything in the master process. This is handy for
    debugging.

``skip_stages``
    Build/indexing stages to skip, for debugging: ``build``, ``index``, or
    both, whitespace-separated. Default: none

``www_root``
    URL path prefix to the root of DXR's web app. Default: empty

``google_analytics_key``
  Google analytics key. If set, the analytics snippet will added automatically
  to every page.

``es_alias``
    A ``format()``-style template for coming up with elasticsearch alias
    names. These live in the same namespace as indices, so don't pave over any
    index name you're already using. The variables ``{format}`` and ``{tree}``
    will be substituted, and their meanings are as in ``es_index``. Default:
    ``dxr_{format}_{tree}``.

``es_hosts``
    A whitespace-delimited list of elasticsearch nodes to talk to. Be sure to
    include port numbers. Default: http://127.0.0.1:9200/. Remember that you
    can split whitespace-containing things across lines in an ini file by
    leading with spaces.

``es_index``
    A ``format()``-style template for coming up with elasticsearch index
    names. The variable ``{tree}`` will be replaced with the tree name,
    ``{format}`` will be replaced with the format version, and ``{unique}``
    will be replaced with a unique ID to keep a tree's new index from
    colliding with the old one. The unique ID includes a random number and the
    build hosts's MAC address so errant concurrent builds on different hosts
    at least won't clobber each other. Default: ``dxr_{format}_{tree}_{unique}``

``es_indexing_timeout``
    The number of seconds DXR should wait for elasticsearch responses during
    indexing. Default: 60

``es_refresh_interval``
    The number of seconds between elasticsearch's consolidation passes during
    indexing. Turn this up for higher IO efficiency and fewer segments in the
    final index. Turn it down to avoid timeouts at the end of indexing runs.
    (You can also dodge these by cranking up ``es_indexing_timeout``.) Set to
    -1 to do no refreshes at all, except directly after an indexing run
    completes. Default: 60

``max_thumbnail_size``
    A number that specifies the file size in bytes at which images will not be
    used for their icon previews on folder browsing pages. Default: 20KB.

(Refer to the Plugin Configuration section for plugin keys available here).


Tree Sections
-------------

Any section that is not named ``[DXR]`` represents a tree to be indexed. Here
are the options that can go inside a tree:

``build_command``
    Command for building your source code. Default: ``make -j $jobs``. Note
    that ``$jobs`` will be replaced with ``workers`` from the config file
    (though 1 if ``workers`` is set to 0).

``disabled_plugins``
   Plugins disabled in this tree, in addition to ones already disabled in the
   ``[DXR]`` section. Default: ``*``

``enabled_plugins``
    Plugins enabled in this tree. Default: ``*``. ``*`` enables the same
    plugins enabled in the ``[DXR]`` section.

``ignore_patterns``
    Whitespace-separated list of Unix `shell-style
    <http://docs.python.org/library/fnmatch.html>`__ file names or paths to
    ignore. Paths start with a slash, and file names don't. Patterns
    containing whitespace can be expressed by enclosing them in double quotes:
    ``"Lovely readable name.human"``.

``log_folder``
    Folder for indexing logs. Default: ``<global log_folder>/<tree>``

``object_folder``
    Folder where object files will be stored. **Required.**

``source_folder``
    The folder containing the source code to index. **Required.**

``source_encoding``
    The Unicode encoding of the tree's source files. Default: ``utf-8``

``temp_folder``
    Folder for temporary items made during indexing. Default: ``<global
    temp_folder>/<tree>``. You generally shouldn't set this.


Plugin Configuration
====================

Plugin-specific options go in ``[[double-bracketed]]`` sections under trees.
For example... ::

    [some-tree]

        [[buglink]]
        url = http://www.example.com/
        name = Example bug tracker

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

[[omniglot]]
------------

``p4web_url``
    The URL to the root of a p4web installation. Default: ``http://p4web/``
