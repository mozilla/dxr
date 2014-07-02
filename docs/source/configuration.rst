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

``directory_index``
    Filename for directory index files in the generated static HTML. Default:
    ``.dxr-directory-index.html``

    Resist the temptation to use ``index.html`` for ``directory_index``. Any
    indexed file with the same name would then shadow the directory index,
    confusing users.

``disabled_plugins``
    Names of plugins to disable. Default: empty

``disable_workers``
    If non-empty, do not use a worker pool for building the static HTML.
    Default: empty

``enabled_plugins``
    Names of plugins to enable. Default: ``*``

``filter_lang``
    The default programming language for this instance. Only filters registered
    for this language will be used. Default: ``C``

``generated_date``
    The "generated on" date stamped at the bottom of every DXR web page, in
    RFC-822 (also known as RFC 2822) format. Default: the time the indexing run
    started

``log_folder``
    The default container for individual tree-specific log folders. Default:
    ``<temp_folder>/logs``.

``nb_jobs``
    Number of processes allowed in worker pools. Default: ``1``. This value can
    be overwritten by the :option:`-j` argument to :program:`dxr-build.py`.

``plugin_folder``
    Folder to search for plugins. Default: ``<dxr_root>/plugins``. This will
    soon be deprecated in favor of a new plugin discovery model.

    Please note that :program:`dxr-build.py` assumes the plugins in
    ``plugin_folder`` are already built and ready for use. If you specify your
    own plugin folder, the top-level makefile will not take care of this for
    you.

``skip_stages``
    Build/indexing stages to skip: zero or more of ``index`` and ``html``,
    space-separated. Default: none

``wwwroot``
    URL path prefix to the root of DXR's web app. Default: ``/``

(Refer to the Plugin Configuration section for plugin keys available
here).


Tree Sections
-------------

Any section that is not named ``[DXR]`` represents a tree to be indexed. Here
are the options describing a tree:

``build_command``
    Command for building your source code. Default: ``make -j $jobs``. Note
    that ``$jobs`` will be replaced with ``nb_jobs`` from the config file or
    the value of the :option:`-j` option from the
    :program:`dxr-build.py` command line. If you
    define a ``build_command`` not containing ``$jobs``, you will be warned,
    but indexing will continue.

``disabled_plugins``
   Plugins disabled in this tree, in addition to ones already disabled in the
   ``[DXR]`` section. Default: ``*``

``enabled_plugins``
    Plugins enabled in this tree. Default: ``*``. It is impossible to enable a
    plugin not already enabled in the ``[DXR]`` section.

``ignore_patterns``
    Space-separated list of Unix `shell-style
    <http://docs.python.org/library/fnmatch.html>`__ file patterns to ignore.

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


Plugin-Specific Options
=======================

Options prefixed with ``plugin_`` (except ``plugin_folder``) are reserved for
use by plugins. These options can appear in the global ``[DXR]`` section or in
tree sections. Plugin developers should name their config options like
``plugin_<plugin name>_<option>``. (See :ref:`writing-plugins` for more details
on plugin development.)

At the moment, all the existing plugin options are valid only in tree sections:

``plugin_buglink_name``
    Name of the tree's bug tracker installation, e.g. ``Mozilla's Bugzilla``
    
``plugin_buglink_regex``
    Regex for finding bug references to link in the source code. Default:
    ``(?i)bug\s+#?([0-9]+)``

``plugin_buglink_url``
    URL pattern for building links to tickets. ``%s`` will be replaced with the
    ticket number. The option should include the URL scheme.

``plugin_omniglot_p4web``
    The URL to the root of a p4web installation. Default: ``http://p4web/``
