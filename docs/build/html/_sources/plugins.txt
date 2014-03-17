DXR Plugin Architecture
=======================

*This document describes how to write plugins for DXR.*

Design Philosophy
-----------------

DXR is designed to run as cron job producing builds on the fly without
manual supervision. For this reason, we consider any minor failure
fatal. Otherwise, we would risk DXR silently producing and pushing
garbage builds to production servers. For example, we could ignore a
missing file in a plugin or ignore a single plugin, should it fail to
build, but, for, simplicity we choose to crash instead. Please keep this
principle in mind when designing plugins, and honor it by crashing on
failure.

Required Plugin Files
---------------------

*List of files that must be defined by a plugin.*

A plugin is a folder located in the ``plugin/`` folder, a plugin folder
**must** contain these 3 files.

-  ``makefile`` Make dependencies for this plugin
-  ``indexer.py`` Build database
-  ``htmlifier.py`` Generate metadata for HTML building

Plugins should have a name without dashes or other special characters
not allowed in Python module names. Notice that the plugin folder will
be added to the search path for modules, so plugin names shouldn't
conflict with other modules, and a plugin is able to import submodules
from within its own plugin folder if it contains an ``__init__.py``
file.

Plugin Makefile
---------------

*File for building anything the plugin wants done before indexing.*

This **must** be a GNU makefile with targets ``build``, ``check``, and
``clean`` for building dependencies, verifying the build, and cleaning
up after it, respectively. Operations of this makefile should, insofar
as possible, remain within the plugin's subdirectory.

The targets will be invoked by the top-level makefile, so your plugin
**must** be listed here.

Plugin Indexer
--------------

*Python plugin for pre- and post processing builds, ie. build the
database.*

This must be a python module with two functions
``pre_process(tree, environ)`` and ``post_process(tree, conn)`` where
parameters ``tree`` and ``conn`` are a config for the tree and a
database connection, respectively. The ``environ`` parameter is a
dictionary of environment variables and may be modified prior to build
using by the ``pre_process`` function.

Both functions will be called only once per tree and are allowed to use
a number of subprocess as specified by ``tree.config.nb_jobs``. If a
plugin desires to store information from pre- or post processing, it can
do so in its own temporary directory: each plugin is allowed to use the
temporary folder ``<tree.temp_folder>/plugins/<plugin-name>``. (The
temporary folder will remain until htmlification is done).

Plugin Htmlifier
----------------

*Python plugin for htmlification of source files.*

This must be a python module with two functions ``load(tree, conn)`` and
``htmlify(path, text)``. This module will be used by multiple processes
concurrently, but in any given instance ``load`` will only be invoked
once, to allow the module to load resources into global scope for
simplicity and to facilitate caching.

Once ``load(tree, conn)`` has been invoked with the tree config object
and database connnection, the ``htmlify(conn, path, text)`` function may
be invoked multiple times. The ``path`` parameter is the path of the
file in the tree; the ``text`` parameter is the file contents as string.

The ``htmlify`` function return either ``None`` or an object with
methods ``refs()``, ``regions()``, ``annotations()`` and ``links()``,
which yields as defined below:

-  ``refs()`` Yields tuples of ``(start, end, menu)``
-  ``regions()`` Yields tuples of ``(start, end, class)``
-  ``annotations()`` Yields tuples of ``(line, attributes)`` where
   ``attributes`` is a dictionary defined by plugins. It must be
   sensible to assign the key-value pairs as HTML attributes on a
   ``div`` tag, and ``class`` must contain ``note note-<type>`` where
   ``type`` can be used templates to differentiate annotations.
-  ``links()`` Yields tuples of ``(importance, section, items)``, where
   ``items`` is a generator of tuples of ``(icon, title, href)``.
   ``importance`` is an integer used to sort sidebar sections.

Note that the htmlifier module may not write to the database. It also
strongly recommended that the htmlifier module doesn't write to the
plugins temporary folder. It is a **strict requirement** that the
htmlifier module may be loaded and used by multiple processes at the
same time. For this reason, the htmlifier is not allowed to have worker
processes of its own.

Plugin Configration
-------------------

Configuration keys prefixed with ``plugin_`` in either a tree section or
the DXR section of the configuration will be read and stored on the
``tree`` and ``config`` objects, respectively. Please note that these
values will not have any default values, nor will they be present unless
defined in the config file.

It's the plugins' responsibility to validate these values. Plugins are
advised to prefix all config keys as ``plugin_<plugin-name>_<key>``.
It's also recommended that plugins document their keys in the plugin
section of Configuration.mkd.relatively sane
